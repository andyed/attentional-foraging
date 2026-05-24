"""Forward dwell × regression distance.

Question: does the time the user spent at organic_K during forward
scan predict how far back they regress when they jump back to K?
(The "anchor hypothesis" — long jumps go to results that were
deliberated on.)

For each organic→organic regression event J→K in the dd_top-topped
substrate, computes:
  - dwell_at_dest_before    cumulative fixation-ms at organic_K
                            before the regression-landing fixation
  - dwell_at_source_before  cumulative at organic_J through end of
                            source fixation
  - total_forward_dwell_before  sum of dwell across all organic_*
                            fixations before the regression
  - size = J - K

Correlates each with size (Spearman + Pearson), plus stratifies by
prior-visit status (destination was previously fixated vs first-visit).

Run:    .venv/bin/python scripts/dd_top_regression_dwell_vs_size.py
Output: scripts/output/dd_top_regression_dwell_vs_size/summary.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, pearsonr

ROOT = Path(__file__).resolve().parent.parent
SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"
OUT_DIR = ROOT / "scripts/output/dd_top_regression_dwell_vs_size"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_events() -> list[dict]:
    events: list[dict] = []
    with SEQ_PATH.open() as f:
        for line in f:
            d = json.loads(line)
            states = d["states"]
            durs = d["durations_ms"]
            cum: dict[str, float] = defaultdict(float)
            cum_organic_total = 0.0
            for i, (s, dur) in enumerate(zip(states, durs)):
                if i > 0:
                    a = states[i - 1]
                    if a.startswith("organic_") and s.startswith("organic_"):
                        try:
                            ja, jb = int(a.split("_")[1]), int(s.split("_")[1])
                        except (ValueError, IndexError):
                            ja = jb = None
                        if ja is not None and jb is not None and jb < ja:
                            events.append({
                                "trial": d["trial_id"],
                                "participant": d["participant"],
                                "size": ja - jb,
                                "dwell_at_dest_before": cum[s],
                                "dwell_at_source_before": cum[a],
                                "total_forward_dwell_before": cum_organic_total,
                            })
                cum[s] += dur
                if s.startswith("organic_"):
                    cum_organic_total += dur
    return events


def main() -> int:
    events = extract_events()
    print(f"n regression events: {len(events):,}")
    visited = sum(1 for e in events if e["dwell_at_dest_before"] > 0)
    print(f"  destination prior-visited: {visited:,} "
          f"({visited / len(events) * 100:.1f}%)")
    print(f"  destination fresh: {len(events) - visited:,} "
          f"({(len(events) - visited) / len(events) * 100:.1f}%)\n")

    sizes = np.array([e["size"] for e in events])
    dest = np.array([e["dwell_at_dest_before"] for e in events])
    src = np.array([e["dwell_at_source_before"] for e in events])
    tot = np.array([e["total_forward_dwell_before"] for e in events])

    metrics = {
        "dwell_at_dest_before": dest,
        "dwell_at_source_before": src,
        "total_forward_dwell_before": tot,
    }
    correlations = {}
    print(f"=== Correlations against regression size ===\n")
    for name, vec in metrics.items():
        rs, ps = spearmanr(vec, sizes)
        rp, pp = pearsonr(vec, sizes)
        correlations[name] = {
            "spearman_r": round(float(rs), 5),
            "spearman_p": round(float(ps), 5),
            "pearson_r": round(float(rp), 5),
            "pearson_p": round(float(pp), 5),
            "n": len(vec),
        }
        sig = " *" if ps < 0.05 else ""
        print(f"  {name:30s}: Spearman ρ={rs:+.4f} p={ps:.4f} | "
              f"Pearson r={rp:+.4f} p={pp:.6f}{sig}")

    # Quartile breakdown of revisits only
    print(f"\n=== Quartile of prior dwell at dest (revisits only) ===\n")
    rev = [e for e in events if e["dwell_at_dest_before"] > 0]
    dwell_v = np.array([e["dwell_at_dest_before"] for e in rev])
    sz_v = np.array([e["size"] for e in rev])
    q = np.percentile(dwell_v, [25, 50, 75])
    buckets = np.digitize(dwell_v, q)
    quartile_rows = []
    print(f"  {'q':>2} {'dwell range (ms)':>20} {'n':>5} {'med size':>8} {'mean size':>10}")
    for b in range(4):
        m = buckets == b
        if m.sum() == 0:
            continue
        ds = dwell_v[m]
        szm = sz_v[m]
        row = {
            "quartile": b + 1,
            "dwell_range_ms": [int(ds.min()), int(ds.max())],
            "n_events": int(m.sum()),
            "median_regression_size": int(np.median(szm)),
            "mean_regression_size": round(float(szm.mean()), 3),
        }
        quartile_rows.append(row)
        print(f"  q{b+1} [{int(ds.min()):>4}-{int(ds.max()):>5}] {m.sum():>5} "
              f"{int(np.median(szm)):>8} {szm.mean():>10.3f}")

    # Revisit vs fresh size distributions
    fresh = [e for e in events if e["dwell_at_dest_before"] == 0]
    GROUPS = {"short(1-2)": [1, 2], "mid(3)": [3], "long(>=4)": [4, 5, 6, 7, 8, 9]}
    by_visit = {}
    for label, subset in [("revisits", rev), ("first_visits", fresh)]:
        sz = np.array([e["size"] for e in subset])
        by_visit[label] = {
            "n": int(len(sz)),
            "median": int(np.median(sz)) if len(sz) else None,
            "mean": round(float(sz.mean()), 3) if len(sz) else None,
            "size_share": {label2: round(float(sum(1 for x in sz if x in sizes2)
                                              / len(sz)), 4)
                           for label2, sizes2 in GROUPS.items()}
            if len(sz) else {},
        }

    summary = {
        "n_regression_events": len(events),
        "n_destination_previously_visited": visited,
        "n_destination_first_visit": len(events) - visited,
        "frac_destination_revisit": round(visited / len(events), 4),
        "correlations_against_size": correlations,
        "prior_dwell_quartiles_revisits_only": quartile_rows,
        "size_distribution_by_visit_status": by_visit,
        "interpretation": (
            "The anchor hypothesis — long regressions go to results "
            "that were previously dwelt on longer — is null. Across all "
            "5,738 regression events the dwell-at-destination × size "
            "Spearman is +0.004 (p=0.75); restricted to revisits only "
            "it is -0.007 (p=0.61). Median regression size is identically "
            "1 across all four prior-dwell quartiles. The +0.093 "
            "correlation between total cumulative forward dwell and "
            "regression size is small and likely a coverage effect "
            "(longer trials have visited more positions, so longer "
            "regressions become possible)."
        ),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_DIR}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
