"""STUB-C component: per-feature deferred-vs-eval-rejected dissociation
table for §4.5 of paper-v4, re-derived under bbox-organic attribution.

Inputs (under [organic]):
  cursor-approach-features-organic.json    (was_clicked, position, trial_id)
  regression_labels_cache_organic.json     (will_regress, parallel to above)
  Trajectory features per (trial, organic_pos) computed via
  nb30_scroll_trajectory.compute_features_for_trial(attribution='organic')

Output:
  scripts/output/aoi-consumer-cascade/nb28_per_feature_dissociation_organic.json
  + stdout MW table

The legacy table (paper-v3 lines 411-420) shipped under [absolute] from
NB30. Six features tested in deferred-vs-eval-rejected MW two-sided:
  n_reversals, min_abs_velocity, vt_any_ms, vt_center_ms,
  avg_viewport_y_px, max_overlap_frac

Run:
  .venv/bin/python scripts/nb28_per_feature_dissociation_organic.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from nb30_scroll_trajectory import compute_features_for_trial  # noqa: E402

FEAT_PATH = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
LABELS_PATH = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'
APPROACH_THRESHOLD_PX = 100.0


def cohens_d(a, b):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    b = np.asarray(b, float); b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def main():
    print(f'[load] {FEAT_PATH.name}', file=sys.stderr)
    features = json.load(open(FEAT_PATH))
    labels = json.load(open(LABELS_PATH))
    assert len(features) == len(labels)

    # Index by (trial, position)
    feat_by_tp = {(r['trial_id'], int(r['position'])): r for r in features}
    wr_by_tp = {(features[i]['trial_id'], int(features[i]['position'])): bool(labels[i])
                for i in range(len(features))}

    # Compute trajectory features per trial, per organic position
    trial_ids = sorted({r['trial_id'] for r in features})
    n_trials = len(trial_ids)
    print(f'[walk] {n_trials:,} trials with cursor-approach features', file=sys.stderr)

    # Per (trial, organic_pos): trajectory features dict
    traj_by_tp: dict[tuple[str, int], dict] = {}
    n_skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{n_trials}', file=sys.stderr)
        per_pos = compute_features_for_trial(tid, attribution='organic')
        if per_pos is None:
            n_skipped += 1
            continue
        for pos, traj in enumerate(per_pos):
            traj_by_tp[(tid, pos)] = traj

    print(f'  {len(traj_by_tp):,} (trial, organic_pos) trajectory records '
          f'(skipped {n_skipped} trials)', file=sys.stderr)

    # Build records: approached-non-click subset
    records = []
    for (tid, pos), feat in feat_by_tp.items():
        if feat.get('was_clicked', False):
            continue
        if (tid, pos) not in traj_by_tp:
            continue
        if float(feat.get('min_dist', 1e9)) >= APPROACH_THRESHOLD_PX:
            continue  # not approached
        traj = traj_by_tp[(tid, pos)]
        wr = wr_by_tp.get((tid, pos), False)
        records.append({'wr': wr, 'feat': feat, 'traj': traj})

    n_def = sum(1 for r in records if r['wr'])
    n_rej = sum(1 for r in records if not r['wr'])
    print(f'\n  approached non-click subset: n = {len(records):,}  '
          f'(deferred = {n_def:,}; evaluated-rejected = {n_rej:,})', file=sys.stderr)

    # Six features (public names returned by compute_features_for_trial)
    metrics = [
        ('n_reversals',      'n_reversals (EWM reload)',                'n_reversals'),
        ('min_abs_velocity', 'min_abs_velocity_px_per_s (EWM stabilize)', 'min_abs_velocity'),
        ('vt_any_ms',        'vt_any_ms (EWM residence)',               'vt_any'),
        ('vt_center_ms',     'vt_center_ms (foveal zone)',              'vt_center_ms'),
        ('avg_viewport_y',   'avg_viewport_y_px (buffer position)',     'avg_viewport_y'),
        ('max_overlap_frac', 'max_overlap_frac',                        'max_overlap_frac'),
    ]

    print(f'\n=== Per-feature DEFERRED-vs-EVAL-REJECTED dissociation under [organic] ===')
    print(f'{"feature":>34s}  {"def median":>11s}  {"rej median":>11s}  {"d":>7s}  {"MW p (two-sided)":>20s}')
    table_rows = []
    for short, label, key_field in metrics:
        def_vals = []; rej_vals = []
        for r in records:
            val = r['traj'].get(key_field, np.nan)
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if not np.isfinite(v):
                continue
            if r['wr']:
                def_vals.append(v)
            else:
                rej_vals.append(v)
        d_arr = np.array(def_vals); r_arr = np.array(rej_vals)
        if len(d_arr) < 10 or len(r_arr) < 10:
            print(f'  {label:>34s}  insufficient n ({len(d_arr)} / {len(r_arr)})')
            continue
        u, p = stats.mannwhitneyu(d_arr, r_arr, alternative='two-sided')
        d_eff = cohens_d(d_arr, r_arr)
        med_d = float(np.median(d_arr))
        med_r = float(np.median(r_arr))
        sig = '***' if p < 1e-9 else ('**' if p < 1e-4 else ('*' if p < 0.05 else ''))
        print(f'  {label:>34s}  {med_d:>11.3f}  {med_r:>11.3f}  {d_eff:>+7.3f}  {p:>13.3e}  {sig}')
        table_rows.append({
            'feature': short, 'label': label,
            'n_def': len(d_arr), 'n_rej': len(r_arr),
            'median_def': med_d, 'median_rej': med_r,
            'mean_def': float(d_arr.mean()), 'mean_rej': float(r_arr.mean()),
            'cohens_d': float(d_eff), 'mw_p': float(p),
        })

    # Save
    out = {
        'attribution': 'organic',
        'population': 'approached non-click (min_dist < 100 px), under bbox-organic',
        'n_records': len(records),
        'n_deferred': n_def,
        'n_eval_rejected': n_rej,
        'rows': table_rows,
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/nb28_per_feature_dissociation_organic.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
