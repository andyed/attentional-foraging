"""
data_loader.py — shared data loading utilities for attentional-foraging notebooks.

Loads directly from the AdSERP data directory structure. Eliminates the
per-notebook boilerplate of path setup, CSV parsing, scroll interpolation,
result band estimation, and SERP text extraction.

Usage:
    from data_loader import *

    trial_ids = get_trial_ids()
    fixations = load_fixations('p004-b1-t1')
    events, scrolls, clicks = load_mouse_events('p004-b1-t1')
    doc_h, scr_h, ts = get_trial_meta('p004-b1-t1')

═══════════════════════════════════════════════════════════════════════════
COORDINATE SYSTEM CONVENTIONS — READ BEFORE TOUCHING FIXATION/CURSOR CODE
═══════════════════════════════════════════════════════════════════════════

AdSERP gaze, cursor, and click streams are ALL in PAGE-SPACE (coordinates
relative to the top-left of the full-page screenshot, with scroll already
baked in). There is no screen-space / page-space conversion to do at the
fixation level — comparing any two streams is just `(x1, y1)` vs `(x2, y2)`.

  1. GAZE  (fixation-data/*.csv, columns FPOGX/FPOGY)
     SOURCE: Gazepoint GP3 HD, 150 Hz.
     SPACE:  PAGE-space. Per the AdSERP README
             (https://github.com/kayhan-latifzadeh/AdSERP):
               "FPOGX/FPOGY: Fixation positions ... relative to the
                top-left corner of the screenshot in pixels."
             The screenshot is the full-page capture, so FPOGY can exceed
             `screen_height` whenever the user has scrolled.
     VERIFY: For 18/20 scrolled trials sampled on 2026-04-12,
             Pearson r(FPOGY, scrollY) ≈ 0.95 and (FPOGY − scrollY) falls
             inside the viewport [0, scr_h] for 98%+ of fixations — proof
             that FPOGY already includes scroll.

  2. CURSOR (mouse-movement-data/*.csv, columns xpos/ypos)
     SOURCE: evtrack JS library, pageX/pageY from DOM events.
     SPACE:  PAGE-space. Same convention as gaze.

  3. CLICK EVENTS (clicks[-1] from load_mouse_events)
     Same convention as cursor — page-space, already includes scroll.

  4. RESULT BAND TOPS (`result_band_tops(n_results, doc_h)`)
     PAGE-space, measured from doc top. Compare page-space Ys directly.

To map a fixation or cursor Y to a viewport position (for "which result
was on screen at this moment" type questions), SUBTRACT the scroll offset
at that timestamp. Nothing in this module adds scroll to a fixation or
cursor Y — if you find yourself writing `+ scroll` on either, stop.

═══════════════════════════════════════════════════════════════════════════
AUDIT HISTORY
═══════════════════════════════════════════════════════════════════════════

  2026-04-09 — CURSOR/CLICK bug fixed. Prior code added scroll to cursor
               and click Ys (which were already page-space), double-counting
               scroll on 82% of the corpus. Affected NB01/03/05/06/07b/10/
               12/15/18/23/24 plus two precomputed scripts.

  2026-04-12 — FIXATION bug fixed. Prior docstring and helpers falsely
               documented FPOGX/FPOGY as screen-space (viewport pixels),
               so callers did `page_y = fix.y + scroll` — the same
               double-count on the gaze side. Discovered while validating
               the 31 canonical gazeplot trials against the authors' own
               full-page screenshots (Zenodo record 15236546). Empirical
               falsification above. AdSERP README is authoritative.
               Affected NB14/15/18/19/22 and the pupil-lfhf forked loader.

See `test_coordinate_invariants.py` for the regression tests.
"""

import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent
DATA_DIR = _ROOT / 'AdSERP' / 'data'
FIXATION_DIR = DATA_DIR / 'fixation-data'
MOUSE_DIR = DATA_DIR / 'mouse-movement-data'
METADATA_DIR = DATA_DIR / 'trial-metadata'
SERP_DIR = DATA_DIR / 'serps'
AD_DIR = DATA_DIR / 'ad-boundary-data'
PUPIL_DIR = DATA_DIR / 'pupil-data'
ORGANIC_BBOX_DIR = DATA_DIR / 'organic-boundary-data'

# Legacy aliases — older notebooks reference FIX_DIR directly
FIX_DIR = FIXATION_DIR

# ── Trial discovery ────────────────────────────────────────────────────────

def get_trial_ids():
    """Sorted list of all trial IDs (from mouse-movement-data filenames)."""
    return sorted(f.replace('.csv', '') for f in os.listdir(MOUSE_DIR) if f.endswith('.csv'))

# ── Fixation loading ───────────────────────────────────────────────────────

def load_fixations(trial_id):
    """Load fixations for a trial.

    Returns list of dicts: {t, x, y, d} where t is timestamp (ms), x/y are
    page-space pixels (relative to the full-page screenshot, includes scroll),
    and d is duration (ms).

    No clamping: prior versions clamped FPOGY to [0, scr_h] under the false
    assumption that FPOGY was viewport-space and that values above scr_h were
    eye-tracker noise. Per the AdSERP README, FPOGY is page-space — values
    above scr_h are legitimate gazes at below-fold content after the user
    scrolled. See module docstring audit history (2026-04-12).
    """
    path = FIXATION_DIR / f'{trial_id}.csv'
    fixations = []
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                fixations.append({
                    't': float(row['timestamp']),
                    'x': float(row['FPOGX']),
                    'y': float(row['FPOGY']),
                    'd': float(row['FPOGD']),
                })
            except (ValueError, KeyError):
                continue
    return fixations

# ── Mouse / scroll / click loading ─────────────────────────────────────────

def load_mouse_events(trial_id):
    """Load mouse, scroll, and click events for a trial.

    Returns:
        all_events: list of (t, event_type, x, y)
        scrolls: list of (t, y) for scroll events
        clicks: list of (t, x, y) for click events
    """
    path = MOUSE_DIR / f'{trial_id}.csv'
    all_events, scrolls, clicks = [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            t = int(float(row['timestamp']))
            evt = row['event']
            x, y = float(row['xpos']), float(row['ypos'])
            all_events.append((t, evt, x, y))
            if evt == 'scroll':
                scrolls.append((t, y))
            elif evt == 'click':
                clicks.append((t, x, y))
    return all_events, scrolls, clicks


def load_mouse_and_scroll(trial_id):
    """Compatibility wrapper returning (mouse, scrolls) in the shape that
    NB11 and NB02 expect.

    Returns:
        mouse: list of (t, x, y) cursor-position samples (mousemove family,
               plus click for the terminal position)
        scrolls: list of (t, y) scroll events
    """
    events, scrolls, _ = load_mouse_events(trial_id)
    pos_events = {'mousemove', 'mouseover', 'mouseout',
                  'mousedown', 'mouseup', 'click'}
    mouse = [(t, x, y) for (t, evt, x, y) in events if evt in pos_events]
    return mouse, scrolls


def has_regression(scrolls, threshold_px=30):
    """True if the scroll trace contains a backward movement of at least
    threshold_px below the running high-water mark.

    Args:
        scrolls: list of (t, y) as returned by load_mouse_events()
        threshold_px: minimum backward travel to count as a regression
    """
    if not scrolls:
        return False
    hwm = scrolls[0][1]
    for _, y in scrolls:
        if hwm - y > threshold_px:
            return True
        if y > hwm:
            hwm = y
    return False


def compute_lag_for_trial(fix, mouse, scrolls, step_ms=50, max_offset=2000):
    """Scroll-corrected gaze–cursor Y cross-correlation.

    Returns best_lag_ms (int) where the correlation between gaze-Y and
    cursor-Y peaks. Negative = gaze leads cursor (Huang et al. 2012
    reports ~-700ms). Returns None if insufficient data.

    Accepts fixations in either tuple (t, x, y, d) or dict
    {t, x, y, d, ...} form — both NB02 and data_loader shapes are OK.

    This is the canonical replacement for NB02's `compute_lag`, which
    references an undefined `RY` global. Assumes mouse and gaze share
    the same pixel coordinate space (RY ≡ 1), which is correct for the
    AdSERP dataset (Gazepoint GP3 pixel coords + evtrack pageY).
    """
    if len(fix) < 5 or len(mouse) < 20:
        return None

    def _fx(f):
        if isinstance(f, dict):
            return f['t'], f['y'], f['d']
        return f[0], f[2], f[3]

    fix_t = np.array([_fx(f)[0] for f in fix], dtype=float)
    fix_y = np.array([_fx(f)[1] for f in fix], dtype=float)
    fix_d = np.array([_fx(f)[2] for f in fix], dtype=float)

    mt = np.array([m[0] for m in mouse], dtype=float)
    my = np.array([m[2] for m in mouse], dtype=float)

    t0 = min(fix_t.min(), mt.min())
    t1 = max((fix_t + fix_d).max(), mt.max())
    times = np.arange(t0, t1, step_ms)
    if len(times) < 20:
        return None

    # Rasterize gaze-Y to timebase (screen-space)
    gy = np.full(len(times), np.nan)
    for t, y, d in zip(fix_t, fix_y, fix_d):
        mask = (times >= t) & (times < t + d)
        gy[mask] = y

    # Rasterize mouse-Y to timebase, subtract scroll to bring into screen-space
    if scrolls:
        st = np.array([s[0] for s in scrolls], dtype=float)
        sy = np.array([s[1] for s in scrolls], dtype=float)
        mouse_scroll = np.interp(mt, st, sy, left=sy[0], right=sy[-1])
    else:
        mouse_scroll = np.zeros_like(mt)
    mouse_screen_y = my - mouse_scroll
    my_interp = np.interp(times, mt, mouse_screen_y, left=np.nan, right=np.nan)

    offsets = np.arange(-max_offset, max_offset + 1, step_ms)
    corrs = np.full(len(offsets), np.nan)
    for i, off in enumerate(offsets):
        shift = int(off / step_ms)
        if shift >= 0:
            g = gy[shift:]
            m = my_interp[:len(g)]
        else:
            m = my_interp[-shift:]
            g = gy[:len(m)]
        v = np.isfinite(g) & np.isfinite(m)
        if v.sum() < 20:
            continue
        gv, mv = g[v], m[v]
        if gv.std() < 1 or mv.std() < 1:
            continue
        corrs[i] = np.corrcoef(gv, mv)[0, 1]

    if not np.isfinite(corrs).any():
        return None
    return int(offsets[int(np.nanargmax(corrs))])


# ── Trial metadata ─────────────────────────────────────────────────────────

def get_trial_meta(trial_id):
    """Get trial metadata from XML.

    Returns: (doc_height, screen_height, timestamp) or (None, None, None).
    """
    path = METADATA_DIR / f'{trial_id}.xml'
    try:
        tree = ET.parse(path)
        doc_h = int(tree.find('.//document').text.split('x')[1])
        scr_h = int(tree.find('.//screen').text.split('x')[1])
        ts = int(tree.find('.//timestamp').text)
        return doc_h, scr_h, ts
    except Exception:
        return None, None, None

def get_query(trial_id):
    """Extract search query from trial metadata XML."""
    path = METADATA_DIR / f'{trial_id}.xml'
    try:
        tree = ET.parse(path)
        q = tree.find('.//query')
        return q.text if q is not None else ''
    except Exception:
        return ''

# ── Scroll interpolation ──────────────────────────────────────────────────

def interpolate_scroll(t, scroll_ts, scroll_ys):
    """Linearly interpolate scroll position at time t.

    Args:
        t: timestamp (ms)
        scroll_ts: sorted list of scroll event timestamps
        scroll_ys: corresponding scroll Y positions

    Returns: estimated scroll Y at time t.
    """
    if not scroll_ts:
        return 0.0
    if t <= scroll_ts[0]:
        return scroll_ys[0]
    if t >= scroll_ts[-1]:
        return scroll_ys[-1]
    idx = bisect_right(scroll_ts, t) - 1
    if idx < len(scroll_ts) - 1:
        frac = (t - scroll_ts[idx]) / max(scroll_ts[idx + 1] - scroll_ts[idx], 1)
        return scroll_ys[idx] + frac * (scroll_ys[idx + 1] - scroll_ys[idx])
    return scroll_ys[-1]

# ── Rank semantics ─────────────────────────────────────────────────────────
#
# POSITION SEMANTICS — READ BEFORE COMPUTING OR CITING "POSITION"
#
# The SERP has two distinct notions of "position":
#
#   1. ABSOLUTE RANK  (slot index, ads + organic pooled)
#      0..N-1 where N is the total number of h3 result slots in the DOM.
#      N is typically 11-17 because AdSERP Google results interleave
#      dd_top (direct-display ads at top), native_ad (in-stream ads), and
#      organic results. The first h3 may be a dd_top ad, pushing the
#      first organic result to absolute_rank 1 or 2.
#      Use when: the analysis *should* count ads as first-class slots
#      (e.g., NB22 element-type interaction, discrimination-cost claims,
#      NB24 retreat-arc geometry that cares about the visual region of
#      the clicked element regardless of its type).
#
#   2. ORGANIC RANK  (ads excluded)
#      0..M-1 where M is the number of organic h3 slots in the DOM.
#      M is typically 10 in AdSERP. This is the canonical "SERP position"
#      used in the search-behavior literature (click-through-rate by rank,
#      position bias, rank effects papers).
#      Use when: the claim is about the user's experience of results as
#      a ranked organic list (e.g., click-by-rank curves, NB23 rank
#      effects, comparisons with prior SERP literature).
#
# Helpers below come in pairs — `count_absolute_ranks()` /
# `count_organic_ranks()`, `absolute_rank_band_tops()` /
# `organic_rank_band_tops()`, and `absolute_to_organic_rank()` for
# per-trial mapping. The legacy names `count_results_html()` and
# `result_band_tops()` are retained as aliases for the *absolute* family
# (that's what they always computed, despite the misleading "organic"
# wording in prior docstrings) so existing callers don't break, but new
# code should prefer the precise names above.
#
# Post-2026-04-12 observation: across 2,776 AdSERP trials,
#   count_absolute_ranks distribution = {10: 188, 11: 632, 12: 879,
#   13: 644, 14: 228, 15: 117, 16: 41, 17: 12}
# Only 7% of trials have exactly 10 absolute slots; 92% have 11+ because
# of interleaved ads. Any "position 0-10" claim based on absolute rank
# is *not* the same curve as the canonical organic-rank click-through
# from the search literature.
#
# See add_etype_to_features.py for the ad-overlap classification rule
# (adopted canonical from NB24's classify_position). Ad-boundary data
# lives at AdSERP/data/ad-boundary-data/<trial_id>.json.
# ───────────────────────────────────────────────────────────────────────────

# Result column x-range, same constants as add_etype_to_features.py
_RESULT_COL_X_MIN = 162
_RESULT_COL_X_MAX = 702


def _load_ad_regions(trial_id):
    """Load ad boundary rects for a trial.

    Returns dict {etype: [(x, y, w, h), ...]}. Excludes `dd_right` because
    right-rail ads are outside the result column and don't displace ranks.
    Returns {} if ad-boundary-data is missing for the trial.
    """
    path = AD_DIR / f'{trial_id}.json'
    if not path.exists():
        return {}
    try:
        d = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for etype, elements in d.items():
        if etype == 'dd_right':
            continue
        rects = []
        for el in elements:
            loc = el.get('location', {})
            size = el.get('size', {})
            rects.append((loc.get('x', 0), loc.get('y', 0),
                          size.get('width', 0), size.get('height', 0)))
        if rects:
            out[etype] = rects
    return out


def _rect_in_result_column(rx, rw):
    return rx < _RESULT_COL_X_MAX and (rx + rw) > _RESULT_COL_X_MIN


def result_bands(n_results, doc_height):
    """Estimate Y-coordinate boundaries for each absolute-rank slot.

    Returns list of (top, bottom) tuples. Uses uniform subdivision of
    `(200, doc_height - 400)` into `n_results` bands. The caller decides
    whether `n_results` is absolute or organic; this function just divides.
    """
    header = 200
    per_res = (doc_height - 400) / max(n_results, 1)
    return [(header + i * per_res, header + (i + 1) * per_res) for i in range(n_results)]


# ── Absolute rank (all h3 slots, ads + organic) ────────────────────────────

def count_absolute_ranks(trial_id):
    """Count every h3 result slot in the SERP (ads + organic pooled).

    This is the total number of visually-distinct ranked slots the user
    could approach, regardless of element type. For most AdSERP trials
    this is 11-13 (10 organic + 1-3 ads).
    """
    path = SERP_DIR / f'{trial_id}.html'
    if not path.exists():
        return 0
    try:
        from bs4 import BeautifulSoup
        with open(path, encoding='utf-8', errors='replace') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        return len(soup.find_all('h3'))
    except Exception:
        return 0


def absolute_rank_band_tops(n_absolute, doc_height):
    """Return top Y-coordinates for absolute-rank band lookup.

    n_absolute should come from `count_absolute_ranks(tid)`.
    """
    header = 200
    per_res = (doc_height - 400) / max(n_absolute, 1)
    return [header + i * per_res for i in range(n_absolute)]


# ── Organic rank (ads excluded) ────────────────────────────────────────────

def absolute_to_organic_rank(trial_id, doc_height=None):
    """Build a per-trial map: absolute_rank → organic_rank (or None for ad slots).

    Uses ad-boundary-data to identify which absolute-rank slots overlap
    ad rectangles in the result column (dd_top, native_ad). Slots not
    overlapping any ad are labeled organic and assigned sequential
    organic ranks starting from 0. Ad slots get None.

    Args:
        trial_id: e.g., 'p004-b1-t1'
        doc_height: optional override; defaults to trial metadata.

    Returns:
        {absolute_rank: organic_rank_or_None}. Keys cover 0..n_absolute-1.
        len([v for v in result.values() if v is not None]) == organic count.
    """
    if doc_height is None:
        meta = get_trial_meta(trial_id)
        doc_height = meta[0] if meta[0] else 2642
    n_abs = count_absolute_ranks(trial_id)
    if n_abs == 0:
        return {}
    tops = absolute_rank_band_tops(n_abs, doc_height)
    ad_regions = _load_ad_regions(trial_id)

    result = {}
    organic_counter = 0
    for abs_rank in range(n_abs):
        top = tops[abs_rank]
        bottom = tops[abs_rank + 1] if abs_rank + 1 < n_abs else doc_height - 200
        center_y = (top + bottom) / 2
        is_ad = False
        for etype, rects in ad_regions.items():
            for rx, ry, rw, rh in rects:
                if not _rect_in_result_column(rx, rw):
                    continue
                if ry <= center_y <= ry + rh:
                    is_ad = True
                    break
            if is_ad:
                break
        if is_ad:
            result[abs_rank] = None
        else:
            result[abs_rank] = organic_counter
            organic_counter += 1
    return result


def count_organic_ranks(trial_id, doc_height=None):
    """Count organic-only result slots (ads excluded)."""
    mapping = absolute_to_organic_rank(trial_id, doc_height)
    return sum(1 for v in mapping.values() if v is not None)


def organic_rank_band_tops(trial_id, doc_height=None):
    """Return top Y-coordinates for organic-rank band lookup.

    Unlike `absolute_rank_band_tops`, this is trial-specific because the
    ad layout differs per trial. Returns a list of length organic count.
    """
    if doc_height is None:
        meta = get_trial_meta(trial_id)
        doc_height = meta[0] if meta[0] else 2642
    n_abs = count_absolute_ranks(trial_id)
    abs_tops = absolute_rank_band_tops(n_abs, doc_height)
    mapping = absolute_to_organic_rank(trial_id, doc_height)
    return [abs_tops[abs_rank]
            for abs_rank in range(n_abs)
            if mapping.get(abs_rank) is not None]


# ── Pixel-accurate organic AOIs (from extract_organic_bboxes.py) ───────────
#
# Methodology spec: docs/methodology/organic-result-aoi-extraction.md
# These functions consume the bbox JSONs written by
# scripts/extract_organic_bboxes.py. They are the preferred path for
# per-result fixation/cursor attribution; the band-estimation functions
# below remain for backward compatibility and graceful fallback when no
# bbox JSON exists for a trial.

def load_aois(trial_id, include_widgets=False, include_cells=False):
    """Load pixel-accurate AOIs from the organic-bbox enrichment.

    Args:
        trial_id: e.g. 'p004-b1-t1'.
        include_widgets: if True, return refinement-widget AOIs alongside
            organics. Default False — most analyses aggregate organics
            only and including widgets silently changes per-rank
            denominators. Set True for widget-visit analyses.
        include_cells: if True, return composite-organic sub-cells
            (local-pack listings, multi-row PAA expansions). Default
            False — cells are a second-column variable, not a rank
            overload; opt in only when sub-listing granularity is needed.

    Returns:
        dict with keys:
            'organic':      list of {'position', 'y_top', 'y_bottom',
                              'x_top', 'x_bottom'} dicts in rank order
                              (position is 1-indexed from the JSON).
            'widget':       same shape; empty unless include_widgets=True.
            'organic_cell': same shape plus 'parent_position'; empty
                              unless include_cells=True.
            'meta':         trial-level metadata from extract_trial.
            'source':       'bbox' if JSON present; 'band_estimate' if
                              fallback synthesized from result_bands().

    Falls back to band estimation if the bbox JSON is missing for the
    trial, so callers get a uniform interface either way. Inspect the
    'source' field to tell which they got.
    """
    path = ORGANIC_BBOX_DIR / f'{trial_id}.json'
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        organic = [
            {
                'position': r['position'],
                'y_top': r['location']['y'],
                'y_bottom': r['location']['y'] + r['size']['height'],
                'x_top': r['location']['x'],
                'x_bottom': r['location']['x'] + r['size']['width'],
            }
            for r in data.get('organic_result', [])
        ]
        widgets = []
        if include_widgets:
            widgets = [
                {
                    'position': w['position'],
                    'y_top': w['location']['y'],
                    'y_bottom': w['location']['y'] + w['size']['height'],
                    'x_top': w['location']['x'],
                    'x_bottom': w['location']['x'] + w['size']['width'],
                }
                for w in data.get('widget', [])
            ]
        cells = []
        if include_cells:
            cells = [
                {
                    'position': c['position'],
                    'parent_position': c.get('parent_position'),
                    'y_top': c['location']['y'],
                    'y_bottom': c['location']['y'] + c['size']['height'],
                    'x_top': c['location']['x'],
                    'x_bottom': c['location']['x'] + c['size']['width'],
                }
                for c in data.get('organic_cell', [])
            ]
        return {
            'organic': organic,
            'widget': widgets,
            'organic_cell': cells,
            'meta': data.get('_meta', {}),
            'source': 'bbox',
        }

    # Fallback: synthesize organic AOIs from band estimation. Uses
    # count_organic_ranks() for the denominator (excludes shipped ads
    # but cannot exclude widget-heading h3s — see methodology §6.2).
    meta = get_trial_meta(trial_id)
    doc_h = meta[0] if meta and meta[0] else 2642
    n_org = count_organic_ranks(trial_id, doc_h) or 0
    if n_org == 0:
        return {'organic': [], 'widget': [], 'organic_cell': [],
                'meta': {}, 'source': 'band_estimate'}
    bands = result_bands(n_org, doc_h)
    organic = [
        {
            'position': i + 1,
            'y_top': int(top), 'y_bottom': int(bot),
            'x_top': 162, 'x_bottom': 748,  # main-column geometry from extract_organic_bboxes
        }
        for i, (top, bot) in enumerate(bands)
    ]
    return {'organic': organic, 'widget': [], 'organic_cell': [],
            'meta': {}, 'source': 'band_estimate'}


def organic_aoi_bands(trial_id):
    """Pixel-accurate (y_top, y_bottom) bands for each organic on this trial.

    Drop-in replacement for `result_bands(n, doc_h)` callers. Differences:
      - Uses extracted bboxes when available (pixel-accurate; respects
        actual rendered card heights and inter-card gaps).
      - Falls back to band estimation when bbox JSON missing.
      - Number of bands is determined by the trial's actual organic
        count, not passed in — caller no longer needs to guess.

    Returns list of (y_top, y_bottom) integer tuples in rank order.
    """
    aois = load_aois(trial_id)
    return [(a['y_top'], a['y_bottom']) for a in aois['organic']]


def organic_aoi_tops(trial_id):
    """Convenience: just the y-tops of `organic_aoi_bands(trial_id)`.

    Drop-in replacement for `result_band_tops(n, doc_h)` callers passing
    an organic count. Use with `assign_fixation_to_position(page_y, tops, len(tops))`
    to attribute a fixation to its organic-rank slot.
    """
    return [b[0] for b in organic_aoi_bands(trial_id)]


def attribute_click_to_organic(click_y, trial_id, tolerance_px=30):
    """[DEPRECATED 2026-05-05] Legacy organic-only Y-snap click attribution.

    Use `attribute_click_to_typed_gapfill` instead. This helper is Y-only
    (no X check), which silently mis-attributes off-axis clicks. Retained
    for cascade audits against pre-2026-05-05 K-claims; not the public
    API. See docs/null-findings/2026-05-05-bbox-y-coverage.md.

    --- legacy docstring follows ---

    Attribute a click y-coordinate to an organic AOI position with tolerance.

    Bbox AOIs are extracted tight to visual content. Clicks frequently land
    in the small visual gap between adjacent card rectangles (~10–15 px
    typical) — under strict containment those clicks register as "off-AOI"
    even though they were almost certainly intended for the nearest card.

    This helper handles the gap by:
      1. Returning the position number (1-indexed, matching organic_result.position)
         if the click falls inside any organic AOI rectangle.
      2. Otherwise, returning the position of the nearest organic (by distance
         from click y to that organic's nearest edge), provided the distance
         is ≤ tolerance_px.
      3. Otherwise, returning None (click is genuinely off-AOI — knowledge
         panel, image carousel, footer, "Tools", or large gap).

    Empirical basis (full corpus, n=2,775 clicks):
      - 64.3% land inside an organic rect (strict containment)
      - +27.8% within 30 px of nearest organic edge → snap to that organic
      - 7.5% genuinely off-AOI at any distance > 30 px

    The 30 px default reflects the elbow in the off-AOI distance distribution:
    further loosening to 50/100/200 px rescues only an extra ~0.3 percentage
    points, suggesting 30 px captures all the legitimate "intended for this
    card" clicks while excluding distant off-AOI clicks.

    Args:
        click_y: page-space click y-coordinate (already includes scroll).
        trial_id: e.g. 'p004-b1-t1'.
        tolerance_px: snap distance threshold. Set to 0 for strict containment
            (matches the bbox JSON exactly). Default 30.

    Returns:
        int (organic position, 1-indexed) or None.
    """
    aois = load_aois(trial_id, include_widgets=True)
    organics = aois['organic']
    if not organics:
        return None

    # Strict containment in organic always wins.
    for o in organics:
        if o['y_top'] <= click_y <= o['y_bottom']:
            return o['position']

    # Before snapping, refuse if the click is inside any ad rectangle —
    # those are ad clicks, not organic clicks, regardless of proximity to
    # an adjacent organic.
    path = ORGANIC_BBOX_DIR / f'{trial_id}.json'
    ad_rects = []
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        for kind in ('native_ad', 'dd_top', 'dd_right'):
            for r in data.get(kind, []):
                ry = r['location']['y']
                rh = r['size']['height']
                ad_rects.append((ry, ry + rh))
    for top, bot in ad_rects:
        if top <= click_y <= bot:
            return None

    # Refuse if inside any widget rect (already filtered as non-organic).
    for w in aois['widget']:
        if w['y_top'] <= click_y <= w['y_bottom']:
            return None

    # Snap to nearest organic edge if within tolerance.
    best_pos = None
    best_dist = float('inf')
    for o in organics:
        d = min(abs(click_y - o['y_top']), abs(click_y - o['y_bottom']))
        if d < best_dist:
            best_dist = d
            best_pos = o['position']

    if best_dist <= tolerance_px:
        return best_pos
    return None


# ── Typed AOI helpers (Phase-3 cascade: HTML+vision typed attribution) ───
#
# The typed-AOI pipeline (Phase 1 + 2 of feat/aoi-pipeline-v3-typed) writes
# per-trial typed JSONs at `data/aoi-typed/<trial_id>.json` with an entry
# per detected SERP card and a `position` field. position >= 0 = on the
# main scroll axis; position == -1 = off-axis (chrome, dd_right, #botstuff
# Related Searches, #rhs Knowledge Panel).
#
# Card types:
#   organic | dd_top | native_ad | dd_right | top_places | knowledge_panel
#   | paa | related_searches | image_pack | other_widget | unknown_widget
#   | chrome
#
# Helpers below mirror the organic_aoi_* / _hybrid_aoi_tops conventions.

_TYPED_AOI_DIR = (DATA_DIR.parent / 'data/aoi-typed') if DATA_DIR.name == 'data' else (DATA_DIR.parent.parent / 'data/aoi-typed')


def _typed_aoi_path(trial_id):
    """Return the path to the typed AOI map for a trial."""
    # Resolve relative to the project root, not relative to AdSERP/data/
    project_root = DATA_DIR.parent.parent if DATA_DIR.name == 'data' else DATA_DIR.parent
    return project_root / 'data' / 'aoi-typed' / f'{trial_id}.json'


def load_typed_aois(trial_id):
    """Load the full typed AOI list for a trial. Returns list of dicts as
    produced by `scripts/build_typed_aoi_map.py`. Empty list if missing."""
    p = _typed_aoi_path(trial_id)
    if not p.exists():
        return []
    return json.load(open(p))


def typed_aoi_bands(trial_id):
    """Return list of (y_top, y_bottom, type) tuples for cards on the main
    scroll axis (position >= 0), sorted by display position.

    Drop-in replacement for `organic_aoi_bands(trial_id)` callers that need
    typed labels. Same y-coordinate convention (page-space pixels).
    """
    cards = load_typed_aois(trial_id)
    main = [c for c in cards if c.get('position', -1) >= 0
            and c.get('y') is not None and c.get('height') is not None]
    main.sort(key=lambda c: c['position'])
    return [(int(c['y']), int(c['y']) + int(c['height']), c['type']) for c in main]


def typed_aoi_tops(trial_id):
    """Convenience: just the y-tops of `typed_aoi_bands(trial_id)`.

    Mirrors `organic_aoi_tops` and `_hybrid_aoi_tops`. Use with
    `assign_fixation_to_position(page_y, tops, len(tops))` to attribute a
    fixation to its typed-display-order slot.
    """
    return [b[0] for b in typed_aoi_bands(trial_id)]


def typed_aoi_etypes(trial_id):
    """Parallel to `typed_aoi_tops`: list of etype strings in display order.

    Useful when the caller needs both position-by-y AND etype labels.
    """
    return [b[2] for b in typed_aoi_bands(trial_id)]


def attribute_click_to_typed(click_y, trial_id, tolerance_px=30):
    """[DEPRECATED 2026-05-05] Legacy Y-only typed click attribution.

    Use `attribute_click_to_typed_gapfill` instead. This helper is Y-only
    (no X check), which silently mis-attributes off-axis clicks (right-rail
    dd_right, page chrome). The 22.7 % `approached & clicked` contamination
    finding (`scripts/audit_cascade_contamination.py`) was driven by this
    helper. Retained for cascade audits against pre-2026-05-05 K-claims;
    not the public API. See docs/null-findings/2026-05-05-bbox-y-coverage.md.

    --- legacy docstring follows ---

    Attribute a click y-coordinate to a typed AOI position with tolerance.

    Mirrors `attribute_click_to_organic` but uses the typed AOI map. Returns
    a (position, etype) tuple, or None if the click is genuinely off-AOI
    (further than tolerance_px from any main-axis AOI edge).

    Snap policy: tolerant 30 px, matching the existing organic click-snap
    rule. Off-axis cards (chrome, dd_right, #botstuff, #rhs) are NOT
    candidates for snap — they have position = -1.

    Args:
        click_y: page-space click y-coordinate (already includes scroll).
        trial_id: e.g. 'p004-b1-t1'.
        tolerance_px: snap distance threshold. Default 30.

    Returns:
        (int position, str etype) or None.
    """
    cards = load_typed_aois(trial_id)
    main = [c for c in cards if c.get('position', -1) >= 0
            and c.get('y') is not None and c.get('height') is not None]
    if not main:
        return None

    # Strict containment first
    for c in main:
        y_top = c['y']
        y_bot = c['y'] + c['height']
        if y_top <= click_y <= y_bot:
            return (c['position'], c['type'])

    # Snap to nearest edge if within tolerance
    best = None
    best_dist = float('inf')
    for c in main:
        y_top = c['y']
        y_bot = c['y'] + c['height']
        d = min(abs(click_y - y_top), abs(click_y - y_bot))
        if d < best_dist:
            best_dist = d
            best = (c['position'], c['type'])
    if best_dist <= tolerance_px:
        return best
    return None


# ── Typed AOI gapfill helpers (post-2026-05-05 cascade) ──────────────────
#
# The `typed_gapfill` flavor mirrors `typed` but reads bboxes from
# `data/aoi-typed-gapfill/` where organic bboxes have been midpoint-split
# to fill inter-result Y gaps. See
# docs/null-findings/2026-05-05-bbox-y-coverage.md for context.
#
# Pragmatic, not principled: the midpoint heuristic recovers signal that
# was being silently dropped under tight `typed` bboxes; it does not claim
# to identify the "true" boundary between adjacent results (a DOM/CSS
# question). Both flavors stay queryable side-by-side.


def _typed_gapfill_aoi_path(trial_id):
    project_root = DATA_DIR.parent.parent if DATA_DIR.name == 'data' else DATA_DIR.parent
    return project_root / 'data' / 'aoi-typed-gapfill' / f'{trial_id}.json'


def load_typed_gapfill_aois(trial_id):
    """Load the typed_gapfill AOI list for a trial. Returns [] if missing."""
    p = _typed_gapfill_aoi_path(trial_id)
    if not p.exists():
        return []
    return json.load(open(p))


def typed_gapfill_aoi_bands(trial_id):
    """Return list of (y_top, y_bottom, type) tuples for cards on the main
    scroll axis (position >= 0), sorted by display position. Mirror of
    `typed_aoi_bands` over the gapfilled AOI map."""
    cards = load_typed_gapfill_aois(trial_id)
    main = [c for c in cards if c.get('position', -1) >= 0
            and c.get('y') is not None and c.get('height') is not None]
    main.sort(key=lambda c: c['position'])
    return [(int(c['y']), int(c['y']) + int(c['height']), c['type']) for c in main]


def typed_gapfill_aoi_tops(trial_id):
    """Mirror of `typed_aoi_tops` over gapfilled AOIs."""
    return [b[0] for b in typed_gapfill_aoi_bands(trial_id)]


def typed_gapfill_aoi_etypes(trial_id):
    """Mirror of `typed_aoi_etypes` over gapfilled AOIs."""
    return [b[2] for b in typed_gapfill_aoi_bands(trial_id)]


def attribute_click_to_typed_gapfill(
    click_x, click_y, trial_id, x_tol=5, y_tol=10
):
    """X+Y bbox-aware click attribution under typed_gapfill.

    Unlike `attribute_click_to_typed`, this enforces an X check (clicks
    outside the result column don't snap to in-column AOIs). The existing
    Y-only attribution silently rolled right-rail and chrome clicks into
    organic; this fix is the core motivation of the gapfill cascade.

    Strict containment with tolerance: an AOI's bbox is inflated by
    (x_tol, y_tol) symmetrically; on overlap, prefer the smaller-area AOI.

    Args:
        click_x: page-space click x-coordinate.
        click_y: page-space click y-coordinate.
        trial_id: e.g. 'p004-b1-t1'.
        x_tol: X tolerance for link-padding clicks. Default 5 px.
        y_tol: Y tolerance for link-padding clicks. Default 10 px.
            (Most inter-result gaps are absorbed by the gapfill itself.)

    Returns:
        (int position, str etype) or None.
    """
    cards = load_typed_gapfill_aois(trial_id)
    main = [c for c in cards if c.get('position', -1) >= 0
            and c.get('y') is not None and c.get('height') is not None
            and c.get('x') is not None and c.get('width') is not None]
    if not main:
        return None

    # Pass 1: strict containment (zero tolerance). If any AOI strictly
    # contains the click, prefer the smallest-area one (mostly relevant on
    # the rare case of widget-within-organic overlap).
    best_strict = None
    best_strict_area = float('inf')
    for c in main:
        x, y, w, h = c['x'], c['y'], c['width'], c['height']
        if x <= click_x <= x + w and y <= click_y <= y + h:
            area = max(1.0, w * h)
            if area < best_strict_area:
                best_strict_area = area
                best_strict = (c['position'], c['type'])
    if best_strict is not None:
        return best_strict

    # Pass 2: tolerance fallback. Pick the AOI whose inflated bbox contains
    # the click; on overlap prefer the smallest-area AOI.
    best = None
    best_area = float('inf')
    for c in main:
        x, y, w, h = c['x'], c['y'], c['width'], c['height']
        in_x = (x - x_tol) <= click_x <= (x + w + x_tol)
        in_y = (y - y_tol) <= click_y <= (y + h + y_tol)
        if in_x and in_y:
            area = max(1.0, w * h)
            if area < best_area:
                best_area = area
                best = (c['position'], c['type'])
    return best


def is_main_axis_click(trial_id):
    """True iff the trial's final click attributes to a main-axis AOI under
    typed_gapfill (with default tolerance). False for the 158 hard-error
    trials (dd_right, right_chrome, off-target where click is in no
    main-axis bbox).

    Use as a trial-level filter for any click-outcome analysis under
    typed_gapfill: contaminated trials have no defensible main-axis click
    target and should be dropped from `was_clicked` populations.
    """
    try:
        _, _, clicks = load_mouse_events(trial_id)
    except Exception:
        return False
    if not clicks:
        return False
    final = clicks[-1]
    if len(final) < 3:
        return False
    cx, cy = float(final[1]), float(final[2])
    return attribute_click_to_typed_gapfill(cx, cy, trial_id) is not None


# ── Legacy aliases (retained for backward compatibility) ──────────────────
#
# These names were written before the absolute-vs-organic distinction was
# made explicit. They always computed *absolute* rank despite docstrings
# that sometimes said "organic". New code should use the precise helpers
# above; existing callers (many notebooks and scripts) continue to work.

def result_band_tops(n_results, doc_height):
    """DEPRECATED alias for `absolute_rank_band_tops`.

    Historically computed on `count_results_html` which returns the total
    h3 count (absolute rank, ads pooled with organic). New code should
    call `absolute_rank_band_tops` or `organic_rank_band_tops` explicitly.
    """
    return absolute_rank_band_tops(n_results, doc_height)


def count_results_html(trial_id):
    """DEPRECATED alias for `count_absolute_ranks`.

    Historical docstring said "Count organic results in SERP HTML (by
    h3 tags)" but the implementation returned every h3 — including ads.
    The 2026-04-12 analysis of `count_absolute_ranks` distribution
    (92% of trials have 11+ slots) made the drift visible. New code
    should call `count_absolute_ranks` or `count_organic_ranks` by intent.
    """
    return count_absolute_ranks(trial_id)

def assign_fixation_to_position(page_y, tops, n_results):
    """Map a page-space fixation Y to a result position.

    FPOGY from load_fixations() is already page-space (see module docstring).
    This function just bisects against the page-space result band tops — no
    scroll arithmetic. The function accepts cursor_y and click_y too, since
    all three streams share the page-space convention; the separate helpers
    `click_to_position()` and `cursor_to_position()` are kept for clarity at
    call sites.

    Args:
        page_y: page-space Y (fixation, cursor, or click).
        tops: result band top boundaries (page-space, from result_band_tops).
        n_results: total number of results.

    Returns: position index (0-based), or -1 if outside all bands.
    """
    pos = bisect_right(tops, float(page_y)) - 1
    if 0 <= pos < n_results:
        return pos
    return -1


# ── Canonical cursor/click helpers (coordinate-safe) ──────────────────────
#
# These are the ONLY correct ways to get click position, cursor position,
# and gaze-cursor distance from AdSERP data. Use them instead of cargo-
# culting `+ scroll` onto raw mouse Ys. See module docstring for why.

def get_click_page_xy(clicks):
    """Return the last click's (x_page, y_page) in page-space, or None.

    `clicks` is the third element of the tuple returned by
    `load_mouse_events()`. Values are taken AS-IS — evtrack ypos is already
    page-space, so adding scroll would double-count it.
    """
    if not clicks:
        return None
    _, x, y = clicks[-1]
    return (float(x), float(y))


def click_to_position(clicks, tops, n_results):
    """[DEPRECATED 2026-05-05] Legacy Y-band-only click attribution.

    Use `attribute_click_to_typed_gapfill(click_x, click_y, trial_id)`
    instead. This helper does Y-bisect against AOI tops with NO X CHECK
    and assigns clicks anywhere in the document to whatever AOI shares
    their Y. It silently mis-attributes off-axis clicks (right-rail
    dd_right ads, page chrome, far-off-target) to main-axis AOIs and is
    the root cause of the 22.7 % contamination found by
    `scripts/audit_cascade_contamination.py`. Retained for cascade audits
    against pre-2026-05-05 K-claims; not the public API.

    See docs/null-findings/2026-05-05-bbox-y-coverage.md.

    --- legacy docstring follows ---

    Map the last click to a result position via its page-space Y.

    The coordinate-safe replacement for `assign_fixation_to_position(
    clicks[-1][2], click_scroll, tops, n_results)` — which is WRONG because
    `clicks[-1][2]` is already page-space.

    Args:
        clicks: list of (t, x, y) from load_mouse_events().
        tops: result band top boundaries (page-space).
        n_results: total number of results.

    Returns: position index (0-based), or None if no click / outside bands.
    """
    xy = get_click_page_xy(clicks)
    if xy is None:
        return None
    _, page_y = xy
    pos = bisect_right(tops, page_y) - 1
    if 0 <= pos < n_results:
        return pos
    return None


def cursor_to_position(cursor_y_page, tops, n_results):
    """Map a page-space cursor Y to a result position.

    Use for "cursor is near result N" analyses (NB15's dwell-in-proximity,
    NB24's retreat arc target). `cursor_y_page` must come straight from an
    evtrack mouse event, not with scroll added.
    """
    pos = bisect_right(tops, float(cursor_y_page)) - 1
    if 0 <= pos < n_results:
        return pos
    return -1


def page_y_to_viewport_y(page_y, scroll_y_at_t):
    """Subtract scroll to get the viewport-relative Y at a given moment.

    Use when you need "where on the visible screen was this thing at time t"
    — e.g. for rendering, for viewport-containment tests, or for mapping
    to eye-tracker calibration targets. The result can be negative (the
    point has scrolled off the top) or exceed screen_height (hasn't scrolled
    into view yet).
    """
    return float(page_y) - float(scroll_y_at_t)


def viewport_y_to_page_y(viewport_y, scroll_y_at_t):
    """Add scroll to a viewport-relative Y to get page-space.

    The inverse of `page_y_to_viewport_y`. Rarely needed for AdSERP data
    since all three streams (gaze, cursor, click) arrive in page-space —
    this exists for callers synthesizing gaze at a target screen location.
    """
    return float(viewport_y) + float(scroll_y_at_t)


def gaze_cursor_distance(fix_x, fix_y, cursor_x, cursor_y):
    """Euclidean distance between gaze and cursor, in page-space pixels.

    Both streams are page-space per the module docstring, so no scroll
    arithmetic enters — the distance is just hypot of the deltas. Scroll
    cancels even under the old (wrong) screen-space interpretation, which
    is why the original NB15 bug (adding scroll to both sides) was
    algebraically a no-op on dx/dy but still produced nonsense when the
    code later compared fix_y to a mixed-space quantity.
    """
    dx = float(fix_x) - float(cursor_x)
    dy = float(fix_y) - float(cursor_y)
    return float(np.hypot(dx, dy))


def interpolate_cursor_at(t, mouse_ts, mouse_xs, mouse_ys):
    """Linear-interpolate cursor position at time t. Returns (x_page, y_page) or None.

    Helper for per-fixation gaze-cursor analyses. `mouse_ts/xs/ys` should be
    numpy arrays extracted from `load_mouse_events()` (positional events
    only: mousemove, click, mouseover). Values stay in evtrack page-space.
    """
    n = len(mouse_ts)
    if n == 0:
        return None
    if n == 1:
        return (float(mouse_xs[0]), float(mouse_ys[0]))
    idx = int(np.searchsorted(mouse_ts, t))
    if idx <= 0:
        return (float(mouse_xs[0]), float(mouse_ys[0]))
    if idx >= n:
        return (float(mouse_xs[-1]), float(mouse_ys[-1]))
    t0, t1 = float(mouse_ts[idx - 1]), float(mouse_ts[idx])
    frac = 0.0 if t1 == t0 else (float(t) - t0) / (t1 - t0)
    x = float(mouse_xs[idx - 1]) + frac * (float(mouse_xs[idx]) - float(mouse_xs[idx - 1]))
    y = float(mouse_ys[idx - 1]) + frac * (float(mouse_ys[idx]) - float(mouse_ys[idx - 1]))
    return (x, y)

# ── SERP text extraction ──────────────────────────────────────────────────

STOPWORDS = frozenset(
    'the a an and or but in on at to for of is it this that was were be been '
    'being have has had do does did will would shall should may might can could '
    'with from by as are not no its my your his her their our its '
    'between both during each few how more most other some such through until '
    'where which while who whom why into over under buy'.split()
)

def tokenize(text):
    """Lowercase, split on non-alphanumeric, remove stopwords and single chars."""
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

def extract_serp_results(trial_id):
    """Extract ordered results from a SERP HTML file.

    Returns list of dicts: {position, title, snippet, tokens, token_set}.
    """
    from bs4 import BeautifulSoup
    path = SERP_DIR / f'{trial_id}.html'
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    results = []
    rso = soup.find(id='rso') or soup

    for i, h3 in enumerate(rso.find_all('h3')):
        title = h3.get_text(strip=True)
        container = h3.parent
        for _ in range(5):
            if container and container.parent:
                container = container.parent
                if container.name == 'div' and container.get('class') and any('g' in c for c in container.get('class', [])):
                    break

        snippets = []
        if container:
            for el in container.find_all(['span', 'div'], recursive=True):
                t = el.get_text(strip=True)
                if t and t != title and len(t) > 20:
                    snippets.append(t)

        full_text = title + ' ' + ' '.join(snippets[:3])
        tokens = tokenize(full_text)
        results.append({
            'position': i,
            'title': title,
            'snippet': ' '.join(snippets[:2])[:200],
            'tokens': tokens,
            'token_set': set(tokens),
        })

    return results

# ── Catalog and supplementary data ─────────────────────────────────────────

def load_catalog():
    """Load interesting-trials.json catalog.

    Returns dict with keys: generated, total_trials, tagged_trials,
    tag_counts, prototypical, trials (list of trial dicts).
    """
    path = DATA_DIR / 'interesting-trials.json'
    with open(path) as f:
        return json.load(f)

def load_catalog_indexed():
    """Load catalog as a dict keyed by trial_id."""
    cat = load_catalog()
    return {t['trial_id']: t for t in cat['trials']}

def load_lhipa():
    """Load pre-computed LHIPA scores per trial.

    Returns dict: {trial_id: {lhipa, ...}}.
    """
    path = Path(__file__).parent / 'lhipa_per_trial.json'
    with open(path) as f:
        return json.load(f)

def remove_blinks(timestamps, pupil_diameters, validity, exclusion_ms=200):
    """Remove blink samples and interpolate gaps.

    Blinks identified by validity=0 or pupil_diameter<=0.
    A 200ms exclusion window removes pre- and post-blink artifacts.

    Returns (clean_timestamps, clean_pupil_diameters) as numpy arrays,
    or (None, None) if >50% of samples are invalid.
    """
    ts = np.array(timestamps, dtype=float)
    pd = np.array(pupil_diameters, dtype=float)
    val = np.array(validity, dtype=int)

    invalid = (val == 0) | (pd <= 0)

    if invalid.any():
        invalid_times = ts[invalid]
        for it in invalid_times:
            mask = (ts >= it - exclusion_ms) & (ts <= it + exclusion_ms)
            invalid[mask] = True

    if invalid.sum() > len(invalid) * 0.5:
        return None, None

    valid_mask = ~invalid
    if valid_mask.sum() < 50:
        return None, None

    clean_pd = pd.copy()
    valid_indices = np.where(valid_mask)[0]
    invalid_indices = np.where(invalid)[0]

    if len(invalid_indices) > 0 and len(valid_indices) > 1:
        clean_pd[invalid_indices] = np.interp(
            ts[invalid_indices], ts[valid_indices], pd[valid_indices]
        )

    return ts, clean_pd


def load_pupil_trial(trial_id):
    """Load and blink-clean pupil data for a trial.

    Combines left and right eyes (mean when both valid, single-eye fallback).
    Returns dict with ts, clean_pd, raw_pd, validity, bpogx, bpogy.
    Returns None if trial is unusable (>50% blinks or <100 samples).
    """
    pupil_path = PUPIL_DIR / f'{trial_id}.csv'
    if not pupil_path.exists():
        return None

    timestamps, mean_pd, combined_val = [], [], []
    bpogx_list, bpogy_list = [], []

    with open(pupil_path) as f:
        for row in csv.DictReader(f):
            try:
                t = int(float(row['timestamp']))
                lpd = float(row['LPD'])
                rpd = float(row['RPD'])
                lv = int(row['LPV'])
                rv = int(row['RPV'])
            except (ValueError, KeyError):
                continue

            timestamps.append(t)
            bpogx_list.append(float(row.get('BPOGX', 0)))
            bpogy_list.append(float(row.get('BPOGY', 0)))

            if lv and rv:
                mean_pd.append((lpd + rpd) / 2)
                combined_val.append(1)
            elif lv:
                mean_pd.append(lpd)
                combined_val.append(1)
            elif rv:
                mean_pd.append(rpd)
                combined_val.append(1)
            else:
                mean_pd.append(0)
                combined_val.append(0)

    if len(timestamps) < 100:
        return None

    clean_ts, clean_pd = remove_blinks(timestamps, mean_pd, combined_val)
    if clean_ts is None:
        return None

    return {
        'ts': clean_ts,
        'clean_pd': clean_pd,
        'raw_pd': mean_pd,
        'validity': combined_val,
        'bpogx': bpogx_list,
        'bpogy': bpogy_list,
    }


def load_difficulty_measures():
    """Load pre-computed SERP difficulty measures.

    Returns dict: {trial_id: {jaccard, relevance_spread, distinctive_density, ...}}.
    """
    path = DATA_DIR / 'serp-difficulty-measures.json'
    with open(path) as f:
        return json.load(f)

# ── Composite loaders ──────────────────────────────────────────────────────

def load_trial(trial_id):
    """Load all data for a single trial.

    Returns dict with: fixations, events, scrolls, clicks,
    doc_height, screen_height, page_timestamp, scroll_ts, scroll_ys.
    Returns None if essential data is missing.
    """
    doc_h, scr_h, ts = get_trial_meta(trial_id)
    if doc_h is None:
        return None

    fixations = load_fixations(trial_id)
    events, scrolls, clicks = load_mouse_events(trial_id)

    scroll_ts = [s[0] for s in scrolls]
    scroll_ys = [s[1] for s in scrolls]

    return {
        'trial_id': trial_id,
        'fixations': fixations,
        'events': events,
        'scrolls': scrolls,
        'clicks': clicks,
        'doc_height': doc_h,
        'screen_height': scr_h,
        'page_timestamp': ts,
        'scroll_ts': scroll_ts,
        'scroll_ys': scroll_ys,
    }

# ── Forward/regression classification ─────────────────────────────────────

def classify_fixations(trial, hwm_tolerance=50):
    """Classify each fixation as forward-pass or regression.

    A fixation is 'forward' if the scroll offset at fixation time is within
    hwm_tolerance pixels of the scroll high-water mark. Otherwise it's a
    regression — the user scrolled back up.

    Args:
        trial: dict from load_trial()
        hwm_tolerance: pixels below HWM that still count as forward (default 50)

    Returns:
        List of dicts, one per fixation, each with:
          t, x, y, d: original fixation fields
          scroll_y: scroll offset at fixation time
          page_y: y position in page coordinates (y + scroll_y)
          position: result position (0–9), or -1 if outside result bands
          is_forward: True if forward-pass, False if regression
    """
    fixations = trial['fixations']
    scr_h = trial['screen_height']
    doc_h = trial['doc_height']
    sts = trial['scroll_ts']
    sys_ = trial['scroll_ys']

    bands = result_bands(10, doc_h)
    tops = [b[0] for b in bands]

    hwm = 0.0
    result = []

    for fix in fixations:
        so = 0.0
        if sts:
            if fix['t'] <= sts[0]:
                so = sys_[0]
            elif fix['t'] >= sts[-1]:
                so = sys_[-1]
            else:
                so = sys_[bisect_right(sts, fix['t']) - 1]

        if so > hwm:
            hwm = so

        is_forward = (so >= hwm - hwm_tolerance)

        page_y = fix['y']  # FPOGY is already page-space (see module docstring)
        pos = bisect_right(tops, page_y) - 1
        if pos < 0 or pos > 9:
            pos = -1

        result.append({
            't': fix['t'],
            'x': fix['x'],
            'y': fix['y'],
            'd': fix['d'],
            'scroll_y': so,
            'page_y': page_y,
            'position': pos,
            'is_forward': is_forward,
        })

    return result


# ── Plotting defaults ──────────────────────────────────────────────────────

def setup_plotting():
    """Apply consistent matplotlib style across all notebooks."""
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'figure.figsize': (12, 6),
        'figure.dpi': 150,
        'font.family': 'sans-serif',
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })
