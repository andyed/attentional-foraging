"""Recompute NB23's rank-effects claims on ORGANIC rank.

The original NB23 K1–K4 claims are indexed by absolute rank (or by an even
ten-band split of doc height). That pools ads with organic and introduces
artifacts:

  - K1's non-monotone pos 0→1→2 (26.9% → 22.0% → 24.3%) is a dd_top ad
    slot displacing some position-0 clicks.
  - K4's LF/HF bump at positions 5–7 is likely native_ad contamination.

This script recomputes:
  - CTR-by-organic-rank (trial-level) on two cohorts:
       * full corpus (N = 2,776)
       * clean_for_ctr = plain_top ∩ n_org ∈ {9,10,11} (N = 555)
  - Click-share-by-organic-rank on both cohorts
  - Fixation count × organic rank (N clicked trials, per-(trial, org_rank))
  - Total dwell × organic rank
  - Butterworth LF/HF × organic rank (reusing precomputed absolute-rank JSON
    via the absolute_to_organic_rank mapping — no re-filtering needed)

Writes all tables to scripts/output/nb23_organic_rank/ plus a JSON summary
of every new K-ID value suitable for updating update_key_claims.py.

Run:
    .venv/bin/python scripts/compute_nb23_organic_rank.py

Idempotent, ~30 seconds.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import math
from itertools import permutations

import numpy as np
from scipy.stats import spearmanr, rankdata

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    DATA_DIR,
    get_trial_ids,
    get_trial_meta,
    load_fixations,
    load_mouse_events,
    count_absolute_ranks,
    absolute_to_organic_rank,
    absolute_rank_band_tops,
    interpolate_scroll,
)

OUT_DIR = ROOT / 'scripts' / 'output' / 'nb23_organic_rank'
OUT_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_CSV = ROOT / 'scripts' / 'output' / 'serp_structure_survey' / 'trial_snapshot.csv'
BW_JSON = DATA_DIR / 'butterworth-lfhf-by-position.json'


def _load_clean_cohort() -> set[str]:
    """Deterministic reproduction of clean_for_ctr from trial_snapshot.csv.

    clean_for_ctr = trials where plain_top == 1 and n_org in {9, 10, 11}.
    """
    tids: set[str] = set()
    with open(SNAPSHOT_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['plain_top']) == 1 and int(row['n_org']) in (9, 10, 11):
                tids.add(row['tid'])
    return tids


def _spearman(xs: list[int], ys: list[float]) -> tuple[float, float]:
    """Spearman ρ with a numerically sane p-value.

    scipy.stats.spearmanr uses the t-approximation which underflows to
    ~6.6e-64 when |ρ| = 1 exactly. For small N (≤ 12) we compute the
    exact permutation p (N ≤ 10 brute-force, 11–12 via permutation_test
    with factorial-equivalent resamples). For N > 12 the asymptotic
    approximation is fine.
    """
    pairs = [(x, y) for x, y in zip(xs, ys) if y is not None and not np.isnan(y)]
    if len(pairs) < 3:
        return (float('nan'), float('nan'))
    xa, ya = zip(*pairs)
    rho, p_asymp = spearmanr(xa, ya)
    rho = float(rho)
    n = len(pairs)
    # For n ≤ 11 always compute an exact permutation p: the t-approximation
    # is too loose at small N and underflows to ~6.6e-64 when |ρ| → 1.
    if n <= 11:
        return (rho, _exact_spearman_p(list(xa), list(ya), rho))
    return (rho, float(p_asymp))


def _exact_spearman_p(xa: list, ya: list, observed_rho: float) -> float:
    """Exact two-sided Spearman p via full n! permutation enumeration.

    Vectorized with numpy: builds all permutations of ry once, then
    computes D² = Σ(rx − permuted_ry)² in a batched matrix multiply,
    converts to ρ, counts |ρ| ≥ observed.
    """
    n = len(xa)
    if n < 3:
        return float('nan')
    rx = rankdata(xa).astype(np.float64)
    ry = rankdata(ya).astype(np.float64)
    denom = n * (n * n - 1)
    n_fact = math.factorial(n)
    observed = abs(observed_rho)

    hits = 0
    BATCH = 200_000
    batch: list = []
    for perm in permutations(range(n)):
        batch.append(perm)
        if len(batch) == BATCH:
            hits += _count_hits(batch, rx, ry, denom, observed)
            batch = []
    if batch:
        hits += _count_hits(batch, rx, ry, denom, observed)
    return hits / n_fact


def _count_hits(batch: list, rx: np.ndarray, ry: np.ndarray,
                denom: int, observed: float) -> int:
    arr = np.asarray(batch)
    permuted = ry[arr]
    D = np.sum((rx[None, :] - permuted) ** 2, axis=1)
    rhos = 1.0 - 6.0 * D / denom
    return int((np.abs(rhos) >= observed - 1e-12).sum())


def main() -> None:
    t0 = time.time()
    tids = get_trial_ids()
    clean_tids = _load_clean_cohort()
    print(f'[nb23-org] {len(tids)} trials, {len(clean_tids)} in clean_for_ctr cohort')

    with open(BW_JSON) as f:
        bw_data = json.load(f)
    print(f'[nb23-org] {len(bw_data)} trials with Butterworth LF/HF')

    # ── Per-rank accumulators ─────────────────────────────────────────────
    # CTR: trial-level once-per-rank for clicks, once per impression
    full_imp: Counter[int] = Counter()
    full_click_trials: Counter[int] = Counter()
    clean_imp: Counter[int] = Counter()
    clean_click_trials: Counter[int] = Counter()

    # Click share (click count, not trials — matches NB23:K1 semantics)
    full_click_count: Counter[int] = Counter()
    clean_click_count: Counter[int] = Counter()
    full_clicks_in_ad = 0
    clean_clicks_in_ad = 0
    full_clicks_no_rank = 0
    clean_clicks_no_rank = 0

    # Fixation count / dwell per (trial, org_rank) — exclude zeros
    fix_rows_full: list[dict] = []
    fix_rows_clean: list[dict] = []

    # Butterworth LF/HF per (trial, org_rank)
    lfhf_full: defaultdict[int, list[float]] = defaultdict(list)
    lfhf_clean: defaultdict[int, list[float]] = defaultdict(list)

    n_bw_missing = 0
    n_fix_missing = 0

    for idx, tid in enumerate(tids):
        if idx and idx % 500 == 0:
            print(f'[nb23-org]   {idx}/{len(tids)}  ({time.time() - t0:.1f}s)')

        doc_h, scr_h, _ = get_trial_meta(tid)
        if doc_h is None:
            doc_h = 2642
        n_abs = count_absolute_ranks(tid)
        if n_abs == 0:
            continue

        mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
        tops = absolute_rank_band_tops(n_abs, doc_h)
        in_clean = tid in clean_tids

        # Impressions: one per organic rank present
        present_org_ranks = sorted({v for v in mapping.values() if v is not None})
        for r in present_org_ranks:
            full_imp[r] += 1
            if in_clean:
                clean_imp[r] += 1

        # ── Clicks ───────────────────────────────────────────────────────
        try:
            _, _, clicks = load_mouse_events(tid)
        except Exception:
            clicks = []

        trial_org_clicks: set[int] = set()
        for (_, _, cy) in clicks:
            abs_rank = None
            for r in range(n_abs):
                top = tops[r]
                bot = tops[r + 1] if r + 1 < n_abs else doc_h - 200
                if top <= cy < bot:
                    abs_rank = r
                    break
            if abs_rank is None:
                full_clicks_no_rank += 1
                if in_clean:
                    clean_clicks_no_rank += 1
                continue
            org_rank = mapping.get(abs_rank)
            if org_rank is None:
                full_clicks_in_ad += 1
                if in_clean:
                    clean_clicks_in_ad += 1
                continue
            full_click_count[org_rank] += 1
            if in_clean:
                clean_click_count[org_rank] += 1
            trial_org_clicks.add(org_rank)

        for r in trial_org_clicks:
            full_click_trials[r] += 1
            if in_clean:
                clean_click_trials[r] += 1

        # ── Fixation count / dwell per organic rank ──────────────────────
        fixations = load_fixations(tid)
        if not fixations:
            n_fix_missing += 1
        else:
            per_org: defaultdict[int, dict] = defaultdict(
                lambda: {'fix_count': 0, 'fix_total_ms': 0})
            for fix in fixations:
                y = fix['y']  # page-space (2026-04-12 audit)
                # Which absolute rank band does this fixation fall in?
                abs_rank = None
                for r in range(n_abs):
                    top = tops[r]
                    bot = tops[r + 1] if r + 1 < n_abs else doc_h - 200
                    if top <= y < bot:
                        abs_rank = r
                        break
                if abs_rank is None:
                    continue
                org_rank = mapping.get(abs_rank)
                if org_rank is None:
                    continue
                per_org[org_rank]['fix_count'] += 1
                per_org[org_rank]['fix_total_ms'] += fix['d']

            for org_rank, stats in per_org.items():
                row = {'trial': tid, 'org_rank': org_rank,
                       'fix_count': stats['fix_count'],
                       'fix_total_ms': stats['fix_total_ms']}
                fix_rows_full.append(row)
                if in_clean:
                    fix_rows_clean.append(row)

        # ── Butterworth LF/HF per organic rank ───────────────────────────
        bw = bw_data.get(tid)
        if bw is None:
            n_bw_missing += 1
        else:
            for entry in bw['positions']:
                abs_pos = entry['pos']
                lfhf = entry['lfhf']
                if lfhf is None:
                    continue
                org_rank = mapping.get(abs_pos)
                if org_rank is None:
                    continue
                lfhf_full[org_rank].append(float(lfhf))
                if in_clean:
                    lfhf_clean[org_rank].append(float(lfhf))

    elapsed = time.time() - t0
    print(f'[nb23-org] done in {elapsed:.1f}s  '
          f'(bw_missing={n_bw_missing}, fix_missing={n_fix_missing})')

    # ── Build CTR / click-share tables ────────────────────────────────────
    def _write_ctr(name: str, imp: Counter, clk_trials: Counter,
                   clk_count: Counter) -> list[dict]:
        path = OUT_DIR / f'{name}.csv'
        out_rows = []
        total_clicks = sum(clk_count.values())
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['org_rank', 'impressions', 'click_trials',
                        'click_count', 'ctr', 'click_share_pct'])
            for r in sorted(imp):
                i = imp[r]
                ct = clk_trials.get(r, 0)
                cc = clk_count.get(r, 0)
                ctr = ct / i if i else 0.0
                share = 100 * cc / total_clicks if total_clicks else 0.0
                w.writerow([r, i, ct, cc, f'{ctr:.4f}', f'{share:.4f}'])
                out_rows.append({'org_rank': r, 'impressions': i,
                                 'click_trials': ct, 'click_count': cc,
                                 'ctr': ctr, 'click_share_pct': share})
        return out_rows

    full_table = _write_ctr('ctr_and_share_full', full_imp,
                            full_click_trials, full_click_count)
    clean_table = _write_ctr('ctr_and_share_clean_for_ctr', clean_imp,
                             clean_click_trials, clean_click_count)

    # ── Spearmans on the CTR / share curves ──────────────────────────────
    # Restrict to org_rank in 0..9 for direct comparison with K1's 0..10 range
    # (but organic rank hits its natural tail around 10+; use 0..9).
    def _stats_for_table(table: list[dict], ranks=range(0, 10)) -> dict:
        rows = [r for r in table if r['org_rank'] in ranks]
        ctrs = [(r['org_rank'], r['ctr']) for r in rows]
        shares = [(r['org_rank'], r['click_share_pct']) for r in rows]
        xs_ctr, ys_ctr = zip(*ctrs) if ctrs else ([], [])
        xs_sh, ys_sh = zip(*shares) if shares else ([], [])
        ctr_rho, ctr_p = _spearman(list(xs_ctr), list(ys_ctr))
        sh_rho, sh_p = _spearman(list(xs_sh), list(ys_sh))
        return {
            'n_points': len(rows),
            'ranks': [r['org_rank'] for r in rows],
            'ctr': [r['ctr'] for r in rows],
            'click_share_pct': [r['click_share_pct'] for r in rows],
            'ctr_rho': ctr_rho, 'ctr_p': ctr_p,
            'click_share_rho': sh_rho, 'click_share_p': sh_p,
        }

    full_stats = _stats_for_table(full_table)
    clean_stats = _stats_for_table(clean_table)

    # ── Fixation count / dwell means by org_rank ─────────────────────────
    def _means_by_rank(rows: list[dict], field: str, ranks=range(0, 10)) -> list[float]:
        out = []
        for r in ranks:
            vals = [x[field] for x in rows if x['org_rank'] == r]
            out.append(float(np.mean(vals)) if vals else float('nan'))
        return out

    ranks_10 = list(range(0, 10))

    fc_full = _means_by_rank(fix_rows_full, 'fix_count')
    fc_clean = _means_by_rank(fix_rows_clean, 'fix_count')
    dw_full = [v / 1000 for v in _means_by_rank(fix_rows_full, 'fix_total_ms')]
    dw_clean = [v / 1000 for v in _means_by_rank(fix_rows_clean, 'fix_total_ms')]

    fc_full_rho, fc_full_p = _spearman(ranks_10, fc_full)
    fc_clean_rho, fc_clean_p = _spearman(ranks_10, fc_clean)
    dw_full_rho, dw_full_p = _spearman(ranks_10, dw_full)
    dw_clean_rho, dw_clean_p = _spearman(ranks_10, dw_clean)

    # ── LF/HF medians by org_rank ────────────────────────────────────────
    lfhf_full_med = [float(np.median(lfhf_full[r])) if lfhf_full[r] else float('nan')
                     for r in ranks_10]
    lfhf_clean_med = [float(np.median(lfhf_clean[r])) if lfhf_clean[r] else float('nan')
                      for r in ranks_10]
    lfhf_full_rho, lfhf_full_p = _spearman(ranks_10, lfhf_full_med)
    lfhf_clean_rho, lfhf_clean_p = _spearman(ranks_10, lfhf_clean_med)

    # Also compute LF/HF over ranks 0..10 (K4 uses 11 positions) for
    # apples-to-apples comparison with the existing K4.
    ranks_11 = list(range(0, 11))
    lfhf_full_med_11 = [float(np.median(lfhf_full[r])) if lfhf_full[r] else float('nan')
                        for r in ranks_11]
    lfhf_full_rho_11, lfhf_full_p_11 = _spearman(ranks_11, lfhf_full_med_11)

    # ── Write fixation/lfhf tables ───────────────────────────────────────
    with open(OUT_DIR / 'by_org_rank_full.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['org_rank', 'n_fix_rows', 'fix_count_mean',
                    'dwell_s_mean', 'n_lfhf', 'lfhf_median'])
        for r in ranks_10:
            n_fix = sum(1 for x in fix_rows_full if x['org_rank'] == r)
            n_lfhf = len(lfhf_full[r])
            w.writerow([r, n_fix, f'{fc_full[r]:.3f}', f'{dw_full[r]:.3f}',
                        n_lfhf, f'{lfhf_full_med[r]:.4f}'])

    with open(OUT_DIR / 'by_org_rank_clean_for_ctr.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['org_rank', 'n_fix_rows', 'fix_count_mean',
                    'dwell_s_mean', 'n_lfhf', 'lfhf_median'])
        for r in ranks_10:
            n_fix = sum(1 for x in fix_rows_clean if x['org_rank'] == r)
            n_lfhf = len(lfhf_clean[r])
            w.writerow([r, n_fix, f'{fc_clean[r]:.3f}', f'{dw_clean[r]:.3f}',
                        n_lfhf, f'{lfhf_clean_med[r]:.4f}'])

    # ── Assemble K-ID summary JSON ───────────────────────────────────────
    key_claims = {
        'K18_ctr_by_org_rank_full': {
            'measure': 'CTR by organic rank (full corpus)',
            'cohort': 'full',
            'n_trials': len(tids),
            'n_ranks': full_stats['n_points'],
            'rho': round(full_stats['ctr_rho'], 4),
            'p': full_stats['ctr_p'],
            'ranks_0_to_9_ctr': [round(x, 4) for x in full_stats['ctr']],
        },
        'K19_ctr_by_org_rank_clean': {
            'measure': 'CTR by organic rank (clean_for_ctr: plain_top ∩ n_org∈{9,10,11})',
            'cohort': 'clean_for_ctr',
            'n_trials': len(clean_tids),
            'n_ranks': clean_stats['n_points'],
            'rho': round(clean_stats['ctr_rho'], 4),
            'p': clean_stats['ctr_p'],
            'ranks_0_to_9_ctr': [round(x, 4) for x in clean_stats['ctr']],
        },
        'K20_click_share_by_org_rank_full': {
            'measure': 'Click share by organic rank (full corpus)',
            'cohort': 'full',
            'n_trials': len(tids),
            'n_ranks': full_stats['n_points'],
            'rho': round(full_stats['click_share_rho'], 4),
            'p': full_stats['click_share_p'],
            'click_share_pct': [round(x, 3) for x in full_stats['click_share_pct']],
        },
        'K21_click_share_by_org_rank_clean': {
            'measure': 'Click share by organic rank (clean_for_ctr)',
            'cohort': 'clean_for_ctr',
            'n_trials': len(clean_tids),
            'n_ranks': clean_stats['n_points'],
            'rho': round(clean_stats['click_share_rho'], 4),
            'p': clean_stats['click_share_p'],
            'click_share_pct': [round(x, 3) for x in clean_stats['click_share_pct']],
        },
        'K22_fix_count_by_org_rank_full': {
            'measure': 'Fixation count × organic rank (full corpus)',
            'n_ranks': 10,
            'rho': round(fc_full_rho, 4),
            'p': fc_full_p,
            'means': [round(x, 3) for x in fc_full],
        },
        'K23_fix_count_by_org_rank_clean': {
            'measure': 'Fixation count × organic rank (clean_for_ctr)',
            'n_ranks': 10,
            'rho': round(fc_clean_rho, 4),
            'p': fc_clean_p,
            'means': [round(x, 3) for x in fc_clean],
        },
        'K24_dwell_by_org_rank_full': {
            'measure': 'Total dwell × organic rank (full corpus)',
            'n_ranks': 10,
            'rho': round(dw_full_rho, 4),
            'p': dw_full_p,
            'means_s': [round(x, 3) for x in dw_full],
        },
        'K25_dwell_by_org_rank_clean': {
            'measure': 'Total dwell × organic rank (clean_for_ctr)',
            'n_ranks': 10,
            'rho': round(dw_clean_rho, 4),
            'p': dw_clean_p,
            'means_s': [round(x, 3) for x in dw_clean],
        },
        'K26_lfhf_by_org_rank_full_0_9': {
            'measure': 'Butterworth LF/HF × organic rank (full corpus, ranks 0–9)',
            'n_ranks': 10,
            'rho': round(lfhf_full_rho, 4),
            'p': lfhf_full_p,
            'medians': [round(x, 3) for x in lfhf_full_med],
            'sample_sizes': [len(lfhf_full[r]) for r in ranks_10],
        },
        'K27_lfhf_by_org_rank_full_0_10': {
            'measure': 'Butterworth LF/HF × organic rank (full corpus, ranks 0–10, '
                       'for parity with existing K4 which uses 11 positions)',
            'n_ranks': 11,
            'rho': round(lfhf_full_rho_11, 4),
            'p': lfhf_full_p_11,
            'medians': [round(x, 3) for x in lfhf_full_med_11],
            'sample_sizes': [len(lfhf_full[r]) for r in ranks_11],
        },
        'K28_lfhf_by_org_rank_clean_0_9': {
            'measure': 'Butterworth LF/HF × organic rank (clean_for_ctr, ranks 0–9)',
            'n_ranks': 10,
            'rho': round(lfhf_clean_rho, 4),
            'p': lfhf_clean_p,
            'medians': [round(x, 3) for x in lfhf_clean_med],
            'sample_sizes': [len(lfhf_clean[r]) for r in ranks_10],
        },
    }

    diagnostics = {
        'n_trials_full': len(tids),
        'n_trials_clean_for_ctr': len(clean_tids),
        'full_clicks_in_ad_slot': full_clicks_in_ad,
        'full_clicks_no_rank': full_clicks_no_rank,
        'clean_clicks_in_ad_slot': clean_clicks_in_ad,
        'clean_clicks_no_rank': clean_clicks_no_rank,
        'bw_missing': n_bw_missing,
        'fix_missing': n_fix_missing,
        'elapsed_s': round(elapsed, 1),
    }

    (OUT_DIR / 'key_claims_summary.json').write_text(
        json.dumps({'key_claims': key_claims, 'diagnostics': diagnostics},
                   indent=2))

    # ── Print terse report ───────────────────────────────────────────────
    print()
    print('── Clicks in ad slots (diagnostic) ──')
    print(f'  full   : {full_clicks_in_ad} clicks in ads  ({full_clicks_no_rank} no-rank)')
    print(f'  clean  : {clean_clicks_in_ad} clicks in ads  ({clean_clicks_no_rank} no-rank)')
    print()
    print('── K-ID values ──')
    for k, v in key_claims.items():
        rho = v['rho']
        p = v['p']
        if p is not None and not (isinstance(p, float) and np.isnan(p)):
            print(f'  {k}  rho={rho:+.4f}  p={p:.3g}')
        else:
            print(f'  {k}  rho={rho:+.4f}  p=nan')
    print()
    print('── CTR curves (ranks 0..9) ──')
    print(f'  full   CTR: {[round(x, 4) for x in full_stats["ctr"]]}')
    print(f'  clean  CTR: {[round(x, 4) for x in clean_stats["ctr"]]}')
    print(f'  full   share%: {[round(x, 2) for x in full_stats["click_share_pct"]]}')
    print(f'  clean  share%: {[round(x, 2) for x in clean_stats["click_share_pct"]]}')
    print()
    print(f'[nb23-org] outputs in {OUT_DIR}')


if __name__ == '__main__':
    main()
