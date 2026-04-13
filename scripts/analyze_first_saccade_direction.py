#!/usr/bin/env python
"""First-saccade direction analysis — Survey follow-up #1.

Per the 2026-04-12 survey-phase memo (§8), this script tests whether the
first saccade (fixation 0 -> fixation 1) shows a direction bias toward
ad rectangles on ad_top trials, which would support active stimulus-driven
ad detection. If Survey is gist formation, the first saccade should have
no systematic ad-directed bias beyond what chance and page geometry imply.

Metrics per trial:
    theta0_deg    angle of first-saccade vector (0 = right, 90 = down)
    r0_px         magnitude of first-saccade vector
    theta_ad_deg  angle from fix 0 to nearest point on nearest ad rect
                  (0 if fix 0 is inside an ad)
    d_ad_px       Euclidean distance from fix 0 to the ad target point
    angdiff_deg   smallest absolute angle between theta0 and theta_ad

Outputs under scripts/output/first_saccade_direction/:
    per_trial.csv
    hist_theta0_bins.csv
    summary.json
    bootstrap_angdiff_ad_top.csv
    magnitude_summary.csv
    ddtop_strata.csv

Run:
    .venv/bin/python scripts/analyze_first_saccade_direction.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    load_fixations,
    _load_ad_regions,
    _rect_in_result_column,
)

OUT_DIR = ROOT / 'scripts' / 'output' / 'first_saccade_direction'
OUT_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT = ROOT / 'scripts' / 'output' / 'serp_structure_survey' / 'trial_snapshot.csv'

# Result column bounds
COL_X_MIN = 162
COL_X_MAX = 702

# Test D stratification: dd_top ads in AdSERP always sit at y ≈ 158-258 —
# they never move below the fold, so an "upper vs lower" Y split is
# degenerate. The meaningful stratification is the *depth* of the dd_top
# ad block: `first_org_abs` from the trial snapshot tells us the abs rank
# of the first organic result, which equals the number of top-ads above
# the first organic (1, 2, or 3). We split ad_top into:
#   shallow_top : first_org_abs == 1  (single top ad)
#   deep_top    : first_org_abs >= 2  (two or three top ads)
# This maps onto the task's "upper region vs lower region" spec by
# proxying "how far down the top-ad block extends."

RNG = np.random.default_rng(20260412)
N_BOOT = 2000


# ── Geometry helpers ──────────────────────────────────────────────────────

def filter_in_col_rects(ad_regions: dict) -> list[tuple[float, float, float, float, str]]:
    """Return [(x, y, w, h, etype), ...] for dd_top + native_ad rects in the
    result column. Matches the convention in analyze_survey_vs_ads.py —
    same clipping, same etype filter.
    """
    out = []
    for etype, ers in ad_regions.items():
        if etype not in ('dd_top', 'native_ad'):
            continue
        for (rx, ry, rw, rh) in ers:
            if not _rect_in_result_column(rx, rw):
                continue
            cx0 = max(rx, COL_X_MIN)
            cx1 = min(rx + rw, COL_X_MAX)
            if cx1 <= cx0:
                continue
            out.append((cx0, ry, cx1 - cx0, rh, etype))
    return out


def closest_point_on_rect(px: float, py: float,
                          rx: float, ry: float, rw: float, rh: float):
    """Return (cx, cy, inside) where (cx, cy) is the closest point on the
    rect to (px, py), and inside is True if (px, py) is inside the rect.
    If inside, we return the closest point on the rect *edge* (so that the
    angle-to-nearest-edge is defined per the task spec).
    """
    x0, x1 = rx, rx + rw
    y0, y1 = ry, ry + rh
    inside = (x0 <= px <= x1) and (y0 <= py <= y1)
    if not inside:
        cx = min(max(px, x0), x1)
        cy = min(max(py, y0), y1)
        return cx, cy, False
    # Inside: closest edge point
    dx_left = px - x0
    dx_right = x1 - px
    dy_top = py - y0
    dy_bot = y1 - py
    m = min(dx_left, dx_right, dy_top, dy_bot)
    if m == dx_left:
        return x0, py, True
    if m == dx_right:
        return x1, py, True
    if m == dy_top:
        return px, y0, True
    return px, y1, True


def nearest_ad_target(px: float, py: float, rects):
    """Find the nearest rect to (px, py) and return (tx, ty, d, inside, etype).
    When fix 0 is inside a rect, target is the closest edge of *that* rect.
    When outside, target is the closest-point on the closest rect.
    """
    # Prefer containing rect if any
    best = None
    for (rx, ry, rw, rh, et) in rects:
        cx, cy, inside = closest_point_on_rect(px, py, rx, ry, rw, rh)
        if inside:
            d = math.hypot(px - cx, py - cy)
            return cx, cy, d, True, et
        d = math.hypot(px - cx, py - cy)
        if best is None or d < best[2]:
            best = (cx, cy, d, False, et)
    return best if best is not None else (None, None, None, None, None)


def angle_deg(dx: float, dy: float) -> float:
    """Return angle in degrees in [0, 360). 0 = right (+x), 90 = down (+y).
    Page coordinates (y grows downward), so we use math.atan2(dy, dx) directly.
    """
    a = math.degrees(math.atan2(dy, dx))
    if a < 0:
        a += 360.0
    return a


def smallest_angle_diff(a: float, b: float) -> float:
    """Smallest absolute angular distance in degrees, in [0, 180]."""
    d = abs(a - b) % 360.0
    if d > 180.0:
        d = 360.0 - d
    return d


# ── Cohort loading ────────────────────────────────────────────────────────

def load_cohorts():
    rows = []
    with open(SNAPSHOT) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    cohort_rows = load_cohorts()
    print(f'[info] loaded {len(cohort_rows)} trials from snapshot')

    per_trial = []
    skipped = 0
    missing_ad = 0
    no_fix = 0

    for r in cohort_rows:
        tid = r['tid']
        plain_top = r['plain_top'] == '1'
        n_ddtop = int(r['n_ddtop']) if r['n_ddtop'] else 0
        n_native = int(r['n_native']) if r['n_native'] else 0
        try:
            first_org_abs = int(r['first_org_abs']) if r['first_org_abs'] else 0
        except ValueError:
            first_org_abs = 0

        fix = load_fixations(tid)
        if len(fix) < 2:
            skipped += 1
            no_fix += 1
            continue
        f0 = fix[0]
        f1 = fix[1]
        dx = f1['x'] - f0['x']
        dy = f1['y'] - f0['y']
        r0 = math.hypot(dx, dy)
        if r0 < 1e-6:
            skipped += 1
            continue
        theta0 = angle_deg(dx, dy)

        ad_regions = _load_ad_regions(tid)
        rects = filter_in_col_rects(ad_regions)
        if not rects:
            missing_ad += 1
            # Still record fix-direction data so plain_top trials with no
            # ads show up, but the ad metrics will be None.
            per_trial.append({
                'tid': tid,
                'pid': r['pid'],
                'cohort': 'plain_top' if plain_top else 'ad_top',
                'n_ddtop': n_ddtop,
                'n_native': n_native,
                'fix0_x': f0['x'], 'fix0_y': f0['y'],
                'fix1_x': f1['x'], 'fix1_y': f1['y'],
                'r0_px': r0,
                'theta0_deg': theta0,
                'theta_ad_deg': '',
                'd_ad_px': '',
                'angdiff_deg': '',
                'fix0_inside_ad': '',
                'ad_etype': '',
                'ddtop_top_y': '',
                'ddtop_stratum': 'shallow_top' if first_org_abs == 1
                                  else ('deep_top' if first_org_abs >= 2 else ''),
            })
            continue

        tx, ty, d_ad, inside, etype = nearest_ad_target(f0['x'], f0['y'], rects)
        if tx is None:
            skipped += 1
            continue

        if d_ad < 1e-6:
            # Fix 0 is exactly on the edge (or the rect is degenerate).
            # Angle-to-ad is undefined; skip.
            theta_ad = ''
            angdiff = ''
        else:
            theta_ad = angle_deg(tx - f0['x'], ty - f0['y'])
            angdiff = smallest_angle_diff(theta0, theta_ad)

        # dd_top block depth stratum (for Test D).
        ddtop_top_y = ''
        ddtop_rects = [rr for rr in rects if rr[4] == 'dd_top']
        if ddtop_rects:
            ddtop_rects.sort(key=lambda rr: rr[1])
            ddtop_top_y = ddtop_rects[0][1]
        if first_org_abs == 1:
            ddtop_stratum = 'shallow_top'
        elif first_org_abs >= 2:
            ddtop_stratum = 'deep_top'
        else:
            ddtop_stratum = ''

        per_trial.append({
            'tid': tid,
            'pid': r['pid'],
            'cohort': 'plain_top' if plain_top else 'ad_top',
            'n_ddtop': n_ddtop,
            'n_native': n_native,
            'fix0_x': f0['x'], 'fix0_y': f0['y'],
            'fix1_x': f1['x'], 'fix1_y': f1['y'],
            'r0_px': r0,
            'theta0_deg': theta0,
            'theta_ad_deg': theta_ad,
            'd_ad_px': d_ad,
            'angdiff_deg': angdiff,
            'fix0_inside_ad': 1 if inside else 0,
            'ad_etype': etype,
            'ddtop_top_y': ddtop_top_y,
            'ddtop_stratum': ddtop_stratum,
        })

    print(f'[info] per_trial rows: {len(per_trial)}  skipped: {skipped}  '
          f'missing_ad_json: {missing_ad}  <2 fix: {no_fix}')

    # Write per_trial.csv
    with open(OUT_DIR / 'per_trial.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(per_trial[0].keys()))
        w.writeheader()
        w.writerows(per_trial)

    # ── Test A: theta0 distribution ────────────────────────────────────
    bins = np.arange(0, 361, 30)
    hist_rows = []
    for cohort in ('plain_top', 'ad_top'):
        thetas = np.array([p['theta0_deg'] for p in per_trial
                           if p['cohort'] == cohort], dtype=float)
        hist, _ = np.histogram(thetas, bins=bins)
        n = len(thetas)
        for i, edge in enumerate(bins[:-1]):
            hist_rows.append({
                'cohort': cohort,
                'bin_low': int(edge),
                'bin_high': int(bins[i + 1]),
                'n': int(hist[i]),
                'frac': hist[i] / n if n else 0.0,
            })
    with open(OUT_DIR / 'hist_theta0_bins.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['cohort', 'bin_low', 'bin_high', 'n', 'frac'])
        w.writeheader()
        w.writerows(hist_rows)

    # Circular summary (mean, mode bin) per cohort
    circ_summary = {}
    for cohort in ('plain_top', 'ad_top'):
        thetas = np.array([p['theta0_deg'] for p in per_trial
                           if p['cohort'] == cohort], dtype=float)
        if len(thetas) == 0:
            continue
        rads = np.deg2rad(thetas)
        cbar = np.mean(np.cos(rads))
        sbar = np.mean(np.sin(rads))
        mean_ang = (math.degrees(math.atan2(sbar, cbar)) + 360) % 360
        R = math.hypot(cbar, sbar)  # resultant length (0 = uniform, 1 = peaked)
        # Mode bin
        hist, _ = np.histogram(thetas, bins=bins)
        mode_bin = int(bins[np.argmax(hist)])
        # Down fraction: theta in (60, 120]
        down_frac = float(np.mean((thetas > 60) & (thetas <= 120)))
        circ_summary[cohort] = {
            'n': int(len(thetas)),
            'mean_theta_deg': mean_ang,
            'resultant_R': R,
            'mode_bin_low': mode_bin,
            'mode_bin_count': int(hist.max()),
            'down_frac': down_frac,
        }

    # ── Test B: angdiff bootstrap on ad_top ─────────────────────────────
    ad_rows = [p for p in per_trial if p['cohort'] == 'ad_top'
               and p['angdiff_deg'] != '']
    observed_theta_ad = np.array([p['theta_ad_deg'] for p in ad_rows], dtype=float)
    observed_theta0 = np.array([p['theta0_deg'] for p in ad_rows], dtype=float)
    observed_diffs = np.array([
        smallest_angle_diff(t0, ta)
        for t0, ta in zip(observed_theta0, observed_theta_ad)
    ])
    observed_median = float(np.median(observed_diffs))
    observed_mean = float(np.mean(observed_diffs))

    # Null: shuffle theta0 across trials in the ad_top cohort, preserving
    # the theta_ad distribution (which reflects geometry of where fix 0
    # sits relative to the ad rect on each trial). Random pairing breaks
    # any systematic first-saccade direction.
    null_medians = np.zeros(N_BOOT)
    null_means = np.zeros(N_BOOT)
    n_ad = len(observed_diffs)
    for b in range(N_BOOT):
        shuffled = RNG.permutation(observed_theta0)
        diffs = np.abs(shuffled - observed_theta_ad) % 360.0
        diffs = np.where(diffs > 180, 360 - diffs, diffs)
        null_medians[b] = np.median(diffs)
        null_means[b] = np.mean(diffs)

    null_med_mean = float(np.mean(null_medians))
    null_med_ci_lo = float(np.quantile(null_medians, 0.025))
    null_med_ci_hi = float(np.quantile(null_medians, 0.975))
    # One-sided p: P(null <= observed)
    p_one_sided = float(np.mean(null_medians <= observed_median))

    with open(OUT_DIR / 'bootstrap_angdiff_ad_top.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['stat', 'value'])
        w.writerow(['n_trials', n_ad])
        w.writerow(['observed_median_angdiff_deg', observed_median])
        w.writerow(['observed_mean_angdiff_deg', observed_mean])
        w.writerow(['null_median_mean', null_med_mean])
        w.writerow(['null_median_ci_lo', null_med_ci_lo])
        w.writerow(['null_median_ci_hi', null_med_ci_hi])
        w.writerow(['p_one_sided_obs_le_null', p_one_sided])
        w.writerow(['n_boot', N_BOOT])

    # Split ad_top by whether fix 0 is already inside an ad rect. This is
    # critical because the geometry of "angle to nearest edge" flips: when
    # fix 0 is inside an ad, the nearest-edge angle points to an edge, and
    # a saccade that "stays in the ad" would point toward the far edge
    # (rarely), while a saccade that "escapes" would point toward the near
    # edge. When fix 0 is outside, ad-directed means aimed at the rect.
    inside_rows = [p for p in ad_rows if p['fix0_inside_ad'] == 1]
    outside_rows = [p for p in ad_rows if p['fix0_inside_ad'] == 0]
    inside_median_angdiff = float(np.median([p['angdiff_deg'] for p in inside_rows])) if inside_rows else None
    outside_median_angdiff = float(np.median([p['angdiff_deg'] for p in outside_rows])) if outside_rows else None

    # Null per subgroup (shuffle theta0 within the subgroup)
    def boot_null(rows_list):
        if not rows_list:
            return None, None, None
        t0 = np.array([p['theta0_deg'] for p in rows_list], dtype=float)
        ta = np.array([p['theta_ad_deg'] for p in rows_list], dtype=float)
        obs = np.median([smallest_angle_diff(a, b) for a, b in zip(t0, ta)])
        nulls = np.zeros(N_BOOT)
        for b in range(N_BOOT):
            shuf = RNG.permutation(t0)
            d = np.abs(shuf - ta) % 360.0
            d = np.where(d > 180, 360 - d, d)
            nulls[b] = np.median(d)
        p = float(np.mean(nulls <= obs))
        return float(obs), float(np.mean(nulls)), p

    inside_obs, inside_null, inside_p = boot_null(inside_rows)
    outside_obs, outside_null, outside_p = boot_null(outside_rows)

    # Plain_top as a control: compare observed angdiff distributions
    plain_ad_rows = [p for p in per_trial if p['cohort'] == 'plain_top'
                     and p['angdiff_deg'] != '']
    if plain_ad_rows:
        plain_diffs = np.array([p['angdiff_deg'] for p in plain_ad_rows], dtype=float)
        plain_median = float(np.median(plain_diffs))
        plain_mean = float(np.mean(plain_diffs))
    else:
        plain_median = None
        plain_mean = None

    # ── Test C: magnitude summary ───────────────────────────────────────
    mag_rows = []
    for cohort in ('plain_top', 'ad_top'):
        rs = np.array([p['r0_px'] for p in per_trial if p['cohort'] == cohort],
                      dtype=float)
        mag_rows.append({
            'cohort': cohort,
            'n': len(rs),
            'mean_r0_px': float(np.mean(rs)),
            'median_r0_px': float(np.median(rs)),
            'q25_r0_px': float(np.quantile(rs, 0.25)),
            'q75_r0_px': float(np.quantile(rs, 0.75)),
        })
    with open(OUT_DIR / 'magnitude_summary.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(mag_rows[0].keys()))
        w.writeheader()
        w.writerows(mag_rows)

    # Mann-Whitney style: use a bootstrap difference of medians
    plain_rs = np.array([p['r0_px'] for p in per_trial
                         if p['cohort'] == 'plain_top'], dtype=float)
    ad_rs = np.array([p['r0_px'] for p in per_trial
                      if p['cohort'] == 'ad_top'], dtype=float)
    obs_diff_med = float(np.median(plain_rs) - np.median(ad_rs))
    pooled = np.concatenate([plain_rs, ad_rs])
    nP = len(plain_rs)
    boot_diffs = np.zeros(1000)
    for b in range(1000):
        perm = RNG.permutation(pooled)
        boot_diffs[b] = np.median(perm[:nP]) - np.median(perm[nP:])
    p_perm = float(np.mean(np.abs(boot_diffs) >= abs(obs_diff_med)))

    # ── Test D: dd_top block depth stratification ───────────────────────
    ddtop_rows = [p for p in per_trial if p['cohort'] == 'ad_top'
                  and p['ddtop_stratum'] != '']
    strata_rows = []
    for stratum in ('shallow_top', 'deep_top'):
        sel = [p for p in ddtop_rows if p['ddtop_stratum'] == stratum]
        if not sel:
            continue
        thetas = np.array([p['theta0_deg'] for p in sel], dtype=float)
        rads = np.deg2rad(thetas)
        cbar = np.mean(np.cos(rads))
        sbar = np.mean(np.sin(rads))
        mean_ang = (math.degrees(math.atan2(sbar, cbar)) + 360) % 360
        down_frac = float(np.mean((thetas > 60) & (thetas <= 120)))
        ang_sel = [p for p in sel if p['angdiff_deg'] != '']
        if ang_sel:
            med_angdiff = float(np.median(
                [p['angdiff_deg'] for p in ang_sel]))
        else:
            med_angdiff = None
        strata_rows.append({
            'stratum': stratum,
            'n': len(sel),
            'mean_theta_deg': mean_ang,
            'down_frac': down_frac,
            'median_angdiff_deg': med_angdiff,
            'median_r0_px': float(np.median(
                [p['r0_px'] for p in sel])),
        })
    with open(OUT_DIR / 'ddtop_strata.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(strata_rows[0].keys()))
        w.writeheader()
        w.writerows(strata_rows)

    # ── summary.json ────────────────────────────────────────────────────
    summary = {
        'n_trials_processed': len(per_trial),
        'n_skipped': skipped,
        'n_missing_ad_json': missing_ad,
        'n_less_than_two_fix': no_fix,
        'circ_summary': circ_summary,
        'test_b': {
            'n_ad_top_with_angdiff': n_ad,
            'observed_median_angdiff_deg': observed_median,
            'observed_mean_angdiff_deg': observed_mean,
            'null_median_mean': null_med_mean,
            'null_median_ci_lo': null_med_ci_lo,
            'null_median_ci_hi': null_med_ci_hi,
            'p_one_sided_obs_le_null': p_one_sided,
            'n_boot': N_BOOT,
            'plain_top_control_median_angdiff_deg': plain_median,
            'plain_top_control_mean_angdiff_deg': plain_mean,
            'ad_top_inside_rect': {
                'n': len(inside_rows),
                'observed_median_angdiff_deg': inside_obs,
                'null_median_mean': inside_null,
                'p_one_sided_obs_le_null': inside_p,
            },
            'ad_top_outside_rect': {
                'n': len(outside_rows),
                'observed_median_angdiff_deg': outside_obs,
                'null_median_mean': outside_null,
                'p_one_sided_obs_le_null': outside_p,
            },
        },
        'test_c': {
            'plain_top_median_r0_px': float(np.median(plain_rs)),
            'ad_top_median_r0_px': float(np.median(ad_rs)),
            'diff_median_px': obs_diff_med,
            'perm_p_two_sided': p_perm,
        },
        'test_d': strata_rows,
        'runtime_s': time.time() - t_start,
    }
    with open(OUT_DIR / 'summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    # ── Console dump ────────────────────────────────────────────────────
    print()
    print('=' * 60)
    print('TEST A — theta0 circular summary')
    for cohort, s in circ_summary.items():
        print(f'  {cohort:10s} n={s["n"]:5d}  mean={s["mean_theta_deg"]:6.1f}  '
              f'R={s["resultant_R"]:.3f}  mode_bin={s["mode_bin_low"]}-'
              f'{s["mode_bin_low"]+30}  down_frac={s["down_frac"]:.3f}')
    print()
    print('TEST B — angdiff vs nearest ad (ad_top cohort)')
    print(f'  n_ad_top = {n_ad}')
    print(f'  observed median angdiff = {observed_median:.2f} deg')
    print(f'  null median (shuffle)   = {null_med_mean:.2f} deg '
          f'[{null_med_ci_lo:.2f}, {null_med_ci_hi:.2f}]')
    print(f'  p(null <= observed)     = {p_one_sided:.3f}')
    if plain_median is not None:
        print(f'  plain_top control median angdiff = {plain_median:.2f} deg')
    print(f'  ad_top | fix0 INSIDE  rect n={len(inside_rows):4d}  '
          f'obs={inside_obs:.2f}  null={inside_null:.2f}  p={inside_p:.3f}')
    print(f'  ad_top | fix0 OUTSIDE rect n={len(outside_rows):4d}  '
          f'obs={outside_obs:.2f}  null={outside_null:.2f}  p={outside_p:.3f}')
    print()
    print('TEST C — first-saccade magnitude')
    for m in mag_rows:
        print(f'  {m["cohort"]:10s} n={m["n"]:5d}  median={m["median_r0_px"]:6.1f}  '
              f'mean={m["mean_r0_px"]:6.1f}')
    print(f'  plain_top − ad_top median diff = {obs_diff_med:+.1f} px  '
          f'perm p = {p_perm:.3f}')
    print()
    print('TEST D — dd_top block depth (shallow=1 ad, deep=2+ ads)')
    for s in strata_rows:
        print(f'  {s["stratum"]:14s} n={s["n"]:5d}  mean_theta={s["mean_theta_deg"]:6.1f}  '
              f'down_frac={s["down_frac"]:.3f}  '
              f'median_angdiff={s["median_angdiff_deg"]}  '
              f'median_r0={s["median_r0_px"]:.1f}')
    print()
    print(f'[done] runtime = {time.time() - t_start:.1f}s')


if __name__ == '__main__':
    main()
