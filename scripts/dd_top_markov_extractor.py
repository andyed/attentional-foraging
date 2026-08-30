"""AOI-fixation sequence extractor for dd_top-topped SERPs (Markov substrate).

Restricts to the 1,582 / 2,776 trials where the highest-y non-organic
non-chrome AOI is `dd_top` (the modal layout family, 57.0% of the
corpus). Within that stratum, builds per-trial AOI state sequences from
the fixation stream, suitable for first-order / semi-Markov / sequence
analysis.

State alphabet (position-aware for AOI types with stable rank, type-
collapsed for everything else):

  dd_top_cell_K        K = 1..n_cells (midpoint-split, so every in-dd_top
                         fixation lands in some cell; n_cells modal 4)
  organic_K            K = 1..n_organic (1-indexed by `position` field)
  image_pack
  native_ad            (collapses all native_ad bboxes — typically 3 per SERP,
                         all in-stream below dd_top + organic)
  paa
  knowledge_panel
  related_searches
  pagination
  dd_right_any         (collapses dd_right + dd_right_cell — right-rail)
  off                  fixation outside any AOI / chrome

Outputs:
  scripts/output/dd_top_markov/sequences.jsonl  — one line per trial
  scripts/output/dd_top_markov/transition_matrix_corpus.json
  scripts/output/dd_top_markov/summary.json

Run:
    .venv/bin/python scripts/dd_top_markov_extractor.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import (load_fixations, get_trial_ids,  # noqa: E402
                         typed_alignment_exclusions)
from probe_cellsplit_features import load_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/dd_top_markov"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TYPED_AOI_DIR = ROOT / "data/aoi-typed-gapfill"

# Types collapsed to a single state (no position-aware suffix). Order
# doesn't matter for state assignment but anchors the alphabet listing.
COLLAPSED_TYPES = (
    "image_pack", "native_ad", "paa", "knowledge_panel",
    "related_searches", "pagination", "unknown_widget",
    "other_widget", "top_places",
)
OFF_STATE = "off"


def _in_bbox(x: float, y: float, b: dict) -> bool:
    bx, by = b["x"], b["y"]
    return bx <= x <= bx + b["w"] and by <= y <= by + b["h"]


def _in_typed_aoi(x: float, y: float, a: dict) -> bool:
    return (a["x"] <= x <= a["x"] + a["width"]
            and a["y"] <= y <= a["y"] + a["height"])


def _read_typed_gapfill_raw(trial_id: str) -> list[dict] | None:
    """Returns the typed-gapfill AOI list (parents only, includes
    organic with `position`).

    Deliberately NOT named load_typed_aois: that name belongs to data_loader's gated
    loader, and shadowing it here made an ungated read look like a gated one. This reads
    the directory raw; the alignment-exclusion gate is applied to the trial list in main().
    """
    p = TYPED_AOI_DIR / f"{trial_id}.json"
    if not p.exists():
        return None
    return json.load(open(p))


def is_dd_top_topped(typed_aois: list[dict]) -> bool:
    """A trial is dd_top-topped if the smallest-y non-organic non-chrome
    typed AOI is of type dd_top."""
    non_org = [a for a in typed_aois
               if a.get("type") not in ("organic", "chrome")
               and a.get("y") is not None]
    if not non_org:
        return False
    non_org.sort(key=lambda a: a["y"])
    return non_org[0]["type"] == "dd_top"


def assign_state(fix: dict, cells: list[dict], typed_aois: list[dict]) -> str:
    """Map a fixation (x, y) to one AOI state.

    Priority:
      1. dd_top_cell (after midpoint-split, covers full dd_top parent)
      2. dd_right_cell  -> dd_right_any
      3. organic_cell   -> organic_K (parent rank)
      4. typed-gapfill AOI (organic_K / collapsed type / dd_right_any)
      5. off
    """
    x, y = fix["x"], fix["y"]

    # 1-3. Try cells first (from cascade snapshot, post-midpoint-split)
    for c in cells:
        if c["kind"] == "dd_top_cell" and _in_bbox(x, y, c):
            return f"dd_top_cell_{c.get('position') or c.get('bbox_index', 0) + 1}"
        if c["kind"] == "dd_right_cell" and _in_bbox(x, y, c):
            return "dd_right_any"
        if c["kind"] == "organic_cell" and _in_bbox(x, y, c):
            # organic_cell parent rank not directly attached; fall through
            # to typed-AOI matching for position assignment.
            pass

    # 4. Typed-gapfill AOIs (parents only)
    matches = []
    for a in typed_aois:
        if a.get("type") == "chrome":
            continue
        if a.get("x") is None or a.get("y") is None:
            continue
        if _in_typed_aoi(x, y, a):
            matches.append(a)
    if matches:
        # Prefer smallest bbox (most specific) on overlap.
        m = min(matches, key=lambda a: a["width"] * a["height"])
        t = m["type"]
        if t == "organic":
            pos = m.get("position")
            return f"organic_{pos}" if pos else "organic_unk"
        if t == "dd_top":
            # In dd_top parent but not in any cell — rare with midpoint-split
            return "dd_top_other"
        if t == "dd_right":
            return "dd_right_any"
        if t in COLLAPSED_TYPES:
            return t
        return t  # unknown type — preserve as-is

    return OFF_STATE


def process_trial(trial_id: str) -> dict | None:
    typed_aois = _read_typed_gapfill_raw(trial_id)
    if typed_aois is None or not is_dd_top_topped(typed_aois):
        return None
    try:
        cells = load_aois(trial_id, midpoint_split=True)
    except FileNotFoundError:
        cells = []
    cells = [c for c in cells if c.get("role") == "cell"]

    fixations = load_fixations(trial_id)
    if len(fixations) < 2:
        return None

    states = []
    durations = []
    timestamps = []
    for fix in fixations:
        s = assign_state(fix, cells, typed_aois)
        states.append(s)
        durations.append(int(fix["d"]))
        timestamps.append(int(fix["t"]))
    return {
        "trial_id": trial_id,
        "participant": trial_id.split("-", 1)[0],
        "n_fixations": len(fixations),
        "n_dd_top_cells": sum(1 for c in cells if c["kind"] == "dd_top_cell"),
        "n_organic": sum(1 for a in typed_aois if a.get("type") == "organic"),
        "states": states,
        "durations_ms": durations,
        "timestamps_ms": timestamps,
    }


def build_transition_matrix(sequences: list[list[str]]) -> tuple[list[str], np.ndarray]:
    """Build (alphabet, transition_count_matrix) from a list of state
    sequences. Self-transitions counted normally (a state followed by
    itself, e.g. multi-fixation cluster in one AOI)."""
    alphabet = sorted({s for seq in sequences for s in seq})
    idx = {s: i for i, s in enumerate(alphabet)}
    n = len(alphabet)
    counts = np.zeros((n, n), dtype=int)
    for seq in sequences:
        for a, b in zip(seq[:-1], seq[1:]):
            counts[idx[a], idx[b]] += 1
    return alphabet, counts


def normalize_rows(counts: np.ndarray) -> np.ndarray:
    row_sums = counts.sum(axis=1, keepdims=True)
    safe = np.where(row_sums == 0, 1, row_sums)
    return counts / safe


def entropy_bits(p: np.ndarray) -> float:
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def main() -> int:
    # alignment_suspect trials are excluded from typed-flavor derivation
    # (data/aoi-typed/alignment-exclusions.json; docs/local-pack-aoi-shift.md Quality gate).
    excluded = typed_alignment_exclusions()
    trial_ids = [t for t in get_trial_ids() if t not in excluded]
    print(f"[1/3] iterating {len(trial_ids)} trial IDs "
          f"({len(excluded)} alignment_suspect excluded), filtering to dd_top-topped...")
    kept = []
    n_iter = 0
    for tid in trial_ids:
        n_iter += 1
        rec = process_trial(tid)
        if rec is not None:
            kept.append(rec)
        if n_iter % 500 == 0:
            print(f"    processed {n_iter} ({len(kept)} kept)")
    print(f"  kept {len(kept)} dd_top-topped trials with >= 2 fixations")
    total_fix = sum(r["n_fixations"] for r in kept)
    total_trans = sum(r["n_fixations"] - 1 for r in kept)
    print(f"  total fixations: {total_fix:,}; total transitions: {total_trans:,}")

    # Write per-trial sequences (JSONL, one trial per line)
    seq_path = OUT_DIR / "sequences.jsonl"
    with seq_path.open("w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    print(f"  wrote {seq_path}")

    print(f"[2/3] building corpus transition matrix...")
    sequences = [r["states"] for r in kept]
    alphabet, counts = build_transition_matrix(sequences)
    probs = normalize_rows(counts)
    print(f"  alphabet size: {len(alphabet)}")
    print(f"  total transitions: {counts.sum():,}")

    # Stationary distribution = state visit frequency / total
    state_freq = Counter(s for seq in sequences for s in seq)
    pi = np.array([state_freq[s] for s in alphabet], dtype=float)
    pi = pi / pi.sum()

    # Row-entropy = "where does each state typically go next" predictability
    row_entropies = {alphabet[i]: round(entropy_bits(probs[i]), 4)
                     for i in range(len(alphabet))}
    overall_transition_entropy = float(sum(
        pi[i] * entropy_bits(probs[i]) for i in range(len(alphabet))
    ))

    matrix_path = OUT_DIR / "transition_matrix_corpus.json"
    matrix_path.write_text(json.dumps({
        "alphabet": alphabet,
        "stationary_distribution": {alphabet[i]: round(float(pi[i]), 6)
                                    for i in range(len(alphabet))},
        "row_normalized_probs": probs.round(6).tolist(),
        "counts": counts.tolist(),
        "row_entropies_bits": row_entropies,
        "weighted_avg_transition_entropy_bits": round(overall_transition_entropy, 4),
        "max_entropy_bits": round(np.log2(len(alphabet)), 4),
    }, indent=2))
    print(f"  wrote {matrix_path}")

    print(f"[3/3] summary stats + top transitions...")
    # Top-30 transitions by count
    n = len(alphabet)
    flat = [(alphabet[i], alphabet[j], int(counts[i, j]))
            for i in range(n) for j in range(n) if counts[i, j] > 0]
    flat.sort(key=lambda r: -r[2])
    top_transitions = [{"from": a, "to": b, "count": c,
                        "p_to_given_from": round(float(probs[alphabet.index(a),
                                                              alphabet.index(b)]), 4)}
                       for a, b, c in flat[:30]]

    # Per-participant trial count (for downstream per-pid matrices)
    pid_counts = Counter(r["participant"] for r in kept)

    summary = {
        "n_trials_dd_top_topped": len(kept),
        "n_trials_total_corpus": 2776,
        "frac_of_corpus": round(len(kept) / 2776, 4),
        "total_fixations": total_fix,
        "total_transitions": total_trans,
        "alphabet_size": len(alphabet),
        "alphabet": alphabet,
        "stationary_top10": [(s, round(float(pi[alphabet.index(s)]), 4))
                             for s in sorted(state_freq, key=state_freq.get,
                                             reverse=True)[:10]],
        "weighted_avg_transition_entropy_bits": round(overall_transition_entropy, 4),
        "max_entropy_bits": round(np.log2(len(alphabet)), 4),
        "top_30_transitions_by_count": top_transitions,
        "trials_per_participant": {
            "min": min(pid_counts.values()),
            "max": max(pid_counts.values()),
            "median": int(np.median(list(pid_counts.values()))),
            "n_participants": len(pid_counts),
        },
    }
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"  wrote {summary_path}\n")

    print("---")
    print(f"dd_top-topped trials kept:  {len(kept):>4}  ({summary['frac_of_corpus']:.1%} of corpus)")
    print(f"total fixation-transitions: {total_trans:>6,}")
    print(f"alphabet size:              {len(alphabet)}")
    print(f"max possible entropy:       {summary['max_entropy_bits']:.3f} bits")
    print(f"actual weighted entropy:    {summary['weighted_avg_transition_entropy_bits']:.3f} bits")
    print(f"sequence has structure (entropy < max).")
    print()
    print("Top-10 transitions by count:")
    for t in top_transitions[:10]:
        print(f"  {t['from']:>20s} → {t['to']:<20s} {t['count']:>5}  p={t['p_to_given_from']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
