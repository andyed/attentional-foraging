"""Stress-test LF/HF first-pass → predicts-regression-return.

12 angles on the same primary claim, output single JSON + markdown report.

Run:
  .venv/bin/python scripts/lfhf_predicts_return_stress.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_predicts_return_stress'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta,
    organic_aoi_tops, extract_serp_results,
    result_band_tops, assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

ATTRIBUTIONS = ['absolute', 'organic', 'organic_hybrid']
INPUTS = {
    'absolute':       {'lfhf': DATA / 'butterworth-lfhf-by-position.json',
                       'ripa2': DATA / 'ripa2-by-position.json'},
    'organic':        {'lfhf': DATA / 'butterworth-lfhf-by-position-organic.json',
                       'ripa2': DATA / 'ripa2-by-position-organic.json'},
    'organic_hybrid': {'lfhf': DATA / 'butterworth-lfhf-by-position-organic.json',
                       'ripa2': DATA / 'ripa2-by-position-organic.json'},
}


# ── helpers ──────────────────────────────────────────────────────────

def participant_id(tid):
    return tid.split('-')[0]


def regressed_positions(tid, attr):
    fix = load_fixations(tid)
    meta = get_trial_meta(tid)
    if not fix or meta is None or not meta[0]:
        return None
    doc_h = meta[0]
    if attr == 'organic':
        tops = organic_aoi_tops(tid)
        n_res = len(tops)
    elif attr == 'organic_hybrid':
        tops = _hybrid_aoi_tops(tid)
        n_res = len(tops)
    else:
        serp = extract_serp_results(tid)
        n_res = len(serp) if serp else 10
        tops = result_band_tops(n_res, doc_h) if n_res else []
    if not tops:
        return None
    pos_seq = []
    for f in fix:
        p = assign_fixation_to_position(f['y'], tops, n_res)
        if p is not None and p >= 0:
            pos_seq.append(p)
    visited, regressed = set(), set()
    max_seen = -1
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressed.add(p)
        visited.add(p)
        if p > max_seen:
            max_seen = p
    return regressed


def collect_records(attr):
    """Return list of dicts: trial_id, pid, pos, lfhf, ripa2, returned."""
    lfhf = json.load(open(INPUTS[attr]['lfhf']))
    ripa2 = json.load(open(INPUTS[attr]['ripa2']))
    records = []
    for tid, payload in lfhf.items():
        positions = [p for p in payload.get('positions', [])
                     if p.get('lfhf') is not None]
        if not positions:
            continue
        regressed = regressed_positions(tid, attr)
        if regressed is None:
            continue
        rp = {p['pos']: p.get('ripa2') for p in ripa2.get(tid, {}).get('positions', [])
              if p.get('ripa2') is not None}
        for p in positions:
            pos = int(p['pos'])
            records.append({
                'trial_id': tid, 'pid': participant_id(tid), 'pos': pos,
                'lfhf': float(p['lfhf']),
                'ripa2': rp.get(pos),
                'returned': pos in regressed,
            })
    return records


def cohens_d(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0


def cliffs_delta(a, b):
    """Cliff's δ — non-parametric effect size, in [-1, 1]."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0 or len(b) == 0:
        return float('nan')
    # Efficient: rank pooled, separate ranks, derive U
    n1, n2 = len(a), len(b)
    u, _ = stats.mannwhitneyu(a, b, alternative='two-sided')
    return float((2 * u) / (n1 * n2) - 1)


def auc_with_ci(y, scores, n_boot=2000, rng=None):
    """AUC + 95% CI via bootstrap of pairs."""
    if rng is None:
        rng = np.random.default_rng(20260503)
    y, scores = np.asarray(y), np.asarray(scores)
    auc = float(roc_auc_score(y, scores))
    n = len(y)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        try:
            boots[b] = roc_auc_score(y[idx], scores[idx])
        except ValueError:
            boots[b] = np.nan
    boots = boots[~np.isnan(boots)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return auc, float(lo), float(hi)


def cluster_bootstrap(deltas, n_boot=2000, rng=None):
    if rng is None:
        rng = np.random.default_rng(20260503)
    delta_vals = np.array(deltas)
    if len(delta_vals) == 0:
        return float('nan'), float('nan')
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(len(delta_vals), size=len(delta_vals), replace=True)
        boots[b] = delta_vals[idx].mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def trial_cluster_bootstrap_delta(records, n_boot=2000, rng=None):
    """Bootstrap trials; for each bootstrap sample compute mean(returned) - mean(not)."""
    if rng is None:
        rng = np.random.default_rng(20260503)
    by_trial = defaultdict(list)
    for r in records:
        by_trial[r['trial_id']].append(r)
    trials = list(by_trial.keys())
    boots = []
    for b in range(n_boot):
        idx = rng.choice(len(trials), size=len(trials), replace=True)
        ret, nrt = [], []
        for i in idx:
            for r in by_trial[trials[i]]:
                (ret if r['returned'] else nrt).append(r['lfhf'])
        if ret and nrt:
            boots.append(np.mean(ret) - np.mean(nrt))
    boots = np.array(boots)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(np.mean(boots)), float(lo), float(hi)


# ── per-attribution stress tests ─────────────────────────────────────

def stress(attr):
    records = collect_records(attr)
    n = len(records)
    pids = sorted({r['pid'] for r in records})
    trials = sorted({r['trial_id'] for r in records})
    n_returned = sum(1 for r in records if r['returned'])
    n_not = n - n_returned
    print(f'\n=== {attr.upper()} === records: {n:,}  '
          f'(returned {n_returned:,}, not {n_not:,})  '
          f'participants: {len(pids)}  trials: {len(trials):,}',
          file=sys.stderr)

    lfhf = np.array([r['lfhf'] for r in records])
    y = np.array([r['returned'] for r in records], dtype=bool)
    out = {
        'attribution': attr,
        'n_records': n, 'n_returned': n_returned, 'n_not_returned': n_not,
        'n_participants': len(pids), 'n_trials': len(trials),
    }

    # ── Angle 1: observation-level Mann–Whitney + Cliff's δ ──
    u, p_mw = stats.mannwhitneyu(lfhf[y], lfhf[~y], alternative='greater')
    d = cohens_d(lfhf[y], lfhf[~y])
    delta = cliffs_delta(lfhf[y], lfhf[~y])
    out['angle1_obs_mw'] = {
        'p_one_sided_greater': float(p_mw),
        'cohens_d': d, 'cliffs_delta': delta,
        'median_returned': float(np.median(lfhf[y])),
        'median_not': float(np.median(lfhf[~y])),
        'mean_returned': float(np.mean(lfhf[y])),
        'mean_not': float(np.mean(lfhf[~y])),
    }

    # ── Angle 2: AUC of LF/HF for predicting return ──
    auc, lo, hi = auc_with_ci(y, lfhf)
    out['angle2_obs_auc'] = {'auc': auc, 'ci95': [lo, hi]}

    # ── Angle 3: participant Wilcoxon, mean-Δ ──
    by_pid = defaultdict(lambda: {'r': [], 'n': []})
    for r in records:
        by_pid[r['pid']]['r' if r['returned'] else 'n'].append(r['lfhf'])
    deltas_mean = []
    for pid, vals in by_pid.items():
        if vals['r'] and vals['n']:
            deltas_mean.append(float(np.mean(vals['r']) - np.mean(vals['n'])))
    deltas_mean = np.array(deltas_mean)
    n_in_test_mean = len(deltas_mean)
    p_two_mean = float(stats.wilcoxon(deltas_mean, alternative='two-sided').pvalue) if n_in_test_mean else float('nan')
    p_one_mean = float(stats.wilcoxon(deltas_mean, alternative='greater').pvalue) if n_in_test_mean else float('nan')
    out['angle3_participant_wilcoxon_meandelta'] = {
        'n_participants_in_test': n_in_test_mean,
        'mean_delta_across_participants': float(deltas_mean.mean()),
        'pct_positive': float(100 * (deltas_mean > 0).mean()),
        'p_two_sided': p_two_mean,
        'p_one_sided_greater': p_one_mean,
    }

    # ── Angle 4: participant Wilcoxon, median-of-medians-Δ ──
    deltas_med = []
    for pid, vals in by_pid.items():
        if vals['r'] and vals['n']:
            deltas_med.append(float(np.median(vals['r']) - np.median(vals['n'])))
    deltas_med = np.array(deltas_med)
    p_two_med = float(stats.wilcoxon(deltas_med, alternative='two-sided').pvalue)
    p_one_med = float(stats.wilcoxon(deltas_med, alternative='greater').pvalue)
    out['angle4_participant_wilcoxon_medianofmedians'] = {
        'n_participants_in_test': len(deltas_med),
        'median_of_medians_delta': float(np.median(deltas_med)),
        'pct_positive': float(100 * (deltas_med > 0).mean()),
        'p_two_sided': p_two_med,
        'p_one_sided_greater': p_one_med,
    }

    # ── Angle 5 (substituted): obs-vs-participant p-value spread ──
    # variance partition signature; large gap implies between-pid heterogeneity
    out['angle5_variance_partition'] = {
        'note': 'mixed-effects unavailable (no statsmodels); proxy via obs-vs-participant p-value gap',
        'obs_p_one_sided': float(p_mw),
        'participant_mean_p_one_sided': p_one_mean,
        'spread_log10': float(np.log10(p_one_mean) - np.log10(p_mw)) if p_one_mean > 0 and p_mw > 0 else float('nan'),
    }

    # ── Angle 6: per-participant AUC distribution; sign test against 0.5 ──
    per_pid_auc = []
    for pid, vals in by_pid.items():
        if len(vals['r']) >= 1 and len(vals['n']) >= 1:
            yp = [1] * len(vals['r']) + [0] * len(vals['n'])
            sp = vals['r'] + vals['n']
            try:
                per_pid_auc.append(float(roc_auc_score(yp, sp)))
            except ValueError:
                pass
    per_pid_auc = np.array(per_pid_auc)
    n_above_half = int((per_pid_auc > 0.5).sum())
    sign_p = float(stats.binomtest(n_above_half, len(per_pid_auc), 0.5,
                                    alternative='greater').pvalue) if len(per_pid_auc) else float('nan')
    out['angle6_per_participant_auc'] = {
        'n_participants': int(len(per_pid_auc)),
        'auc_mean': float(per_pid_auc.mean()) if len(per_pid_auc) else float('nan'),
        'auc_median': float(np.median(per_pid_auc)) if len(per_pid_auc) else float('nan'),
        'pct_above_chance': float(100 * (per_pid_auc > 0.5).mean()) if len(per_pid_auc) else float('nan'),
        'sign_test_p_one_sided': sign_p,
        'auc_p25': float(np.percentile(per_pid_auc, 25)) if len(per_pid_auc) else float('nan'),
        'auc_p75': float(np.percentile(per_pid_auc, 75)) if len(per_pid_auc) else float('nan'),
    }

    # ── Angle 8: rank-stratified ──
    def stratum_test(mask, label):
        if mask.sum() == 0:
            return None
        u_s, p_s = stats.mannwhitneyu(lfhf[mask & y], lfhf[mask & ~y], alternative='greater')
        return {
            'n_total': int(mask.sum()),
            'n_returned': int((mask & y).sum()),
            'p_one_sided_greater': float(p_s),
            'cohens_d': cohens_d(lfhf[mask & y], lfhf[mask & ~y]),
            'median_returned': float(np.median(lfhf[mask & y])) if (mask & y).sum() else float('nan'),
            'median_not': float(np.median(lfhf[mask & ~y])) if (mask & ~y).sum() else float('nan'),
        }

    pos = np.array([r['pos'] for r in records])
    out['angle8_rank_stratified'] = {
        'P0-P3 (commit-action surface)': stratum_test(pos <= 3, 'P0-3'),
        'P4-P10 (plateau)': stratum_test((pos >= 4) & (pos <= 10), 'P4-10'),
    }

    # ── Angle 9: cluster bootstrap CI on Δ — both clusterings ──
    pid_lo, pid_hi = cluster_bootstrap(deltas_mean.tolist())
    trial_mean, trial_lo, trial_hi = trial_cluster_bootstrap_delta(records)
    out['angle9_cluster_bootstrap'] = {
        'participant_cluster_ci95_on_mean_delta': [pid_lo, pid_hi],
        'trial_cluster_ci95_on_mean_delta': [trial_lo, trial_hi],
        'trial_cluster_mean_delta': trial_mean,
    }

    # ── Angle 10: comparator channels (RIPA2 + first-pass dwell + n_fix) ──
    ripa2_arr = np.array([r['ripa2'] if r['ripa2'] is not None else np.nan
                          for r in records])
    valid = ~np.isnan(ripa2_arr)
    if valid.sum():
        u_r, p_r = stats.mannwhitneyu(ripa2_arr[valid & y], ripa2_arr[valid & ~y],
                                       alternative='two-sided')
        out['angle10_comparator_ripa2'] = {
            'n_with_ripa2': int(valid.sum()),
            'p_two_sided': float(p_r),
            'cohens_d': cohens_d(ripa2_arr[valid & y], ripa2_arr[valid & ~y]),
            'median_returned': float(np.median(ripa2_arr[valid & y])),
            'median_not': float(np.median(ripa2_arr[valid & ~y])),
        }
    # We'd need fix-count + first-pass-dwell joined per (trial, pos) — stub
    # in via encoding-vs-retrieval for note purposes
    out['angle10_comparator_note'] = (
        'first-pass dwell wr/nr from K16: 194 vs 214 ms (gaze-only, p=8.1e-32, '
        'opposite direction — wr lingered LESS at fixation level but had HIGHER LF/HF '
        'segment-level)'
    )

    # ── Angle 11: per-rank Δ wr/nr (forest plot data) ──
    per_rank = {}
    for rank in range(11):
        mask = pos == rank
        n_r = int((mask & y).sum())
        n_n = int((mask & ~y).sum())
        if n_r >= 5 and n_n >= 5:
            try:
                u_k, p_k = stats.mannwhitneyu(lfhf[mask & y], lfhf[mask & ~y],
                                               alternative='two-sided')
                per_rank[str(rank)] = {
                    'n_returned': n_r, 'n_not': n_n,
                    'median_returned': float(np.median(lfhf[mask & y])),
                    'median_not': float(np.median(lfhf[mask & ~y])),
                    'delta_median': float(np.median(lfhf[mask & y]) - np.median(lfhf[mask & ~y])),
                    'cohens_d': cohens_d(lfhf[mask & y], lfhf[mask & ~y]),
                    'p_two_sided': float(p_k),
                }
            except ValueError:
                pass
    out['angle11_per_rank'] = per_rank

    # ── Angle 12: subset stress ──
    # 12a: ≥3-position trials only
    by_trial = defaultdict(list)
    for r in records:
        by_trial[r['trial_id']].append(r)
    keep_trials = {t for t, rs in by_trial.items() if len(rs) >= 3}
    sub3 = [r for r in records if r['trial_id'] in keep_trials]
    if sub3:
        lfhf3 = np.array([r['lfhf'] for r in sub3])
        y3 = np.array([r['returned'] for r in sub3], dtype=bool)
        u3, p3 = stats.mannwhitneyu(lfhf3[y3], lfhf3[~y3], alternative='greater')
        out['angle12a_ge3_position_trials'] = {
            'n_trials': len(keep_trials),
            'n_records': len(sub3),
            'p_one_sided_greater': float(p3),
            'cohens_d': cohens_d(lfhf3[y3], lfhf3[~y3]),
        }
    # 12b: log-transform (handle skew)
    lf_pos = lfhf > 0
    log_lf = np.log(lfhf[lf_pos])
    y_log = y[lf_pos]
    u_log, p_log = stats.mannwhitneyu(log_lf[y_log], log_lf[~y_log], alternative='greater')
    out['angle12b_log_transform'] = {
        'n_records': int(lf_pos.sum()),
        'p_one_sided_greater': float(p_log),
        'cohens_d': cohens_d(log_lf[y_log], log_lf[~y_log]),
    }
    # 12c: trim 2.5%/97.5%
    lo_q, hi_q = np.percentile(lfhf, [2.5, 97.5])
    keep = (lfhf >= lo_q) & (lfhf <= hi_q)
    u_t, p_t = stats.mannwhitneyu(lfhf[keep & y], lfhf[keep & ~y], alternative='greater')
    out['angle12c_trimmed'] = {
        'n_records': int(keep.sum()),
        'p_one_sided_greater': float(p_t),
        'cohens_d': cohens_d(lfhf[keep & y], lfhf[keep & ~y]),
    }

    # Print summary
    a1 = out['angle1_obs_mw']; a2 = out['angle2_obs_auc']
    a3 = out['angle3_participant_wilcoxon_meandelta']
    a4 = out['angle4_participant_wilcoxon_medianofmedians']
    a6 = out['angle6_per_participant_auc']
    a9 = out['angle9_cluster_bootstrap']
    print(f'  A1 obs MW p1: {a1["p_one_sided_greater"]:.2e}  d={a1["cohens_d"]:+.3f}', file=sys.stderr)
    print(f'  A2 obs AUC: {a2["auc"]:.3f} CI [{a2["ci95"][0]:.3f}, {a2["ci95"][1]:.3f}]', file=sys.stderr)
    print(f'  A3 ppt mean-Δ Wilcoxon p2: {a3["p_two_sided"]:.4f}  Δ={a3["mean_delta_across_participants"]:+.3f}  pos={a3["pct_positive"]:.0f}%', file=sys.stderr)
    print(f'  A4 ppt med-of-med Wilcoxon p2: {a4["p_two_sided"]:.4f}  Δ={a4["median_of_medians_delta"]:+.3f}', file=sys.stderr)
    print(f'  A6 ppt AUC mean: {a6["auc_mean"]:.3f}  pct above 0.5: {a6["pct_above_chance"]:.0f}%  sign-test p={a6["sign_test_p_one_sided"]:.4f}', file=sys.stderr)
    print(f'  A9 ppt-cluster CI: [{a9["participant_cluster_ci95_on_mean_delta"][0]:+.3f}, {a9["participant_cluster_ci95_on_mean_delta"][1]:+.3f}]', file=sys.stderr)
    print(f'  A9 trial-cluster CI: [{a9["trial_cluster_ci95_on_mean_delta"][0]:+.3f}, {a9["trial_cluster_ci95_on_mean_delta"][1]:+.3f}]', file=sys.stderr)

    return out


def write_report(results):
    lines = []
    lines.append('# LF/HF first-pass → predicts regressive return — stress test\n')
    lines.append(f'_Generated 2026-05-03 by `scripts/lfhf_predicts_return_stress.py`._\n')
    lines.append('## Headline\n')
    abs_r = results['absolute']
    a3 = abs_r['angle3_participant_wilcoxon_meandelta']
    a4 = abs_r['angle4_participant_wilcoxon_medianofmedians']
    a1 = abs_r['angle1_obs_mw']
    lines.append(f'Paper claim (`adserp.tex` L174): participant-Wilcoxon **p = 0.0055**, 63% direction, CI [+0.94, +3.85], N=6,112 / 46 participants.\n')
    lines.append('| Angle | Absolute | Organic (bbox) | Organic-hybrid |')
    lines.append('|---|---|---|---|')
    for attr in ATTRIBUTIONS:
        r = results[attr]
        n = f'N={r["n_records"]:,}, ppt={r["n_participants"]}'
    # Build the comparison table
    rows = [
        ('records / participants', lambda r: f'{r["n_records"]:,} / {r["n_participants"]}'),
        ('A1 obs MW p (one-sided greater)', lambda r: f'{r["angle1_obs_mw"]["p_one_sided_greater"]:.2e}'),
        ('A1 Cohen\'s d', lambda r: f'{r["angle1_obs_mw"]["cohens_d"]:+.3f}'),
        ('A1 Cliff\'s δ', lambda r: f'{r["angle1_obs_mw"]["cliffs_delta"]:+.3f}'),
        ('A2 obs AUC [95% CI]', lambda r: f'{r["angle2_obs_auc"]["auc"]:.3f} [{r["angle2_obs_auc"]["ci95"][0]:.3f}, {r["angle2_obs_auc"]["ci95"][1]:.3f}]'),
        ('A3 ppt mean-Δ', lambda r: f'{r["angle3_participant_wilcoxon_meandelta"]["mean_delta_across_participants"]:+.3f}'),
        ('A3 Wilcoxon p (two-sided)', lambda r: f'{r["angle3_participant_wilcoxon_meandelta"]["p_two_sided"]:.4f}'),
        ('A3 % participants Δ > 0', lambda r: f'{r["angle3_participant_wilcoxon_meandelta"]["pct_positive"]:.0f}%'),
        ('A4 ppt median-of-medians Δ', lambda r: f'{r["angle4_participant_wilcoxon_medianofmedians"]["median_of_medians_delta"]:+.3f}'),
        ('A4 Wilcoxon p (two-sided)', lambda r: f'{r["angle4_participant_wilcoxon_medianofmedians"]["p_two_sided"]:.4f}'),
        ('A6 ppt AUC mean', lambda r: f'{r["angle6_per_participant_auc"]["auc_mean"]:.3f}'),
        ('A6 % participants AUC > 0.5', lambda r: f'{r["angle6_per_participant_auc"]["pct_above_chance"]:.0f}%'),
        ('A6 sign-test p (one-sided)', lambda r: f'{r["angle6_per_participant_auc"]["sign_test_p_one_sided"]:.4f}'),
        ('A9 ppt-cluster 95% CI on mean Δ', lambda r: f'[{r["angle9_cluster_bootstrap"]["participant_cluster_ci95_on_mean_delta"][0]:+.2f}, {r["angle9_cluster_bootstrap"]["participant_cluster_ci95_on_mean_delta"][1]:+.2f}]'),
        ('A9 trial-cluster 95% CI on mean Δ', lambda r: f'[{r["angle9_cluster_bootstrap"]["trial_cluster_ci95_on_mean_delta"][0]:+.2f}, {r["angle9_cluster_bootstrap"]["trial_cluster_ci95_on_mean_delta"][1]:+.2f}]'),
        ('A12a ≥3-pos trials, MW p', lambda r: f'{r.get("angle12a_ge3_position_trials", {}).get("p_one_sided_greater", float("nan")):.2e}'),
        ('A12b log-transform, MW p', lambda r: f'{r["angle12b_log_transform"]["p_one_sided_greater"]:.2e}'),
        ('A12c trimmed (2.5/97.5), MW p', lambda r: f'{r["angle12c_trimmed"]["p_one_sided_greater"]:.2e}'),
    ]
    # Render headed table
    header = '| Angle | absolute | organic | organic_hybrid |'
    sep = '|---|---|---|---|'
    lines.append(header); lines.append(sep)
    for label, fn in rows:
        cells = [label]
        for attr in ATTRIBUTIONS:
            try:
                cells.append(fn(results[attr]))
            except (KeyError, TypeError):
                cells.append('—')
        lines.append('| ' + ' | '.join(cells) + ' |')

    lines.append('\n## A8 — rank stratified (one-sided greater)\n')
    lines.append('| Attribution | P0–P3 N / p / d | P4–P10 N / p / d |')
    lines.append('|---|---|---|')
    for attr in ATTRIBUTIONS:
        a8 = results[attr]['angle8_rank_stratified']
        steep = a8.get('P0-P3 (commit-action surface)') or {}
        plat = a8.get('P4-P10 (plateau)') or {}
        steep_s = f'{steep.get("n_total", 0):,} / {steep.get("p_one_sided_greater", float("nan")):.2e} / {steep.get("cohens_d", float("nan")):+.3f}' if steep else '—'
        plat_s = f'{plat.get("n_total", 0):,} / {plat.get("p_one_sided_greater", float("nan")):.2e} / {plat.get("cohens_d", float("nan")):+.3f}' if plat else '—'
        lines.append(f'| {attr} | {steep_s} | {plat_s} |')

    lines.append('\n## A11 — per-rank Δ (median(returned) − median(not), absolute attribution)\n')
    lines.append('| Rank | n_returned | n_not | Δ median | d | p (two-sided) |')
    lines.append('|---|---|---|---|---|---|')
    for rank in sorted(results['absolute']['angle11_per_rank'].keys(), key=int):
        r = results['absolute']['angle11_per_rank'][rank]
        lines.append(f'| {rank} | {r["n_returned"]} | {r["n_not"]} | {r["delta_median"]:+.2f} | {r["cohens_d"]:+.3f} | {r["p_two_sided"]:.3e} |')

    lines.append('\n## A10 — RIPA2 same test (sanity check on the dissociation)\n')
    for attr in ATTRIBUTIONS:
        a10 = results[attr].get('angle10_comparator_ripa2', {})
        lines.append(f'- **{attr}**: n={a10.get("n_with_ripa2", 0):,}, '
                     f'p_two_sided={a10.get("p_two_sided", float("nan")):.2e}, '
                     f'd={a10.get("cohens_d", float("nan")):+.3f}, '
                     f'medians wr={a10.get("median_returned", float("nan")):.4g} vs nr={a10.get("median_not", float("nan")):.4g}')

    lines.append(f'\n## Limitations\n')
    lines.append('- Mixed-effects (Angle 5) skipped — `statsmodels` not in venv. Variance partition reported via obs-vs-participant p-value gap and per-participant AUC distribution.')
    lines.append('- Angle 13/14 (within-item paired first-visit vs return-visit LF/HF) requires Phase 2 — return-visit LF/HF must be computed via pupil-lfhf gated to revisit fixations.')
    lines.append('- LHIPA comparator skipped — trial-level only, can\'t do per-(trial, position) test.')

    return '\n'.join(lines)


def main():
    print('[stress] LF/HF first-pass → predicts return — 12-angle sweep', file=sys.stderr)
    results = {}
    for attr in ATTRIBUTIONS:
        results[attr] = stress(attr)

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(results, indent=2))
    print(f'\nwrote {out_json.relative_to(ROOT)}', file=sys.stderr)

    out_md = OUT / 'report.md'
    out_md.write_text(write_report(results))
    print(f'wrote {out_md.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
