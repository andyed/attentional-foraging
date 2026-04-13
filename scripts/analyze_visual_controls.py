#!/usr/bin/env python
"""Visually-matched non-ad control for Survey-phase capture analysis.

Follow-up to scripts/analyze_survey_vs_ads.py, which found Survey
fixations over-index on dd_top ads by 2.45x over the uniform baseline
on ad-top trials. Open question: is this a generic visual-salience
effect (any visually-dense element captures early gaze) or something
ad-specific?

This script implements approach (c) from the task brief: use dd_right
(right-rail ads) as a visually salient control that is *spatially
segregated* from the reading flow. Right-rail ads share the "ad
branding / visual density" attributes of dd_top ads but sit in a
separate column at x in [802, 1023] (outside the result column
[162, 702]). If dd_right captures Survey gaze at rates similar to
dd_top, the effect is "visually salient element anywhere on page";
if dd_right is at-chance relative to its own base rate, then the
dd_top capture is in-column / flow-specific.

Approach (c) was chosen because:
  - Data is immediately available (`ad-boundary-data/<tid>.json`
    carries `dd_right` directly; `_load_ad_regions` filters it out
    but we reload the raw JSON).
  - dd_right matches dd_top on ad-branding, image density, and
    visual-layout properties. It differs on spatial location only.
  - Knowledge panels, shopping cards, etc. have no ground-truth
    rectangles in this corpus, so approaches (a) and (b) would be
    brittle proxies at best.

Key test:
  ratio_survey_over_base_ddtop  vs  ratio_survey_over_base_ddright
  (on the matched cohort that has BOTH present; and separately on
  cohorts with only one).

Outputs:
    scripts/output/visual_controls/
      per_trial.csv      — one row per trial with dd_top / dd_right stats
      summary.csv        — cohort summaries (all / both / only_ddtop / only_ddright)
      summary.json       — top-line numbers for memo
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    get_trial_ids,
    get_trial_meta,
    load_fixations,
    _rect_in_result_column,
)

AD_DIR = ROOT / 'AdSERP' / 'data' / 'ad-boundary-data'
OUT_DIR = ROOT / 'scripts' / 'output' / 'visual_controls'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Result column (where dd_top / native_ad live)
COL_X_MIN = 162
COL_X_MAX = 702

# Right-rail column (where dd_right lives — observed x in [802, 1023])
# Derived from inspection: dd_right.location.x = 802, width median 221
# (max 411 when there are wide creatives).
RIGHT_X_MIN = 702  # use gap between result column and right rail as left edge
RIGHT_X_MAX = 1100  # generous right edge, past observed w=411 extent

# Viewport (screen) typical width; fixations can go wider in doc-space
# but for area-fraction computations we use the page width covered by
# rects + fixations.
VIEWPORT_X_MAX = 1280  # Tobii screen width typical

K_SURVEY = 5


def load_raw_ad_regions(trial_id: str) -> dict:
    """Load raw boundary JSON including dd_right."""
    path = AD_DIR / f'{trial_id}.json'
    if not path.exists():
        return {}
    try:
        d = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for etype, elements in d.items():
        rects = []
        for el in elements:
            loc = el.get('location', {})
            size = el.get('size', {})
            rects.append((
                float(loc.get('x', 0)),
                float(loc.get('y', 0)),
                float(size.get('width', 0)),
                float(size.get('height', 0)),
            ))
        if rects:
            out[etype] = rects
    return out


def point_in_any_rect(px, py, rects) -> bool:
    for (rx, ry, rw, rh) in rects:
        if rx <= px <= rx + rw and ry <= py <= ry + rh:
            return True
    return False


def y_extent_of(rects: list) -> tuple[float, float]:
    ys = []
    for (rx, ry, rw, rh) in rects:
        ys.extend([ry, ry + rh])
    if not ys:
        return (float('inf'), float('-inf'))
    return (min(ys), max(ys))


def compute_trial_record(tid: str):
    fix = load_fixations(tid)
    if len(fix) < 2:
        return None
    doc_h, scr_h, _ts = get_trial_meta(tid)
    ad_regions = load_raw_ad_regions(tid)

    # In-column dd_top (keep native_ad separate; we use dd_top as the
    # primary in-column ad so the ratio is directly comparable to the
    # 2.45x number from §2 of survey-phase-vs-ads.md)
    ddtop_rects = [
        (rx, ry, rw, rh)
        for (rx, ry, rw, rh) in ad_regions.get('dd_top', [])
        if _rect_in_result_column(rx, rw)
    ]
    # Right-rail
    ddright_rects = list(ad_regions.get('dd_right', []))

    has_ddtop = len(ddtop_rects) > 0
    has_ddright = len(ddright_rects) > 0

    # Survey = first K fixations, no column filtering so the right rail
    # is reachable. (For dd_top base rate we restrict to the result
    # column; for dd_right base rate we restrict to the right-rail
    # column. Each rect is evaluated against fixations in its own
    # horizontal strip so the baselines match.)
    survey = fix[:K_SURVEY]
    evaluate = fix[K_SURVEY:]

    # dd_top: fixations inside the result column, then check rects
    def in_col(f):
        return COL_X_MIN <= f['x'] <= COL_X_MAX

    def in_right(f):
        return RIGHT_X_MIN <= f['x'] <= RIGHT_X_MAX

    survey_col = [f for f in survey if in_col(f)]
    eval_col = [f for f in evaluate if in_col(f)]
    survey_right = [f for f in survey if in_right(f)]
    eval_right = [f for f in evaluate if in_right(f)]

    # Base rates — area fraction of the *relevant strip*.
    # Compute the y-extent spanned by all fixations of the trial
    # (bounded by [0, doc_h]) so both strips use the same y-range.
    ys = [f['y'] for f in fix]
    y0 = max(0.0, min(ys))
    y1 = min(float(doc_h or 2642), max(ys))
    if y1 - y0 < 1:
        y1 = y0 + 1

    col_area = (COL_X_MAX - COL_X_MIN) * (y1 - y0)
    right_area = (RIGHT_X_MAX - RIGHT_X_MIN) * (y1 - y0)

    def rect_area_in_strip(rects, x_lo, x_hi):
        tot = 0.0
        for (rx, ry, rw, rh) in rects:
            ax0 = max(rx, x_lo)
            ax1 = min(rx + rw, x_hi)
            ay0 = max(ry, y0)
            ay1 = min(ry + rh, y1)
            if ax1 > ax0 and ay1 > ay0:
                tot += (ax1 - ax0) * (ay1 - ay0)
        return tot

    ddtop_area = rect_area_in_strip(ddtop_rects, COL_X_MIN, COL_X_MAX)
    ddright_area = rect_area_in_strip(ddright_rects, RIGHT_X_MIN, RIGHT_X_MAX)

    ddtop_base_rate = ddtop_area / col_area if col_area > 0 else float('nan')
    ddright_base_rate = ddright_area / right_area if right_area > 0 else float('nan')

    # On-rect counts (conditional on fixation being in the relevant strip)
    n_survey_on_ddtop = sum(1 for f in survey_col
                            if point_in_any_rect(f['x'], f['y'], ddtop_rects))
    n_eval_on_ddtop = sum(1 for f in eval_col
                          if point_in_any_rect(f['x'], f['y'], ddtop_rects))
    n_survey_on_ddright = sum(1 for f in survey_right
                              if point_in_any_rect(f['x'], f['y'], ddright_rects))
    n_eval_on_ddright = sum(1 for f in eval_right
                            if point_in_any_rect(f['x'], f['y'], ddright_rects))

    # Raw survey-fixation allocation across strips (viewport-wide), so
    # we can also answer "how much of Survey goes to each column".
    n_survey_viewport = len(survey)
    n_survey_in_col = len(survey_col)
    n_survey_in_right = len(survey_right)

    return {
        'tid': tid,
        'has_ddtop': int(has_ddtop),
        'has_ddright': int(has_ddright),
        'n_ddtop_rects': len(ddtop_rects),
        'n_ddright_rects': len(ddright_rects),
        'ddtop_area': ddtop_area,
        'ddright_area': ddright_area,
        'col_area': col_area,
        'right_area': right_area,
        'ddtop_base_rate': ddtop_base_rate,
        'ddright_base_rate': ddright_base_rate,
        'n_survey_viewport': n_survey_viewport,
        'n_survey_col': n_survey_in_col,
        'n_survey_right': n_survey_in_right,
        'n_eval_col': len(eval_col),
        'n_eval_right': len(eval_right),
        'n_survey_on_ddtop': n_survey_on_ddtop,
        'n_eval_on_ddtop': n_eval_on_ddtop,
        'n_survey_on_ddright': n_survey_on_ddright,
        'n_eval_on_ddright': n_eval_on_ddright,
        'y0': y0,
        'y1': y1,
    }


def summarize_cohort(records, name, pred):
    subset = [r for r in records if pred(r)]
    n = len(subset)
    if n == 0:
        return None

    # DD_TOP: fixation-weighted rates conditional on fixation being
    # inside the result column.
    tot_s_col = sum(r['n_survey_col'] for r in subset)
    tot_e_col = sum(r['n_eval_col'] for r in subset)
    tot_s_on_ddtop = sum(r['n_survey_on_ddtop'] for r in subset)
    tot_e_on_ddtop = sum(r['n_eval_on_ddtop'] for r in subset)
    p_s_ddtop = tot_s_on_ddtop / tot_s_col if tot_s_col else float('nan')
    p_e_ddtop = tot_e_on_ddtop / tot_e_col if tot_e_col else float('nan')
    base_ddtop = float(np.mean([r['ddtop_base_rate'] for r in subset
                                if math.isfinite(r['ddtop_base_rate'])]))

    # DD_RIGHT: fixation-weighted rates conditional on fixation being
    # inside the right-rail strip.
    tot_s_right = sum(r['n_survey_right'] for r in subset)
    tot_e_right = sum(r['n_eval_right'] for r in subset)
    tot_s_on_ddright = sum(r['n_survey_on_ddright'] for r in subset)
    tot_e_on_ddright = sum(r['n_eval_on_ddright'] for r in subset)
    p_s_ddright = tot_s_on_ddright / tot_s_right if tot_s_right else float('nan')
    p_e_ddright = tot_e_on_ddright / tot_e_right if tot_e_right else float('nan')
    base_ddright = float(np.mean([r['ddright_base_rate'] for r in subset
                                  if math.isfinite(r['ddright_base_rate'])]))

    # Viewport-weighted: fraction of Survey fixations that land on the
    # target rect, using the full Survey window as denominator (no
    # strip filter). This is the most direct "how much of Survey gets
    # captured" number.
    tot_s_viewport = sum(r['n_survey_viewport'] for r in subset)
    vw_s_ddtop = tot_s_on_ddtop / tot_s_viewport if tot_s_viewport else float('nan')
    vw_s_ddright = tot_s_on_ddright / tot_s_viewport if tot_s_viewport else float('nan')

    return {
        'cohort': name,
        'n_trials': n,
        # dd_top numbers
        'dd_top_n_trials_with_rect': sum(1 for r in subset if r['has_ddtop']),
        'dd_top_base_rate': base_ddtop,
        'dd_top_p_survey_col': p_s_ddtop,
        'dd_top_p_eval_col': p_e_ddtop,
        'dd_top_ratio_survey_over_base': (p_s_ddtop / base_ddtop)
            if base_ddtop else float('nan'),
        'dd_top_ratio_survey_over_eval': (p_s_ddtop / p_e_ddtop)
            if p_e_ddtop else float('nan'),
        'dd_top_vw_p_survey': vw_s_ddtop,
        'dd_top_tot_survey_col_fix': tot_s_col,
        'dd_top_tot_survey_on_rect': tot_s_on_ddtop,
        # dd_right numbers
        'dd_right_n_trials_with_rect': sum(1 for r in subset if r['has_ddright']),
        'dd_right_base_rate': base_ddright,
        'dd_right_p_survey_strip': p_s_ddright,
        'dd_right_p_eval_strip': p_e_ddright,
        'dd_right_ratio_survey_over_base': (p_s_ddright / base_ddright)
            if base_ddright else float('nan'),
        'dd_right_ratio_survey_over_eval': (p_s_ddright / p_e_ddright)
            if p_e_ddright else float('nan'),
        'dd_right_vw_p_survey': vw_s_ddright,
        'dd_right_tot_survey_strip_fix': tot_s_right,
        'dd_right_tot_survey_on_rect': tot_s_on_ddright,
        # Survey allocation
        'mean_n_survey_in_col': float(np.mean([r['n_survey_col'] for r in subset])),
        'mean_n_survey_in_right': float(np.mean([r['n_survey_right'] for r in subset])),
    }


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            out = {}
            for k, v in r.items():
                if isinstance(v, float):
                    out[k] = f'{v:.4f}'
                else:
                    out[k] = v
            w.writerow(out)


def main():
    t0 = time.time()
    tids = get_trial_ids()
    print(f'[visual_controls] processing {len(tids)} trials...', flush=True)
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
            print(f'  {i + 1}/{len(tids)} ({time.time() - t0:.1f}s)', flush=True)

    print(f'[visual_controls] {len(records)} records, {skipped} skipped '
          f'({time.time() - t0:.1f}s)', flush=True)

    # Per-trial CSV
    per_trial_path = OUT_DIR / 'per_trial.csv'
    keys = [k for k in records[0].keys()]
    with open(per_trial_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in records:
            w.writerow(r)

    # Cohort summaries
    cohorts = [
        ('all', lambda r: True),
        ('has_ddtop', lambda r: r['has_ddtop'] == 1),
        ('has_ddright', lambda r: r['has_ddright'] == 1),
        ('both_ddtop_ddright', lambda r: r['has_ddtop'] == 1 and r['has_ddright'] == 1),
        ('only_ddtop', lambda r: r['has_ddtop'] == 1 and r['has_ddright'] == 0),
        ('only_ddright', lambda r: r['has_ddtop'] == 0 and r['has_ddright'] == 1),
        ('neither', lambda r: r['has_ddtop'] == 0 and r['has_ddright'] == 0),
    ]
    summary_rows = []
    for name, pred in cohorts:
        row = summarize_cohort(records, name, pred)
        if row is not None:
            summary_rows.append(row)
    write_csv(OUT_DIR / 'summary.csv', summary_rows)

    # Top-line JSON
    top = {
        'n_trials_analyzed': len(records),
        'n_has_ddtop': sum(1 for r in records if r['has_ddtop']),
        'n_has_ddright': sum(1 for r in records if r['has_ddright']),
        'n_both': sum(1 for r in records
                      if r['has_ddtop'] and r['has_ddright']),
        'cohorts': summary_rows,
    }
    with open(OUT_DIR / 'summary.json', 'w') as f:
        json.dump(top, f, indent=2, default=str)

    print(f'[visual_controls] wrote outputs to {OUT_DIR}')
    # Print key ratios
    for r in summary_rows:
        print(f'  {r["cohort"]:<20} '
              f'dd_top S/base={r["dd_top_ratio_survey_over_base"]:.2f} '
              f'dd_right S/base={r["dd_right_ratio_survey_over_base"]:.2f} '
              f'ddright_n_with_rect={r["dd_right_n_trials_with_rect"]}')


if __name__ == '__main__':
    main()
