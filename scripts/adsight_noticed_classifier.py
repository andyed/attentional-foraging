"""Per-etype 'noticed' binary classifier — AdSight (Villaizán-Vallelado et al.,
SIGIR '25) replication at 9-etype granularity using LightGBM + LOSO 47-fold CV
on the AllSERP typed_gapfill substrate.

Per CIKM 2026 path-1 plan: AdSight pooled the SERP into 4 buckets (direct-top,
direct-right, organic-top, organic-bottom) and ran one binary classifier per
bucket from cursor trajectories. typed_gapfill exposes 9+ element types
(organic, dd_top, native_ad, image_pack, paa, knowledge_panel, top_places,
unknown_widget, other_widget, plus dd_right and chrome).

Three feature sets are run per etype, and additionally the same etypes pooled
back into AdSight's four buckets so the granularity claim is decomposable
holding everything else constant:

  full          — 12 cursor features (per-AOI distances, dwell-in-proximity,
                  AOI metadata, position, plus three trial-level cursor
                  aggregates: trial_cursor_path_px, trial_duration_ms,
                  n_aois_on_trial)
  per_aoi_only  — drops the three trial-level features (rigor-audit ablation
                  to verify per-etype claims do not collapse onto trial-level
                  signal alone)

Reports: pooled out-of-fold AUC + per-fold AUC mean ± SD across the 47 LOSO
folds (one fold per participant). The per-fold SD lets a reader compare
against external work (e.g. attcur 5-seed mean ± SD).

Source features:
  AdSERP/data/adsight-noticed-features-typed-gapfill.json
  (built by scripts/adsight_noticed_features.py)

Output:
  scripts/output/adsight_noticed_replication/summary.json
  scripts/output/adsight_noticed_replication/per_etype_table.csv
  scripts/output/adsight_noticed_replication/buckets_table.csv
"""
from __future__ import annotations

import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    average_precision_score, f1_score, roc_auc_score,
)

warnings.filterwarnings('ignore', category=UserWarning)

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/adsight-noticed-features-typed-gapfill.json'
OUT_DIR = ROOT / 'scripts/output/adsight_noticed_replication'
OUT_DIR.mkdir(parents=True, exist_ok=True)

PER_AOI_FEATS = [
    'min_dist_aoi', 'mean_dist_aoi', 'final_dist_aoi',
    'dwell_in_proximity_ms',
    'aoi_x', 'aoi_y', 'aoi_width', 'aoi_height',
    'position',
]
TRIAL_LEVEL_FEATS = [
    'trial_cursor_path_px', 'trial_duration_ms', 'n_aois_on_trial',
]
FULL_FEATS = PER_AOI_FEATS + TRIAL_LEVEL_FEATS

# AdSight published 4-bucket reference (Table 2; Villaizán-Vallelado SIGIR '25).
ADSIGHT_REF = {
    'direct-top':     {'auc': 0.8079, 'fixation_rate': 0.42},
    'direct-right':   {'auc': 0.8172, 'fixation_rate': 0.46},
    'organic-top':    {'auc': 0.8795, 'fixation_rate': 0.44},
    'organic-bottom': {'auc': 0.8585, 'fixation_rate': 0.29},
}

# Etype → AdSight 4-bucket pool. We keep `chrome` and `unknown_widget` /
# `other_widget` out of the bucket pool — they have no AdSight analogue and
# pooling would introduce a denominator mismatch.
def adsight_bucket(rec: dict) -> str | None:
    e = rec['etype']
    if e == 'dd_top' or e == 'native_ad':
        return 'direct-top'
    if e == 'dd_right':
        return 'direct-right'
    # organic-top vs organic-bottom: viewport split. AdSERP screens are
    # ~1080 px tall; AdSight's split is by viewport so anything with
    # aoi_y < 1080 is top, else bottom. Apply to the typed organic
    # surfaces (organic, image_pack, knowledge_panel, paa, top_places).
    organic_like = {'organic', 'image_pack', 'knowledge_panel', 'paa',
                    'top_places'}
    if e in organic_like:
        return 'organic-top' if rec['aoi_y'] < 1080.0 else 'organic-bottom'
    return None  # chrome / unknown_widget / other_widget excluded


# Min sample size to attempt classification (some etypes are sparse).
MIN_N = 50
MIN_POS = 5


def _per_fold_auc(y, pooled, pid):
    """Compute per-fold AUC (one fold per participant). Returns list of
    finite AUC values; folds with degenerate y_te (all-positive or
    all-negative) are skipped."""
    aucs = []
    for p in sorted(set(pid)):
        mask = (pid == p) & np.isfinite(pooled)
        if mask.sum() < 2:
            continue
        yt = y[mask]
        if len(set(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, pooled[mask]))
    return aucs


def loso_fit(rows: list[dict], features: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    """Run LOSO 47-fold over rows. Returns (y, pooled, pid, n_folds_used,
    n_folds_skipped)."""
    n = len(rows)
    y = np.array([r['noticed'] for r in rows], dtype=int)
    X = np.array([[float(r.get(f, 0.0) or 0.0) for f in features]
                  for r in rows], dtype=float)
    pid = np.array([r['trial_id'].split('-')[0] for r in rows])
    pooled = np.full(n, np.nan, dtype=float)
    parts = sorted(set(pid))
    skipped_folds = 0
    for p in parts:
        tr = pid != p
        te = pid == p
        y_tr = y[tr]
        if y_tr.sum() == 0 or y_tr.sum() == y_tr.size:
            skipped_folds += 1
            continue
        clf = LGBMClassifier(
            n_estimators=200, learning_rate=0.05,
            num_leaves=31, min_data_in_leaf=20,
            verbose=-1,
        )
        clf.fit(X[tr], y_tr)
        pooled[te] = clf.predict_proba(X[te])[:, 1]
    return y, pooled, pid, len(parts) - skipped_folds, skipped_folds


def evaluate(rows: list[dict], features: list[str]) -> dict:
    n = len(rows)
    if n < MIN_N:
        return {'n': n, 'note': 'too few rows', 'skipped': True}
    y_tot = sum(r['noticed'] for r in rows)
    if y_tot < MIN_POS or (n - y_tot) < MIN_POS:
        return {'n': n, 'n_pos': int(y_tot), 'n_neg': n - int(y_tot),
                'note': 'class too sparse', 'skipped': True}
    y, pooled, pid, n_used, n_skip = loso_fit(rows, features)
    valid = np.isfinite(pooled)
    if valid.sum() < MIN_N or len(set(y[valid])) < 2:
        return {'n': n, 'note': 'pooled folds insufficient', 'skipped': True}
    yt = y[valid]; yp = pooled[valid]
    pooled_auc = float(roc_auc_score(yt, yp))
    pooled_ap = float(average_precision_score(yt, yp))
    pooled_f1 = float(f1_score(yt, (yp >= 0.5).astype(int)))
    fold_aucs = _per_fold_auc(y, pooled, pid)
    return {
        'n': n,
        'n_pos': int(yt.sum()),
        'n_neg': int((1 - yt).sum()),
        'base_rate': float(yt.mean()),
        'auc_pooled': pooled_auc,
        'ap_pooled': pooled_ap,
        'f1@0.5_pooled': pooled_f1,
        'auc_per_fold_mean': float(np.mean(fold_aucs)) if fold_aucs else None,
        'auc_per_fold_sd': float(np.std(fold_aucs, ddof=1)) if len(fold_aucs) > 1 else None,
        'n_folds_with_auc': len(fold_aucs),
        'n_folds_used': n_used,
        'n_folds_skipped': n_skip,
        'skipped': False,
    }


def main() -> None:
    print(f'[load] {FEAT.name}', file=sys.stderr)
    rows = json.load(open(FEAT))
    n_part = len({r['trial_id'].split('-')[0] for r in rows})
    n_trial = len({r['trial_id'] for r in rows})
    print(f'  rows: {len(rows):,}  trials: {n_trial:,}  participants: {n_part}',
          file=sys.stderr)

    etypes = sorted(set(r['etype'] for r in rows))
    print(f'  etypes: {etypes}', file=sys.stderr)

    # ── per-etype, two feature sets ──────────────────────────────────────
    print('\n[fit] per-etype LightGBM, LOSO 47-fold', file=sys.stderr)
    per_etype: dict[str, dict] = {}
    for e in etypes:
        sub = [r for r in rows if r['etype'] == e]
        full = evaluate(sub, FULL_FEATS)
        per_aoi = evaluate(sub, PER_AOI_FEATS)
        per_etype[e] = {'full': full, 'per_aoi_only': per_aoi}
        if full.get('skipped'):
            print(f'  {e:>20s}  full SKIPPED ({full.get("note")})', file=sys.stderr)
        else:
            f = full
            pa = per_aoi
            sd = f'±{f["auc_per_fold_sd"]:.3f}' if f['auc_per_fold_sd'] is not None else '   n/a'
            pa_auc = pa['auc_pooled'] if not pa.get('skipped') else None
            pa_str = f'{pa_auc:.4f}' if pa_auc is not None else '   skip'
            print(f'  {e:>20s}  n={f["n"]:6d}  pos={f["n_pos"]:5d}  '
                  f'base={f["base_rate"]:.3f}  '
                  f'AUCpool={f["auc_pooled"]:.4f}  '
                  f'AUCfold={f["auc_per_fold_mean"]:.4f}{sd}  '
                  f'AUCnoTrial={pa_str}',
                  file=sys.stderr)

    # ── pooled to AdSight's 4 buckets, full feature set ──────────────────
    print('\n[fit] AdSight 4-bucket pool, LOSO 47-fold (full features)',
          file=sys.stderr)
    bucket_results: dict[str, dict] = {}
    for b in ['direct-top', 'direct-right', 'organic-top', 'organic-bottom']:
        sub = [r for r in rows if adsight_bucket(r) == b]
        res = evaluate(sub, FULL_FEATS)
        bucket_results[b] = res
        if res.get('skipped'):
            print(f'  {b:>15s}  SKIPPED ({res.get("note")})', file=sys.stderr)
        else:
            sd = f'±{res["auc_per_fold_sd"]:.3f}' if res['auc_per_fold_sd'] is not None else '   n/a'
            ref = ADSIGHT_REF[b]
            print(f'  {b:>15s}  n={res["n"]:6d}  base={res["base_rate"]:.3f}  '
                  f'AUCpool={res["auc_pooled"]:.4f}  '
                  f'AUCfold={res["auc_per_fold_mean"]:.4f}{sd}  '
                  f'(AdSight Seq2Seq: AUC={ref["auc"]:.4f})',
                  file=sys.stderr)

    summary = {
        'features': {
            'full': FULL_FEATS,
            'per_aoi_only': PER_AOI_FEATS,
            'trial_level_dropped_in_per_aoi_only': TRIAL_LEVEL_FEATS,
        },
        'method': 'LightGBM binary classifier, LOSO by participant '
                  '(47-fold). Reports pooled-out-of-fold AUC and per-fold '
                  'AUC (mean ± SD across folds).',
        'source': str(FEAT.relative_to(ROOT)),
        'cohort': {
            'n_rows': len(rows),
            'n_trials': n_trial,
            'n_participants': n_part,
            'note': 'main-axis trials only; the AdSight paper reports 2,732 '
                    'trials (2,776 minus 44 malformed); we report 2,546 '
                    '(2,776 minus 230 hard-error main-axis-click '
                    'exclusions). Cohorts are not identical.',
        },
        'adsight_reference_table_2': ADSIGHT_REF,
        'per_etype': per_etype,
        'bucketed_to_adsight': bucket_results,
    }
    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Per-etype CSV: full + per-aoi-only side by side for easy review.
    with open(OUT_DIR / 'per_etype_table.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['etype', 'n', 'n_pos', 'base_rate',
                    'full_auc_pool', 'full_auc_fold_mean', 'full_auc_fold_sd',
                    'per_aoi_auc_pool', 'delta_drop_trial_level',
                    'n_folds_with_auc'])
        for e, both in per_etype.items():
            f_, p_ = both['full'], both['per_aoi_only']
            if f_.get('skipped'):
                w.writerow([e, f_.get('n', 0), '', '', '', '', '', '', '', ''])
                continue
            full_auc = f_['auc_pooled']
            pa_auc = p_['auc_pooled'] if not p_.get('skipped') else None
            delta = f'{full_auc - pa_auc:+.4f}' if pa_auc is not None else ''
            w.writerow([
                e, f_['n'], f_['n_pos'], f'{f_["base_rate"]:.4f}',
                f'{full_auc:.4f}',
                f'{f_["auc_per_fold_mean"]:.4f}',
                f'{f_["auc_per_fold_sd"]:.4f}' if f_['auc_per_fold_sd'] is not None else '',
                f'{pa_auc:.4f}' if pa_auc is not None else '',
                delta,
                f_['n_folds_with_auc'],
            ])

    # Bucket CSV with AdSight reference column.
    with open(OUT_DIR / 'buckets_table.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['bucket', 'n', 'n_pos', 'base_rate',
                    'auc_pool', 'auc_fold_mean', 'auc_fold_sd',
                    'adsight_auc', 'delta_vs_adsight',
                    'adsight_fixation_rate', 'n_folds_with_auc'])
        for b, r in bucket_results.items():
            ref = ADSIGHT_REF[b]
            if r.get('skipped'):
                w.writerow([b, r.get('n', 0), '', '', '', '', '',
                            f'{ref["auc"]:.4f}', '',
                            f'{ref["fixation_rate"]:.2f}', ''])
                continue
            delta = r['auc_pooled'] - ref['auc']
            w.writerow([
                b, r['n'], r['n_pos'], f'{r["base_rate"]:.4f}',
                f'{r["auc_pooled"]:.4f}',
                f'{r["auc_per_fold_mean"]:.4f}',
                f'{r["auc_per_fold_sd"]:.4f}' if r['auc_per_fold_sd'] is not None else '',
                f'{ref["auc"]:.4f}',
                f'{delta:+.4f}',
                f'{ref["fixation_rate"]:.2f}',
                r['n_folds_with_auc'],
            ])

    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}',
          file=sys.stderr)
    print(f'[out] {(OUT_DIR / "per_etype_table.csv").relative_to(ROOT)}',
          file=sys.stderr)
    print(f'[out] {(OUT_DIR / "buckets_table.csv").relative_to(ROOT)}',
          file=sys.stderr)


if __name__ == '__main__':
    main()
