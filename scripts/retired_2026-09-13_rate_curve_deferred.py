"""Sampling-rate curve for the DEFERRED task, plus a scroll+click-only floor.

WHY
---
§6 of the Leaky Cursor says "Sampling rate is not a deployment constraint, as
downsampling the AdSERP cursor stream ... to 1 Hz leaves M4 AUC flat
(0.847 +- 0.001)" and uses it to support deferred-class inference in
deployment. But every rate number in the paper (0.9338 native ... 0.9012 at
1 Hz, and the 0.847 figure) is measured on the CLICK task. The deferred task
has never been run down the rate curve. This producer runs it, and puts the
click curve beside it on the identical rows so the generalisation can be
checked rather than assumed.

TWO THINNING MODES, because the existing thinner is not a rate simulator
-----------------------------------------------------------------------
`compute_cursor_approach_features.downsample_mouse_events` thins ONLY
`mousemove`; click, scroll, mouseover, mouseout, mousedown and mouseup pass
through untouched by design (the click label must survive). But the feature
extractor consumes ALL of those as positional samples, so a "1 Hz" stream
still carries every mouseover. Both modes are therefore reported:

  mousemove_only  -- the paper's protocol, verbatim. What its numbers mean.
  all_positional  -- thin every positional event. What "1 Hz telemetry"
                     would actually give you.

The gap between them is the measurement Peter's skeptic read needs.

SCROLL+CLICK ONLY
-----------------
The floor condition: no cursor position stream at all. Features are built from
the scroll timeline and the viewport, which is the paper's own proposed mobile
analog ("viewport residence replaces cursor proximity-dwell"). Scroll events
are never thinned by the paper's thinner, so this condition is rate-independent
and sits underneath the whole curve.

OUTPUT
------
scripts/output/visit_decomposition/rate_curve_records.json
scripts/output/visit_decomposition/rate_curve_provenance.json

Run: .venv/bin/python scripts/rate_curve_deferred.py
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
# Canonical replacement: scripts/rate_curve_canonical.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/rate_curve_canonical.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")


import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "scripts" / "output" / "visit_decomposition"

from data_loader import (  # noqa: E402
    load_mouse_events, typed_gapfill_aoi_bands, get_trial_meta,
    attribute_click_to_typed_gapfill,
)
from compute_cursor_approach_features import downsample_mouse_events  # noqa: E402

POSITIONAL = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
RATES = [0, 30, 15, 10, 5, 2, 1]          # 0 = native
PROX = 100.0
MAX_DWELL_GAP_MS = 2000.0
MIN_VEL_DT_MS = 8.0
MAX_VEL = 10000.0

M4 = ["min_dist", "mean_dist", "dwell_in_proximity_ms",
      "mean_approach_velocity", "max_approach_velocity",
      "direction_changes", "frac_decreasing"]
SCROLL_FEATS = ["vp_residence_ms", "n_vp_entries", "min_vp_dist", "mean_vp_dist",
                "vp_hwm_return", "n_scroll_events", "session_ms"]


def thin_all_positional(all_events, hz):
    """Greedy thinning applied to EVERY positional event, not just mousemove.
    Non-positional events (load, scroll) pass through so the scroll timeline
    and trial span survive; clicks are kept so the label survives."""
    if not hz or hz <= 0:
        return all_events
    min_gap = 1000.0 / float(hz)
    kept, last = [], None
    for ev in all_events:
        t, evt = ev[0], ev[1]
        if evt == "click" or evt not in POSITIONAL:
            kept.append(ev)
            continue
        if last is None or (t - last) >= min_gap:
            kept.append(ev)
            last = t
    return kept


def cursor_features(ts, ys, bands, positions):
    """d(t) = |y_cursor - y_AOI_centre|. Identical maths to
    visit_dwell_vs_cursor.cursor_features so the curve's native point is
    comparable to the carve analysis."""
    out = {}
    if len(ts) < 2:
        return out
    dts = np.diff(ts)
    ok = dts > 0
    for pos in positions:
        if pos >= len(bands):
            continue
        top, bot = bands[pos][0], bands[pos][1]
        dist = np.abs(ys - (top + bot) / 2.0)
        dd = np.diff(dist)
        in_prox = dist < PROX
        dwell = float(dts[ok & in_prox[1:] & (dts < MAX_DWELL_GAP_MS)].sum())
        if ok.any():
            v = np.clip(-dd[ok] / np.maximum(dts[ok], MIN_VEL_DT_MS) * 1000.0,
                        -MAX_VEL, MAX_VEL)
            mv, xv = float(v.mean()), float(v.max())
            dc = int(np.sum(np.diff(np.sign(v)) != 0)) if len(v) > 1 else 0
            fd = float(np.mean(dd[ok] < 0))
        else:
            mv = xv = 0.0; dc = 0; fd = 0.0
        out[pos] = [float(dist.min()), float(dist.mean()), dwell, mv, xv,
                    float(dc), fd]
    return out


def scroll_features(scrolls, bands, positions, scr_h, t_span):
    """Viewport-residence features from the scroll timeline alone.

    The viewport is [scroll_y, scroll_y + scr_h]. vp_hwm_return asks the
    question Peter's condition is really about: did the scroll high-water mark
    pass below this AOI and the viewport later come back to contain it? That is
    a return event visible to scroll telemetry with no cursor at all.
    """
    out = {}
    if len(scrolls) < 2 or not scr_h:
        return out
    st = np.array([s[0] for s in scrolls], dtype=float)
    sy = np.array([s[1] for s in scrolls], dtype=float)
    dts = np.diff(st)
    ok = dts > 0
    vp_centre = sy + scr_h / 2.0
    for pos in positions:
        if pos >= len(bands):
            continue
        top, bot = bands[pos][0], bands[pos][1]
        c = (top + bot) / 2.0
        inside = (sy <= c) & (c <= sy + scr_h)
        residence = float(dts[ok & inside[1:] & (dts < 30000)].sum())
        entries = int(np.sum((~inside[:-1]) & inside[1:])) + int(inside[0])
        d = np.abs(c - vp_centre)
        # HWM return: viewport bottom got past this AOI, then the AOI came
        # back inside the viewport afterwards.
        hwm_return = 0
        hwm = -1e18
        passed_at = None
        for i in range(len(sy)):
            bottom = sy[i] + scr_h
            if bottom > hwm:
                hwm = bottom
            if passed_at is None and hwm > bot + scr_h * 0.25:
                passed_at = i
            elif passed_at is not None and inside[i]:
                hwm_return = 1
                break
        out[pos] = [residence, float(entries), float(d.min()), float(d.mean()),
                    float(hwm_return), float(len(scrolls)), float(t_span)]
    return out


def main():
    visit_recs = json.load(open(OUT / "records.json"))
    by_trial = defaultdict(list)
    for r in visit_recs:
        by_trial[r["trial_id"]].append(r)

    conditions = ([("mousemove_only", hz) for hz in RATES] +
                  [("all_positional", hz) for hz in RATES if hz != 0])
    ev_mix = Counter()
    records = []
    skipped = Counter()

    trials = sorted(by_trial)
    for i, tid in enumerate(trials, 1):
        if i % 300 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        rs = by_trial[tid]
        positions = [r["position"] for r in rs]
        try:
            bands = typed_gapfill_aoi_bands(tid)
            allev, scrolls, clicks = load_mouse_events(tid, space="screenshot")
        except Exception:
            skipped["load_failed"] += 1
            continue
        if not bands or len(allev) < 2:
            skipped["too_few_events"] += 1
            continue
        doc_h, scr_h, _ = get_trial_meta(tid)
        if scr_h:
            scr_h = scr_h * 0.9000   # screen height -> screenshot space (y ratio)
        for (_t, e, _x, _y) in allev:
            if e in POSITIONAL:
                ev_mix[e] += 1
        t_span = float(allev[-1][0] - allev[0][0])

        click_pos = None
        if clicks:
            # (click_x, click_y, trial_id) -> (position, etype) | None
            hit = attribute_click_to_typed_gapfill(
                clicks[-1][1], clicks[-1][2], tid)
            if hit is None:
                skipped["click_unattributed"] += 1
            else:
                click_pos = hit[0]

        per_cond = {}
        for mode, hz in conditions:
            thinner = downsample_mouse_events if mode == "mousemove_only" else thin_all_positional
            ev = thinner(allev, hz)
            pos_ev = [(t, y) for (t, e, x, y) in ev
                      if e in POSITIONAL and x > 0 and y > 0]
            if len(pos_ev) < 2:
                continue
            pos_ev.sort()
            ts = np.array([p[0] for p in pos_ev], dtype=float)
            ys = np.array([p[1] for p in pos_ev], dtype=float)
            name = f"{mode}@{'native' if hz == 0 else hz}"
            per_cond[name] = {"feats": cursor_features(ts, ys, bands, positions),
                              "n_samples": len(pos_ev)}
        sf = scroll_features(scrolls, bands, positions, scr_h, t_span)

        for r in rs:
            p = r["position"]
            rec = {
                "trial_id": tid, "participant": r["participant"], "position": p,
                "deferred": r["deferred"], "was_clicked": bool(click_pos == p),
                "first_visit_dwell_ms": r["first_visit_dwell_ms"],
                "total_dwell_ms": r["total_dwell_ms"],
                "cond": {}, "scroll": sf.get(p),
            }
            for name, blob in per_cond.items():
                f = blob["feats"].get(p)
                if f is not None:
                    rec["cond"][name] = f
            rec["n_samples"] = {n: b["n_samples"] for n, b in per_cond.items()}
            records.append(rec)

    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                      cwd=ROOT, text=True).strip()
    except Exception:
        sha = "unknown"
    prov = {
        "produced_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "scripts/rate_curve_deferred.py",
        "repo_head": sha, "rates_hz": RATES,
        "conditions": [f"{m}@{'native' if h == 0 else h}" for m, h in conditions],
        "n_records": len(records),
        "n_trials": len({r["trial_id"] for r in records}),
        "positional_event_mix": dict(ev_mix),
        "positional_event_share": {k: round(v / sum(ev_mix.values()), 4)
                                   for k, v in ev_mix.items()},
        "skipped": dict(skipped),
        "m4_order": M4, "scroll_feature_order": SCROLL_FEATS,
        "note": ("mousemove_only is downsample_mouse_events verbatim (thins only "
                 "mousemove); all_positional thins every positional event. "
                 "Scroll features are rate-independent: the thinner never "
                 "touches scroll events."),
    }
    json.dump(records, open(OUT / "rate_curve_records.json", "w"))
    json.dump(prov, open(OUT / "rate_curve_provenance.json", "w"), indent=1)
    print(json.dumps({k: prov[k] for k in
                      ["n_records", "n_trials", "positional_event_share",
                       "skipped"]}, indent=1))


if __name__ == "__main__":
    main()
