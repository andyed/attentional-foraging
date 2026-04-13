#!/usr/bin/env python
"""Survey-phase fixation analysis vs ad locations.

Tests whether the OSEC Survey phase (first K fixations) over-indexes on
ad rectangles relative to the Evaluate phase and a uniform baseline —
the ad-mapping-for-avoidance hypothesis.

Outputs:
    scripts/output/survey_vs_ads/
      per_trial.csv         — one row per trial, Survey/Evaluate ad stats
      summary_k{3,5,7}.csv  — aggregate summary tables
      first_fix_location.csv — first-fixation distance-to-ad distribution
      saccade_amplitude_profile.csv — mean amplitude by ordinal for cohorts
      ad_count_vs_survey_len.csv — scatter data for §6
      summary.json          — top-line numbers for memo

Run:
    .venv/bin/python scripts/analyze_survey_vs_ads.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
import time
from pathlib import Path
from collections import defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    get_trial_ids,
    get_trial_meta,
    load_fixations,
    _load_ad_regions,
    _rect_in_result_column,
)

OUT_DIR = ROOT / 'scripts' / 'output' / 'survey_vs_ads'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Result column bounds (matches _RESULT_COL_X_MIN/MAX in data_loader)
COL_X_MIN = 162
COL_X_MAX = 702
COL_WIDTH = COL_X_MAX - COL_X_MIN

# Survey phase K values
K_VALUES = [3, 5, 7]

# Near-edge threshold for first-fixation analysis
NEAR_PX = 50
FAR_PX = 200

# RNG for null model
rng = np.random.default_rng(20260412)


def filter_in_col_rects(ad_regions: dict) -> list[tuple[float, float, float, float]]:
    """Return list of (x, y, w, h) rects inside the result column for
    the ad types we care about (dd_top + native_ad). dd_right is already
    excluded by _load_ad_regions.
    """
    rects = []
    for etype, ers in ad_regions.items():
        if etype not in ('dd_top', 'native_ad'):
            continue
        for (rx, ry, rw, rh) in ers:
            if not _rect_in_result_column(rx, rw):
                continue
            # Clip to result column so area is computed against in-column area
            cx0 = max(rx, COL_X_MIN)
            cx1 = min(rx + rw, COL_X_MAX)
            if cx1 <= cx0:
                continue
            rects.append((cx0, ry, cx1 - cx0, rh))
    return rects


def point_in_any_rect(px, py, rects) -> bool:
    for (rx, ry, rw, rh) in rects:
        if rx <= px <= rx + rw and ry <= py <= ry + rh:
            return True
    return False


def distance_to_nearest_edge(px, py, rects) -> float:
    """Signed distance to nearest rect edge. Negative = inside. If no
    rects, returns +inf.
    """
    if not rects:
        return float('inf')
    best_outside = float('inf')
    inside = False
    best_inside_penetration = 0.0
    for (rx, ry, rw, rh) in rects:
        x0, x1 = rx, rx + rw
        y0, y1 = ry, ry + rh
        if x0 <= px <= x1 and y0 <= py <= y1:
            # inside this rect
            d = min(px - x0, x1 - px, py - y0, y1 - py)
            inside = True
            best_inside_penetration = max(best_inside_penetration, d)
        else:
            dx = 0.0 if x0 <= px <= x1 else min(abs(px - x0), abs(px - x1))
            dy = 0.0 if y0 <= py <= y1 else min(abs(py - y0), abs(py - y1))
            d = math.hypot(dx, dy)
            if d < best_outside:
                best_outside = d
    if inside:
        return -best_inside_penetration
    return best_outside


def trial_col_y_extent(fixations, rects, doc_h) -> tuple[float, float]:
    """Return (y_min, y_max) to treat as the in-result-column Y extent
    for this trial. Use union of ad-rect y span and fixation y span,
    clipped to [0, doc_h]. Fallback to (0, doc_h).
    """
    ys = []
    for (_rx, ry, _rw, rh) in rects:
        ys.extend([ry, ry + rh])
    for f in fixations:
        if COL_X_MIN <= f['x'] <= COL_X_MAX:
            ys.append(f['y'])
    if not ys:
        return (0.0, float(doc_h or 2642))
    y0 = max(0.0, min(ys))
    y1 = min(float(doc_h or 2642), max(ys))
    if y1 <= y0:
        return (0.0, float(doc_h or 2642))
    return (y0, y1)


def compute_trial_record(tid: str):
    fix = load_fixations(tid)
    if len(fix) < 2:
        return None
    doc_h, _scr_h, _ts = get_trial_meta(tid)
    ad_regions = _load_ad_regions(tid)
    rects = filter_in_col_rects(ad_regions)

    # Counts per type in-column
    dd_top_rects = [(rx, ry, rw, rh) for (rx, ry, rw, rh) in
                    (ad_regions.get('dd_top') or [])
                    if _rect_in_result_column(rx, rw)]
    native_rects = [(rx, ry, rw, rh) for (rx, ry, rw, rh) in
                    (ad_regions.get('native_ad') or [])
                    if _rect_in_result_column(rx, rw)]
    n_ddtop = len(dd_top_rects)
    n_native = len(native_rects)

    # Cohort
    is_plain_top = n_ddtop == 0

    # Restrict analysis fixations to those inside the result column horizontally
    col_fix = [f for f in fix if COL_X_MIN <= f['x'] <= COL_X_MAX]
    if len(col_fix) < 2:
        return None

    y0, y1 = trial_col_y_extent(col_fix, rects, doc_h)
    col_height = max(1.0, y1 - y0)
    col_area = COL_WIDTH * col_height

    # Compute ad area inside the (y0,y1) strip
    ad_area = 0.0
    for (rx, ry, rw, rh) in rects:
        ax0 = max(rx, COL_X_MIN)
        ax1 = min(rx + rw, COL_X_MAX)
        ay0 = max(ry, y0)
        ay1 = min(ry + rh, y1)
        if ax1 > ax0 and ay1 > ay0:
            ad_area += (ax1 - ax0) * (ay1 - ay0)
    ad_area_frac = ad_area / col_area

    rec = {
        'tid': tid,
        'n_col_fix': len(col_fix),
        'n_ddtop': n_ddtop,
        'n_native': n_native,
        'n_total_ads': n_ddtop + n_native,
        'is_plain_top': is_plain_top,
        'col_area': col_area,
        'ad_area': ad_area,
        'ad_area_frac': ad_area_frac,
        'col_y_min': y0,
        'col_y_max': y1,
    }

    # Per-K partitions
    for K in K_VALUES:
        survey = col_fix[:K]
        evaluate = col_fix[K:]
        n_s = len(survey)
        n_e = len(evaluate)
        p_ad_s = sum(1 for f in survey if point_in_any_rect(f['x'], f['y'], rects))
        p_ad_e = sum(1 for f in evaluate if point_in_any_rect(f['x'], f['y'], rects))
        # Edge distances (signed, negative = inside)
        d_s = [distance_to_nearest_edge(f['x'], f['y'], rects) for f in survey]
        d_e = [distance_to_nearest_edge(f['x'], f['y'], rects) for f in evaluate]
        rec[f'n_survey_fix_K{K}'] = n_s
        rec[f'n_eval_fix_K{K}'] = n_e
        rec[f'n_survey_on_ad_K{K}'] = p_ad_s
        rec[f'n_eval_on_ad_K{K}'] = p_ad_e
        rec[f'med_d_survey_K{K}'] = float(np.median(d_s)) if d_s else float('nan')
        rec[f'med_d_eval_K{K}'] = float(np.median(d_e)) if d_e else float('nan')
        # Survey-phase wall-clock duration (t at start of fix K) − t at fix 0
        if n_s >= 1:
            t_start = survey[0]['t']
            t_end = survey[-1]['t'] + survey[-1]['d']
            rec[f'survey_ms_K{K}'] = max(0.0, t_end - t_start)
        else:
            rec[f'survey_ms_K{K}'] = float('nan')

    # First fixation characterization
    f0 = col_fix[0]
    d0 = distance_to_nearest_edge(f0['x'], f0['y'], rects) if rects else float('inf')
    rec['first_fix_x'] = f0['x']
    rec['first_fix_y'] = f0['y']
    rec['first_fix_d_to_ad'] = d0
    rec['first_fix_inside_ad'] = d0 <= 0
    rec['first_fix_near_ad'] = 0 < d0 <= NEAR_PX
    rec['first_fix_far_from_ad'] = d0 > FAR_PX

    # Saccade amplitude profile for first 20 saccades
    amps = []
    for i in range(1, min(21, len(col_fix))):
        dx = col_fix[i]['x'] - col_fix[i - 1]['x']
        dy = col_fix[i]['y'] - col_fix[i - 1]['y']
        amps.append(math.hypot(dx, dy))
    rec['saccade_amps_20'] = amps  # variable length

    # Null model saccade endpoints: K=5 uniform draws within (col_x, y0..y1)
    rec['null_inside_frac'] = ad_area_frac  # expected inside-rate under uniform
    # Also sample, to get median distance-to-edge under null (for reference)
    if rects:
        xs = rng.uniform(COL_X_MIN, COL_X_MAX, size=50)
        ys = rng.uniform(y0, y1, size=50)
        ds = [distance_to_nearest_edge(x, y, rects) for x, y in zip(xs, ys)]
        rec['null_med_d_to_ad'] = float(np.median(ds))
    else:
        rec['null_med_d_to_ad'] = float('nan')
    return rec


def write_per_trial(records):
    path = OUT_DIR / 'per_trial.csv'
    # Flatten: drop saccade_amps_20 into its own file
    keys = [k for k in records[0].keys() if k != 'saccade_amps_20']
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in records:
            w.writerow({k: r[k] for k in keys})


def write_saccade_profile(records):
    # Mean amplitude by ordinal 1..20 for (all / plain-top / ad-top)
    by_cohort = {
        'all': defaultdict(list),
        'plain_top': defaultdict(list),
        'ad_top': defaultdict(list),
    }
    for r in records:
        amps = r['saccade_amps_20']
        cohort = 'plain_top' if r['is_plain_top'] else 'ad_top'
        for i, a in enumerate(amps, start=1):
            by_cohort['all'][i].append(a)
            by_cohort[cohort][i].append(a)

    path = OUT_DIR / 'saccade_amplitude_profile.csv'
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['ordinal', 'cohort', 'n', 'mean_px', 'median_px'])
        for cohort, d in by_cohort.items():
            for i in sorted(d.keys()):
                arr = np.array(d[i])
                w.writerow([i, cohort, len(arr),
                            f'{arr.mean():.1f}', f'{np.median(arr):.1f}'])


def write_first_fix_distribution(records):
    path = OUT_DIR / 'first_fix_location.csv'
    rows = []
    # Overall and per cohort
    buckets = [
        ('all', lambda r: True),
        ('plain_top', lambda r: r['is_plain_top']),
        ('ad_top', lambda r: not r['is_plain_top']),
    ]
    for name, pred in buckets:
        subset = [r for r in records if pred(r)]
        n = len(subset)
        n_inside = sum(1 for r in subset if r['first_fix_inside_ad'])
        n_near = sum(1 for r in subset if r['first_fix_near_ad'])
        n_far = sum(1 for r in subset if r['first_fix_far_from_ad'])
        ds = [r['first_fix_d_to_ad'] for r in subset
              if math.isfinite(r['first_fix_d_to_ad'])]
        rows.append({
            'cohort': name,
            'n_trials': n,
            'pct_first_fix_inside_ad': 100.0 * n_inside / n if n else float('nan'),
            'pct_first_fix_within_50px': 100.0 * n_near / n if n else float('nan'),
            'pct_first_fix_beyond_200px': 100.0 * n_far / n if n else float('nan'),
            'median_d_to_ad_px': float(np.median(ds)) if ds else float('nan'),
        })
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return rows


def summarize_k(records, K: int):
    """Aggregate the per-trial K-partition into corpus-wide numbers."""
    def sub(cond):
        return [r for r in records if cond(r)]

    cohorts = [
        ('all', lambda r: True),
        ('plain_top', lambda r: r['is_plain_top']),
        ('ad_top', lambda r: not r['is_plain_top']),
    ]

    rows = []
    for name, pred in cohorts:
        subset = sub(pred)
        n = len(subset)
        if n == 0:
            continue
        total_s = sum(r[f'n_survey_fix_K{K}'] for r in subset)
        total_e = sum(r[f'n_eval_fix_K{K}'] for r in subset)
        total_s_on_ad = sum(r[f'n_survey_on_ad_K{K}'] for r in subset)
        total_e_on_ad = sum(r[f'n_eval_on_ad_K{K}'] for r in subset)

        # Fixation-weighted corpus rates
        p_s_fix = total_s_on_ad / total_s if total_s else float('nan')
        p_e_fix = total_e_on_ad / total_e if total_e else float('nan')

        # Trial-weighted (each trial contributes its own fraction)
        trial_ps = [r[f'n_survey_on_ad_K{K}'] / r[f'n_survey_fix_K{K}']
                    for r in subset if r[f'n_survey_fix_K{K}']]
        trial_pe = [r[f'n_eval_on_ad_K{K}'] / r[f'n_eval_fix_K{K}']
                    for r in subset if r[f'n_eval_fix_K{K}']]
        p_s_trial = float(np.mean(trial_ps)) if trial_ps else float('nan')
        p_e_trial = float(np.mean(trial_pe)) if trial_pe else float('nan')

        base_rate = float(np.mean([r['ad_area_frac'] for r in subset]))

        # Paired Wilcoxon-style test: per-trial p_survey − p_evaluate
        diffs = []
        for r in subset:
            if r[f'n_survey_fix_K{K}'] and r[f'n_eval_fix_K{K}']:
                a = r[f'n_survey_on_ad_K{K}'] / r[f'n_survey_fix_K{K}']
                b = r[f'n_eval_on_ad_K{K}'] / r[f'n_eval_fix_K{K}']
                diffs.append(a - b)
        diffs_arr = np.array(diffs)
        mean_diff = float(diffs_arr.mean()) if len(diffs_arr) else float('nan')
        frac_pos = float((diffs_arr > 0).mean()) if len(diffs_arr) else float('nan')

        # Distance-to-ad (median of per-trial medians)
        med_d_s = float(np.nanmedian([r[f'med_d_survey_K{K}'] for r in subset]))
        med_d_e = float(np.nanmedian([r[f'med_d_eval_K{K}'] for r in subset]))

        # Survey duration
        sdur = [r[f'survey_ms_K{K}'] for r in subset
                if math.isfinite(r.get(f'survey_ms_K{K}', float('nan')))]
        med_sdur = float(np.median(sdur)) if sdur else float('nan')

        rows.append({
            'cohort': name,
            'K': K,
            'n_trials': n,
            'base_rate_ad_area': base_rate,
            'p_ad_survey_fix_weighted': p_s_fix,
            'p_ad_eval_fix_weighted': p_e_fix,
            'ratio_fix_s_over_e': (p_s_fix / p_e_fix) if p_e_fix else float('nan'),
            'ratio_survey_over_base': (p_s_fix / base_rate) if base_rate else float('nan'),
            'p_ad_survey_trial_mean': p_s_trial,
            'p_ad_eval_trial_mean': p_e_trial,
            'mean_trial_diff_s_minus_e': mean_diff,
            'frac_trials_survey_gt_eval': frac_pos,
            'median_dist_to_ad_survey_px': med_d_s,
            'median_dist_to_ad_eval_px': med_d_e,
            'median_survey_ms': med_sdur,
        })
    return rows


def write_summary_csv(path: Path, rows: list[dict]):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v)
                        for k, v in r.items()})


def write_ad_count_vs_survey(records):
    path = OUT_DIR / 'ad_count_vs_survey_len.csv'
    rows = []
    for r in records:
        rows.append({
            'tid': r['tid'],
            'n_total_ads': r['n_total_ads'],
            'n_ddtop': r['n_ddtop'],
            'n_native': r['n_native'],
            'is_plain_top': int(r['is_plain_top']),
            'survey_ms_K5': r.get('survey_ms_K5', ''),
            'n_col_fix': r['n_col_fix'],
        })
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Spearman ρ: total_ads vs survey_ms_K5
    arr = [(r['n_total_ads'], r['survey_ms_K5'])
           for r in records if math.isfinite(r.get('survey_ms_K5', float('nan')))]
    if len(arr) >= 5:
        xs = np.array([a[0] for a in arr], dtype=float)
        ys = np.array([a[1] for a in arr], dtype=float)
        # Spearman via scipy if available; manual otherwise
        try:
            from scipy.stats import spearmanr
            rho, p = spearmanr(xs, ys)
        except Exception:
            rx = xs.argsort().argsort().astype(float)
            ry = ys.argsort().argsort().astype(float)
            rho = float(np.corrcoef(rx, ry)[0, 1])
            p = float('nan')
        return {'rho_total_ads_vs_survey_ms_K5': float(rho),
                'p': float(p) if p == p else None,
                'n': len(arr)}
    return {}


def main():
    t0 = time.time()
    tids = get_trial_ids()
    print(f'[survey_vs_ads] processing {len(tids)} trials...', flush=True)
    records = []
    skipped = 0
    for i, tid in enumerate(tids):
        try:
            rec = compute_trial_record(tid)
        except Exception as e:
            skipped += 1
            continue
        if rec is None:
            skipped += 1
            continue
        records.append(rec)
        if (i + 1) % 500 == 0:
            dt = time.time() - t0
            print(f'  {i + 1}/{len(tids)}  ({dt:.1f}s)', flush=True)
    print(f'[survey_vs_ads] {len(records)} records, {skipped} skipped, '
          f'{time.time() - t0:.1f}s', flush=True)

    # Write per-trial
    write_per_trial(records)
    write_saccade_profile(records)
    first_fix_rows = write_first_fix_distribution(records)

    # Per-K summaries
    all_summary_rows = []
    for K in K_VALUES:
        rows = summarize_k(records, K)
        write_summary_csv(OUT_DIR / f'summary_k{K}.csv', rows)
        all_summary_rows.extend(rows)

    # Ad count vs survey duration
    ad_survey = write_ad_count_vs_survey(records)

    # Top-line JSON
    def row_find(rows, cohort, K):
        for r in rows:
            if r['cohort'] == cohort and r['K'] == K:
                return r
        return None

    top = {
        'n_trials_analyzed': len(records),
        'n_plain_top': sum(1 for r in records if r['is_plain_top']),
        'n_ad_top': sum(1 for r in records if not r['is_plain_top']),
        'median_ad_area_frac_all': float(np.median([r['ad_area_frac'] for r in records])),
        'iqr_ad_area_frac_all': [
            float(np.percentile([r['ad_area_frac'] for r in records], 25)),
            float(np.percentile([r['ad_area_frac'] for r in records], 75)),
        ],
        'median_ad_area_frac_plain_top': float(np.median(
            [r['ad_area_frac'] for r in records if r['is_plain_top']])),
        'median_ad_area_frac_ad_top': float(np.median(
            [r['ad_area_frac'] for r in records if not r['is_plain_top']])),
        'K5_all': row_find(all_summary_rows, 'all', 5),
        'K5_ad_top': row_find(all_summary_rows, 'ad_top', 5),
        'K5_plain_top': row_find(all_summary_rows, 'plain_top', 5),
        'K3_all': row_find(all_summary_rows, 'all', 3),
        'K7_all': row_find(all_summary_rows, 'all', 7),
        'first_fix': first_fix_rows,
        'ad_count_vs_survey_ms': ad_survey,
    }
    with open(OUT_DIR / 'summary.json', 'w') as f:
        json.dump(top, f, indent=2, default=str)

    print(f'[survey_vs_ads] wrote outputs to {OUT_DIR}')
    # Brief stdout print
    print(json.dumps({
        'n': top['n_trials_analyzed'],
        'median_ad_area_frac': top['median_ad_area_frac_all'],
        'K5_all_p_survey_fix': top['K5_all']['p_ad_survey_fix_weighted'],
        'K5_all_p_eval_fix': top['K5_all']['p_ad_eval_fix_weighted'],
        'K5_all_ratio_s_over_e': top['K5_all']['ratio_fix_s_over_e'],
        'K5_all_ratio_s_over_base': top['K5_all']['ratio_survey_over_base'],
    }, indent=2, default=str))


if __name__ == '__main__':
    main()
