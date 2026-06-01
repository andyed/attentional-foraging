#!/usr/bin/env python
"""OSEC-phase Markov over typed-AOI episodes — first-pass enrichment.

Reads scripts/output/dd_top_markov/sequences.jsonl (the dd_top stratum,
1,581 trials, alphabet of 30 states) and enriches with:

  - per-fixation OSEC phase tag (Survey i<=5, Evaluate i>5; NB13 convention)
  - per-saccade dx/dy/H/V components and direction class
  - per-episode aggregation (contiguous same-state fixations)
  - regression labelling: organic_J -> organic_K with K<J,
    subtype = local (|delta|=1-2) / mid (3) / long (>=4),
    sign = upward (regressions are always V-up by definition)

Emits to scripts/output/osec_markov_blend/:
  - episodes.jsonl            per-episode records
  - saccades.jsonl            per-saccade records
  - transition_matrices.json  per-phase typed-AOI episode transition matrices
                              + regression-only matrix
  - hv_fingerprint.json       per-phase H/V profile (mean, median, dir-class
                              distribution)
  - regression_subtypes.json  subtype counts, phase distribution, transition
                              mass distribution per subtype
  - summary.md                human-readable digest of headline findings

Caveats noted up-front:
  - dd_top stratum only. Generalization to dd_right_top / organic_top is
    a second pass.
  - SURVEY_END=5 fixation-index cutoff (no derived signature). Regressions
    are treated as a transition-class label on Evaluate-phase saccades,
    not a separate phase, in this pass.
  - Direction-class thresholds (see DIRECTION_THRESHOLDS) are first-cut
    and not yet pinned by prior AF convention.

Run: .venv/bin/python scripts/osec_markov_blend.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import load_fixations  # noqa: E402

SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"
OUT_DIR = ROOT / "scripts/output/osec_markov_blend"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SURVEY_END = 5  # NB13 convention: fixation indices 0..SURVEY_END-1 are Survey
# Direction thresholds: micro = saccade amplitude below MICRO_AMP_PX;
# otherwise classify by axis-ratio H_ratio = |dx| / (|dx| + |dy|).
MICRO_AMP_PX = 30.0
H_RATIO_HV_BOUNDARY = 0.70  # H if ratio > 0.70
H_RATIO_VH_BOUNDARY = 0.30  # V if ratio < 0.30; else diagonal
LONG_REGRESSION_THRESHOLD = 4  # |delta| >= 4 (matches dd_top_regression_traits)
MID_REGRESSION_THRESHOLD = 3   # |delta| == 3
# Episodes of an organic_K state pairs as (J,K) with K<J on the K side
# is a regression *into* K from J.


# ── fixation phase / direction helpers ──────────────────────────────────────

def assign_phase(fix_idx: int) -> str:
    return "Survey" if fix_idx < SURVEY_END else "Evaluate"


def classify_direction(dx: float, dy: float) -> tuple[str, str]:
    """Return (dir_class, v_sign).

    dir_class in {micro, horizontal, vertical, diagonal}
    v_sign in {up, down, flat}  — note: page-y grows downward.
    """
    amp = math.hypot(dx, dy)
    if amp < MICRO_AMP_PX:
        return "micro", "flat"
    h_ratio = abs(dx) / (abs(dx) + abs(dy)) if (abs(dx) + abs(dy)) > 0 else 0.5
    if h_ratio > H_RATIO_HV_BOUNDARY:
        cls = "horizontal"
    elif h_ratio < H_RATIO_VH_BOUNDARY:
        cls = "vertical"
    else:
        cls = "diagonal"
    if dy > 5:
        sign = "down"
    elif dy < -5:
        sign = "up"
    else:
        sign = "flat"
    return cls, sign


def organic_pos(state: str) -> int | None:
    if not state.startswith("organic_"):
        return None
    suffix = state.split("_", 1)[1]
    try:
        return int(suffix)
    except ValueError:
        return None


def regression_subtype(delta_abs: int) -> str:
    if delta_abs >= LONG_REGRESSION_THRESHOLD:
        return "long"
    if delta_abs == MID_REGRESSION_THRESHOLD:
        return "mid"
    return "local"  # 1 or 2


# ── core enrichment pass ────────────────────────────────────────────────────

def enrich_trial(d: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (episode_records, saccade_records, fix_records)."""
    trial_id = d["trial_id"]
    states = d["states"]
    durations = d.get("durations_ms", [])
    fix = load_fixations(trial_id)
    if len(fix) != len(states):
        return [], [], []

    fix_records: list[dict] = []
    saccade_records: list[dict] = []

    for i, f in enumerate(fix):
        phase = assign_phase(i)
        fix_records.append({
            "trial_id": trial_id,
            "fix_idx": i,
            "state": states[i],
            "phase": phase,
            "x": f["x"], "y": f["y"], "d": f["d"], "t": f["t"],
        })

    for i in range(len(fix) - 1):
        a, b = fix[i], fix[i + 1]
        dx = b["x"] - a["x"]
        dy = b["y"] - a["y"]
        dir_class, v_sign = classify_direction(dx, dy)
        # The saccade lives at the boundary; assign it the source-fixation phase.
        phase = assign_phase(i)
        from_state = states[i]
        to_state = states[i + 1]
        # regression label only if both are organic_* and dest < source
        regression = None
        op_a = organic_pos(from_state)
        op_b = organic_pos(to_state)
        if op_a is not None and op_b is not None and op_b < op_a:
            delta = op_a - op_b
            regression = {
                "delta_abs": delta,
                "subtype": regression_subtype(delta),
            }
        saccade_records.append({
            "trial_id": trial_id,
            "fix_idx": i,
            "phase": phase,
            "from_state": from_state,
            "to_state": to_state,
            "dx": dx, "dy": dy,
            "amp": math.hypot(dx, dy),
            "h_comp": abs(dx),
            "v_comp": abs(dy),
            "dir_class": dir_class,
            "v_sign": v_sign,
            "regression": regression,
        })

    # episodes = contiguous same-state runs
    episode_records: list[dict] = []
    i0 = 0
    n = len(states)
    while i0 < n:
        j = i0
        while j + 1 < n and states[j + 1] == states[i0]:
            j += 1
        # span fix[i0..j]
        phase = assign_phase(i0)
        dwell_ms = sum(durations[i0:j + 1]) if durations else 0
        episode_records.append({
            "trial_id": trial_id,
            "state": states[i0],
            "entry_fix_idx": i0,
            "exit_fix_idx": j,
            "n_fixations": j - i0 + 1,
            "phase_at_entry": phase,
            "dwell_ms": dwell_ms,
        })
        i0 = j + 1

    return episode_records, saccade_records, fix_records


# ── matrix / fingerprint aggregation ────────────────────────────────────────

def build_transition_matrices(saccades: list[dict]) -> dict:
    """Per-phase transition matrices over the typed-AOI alphabet, plus a
    regression-only matrix. Stored as nested dict for JSON serialization.
    Includes raw counts and row-normalized probabilities.
    """
    by_phase: dict[str, dict[str, Counter[str]]] = {
        "Survey": defaultdict(Counter),
        "Evaluate": defaultdict(Counter),
    }
    regression_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for s in saccades:
        by_phase[s["phase"]][s["from_state"]][s["to_state"]] += 1
        if s["regression"]:
            regression_counter[s["from_state"]][s["to_state"]] += 1

    def normalize(counter_of_counters: dict[str, Counter[str]]) -> dict:
        out = {}
        for src, cnt in counter_of_counters.items():
            total = sum(cnt.values())
            out[src] = {
                "total": total,
                "to": dict(cnt),
                "p_to": {k: v / total for k, v in cnt.items()} if total else {},
            }
        return out

    return {
        "Survey": normalize(by_phase["Survey"]),
        "Evaluate": normalize(by_phase["Evaluate"]),
        "Regression_only": normalize(regression_counter),
        "phase_totals": {
            "Survey": sum(sum(c.values()) for c in by_phase["Survey"].values()),
            "Evaluate": sum(sum(c.values()) for c in by_phase["Evaluate"].values()),
            "Regression_only": sum(sum(c.values()) for c in regression_counter.values()),
        },
    }


def build_hv_fingerprint(saccades: list[dict]) -> dict:
    """Per-phase H/V profile + direction-class distribution."""
    out: dict[str, dict] = {}
    for phase in ("Survey", "Evaluate"):
        sub = [s for s in saccades if s["phase"] == phase]
        amps = np.array([s["amp"] for s in sub], dtype=float)
        h = np.array([s["h_comp"] for s in sub], dtype=float)
        v = np.array([s["v_comp"] for s in sub], dtype=float)
        # H/V ratio at saccade level (skip micros to keep the ratio
        # meaningful)
        non_micro = [s for s in sub if s["dir_class"] != "micro"]
        ratios = np.array(
            [s["h_comp"] / (s["h_comp"] + s["v_comp"])
             for s in non_micro if (s["h_comp"] + s["v_comp"]) > 0],
            dtype=float,
        )
        dir_counter = Counter(s["dir_class"] for s in sub)
        v_sign_counter = Counter(s["v_sign"] for s in sub)
        out[phase] = {
            "n_saccades": len(sub),
            "amp_mean": float(amps.mean()) if amps.size else 0.0,
            "amp_median": float(np.median(amps)) if amps.size else 0.0,
            "h_mean": float(h.mean()) if h.size else 0.0,
            "v_mean": float(v.mean()) if v.size else 0.0,
            "h_median": float(np.median(h)) if h.size else 0.0,
            "v_median": float(np.median(v)) if v.size else 0.0,
            "hv_ratio_mean": float(ratios.mean()) if ratios.size else None,
            "hv_ratio_median": float(np.median(ratios)) if ratios.size else None,
            "dir_class_distribution": {
                k: dir_counter[k] / len(sub) if sub else 0.0
                for k in ("micro", "horizontal", "vertical", "diagonal")
            },
            "v_sign_distribution": {
                k: v_sign_counter[k] / len(sub) if sub else 0.0
                for k in ("up", "down", "flat")
            },
        }
    return out


def analyze_regression_subtypes(saccades: list[dict],
                                episodes: list[dict]) -> dict:
    """Count subtypes, per-phase distribution, and per-subtype destination
    distribution (does long-organic regression snap to organic_1 / top-pull
    target as 68525e7f predicts?).
    """
    subtypes = ("local", "mid", "long")
    counts = Counter()
    by_phase = defaultdict(Counter)
    by_subtype_dest = {st: Counter() for st in subtypes}
    by_subtype_phase_fixidx = {st: [] for st in subtypes}

    for s in saccades:
        if not s["regression"]:
            continue
        st = s["regression"]["subtype"]
        counts[st] += 1
        by_phase[s["phase"]][st] += 1
        by_subtype_dest[st][s["to_state"]] += 1
        by_subtype_phase_fixidx[st].append(s["fix_idx"])

    # Top-pull check: of long regressions, what fraction land on organic_1
    # or organic_2 (the "top of organic" attractor)? If absolute attractor,
    # this fraction should dominate. If relative-distance, this fraction
    # should be small (long regressions land anywhere).
    long_total = counts.get("long", 0)
    long_to_top12 = (by_subtype_dest["long"].get("organic_1", 0)
                     + by_subtype_dest["long"].get("organic_2", 0))
    top_pull_frac = (long_to_top12 / long_total) if long_total else None

    fix_idx_stats = {}
    for st in subtypes:
        arr = np.array(by_subtype_phase_fixidx[st], dtype=float)
        if arr.size:
            fix_idx_stats[st] = {
                "n": int(arr.size),
                "median_fix_idx": float(np.median(arr)),
                "p25": float(np.percentile(arr, 25)),
                "p75": float(np.percentile(arr, 75)),
            }
        else:
            fix_idx_stats[st] = {"n": 0}

    return {
        "subtype_counts": dict(counts),
        "by_phase": {ph: dict(d) for ph, d in by_phase.items()},
        "top_pull_long_frac": top_pull_frac,
        "long_destination_top10": dict(by_subtype_dest["long"].most_common(10)),
        "mid_destination_top10": dict(by_subtype_dest["mid"].most_common(10)),
        "local_destination_top10": dict(by_subtype_dest["local"].most_common(10)),
        "fix_idx_stats": fix_idx_stats,
    }


# ── orchestration ───────────────────────────────────────────────────────────

def kl_divergence(p: dict[str, float], q: dict[str, float],
                  smoothing: float = 1e-6) -> float:
    """Symmetric KL on two distributions over a common vocabulary."""
    keys = set(p) | set(q)
    out = 0.0
    for k in keys:
        pk = p.get(k, 0.0) + smoothing
        qk = q.get(k, 0.0) + smoothing
        out += pk * math.log(pk / qk) + qk * math.log(qk / pk)
    return out * 0.5


def compute_phase_kl(matrices: dict) -> dict:
    """Per-source-state KL between Survey and Evaluate row distributions.
    Reports row-by-row + aggregate (weighted by total mass)."""
    survey = matrices["Survey"]
    evaluate = matrices["Evaluate"]
    rows = sorted(set(survey) | set(evaluate))
    per_row = {}
    weighted_sum = 0.0
    total_weight = 0
    for r in rows:
        p = survey.get(r, {}).get("p_to", {})
        q = evaluate.get(r, {}).get("p_to", {})
        n_s = survey.get(r, {}).get("total", 0)
        n_e = evaluate.get(r, {}).get("total", 0)
        if n_s < 5 or n_e < 5:
            continue  # skip thin rows
        kl = kl_divergence(p, q)
        per_row[r] = {"kl_symmetric": kl, "n_survey": n_s, "n_evaluate": n_e}
        w = n_s + n_e
        weighted_sum += kl * w
        total_weight += w
    weighted_mean = weighted_sum / total_weight if total_weight else None
    return {
        "per_row": per_row,
        "weighted_mean_kl": weighted_mean,
        "n_rows_compared": len(per_row),
    }


def main() -> None:
    print(f"[info] Reading {SEQ_PATH.relative_to(ROOT)}")
    if not SEQ_PATH.exists():
        print(f"[error] sequences.jsonl not found at {SEQ_PATH}")
        sys.exit(1)

    all_episodes: list[dict] = []
    all_saccades: list[dict] = []
    n_trials_in = 0
    n_trials_kept = 0
    for line in SEQ_PATH.open():
        n_trials_in += 1
        d = json.loads(line)
        episodes, saccades, _fix = enrich_trial(d)
        if not episodes:
            continue
        n_trials_kept += 1
        all_episodes.extend(episodes)
        all_saccades.extend(saccades)
        if n_trials_kept % 200 == 0:
            print(f"[info] processed {n_trials_kept} trials, "
                  f"{len(all_saccades):,} saccades")

    print(f"[info] kept {n_trials_kept} / {n_trials_in} trials, "
          f"{len(all_episodes):,} episodes, {len(all_saccades):,} saccades")

    # Persist enriched records.
    epis_path = OUT_DIR / "episodes.jsonl"
    sacc_path = OUT_DIR / "saccades.jsonl"
    with epis_path.open("w") as f:
        for r in all_episodes:
            f.write(json.dumps(r) + "\n")
    with sacc_path.open("w") as f:
        for r in all_saccades:
            f.write(json.dumps(r) + "\n")

    # Aggregations.
    matrices = build_transition_matrices(all_saccades)
    hv = build_hv_fingerprint(all_saccades)
    reg = analyze_regression_subtypes(all_saccades, all_episodes)
    phase_kl = compute_phase_kl(matrices)

    (OUT_DIR / "transition_matrices.json").write_text(
        json.dumps(matrices, indent=2))
    (OUT_DIR / "hv_fingerprint.json").write_text(json.dumps(hv, indent=2))
    (OUT_DIR / "regression_subtypes.json").write_text(json.dumps(reg, indent=2))
    (OUT_DIR / "phase_kl.json").write_text(json.dumps(phase_kl, indent=2))

    # Markdown digest.
    md = [
        "# OSEC-Phase Markov over Typed-AOI Episodes — dd_top first pass",
        "",
        f"- trials kept: **{n_trials_kept}** / {n_trials_in}",
        f"- episodes: **{len(all_episodes):,}**",
        f"- saccades: **{len(all_saccades):,}**",
        "",
        "## H/V fingerprint per phase",
        "",
        "| phase | n_saccades | H̄ (px) | V̄ (px) | H/V ratio (median) | %H | %V | %diag | %micro | %up-V |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for phase in ("Survey", "Evaluate"):
        h = hv[phase]
        dc = h["dir_class_distribution"]
        vs = h["v_sign_distribution"]
        md.append(
            f"| {phase} | {h['n_saccades']:,} | {h['h_mean']:.1f} | {h['v_mean']:.1f} | "
            f"{(h['hv_ratio_median'] or 0):.3f} | "
            f"{dc['horizontal']*100:.1f}% | {dc['vertical']*100:.1f}% | "
            f"{dc['diagonal']*100:.1f}% | {dc['micro']*100:.1f}% | "
            f"{vs['up']*100:.1f}% |"
        )
    md.append("")
    md.append("## Phase KL (Survey vs Evaluate transition rows)")
    md.append("")
    md.append(f"- weighted mean symmetric KL: **{(phase_kl['weighted_mean_kl'] or 0):.3f}**")
    md.append(f"- n rows compared (≥5 saccades in each phase): {phase_kl['n_rows_compared']}")
    md.append("")
    md.append("Top 8 most phase-divergent source states:")
    md.append("")
    top_kl = sorted(phase_kl["per_row"].items(),
                    key=lambda kv: -kv[1]["kl_symmetric"])[:8]
    md.append("| from_state | KL | n_Survey | n_Evaluate |")
    md.append("|---|---|---|---|")
    for state, info in top_kl:
        md.append(
            f"| {state} | {info['kl_symmetric']:.3f} | "
            f"{info['n_survey']} | {info['n_evaluate']} |"
        )
    md.append("")
    md.append("## Regression subtypes (organic→organic, K<J)")
    md.append("")
    md.append(f"- counts: {reg['subtype_counts']}")
    md.append(f"- long-regression top-pull fraction (lands on organic_1 or organic_2): "
              f"**{(reg['top_pull_long_frac'] or 0)*100:.1f}%**")
    md.append("")
    md.append("Per-subtype fixation-index stats (where in the trial they fire):")
    md.append("")
    md.append("| subtype | n | median fix_idx | p25 | p75 |")
    md.append("|---|---|---|---|---|")
    for st in ("local", "mid", "long"):
        s = reg["fix_idx_stats"][st]
        if s["n"]:
            md.append(f"| {st} | {s['n']} | {s['median_fix_idx']:.1f} | "
                      f"{s['p25']:.1f} | {s['p75']:.1f} |")
        else:
            md.append(f"| {st} | 0 | — | — | — |")
    md.append("")
    md.append("Top destinations per subtype:")
    md.append("")
    for st in ("local", "mid", "long"):
        md.append(f"- **{st}**: " + ", ".join(
            f"{k}={v}" for k, v in
            list(reg.get(f"{st}_destination_top10", {}).items())[:8]))
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"_dd_top stratum only · SURVEY_END={SURVEY_END} · "
              f"micro<{MICRO_AMP_PX}px · "
              f"H if ratio>{H_RATIO_HV_BOUNDARY}, V if <{H_RATIO_VH_BOUNDARY}_")

    (OUT_DIR / "summary.md").write_text("\n".join(md))
    print(f"[done] wrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
