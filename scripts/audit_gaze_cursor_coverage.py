"""Gaze-cursor coupling validity in the click-deliberation window.

The AllSERP resource paper claims that gaze and cursor streams are
spatially registered against the same screenshots. This audit checks
the claim end-to-end: in the lead-up to the final click, did gaze ever
land near the click target? If not — if gaze and cursor never co-locate
even within a generous 1.5 s deliberation window — the data isn't
spatially registered and downstream models are at risk.

Two metrics, intentionally
--------------------------

(A) **Concurrent at-click distance.** For the fixation that encompasses
    click_t (or, failing that, the nearest fixation within ±1 s), the
    Euclidean distance to the click coordinates. This is *not* a
    coupling-validity metric — gaze leads cursor by ~650 ms on SERPs
    (Huang/White/Buscher CHI 2012; AdSERP NB11:K1) so by click_t gaze
    has typically already moved on to the next candidate. We report it
    only to show that synchrony is not the right question.

(B) **Lead-window minimum distance.** Across all fixations whose
    midpoint falls in [click_t − 1500 ms, click_t], the minimum
    Euclidean distance to the click coordinates. This is the
    spatial-registration check: did gaze EVER look near the click
    target in the lead-up? If yes, the streams are co-located when it
    matters; if no, they aren't.

Aggregates
----------

For each metric:
- n trials with eligible fixation
- median distance
- p25 / p75 / p95
- pct above pathological threshold T (default 250 px ≈ ~3° visual
  angle, well past the 0.5–1° GP3 calibration tolerance)

Output
------

JSON written to scripts/output/allserp/gaze_cursor_coverage.json
with full provenance via muriel.provenance.

Regime tag: [LAB, AdSERP, allserp-validity-2026-05-10]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, "/Users/andyed/.claude/skills/muriel")

from data_loader import (  # noqa: E402
    get_trial_ids, load_fixations, load_mouse_events,
)
from muriel.provenance import stamp_json  # noqa: E402

WINDOW_MS = 1000          # ±W around click_t for metric (A) fallback
LEAD_WINDOW_MS = 1500     # [click_t − L, click_t] for metric (B)
PATHOLOGICAL_PX = 250


def best_fixation_at(fixations: list[dict], click_t: float) -> tuple[dict, str] | None:
    """Return (fixation, kind) where kind is 'concurrent' or 'window'.

    Concurrent: a fixation whose interval [t, t+d] contains click_t.
    Window: nearest fixation midpoint within ±WINDOW_MS of click_t.
    """
    if not fixations:
        return None

    concurrent = []
    for f in fixations:
        t0 = f["t"]
        t1 = t0 + f["d"]
        if t0 <= click_t <= t1:
            concurrent.append(f)
    if concurrent:
        return max(concurrent, key=lambda f: f["d"]), "concurrent"

    best = None
    best_dt = WINDOW_MS + 1
    for f in fixations:
        mid = f["t"] + f["d"] / 2.0
        dt = abs(mid - click_t)
        if dt < best_dt:
            best_dt = dt
            best = f
    if best is not None and best_dt <= WINDOW_MS:
        return best, "window"
    return None


def lead_window_min_distance(
    fixations: list[dict], click_t: float, click_x: float, click_y: float,
) -> tuple[float, int] | None:
    """Min Euclidean distance from any lead-window fixation to the click.

    Lead window: [click_t − LEAD_WINDOW_MS, click_t], by fixation midpoint.
    Returns (min_distance_px, n_fixations_in_window) or None if window empty.
    """
    in_window = []
    lo = click_t - LEAD_WINDOW_MS
    for f in fixations:
        mid = f["t"] + f["d"] / 2.0
        if lo <= mid <= click_t:
            in_window.append(f)
    if not in_window:
        return None
    best = min(
        np.hypot(f["x"] - click_x, f["y"] - click_y) for f in in_window
    )
    return float(best), len(in_window)


def percentiles(arr: np.ndarray) -> dict:
    if len(arr) == 0:
        return {"median": None, "p25": None, "p75": None, "p95": None}
    return {
        "median": float(np.median(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
    }


def main() -> int:
    tids = get_trial_ids()
    n_total = len(tids)
    print(f"Auditing {n_total:,} trials", file=sys.stderr)

    n_with_click = 0
    n_concurrent = 0
    n_window = 0
    n_no_fixation = 0
    n_lead_window_empty = 0
    concurrent_distances: list[float] = []
    lead_min_distances: list[float] = []
    per_trial: list[dict] = []

    for i, tid in enumerate(tids):
        if i and i % 500 == 0:
            print(f"  {i:,}/{n_total:,}", file=sys.stderr)
        try:
            _, _, clicks = load_mouse_events(tid)
            fixations = load_fixations(tid)
        except FileNotFoundError:
            continue
        if not clicks:
            continue
        n_with_click += 1
        click_t, click_x, click_y = clicks[-1]
        record: dict = {
            "trial_id": tid,
            "click_xy": [click_x, click_y],
            "click_t": click_t,
        }

        # Metric (A) — concurrent at-click distance
        result = best_fixation_at(fixations, click_t)
        if result is None:
            n_no_fixation += 1
            record["concurrent_kind"] = "none"
        else:
            fix, kind = result
            if kind == "concurrent":
                n_concurrent += 1
            else:
                n_window += 1
            d = float(np.hypot(fix["x"] - click_x, fix["y"] - click_y))
            concurrent_distances.append(d)
            record.update({
                "concurrent_kind": kind,
                "concurrent_fix_xy": [fix["x"], fix["y"]],
                "concurrent_distance_px": d,
            })

        # Metric (B) — lead-window minimum distance
        lead = lead_window_min_distance(fixations, click_t, click_x, click_y)
        if lead is None:
            n_lead_window_empty += 1
            record["lead_min_distance_px"] = None
            record["lead_n_fixations"] = 0
        else:
            min_d, n_fix = lead
            lead_min_distances.append(min_d)
            record["lead_min_distance_px"] = min_d
            record["lead_n_fixations"] = n_fix
        per_trial.append(record)

    a_arr = np.array(concurrent_distances, dtype=float)
    b_arr = np.array(lead_min_distances, dtype=float)
    a_path = int((a_arr > PATHOLOGICAL_PX).sum())
    b_path = int((b_arr > PATHOLOGICAL_PX).sum())

    metric_a = {
        **percentiles(a_arr),
        "n_distances": int(len(a_arr)),
        "n_pathological": a_path,
        "pct_pathological": float(100.0 * a_path / len(a_arr)) if len(a_arr) else None,
    }
    metric_b = {
        **percentiles(b_arr),
        "n_distances": int(len(b_arr)),
        "n_pathological": b_path,
        "pct_pathological": float(100.0 * b_path / len(b_arr)) if len(b_arr) else None,
    }

    summary = {
        "regime": "[LAB, AdSERP, allserp-validity-2026-05-10]",
        "concurrent_window_ms": WINDOW_MS,
        "lead_window_ms": LEAD_WINDOW_MS,
        "pathological_threshold_px": PATHOLOGICAL_PX,
        "n_trials_total": n_total,
        "n_trials_with_click": n_with_click,
        "n_with_concurrent_fixation": n_concurrent,
        "n_with_window_fallback": n_window,
        "n_with_no_eligible_fixation": n_no_fixation,
        "n_lead_window_empty": n_lead_window_empty,
        "metric_a_concurrent_at_click": metric_a,
        "metric_b_lead_window_min": metric_b,
        "per_trial": per_trial,
    }

    print("\n────────────────────────────────────────────────────", file=sys.stderr)
    print("Gaze-cursor spatial-registration validity (AllSERP)", file=sys.stderr)
    print("────────────────────────────────────────────────────", file=sys.stderr)
    print(f"  trials                          : {n_total:,}", file=sys.stderr)
    print(f"  with final click                : {n_with_click:,}", file=sys.stderr)
    print(f"  no eligible fixation (A)        : {n_no_fixation:,}", file=sys.stderr)
    print(f"  empty lead window (B)           : {n_lead_window_empty:,}",
          file=sys.stderr)
    print()
    print("  Metric (A) — concurrent at-click distance:", file=sys.stderr)
    print(f"    n      : {metric_a['n_distances']:,}", file=sys.stderr)
    print(f"    median : {metric_a['median']:.1f} px", file=sys.stderr)
    print(f"    IQR    : {metric_a['p25']:.1f} – {metric_a['p75']:.1f} px",
          file=sys.stderr)
    print(f"    p95    : {metric_a['p95']:.1f} px", file=sys.stderr)
    print(f"    > {PATHOLOGICAL_PX} px : {metric_a['n_pathological']} "
          f"({metric_a['pct_pathological']:.2f}%)", file=sys.stderr)
    print()
    print(f"  Metric (B) — lead-window ([click_t − {LEAD_WINDOW_MS} ms, click_t]) "
          f"min distance:", file=sys.stderr)
    print(f"    n      : {metric_b['n_distances']:,}", file=sys.stderr)
    print(f"    median : {metric_b['median']:.1f} px", file=sys.stderr)
    print(f"    IQR    : {metric_b['p25']:.1f} – {metric_b['p75']:.1f} px",
          file=sys.stderr)
    print(f"    p95    : {metric_b['p95']:.1f} px", file=sys.stderr)
    print(f"    > {PATHOLOGICAL_PX} px : {metric_b['n_pathological']} "
          f"({metric_b['pct_pathological']:.2f}%)", file=sys.stderr)

    out_path = ROOT / "scripts/output/allserp/gaze_cursor_coverage.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_json(
        summary, out_path,
        script=__file__,
        dataset="AdSERP/data/{fixations,mouse-movement-data}",
        h_ids=[],
        nb_k_ids=[],
        figure_version="allserp-validity",
        notes=(
            f"Gaze-cursor spatial coupling validity at click moment. "
            f"Window ±{WINDOW_MS} ms, pathological > {PATHOLOGICAL_PX} px."
        ),
    )
    print(f"\nWrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
