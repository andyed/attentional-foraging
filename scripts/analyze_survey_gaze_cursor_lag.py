#!/usr/bin/env python
"""Survey-window gaze-cursor coupling analysis.

Tests whether the cursor tracks gaze more tightly in the Survey phase
(first 5 fixations) than the Evaluate phase (fixations 6..last-pre-click).
Orthogonal signal to the NB17-style "which rects do Survey fixations
land on" approach — here we ask whether the cursor is a proto-commitment
signal during Survey.

Per-trial metrics:
    d_survey  — median page-space Euclidean distance between gaze and
                interpolated cursor for fixations 1..5
    d_eval    — same for fixations 6..last-pre-click
    d_click   — median distance during the 0..2s window before ANY click
                (reference — reproduces NB15 acquisition value)
    ratio     — d_survey / d_eval

Cohorts:
    plain_top  — trials with no dd_top ad at position 1
    ad_top     — trials with a dd_top ad at position 1
    first_fix_in_ad  — first column fixation lands inside an ad rect
    first_fix_in_organic — first column fixation lands outside any ad rect

Outputs:
    scripts/output/survey_gaze_cursor_lag/
      per_trial.csv          — one row per trial
      summary_corpus.csv     — corpus-wide and per-cohort medians + tests
      per_fix_coupling.csv   — median distance by fixation index 0..9
      per_fix_coupling.png   — figure (fixation index × median distance)
      summary.json           — top-line numbers for memo

Run (~2 min):
    .venv/bin/python scripts/analyze_survey_gaze_cursor_lag.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path
from collections import defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    gaze_cursor_distance,
    interpolate_cursor_at,
    _load_ad_regions,
    _rect_in_result_column,
)

OUT_DIR = ROOT / 'scripts' / 'output' / 'survey_gaze_cursor_lag'
OUT_DIR.mkdir(parents=True, exist_ok=True)

SURVEY_K = 5                  # first 5 fixations = Survey window
PRECLICK_WINDOW_MS = 2000     # d_click = 0..2s before any click
COL_X_MIN = 162
COL_X_MAX = 702
MAX_FIX_INDEX = 10            # per-fixation coupling out to index 0..9

POS_EVENTS = {'mousemove', 'mouseover', 'mouseout',
              'mousedown', 'mouseup', 'click'}


def _filter_ad_rects_in_col(ad_regions):
    """Ad rects that fall inside the result column (dd_top + native_ad)."""
    rects = []
    for etype, ers in ad_regions.items():
        if etype not in ('dd_top', 'native_ad'):
            continue
        for (rx, ry, rw, rh) in ers:
            if not _rect_in_result_column(rx, rw):
                continue
            rects.append((rx, ry, rw, rh))
    return rects


def _point_in_any_rect(px, py, rects):
    for (rx, ry, rw, rh) in rects:
        if rx <= px <= rx + rw and ry <= py <= ry + rh:
            return True
    return False


def _has_ddtop(ad_regions):
    for (rx, ry, rw, rh) in (ad_regions.get('dd_top') or []):
        if _rect_in_result_column(rx, rw):
            return True
    return False


def compute_trial_record(tid):
    fix = load_fixations(tid)
    if len(fix) < 2:
        return None
    try:
        events, _scrolls, clicks = load_mouse_events(tid)
    except FileNotFoundError:
        return None

    # Position-only stream for interpolation
    pos = [(t, x, y) for (t, evt, x, y) in events if evt in POS_EVENTS]
    if len(pos) < 2:
        return None
    mt = np.array([p[0] for p in pos], dtype=float)
    mx = np.array([p[1] for p in pos], dtype=float)
    my = np.array([p[2] for p in pos], dtype=float)

    ad_regions = _load_ad_regions(tid)
    rects = _filter_ad_rects_in_col(ad_regions)
    is_ad_top = _has_ddtop(ad_regions)

    # First column fixation for first-fix-in-ad classification
    col_fix = [f for f in fix if COL_X_MIN <= f['x'] <= COL_X_MAX]
    first_col_in_ad = None
    if col_fix and rects:
        f0 = col_fix[0]
        first_col_in_ad = _point_in_any_rect(f0['x'], f0['y'], rects)

    # Per-fixation gaze-cursor distance over the full trial, for later
    # per-index aggregation and phase partitioning.
    per_fix_d = []
    for f in fix:
        cur = interpolate_cursor_at(f['t'], mt, mx, my)
        if cur is None:
            per_fix_d.append(None)
            continue
        d = gaze_cursor_distance(f['x'], f['y'], cur[0], cur[1])
        per_fix_d.append(d)

    # Phase partition: Survey = first 5 fixations; Evaluate = fix 6..last
    # pre-click. If the trial has a click, trim fixations after the last
    # fixation before the first click to better match the "evaluate" idea.
    t_first_click = clicks[0][0] if clicks else None
    if t_first_click is not None:
        last_pre_click_idx = -1
        for i, f in enumerate(fix):
            if f['t'] <= t_first_click:
                last_pre_click_idx = i
            else:
                break
        eval_slice = slice(SURVEY_K, max(SURVEY_K, last_pre_click_idx + 1))
    else:
        eval_slice = slice(SURVEY_K, len(fix))

    survey_d = [d for d in per_fix_d[:SURVEY_K] if d is not None]
    eval_d = [d for d in per_fix_d[eval_slice] if d is not None]

    if not survey_d or not eval_d:
        return None

    d_survey = float(np.median(survey_d))
    d_eval = float(np.median(eval_d))

    # Pre-click window: 0..2000 ms before first click, median cursor-gaze
    # distance across fixations whose t falls in that window.
    d_click = float('nan')
    if t_first_click is not None:
        win_lo = t_first_click - PRECLICK_WINDOW_MS
        win_hi = t_first_click
        win_d = []
        for f, d in zip(fix, per_fix_d):
            if d is None:
                continue
            if win_lo <= f['t'] <= win_hi:
                win_d.append(d)
        if win_d:
            d_click = float(np.median(win_d))

    return {
        'tid': tid,
        'n_fix': len(fix),
        'n_survey_fix_used': len(survey_d),
        'n_eval_fix_used': len(eval_d),
        'd_survey_px': d_survey,
        'd_eval_px': d_eval,
        'd_click_px': d_click,
        'ratio_s_over_e': d_survey / d_eval if d_eval > 0 else float('nan'),
        'is_ad_top': bool(is_ad_top),
        'first_fix_in_ad': first_col_in_ad,  # True/False/None (no ad rects)
        'per_fix_d': per_fix_d[:MAX_FIX_INDEX],  # variable-length list
    }


def wilcoxon_signed_rank(diffs):
    """Wilcoxon signed-rank test wrapper. Returns (W, p, n_nonzero)."""
    try:
        from scipy.stats import wilcoxon
    except Exception:
        return (float('nan'), float('nan'), 0)
    arr = np.asarray([d for d in diffs if math.isfinite(d)], dtype=float)
    nz = arr[arr != 0]
    if len(nz) < 10:
        return (float('nan'), float('nan'), len(nz))
    try:
        stat = wilcoxon(nz, zero_method='wilcox', alternative='two-sided')
        return (float(stat.statistic), float(stat.pvalue), len(nz))
    except Exception:
        return (float('nan'), float('nan'), len(nz))


def summarize_cohort(records, name, pred):
    subset = [r for r in records if pred(r)]
    n = len(subset)
    if n == 0:
        return None
    ds = np.array([r['d_survey_px'] for r in subset], dtype=float)
    de = np.array([r['d_eval_px'] for r in subset], dtype=float)
    dc = np.array([r['d_click_px'] for r in subset
                   if math.isfinite(r['d_click_px'])], dtype=float)
    ratio = np.array([r['ratio_s_over_e'] for r in subset
                      if math.isfinite(r['ratio_s_over_e'])], dtype=float)
    diffs = (ds - de)
    W, p, nw = wilcoxon_signed_rank(diffs.tolist())
    return {
        'cohort': name,
        'n_trials': int(n),
        'median_d_survey_px': float(np.median(ds)),
        'median_d_eval_px': float(np.median(de)),
        'median_d_click_px': float(np.median(dc)) if len(dc) else float('nan'),
        'median_diff_s_minus_e_px': float(np.median(diffs)),
        'median_ratio_s_over_e': float(np.median(ratio)) if len(ratio) else float('nan'),
        'frac_trials_survey_looser': float((diffs > 0).mean()),
        'wilcoxon_W': W,
        'wilcoxon_p': p,
        'wilcoxon_n_nonzero': int(nw),
    }


def write_per_trial(records, path):
    keys = [k for k in records[0].keys() if k != 'per_fix_d']
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in records:
            w.writerow({k: r[k] for k in keys})


def write_per_fix_coupling(records, path):
    """Per-fixation-index median distance for corpus / plain_top / ad_top."""
    by_cohort = {
        'all': defaultdict(list),
        'plain_top': defaultdict(list),
        'ad_top': defaultdict(list),
        'first_fix_in_ad': defaultdict(list),
        'first_fix_in_organic': defaultdict(list),
    }
    for r in records:
        pfd = r['per_fix_d']
        for i, d in enumerate(pfd):
            if d is None:
                continue
            by_cohort['all'][i].append(d)
            if r['is_ad_top']:
                by_cohort['ad_top'][i].append(d)
            else:
                by_cohort['plain_top'][i].append(d)
            if r['first_fix_in_ad'] is True:
                by_cohort['first_fix_in_ad'][i].append(d)
            elif r['first_fix_in_ad'] is False:
                by_cohort['first_fix_in_organic'][i].append(d)

    rows = []
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['fix_index', 'cohort', 'n', 'median_px', 'mean_px', 'iqr_lo_px', 'iqr_hi_px'])
        for cohort, d in by_cohort.items():
            for i in sorted(d.keys()):
                arr = np.array(d[i])
                row = [i, cohort, len(arr),
                       f'{np.median(arr):.1f}',
                       f'{arr.mean():.1f}',
                       f'{np.percentile(arr, 25):.1f}',
                       f'{np.percentile(arr, 75):.1f}']
                w.writerow(row)
                rows.append({
                    'fix_index': i, 'cohort': cohort, 'n': len(arr),
                    'median_px': float(np.median(arr)),
                    'mean_px': float(arr.mean()),
                    'iqr_lo_px': float(np.percentile(arr, 25)),
                    'iqr_hi_px': float(np.percentile(arr, 75)),
                })
    return rows


def render_figure(per_fix_rows, out_path):
    """Per-fixation-index median coupling, WCAG 8:1 contrast floor.

    Background #FFFFFF, ink #000000 (21:1). Plain_top and ad_top lines use
    #003366 (13.1:1) and #8B1A1A (9.0:1) — both above 8:1 against white.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f'[render_figure] matplotlib missing: {exc}', flush=True)
        return

    PLAIN = '#003366'
    ADTOP = '#8B1A1A'
    ALL = '#000000'

    def series(cohort):
        xs, ys, los, his = [], [], [], []
        for r in per_fix_rows:
            if r['cohort'] != cohort:
                continue
            xs.append(r['fix_index'])
            ys.append(r['median_px'])
            los.append(r['iqr_lo_px'])
            his.append(r['iqr_hi_px'])
        order = np.argsort(xs)
        return (np.array(xs)[order], np.array(ys)[order],
                np.array(los)[order], np.array(his)[order])

    fig, ax = plt.subplots(figsize=(10, 6), dpi=140)
    ax.set_facecolor('#FFFFFF')
    fig.patch.set_facecolor('#FFFFFF')

    for cohort, color, label in [
        ('all', ALL, 'All trials'),
        ('plain_top', PLAIN, 'plain_top (no dd_top ad)'),
        ('ad_top', ADTOP, 'ad_top (dd_top ad)'),
    ]:
        xs, ys, los, his = series(cohort)
        if len(xs) == 0:
            continue
        ax.plot(xs, ys, '-o', color=color, linewidth=2.5,
                markersize=8, label=label)

    # Shade the Survey window (first 5 fixations = indices 0..4)
    ax.axvspan(-0.4, 4.4, color='#E0E0E0', alpha=0.6, zorder=0,
               label='Survey window (fix 1–5)')

    ax.set_xlabel('Fixation index (0 = first fixation in trial)',
                  fontsize=13, color='#000000')
    ax.set_ylabel('Median gaze-cursor distance (page-space pixels)',
                  fontsize=13, color='#000000')
    ax.set_title('Gaze-cursor coupling by fixation index\n'
                 '(lower = cursor tracks gaze more tightly)',
                 fontsize=14, color='#000000')
    ax.set_xticks(range(0, MAX_FIX_INDEX))
    ax.tick_params(axis='both', colors='#000000', labelsize=11)
    ax.grid(True, color='#888888', alpha=0.3, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color('#000000')
        spine.set_linewidth(1.2)
    ax.legend(loc='upper right', framealpha=1.0, edgecolor='#000000',
              fontsize=11, labelcolor='#000000')

    plt.tight_layout()
    plt.savefig(out_path, dpi=140, facecolor='#FFFFFF')
    plt.close(fig)


def main():
    t0 = time.time()
    tids = get_trial_ids()
    print(f'[gaze_cursor_lag] processing {len(tids)} trials...', flush=True)
    records = []
    skipped = 0
    for i, tid in enumerate(tids):
        try:
            rec = compute_trial_record(tid)
        except Exception:
            skipped += 1
            continue
        if rec is None:
            skipped += 1
            continue
        records.append(rec)
        if (i + 1) % 500 == 0:
            dt = time.time() - t0
            print(f'  {i + 1}/{len(tids)}  ({dt:.1f}s)', flush=True)
    print(f'[gaze_cursor_lag] {len(records)} records, {skipped} skipped, '
          f'{time.time() - t0:.1f}s', flush=True)

    if not records:
        print('[gaze_cursor_lag] no records — aborting', flush=True)
        return

    # Per-trial CSV
    write_per_trial(records, OUT_DIR / 'per_trial.csv')

    # Cohort summaries
    cohorts = [
        ('all', lambda r: True),
        ('plain_top', lambda r: not r['is_ad_top']),
        ('ad_top', lambda r: r['is_ad_top']),
        ('first_fix_in_ad', lambda r: r['first_fix_in_ad'] is True),
        ('first_fix_in_organic', lambda r: r['first_fix_in_ad'] is False),
    ]
    summary_rows = []
    for name, pred in cohorts:
        row = summarize_cohort(records, name, pred)
        if row is not None:
            summary_rows.append(row)
    with open(OUT_DIR / 'summary_corpus.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        for r in summary_rows:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v)
                        for k, v in r.items()})

    # Per-fix coupling table + figure
    per_fix_rows = write_per_fix_coupling(records, OUT_DIR / 'per_fix_coupling.csv')
    render_figure(per_fix_rows, OUT_DIR / 'per_fix_coupling.png')

    # Top-line JSON
    def find_row(name):
        for r in summary_rows:
            if r['cohort'] == name:
                return r
        return None

    top = {
        'n_records': len(records),
        'n_ad_top': sum(1 for r in records if r['is_ad_top']),
        'n_plain_top': sum(1 for r in records if not r['is_ad_top']),
        'n_first_fix_in_ad': sum(1 for r in records if r['first_fix_in_ad'] is True),
        'n_first_fix_in_organic': sum(1 for r in records
                                      if r['first_fix_in_ad'] is False),
        'summary_all': find_row('all'),
        'summary_plain_top': find_row('plain_top'),
        'summary_ad_top': find_row('ad_top'),
        'summary_first_fix_in_ad': find_row('first_fix_in_ad'),
        'summary_first_fix_in_organic': find_row('first_fix_in_organic'),
    }
    with open(OUT_DIR / 'summary.json', 'w') as f:
        json.dump(top, f, indent=2, default=str)

    print(f'[gaze_cursor_lag] wrote outputs to {OUT_DIR}')
    print(json.dumps({
        'n': top['n_records'],
        'all': {
            'd_survey_px': top['summary_all']['median_d_survey_px'],
            'd_eval_px': top['summary_all']['median_d_eval_px'],
            'd_click_px': top['summary_all']['median_d_click_px'],
            'ratio_s_over_e': top['summary_all']['median_ratio_s_over_e'],
            'wilcoxon_p': top['summary_all']['wilcoxon_p'],
        },
    }, indent=2, default=str))


if __name__ == '__main__':
    main()
