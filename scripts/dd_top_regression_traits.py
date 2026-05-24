"""Per-participant fixation-level organic regression traits, on the
dd_top-topped Markov substrate.

Candidate trait: `long_regression_rate` — among a participant's
organic→organic regressions, what fraction are |delta| >= 4 positions?
Short regressions (sizes 1-2) are immediate corrections;
long regressions are "commit jumps" — leaving a position deep down the
SERP to fixate one near the top before clicking. The mix of short
vs long regressions is hypothesized to vary at the participant level
independent of total regression rate.

Reads:  scripts/output/dd_top_markov/sequences.jsonl
        scripts/output/ad_utility_prior/per_participant.csv
        scripts/output/dd_top_cell_segmentation/per_participant.csv

Outputs: scripts/output/dd_top_regression_traits/{summary.json, per_participant.csv}

Run:    .venv/bin/python scripts/dd_top_regression_traits.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"
PRIOR_CSV = ROOT / "scripts/output/ad_utility_prior/per_participant.csv"
CELL_CSV = ROOT / "scripts/output/dd_top_cell_segmentation/per_participant.csv"
OUT_DIR = ROOT / "scripts/output/dd_top_regression_traits"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LONG_REGRESSION_THRESHOLD = 4  # |delta| >= 4 counted as a "long" regression


def regressions_in_sequence(states: list[str]) -> list[int]:
    """Returns list of regression |delta| values (absolute jump sizes)
    among organic→organic transitions in this sequence."""
    out = []
    for a, b in zip(states[:-1], states[1:]):
        if not (a.startswith("organic_") and b.startswith("organic_")):
            continue
        try:
            ja = int(a.split("_")[1])
            jb = int(b.split("_")[1])
        except (ValueError, IndexError):
            continue
        delta = jb - ja
        if delta < 0:
            out.append(-delta)  # |delta| > 0
    return out


def aggregate_participant(trials: list[dict]) -> dict:
    """Per-participant metrics from a list of trial records."""
    n_trials = len(trials)
    all_reg_sizes: list[int] = []
    n_trials_with_reg = 0
    n_trials_with_long_reg = 0
    for t in trials:
        rs = regressions_in_sequence(t["states"])
        if rs:
            n_trials_with_reg += 1
            all_reg_sizes.extend(rs)
            if max(rs) >= LONG_REGRESSION_THRESHOLD:
                n_trials_with_long_reg += 1
    n_reg = len(all_reg_sizes)
    n_long = sum(1 for s in all_reg_sizes if s >= LONG_REGRESSION_THRESHOLD)
    return {
        "n_trials": n_trials,
        "n_regressions": n_reg,
        "n_long_regressions": n_long,
        "regression_per_trial": round(n_reg / n_trials, 4) if n_trials else 0.0,
        "long_regression_per_trial": round(n_long / n_trials, 4) if n_trials else 0.0,
        "long_regression_rate": (round(n_long / n_reg, 4) if n_reg else None),
        "any_long_reg_trial_rate": round(n_trials_with_long_reg / n_trials, 4) if n_trials else 0.0,
        "mean_regression_size": (round(float(np.mean(all_reg_sizes)), 3)
                                 if all_reg_sizes else None),
        "max_regression_size": (max(all_reg_sizes) if all_reg_sizes else 0),
    }


def split_half(by_pid: dict, metric: str, eligible_pids: list[str],
               seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    a_vals, b_vals = [], []
    for pid in eligible_pids:
        trials = by_pid[pid]
        if len(trials) < 4:
            continue
        idx = np.arange(len(trials))
        rng.shuffle(idx)
        half = len(idx) // 2
        a_metrics = aggregate_participant([trials[i] for i in idx[:half]])
        b_metrics = aggregate_participant([trials[i] for i in idx[half:half * 2]])
        va, vb = a_metrics.get(metric), b_metrics.get(metric)
        if va is None or vb is None:
            continue
        a_vals.append(va)
        b_vals.append(vb)
    if len(a_vals) < 4:
        return {"r_split_half": None, "n_participants": len(a_vals)}
    r, p = spearmanr(a_vals, b_vals)
    sb = (2 * r) / (1 + r) if (1 + r) != 0 else None
    return {
        "r_split_half": round(float(r), 4),
        "r_spearman_brown": round(float(sb), 4) if sb is not None else None,
        "p": round(float(p), 4),
        "n_participants": len(a_vals),
    }


def load_csv_map(path: Path) -> dict[str, dict]:
    out = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            pid = row["participant"]
            out[pid] = {k: v for k, v in row.items() if k != "participant"}
    return out


def main() -> int:
    by_pid: dict[str, list] = defaultdict(list)
    with SEQ_PATH.open() as f:
        for line in f:
            d = json.loads(line)
            by_pid[d["participant"]].append(d)
    print(f"loaded {sum(len(v) for v in by_pid.values()):,} trials across "
          f"{len(by_pid)} participants")

    per_part = {pid: aggregate_participant(trials)
                for pid, trials in by_pid.items()}

    # Eligibility for the long_regression_rate trait: need >= 10
    # regressions total (so the long-rate has >= 1 meaningful tick),
    # and >= 8 trials.
    eligible_pids = sorted(pid for pid, m in per_part.items()
                           if m["n_trials"] >= 8 and m["n_regressions"] >= 10)
    print(f"  {len(eligible_pids)} participants eligible (n_trials>=8, n_regs>=10)")

    # Reliability
    metrics = ["regression_per_trial", "long_regression_per_trial",
               "long_regression_rate", "any_long_reg_trial_rate",
               "mean_regression_size"]
    reliability = {}
    for m in metrics:
        reliability[m] = split_half(by_pid, m, eligible_pids)
    print(f"\nSplit-half reliability (n eligible = {len(eligible_pids)}):")
    for m in metrics:
        r = reliability[m]
        if r["r_split_half"] is not None:
            print(f"  {m:34s} r={r['r_split_half']:+.3f}  "
                  f"SB={r['r_spearman_brown']:+.3f}  n={r['n_participants']}")

    # Correlations with prior axes + cell promiscuity
    prior = load_csv_map(PRIOR_CSV)
    cells = load_csv_map(CELL_CSV)
    axes = {
        "p_ad_survey": prior, "p_ad_click": prior, "p_dd_top_click": prior,
        "regression_rate": prior, "mean_lhipa": prior, "ad_over_index": prior,
        "cell_promiscuity_rate": cells, "mean_touched_fraction": cells,
        "any_cell_engagement_rate": cells,
    }

    print(f"\nCorrelations (Spearman) for eligible participants:")
    correlations: dict[str, dict] = {}
    for m in metrics:
        correlations[m] = {}
        my_vals = [per_part[pid][m] for pid in eligible_pids]
        for axis, src in axes.items():
            paired = [(my_vals[i], float(src[pid][axis]))
                      for i, pid in enumerate(eligible_pids)
                      if pid in src and src[pid].get(axis) not in (None, "", "None")
                      and my_vals[i] is not None]
            if len(paired) < 8:
                continue
            xs, ys = zip(*paired)
            r, p = spearmanr(xs, ys)
            correlations[m][axis] = {
                "spearman_r": round(float(r), 4),
                "p": round(float(p), 4),
                "n": len(paired),
            }

    for m in metrics:
        print(f"  {m}:")
        for axis, stat in correlations[m].items():
            star = " *" if stat["p"] < 0.05 else ""
            print(f"    × {axis:30s} ρ={stat['spearman_r']:+.3f} p={stat['p']:.3f} n={stat['n']}{star}")

    # Per-participant CSV
    csv_path = OUT_DIR / "per_participant.csv"
    keys = ["participant"] + list(next(iter(per_part.values())).keys())
    with csv_path.open("w") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for pid in sorted(per_part.keys()):
            w.writerow({"participant": pid, **per_part[pid]})

    summary = {
        "long_regression_threshold": LONG_REGRESSION_THRESHOLD,
        "n_participants_total": len(per_part),
        "n_participants_eligible": len(eligible_pids),
        "reliability": reliability,
        "correlations": correlations,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_DIR}/summary.json and per_participant.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
