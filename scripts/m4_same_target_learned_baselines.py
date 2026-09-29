"""Matched learned baselines for the cursor-only AdSERP click target.

This experiment holds the paper's press-anchored M4 protocol fixed and changes
only the representation or estimator.  It is intentionally separate from
``m4_cursor_aoi_rerun.py``: that producer remains the authority for cohort,
labels, cursor cutoff, AOI geometry, and the canonical seven-feature vector.

The default benchmark contains three controls:

* ``m4_lightgbm``: nonlinear capacity control on the seven M4 scalars;
* ``relative_flat_lgbm``: fixed LightGBM over the ordered, resampled
  candidate-relative d_i(t) sequence;
* ``global_flat_lgbm``: the same estimator over one global cursor sequence plus
  the candidate AOI center.

The two flattened controls intentionally retain the last pre-buffer sample.
They answer the literal same-stream learned-baseline question, while the
canonical M4-9 result quantifies how strongly any endpoint-aware learner can
exploit the final-distance cue even 500 ms before the press.

Optional terminal-screened temporal encoders use circular convolutions followed by global mean/max
pooling.  This keeps local ordered motion while making the representation
invariant to a cyclic shift, so it cannot single out the final retained sample.
That constraint is necessary for parity with M4's leakage screen: an ordinary
endpoint-aware GRU immediately reconstructs the excluded ``final_dist`` proxy.
The CLI retains ``*_gru_endpoint`` models only as explicit leakage diagnostics;
they are not part of the default comparison.

All models use the same 2,608 trials / 34,328 AOI rows, final-click label,
native mousemove stream ending 500 ms before mousedown, and 47 participant-held
out folds as the canonical M4 result.  Deep-model epoch selection uses only
participants inside each outer training fold, then the chosen epoch count is
retrained on every outer-training participant.  The output contains aggregate
metrics and hashes only; the ignored cache/checkpoints contain derived rows.

Run from the repository root:

    uv run --extra learned-baselines python scripts/m4_same_target_learned_baselines.py

Use ``--prepare-only`` to build and verify the ignored derived cache first.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import warnings

# This checkout shares a workstation with other research jobs.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - exercised by CLI environments
    raise SystemExit(
        "PyTorch is required for the learned baselines. Run with "
        "`uv run --extra learned-baselines ...`."
    ) from exc

# Import LightGBM after PyTorch.  On macOS arm64, loading LightGBM's OpenMP
# runtime first and then executing a PyTorch GRU can segfault in native code.
# The reverse order is covered by the focused training smoke test.
import lightgbm as lgb  # noqa: E402

from m4_cursor_aoi_rerun import (  # noqa: E402
    APPROACH_7,
    load_flavor_cards,
    paired_comparison,
    prepare_trial,
    sha256,
    track_batch,
)


SCHEMA_VERSION = 1
BUFFER_MS = 500
COHORT_BUFFERS_MS = (0, 250, 500, 1000)
DEFAULT_SEEDS = (1729, 2718, 3141)
DEFAULT_MODELS = ("m4_lightgbm", "relative_flat_lgbm", "global_flat_lgbm")
MODEL_CHOICES = DEFAULT_MODELS + (
    "relative_tcn", "global_tcn", "relative_gru_endpoint", "global_gru_endpoint"
)
VELOCITY_SCALE_DOCS_PER_S = 5.0


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:4], "little") & 0x7FFFFFFF


def canonical_paths(root: Path) -> dict[str, Path]:
    return {
        "producer": root / "scripts/m4_cursor_aoi_rerun.py",
        "bridge": root / "scripts/m4_cursor_tracker.mjs",
        "tracker": root.parent / "approach-retreat/src/approach-retreat.js",
        "data_loader": root / "notebooks-v2/data_loader.py",
        "substrate": root / "data/aoi-typed/substrate.json",
        "exclusions": root / "data/aoi-typed/alignment-exclusions.json",
    }


def verify_canonical_sources(root: Path, canonical: dict) -> dict[str, str]:
    current = {name: sha256(path) for name, path in canonical_paths(root).items()}
    expected = canonical["provenance"]["sha256"]
    if current != expected:
        changed = {k: {"current": current.get(k), "expected": expected.get(k)}
                   for k in sorted(set(current) | set(expected))
                   if current.get(k) != expected.get(k)}
        raise ValueError(f"Canonical M4 sources drifted from the headline sidecar: {changed}")
    return current


def resample_cursor(samples: list[list[float]], center: float | None,
                    document_height: float, steps: int) -> np.ndarray:
    """Clock-time interpolation of the retained stream into two channels.

    Global sequences use normalized cursor y and signed cursor velocity.
    Relative sequences use normalized |cursor y - AOI center| and signed
    approach velocity.  Velocity is clipped/scaled symmetrically only to keep
    the neural input bounded; no click or gaze information enters.
    """
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if len(samples) < 2:
        raise ValueError("at least two retained mousemove samples are required")
    if not math.isfinite(document_height) or document_height <= 0:
        raise ValueError("document_height must be positive and finite")
    ts = np.asarray([s[0] for s in samples], dtype=np.float64)
    ys = np.asarray([s[1] for s in samples], dtype=np.float64)
    if np.any(np.diff(ts) < 0):
        raise ValueError("sample timestamps must be monotone")
    # np.interp accepts duplicate source timestamps.  The canonical JS tracker
    # also preserves them; a uniform target grid is the declared learned-model
    # representation rather than a hidden edit to the native M4 stream.
    target_t = np.linspace(ts[0], ts[-1], steps, dtype=np.float64)
    values = np.interp(target_t, ts, ys)
    if center is None:
        level = values / document_height
        signed_velocity = np.gradient(values, target_t / 1000.0) / document_height
    else:
        level = np.abs(values - center) / document_height
        signed_velocity = -np.gradient(level, target_t / 1000.0)
    signed_velocity = np.clip(
        signed_velocity, -VELOCITY_SCALE_DOCS_PER_S, VELOCITY_SCALE_DOCS_PER_S
    ) / VELOCITY_SCALE_DOCS_PER_S
    return np.column_stack([level, signed_velocity]).astype(np.float32)


def trial_aux(samples: list[list[float]]) -> np.ndarray:
    duration_s = max((samples[-1][0] - samples[0][0]) / 1000.0, 0.0)
    # Fixed denominators come from the declared physical domain, not corpus-fit
    # statistics, so they cannot leak the outer participant.
    return np.asarray([
        np.clip(duration_s / 80.0, 0.0, 2.0),
        np.clip(np.log1p(len(samples)) / np.log1p(2000.0), 0.0, 1.5),
    ], dtype=np.float32)


def dataset_config(steps: int) -> dict:
    return {
        "buffer_ms": BUFFER_MS,
        "cohort_buffers_ms": list(COHORT_BUFFERS_MS),
        "anchor_event": "mousedown",
        "sampling": "native mousemove",
        "axis": "vertical document CSS px",
        "resampling": "linear interpolation on clock time from first to last retained sample",
        "steps": steps,
        "global_channels": ["cursor_y / document_height", "cursor_velocity / document_height / 5"],
        "relative_channels": ["abs(cursor_y - AOI_center) / document_height",
                              "approach_velocity / document_height / 5"],
        "aux_channels": ["duration_s / 80", "log1p(sample_count) / log1p(2000)"],
        "candidate_metadata_global": ["AOI_center_y / document_height"],
        "gaze_used": False,
    }


def cache_metadata(cache: np.lib.npyio.NpzFile) -> dict:
    return json.loads(str(cache["metadata_json"].item()))


def load_cache(path: Path, expected: dict) -> dict[str, np.ndarray | dict]:
    with np.load(path, allow_pickle=False) as cache:
        metadata = cache_metadata(cache)
        if metadata["dataset_config"] != expected["dataset_config"]:
            raise ValueError("Prepared cache representation config does not match this run")
        if metadata["canonical_source_sha256"] != expected["canonical_source_sha256"]:
            raise ValueError("Prepared cache canonical source hashes do not match this run")
        arrays = {name: cache[name].copy() for name in cache.files if name != "metadata_json"}
    arrays["metadata"] = metadata
    return arrays


def save_cache(path: Path, arrays: dict[str, np.ndarray], metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata)))


def build_cache(root: Path, cache_path: Path, steps: int,
                canonical: dict, canonical_hashes: dict[str, str]) -> dict:
    sys.path.insert(0, str(root / "notebooks-v2"))
    import data_loader as dl

    started = time.monotonic()
    exclusions = dl.typed_alignment_exclusions()
    bridge = root / "scripts/m4_cursor_tracker.mjs"
    tracker = root.parent / "approach-retreat/src/approach-retreat.js"
    raw_trials: list[dict] = []
    prepared: list[dict] = []
    records: list[dict] = []
    counts: dict[str, int] = {}

    def count(reason: str) -> None:
        counts[reason] = counts.get(reason, 0) + 1

    def flush() -> None:
        if not raw_trials:
            return
        results = track_batch(raw_trials, bridge, tracker)
        for result in results:
            records.extend(result[f"buf{BUFFER_MS}"])
        raw_trials.clear()

    tids = dl.get_trial_ids()
    for i, tid in enumerate(tids):
        if tid in exclusions:
            count("alignment_excluded")
            continue
        cards = load_flavor_cards(dl, tid, "typed")
        if not cards:
            count("no_measured_aoi_map_for_flavor")
            continue
        geometry = dl.get_trial_geometry(tid)
        if geometry is None:
            raise ValueError(f"{tid}: missing coordinate geometry")
        events, _, clicks = dl.load_mouse_events(tid, space="document")
        trial, reason = prepare_trial(
            tid, cards, events, clicks, geometry, list(COHORT_BUFFERS_MS), anchor="mousedown"
        )
        count(reason)
        if trial is None:
            continue
        samples = [s for s in trial["samples"] if s[0] < trial["anchor_t"] - BUFFER_MS]
        if len({s[0] for s in samples}) < 2:
            raise ValueError(f"{tid}: canonical cohort lacks two buf500 timestamps")
        doc_height = float(geometry["doc_height"])
        if not math.isfinite(doc_height) or doc_height <= 0:
            raise ValueError(f"{tid}: invalid document height")
        prepared.append({
            "trial_id": tid,
            "participant": tid.split("-")[0],
            "samples": samples,
            "document_height": doc_height,
            "aois": copy.deepcopy(trial["aois"]),
            "click_position": trial["click_position"],
        })
        tracker_trial = copy.deepcopy(trial)
        tracker_trial["buffers_ms"] = [BUFFER_MS]
        raw_trials.append(tracker_trial)
        if len(raw_trials) >= 25:
            flush()
        if (i + 1) % 500 == 0:
            print(f"prepare {i + 1}/{len(tids)} trials; {len(prepared)} included", flush=True)
    flush()

    record_hash = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    expected_record_hash = canonical["provenance"]["feature_records_sha256"][f"buf{BUFFER_MS}"]
    if record_hash != expected_record_hash:
        raise ValueError(
            f"Prepared M4 record hash {record_hash} != canonical {expected_record_hash}"
        )
    expected_n = canonical["conditions"][f"buf{BUFFER_MS}"]["M4-7"]["n_records"]
    if len(records) != expected_n:
        raise ValueError(f"Prepared {len(records)} rows, expected {expected_n}")
    expected_trials = canonical["conditions"][f"buf{BUFFER_MS}"]["M4-7"]["n_ranked_trials"]
    if len(prepared) != expected_trials:
        raise ValueError(f"Prepared {len(prepared)} trials, expected {expected_trials}")

    max_candidates = max(len(t["aois"]) for t in prepared)
    n = len(prepared)
    global_seq = np.zeros((n, steps, 2), dtype=np.float32)
    relative_seq = np.zeros((n, max_candidates, steps, 2), dtype=np.float32)
    centers = np.zeros((n, max_candidates), dtype=np.float32)
    positions = np.full((n, max_candidates), -1, dtype=np.int16)
    m4_features = np.zeros((n, max_candidates, len(APPROACH_7)), dtype=np.float32)
    labels = np.zeros((n, max_candidates), dtype=np.float32)
    mask = np.zeros((n, max_candidates), dtype=bool)
    aux = np.zeros((n, 2), dtype=np.float32)
    trial_ids = np.asarray([t["trial_id"] for t in prepared])
    participants = np.asarray([t["participant"] for t in prepared])

    cursor = 0
    for i, trial in enumerate(prepared):
        aois = trial["aois"]
        trial_records = records[cursor:cursor + len(aois)]
        cursor += len(aois)
        global_seq[i] = resample_cursor(
            trial["samples"], None, trial["document_height"], steps
        )
        aux[i] = trial_aux(trial["samples"])
        for j, (aoi, record) in enumerate(zip(aois, trial_records)):
            if (record["trial_id"], record["position"]) != (trial["trial_id"], aoi["position"]):
                raise ValueError("Tracker record order differs from prepared AOI order")
            center = float(aoi["center_document_y"])
            mask[i, j] = True
            positions[i, j] = int(aoi["position"])
            labels[i, j] = float(record["was_clicked"])
            centers[i, j] = center / trial["document_height"]
            relative_seq[i, j] = resample_cursor(
                trial["samples"], center, trial["document_height"], steps
            )
            m4_features[i, j] = [float(record[name]) for name in APPROACH_7]
        if labels[i, mask[i]].sum() != 1:
            raise ValueError(f"{trial['trial_id']}: expected exactly one clicked AOI")
    if cursor != len(records):
        raise ValueError("Not every tracker record was consumed")

    keys = [(records[i]["trial_id"], records[i]["position"], records[i]["was_clicked"])
            for i in range(len(records))]
    key_hash = hashlib.sha256(json.dumps(keys).encode()).hexdigest()
    expected_key_hash = canonical["provenance"]["record_keys_and_labels_sha256"]
    if key_hash != expected_key_hash:
        raise ValueError(f"Record key/label hash {key_hash} != canonical {expected_key_hash}")
    local_after = {name: sha256(path) for name, path in canonical_paths(root).items()}
    if local_after != canonical_hashes:
        raise RuntimeError("Canonical source changed while the cache was prepared")

    arrays = {
        "global_seq": global_seq,
        "relative_seq": relative_seq,
        "centers": centers,
        "positions": positions,
        "m4_features": m4_features,
        "labels": labels,
        "mask": mask,
        "aux": aux,
        "trial_ids": trial_ids,
        "participants": participants,
    }
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dataset_config": dataset_config(steps),
        "canonical_source_sha256": canonical_hashes,
        "canonical_summary_sha256": sha256(
            root / "scripts/output/m4_cursor_aoi_mousedown/summary.json"
        ),
        "feature_records_sha256": record_hash,
        "record_keys_and_labels_sha256": key_hash,
        "counts": {"discovered_trials": len(tids), **counts,
                   "records": int(mask.sum()), "max_candidates": max_candidates},
        "preparation_seconds": time.monotonic() - started,
    }
    save_cache(cache_path, arrays, metadata)
    arrays["metadata"] = metadata
    print(f"Prepared and verified cache: {cache_path}", flush=True)
    return arrays


def flatten_valid(data: dict, values: np.ndarray) -> np.ndarray:
    return np.asarray(values)[data["mask"]]


def ranking_metrics(data: dict, scores: np.ndarray,
                    trial_indices: np.ndarray | None = None) -> dict:
    if trial_indices is None:
        trial_indices = np.arange(len(data["trial_ids"]))
    reciprocal_ranks: list[float] = []
    top1: list[float] = []
    for i in trial_indices:
        valid = np.flatnonzero(data["mask"][i])
        order = sorted(valid, key=lambda j: (-float(scores[i, j]), int(data["positions"][i, j])))
        clicked = [rank for rank, j in enumerate(order, start=1) if data["labels"][i, j] == 1]
        if len(clicked) != 1:
            raise ValueError("Expected exactly one clicked AOI per ranked trial")
        rank = clicked[0]
        reciprocal_ranks.append(1.0 / rank if rank <= 10 else 0.0)
        top1.append(float(rank == 1))
    return {
        "mrr_at_10": float(np.mean(reciprocal_ranks)),
        "ndcg_at_1": float(np.mean(top1)),
        "n_ranked_trials": len(reciprocal_ranks),
    }


def metric_bundle(data: dict, scores: np.ndarray) -> tuple[dict, dict[str, float]]:
    y = flatten_valid(data, data["labels"])
    p = flatten_valid(data, scores)
    if not np.isfinite(p).all():
        raise ValueError("Missing or nonfinite held-out scores")
    participants = data["participants"]
    folds: dict[str, float] = {}
    for pid in sorted(set(participants.tolist())):
        trial_idx = np.flatnonzero(participants == pid)
        fold_y = data["labels"][trial_idx][data["mask"][trial_idx]]
        fold_p = scores[trial_idx][data["mask"][trial_idx]]
        if len(set(fold_y.tolist())) == 2:
            folds[str(pid)] = float(roc_auc_score(fold_y, fold_p))
    fold_auc = np.asarray(list(folds.values()))
    metrics = {
        "pooled_auc": float(roc_auc_score(y, p)),
        "pooled_average_precision": float(average_precision_score(y, p)),
        "n_records": int(len(y)),
        "n_clicks": int(y.sum()),
        "n_folds": len(folds),
        "fold_auc_mean": float(fold_auc.mean()),
        "fold_auc_sd": float(fold_auc.std(ddof=1)),
        "fold_auc_median": float(np.median(fold_auc)),
        "fold_auc_iqr": np.quantile(fold_auc, [.25, .75]).tolist(),
        **ranking_metrics(data, scores),
    }
    return metrics, folds


def sklearn_oof(data: dict, feature_name: str) -> np.ndarray:
    if feature_name == "position":
        features = data["positions"].astype(np.float64)[..., None]
    elif feature_name == "m4":
        features = data["m4_features"].astype(np.float64)
    else:
        raise ValueError(feature_name)
    valid = data["mask"]
    X = features[valid]
    y = data["labels"][valid].astype(int)
    row_groups = np.repeat(data["participants"][:, None], valid.shape[1], axis=1)[valid]
    scores = np.full(valid.shape, np.nan, dtype=np.float64)
    flat_scores = np.full(len(y), np.nan, dtype=np.float64)
    for pid in sorted(set(row_groups.tolist())):
        test = row_groups == pid
        train = ~test
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0),
        )
        model.fit(X[train], y[train])
        flat_scores[test] = model.predict_proba(X[test])[:, 1]
    scores[valid] = flat_scores
    return scores


def lightgbm_oof(data: dict, seed: int) -> tuple[np.ndarray, dict]:
    valid = data["mask"]
    X = data["m4_features"][valid]
    y = data["labels"][valid].astype(int)
    row_groups = np.repeat(data["participants"][:, None], valid.shape[1], axis=1)[valid]
    flat_scores = np.full(len(y), np.nan, dtype=np.float64)
    config = {
        "n_estimators": 200,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_child_samples": 100,
        "reg_lambda": 1.0,
        "class_weight": "balanced",
    }
    for pid in sorted(set(row_groups.tolist())):
        test = row_groups == pid
        train = ~test
        model = lgb.LGBMClassifier(
            **config, random_state=seed, n_jobs=1, verbosity=-1,
            deterministic=True, force_col_wise=True,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="X does not have valid feature names.*", category=UserWarning
            )
            model.fit(X[train], y[train])
            flat_scores[test] = model.predict_proba(X[test])[:, 1]
    scores = np.full(valid.shape, np.nan, dtype=np.float64)
    scores[valid] = flat_scores
    return scores, config


def flattened_trajectory_features(data: dict, kind: str) -> np.ndarray:
    """Return valid per-candidate rows while preserving resampled time order."""
    valid = data["mask"]
    n_trials, max_candidates = valid.shape
    repeated_aux = np.broadcast_to(
        data["aux"][:, None, :], (n_trials, max_candidates, data["aux"].shape[-1])
    )
    if kind == "relative_flat_lgbm":
        sequence = data["relative_seq"].reshape(n_trials, max_candidates, -1)
        return np.concatenate([sequence, repeated_aux], axis=-1)[valid]
    if kind == "global_flat_lgbm":
        sequence = data["global_seq"].reshape(n_trials, -1)
        repeated_sequence = np.broadcast_to(
            sequence[:, None, :], (n_trials, max_candidates, sequence.shape[-1])
        )
        return np.concatenate(
            [repeated_sequence, data["centers"][..., None], repeated_aux], axis=-1
        )[valid]
    raise ValueError(kind)


def flattened_trajectory_lightgbm_oof(
    data: dict, kind: str, seed: int
) -> tuple[np.ndarray, dict]:
    valid = data["mask"]
    X = flattened_trajectory_features(data, kind)
    y = data["labels"][valid].astype(int)
    row_groups = np.repeat(data["participants"][:, None], valid.shape[1], axis=1)[valid]
    flat_scores = np.full(len(y), np.nan, dtype=np.float64)
    config = {
        "n_estimators": 200,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_child_samples": 100,
        "reg_lambda": 1.0,
        "class_weight": "balanced",
        "sequence_steps": int(data["global_seq"].shape[1]),
        "terminal_index_policy": "endpoint-aware; ordered raw pre-buffer sequence",
    }
    fit_config = {k: v for k, v in config.items()
                  if k not in ("sequence_steps", "terminal_index_policy")}
    for pid in sorted(set(row_groups.tolist())):
        test = row_groups == pid
        train = ~test
        model = lgb.LGBMClassifier(
            **fit_config, random_state=seed, n_jobs=1, verbosity=-1,
            deterministic=True, force_col_wise=True,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="X does not have valid feature names.*", category=UserWarning
            )
            model.fit(X[train], y[train])
            flat_scores[test] = model.predict_proba(X[test])[:, 1]
    scores = np.full(valid.shape, np.nan, dtype=np.float64)
    scores[valid] = flat_scores
    return scores, config


class RelativeGRU(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.gru = nn.GRU(2, hidden_size, batch_first=True)
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size + 2),
            nn.Linear(hidden_size + 2, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, relative_seq: torch.Tensor, global_seq: torch.Tensor,
                centers: torch.Tensor, aux: torch.Tensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        del global_seq, centers
        b, c, t, f = relative_seq.shape
        flat = relative_seq.reshape(b * c, t, f)
        if mask is None:
            _, hidden = self.gru(flat)
            encoded = hidden[-1]
        else:
            valid = mask.reshape(-1)
            _, hidden = self.gru(flat[valid])
            encoded = torch.zeros(b * c, hidden.shape[-1], device=flat.device)
            encoded[valid] = hidden[-1]
        encoded = encoded.reshape(b, c, -1)
        expanded_aux = aux[:, None, :].expand(-1, c, -1)
        return self.head(torch.cat([encoded, expanded_aux], dim=-1)).squeeze(-1)


class GlobalGRU(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.gru = nn.GRU(2, hidden_size, batch_first=True)
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size + 3),
            nn.Linear(hidden_size + 3, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, relative_seq: torch.Tensor, global_seq: torch.Tensor,
                centers: torch.Tensor, aux: torch.Tensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        del relative_seq
        del mask
        _, hidden = self.gru(global_seq)
        c = centers.shape[1]
        encoded = hidden[-1][:, None, :].expand(-1, c, -1)
        expanded_aux = aux[:, None, :].expand(-1, c, -1)
        return self.head(torch.cat([encoded, centers[..., None], expanded_aux], dim=-1)).squeeze(-1)


class CircularTemporalEncoder(nn.Module):
    """Local order encoder whose pooled representation has no terminal index."""
    def __init__(self, hidden_size: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(2, hidden_size, kernel_size=5, padding=2, padding_mode="circular"),
            nn.GELU(),
        )

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        encoded = self.network(sequence.transpose(1, 2))
        return torch.cat([encoded.mean(dim=-1), encoded.amax(dim=-1)], dim=-1)


class RelativeTCN(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.encoder = CircularTemporalEncoder(hidden_size)
        self.head = nn.Sequential(
            nn.LayerNorm(2 * hidden_size + 2),
            nn.Linear(2 * hidden_size + 2, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, relative_seq: torch.Tensor, global_seq: torch.Tensor,
                centers: torch.Tensor, aux: torch.Tensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        del global_seq, centers
        b, c, t, f = relative_seq.shape
        flat = relative_seq.reshape(b * c, t, f)
        if mask is None:
            encoded = self.encoder(flat)
        else:
            valid = mask.reshape(-1)
            valid_encoded = self.encoder(flat[valid])
            encoded = torch.zeros(b * c, valid_encoded.shape[-1], device=flat.device)
            encoded[valid] = valid_encoded
        encoded = encoded.reshape(b, c, -1)
        expanded_aux = aux[:, None, :].expand(-1, c, -1)
        return self.head(torch.cat([encoded, expanded_aux], dim=-1)).squeeze(-1)


class GlobalTCN(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.encoder = CircularTemporalEncoder(hidden_size)
        self.head = nn.Sequential(
            nn.LayerNorm(2 * hidden_size + 3),
            nn.Linear(2 * hidden_size + 3, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, relative_seq: torch.Tensor, global_seq: torch.Tensor,
                centers: torch.Tensor, aux: torch.Tensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        del relative_seq
        del mask
        encoded = self.encoder(global_seq)
        c = centers.shape[1]
        expanded = encoded[:, None, :].expand(-1, c, -1)
        expanded_aux = aux[:, None, :].expand(-1, c, -1)
        return self.head(
            torch.cat([expanded, centers[..., None], expanded_aux], dim=-1)
        ).squeeze(-1)


def make_model(kind: str, hidden_size: int) -> nn.Module:
    if kind == "relative_tcn":
        return RelativeTCN(hidden_size)
    if kind == "global_tcn":
        return GlobalTCN(hidden_size)
    if kind == "relative_gru_endpoint":
        return RelativeGRU(hidden_size)
    if kind == "global_gru_endpoint":
        return GlobalGRU(hidden_size)
    raise ValueError(kind)


def set_torch_seed(seed: int, threads: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)


def tensor_batch(data: dict, indices: np.ndarray, device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "relative_seq": torch.as_tensor(data["relative_seq"][indices], device=device),
        "global_seq": torch.as_tensor(data["global_seq"][indices], device=device),
        "centers": torch.as_tensor(data["centers"][indices], device=device),
        "aux": torch.as_tensor(data["aux"][indices], device=device),
        "labels": torch.as_tensor(data["labels"][indices], device=device),
        "mask": torch.as_tensor(data["mask"][indices], device=device),
    }


def fit_epochs(data: dict, kind: str, train_indices: np.ndarray, seed: int,
               epochs: int, batch_size: int, hidden_size: int,
               learning_rate: float, weight_decay: float,
               device: torch.device, threads: int) -> nn.Module:
    set_torch_seed(seed, threads)
    model = make_model(kind, hidden_size).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    train_mask = data["mask"][train_indices]
    train_labels = data["labels"][train_indices][train_mask]
    positives = float(train_labels.sum())
    pos_weight = torch.tensor((len(train_labels) - positives) / positives, device=device)
    for epoch in range(epochs):
        model.train()
        order = np.random.default_rng(stable_seed(seed, epoch, "batches")).permutation(train_indices)
        for start in range(0, len(order), batch_size):
            batch = tensor_batch(data, order[start:start + batch_size], device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch["relative_seq"], batch["global_seq"],
                           batch["centers"], batch["aux"], batch["mask"])
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits[batch["mask"]], batch["labels"][batch["mask"]],
                pos_weight=pos_weight,
            )
            loss.backward()
            optimizer.step()
    return model


@torch.inference_mode()
def predict_trials(model: nn.Module, data: dict, indices: np.ndarray,
                   batch_size: int, device: torch.device) -> np.ndarray:
    model.eval()
    scores = np.full(data["mask"].shape, np.nan, dtype=np.float64)
    for start in range(0, len(indices), batch_size):
        current = indices[start:start + batch_size]
        batch = tensor_batch(data, current, device)
        logits = model(batch["relative_seq"], batch["global_seq"],
                       batch["centers"], batch["aux"], batch["mask"])
        probs = torch.sigmoid(logits).cpu().numpy()
        for local, trial_index in enumerate(current):
            scores[trial_index, data["mask"][trial_index]] = probs[local, data["mask"][trial_index]]
    return scores


def select_epoch(data: dict, kind: str, outer_train: np.ndarray,
                 inner_validation: np.ndarray, seed: int, args) -> tuple[int, float]:
    inner_train = np.setdiff1d(outer_train, inner_validation, assume_unique=False)
    set_torch_seed(seed, args.threads)
    model = make_model(kind, args.hidden_size).to(args.device_obj)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    train_labels = data["labels"][inner_train][data["mask"][inner_train]]
    positives = float(train_labels.sum())
    pos_weight = torch.tensor((len(train_labels) - positives) / positives, device=args.device_obj)
    best_auc = -math.inf
    best_epoch = 1
    stale = 0
    for epoch in range(1, args.max_epochs + 1):
        model.train()
        order = np.random.default_rng(stable_seed(seed, epoch, "selection")).permutation(inner_train)
        for start in range(0, len(order), args.batch_size):
            batch = tensor_batch(data, order[start:start + args.batch_size], args.device_obj)
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch["relative_seq"], batch["global_seq"],
                           batch["centers"], batch["aux"], batch["mask"])
            loss = nn.functional.binary_cross_entropy_with_logits(
                logits[batch["mask"]], batch["labels"][batch["mask"]],
                pos_weight=pos_weight,
            )
            loss.backward()
            optimizer.step()
        validation_scores = predict_trials(
            model, data, inner_validation, args.batch_size, args.device_obj
        )
        validation_y = data["labels"][inner_validation][data["mask"][inner_validation]]
        validation_p = validation_scores[inner_validation][data["mask"][inner_validation]]
        validation_auc = float(roc_auc_score(validation_y, validation_p))
        # ``min_epochs`` is a floor on the selected retraining duration, not
        # merely a delay before the patience counter can stop.  The pilot that
        # allowed epoch 1--4 selections produced predictably undertrained,
        # seed-sensitive outer fits; those checkpoints are retained with an
        # explicit ``pilot_unfloored`` suffix and are not headline results.
        if epoch < args.min_epochs:
            continue
        if validation_auc > best_auc + args.min_delta:
            best_auc = validation_auc
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
        if stale >= args.patience:
            break
    return best_epoch, best_auc


def checkpoint_config(kind: str, args, data: dict) -> dict:
    probe_model = make_model(kind, args.hidden_size)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "seeds": list(args.seeds),
        "hidden_size": args.hidden_size,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "max_epochs": args.max_epochs,
        "min_epochs": args.min_epochs,
        "patience": args.patience,
        "min_delta": args.min_delta,
        "inner_val_participants": args.inner_val_participants,
        "dataset_config": data["metadata"]["dataset_config"],
        "record_keys_and_labels_sha256": data["metadata"]["record_keys_and_labels_sha256"],
        "device": str(args.device_obj),
        "n_parameters": sum(p.numel() for p in probe_model.parameters()),
        "terminal_index_policy": (
            "circular convolution plus global mean/max pooling; cyclic-shift invariant"
            if kind.endswith("_tcn") else
            "endpoint-aware diagnostic; can reconstruct excluded final_dist"
        ),
    }


def load_checkpoint(path: Path, config: dict, shape: tuple[int, int],
                    n_seeds: int, n_folds: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    predictions = np.full((n_seeds, *shape), np.nan, dtype=np.float64)
    done = np.zeros(n_folds, dtype=bool)
    epochs = np.zeros(n_folds, dtype=np.int16)
    validation_auc = np.full(n_folds, np.nan, dtype=np.float64)
    if not path.exists():
        return predictions, done, epochs, validation_auc
    with np.load(path, allow_pickle=False) as saved:
        saved_config = json.loads(str(saved["config_json"].item()))
        if saved_config != config:
            raise ValueError(f"Checkpoint config mismatch: {path}")
        predictions = saved["predictions"].copy()
        done = saved["done"].copy()
        epochs = saved["epochs"].copy()
        validation_auc = saved["validation_auc"].copy()
    if predictions.shape != (n_seeds, *shape) or done.shape != (n_folds,):
        raise ValueError(f"Checkpoint array shape mismatch: {path}")
    return predictions, done, epochs, validation_auc


def save_checkpoint(path: Path, config: dict, predictions: np.ndarray,
                    done: np.ndarray, epochs: np.ndarray,
                    validation_auc: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path, predictions=predictions, done=done, epochs=epochs,
        validation_auc=validation_auc, config_json=np.asarray(json.dumps(config)),
    )


def deep_oof(data: dict, kind: str, args) -> tuple[np.ndarray, dict]:
    participants = data["participants"]
    pids = sorted(set(participants.tolist()))
    config = checkpoint_config(kind, args, data)
    checkpoint = args.output_dir / f"checkpoint_{kind}.npz"
    if args.no_resume and checkpoint.exists():
        raise ValueError(f"--no-resume refuses existing checkpoint: {checkpoint}")
    predictions, done, selected_epochs, validation_auc = load_checkpoint(
        checkpoint, config, data["mask"].shape, len(args.seeds), len(pids)
    )
    started = time.monotonic()
    processed = 0
    for fold_index, pid in enumerate(pids):
        if done[fold_index]:
            continue
        test_indices = np.flatnonzero(participants == pid)
        outer_train = np.flatnonzero(participants != pid)
        train_pids = np.asarray(sorted(set(participants[outer_train].tolist())))
        rng = np.random.default_rng(stable_seed(args.selection_seed, pid, "inner-val"))
        validation_pids = rng.choice(
            train_pids, size=min(args.inner_val_participants, len(train_pids) - 1), replace=False
        )
        inner_validation = np.flatnonzero(np.isin(participants, validation_pids))
        epoch_seed = stable_seed(args.selection_seed, pid, kind, "epoch-selection")
        best_epoch, best_validation_auc = select_epoch(
            data, kind, outer_train, inner_validation, epoch_seed, args
        )
        selected_epochs[fold_index] = best_epoch
        validation_auc[fold_index] = best_validation_auc
        fold_auc = []
        for seed_index, seed in enumerate(args.seeds):
            fit_seed = stable_seed(seed, pid, kind, "outer-fit")
            model = fit_epochs(
                data, kind, outer_train, fit_seed, best_epoch, args.batch_size,
                args.hidden_size, args.learning_rate, args.weight_decay,
                args.device_obj, args.threads,
            )
            fold_scores = predict_trials(
                model, data, test_indices, args.batch_size, args.device_obj
            )
            predictions[seed_index, test_indices] = fold_scores[test_indices]
            y = data["labels"][test_indices][data["mask"][test_indices]]
            p = fold_scores[test_indices][data["mask"][test_indices]]
            fold_auc.append(float(roc_auc_score(y, p)))
            del model
        done[fold_index] = True
        save_checkpoint(
            checkpoint, config, predictions, done, selected_epochs, validation_auc
        )
        processed += 1
        print(
            f"{kind} fold {fold_index + 1:02d}/{len(pids)} {pid}: "
            f"epoch={best_epoch}, val_auc={best_validation_auc:.4f}, "
            f"test_auc={np.mean(fold_auc):.4f} ± {np.std(fold_auc):.4f}",
            flush=True,
        )
        if args.fold_limit and processed >= args.fold_limit:
            break
    complete = bool(done.all())
    diagnostics = {
        "config": config,
        "complete": complete,
        "completed_folds": int(done.sum()),
        "checkpoint": str(checkpoint),
        "selected_epoch_by_participant": {
            str(pid): int(selected_epochs[i]) for i, pid in enumerate(pids) if done[i]
        },
        "inner_validation_auc_by_participant": {
            str(pid): float(validation_auc[i]) for i, pid in enumerate(pids) if done[i]
        },
        "epoch_selection_summary": {
            "minimum_selected": int(selected_epochs[done].min()) if done.any() else None,
            "maximum_selected": int(selected_epochs[done].max()) if done.any() else None,
            "at_minimum": int(np.sum(selected_epochs[done] == args.min_epochs)),
            "at_maximum": int(np.sum(selected_epochs[done] == args.max_epochs)),
        },
        "run_seconds_this_invocation": time.monotonic() - started,
    }
    if not complete:
        return predictions, diagnostics
    if not np.isfinite(predictions[:, data["mask"]]).all():
        raise ValueError(f"{kind}: complete checkpoint still has missing held-out predictions")
    return predictions, diagnostics


def summarize_seeded(data: dict, predictions: np.ndarray,
                     seeds: tuple[int, ...]) -> tuple[dict, dict[str, float]]:
    seed_results = {}
    for seed, scores in zip(seeds, predictions):
        metrics, _ = metric_bundle(data, scores)
        seed_results[str(seed)] = metrics
    ensemble = np.full(data["mask"].shape, np.nan, dtype=np.float64)
    ensemble[data["mask"]] = predictions[:, data["mask"]].mean(axis=0)
    ensemble_metrics, ensemble_folds = metric_bundle(data, ensemble)
    return {
        "aggregation": "arithmetic mean of held-out probabilities across seeds",
        "seeds": seed_results,
        "ensemble": ensemble_metrics,
    }, ensemble_folds


def verify_m4_reproduction(canonical: dict, position_metrics: dict, m4_metrics: dict) -> None:
    for name, observed, canonical_name in (
        ("position pooled_auc", position_metrics["pooled_auc"], "M1"),
        ("M4 pooled_auc", m4_metrics["pooled_auc"], "M4-7"),
    ):
        expected = canonical["conditions"][f"buf{BUFFER_MS}"][canonical_name]["pooled_auc"]
        if abs(observed - expected) > 1e-12:
            raise ValueError(f"{name} {observed} != canonical {expected}")
    for metric in ("mrr_at_10", "ndcg_at_1"):
        expected = canonical["conditions"][f"buf{BUFFER_MS}"]["M4-7"][metric]
        if abs(m4_metrics[metric] - expected) > 1e-12:
            raise ValueError(f"M4 {metric} {m4_metrics[metric]} != canonical {expected}")


def run(args) -> dict | None:
    root = args.repo_root.resolve()
    args.output_dir = args.output_dir.resolve()
    args.cache = args.cache.resolve()
    args.device_obj = torch.device(args.device)
    canonical_path = root / "scripts/output/m4_cursor_aoi_mousedown/summary.json"
    canonical = json.loads(canonical_path.read_text())
    canonical_hashes = verify_canonical_sources(root, canonical)
    expected_cache = {
        "dataset_config": dataset_config(args.steps),
        "canonical_source_sha256": canonical_hashes,
    }
    if args.rebuild_cache or not args.cache.exists():
        data = build_cache(root, args.cache, args.steps, canonical, canonical_hashes)
    else:
        data = load_cache(args.cache, expected_cache)
        print(f"Loaded verified derived cache: {args.cache}", flush=True)
    if args.prepare_only:
        return None

    started = time.monotonic()
    position_scores = sklearn_oof(data, "position")
    m4_scores = sklearn_oof(data, "m4")
    position_metrics, position_folds = metric_bundle(data, position_scores)
    m4_metrics, m4_folds = metric_bundle(data, m4_scores)
    verify_m4_reproduction(canonical, position_metrics, m4_metrics)
    print(
        f"canonical parity: position={position_metrics['pooled_auc']:.6f}, "
        f"M4={m4_metrics['pooled_auc']:.6f}", flush=True
    )

    results = {
        "position_lr": position_metrics,
        "m4_lr": m4_metrics,
    }
    fold_results = {"position_lr": position_folds, "m4_lr": m4_folds}
    model_diagnostics = {}

    if "m4_lightgbm" in args.models:
        lgb_scores, lgb_config = lightgbm_oof(data, args.lightgbm_seed)
        lgb_metrics, lgb_folds = metric_bundle(data, lgb_scores)
        results["m4_lightgbm"] = lgb_metrics
        fold_results["m4_lightgbm"] = lgb_folds
        model_diagnostics["m4_lightgbm"] = {"config": lgb_config}
        print(f"m4_lightgbm pooled AUC={lgb_metrics['pooled_auc']:.6f}", flush=True)

    for kind in ("relative_flat_lgbm", "global_flat_lgbm"):
        if kind not in args.models:
            continue
        flat_scores, flat_config = flattened_trajectory_lightgbm_oof(
            data, kind, args.lightgbm_seed
        )
        flat_metrics, flat_folds = metric_bundle(data, flat_scores)
        results[kind] = flat_metrics
        fold_results[kind] = flat_folds
        model_diagnostics[kind] = {"config": flat_config}
        print(f"{kind} pooled AUC={flat_metrics['pooled_auc']:.6f}", flush=True)

    incomplete = []
    for kind in ("relative_tcn", "global_tcn",
                 "relative_gru_endpoint", "global_gru_endpoint"):
        if kind not in args.models:
            continue
        predictions, diagnostics = deep_oof(data, kind, args)
        model_diagnostics[kind] = diagnostics
        if not diagnostics["complete"]:
            incomplete.append(kind)
            continue
        summary, folds = summarize_seeded(data, predictions, args.seeds)
        results[kind] = summary
        fold_results[kind] = folds
        print(f"{kind} ensemble pooled AUC={summary['ensemble']['pooled_auc']:.6f}", flush=True)

    comparisons = {
        "m4_lr_vs_position_lr": paired_comparison(m4_folds, position_folds),
    }
    for name, folds in fold_results.items():
        if name in ("position_lr", "m4_lr"):
            continue
        comparisons[f"{name}_vs_m4_lr"] = paired_comparison(folds, m4_folds)
        comparisons[f"{name}_vs_position_lr"] = paired_comparison(folds, position_folds)
    if "relative_tcn" in fold_results and "global_tcn" in fold_results:
        comparisons["relative_tcn_vs_global_tcn"] = paired_comparison(
            fold_results["relative_tcn"], fold_results["global_tcn"]
        )
    if "relative_flat_lgbm" in fold_results and "global_flat_lgbm" in fold_results:
        comparisons["relative_flat_lgbm_vs_global_flat_lgbm"] = paired_comparison(
            fold_results["relative_flat_lgbm"], fold_results["global_flat_lgbm"]
        )

    import sklearn

    status = "partial_checkpoint" if incomplete else "full_corpus"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "protocol": {
            **data["metadata"]["dataset_config"],
            "candidate_population": "identical to canonical typed M4 headline",
            "click_label": "identical final-click per-AOI label",
            "outer_evaluation": "47-fold leave-one-participant-out",
            "deep_epoch_selection": (
                "participant-held-out validation inside each outer training fold; "
                "selected epoch count retrained on all outer-training participants"
            ),
            "deep_seed_aggregation": "mean held-out probability across fixed seeds",
            "scope": (
                "architecture-inspired same-target controls; not reproductions of "
                "published attention or abandonment experiments"
            ),
        },
        "counts": data["metadata"]["counts"],
        "results": results,
        "comparisons": comparisons,
        "model_diagnostics": model_diagnostics,
        "incomplete_models": incomplete,
        "runtime_seconds_this_invocation": time.monotonic() - started,
        "provenance": {
            "canonical_summary": str(canonical_path),
            "canonical_summary_sha256": sha256(canonical_path),
            "canonical_source_sha256": canonical_hashes,
            "prepared_cache_sha256": sha256(args.cache),
            "prepared_feature_records_sha256": data["metadata"]["feature_records_sha256"],
            "record_keys_and_labels_sha256": data["metadata"]["record_keys_and_labels_sha256"],
            "producer": str(Path(__file__).resolve()),
            "producer_sha256": sha256(Path(__file__).resolve()),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "sklearn": sklearn.__version__,
            "lightgbm": lgb.__version__,
            "torch": torch.__version__,
            "device": str(args.device_obj),
            "threads": args.threads,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "summary.json"
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print(f"Wrote aggregate summary: {output}", flush=True)
    return payload


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument(
        "--output-dir", type=Path,
        default=root / "scripts/output/m4_same_target_learned",
    )
    parser.add_argument(
        "--cache", type=Path,
        default=root / "scripts/output/m4_same_target_learned/prepared.npz",
    )
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--models", nargs="+", choices=MODEL_CHOICES, default=list(DEFAULT_MODELS))
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--hidden-size", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--max-epochs", type=int, default=20)
    parser.add_argument("--min-epochs", type=int, default=5)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--inner-val-participants", type=int, default=5)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--selection-seed", type=int, default=20260913)
    parser.add_argument("--lightgbm-seed", type=int, default=20260913)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument(
        "--fold-limit", type=int, default=0,
        help="Run at most this many unfinished deep folds; creates a partial checkpoint only",
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if args.steps < 2 or args.hidden_size < 1 or args.batch_size < 1:
        parser.error("steps must be >=2; hidden size and batch size must be positive")
    if args.min_epochs < 1 or args.max_epochs < args.min_epochs:
        parser.error("epochs must satisfy 1 <= min_epochs <= max_epochs")
    if args.patience < 1 or args.inner_val_participants < 1 or args.threads < 1:
        parser.error("patience, inner validation participants, and threads must be positive")
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be non-empty and distinct")
    if args.fold_limit < 0:
        parser.error("fold-limit must be nonnegative")
    args.seeds = tuple(args.seeds)
    args.models = tuple(args.models)
    return args


if __name__ == "__main__":
    run(parse_args())
