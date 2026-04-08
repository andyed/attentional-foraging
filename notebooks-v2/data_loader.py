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

# ── Trial discovery ────────────────────────────────────────────────────────

def get_trial_ids():
    """Sorted list of all trial IDs (from mouse-movement-data filenames)."""
    return sorted(f.replace('.csv', '') for f in os.listdir(MOUSE_DIR) if f.endswith('.csv'))

# ── Fixation loading ───────────────────────────────────────────────────────

def load_fixations(trial_id, clamp_y=True):
    """Load fixations for a trial.

    Returns list of dicts: {t, x, y, y_raw, d} where t is timestamp (ms),
    x/y are screen-space pixels, d is duration (ms).

    FPOGY clamp: 24.5% of Gazepoint GP3 HD fixations have FPOGY > screen
    height (1024px). These are eye-tracker noise, not gaze at below-screen
    content. Clamping to [0, screen_height] prevents downstream position
    mapping errors. y_raw preserves the original value.
    """
    path = FIXATION_DIR / f'{trial_id}.csv'
    # Get screen height for clamping
    screen_h = 1024  # default
    if clamp_y:
        meta = get_trial_meta(trial_id)
        if meta[1] is not None:
            screen_h = meta[1]

    fixations = []
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                y_raw = float(row['FPOGY'])
                fixations.append({
                    't': float(row['timestamp']),
                    'x': float(row['FPOGX']),
                    'y': min(y_raw, screen_h) if clamp_y else y_raw,
                    'y_raw': y_raw,
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

# ── Result band estimation ─────────────────────────────────────────────────

def result_bands(n_results, doc_height):
    """Estimate Y-coordinate boundaries for each result position.

    Returns list of (top, bottom) tuples for each result.
    """
    header = 200
    per_res = (doc_height - 400) / max(n_results, 1)
    return [(header + i * per_res, header + (i + 1) * per_res) for i in range(n_results)]

def result_band_tops(n_results, doc_height):
    """Return just the top Y-coordinates for bisect_right lookup."""
    header = 200
    per_res = (doc_height - 400) / max(n_results, 1)
    return [header + i * per_res for i in range(n_results)]

def count_results_html(trial_id):
    """Count organic results in SERP HTML (by h3 tags)."""
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

def assign_fixation_to_position(fix_y, scroll_y, tops, n_results):
    """Map a fixation to a result position using scroll-corrected page-space Y.

    Args:
        fix_y: raw FPOGY (screen pixels)
        scroll_y: scroll offset at fixation time
        tops: result band top boundaries (from result_band_tops)
        n_results: total number of results

    Returns: position index (0-based), or -1 if outside all bands.
    """
    page_y = fix_y + scroll_y
    pos = bisect_right(tops, page_y) - 1
    if 0 <= pos < n_results:
        return pos
    return -1

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

        fy = max(0.0, min(fix['y'], scr_h))
        page_y = fy + so
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
