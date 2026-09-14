"""Does the scroll+click-only condition survive the first-visit carve?

The rate curve's scroll+click-only row scores HIGHER on the deferred task
(0.727) than the full native cursor stream (0.715). Before that is reported as
"scroll telemetry is enough", it has to face the same test that sank the dwell
baseline: viewport residence has the identical circular structure. For the gaze
to make the return fixation that DEFINES `deferred`, the AOI must be on screen.
Residence measured over the whole trial therefore contains the label, exactly
as total_dwell_ms did.

This script recomputes the scroll features twice:
  full        -- whole trial, as the rate curve had it
  first-visit -- truncated at the end of the first gaze visit to that AOI,
                 i.e. what scroll telemetry held BEFORE the return happened

and reports both against the permutation null.
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
# Canonical replacement: scripts/scroll_only_carve.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/scroll_only_carve.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")


import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "scripts" / "output" / "visit_decomposition"

from data_loader import (  # noqa: E402
    load_mouse_events, typed_gapfill_aoi_bands, get_trial_meta,
)
from rate_curve_deferred import scroll_features, SCROLL_FEATS  # noqa: E402
from rate_curve_analyze import loso  # noqa: E402


def main():
    visit = json.load(open(OUT / "records.json"))
    rate = json.load(open(OUT / "rate_curve_records.json"))
    native_ok = {(r["trial_id"], r["position"])
                 for r in rate
                 if "mousemove_only@native" in r["cond"]
                 and r["cond"]["mousemove_only@native"][0] < 100.0}

    by_trial = defaultdict(list)
    for r in visit:
        if r["was_clicked"]:
            continue
        if (r["trial_id"], r["position"]) in native_ok:
            by_trial[r["trial_id"]].append(r)

    rows = []
    for i, (tid, rs) in enumerate(by_trial.items(), 1):
        if i % 400 == 0:
            print(f"  {i}/{len(by_trial)}", flush=True)
        try:
            bands = typed_gapfill_aoi_bands(tid)
            allev, scrolls, _clk = load_mouse_events(tid, space="screenshot")
        except Exception:
            continue
        if not bands or len(scrolls) < 2:
            continue
        _dh, scr_h, _ = get_trial_meta(tid)
        if not scr_h:
            continue
        scr_h *= 0.9000
        t_span = float(allev[-1][0] - allev[0][0])
        positions = [r["position"] for r in rs]
        full = scroll_features(scrolls, bands, positions, scr_h, t_span)
        for r in rs:
            p = r["position"]
            if p not in full:
                continue
            cut = r["first_visit_end_ms"]
            sc_cut = [s for s in scrolls if s[0] <= cut]
            fv = scroll_features(sc_cut, bands, [p], scr_h,
                                 max(cut - allev[0][0], 1.0)) if len(sc_cut) >= 2 else {}
            rows.append({"participant": r["participant"], "deferred": r["deferred"],
                         "full": full[p], "first": fv.get(p)})

    rows = [r for r in rows if r["first"] is not None]
    g = np.array([r["participant"] for r in rows])
    y = np.array([bool(r["deferred"]) for r in rows], dtype=int)
    Xf = np.array([r["full"] for r in rows])
    Xv = np.array([r["first"] for r in rows])
    print(f"\nrows {len(rows):,}  participants {len(set(g))}  "
          f"deferred rate {y.mean():.3f}")

    rng = np.random.default_rng(1)
    nv = np.array([x["auc"] for x in
                   (loso(Xf, y, g, permute=True, rng=rng) for _ in range(100)) if x])
    null = {"mean": float(nv.mean()), "p95": float(np.percentile(nv, 95)),
            "p99": float(np.percentile(nv, 99))}

    out = {"null": null, "n": len(rows)}
    print(f"\n{'='*62}\nSCROLL+CLICK ONLY, deferred task\n{'='*62}")
    for name, X in (("full trial", Xf), ("first visit only", Xv)):
        r = loso(X, y, g)
        out[name] = r
        mark = "  <- inside null" if r["auc"] <= null["p99"] else ""
        print(f"  {name:20s} AUC {r['auc']:.3f}   per-fold "
              f"{r['fold_mean']:.3f} +- {r['fold_sd']:.3f}{mark}")
    print(f"  {'permutation null':20s} mean {null['mean']:.3f}  "
          f"p95 {null['p95']:.3f}  p99 {null['p99']:.3f}")

    print("\n  single features (full | first visit):")
    out["single"] = {}
    for j, nm in enumerate(SCROLL_FEATS):
        a = loso(Xf[:, [j]], y, g)
        b = loso(Xv[:, [j]], y, g)
        out["single"][nm] = {"full": a["auc"] if a else None,
                             "first": b["auc"] if b else None}
        print(f"     {nm:22s} {a['auc']:.3f} | {b['auc']:.3f}")

    json.dump(out, open(OUT / "scroll_carve.json", "w"), indent=1)
    print(f"\nwrote {OUT/'scroll_carve.json'}")


if __name__ == "__main__":
    main()
