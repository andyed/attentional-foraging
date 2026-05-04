"""Does LF/HF predict click at the (trial, position) level?

Beyond the naive argmax test. Computes per-(trial, pos) LF/HF features under
organic_hybrid attribution:
  - lfhf_first       — first-pass segment LF/HF
  - lfhf_return      — return-visit segment LF/HF (None if no return)
  - lfhf_max         — max(first, return)
  - lfhf_delta       — return - first (None if no return)

Then tests:
  - AUC of each feature alone for predicting was_clicked
  - LOSO logistic regression with all LF/HF features

Output: scripts/output/lfhf_click_prediction_test/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_click_prediction_test.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.signal import butter, sosfiltfilt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_click_prediction_test'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

FS = 150
LF_SOS = butter(4, 1.6, btype='low', fs=FS, output='sos')
HF_SOS = butter(4, (1.6, 4.0), btype='band', fs=FS, output='sos')
MIN_SAMPLES = 150


def visit_segments(fix, tops, n_res):
    first, ret = {}, {}
    max_seen = -1
    for f in fix:
        pos = assign_fixation_to_position(f['y'], tops, n_res)
        if pos is None or pos < 0:
            continue
        win = (f['t'], f['t'] + f['d'])
        if pos < max_seen:
            ret.setdefault(pos, []).append(win)
        else:
            first.setdefault(pos, []).append(win)
            if pos > max_seen:
                max_seen = pos
    return first, ret


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    return float(lf_p / hf_p) if hf_p >= 1e-20 else None


def process_trial(tid):
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return []
    ts = np.asarray(pupil['ts'])
    pd = np.asarray(pupil['clean_pd'])
    if len(pd) < MIN_SAMPLES * 2:
        return []
    lf_sig = sosfiltfilt(LF_SOS, pd)
    hf_sig = sosfiltfilt(HF_SOS, pd)

    fix = load_fixations(tid)
    if not fix:
        return []
    tops = _hybrid_aoi_tops(tid)
    if not tops:
        return []
    n_res = len(tops)

    first, ret = visit_segments(fix, tops, n_res)
    rows = []
    for pos, windows in first.items():
        lf_first = lfhf_for_windows(lf_sig, hf_sig, ts, windows)
        ret_w = ret.get(pos)
        lf_return = lfhf_for_windows(lf_sig, hf_sig, ts, ret_w) if ret_w else None
        rows.append({
            'trial_id': tid, 'pid': tid.split('-')[0], 'pos': pos,
            'lfhf_first': lf_first, 'lfhf_return': lf_return,
        })
    return rows


def main():
    print('[lfhf-click] LF/HF features for click prediction (organic_hybrid)',
          file=sys.stderr)

    # Load was_clicked from hybrid features
    feats = json.load(open(DATA / 'cursor-approach-features-organic-hybrid.json'))
    by_trial_pos = {(r['trial_id'], r['position']): r for r in feats}
    print(f'  hybrid feature rows: {len(feats):,}', file=sys.stderr)

    trial_ids = sorted({r['trial_id'] for r in feats})
    print(f'  trials: {len(trial_ids):,}', file=sys.stderr)

    rows = []
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        for r in process_trial(tid):
            key = (r['trial_id'], r['pos'])
            feat_row = by_trial_pos.get(key)
            if feat_row is None or r['lfhf_first'] is None:
                continue
            r['was_clicked'] = bool(feat_row.get('was_clicked', False))
            r['n_fixations'] = feat_row.get('n_fixations')
            r['total_dwell_ms'] = feat_row.get('total_dwell_ms')
            r['lfhf_max'] = max(r['lfhf_first'], r['lfhf_return'] or r['lfhf_first'])
            r['lfhf_delta'] = (r['lfhf_return'] - r['lfhf_first']
                               if r['lfhf_return'] is not None else None)
            r['has_return'] = r['lfhf_return'] is not None
            rows.append(r)

    print(f'\n  records with valid first-pass LF/HF + click label: {len(rows):,}',
          file=sys.stderr)
    n_clicked = sum(1 for r in rows if r['was_clicked'])
    n_unclicked = len(rows) - n_clicked
    print(f'  clicked: {n_clicked:,}  not-clicked: {n_unclicked:,}', file=sys.stderr)

    y = np.array([r['was_clicked'] for r in rows], dtype=int)

    # ── Feature-by-feature AUC ──
    feature_aucs = {}
    for feat_name in ['lfhf_first', 'lfhf_return', 'lfhf_max', 'lfhf_delta']:
        vals = [r[feat_name] for r in rows]
        mask = np.array([v is not None for v in vals])
        n_avail = int(mask.sum())
        scores = np.array([v if v is not None else 0.0 for v in vals])
        if n_avail < 100 or len(np.unique(y[mask])) < 2:
            feature_aucs[feat_name] = {'n': n_avail, 'auc': None}
            continue
        try:
            auc = float(roc_auc_score(y[mask], scores[mask]))
        except ValueError:
            auc = None
        feature_aucs[feat_name] = {'n': n_avail, 'auc': auc}
        print(f'  {feat_name}: n={n_avail:,}  AUC={auc:.3f}' if auc else
              f'  {feat_name}: n={n_avail:,}  AUC=undefined', file=sys.stderr)

    # ── LOSO logistic on LF/HF features ──
    # Use lfhf_first, lfhf_max, plus has_return as binary indicator.
    # Skip lfhf_return / lfhf_delta (lots of None).
    pids = sorted({r['pid'] for r in rows})
    fold_aucs = []
    print(f'\n  Running LOSO logistic on [lfhf_first, lfhf_max, has_return]', file=sys.stderr)
    for held_out in pids:
        X_train, y_train, X_test, y_test = [], [], [], []
        for r in rows:
            x = [r['lfhf_first'], r['lfhf_max'], 1.0 if r['has_return'] else 0.0]
            tgt = X_test if r['pid'] == held_out else X_train
            tgt_y = y_test if r['pid'] == held_out else y_train
            tgt.append(x); tgt_y.append(r['was_clicked'])
        if not X_test or not X_train or len(set(y_test)) < 2:
            continue
        X_train, y_train = np.array(X_train), np.array(y_train, dtype=int)
        X_test, y_test = np.array(X_test), np.array(y_test, dtype=int)
        if len(set(y_train)) < 2:
            continue
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        clf = LogisticRegression(max_iter=200, class_weight='balanced')
        clf.fit(X_train_s, y_train)
        scores = clf.predict_proba(X_test_s)[:, 1]
        try:
            fold_aucs.append(float(roc_auc_score(y_test, scores)))
        except ValueError:
            pass

    loso_auc = float(np.mean(fold_aucs)) if fold_aucs else None
    loso_std = float(np.std(fold_aucs)) if fold_aucs else None

    print(f'\n  LOSO LF/HF-only logistic: AUC = {loso_auc:.3f} ± {loso_std:.3f} '
          f'across {len(fold_aucs)} folds', file=sys.stderr)

    # ── Compare to baseline: trivial features (n_fixations, total_dwell_ms) ──
    print(f'\n  Sanity baseline: dwell-only logistic', file=sys.stderr)
    baseline_aucs = []
    for held_out in pids:
        X_train, y_train, X_test, y_test = [], [], [], []
        for r in rows:
            x = [r.get('n_fixations') or 0, r.get('total_dwell_ms') or 0]
            tgt = X_test if r['pid'] == held_out else X_train
            tgt_y = y_test if r['pid'] == held_out else y_train
            tgt.append(x); tgt_y.append(r['was_clicked'])
        if not X_test or not X_train or len(set(y_test)) < 2 or len(set(y_train)) < 2:
            continue
        X_train, y_train = np.array(X_train), np.array(y_train, dtype=int)
        X_test, y_test = np.array(X_test), np.array(y_test, dtype=int)
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        clf = LogisticRegression(max_iter=200, class_weight='balanced')
        clf.fit(X_train_s, y_train)
        scores = clf.predict_proba(X_test_s)[:, 1]
        try:
            baseline_aucs.append(float(roc_auc_score(y_test, scores)))
        except ValueError:
            pass
    baseline_auc = float(np.mean(baseline_aucs)) if baseline_aucs else None
    baseline_std = float(np.std(baseline_aucs)) if baseline_aucs else None
    print(f'  LOSO dwell-only logistic: AUC = {baseline_auc:.3f} ± {baseline_std:.3f}',
          file=sys.stderr)

    # ── Combined: LF/HF + dwell ──
    combined_aucs = []
    print(f'\n  LOSO combined [lfhf_first, lfhf_max, has_return, n_fixations, total_dwell_ms]',
          file=sys.stderr)
    for held_out in pids:
        X_train, y_train, X_test, y_test = [], [], [], []
        for r in rows:
            x = [r['lfhf_first'], r['lfhf_max'],
                 1.0 if r['has_return'] else 0.0,
                 r.get('n_fixations') or 0, r.get('total_dwell_ms') or 0]
            tgt = X_test if r['pid'] == held_out else X_train
            tgt_y = y_test if r['pid'] == held_out else y_train
            tgt.append(x); tgt_y.append(r['was_clicked'])
        if not X_test or not X_train or len(set(y_test)) < 2 or len(set(y_train)) < 2:
            continue
        X_train, y_train = np.array(X_train), np.array(y_train, dtype=int)
        X_test, y_test = np.array(X_test), np.array(y_test, dtype=int)
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        clf = LogisticRegression(max_iter=200, class_weight='balanced')
        clf.fit(X_train_s, y_train)
        scores = clf.predict_proba(X_test_s)[:, 1]
        try:
            combined_aucs.append(float(roc_auc_score(y_test, scores)))
        except ValueError:
            pass
    combined_auc = float(np.mean(combined_aucs)) if combined_aucs else None
    combined_std = float(np.std(combined_aucs)) if combined_aucs else None
    print(f'  LOSO combined logistic: AUC = {combined_auc:.3f} ± {combined_std:.3f}',
          file=sys.stderr)

    out = {
        'attribution': 'organic_hybrid',
        'n_records': len(rows),
        'n_clicked': n_clicked,
        'n_unclicked': n_unclicked,
        'feature_aucs': feature_aucs,
        'loso_lfhf_only': {'auc_mean': loso_auc, 'auc_std': loso_std,
                            'n_folds': len(fold_aucs)},
        'loso_dwell_only_baseline': {'auc_mean': baseline_auc, 'auc_std': baseline_std,
                                       'n_folds': len(baseline_aucs)},
        'loso_combined': {'auc_mean': combined_auc, 'auc_std': combined_std,
                           'n_folds': len(combined_aucs)},
    }

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(out, indent=2))

    lines = [
        '# LF/HF features for click prediction (organic_hybrid)\n',
        '_Generated 2026-05-03 by `scripts/lfhf_click_prediction_test.py`._\n',
        f'**Records**: {len(rows):,} (clicked: {n_clicked:,}, not-clicked: {n_unclicked:,})\n',
        '## Per-feature AUC (each feature alone vs was_clicked)\n',
        '| Feature | n records | AUC |',
        '|---|---|---|',
    ]
    for fname, info in feature_aucs.items():
        auc = info['auc']
        auc_str = f'{auc:.3f}' if auc is not None else '—'
        lines.append(f'| `{fname}` | {info["n"]:,} | {auc_str} |')

    lines.extend([
        '\n## LOSO logistic regression — LF/HF features only\n',
        f'Features: `[lfhf_first, lfhf_max, has_return]`\n',
        f'**LOSO AUC = {loso_auc:.3f} ± {loso_std:.3f}** ({len(fold_aucs)} folds)\n',
        '\n## Sanity baseline — dwell only\n',
        f'Features: `[n_fixations, total_dwell_ms]`\n',
        f'**LOSO AUC = {baseline_auc:.3f} ± {baseline_std:.3f}** ({len(baseline_aucs)} folds)\n',
        '\n## Combined — LF/HF + dwell\n',
        f'Features: `[lfhf_first, lfhf_max, has_return, n_fixations, total_dwell_ms]`\n',
        f'**LOSO AUC = {combined_auc:.3f} ± {combined_std:.3f}** ({len(combined_aucs)} folds)\n',
        '\n## Verdict template (fill in after run)\n',
        '- LF/HF alone: weak/moderate/strong (AUC vs 0.5)',
        '- LF/HF on top of dwell: lift / no lift',
        '- Hybrid M3 cursor-approach baseline (NB21:K-bbox-3) is AUC 0.870 — combining LF/HF with that suite is the next step if these results justify it.',
    ])

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
