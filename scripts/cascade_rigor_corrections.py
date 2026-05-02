"""Compute the missing CIs + multiple-comparison corrections that the
2026-05-02 rigor audit flagged on the cascade artifacts.

Operates on existing JSONs in scripts/output/aoi-consumer-cascade/ and
re-derives the per-fixation samples by walking the data once. No new
analyses; just adds the rigor scaffolding for paper-prose use.

Outputs:
  scripts/output/aoi-consumer-cascade/rigor_corrections.json
  + stdout summary

Run:
  .venv/bin/python scripts/cascade_rigor_corrections.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

OUT_DIR = ROOT / 'scripts/output/aoi-consumer-cascade'
RNG = np.random.default_rng(2026)
N_BOOT = 2000  # bootstrap iterations for CIs


# ──────────────────────────────────────────────────────────────────────
# Block 1: Bonferroni / Holm / BH-FDR on the 14-metric will-return scan
# ──────────────────────────────────────────────────────────────────────

def correct_will_return_scan() -> dict:
    """Apply multiple-comparison corrections to the 14-metric scan."""
    scan = json.load(open(OUT_DIR / 'will_return_predictor_scan.json'))
    metrics = scan['metrics']
    pvals = np.array([m['p'] for m in metrics])
    m_count = len(pvals)

    # Bonferroni: alpha / m
    bonf_threshold_001 = 0.001 / m_count  # ≈ 7.1e-5
    bonf_threshold_01  = 0.01  / m_count  # ≈ 7.1e-4
    bonf_threshold_05  = 0.05  / m_count  # ≈ 3.6e-3
    bonf_p = np.minimum(pvals * m_count, 1.0)

    # Holm step-down
    order = np.argsort(pvals)
    holm_p = np.empty_like(pvals)
    running_max = 0.0
    for rank_idx, i in enumerate(order):
        adj = pvals[i] * (m_count - rank_idx)
        running_max = max(running_max, min(adj, 1.0))
        holm_p[i] = running_max

    # Benjamini-Hochberg FDR
    bh_p = np.empty_like(pvals)
    sorted_idx = np.argsort(pvals)
    sorted_p = pvals[sorted_idx]
    bh_sorted = np.empty_like(sorted_p)
    running_min = 1.0
    for k in reversed(range(m_count)):
        adj = sorted_p[k] * m_count / (k + 1)
        running_min = min(running_min, adj)
        bh_sorted[k] = running_min
    for i, idx in enumerate(sorted_idx):
        bh_p[idx] = bh_sorted[i]

    rows = []
    for i, m in enumerate(metrics):
        rows.append({
            'metric': m['metric'],
            'd': m['d'],
            'p_raw': float(pvals[i]),
            'p_bonferroni': float(bonf_p[i]),
            'p_holm': float(holm_p[i]),
            'p_bh_fdr': float(bh_p[i]),
            'survives_bonf_05': bool(pvals[i] < bonf_threshold_05),
            'survives_bonf_01': bool(pvals[i] < bonf_threshold_01),
            'survives_bonf_001': bool(pvals[i] < bonf_threshold_001),
            'n_wr': m['n_wr'], 'n_nr': m['n_nr'],
        })
    return {
        'k_metrics_tested': m_count,
        'bonferroni_thresholds': {
            'alpha_05': bonf_threshold_05,
            'alpha_01': bonf_threshold_01,
            'alpha_001': bonf_threshold_001,
        },
        'rows': rows,
    }


# ──────────────────────────────────────────────────────────────────────
# Block 2: Bootstrap CIs on Cohen's d for each will-return predictor
#          (re-derive from raw fixation-pupil + EVR labels)
# ──────────────────────────────────────────────────────────────────────

def cohens_d(a, b):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    b = np.asarray(b, float); b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def bootstrap_d_ci(wr_vals, nr_vals, n_boot=N_BOOT, alpha=0.05):
    wr = np.asarray(wr_vals, float); wr = wr[np.isfinite(wr)]
    nr = np.asarray(nr_vals, float); nr = nr[np.isfinite(nr)]
    if len(wr) < 30 or len(nr) < 30:
        return float('nan'), float('nan')
    ds = np.empty(n_boot)
    for b in range(n_boot):
        wr_b = RNG.choice(wr, size=len(wr), replace=True)
        nr_b = RNG.choice(nr, size=len(nr), replace=True)
        pooled = np.sqrt((wr_b.var(ddof=1) + nr_b.var(ddof=1)) / 2)
        ds[b] = (wr_b.mean() - nr_b.mean()) / pooled if pooled > 0 else 0.0
    lo, hi = np.percentile(ds, [100*alpha/2, 100*(1-alpha/2)])
    return float(lo), float(hi)


def bootstrap_median_diff_ci(wr_vals, nr_vals, n_boot=N_BOOT, alpha=0.05):
    """Hodges-Lehmann-style CI on the difference of medians."""
    wr = np.asarray(wr_vals, float); wr = wr[np.isfinite(wr)]
    nr = np.asarray(nr_vals, float); nr = nr[np.isfinite(nr)]
    if len(wr) < 30 or len(nr) < 30:
        return float('nan'), float('nan')
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        wr_b = RNG.choice(wr, size=len(wr), replace=True)
        nr_b = RNG.choice(nr, size=len(nr), replace=True)
        diffs[b] = float(np.median(wr_b) - np.median(nr_b))
    lo, hi = np.percentile(diffs, [100*alpha/2, 100*(1-alpha/2)])
    return float(lo), float(hi)


def rederive_will_return_with_cis():
    """Re-walk fixation-pupil to assemble per-(trial, position) records,
    then bootstrap CIs on d for each metric."""
    from data_loader import (  # noqa: E402
        DATA_DIR, load_fixations, organic_aoi_tops, assign_fixation_to_position,
    )
    FIX_PUPIL_DIR = DATA_DIR / 'fixation-pupil'
    EVR_PATH = DATA_DIR / 'encoding-vs-retrieval.json'
    LFHF_PATH = DATA_DIR / 'butterworth-lfhf-by-position-organic.json'
    RIPA2_PATH = DATA_DIR / 'ripa2-by-position-organic.json'

    print('  re-loading EVR + LF/HF + RIPA2', file=sys.stderr)
    evr = json.load(open(EVR_PATH))
    lfhf_data = json.load(open(LFHF_PATH))
    ripa2_data = json.load(open(RIPA2_PATH))

    print('  walking fixation-pupil for per-(trial, pos) records...', file=sys.stderr)
    records = []
    for tid, et in evr.items():
        fp_path = FIX_PUPIL_DIR / f'{tid}.json'
        if not fp_path.exists():
            continue
        fix_pupil = json.load(open(fp_path))
        fixations = load_fixations(tid)
        if not fixations or len(fix_pupil) != len(fixations):
            continue
        tops = organic_aoi_tops(tid)
        n_results = len(tops)
        if n_results == 0:
            continue
        wr_by_pos = {fp['pos']: fp.get('will_regress', False)
                     for fp in et.get('first_pass', [])}
        if not wr_by_pos:
            continue
        by_pos = defaultdict(list)
        high_water = -1
        for f, p in zip(fixations, fix_pupil):
            pos = assign_fixation_to_position(f['y'], tops, n_results)
            if pos is None or pos < 0 or pos >= n_results:
                continue
            if pos >= high_water:
                high_water = pos
                by_pos[int(pos)].append((f, p))
        lfhf_t = {pp['pos']: pp['lfhf'] for pp in lfhf_data.get(tid, {}).get('positions', [])
                  if pp.get('lfhf') is not None}
        ripa2_t = {pp['pos']: pp['ripa2'] for pp in ripa2_data.get(tid, {}).get('positions', [])
                   if pp.get('ripa2') is not None}
        for pos, fp_list in by_pos.items():
            if pos not in wr_by_pos:
                continue
            mean_pds = [p['mean_pd'] for _, p in fp_list if p.get('mean_pd') is not None]
            pd_changes = [p['pd_change'] for _, p in fp_list if p.get('pd_change') is not None]
            durations = [f['d'] for f, _ in fp_list]
            n_fix = len(fp_list)
            if n_fix < 2 or len(mean_pds) < 2:
                continue
            rec = {
                'wr': bool(wr_by_pos[pos]),
                'mean_pd_mean': float(np.mean(mean_pds)),
                'mean_pd_max': float(np.max(mean_pds)),
                'pd_change_mean': float(np.mean(pd_changes)) if pd_changes else float('nan'),
                'pd_change_max': float(np.max(pd_changes)) if pd_changes else float('nan'),
                'pd_change_min': float(np.min(pd_changes)) if pd_changes else float('nan'),
                'n_fix': float(n_fix),
                'mean_fix_duration': float(np.mean(durations)),
                'max_fix_duration': float(np.max(durations)),
                'sum_fix_duration': float(np.sum(durations)),
                'first_pd': float(mean_pds[0]),
                'last_pd': float(mean_pds[-1]),
                'pd_trajectory': float(mean_pds[-1] - mean_pds[0]),
                'lfhf_existing': lfhf_t.get(pos, float('nan')),
                'ripa2_existing': ripa2_t.get(pos, float('nan')),
            }
            records.append(rec)

    metrics = [
        'mean_pd_mean', 'mean_pd_max',
        'pd_change_mean', 'pd_change_max', 'pd_change_min',
        'n_fix',
        'mean_fix_duration', 'max_fix_duration', 'sum_fix_duration',
        'first_pd', 'last_pd', 'pd_trajectory',
        'lfhf_existing', 'ripa2_existing',
    ]

    print(f'  bootstrap CIs (n_boot={N_BOOT})...', file=sys.stderr)
    out = []
    for m in metrics:
        wr_vals = [r[m] for r in records if r['wr']]
        nr_vals = [r[m] for r in records if not r['wr']]
        d = cohens_d(wr_vals, nr_vals)
        d_lo, d_hi = bootstrap_d_ci(wr_vals, nr_vals)
        med_diff_lo, med_diff_hi = bootstrap_median_diff_ci(wr_vals, nr_vals)
        med_wr = float(np.median([v for v in wr_vals if np.isfinite(v)])) if wr_vals else float('nan')
        med_nr = float(np.median([v for v in nr_vals if np.isfinite(v)])) if nr_vals else float('nan')
        out.append({
            'metric': m,
            'd': float(d),
            'd_ci95': [d_lo, d_hi],
            'median_diff': float(med_wr - med_nr),
            'median_diff_ci95': [med_diff_lo, med_diff_hi],
            'median_wr': med_wr,
            'median_nr': med_nr,
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# Block 3: Two-proportion test + CI on dd_top (17.1%) vs organic (14.6%)
# ──────────────────────────────────────────────────────────────────────

def click_rate_comparisons():
    nb21_hybrid = json.load(open(OUT_DIR / 'nb21_loso_hybrid.json'))
    et = nb21_hybrid['etype_breakdown']
    pairs = [
        ('dd_top', 'organic'),
        ('dd_top', 'native_ad'),
        ('organic', 'native_ad'),
    ]
    out = []
    for a, b in pairs:
        n_a = et[a]['n']; k_a = et[a]['n_clicked']
        n_b = et[b]['n']; k_b = et[b]['n_clicked']
        p_a = k_a / n_a; p_b = k_b / n_b
        # Pooled two-proportion z-test
        p_pool = (k_a + k_b) / (n_a + n_b)
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
        z = (p_a - p_b) / se if se > 0 else 0.0
        p_two = 2 * (1 - stats.norm.cdf(abs(z)))
        # Wilson-ish CI on the difference (Newcombe method 10)
        # Per-arm Wilson CIs first
        def wilson(k, n, alpha=0.05):
            zc = stats.norm.ppf(1 - alpha/2)
            denom = 1 + zc*zc/n
            centre = (k + zc*zc/2) / n / denom
            half = zc * np.sqrt((k*(n-k)/n + zc*zc/4) / n) / n / denom
            return centre - half, centre + half
        lo_a, hi_a = wilson(k_a, n_a)
        lo_b, hi_b = wilson(k_b, n_b)
        # Newcombe 10 difference CI
        diff_lo = (p_a - p_b) - np.sqrt((p_a - lo_a)**2 + (hi_b - p_b)**2)
        diff_hi = (p_a - p_b) + np.sqrt((hi_a - p_a)**2 + (p_b - lo_b)**2)
        out.append({
            'pair': f'{a} − {b}',
            'p_a': float(p_a), 'n_a': n_a, 'p_b': float(p_b), 'n_b': n_b,
            'diff_pp': float(100 * (p_a - p_b)),
            'diff_ci95_pp': [float(100 * diff_lo), float(100 * diff_hi)],
            'z': float(z), 'p_value': float(p_two),
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# Block 4: Click-quadrant lift (RIPA2 × LF/HF cross-product)
#          Bootstrap CI on +14.2 pp (bbox) vs +5.9 pp (legacy)
# ──────────────────────────────────────────────────────────────────────

def click_quadrant_cis():
    """Re-derive click rates per quadrant under both attributions, with
    bootstrap CI on the high-high vs low-low lift."""
    DATA_DIR = ROOT / 'AdSERP' / 'data'

    def quad_lift(lfhf_path, ripa2_path, feat_path, label, n_boot=N_BOOT):
        lfhf = json.load(open(lfhf_path))
        ripa2 = json.load(open(ripa2_path))
        feats = json.load(open(feat_path))
        feat_by_tp = {(r['trial_id'], r['position']): bool(r.get('was_clicked', False))
                      for r in feats}
        records = []
        for tid in lfhf:
            if tid not in ripa2: continue
            lt = {p['pos']: p['lfhf'] for p in lfhf[tid]['positions'] if p.get('lfhf') is not None}
            rt = {p['pos']: p['ripa2'] for p in ripa2[tid]['positions'] if p.get('ripa2') is not None}
            for pos in set(lt) & set(rt):
                key = (tid, pos)
                if key not in feat_by_tp: continue
                records.append((lt[pos], rt[pos], feat_by_tp[key]))
        if not records:
            return None
        lf = np.array([r[0] for r in records])
        rp = np.array([r[1] for r in records])
        clk = np.array([r[2] for r in records], dtype=bool)
        lf_med = np.median(lf)
        rp_med = np.median(rp)
        hh_mask = (lf >= lf_med) & (rp >= rp_med)
        ll_mask = (lf <  lf_med) & (rp <  rp_med)
        rate_hh = float(clk[hh_mask].mean()) * 100
        rate_ll = float(clk[ll_mask].mean()) * 100
        lift_pp = rate_hh - rate_ll
        # Bootstrap CI on lift
        n_rec = len(records)
        idx = np.arange(n_rec)
        lifts = np.empty(n_boot)
        for b in range(n_boot):
            sample = RNG.choice(idx, size=n_rec, replace=True)
            lf_s = lf[sample]; rp_s = rp[sample]; clk_s = clk[sample]
            lf_ms = np.median(lf_s); rp_ms = np.median(rp_s)
            hh = (lf_s >= lf_ms) & (rp_s >= rp_ms)
            ll = (lf_s <  lf_ms) & (rp_s <  rp_ms)
            lifts[b] = (clk_s[hh].mean() - clk_s[ll].mean()) * 100
        lo, hi = np.percentile(lifts, [2.5, 97.5])
        return {
            'label': label,
            'n_records': n_rec,
            'rate_HH_pp': rate_hh,
            'rate_LL_pp': rate_ll,
            'lift_pp': float(lift_pp),
            'lift_ci95_pp': [float(lo), float(hi)],
        }

    out = []
    out.append(quad_lift(
        DATA_DIR / 'butterworth-lfhf-by-position.json',
        DATA_DIR / 'ripa2-by-position.json',
        DATA_DIR / 'cursor-approach-features.json',
        'absolute (legacy)',
    ))
    out.append(quad_lift(
        DATA_DIR / 'butterworth-lfhf-by-position-organic.json',
        DATA_DIR / 'ripa2-by-position-organic.json',
        DATA_DIR / 'cursor-approach-features-organic.json',
        'bbox-organic',
    ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Block 5: NB21 LOSO AUC per-fold SDs across attributions
# ──────────────────────────────────────────────────────────────────────

def loso_auc_with_sd():
    out = {}
    for attr, fname in [
        ('absolute', 'nb21_loso_organic.json'),  # actually organic, see below
        ('organic', 'nb21_loso_organic.json'),
        ('hybrid', 'nb21_loso_hybrid.json'),
    ]:
        path = OUT_DIR / fname
        if not path.exists():
            continue
        d = json.load(open(path))
        per_part = d.get('M3_per_part_auc', [])
        if per_part:
            aucs = np.array([a for _, a in per_part])
            out[attr] = {
                'M3_auc': float(d['M3_auc']),
                'M3_per_part_mean': float(aucs.mean()),
                'M3_per_part_sd': float(aucs.std(ddof=1)),
                'M3_per_part_median': float(np.median(aucs)),
                'M3_per_part_iqr_lo': float(np.percentile(aucs, 25)),
                'M3_per_part_iqr_hi': float(np.percentile(aucs, 75)),
                'n_participants_with_auc': int(len(aucs)),
            }
    # Drop the spurious 'absolute' key (we don't have a JSON for it; would need an absolute LOSO retrain)
    out.pop('absolute', None)
    return out


# ──────────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────────

def main():
    print('[1] Multiple-comparison correction on will-return scan', file=sys.stderr)
    correction = correct_will_return_scan()
    print()
    print(f"  Bonferroni α = 0.05 / k=14 = {correction['bonferroni_thresholds']['alpha_05']:.3e}")
    print(f"  Bonferroni α = 0.001 / k=14 = {correction['bonferroni_thresholds']['alpha_001']:.3e}")
    print(f"  {'metric':22s} {'p_raw':>10s} {'p_holm':>10s} {'p_BH-FDR':>10s} {'survives_bonf_05':>17s}")
    for r in sorted(correction['rows'], key=lambda x: x['p_raw']):
        print(f"  {r['metric']:22s} {r['p_raw']:>10.3e} {r['p_holm']:>10.3e} "
              f"{r['p_bh_fdr']:>10.3e} {'✓' if r['survives_bonf_05'] else '✗':>17s}")

    print('\n[2] Bootstrap CIs on will-return Cohen\'s d', file=sys.stderr)
    d_cis = rederive_will_return_with_cis()
    print()
    print(f"  {'metric':22s} {'d':>7s} {'d 95% CI':>22s} {'med diff (95% CI)':>28s}")
    for r in sorted(d_cis, key=lambda x: -abs(x['d'])):
        d = r['d']
        d_ci = r['d_ci95']
        md = r['median_diff']
        md_ci = r['median_diff_ci95']
        print(f"  {r['metric']:22s} {d:+7.3f} [{d_ci[0]:+.3f}, {d_ci[1]:+.3f}]   "
              f"{md:+8.4g}  [{md_ci[0]:+.4g}, {md_ci[1]:+.4g}]")

    print('\n[3] Click-rate by etype: two-proportion z + Newcombe diff CI', file=sys.stderr)
    crc = click_rate_comparisons()
    print()
    print(f"  {'pair':28s} {'rate A':>8s} {'rate B':>8s} {'Δ pp':>8s} {'95% CI (Δ pp)':>22s} {'p':>10s}")
    for r in crc:
        print(f"  {r['pair']:28s} "
              f"{r['p_a']*100:>7.2f}% {r['p_b']*100:>7.2f}% "
              f"{r['diff_pp']:>+7.2f}  "
              f"[{r['diff_ci95_pp'][0]:+.2f}, {r['diff_ci95_pp'][1]:+.2f}]  "
              f"{r['p_value']:>10.3e}")

    print('\n[4] Click-quadrant lift CI (RIPA2 × LF/HF)', file=sys.stderr)
    cq = click_quadrant_cis()
    print()
    for r in cq:
        if r is None: continue
        print(f"  {r['label']:24s}  HH={r['rate_HH_pp']:>5.1f}%  LL={r['rate_LL_pp']:>5.1f}%  "
              f"Δ={r['lift_pp']:>+5.1f} pp  95% CI [{r['lift_ci95_pp'][0]:+.1f}, {r['lift_ci95_pp'][1]:+.1f}]")

    print('\n[5] NB21 LOSO AUC + per-participant SD across attributions', file=sys.stderr)
    loso = loso_auc_with_sd()
    print()
    for attr, vals in loso.items():
        print(f"  {attr:8s}  M3 AUC = {vals['M3_auc']:.3f}  per-part mean ± SD = "
              f"{vals['M3_per_part_mean']:.3f} ± {vals['M3_per_part_sd']:.3f}  "
              f"median = {vals['M3_per_part_median']:.3f}  IQR=[{vals['M3_per_part_iqr_lo']:.3f}, {vals['M3_per_part_iqr_hi']:.3f}]")

    out = {
        'will_return_corrections': correction,
        'will_return_d_cis': d_cis,
        'click_rate_comparisons': crc,
        'click_quadrant_cis': cq,
        'loso_auc_dispersion': loso,
    }
    out_path = OUT_DIR / 'rigor_corrections.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
