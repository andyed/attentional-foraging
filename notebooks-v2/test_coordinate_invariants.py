"""Regression test: coordinate-space invariants for AdSERP.

Locks in the conventions documented in data_loader.py's module docstring.
All three streams (gaze, cursor, click) are PAGE-space. Prior versions of
this test enforced the false "gaze is screen-space" contract that caused
the 2026-04-12 fixation-side coordinate bug.

Run:
    /Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
        notebooks-v2/test_coordinate_invariants.py

Exit code 0 if all invariants hold, 1 otherwise. Prints a clear summary.
"""
from __future__ import annotations

import math
import statistics
import sys
from bisect import bisect_right
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    click_to_position,
    count_results_html,
    cursor_to_position,
    gaze_cursor_distance,
    get_click_page_xy,
    get_trial_ids,
    get_trial_meta,
    interpolate_cursor_at,
    interpolate_scroll,
    load_fixations,
    load_mouse_events,
    page_y_to_viewport_y,
    result_band_tops,
    viewport_y_to_page_y,
)

SCROLLED_TRIAL = 'p004-b2-t3'   # 163 scroll events, max scroll ~1111 px
NO_SCROLL_TRIAL = 'p004-b1-t1'  # 0 scroll events
DEEP_SCROLL_TRIAL = 'p045-b2-t6'  # 312 fixations, heavy scrolling

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = '') -> None:
    mark = 'PASS' if cond else 'FAIL'
    print(f'  [{mark}] {name}' + (f'  — {detail}' if detail else ''))
    if not cond:
        FAILURES.append(name)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 1: evtrack mouse Y empirically exceeds window height.
# Ground-truth check that cursor ypos is page-space (pageY, includes scroll).
# ─────────────────────────────────────────────────────────────────────────
print('[1] evtrack ypos is page-space (pageY, includes scroll)')
events, scrolls, clicks = load_mouse_events(SCROLLED_TRIAL)
mouse_ys = [y for (_, evt, _, y) in events
            if evt in ('mousemove', 'click', 'mouseover') and y > 0]
max_mouse_y = max(mouse_ys) if mouse_ys else 0
# Window height from trial metadata — see AdSERP README trial-metadata XML.
# For p004-b2-t3 the window is 1137 px tall; any mouse Y exceeding that
# proves ypos is page-space.
WINDOW_H = 1137
check(
    'max mouse Y exceeds window height on scrolled trial',
    max_mouse_y > WINDOW_H,
    f'max={max_mouse_y:.0f}px  window={WINDOW_H}px',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 2: FPOGY is PAGE-space (includes scroll).
# Three converging checks on a heavily-scrolled trial:
#   2a. Max FPOGY exceeds screen_height — impossible if viewport-bounded.
#   2b. Pearson r(FPOGY, scrollY) is strongly positive — FPOGY tracks scroll.
#   2c. (FPOGY − scrollY) falls inside the viewport for most fixations —
#       the residual has viewport shape.
# AdSERP README: "FPOGX/FPOGY ... relative to the top-left corner of the
# screenshot in pixels" (the screenshot is the full-page capture).
# ─────────────────────────────────────────────────────────────────────────
print('\n[2] FPOGY is page-space (AdSERP README + empirical)')
deep_fixations = load_fixations(DEEP_SCROLL_TRIAL)
_, deep_scrolls, _ = load_mouse_events(DEEP_SCROLL_TRIAL)
deep_doc_h, deep_scr_h, _ = get_trial_meta(DEEP_SCROLL_TRIAL)
deep_scroll_ts = [s[0] for s in deep_scrolls]
deep_scroll_ys = [s[1] for s in deep_scrolls]

fpogy_vals = [f['y'] for f in deep_fixations]
max_fpogy = max(fpogy_vals)
check(
    '2a. max FPOGY exceeds screen_height on scrolled trial',
    max_fpogy > deep_scr_h,
    f'max_fpogy={max_fpogy:.0f}  scr_h={deep_scr_h}',
)

# Pearson r(FPOGY, scrollY) at fixation times
pair_y = []
pair_s = []
for f in deep_fixations:
    sy = interpolate_scroll(f['t'], deep_scroll_ts, deep_scroll_ys)
    pair_y.append(f['y'])
    pair_s.append(sy)
if len(pair_y) >= 3 and statistics.stdev(pair_s) > 0:
    mean_y = statistics.mean(pair_y)
    mean_s = statistics.mean(pair_s)
    cov = sum((y - mean_y) * (s - mean_s) for y, s in zip(pair_y, pair_s)) / len(pair_y)
    r_ys = cov / (statistics.stdev(pair_y) * statistics.stdev(pair_s))
else:
    r_ys = 0.0
check(
    '2b. Pearson r(FPOGY, scrollY) > 0.5',
    r_ys > 0.5,
    f'r={r_ys:.3f}',
)

# Viewport residual: (FPOGY - scroll) should fit in [0, scr_h] modulo a
# small tolerance for the eye tracker's occasional over-range reports.
residuals = [y - s for y, s in zip(pair_y, pair_s)]
TOL = 50
in_viewport = sum(1 for r in residuals if -TOL <= r <= deep_scr_h + TOL)
frac_vp = in_viewport / max(len(residuals), 1)
check(
    '2c. (FPOGY - scrollY) in viewport for >90% of fixations',
    frac_vp > 0.9,
    f'frac={frac_vp:.1%}  tol=±{TOL}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 3: assign_fixation_to_position is a simple page-space bisect.
# New signature: (page_y, tops, n_results). No scroll param.
# ─────────────────────────────────────────────────────────────────────────
print('\n[3] assign_fixation_to_position: page-space bisect, no scroll')
doc_h, scr_h, _ = get_trial_meta(SCROLLED_TRIAL)
n_results = max(count_results_html(SCROLLED_TRIAL), 1)
tops = result_band_tops(n_results, doc_h)

# Synthetic page_y in the middle of the page
fake_page_y = (tops[len(tops) // 2] + tops[len(tops) // 2 + 1]) / 2 if len(tops) >= 2 else tops[0] + 100
pos_via_helper = assign_fixation_to_position(fake_page_y, tops, n_results)
pos_manual = bisect_right(tops, fake_page_y) - 1
if not (0 <= pos_manual < n_results):
    pos_manual = -1
check(
    'assign_fixation_to_position matches manual bisect',
    pos_via_helper == pos_manual,
    f'helper={pos_via_helper}  manual={pos_manual}  '
    f'page_y={fake_page_y:.0f}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 4: click_to_position — click_y is already page-space.
# ─────────────────────────────────────────────────────────────────────────
print('\n[4] click_to_position: page-space click contract')
if clicks:
    _ct, _cx, cy_page = clicks[-1]
    pos_correct = click_to_position(clicks, tops, n_results)
    pos_manual_correct = bisect_right(tops, cy_page) - 1
    if not (0 <= pos_manual_correct < n_results):
        pos_manual_correct = None
    check(
        'click_to_position == manual page-space bisect',
        pos_correct == pos_manual_correct,
        f'helper={pos_correct}  manual={pos_manual_correct}',
    )

    if pos_correct is not None:
        band_top = tops[pos_correct]
        band_bot = (tops[pos_correct + 1] if pos_correct + 1 < len(tops)
                    else float('inf'))
        in_band = band_top <= cy_page < band_bot
        check(
            'click_y_page lies within its reported band',
            in_band,
            f'click_y={cy_page:.0f}  band=[{band_top:.0f}, '
            f'{band_bot:.0f})  pos={pos_correct}',
        )
else:
    check('trial has clicks', False, 'no clicks in SCROLLED_TRIAL')


# ─────────────────────────────────────────────────────────────────────────
# Invariant 5: gaze_cursor_distance is scroll-invariant.
# Both inputs are page-space, so scroll never enters. Prior implementation
# took a scroll_y_at_t parameter; the new one does not. Same answer for
# any synthetic point pair regardless of scroll position.
# ─────────────────────────────────────────────────────────────────────────
print('\n[5] gaze_cursor_distance: scroll-invariant, page-space Euclidean')
fix_x, fix_y_page = 500.0, 1400.0
cur_x, cur_y_page = 520.0, 1420.0
d_expected = math.hypot(fix_x - cur_x, fix_y_page - cur_y_page)
d_helper = gaze_cursor_distance(fix_x, fix_y_page, cur_x, cur_y_page)
check(
    'helper == raw Euclidean (page-space)',
    abs(d_helper - d_expected) < 1e-6,
    f'helper={d_helper:.3f}  raw={d_expected:.3f}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 6: no-scroll trial sanity — fixations never exceed scr_h.
# On a trial that never scrolled, FPOGY is bounded by the initial viewport
# (modulo eye-tracker over-range noise). This is a safety check that the
# page-space interpretation still predicts what we'd see on a trial where
# page-space and viewport-space happen to coincide.
# ─────────────────────────────────────────────────────────────────────────
print('\n[6] no-scroll trial: FPOGY bounded by viewport')
no_scroll_fixations = load_fixations(NO_SCROLL_TRIAL)
_, scrolls_ns, clicks_ns = load_mouse_events(NO_SCROLL_TRIAL)
ns_doc_h, ns_scr_h, _ = get_trial_meta(NO_SCROLL_TRIAL)
check('no-scroll trial has zero scroll events', len(scrolls_ns) == 0)
ns_ys = [f['y'] for f in no_scroll_fixations]
if ns_ys:
    max_ns_y = max(ns_ys)
    # Allow the standard 50 px over-range tolerance for eye tracker noise.
    check(
        'no-scroll trial: max FPOGY ≤ scr_h + tolerance',
        max_ns_y <= ns_scr_h + 50,
        f'max_fpogy={max_ns_y:.0f}  scr_h={ns_scr_h}',
    )


# ─────────────────────────────────────────────────────────────────────────
# Invariant 7: interpolate_cursor_at stays within its bracket.
# ─────────────────────────────────────────────────────────────────────────
print('\n[7] interpolate_cursor_at stays within its bracket')
import numpy as np  # noqa: E402

mouse_timeline = [(t, x, y) for (t, evt, x, y) in events
                  if evt in ('mousemove', 'click', 'mouseover') and y > 0]
if len(mouse_timeline) >= 3:
    mt = np.array([m[0] for m in mouse_timeline], dtype=float)
    mx = np.array([m[1] for m in mouse_timeline], dtype=float)
    my = np.array([m[2] for m in mouse_timeline], dtype=float)
    mid_t = (mt[0] + mt[-1]) / 2
    out = interpolate_cursor_at(mid_t, mt, mx, my)
    if out is not None:
        x_out, y_out = out
        x_min, x_max = float(mx.min()), float(mx.max())
        y_min, y_max = float(my.min()), float(my.max())
        check(
            'interpolated x within observed range',
            x_min <= x_out <= x_max,
            f'x={x_out:.1f} range=[{x_min:.0f}, {x_max:.0f}]',
        )
        check(
            'interpolated y within observed range',
            y_min <= y_out <= y_max,
            f'y={y_out:.1f} range=[{y_min:.0f}, {y_max:.0f}]',
        )


# ─────────────────────────────────────────────────────────────────────────
# Invariant 8: viewport↔page round-trip (for the rare caller that needs it).
# ─────────────────────────────────────────────────────────────────────────
print('\n[8] viewport↔page round-trip')
for y, scroll_val in [(100, 50), (1000, 300), (0, 0), (500, 0)]:
    page = viewport_y_to_page_y(y, scroll_val)
    back = page_y_to_viewport_y(page, scroll_val)
    check(
        f'round-trip viewport={y} scroll={scroll_val}',
        abs(back - y) < 1e-9,
        f'back={back}',
    )


# ─────────────────────────────────────────────────────────────────────────
# Invariant 9: Synthetic corner cases for click_to_position.
# ─────────────────────────────────────────────────────────────────────────
print('\n[9] click_to_position: synthetic corner cases')
fake_tops = [200.0, 500.0, 800.0, 1100.0, 1400.0]
fake_n = 5


def _mk_click(y: float) -> list:
    return [(0, 0, float(y))]


check(
    'click at tops[0]=200 → pos 0',
    click_to_position(_mk_click(200.0), fake_tops, fake_n) == 0,
)
check(
    'click at tops[1]=500 → pos 1',
    click_to_position(_mk_click(500.0), fake_tops, fake_n) == 1,
)
check(
    'click at 499.99 → pos 0 (just above next band)',
    click_to_position(_mk_click(499.99), fake_tops, fake_n) == 0,
)
check(
    'click at 2000 (past last top) → pos 4',
    click_to_position(_mk_click(2000.0), fake_tops, fake_n) == 4,
)
check(
    'click at 100 (above first top) → None',
    click_to_position(_mk_click(100.0), fake_tops, fake_n) is None,
)
check(
    'empty clicks → None',
    click_to_position([], fake_tops, fake_n) is None,
)

# Deep click (past scr_h) must not be clamped.
SCR_H = 1024
big_click_y = SCR_H + 600
check(
    'click past scr_h is NOT clamped — deep position preserved',
    click_to_position(_mk_click(big_click_y), fake_tops, fake_n) == 4,
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 10: Corpus-wide page-space bounds for BOTH streams.
# For every trial: every fixation Y and every click Y must lie within
# the page (0 ≤ y ≤ doc_h + tolerance). Report trials where the OLD
# buggy formula (`fix.y + scroll`) would have exceeded doc_h — those are
# the trials that were actively mis-mapped by the pre-2026-04-12 pipeline.
# ─────────────────────────────────────────────────────────────────────────
print('\n[10] corpus-wide: FPOGY and click_y within page bounds')
trial_ids = get_trial_ids()
TOL_PAGE = 100  # small slack for eye-tracker over-range

fix_in_bounds = 0
fix_out_bounds = 0
click_in_bounds = 0
click_out_bounds = 0
buggy_overflow_trials = 0
inspected = 0

for tid in trial_ids:
    meta = get_trial_meta(tid)
    if not meta[0]:
        continue
    doc_h_t = meta[0]
    inspected += 1

    fixes = load_fixations(tid)
    _, t_scrolls, t_clicks = load_mouse_events(tid)
    scroll_ts_t = [s[0] for s in t_scrolls]
    scroll_ys_t = [s[1] for s in t_scrolls]

    for f in fixes:
        if 0 <= f['y'] <= doc_h_t + TOL_PAGE:
            fix_in_bounds += 1
        else:
            fix_out_bounds += 1

    for (ct, _cx, cy) in t_clicks:
        if 0 <= cy <= doc_h_t + TOL_PAGE:
            click_in_bounds += 1
        else:
            click_out_bounds += 1

    # Did the OLD formula (fix.y + scroll) produce any y beyond doc_h?
    if scroll_ts_t:
        for f in fixes:
            sy = interpolate_scroll(f['t'], scroll_ts_t, scroll_ys_t)
            buggy_y = f['y'] + sy
            if buggy_y > doc_h_t + TOL_PAGE:
                buggy_overflow_trials += 1
                break

total_fix = fix_in_bounds + fix_out_bounds
total_click = click_in_bounds + click_out_bounds
print(f'   trials inspected: {inspected}')
print(f'   fixations in-bounds: {fix_in_bounds}/{total_fix} '
      f'({100 * fix_in_bounds / max(total_fix, 1):.2f}%)')
print(f'   clicks    in-bounds: {click_in_bounds}/{total_click} '
      f'({100 * click_in_bounds / max(total_click, 1):.2f}%)')
print(f'   trials where OLD formula fix.y + scroll overflows doc_h: '
      f'{buggy_overflow_trials}/{inspected}')

check(
    'FPOGY in [0, doc_h + tol] for >98% of fixations corpus-wide',
    fix_in_bounds / max(total_fix, 1) > 0.98,
)
check(
    'click_y in [0, doc_h + tol] for >99% of clicks corpus-wide',
    click_in_bounds / max(total_click, 1) > 0.99,
)
check(
    'OLD formula overflows doc_h on most scrolled trials '
    '(the bug the fix removes)',
    buggy_overflow_trials > inspected * 0.3,
    f'{buggy_overflow_trials}/{inspected}',
)


# ─────────────────────────────────────────────────────────────────────────
print()
if FAILURES:
    print(f'FAILED: {len(FAILURES)} invariant(s) violated')
    for f in FAILURES:
        print(f'  - {f}')
    sys.exit(1)
else:
    print('OK: all coordinate-space invariants hold')
    sys.exit(0)
