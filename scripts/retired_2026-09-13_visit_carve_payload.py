"""Build the interrogation payload for the first-vs-subsequent-visit carve.

Emits everything a coauthor needs to poke at the claim without rerunning the
pipeline: distributions, per-participant spread, construct edge cases, and the
AO-SERP replication row. Written for the review page; also readable as JSON.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# RETIRED 2026-09-13. DO NOT RUN. DO NOT CITE ITS NUMBERS.
#
# Built on the lineage retired from the paper on 2026-09-06: features from
# compute_cursor_approach_features.py / m4_nb21_hybrid_rerun.py (whose
# identically-named fields are gaze-cursor distances over fixation-selected
# rows) and labels from compute_regression_labels.py. Its outputs look
# canonical and are not.
#
# Canonical replacement: scripts/deferred_dwell_carve.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/deferred_dwell_carve.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")

import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "output" / "visit_decomposition"

recs = json.load(open(OUT / "records.json"))
carve = json.load(open(OUT / "dwell_carve.json"))
prov = json.load(open(OUT / "provenance.json"))

pool = [r for r in recs if not r["was_clicked"]]
dfr = [r for r in pool if r["deferred"]]
rej = [r for r in pool if not r["deferred"]]


def hist(vals, lo, hi, nbins=32, log=False):
    v = np.array([x for x in vals if x is not None], dtype=float)
    v = v[(v >= lo) & (v <= hi)]
    if log:
        edges = np.logspace(np.log10(max(lo, 1)), np.log10(hi), nbins + 1)
    else:
        edges = np.linspace(lo, hi, nbins + 1)
    counts, _ = np.histogram(v, bins=edges)
    return {"edges": [round(float(e), 1) for e in edges],
            "counts": [int(c) for c in counts], "n": int(len(v))}


def q(vals, ps=(10, 25, 50, 75, 90)):
    v = np.array([x for x in vals if x is not None], dtype=float)
    return {f"p{p}": round(float(np.percentile(v, p)), 1) for p in ps}


payload = {
    "provenance": prov,
    "validation": carve.get("_validation"),
    "pool": {
        "n_noclick": len(pool), "n_deferred": len(dfr), "n_rejected": len(rej),
        "n_approached": carve["_pool"]["n_approached"],
        "n_participants": len({r["participant"] for r in pool}),
        "n_trials": len({r["trial_id"] for r in pool}),
    },
    "medians": {
        k: {"deferred": round(float(np.median([r[k] for r in dfr])), 1),
            "rejected": round(float(np.median([r[k] for r in rej])), 1)}
        for k in ["total_dwell_ms", "first_visit_dwell_ms", "subsequent_dwell_ms",
                  "n_visits", "n_fix_total", "n_fix_first_visit"]
    },
    "quantiles": {
        "first_visit_dwell_deferred": q([r["first_visit_dwell_ms"] for r in dfr]),
        "first_visit_dwell_rejected": q([r["first_visit_dwell_ms"] for r in rej]),
        "total_dwell_deferred": q([r["total_dwell_ms"] for r in dfr]),
        "total_dwell_rejected": q([r["total_dwell_ms"] for r in rej]),
    },
    "subsequent_share_deferred": round(float(np.median(
        [r["subsequent_dwell_ms"] / max(r["total_dwell_ms"], 1) for r in dfr])), 3),
    "hist": {
        "first_visit_deferred": hist([r["first_visit_dwell_ms"] for r in dfr], 0, 3000),
        "first_visit_rejected": hist([r["first_visit_dwell_ms"] for r in rej], 0, 3000),
        "total_deferred": hist([r["total_dwell_ms"] for r in dfr], 0, 8000),
        "total_rejected": hist([r["total_dwell_ms"] for r in rej], 0, 8000),
        "return_gap": hist([r["return_gap_ms"] for r in pool if r.get("return_gap_ms")],
                           50, 30000, nbins=32, log=True),
    },
    "return_gap_q": q([r["return_gap_ms"] for r in pool if r.get("return_gap_ms")]),
    "n_visits_dist": {
        "deferred": {str(k): int(sum(1 for r in dfr if r["n_visits"] == k))
                     for k in range(1, 9)},
        "rejected": {str(k): int(sum(1 for r in rej if r["n_visits"] == k))
                     for k in range(1, 9)},
    },
    "edge_cases": {
        "deferred_and_revisited": sum(1 for r in pool if r["deferred"] and r["plain_revisit"]),
        "revisited_not_deferred": sum(1 for r in pool if r["plain_revisit"] and not r["deferred"]),
        "deferred_not_revisited": sum(1 for r in pool if r["deferred"] and not r["plain_revisit"]),
    },
    "auc": {k: v for k, v in carve.items() if not k.startswith("_")},
    "null": carve["_null_M4"],
    "rate_curve": json.load(open(OUT / "rate_curve_results.json")),
    "scroll_carve": json.load(open(OUT / "scroll_carve.json")),
    "ao_replication": {
        "source": "collab/allawati-ai-overviews/abandonment-2026-09-13/FINDINGS.md",
        "n": 1077, "participants": 36,
        "dwell_total": 0.789, "dwell_first_pass": 0.459,
        "mean_dist": 0.652, "m4": 0.726, "null_p99": 0.545,
        "first_pass_median_deferred": 758.3, "first_pass_median_rejected": 729.2,
    },
}
json.dump(payload, open(OUT / "carve_payload.json", "w"), indent=1)
print(json.dumps({k: payload[k] for k in
                  ["pool", "medians", "edge_cases", "return_gap_q",
                   "subsequent_share_deferred"]}, indent=1))
