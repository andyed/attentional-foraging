"""NB31 — Motor-event → fixation-location predictions.

Peter Dixon-Moses (Slack 2026-04-19): four testable predictions about
where gaze lands after motor events.

  Test 1: scroll event → next fixation at viewport bottom
  Test 2: large scroll → next fixation moves back toward top
  Test 3: scroll regression → next fixation at viewport top
  Test 4: mouse event → fixation co-located with mouse y

On AdSERP LAB: gaze + mouse + scroll streams already loaded by
data_loader. For each motor event, find the next fixation in a small
window and record its viewport-relative y. Aggregate and test.

Output: scripts/output/nb31_motor_fixation/summary.json + per-test
medians / p-values.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, wilcoxon

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (
    get_trial_ids, get_trial_meta, load_fixations, load_mouse_events,
)

OUT = ROOT / "scripts/output/nb31_motor_fixation"
OUT.mkdir(parents=True, exist_ok=True)

# Windows for "next fixation after event" matching
NEXT_FIX_WINDOW_MS = 1000
LARGE_SCROLL_PX = 200  # threshold for "large" scroll event
SCROLL_REGRESSION_PX = -30  # threshold for regressive scroll (negative = up)


def scroll_y_at(t_ms, scrolls):
    """Piecewise-constant scrollY at time t. scrolls is sorted list of (t, y)."""
    if not scrolls:
        return 0.0
    # Binary search or simple linear scan (trials are small enough)
    y = 0.0
    for (ts, sy) in scrolls:
        if ts > t_ms:
            break
        y = float(sy)
    return y


def mouse_y_at(t_ms, mouse):
    """Page-space mouse_y at time t (closest previous event)."""
    if not mouse:
        return None
    y = None
    for (tm, mx, my) in mouse:
        if tm > t_ms:
            break
        y = float(my)
    return y


def main():
    trials = get_trial_ids()
    print(f"trials to process: {len(trials):,}")

    # Collectors — keyed by test
    t1_viewport_y = []        # scroll event → next fix viewport-y
    t2_rows = []              # (scroll_magnitude_px, viewport_y)
    t3_regress_vp_y = []      # scroll regression → next fix viewport-y
    t4_mouse_offset_px = []   # |fix_y − mouse_y| at nearest fix
    t4_random_offset_px = []  # baseline: |random_fix_y − mouse_y|

    viewport_heights = []

    n_ok = 0
    for tid in trials:
        try:
            _, scr_h, _ = get_trial_meta(tid)
        except Exception:
            continue
        if scr_h <= 0:
            continue
        fixations = load_fixations(tid)
        mouse, scrolls, _ = load_mouse_events(tid)
        if not fixations:
            continue

        # Normalize fix entries: expect (t, page_x, page_y, dur)
        fix_list = []
        for f in fixations:
            if isinstance(f, dict):
                fix_list.append((f.get("t"), f.get("x"), f.get("y"), f.get("dur", 0)))
            else:
                # tuple / list form
                if len(f) >= 3:
                    fix_list.append((f[0], f[1], f[2], f[3] if len(f) > 3 else 0))
        if not fix_list:
            continue
        # Mouse events: (t, x, y) form — from load_mouse_events (filtered to movement type)
        mouse_list = []
        for e in mouse:
            if isinstance(e, (list, tuple)) and len(e) >= 3:
                mouse_list.append((e[0], e[1], e[2]))
        scroll_list = sorted([(s[0], s[1]) for s in scrolls])

        viewport_heights.append(scr_h)
        n_ok += 1

        # For each fixation, find the next one (for baselines)
        fix_times = np.array([f[0] for f in fix_list])
        fix_ys = np.array([f[2] for f in fix_list])

        # ── Test 1 / 2 / 3: scroll event → next fixation ──
        for (st, sy) in scroll_list:
            # Next fixation within NEXT_FIX_WINDOW_MS
            nf_idx = np.searchsorted(fix_times, st)
            if nf_idx >= len(fix_times):
                continue
            nf_t = fix_times[nf_idx]
            if nf_t - st > NEXT_FIX_WINDOW_MS:
                continue
            # Viewport y = page_y − scroll_y_at(fix_time)
            sy_at_fix = scroll_y_at(nf_t, scroll_list)
            vp_y = fix_ys[nf_idx] - sy_at_fix
            # Clamp to viewport bounds for sanity (discard fixations outside vp)
            if vp_y < 0 or vp_y > scr_h:
                continue

            t1_viewport_y.append(vp_y / scr_h)  # normalize by viewport height

            # For Test 2 and 3, compute scroll magnitude: sy − previous scrollY
            prev_sy = scroll_list[scroll_list.index((st, sy)) - 1][1] if scroll_list.index((st, sy)) > 0 else 0.0
            scroll_delta = sy - prev_sy
            t2_rows.append((scroll_delta, vp_y / scr_h))

            if scroll_delta < SCROLL_REGRESSION_PX:
                t3_regress_vp_y.append(vp_y / scr_h)

        # ── Test 4: mouse event → fix co-located with mouse y ──
        # Sample: take every 5th mouse event to keep the test set manageable
        for i, (mt, mx, my) in enumerate(mouse_list[::5]):
            # Nearest fixation in time (before or after, within ±500 ms)
            nf_idx = np.searchsorted(fix_times, mt)
            candidates = []
            if nf_idx < len(fix_times) and fix_times[nf_idx] - mt <= 500:
                candidates.append(nf_idx)
            if nf_idx > 0 and mt - fix_times[nf_idx - 1] <= 500:
                candidates.append(nf_idx - 1)
            if not candidates:
                continue
            fi = min(candidates, key=lambda k: abs(fix_times[k] - mt))
            actual = abs(fix_ys[fi] - my)
            t4_mouse_offset_px.append(actual)
            # Random baseline: compare to another random fixation in the trial
            rand_fi = np.random.randint(0, len(fix_ys))
            t4_random_offset_px.append(abs(fix_ys[rand_fi] - my))

    print(f"usable trials: {n_ok:,}")
    print(f"median viewport height: {np.median(viewport_heights):.0f} px")

    # ── Test 1 ──
    print("\n" + "=" * 72)
    print("Test 1: scroll event → next fixation at viewport bottom?")
    print("=" * 72)
    vp_y_arr = np.array(t1_viewport_y)
    print(f"  N events with valid next-fix: {len(vp_y_arr):,}")
    if len(vp_y_arr) > 0:
        print(f"  fix viewport-y as fraction of scr_h:")
        print(f"    mean = {vp_y_arr.mean():.3f}   median = {np.median(vp_y_arr):.3f}")
        print(f"    quartiles = {np.percentile(vp_y_arr, 25):.3f} / {np.percentile(vp_y_arr, 50):.3f} / {np.percentile(vp_y_arr, 75):.3f}")
        # Test: is the mean > 0.5? (bottom half)
        # Use one-sample Wilcoxon against 0.5
        try:
            w = wilcoxon(vp_y_arr - 0.5, alternative="greater")
            p1 = float(w.pvalue)
        except Exception:
            p1 = float("nan")
        print(f"    one-sample Wilcoxon (fix_vp_y > 0.5 of scr_h): p = {p1:.4e}")
        bottom_third = (vp_y_arr > 2 / 3).mean()
        top_third = (vp_y_arr < 1 / 3).mean()
        print(f"    % in bottom third = {bottom_third*100:.1f}%   % in top third = {top_third*100:.1f}%")

    # ── Test 2 ──
    print("\n" + "=" * 72)
    print("Test 2: large scroll → next fixation moves back toward top?")
    print("=" * 72)
    if t2_rows:
        deltas = np.array([r[0] for r in t2_rows])
        vps = np.array([r[1] for r in t2_rows])
        # Bin by scroll delta magnitude (absolute)
        bins = [(-1e9, -200), (-200, -50), (-50, 50), (50, 200), (200, 1e9)]
        print(f"  bin                  n      mean vp-y  median vp-y")
        for (lo, hi) in bins:
            mask = (deltas >= lo) & (deltas < hi)
            if mask.sum() < 10:
                continue
            print(f"  ({lo:+.0f}, {hi:+.0f})   {mask.sum():>6}   {vps[mask].mean():.3f}    {np.median(vps[mask]):.3f}")
        # Test: do LARGE positive scrolls (delta > 200) have fixations closer to top than small positive (50-200)?
        large_pos = (deltas > 200)
        mid_pos = (deltas > 50) & (deltas <= 200)
        if large_pos.sum() >= 10 and mid_pos.sum() >= 10:
            u, p2 = mannwhitneyu(vps[large_pos], vps[mid_pos], alternative="less")
            print(f"  Mann–Whitney (large-scroll fix-vp-y < mid-scroll fix-vp-y): U = {u:.0f}, p = {p2:.4e}")

    # ── Test 3 ──
    print("\n" + "=" * 72)
    print(f"Test 3: scroll regression (Δ < {SCROLL_REGRESSION_PX} px) → next fix at viewport top?")
    print("=" * 72)
    reg_arr = np.array(t3_regress_vp_y)
    print(f"  N regression events with valid next-fix: {len(reg_arr):,}")
    if len(reg_arr) > 0:
        print(f"  fix viewport-y as fraction of scr_h:")
        print(f"    mean = {reg_arr.mean():.3f}   median = {np.median(reg_arr):.3f}")
        try:
            w = wilcoxon(reg_arr - 0.5, alternative="less")
            p3 = float(w.pvalue)
        except Exception:
            p3 = float("nan")
        print(f"    one-sample Wilcoxon (fix_vp_y < 0.5 of scr_h): p = {p3:.4e}")
        top_third = (reg_arr < 1 / 3).mean()
        bottom_third = (reg_arr > 2 / 3).mean()
        print(f"    % in top third = {top_third*100:.1f}%   % in bottom third = {bottom_third*100:.1f}%")

    # ── Test 4 ──
    print("\n" + "=" * 72)
    print("Test 4: mouse event → fixation co-located with mouse y?")
    print("=" * 72)
    actual = np.array(t4_mouse_offset_px)
    rand = np.array(t4_random_offset_px)
    print(f"  N events sampled: {len(actual):,}")
    if len(actual) > 0:
        print(f"  |fix_y − mouse_y| at nearest fix:   median = {np.median(actual):.0f} px")
        print(f"  |fix_y − mouse_y| at random baseline: median = {np.median(rand):.0f} px")
        u, p4 = mannwhitneyu(actual, rand, alternative="less")
        print(f"  Mann–Whitney (actual < random): U = {u:.0f}, p = {p4:.4e}")
        print(f"  actual/random ratio of medians: {np.median(actual)/np.median(rand):.2f}")

    summary = {
        "n_trials_used": n_ok,
        "median_viewport_h_px": int(np.median(viewport_heights)) if viewport_heights else None,
        "test1_scroll_to_next_fix": {
            "n": len(t1_viewport_y),
            "mean_frac_of_scr_h": float(np.mean(t1_viewport_y)) if t1_viewport_y else None,
            "median_frac_of_scr_h": float(np.median(t1_viewport_y)) if t1_viewport_y else None,
            "wilcoxon_vs_0.5_greater_p": float(p1) if t1_viewport_y else None,
        },
        "test3_regression_to_next_fix": {
            "n": len(t3_regress_vp_y),
            "mean_frac_of_scr_h": float(np.mean(t3_regress_vp_y)) if len(reg_arr) else None,
            "wilcoxon_vs_0.5_less_p": float(p3) if len(reg_arr) else None,
        },
        "test4_mouse_to_fix": {
            "n": len(actual),
            "median_actual_px": int(np.median(actual)) if len(actual) else None,
            "median_random_px": int(np.median(rand)) if len(actual) else None,
            "mannwhitney_p": float(p4) if len(actual) else None,
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
