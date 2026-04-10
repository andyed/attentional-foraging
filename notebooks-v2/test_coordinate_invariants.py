"""Regression test: coordinate-space invariants for AdSERP.

Locks in the conventions documented in data_loader.py's module docstring so
the scroll-double-counting bug (NB01/03/05/06/07b/10/12/15/18/23/24, plus
compute_butterworth_lfhf.py and compute_ripa2.py prior to 2026-04) cannot
silently reappear.

Run:
    /Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
        notebooks-v2/test_coordinate_invariants.py

Exit code 0 if all invariants hold, 1 otherwise. Prints a clear summary.
"""
from __future__ import annotations

import sys
import math
from pathlib import Path
from bisect import bisect_right

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events, get_trial_meta, interpolate_scroll,
    result_band_tops, count_results_html,
    assign_fixation_to_position,
    get_click_page_xy, click_to_position, cursor_to_position,
    screen_y_to_page_y, page_y_to_screen_y,
    gaze_cursor_distance, interpolate_cursor_at,
)

SCROLLED_TRIAL = 'p004-b2-t3'   # 163 scroll events, max scroll ~1111 px
NO_SCROLL_TRIAL = 'p004-b1-t1'  # 0 scroll events

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = ''):
    mark = 'PASS' if cond else 'FAIL'
    print(f'  [{mark}] {name}' + (f'  — {detail}' if detail else ''))
    if not cond:
        FAILURES.append(name)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 1: evtrack mouse Y empirically exceeds window height.
# This is the ground-truth check that `ypos` is page-space, not screen.
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
# Invariant 2: assign_fixation_to_position handles gaze correctly.
# Contract: input is SCREEN-space; function adds scroll internally.
# ─────────────────────────────────────────────────────────────────────────
print('\n[2] assign_fixation_to_position: screen-space gaze contract')
doc_h, scr_h, _ = get_trial_meta(SCROLLED_TRIAL)
n_results = max(count_results_html(SCROLLED_TRIAL), 1)
tops = result_band_tops(n_results, doc_h)

# Pick a gaze near top of viewport at a moment when scroll ~500 px.
scroll_ts = [s[0] for s in scrolls]
scroll_ys = [s[1] for s in scrolls]
mid_scroll_t = scroll_ts[len(scroll_ts) // 2]
scroll_here = interpolate_scroll(mid_scroll_t, scroll_ts, scroll_ys)

# Synthetic gaze at screen_y=300 → page_y=300+scroll_here
fake_screen_y = 300
pos_via_helper = assign_fixation_to_position(
    fake_screen_y, scroll_here, tops, n_results
)
pos_manual = bisect_right(tops, fake_screen_y + scroll_here) - 1
check(
    'assign_fixation_to_position matches manual bisect',
    pos_via_helper == pos_manual,
    f'helper={pos_via_helper}  manual={pos_manual}  '
    f'scroll={scroll_here:.0f}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 3: click_to_position uses page-space directly (no scroll add).
# Contract: clicks[-1][2] is already page-space. click_to_position must
# return the same answer as bisect(tops, clicks[-1][2]) and must NOT match
# the old buggy formula on scrolled trials.
# ─────────────────────────────────────────────────────────────────────────
print('\n[3] click_to_position: page-space click contract')
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

    # The click's page-Y actually lies within the band of the returned
    # position. This is the invariant that was silently violated by the
    # buggy formula on scrolled trials (see Invariant 9 for the full count).
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
# Invariant 4: no-scroll trial — buggy and correct formulas agree exactly.
# This is the safety bar: the fix is neutral on unaffected data.
# ─────────────────────────────────────────────────────────────────────────
print('\n[4] no-scroll trial: buggy and correct formulas agree')
_events_ns, scrolls_ns, clicks_ns = load_mouse_events(NO_SCROLL_TRIAL)
has_no_scroll = len(scrolls_ns) == 0
check('no-scroll trial has zero scroll events', has_no_scroll)

if clicks_ns:
    doc_h_ns, _scr_h_ns, _ = get_trial_meta(NO_SCROLL_TRIAL)
    n_ns = max(count_results_html(NO_SCROLL_TRIAL), 1)
    tops_ns = result_band_tops(n_ns, doc_h_ns)
    ct_ns, _cx_ns, cy_ns = clicks_ns[-1]
    scroll_ns_val = interpolate_scroll(ct_ns, [], [])

    pos_correct_ns = click_to_position(clicks_ns, tops_ns, n_ns)
    # Buggy formula with zero scroll is identical to correct.
    pos_buggy_ns_y = cy_ns + scroll_ns_val
    pos_buggy_ns = bisect_right(tops_ns, pos_buggy_ns_y) - 1
    if not (0 <= pos_buggy_ns < n_ns):
        pos_buggy_ns = None

    check(
        'buggy ≡ correct on no-scroll trial (sanity bar)',
        pos_correct_ns == pos_buggy_ns,
        f'correct={pos_correct_ns}  buggy={pos_buggy_ns}',
    )


# ─────────────────────────────────────────────────────────────────────────
# Invariant 5: gaze_cursor_distance returns screen-space Euclidean, and
# agrees with raw Euclidean on no-scroll trials.
# ─────────────────────────────────────────────────────────────────────────
print('\n[5] gaze_cursor_distance: screen-space Euclidean')

# Case A: no scroll — all three formulas must agree.
fix_x, fix_y = 500.0, 400.0
cur_x_page, cur_y_page = 520.0, 420.0
scroll_a = 0.0
d_helper_a = gaze_cursor_distance(fix_x, fix_y, cur_x_page, cur_y_page, scroll_a)
d_raw_a = math.hypot(fix_x - cur_x_page, fix_y - cur_y_page)
check(
    'no-scroll: helper == raw Euclidean',
    abs(d_helper_a - d_raw_a) < 1e-6,
    f'helper={d_helper_a:.3f}  raw={d_raw_a:.3f}',
)

# Case B: with scroll — NB15-style buggy formula diverges.
scroll_b = 500.0
d_helper_b = gaze_cursor_distance(fix_x, fix_y, cur_x_page, cur_y_page, scroll_b)
# NB15 buggy: hypot(fix_x - mx, (fix_y + s) - (my + s)) = hypot(dx, fix_y - my)
d_nb15_b = math.hypot(fix_x - cur_x_page, fix_y - cur_y_page)
# Correct screen-space distance:
# screen_cursor_y = cur_y_page - scroll_b = -80 (off-screen, valid calc)
# dy = fix_y - screen_cursor_y = 400 - (420 - 500) = 480
d_expected_b = math.hypot(fix_x - cur_x_page, fix_y - (cur_y_page - scroll_b))
check(
    'scrolled: helper == expected screen-space distance',
    abs(d_helper_b - d_expected_b) < 1e-6,
    f'helper={d_helper_b:.3f}  expected={d_expected_b:.3f}',
)
check(
    'scrolled: helper differs from NB15 buggy formula',
    abs(d_helper_b - d_nb15_b) > 1.0,
    f'helper={d_helper_b:.3f}  nb15_buggy={d_nb15_b:.3f}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 6: round-trip screen↔page conversion is exact.
# ─────────────────────────────────────────────────────────────────────────
print('\n[6] screen↔page round-trip')
for s, scroll_val in [(100, 50), (1000, 300), (0, 0), (500, 0)]:
    page = screen_y_to_page_y(s, scroll_val)
    back = page_y_to_screen_y(page, scroll_val)
    check(
        f'round-trip screen={s} scroll={scroll_val}',
        abs(back - s) < 1e-9,
        f'back={back}',
    )


# ─────────────────────────────────────────────────────────────────────────
# Invariant 7: interpolate_cursor_at produces values within the bracketing
# mouse events (sanity — this is the helper NB15 should be using).
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
# Invariant 8: Synthetic corner cases for click_to_position.
# Clicks exactly on tops[i], past last result, and above first result.
# Also confirms no hidden scr_h clamp leaked in.
# ─────────────────────────────────────────────────────────────────────────
print('\n[8] click_to_position: synthetic corner cases')

# Build a fake tops list. n_results=5 with 300 px bands starting at 200.
fake_tops = [200.0, 500.0, 800.0, 1100.0, 1400.0]
fake_n = 5


def _mk_click(y):
    """Build a minimal clicks list for click_to_position()."""
    return [(0, 0, float(y))]


# 8a: click exactly on tops[0] → pos 0.
check(
    'click at tops[0]=200 → pos 0',
    click_to_position(_mk_click(200.0), fake_tops, fake_n) == 0,
)

# 8b: click exactly on tops[1] → pos 1 (bisect_right steps past the tie).
check(
    'click at tops[1]=500 → pos 1',
    click_to_position(_mk_click(500.0), fake_tops, fake_n) == 1,
)

# 8c: click just before tops[1] → still pos 0.
check(
    'click at 499.99 → pos 0 (just above next band)',
    click_to_position(_mk_click(499.99), fake_tops, fake_n) == 0,
)

# 8d: click past the last top → pos n-1 (there's no explicit band bottom).
check(
    'click at 2000 (past last top) → pos 4',
    click_to_position(_mk_click(2000.0), fake_tops, fake_n) == 4,
)

# 8e: click above the first top → None (off-SERP, above the header).
check(
    'click at 100 (above first top) → None',
    click_to_position(_mk_click(100.0), fake_tops, fake_n) is None,
)

# 8f: no clicks → None (not exception).
check(
    'empty clicks → None',
    click_to_position([], fake_tops, fake_n) is None,
)

# 8g: scr_h clamp must NOT leak into click_to_position.
# NB05/06/07b used `min(click_y, scr_h) + so` which double-counts scroll
# AND clamps any click below the fold. click_to_position should not
# clamp at all: give it a large page-space Y and verify we get the deep
# position, not a clamped one.
SCR_H = 1024
big_click_y = SCR_H + 600  # 1624 px, clearly past scr_h
pos_no_clamp = click_to_position(_mk_click(big_click_y), fake_tops, fake_n)
# big_click_y=1624 → falls into band 4 (tops[4]=1400, nothing after)
check(
    'click past scr_h is NOT clamped — deep position preserved',
    pos_no_clamp == 4,
    f'pos={pos_no_clamp}',
)


# ─────────────────────────────────────────────────────────────────────────
# Invariant 9: Corpus-wide band-containment sanity.
# For every trial with a click, the CORRECT formula places the click
# within the band of its reported position. Then we count how many trials
# the OLD buggy formula would have mis-placed (invariant violated).
# This is the headline number for the CHANGELOG.
# ─────────────────────────────────────────────────────────────────────────
print('\n[9] corpus-wide: click_y falls within reported band')
from data_loader import get_trial_ids  # noqa: E402

trial_ids = get_trial_ids()
ok_correct = 0
bad_correct = 0
ok_buggy = 0
bad_buggy = 0
disagree_scrolled = 0
disagree_noscroll = 0
n_clicks = 0
n_scrolled_with_click = 0

for tid in trial_ids:
    meta = get_trial_meta(tid)
    if not meta:
        continue
    doc_h_t, _, _ = meta
    n_res = max(count_results_html(tid), 1)
    t_tops = result_band_tops(n_res, doc_h_t)

    _, t_scrolls, t_clicks = load_mouse_events(tid)
    if not t_clicks:
        continue
    n_clicks += 1
    t_scroll_ts = [s[0] for s in t_scrolls]
    t_scroll_ys = [s[1] for s in t_scrolls]
    had_scroll = len(t_scrolls) > 0
    if had_scroll:
        n_scrolled_with_click += 1

    ct2, _, cy_page2 = t_clicks[-1]
    click_scroll2 = interpolate_scroll(ct2, t_scroll_ts, t_scroll_ys)

    pos_c = click_to_position(t_clicks, t_tops, n_res)
    # Correct band containment test
    if pos_c is not None:
        bt = t_tops[pos_c]
        bb = t_tops[pos_c + 1] if pos_c + 1 < len(t_tops) else float('inf')
        if bt <= cy_page2 < bb:
            ok_correct += 1
        else:
            bad_correct += 1
    else:
        # Click outside any band — not a failure per se, just count it.
        pass

    # Buggy formula: cy_page2 + click_scroll2
    buggy_y = cy_page2 + click_scroll2
    pos_b_raw = bisect_right(t_tops, buggy_y) - 1
    pos_b = pos_b_raw if 0 <= pos_b_raw < n_res else None

    if pos_b is not None:
        bt_b = t_tops[pos_b]
        bb_b = t_tops[pos_b + 1] if pos_b + 1 < len(t_tops) else float('inf')
        # Check the band containment against the ACTUAL page-space click Y
        # (not the buggy-inflated one): this is the real-world "did the
        # buggy formula place the click in a band that actually contains
        # the click".
        if bt_b <= cy_page2 < bb_b:
            ok_buggy += 1
        else:
            bad_buggy += 1

    if pos_c != pos_b:
        if had_scroll:
            disagree_scrolled += 1
        else:
            disagree_noscroll += 1

print(f'   trials with clicks: {n_clicks}  '
      f'(scrolled: {n_scrolled_with_click})')
print(f'   CORRECT formula: {ok_correct} in-band / {bad_correct} out-of-band')
print(f'   BUGGY   formula: {ok_buggy} in-band / {bad_buggy} out-of-band')
print(f'   disagreements:  {disagree_scrolled} scrolled, '
      f'{disagree_noscroll} no-scroll')

check(
    'CORRECT formula: all clicks land in their reported band',
    bad_correct == 0,
    f'out_of_band={bad_correct}',
)
check(
    'BUGGY formula: mis-places clicks on scrolled trials',
    bad_buggy > 0,
    f'out_of_band={bad_buggy}  (this is the bug the fix removes)',
)
check(
    'BUGGY formula: agrees with CORRECT on no-scroll trials',
    disagree_noscroll == 0,
    f'disagreements={disagree_noscroll}',
)
check(
    'BUGGY formula: disagrees with CORRECT on scrolled trials',
    disagree_scrolled > 0,
    f'disagreements={disagree_scrolled}/{n_scrolled_with_click}',
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
