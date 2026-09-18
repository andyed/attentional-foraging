"""Retrain and export the deployed M5 deferred-class detector on the cursor-only stream.

Replaces approach-retreat/scripts/models/m5_final_model.json (2026-05-02), which
was trained on fixation-selected rows with gaze-to-cursor distances and
fixation-weighted dwell (see docs/ablations/deferred_drop_decomposition.md:
on identical rows and labels those features score 0.771 and the tracker's
cursor-only features 0.665; the old features carried part of the gaze-return
label). This producer trains on exactly what m5_inference.py measures at
runtime: the tracker's one-dimensional cursor-to-centre distance on native
mousemove events, press-anchored buf500, seven features (no final_dist /
retreat_dist).

Protocol (identical to m4_cursor_only_downstream.py section 4.3, whose helpers
are imported rather than copied):
  rows    = cursor-only-typed-features-mousedown.json, conditions buf500
  label   = NB22 gaze-regression label, re-keyed by (trial, position)
  pool    = approached (min_dist < 100 px) AND not clicked
  LOSO    = 47-fold, StandardScaler + LogisticRegression(balanced, C=1.0, max_iter=5000)
  GATE    = pooled OOF AUC must equal m4_cursor_only_downstream/summary.json
            section_4_3.deployable_M4_7.pooled_auc to 1e-6, else abort
  p*      = Youden-J on the OOF probabilities
  export  = full-data refit (scaler + LR on all pool rows), same JSON schema
            as m5_final_model.json plus provenance

Run from attentional-foraging:
  .venv/bin/python scripts/export_m5_cursor_only.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from m4_cursor_aoi_rerun import APPROACH_7  # noqa: E402
from m4_cursor_only_downstream import APPROACH_PX, loso_proba, rel, sha256, summarize, youden  # noqa: E402

AR_ROOT = ROOT.parent / 'approach-retreat'
GATE_TOL = 1e-6

LINEAGE_NOTE = (
    'Replaces m5_final_model.json (2026-05-02, kept as m5_final_model.legacy-2026-05-02.json). '
    'That model was trained on the LAB organic stream from compute_cursor_approach_features.py: '
    'rows selected by fixation, the cursor sampled at fixation times, min_dist/mean_dist measured '
    'from the FIXATION position to the cursor, and dwell_in_proximity_ms weighted by fixation '
    'duration; it also consumed final_dist and retreat_dist, the two terms the click-buffer screen '
    'excludes on principle. Those features carried part of the gaze-return label they were trained '
    'to predict: on identical rows and labels they score 0.771 and the tracker\'s cursor-only '
    'features 0.665 (paired participant delta -0.068 [-0.116, -0.017]); sampling, buffer and '
    'population each move < 0.01 (attentional-foraging/docs/ablations/deferred_drop_decomposition.md). '
    'They were also not the measurement m5_inference.py computes at runtime, so the shipped scaler '
    'statistics (min_dist mean 61 px, dwell mean 1,488 ms) standardised runtime features against the '
    'wrong distribution. This model is trained on exactly the runtime measurement: the tracker\'s '
    'one-dimensional cursor-to-centre distance on native mousemove events, press-anchored 500 ms '
    'buffer, seven features. The drop from LOSO 0.769 to 0.691 is the removal of the gaze term, '
    'not a regression.'
)


def load_inputs(args):
    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar_path = ROOT / 'scripts/output' / args.summary_dir / 'summary.json'
    sidecar = json.loads(sidecar_path.read_text())
    # Same integrity check as m4_cursor_only_downstream.py: the cache must be the one
    # the aggregate sidecar was computed from.
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))

    lab_rows = json.loads(args.lab_rows.read_text())
    reg = json.loads(args.label_cache.read_text())
    assert len(lab_rows) == len(reg), 'label cache and typed LAB rows are not aligned'
    label_by_key = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}
    gaze = np.asarray([int(label_by_key.get((r['trial_id'], r['position']), False)) for r in records])
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    pool = approached & (clicked == 0)
    return cache, records, gaze, pool


def run(args):
    cache, records, gaze, pool = load_inputs(args)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    print(f'records={len(records)} pool={int(pool.sum())} deferred={int((gaze[pool] == 1).sum())} '
          f'eval_rejected={int((gaze[pool] == 0).sum())} participants={len(np.unique(pid))}')

    # ---- LOSO gate -------------------------------------------------------------------------
    oof, _ = loso_proba(records, APPROACH_7, gaze, pool)
    loso, folds = summarize(gaze, oof, pid, pool)
    expected = json.loads(args.gate_sidecar.read_text())['section_4_3']['deployable_M4_7']['pooled_auc']
    gate_diff = abs(loso['pooled_auc'] - expected)
    gate = {'expected_pooled_auc': expected, 'reproduced_pooled_auc': loso['pooled_auc'],
            'abs_diff': gate_diff, 'tolerance': GATE_TOL, 'passed': bool(gate_diff <= GATE_TOL),
            'sidecar': rel(args.gate_sidecar)}
    print(f'gate: expected {expected:.7f} reproduced {loso["pooled_auc"]:.7f} diff {gate_diff:.2e}')
    if not gate['passed']:
        sys.exit(f'ABORT: LOSO pooled AUC {loso["pooled_auc"]} != sidecar {expected} (diff {gate_diff})')

    yj = youden(gaze, oof, pool)
    print(f'youden: threshold {yj["threshold"]:.4f} precision {yj["precision"]:.3f} '
          f'recall {yj["recall"]:.3f} f1 {yj["f1"]:.3f}')

    # ---- Full-data refit ---------------------------------------------------------------------
    X = np.asarray([[r[f] for f in APPROACH_7] for r in records], dtype=float)[pool]
    y = gaze[pool]
    pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
    pipe.fit(X, y)
    scaler, lr = pipe.named_steps['standardscaler'], pipe.named_steps['logisticregression']

    # Self-check: the exported arithmetic must reproduce sklearn's predict_proba.
    z = ((X - scaler.mean_) / scaler.scale_) @ lr.coef_[0] + lr.intercept_[0]
    manual = 1.0 / (1.0 + np.exp(-z))
    max_err = float(np.abs(manual - pipe.predict_proba(X)[:, 1]).max())
    if max_err > 1e-9:
        sys.exit(f'ABORT: exported arithmetic disagrees with sklearn (max err {max_err})')

    n_pool, n_def = int(pool.sum()), int(y.sum())
    model = {
        'model': "LogisticRegression(class_weight='balanced', C=1.0) + StandardScaler",
        'trained_on': 'all 47 participants, no holdout (full-data refit); '
                      '[LAB, AdSERP, typed, cursor-only, press-anchored buf500]',
        'n_episodes': n_pool,
        'n_deferred': n_def,
        'n_eval_rej': n_pool - n_def,
        'operating_threshold': yj['threshold'],
        'operating_threshold_method': 'Youden-J on LOSO out-of-fold predictions',
        'loso_auc': loso['pooled_auc'],
        'loso_fold_auc_mean': loso['fold_auc_mean'],
        'loso_fold_auc_sd': loso['fold_auc_sd'],
        'loso_youden_j': yj,
        'features': list(APPROACH_7),
        'scaler_mean': scaler.mean_.tolist(),
        'scaler_scale': scaler.scale_.tolist(),
        'coefficients_raw': lr.coef_[0].tolist(),
        'intercept': float(lr.intercept_[0]),
        'apply': 'score = sigmoid(sum_i(coef_i * (feat_i - scaler_mean_i) / scaler_scale_i) + intercept); '
                 'pred_deferred = score >= operating_threshold',
        'regime_for_inference': 'WILD-compatible (cursor features only, the tracker\'s runtime measurement); '
                                'supervision was [LAB, NB22 gaze-derived]',
        'provenance': {
            'producer': 'attentional-foraging/scripts/export_m5_cursor_only.py',
            'producer_sha256': sha256(__file__),
            'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'feature_cache': rel(args.feature_cache),
            'feature_cache_sha256': sha256(args.feature_cache),
            'feature_cache_condition': f'buf{args.buffer}',
            'anchor_event': cache['anchor_event'], 'sampling': cache['sampling'],
            'label_cache': rel(args.label_cache),
            'label_cache_sha256': sha256(args.label_cache),
            'label_alignment_rows': rel(args.lab_rows),
            'pool': f'approached (min_dist < {APPROACH_PX} px) and not clicked',
            'gate': gate,
            'sklearn': __import__('sklearn').__version__, 'python': sys.version.split()[0],
        },
        'lineage_note': LINEAGE_NOTE,
    }

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / 'm5_cursor_only_v2.json'
    model_path.write_text(json.dumps(model, indent=2, allow_nan=False) + '\n')
    summary = {'schema_version': 1, 'generated_utc': model['provenance']['generated_utc'],
               'population': {'records': len(records), 'participants': int(len(np.unique(pid))),
                              'pool': n_pool, 'deferred': n_def, 'eval_rejected': n_pool - n_def},
               'gate': gate, 'loso': loso, 'youden_j': yj, 'fold_aucs': folds,
               'refit_selfcheck_max_abs_err': max_err,
               'model_file': rel(model_path),
               'provenance': {k: v for k, v in model['provenance'].items() if k != 'gate'}}
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(f'wrote {model_path}')
    if args.ar_models_dir:
        args.ar_models_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(model_path, args.ar_models_dir / 'm5_cursor_only_v2.json')
        print(f'wrote {args.ar_models_dir / "m5_cursor_only_v2.json"}')
    return model


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--feature-cache', type=Path, default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--lab-rows', type=Path, default=ROOT / 'AdSERP/data/cursor-approach-features-typed.json')
    ap.add_argument('--label-cache', type=Path,
                    default=ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown',
                    help='aggregate sidecar whose feature-records hash the cache must match')
    ap.add_argument('--gate-sidecar', type=Path, default=ROOT / 'scripts/output/m4_cursor_only_downstream/summary.json')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'scripts/output/m5_cursor_only_v2')
    ap.add_argument('--ar-models-dir', type=Path, default=AR_ROOT / 'scripts/models',
                    help='approach-retreat models dir to copy the export into (empty string to skip)')
    args = ap.parse_args()
    if args.ar_models_dir is not None and str(args.ar_models_dir) == '':
        args.ar_models_dir = None
    return args


if __name__ == '__main__':
    run(parse_args())
