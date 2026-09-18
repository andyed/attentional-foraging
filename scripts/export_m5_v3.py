"""Export the deployable deferred SCORE (M5 v3): cursor + viewport bands, +/- SERP rank.

M5 v2 (scripts/export_m5_cursor_only.py) ships seven cursor features at LOSO
0.691 on the cursor-only typed stream. At its Youden point that model cannot
separate deferred from evaluated-rejected per result: TPR 0.7276 / FPR 0.4425
on 6,800 deferred and 3,132 rejected leaves the rejected-label precision at
48.5 %. docs/ablations/viewport_bands_cursor_only.md scores the three viewport
band features on the same pool at 0.789 alone and 0.789 with the cursor, and
the library already emits the bands at runtime, so the deployable model should
read them.

Two things change relative to v2 beyond the feature set:

  1. the artifact is a calibrated SCORE. `operating_threshold` stays (the
     schema and m5_inference.M5Classifier need it) but the model JSON carries
     an `operating_points` table and a `calibration` block, both from the LOSO
     out-of-fold scores, so a consumer picks its own point rather than
     inheriting Youden-J.
  2. a second variant takes the typed `position` integer, to say whether rank
     adds anything a cursor-plus-viewport model does not already have.
  3. the DEPLOYED fit is unweighted (class_weight=None). The balanced fit the
     gate and every science comparison use is not a probability: it fits as if
     the classes were even while the pool prior is 0.685, so its out-of-fold
     score under-predicts in nine of ten deciles (Brier 0.1918, worst bin off
     by 0.226). Since the consumer's use is the continuous score, that is a
     defect in the instrument, so the exported models are refitted without
     class weighting and carry the prior they are calibrated to.

Protocol (identical to viewport_bands_cursor_only.py, whose helpers are
imported rather than copied):
  rows    = cursor-only-typed-features-mousedown.json, condition buf500
  label   = NB22 gaze-regression label, re-keyed by (trial, position)
  pool    = approached (min_dist < 100 px) AND not clicked  (9,932 rows)
  bands   = edmonds-2026-vpbands-v1, full window only (no first-visit carve),
            screenshot space, cut at mousedown(final click) - 500 ms
  LOSO    = 47-fold, StandardScaler + LogisticRegression(C=1.0); balanced for
            the gate and the science table, class_weight=None for the exports,
            each with its own out-of-fold scores, operating points and bins
  GATE    = LOSO pooled AUC for cursor_M4_7, bands_3 and cursor_M4_7+bands_3
            must each equal viewport_bands_cursor_only/summary.json to 1e-6
  export  = unweighted full-data refit, v2's JSON schema plus score_semantics,
            training_prior, operating_points, calibration, feature_units and
            LOSO coefficients; a Platt layer is added only if the unweighted
            out-of-fold score misses calibration by more than CAL_TOL

Run from attentional-foraging:
  .venv/bin/python scripts/export_m5_v3.py
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from m4_cursor_aoi_rerun import APPROACH_7, load_flavor_cards, main_cards  # noqa: E402
from m4_cursor_only_downstream import (  # noqa: E402
    paired, rel, sha256, summarize, youden,
)
from export_m5_cursor_only import load_inputs  # noqa: E402
from viewport_bands_cursor_only import (  # noqa: E402
    BANDS, BAND_ALL, band_ms, model_block, observation_cutoff,
)
from reduction_baselines import within_trial_auc  # noqa: E402

AR_ROOT = ROOT.parent / 'approach-retreat'
GATE_TOL = 1e-6
RANK = 'position'
FIXED_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
N_CAL_BINS = 10
CAL_TOL = 0.05  # max |mean score - observed rate| in any equal-count bin before a Platt layer is added

FEATURE_UNITS = {
    'min_dist': 'px', 'mean_dist': 'px', 'dwell_in_proximity_ms': 'ms',
    'mean_approach_velocity': 'px/s', 'max_approach_velocity': 'px/s',
    'direction_changes': 'count', 'frac_decreasing': 'fraction',
    'vp_any': 'ms', 'vt_top': 'ms', 'vt_mid': 'ms', 'vt_bot': 'ms',
    RANK: 'rank 0-based',
}

SCORE_SEMANTICS = (
    'This is P(deferred | approached, not clicked) under the LAB NB22 gaze-regression label: the '
    'probability that a result the cursor approached but did not click is one the participant later '
    'returned to. The intended consumer use is the continuous score - as a per-episode feature, or '
    'averaged per result across sessions - not a hard label; any threshold is the consumer\'s choice, '
    'and operating_points gives the precision/recall of the choices from the LOSO out-of-fold scores. '
    'operating_threshold is retained for schema compatibility with m5_inference.M5Classifier and '
    'carries the Youden-J point, which is one row of that table and not a recommendation. '
    'PRIOR SHIFT: the score is calibrated to training_prior (the share of deferred rows in the '
    'training pool). To move it to a different base rate, work on the logit: '
    'logit_new = logit_old + log((p_new / (1 - p_new)) / (p_train / (1 - p_train))), i.e. add the log '
    'odds ratio of the new prior to the old, then re-apply the sigmoid.'
)

LINEAGE_NOTE = (
    'Successor to m5_cursor_only_v2.json (2026-09-18), which stays in place as the cursor-only model. '
    'v2 is the seven-feature tracker vector at LOSO 0.691; on its Youden point (TPR 0.7276, FPR 0.4425, '
    '6,800 deferred / 3,132 rejected) the rejected-label precision is 48.5 %, i.e. a hard EVALUATED_REJECTED '
    'call from the cursor alone is near a coin flip. v3 adds the three viewport-band features the library '
    'already emits at runtime (edmonds-2026-vpbands-v1: ms the result spent in the top / middle / bottom '
    'third of the viewport, over the same window every cursor feature uses). Science caveat carried '
    'forward from docs/ablations/viewport_bands_cursor_only.md: the band signal is mostly the return - cut '
    'at the end of the first gaze visit, bands fall 0.771 -> 0.553 - which does not matter for an instrument '
    'whose consumer wants to know whether the user came back, but does mean the bands are not a prediction '
    'made before the return happened. '
    'Class weighting: v2 and every gate/science number use class_weight=\'balanced\'; the exported v3 models '
    'are refitted with class_weight=None because the balanced score is not a probability (it fits as if the '
    'classes were even while the pool prior is 0.685) and the consumer\'s product is the continuous score. '
    'Ranking is unaffected - the paired per-participant delta between the two fits is in summary.json.'
)


def _pipe(class_weight):
    return make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=5000, class_weight=class_weight, C=1.0))


def loso_proba_cw(records, feats, y, mask, class_weight):
    """m4_cursor_only_downstream.loso_proba with the class weighting exposed;
    class_weight='balanced' is that function, fold for fold."""
    X = np.asarray([[r[f] for f in feats] for r in records], dtype=float)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    proba = np.full(len(records), np.nan)
    for p in np.unique(pid):
        train, test = mask & (pid != p), mask & (pid == p)
        if len(set(y[train])) < 2 or not test.any():
            continue
        m = _pipe(class_weight)
        m.fit(X[train], y[train])
        proba[test] = m.predict_proba(X[test])[:, 1]
    return proba, pid


def model_block_cw(records, feats, y, mask, pid, tids, class_weight):
    """viewport_bands_cursor_only.model_block with the class weighting exposed."""
    proba, _ = loso_proba_cw(records, feats, y, mask, class_weight)
    s, folds = summarize(y, proba, pid, mask)
    wt, n_pairs = within_trial_auc(tids, y, proba, mask)
    s['within_trial_auc'] = float(wt)
    s['within_trial_pairs'] = int(n_pairs)
    s['features'] = list(feats)
    s['class_weight'] = class_weight
    return s, folds, proba


def platt_fit(y, score):
    """Platt scaling on the out-of-fold logit: p_cal = sigmoid(a * z + b), where
    z is the model's own logit, so the layer composes with `apply` rather than
    needing a second model. Unregularised (C = 1e10) because the fit has two
    parameters and 9,932 rows."""
    q = np.clip(score, 1e-12, 1 - 1e-12)
    z = np.log(q / (1 - q))
    lr = LogisticRegression(C=1e10, max_iter=10000)
    lr.fit(z.reshape(-1, 1), y)
    a, b = float(lr.coef_[0][0]), float(lr.intercept_[0])
    return a, b, 1.0 / (1.0 + np.exp(-(a * z + b)))


def loso_coefficients(records, feats, y, mask, class_weight):
    """Per-fold standardized coefficients (the scaler is inside each fold's pipeline),
    reported as the mean and sd over the 47 LOSO fits."""
    X = np.asarray([[r[f] for f in feats] for r in records], dtype=float)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    rows = []
    for p in np.unique(pid):
        train = mask & (pid != p)
        if len(set(y[train])) < 2:
            continue
        m = _pipe(class_weight)
        m.fit(X[train], y[train])
        rows.append(m[-1].coef_.ravel())
    a = np.asarray(rows)
    return {'n_folds': int(len(a)), 'class_weight': class_weight,
            'mean': dict(zip(feats, a.mean(axis=0).tolist())),
            'sd': dict(zip(feats, a.std(axis=0, ddof=1).tolist()))}


def operating_point(y, proba, t, method):
    """Both classes' precision and recall at threshold t. deferred = 1."""
    pred = proba >= t
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum()); tn = int((~pred & (y == 0)).sum())
    def ratio(a, b):
        return float(a / b) if b else 0.0
    return {'threshold': float(t), 'method': method,
            'predicted_deferred_share': float(pred.mean()),
            'deferred_precision': ratio(tp, tp + fp), 'deferred_recall': ratio(tp, tp + fn),
            'rejected_precision': ratio(tn, tn + fn), 'rejected_recall': ratio(tn, tn + fp),
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}


def operating_points(y, proba, yj_threshold, prior):
    """Fixed grid + Youden-J + the threshold whose predicted-deferred share matches
    the pool prior (the quantile of the score distribution at 1 - prior)."""
    pts = [operating_point(y, proba, t, 'fixed grid') for t in FIXED_THRESHOLDS]
    pts.append(operating_point(y, proba, yj_threshold, 'Youden-J on LOSO out-of-fold scores'))
    t_prior = float(np.quantile(proba, 1.0 - prior))
    pts.append(operating_point(y, proba, t_prior,
                               f'prior-matching: predicted-deferred share = pool prior {prior:.4f}'))
    return sorted(pts, key=lambda d: d['threshold'])


def calibration(y, proba, n_bins=N_CAL_BINS):
    """Equal-count bins of the out-of-fold score."""
    order = np.argsort(proba, kind='stable')
    bins = []
    for chunk in np.array_split(order, n_bins):
        s, yy = proba[chunk], y[chunk]
        bins.append({'edge_lo': float(s.min()), 'edge_hi': float(s.max()),
                     'mean_score': float(s.mean()), 'observed_deferred_rate': float(yy.mean()),
                     'n': int(len(chunk))})
    gap = max(abs(b['mean_score'] - b['observed_deferred_rate']) for b in bins)
    brier = float(np.mean((proba - y) ** 2))
    return {'n_bins': n_bins, 'binning': 'equal-count on the LOSO out-of-fold score',
            'bins': bins, 'brier_score': brier,
            'max_abs_gap_mean_score_minus_observed_rate': float(gap),
            'verdict': ('calibrated: no equal-count bin is off by more than '
                        f'{gap:.3f} in probability' if gap <= 0.05 else
                        f'not calibrated: worst equal-count bin is off by {gap:.3f} in probability')}


def page_identity(tids, metadata_dir):
    """AdSERP serves each trial its own generated SERP. If a page were shown to
    several participants, the aggregate-use check (mean score per (page, position)
    vs observed deferred rate) would be computable; this reports whether it is."""
    slug, task, missing = {}, {}, 0
    for t in tids:
        try:
            tree = ET.parse(metadata_dir / f'{t}.xml')
            url = (tree.find('.//url').text or '')
            slug[t] = url.split('q=', 1)[1] if 'q=' in url else None
            node = tree.find('.//task')
            task[t] = (node.text or '').split('|')[0].strip() if node is not None else None
        except Exception:
            missing += 1
    by_slug, by_task = defaultdict(set), defaultdict(set)
    for t, s in slug.items():
        if s:
            by_slug[s].add(t.split('-')[0])
    for t, s in task.items():
        if s:
            by_task[s].add(t.split('-')[0])
    sizes = Counter(len(v) for v in by_slug.values())
    return {'metadata_dir': rel(metadata_dir), 'trials': len(tids), 'metadata_unreadable': missing,
            'page_key': 'url query slug (page.php?q=<slug>) from trial-metadata XML',
            'distinct_pages': len(by_slug), 'distinct_task_ids': len(by_task),
            'max_participants_per_page': max((len(v) for v in by_slug.values()), default=0),
            'max_participants_per_task_id': max((len(v) for v in by_task.values()), default=0),
            'participants_per_page_histogram': {str(k): int(v) for k, v in sorted(sizes.items())}}


def compute_bands(dl, records, flavor):
    """Full-window band ms per (trial, position), the viewport_bands_cursor_only
    convention: screenshot space, first mouse event to mousedown(final click) - 500 ms."""
    tids = sorted({r['trial_id'] for r in records})
    full, skips = {}, Counter()
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  bands {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, flavor))
        except Exception:
            skips['cards_unusable'] += 1
            continue
        if not cards:
            skips['no_typed_cards'] += 1
            continue
        geom = dl.get_trial_geometry(tid)
        if geom is None or not geom['screen_height']:
            skips['no_geometry'] += 1
            continue
        try:
            events, scrolls, clicks = dl.load_mouse_events(tid, space='document')
        except Exception:
            events = []
        if not events:
            skips['no_mouse_events'] += 1
            continue
        cutoff = observation_cutoff(events, clicks)
        if cutoff is None:
            skips['no_final_click_or_press'] += 1
            continue
        t_start = min(e[0] for e in events)
        if cutoff <= t_start:
            skips['cutoff_before_first_event'] += 1
            continue
        ry = geom['ratio_y']
        scrolls_ss = [(t, yy * ry) for t, yy in scrolls if math.isfinite(t) and math.isfinite(yy)]
        for p, v in band_ms(cards, scrolls_ss, t_start, cutoff, geom['screen_height'] * ry).items():
            full[(tid, p)] = v
    for r in records:
        v = full.get((r['trial_id'], r['position']), [0.0] * 4)
        for j, nm in enumerate(BAND_ALL):
            r[nm] = v[j]
    have = np.asarray([(r['trial_id'], r['position']) in full for r in records])
    return have, dict(skips), len({k[0] for k in full}), len(tids)


def refit_export(records, feats, y, pool, oof, loso, name, extra, class_weight,
                 balanced_reference=None):
    """Full-data refit + the v2 model JSON schema, plus the v3 score blocks.

    The exported score is the fitted logistic model, Platt-corrected only when
    the out-of-fold score misses calibration by more than CAL_TOL in any
    equal-count bin. The operating points and the reported bins are always on
    the score the file actually emits.
    """
    X = np.asarray([[r[f] for f in feats] for r in records], dtype=float)[pool]
    yy = y[pool]
    pipe = _pipe(class_weight)
    pipe.fit(X, yy)
    scaler, lr = pipe.named_steps['standardscaler'], pipe.named_steps['logisticregression']
    z = ((X - scaler.mean_) / scaler.scale_) @ lr.coef_[0] + lr.intercept_[0]
    max_err = float(np.abs(1.0 / (1.0 + np.exp(-z)) - pipe.predict_proba(X)[:, 1]).max())
    if max_err > 1e-9:
        sys.exit(f'ABORT: exported arithmetic disagrees with sklearn for {name} (max err {max_err})')

    sel = pool & np.isfinite(oof)
    y_sel, p_sel = y[sel], oof[sel]
    cal_raw = calibration(y_sel, p_sel)
    platt, cal_final, score_sel = None, cal_raw, p_sel
    if cal_raw['max_abs_gap_mean_score_minus_observed_rate'] > CAL_TOL:
        a, b, score_sel = platt_fit(y_sel, p_sel)
        platt = {'a': a, 'b': b,
                 'fitted_on': 'the LOSO out-of-fold logits of this model, all pool rows',
                 'reason': 'the uncalibrated out-of-fold score missed calibration by '
                           f'{cal_raw["max_abs_gap_mean_score_minus_observed_rate"]:.3f} '
                           f'(tolerance {CAL_TOL})'}
        cal_final = calibration(y_sel, score_sel)
    score_full = np.full(len(records), np.nan)
    score_full[sel] = score_sel
    yj = youden(y, score_full, pool)
    prior = float(yy.mean())
    n_pool, n_def = int(pool.sum()), int(yy.sum())
    apply_formula = ('z = sum_i(coef_i * (feat_i - scaler_mean_i) / scaler_scale_i) + intercept; '
                     'score = sigmoid(z); pred_deferred = score >= operating_threshold')
    if platt:
        apply_formula = ('z = sum_i(coef_i * (feat_i - scaler_mean_i) / scaler_scale_i) + intercept; '
                         'score = sigmoid(platt.a * z + platt.b); '
                         'pred_deferred = score >= operating_threshold. '
                         'NOTE: the Platt layer is part of the score - a consumer that stops at '
                         'sigmoid(z) emits the uncalibrated score.')
    model = {
        'model': f"LogisticRegression(class_weight={class_weight!r}, C=1.0) + StandardScaler",
        'class_weight': class_weight,
        'trained_on': 'all 47 participants, no holdout (full-data refit); '
                      '[LAB, AdSERP, typed, cursor-only + viewport bands, press-anchored buf500]',
        'n_episodes': n_pool,
        'n_deferred': n_def,
        'n_eval_rej': n_pool - n_def,
        'training_prior': prior,
        'training_prior_note': f'{n_def} deferred / {n_pool} pool rows; the score is calibrated to this '
                               'base rate, see score_semantics for the prior shift',
        'score_semantics': SCORE_SEMANTICS,
        'operating_threshold': yj['threshold'],
        'operating_threshold_method': 'Youden-J on LOSO out-of-fold predictions (one row of operating_points)',
        'operating_points': operating_points(y_sel, score_sel, yj['threshold'], prior),
        'calibration': cal_final,
        'platt': platt,
        'loso_auc': loso['pooled_auc'],
        'loso_within_trial_auc': loso['within_trial_auc'],
        'loso_fold_auc_mean': loso['fold_auc_mean'],
        'loso_fold_auc_sd': loso['fold_auc_sd'],
        'loso_youden_j': yj,
        'loso_standardized_coefficients': loso_coefficients(records, feats, y, pool, class_weight),
        'features': list(feats),
        'feature_units': {f: FEATURE_UNITS[f] for f in feats},
        'scaler_mean': scaler.mean_.tolist(),
        'scaler_scale': scaler.scale_.tolist(),
        'coefficients_raw': lr.coef_[0].tolist(),
        'intercept': float(lr.intercept_[0]),
        'apply': apply_formula,
        'refit_selfcheck_max_abs_err': max_err,
        'regime_for_inference': 'WILD-compatible (cursor features plus the viewport bands the library emits '
                                'at runtime); supervision was [LAB, NB22 gaze-derived]',
        'band_definition': 'edmonds-2026-vpbands-v1: scrollY = 0 from the first mouse event, stepped at each '
                           'scroll event; vt_top/vt_mid/vt_bot accrue ms by which third of the viewport the '
                           'result centre lies in, over the first mouse event to mousedown(final click) - 500 ms, '
                           'in screenshot space (scroll y * ratio_y, vp_h = screen_height * ratio_y)',
        'balanced_reference': balanced_reference,
        'provenance': dict(extra),
        'lineage_note': LINEAGE_NOTE,
    }
    if platt is None:
        model['calibration']['platt_layer'] = (f'none: the uncalibrated out-of-fold score is within {CAL_TOL} '
                                               'in every equal-count bin')
    else:
        model['calibration_uncalibrated'] = cal_raw
    return model, max_err


def run(args):
    import data_loader as dl

    cache, records, y, shipped_pool = load_inputs(args)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    tids_arr = [r['trial_id'] for r in records]
    print(f'records={len(records)} shipped_pool={int(shipped_pool.sum())} '
          f'deferred={int(y[shipped_pool].sum())} participants={len(np.unique(pid))}')

    print('computing viewport bands (full window only, no first-visit carve)...')
    have, skips, n_band_trials, n_trials = compute_bands(dl, records, args.flavor)
    pool = shipped_pool & have
    print(f'bands on {n_band_trials}/{n_trials} trials, skips {skips}; '
          f'pool {int(pool.sum())} of shipped {int(shipped_pool.sum())}')

    # ---- gate: three reference AUCs, before any v3 number ---------------------------------
    ref = json.loads(args.bands_sidecar.read_text())['models']
    gate_specs = [('cursor_M4_7', list(APPROACH_7)), ('bands_3', list(BANDS)),
                  ('cursor_M4_7_plus_bands_3', list(APPROACH_7) + list(BANDS))]
    gate, blocks, folds = {'tolerance': GATE_TOL, 'sidecar': rel(args.bands_sidecar), 'checks': {}}, {}, {}
    ok = True
    for name, feats in gate_specs:
        s, f = model_block(records, feats, y, pool, pid, tids_arr)
        blocks[name], folds[name] = s, f
        expected = ref[name]['pooled_auc']
        d = abs(s['pooled_auc'] - expected)
        gate['checks'][name] = {'expected_pooled_auc': expected, 'reproduced_pooled_auc': s['pooled_auc'],
                                'abs_diff': d, 'passed': bool(d <= GATE_TOL)}
        ok = ok and d <= GATE_TOL
        print(f'gate {name:26s} expected {expected:.9f} reproduced {s["pooled_auc"]:.9f} diff {d:.2e}')
    gate['passed'] = bool(ok)
    if not ok:
        sys.exit('ABORT: gate failed - the reference viewport-bands AUCs were not reproduced; '
                 'no v3 model is exported')

    # ---- the rest of the LOSO table ---------------------------------------------------------
    for name, feats in (('cursor_M4_7_plus_bands_3_plus_rank', list(APPROACH_7) + list(BANDS) + [RANK]),
                        ('cursor_M4_7_plus_vp_any_plus_bands_3', list(APPROACH_7) + list(BAND_ALL)),
                        ('bands_3_plus_rank', list(BANDS) + [RANK]),
                        ('rank_alone', [RANK])):
        blocks[name], folds[name] = model_block(records, feats, y, pool, pid, tids_arr)
    print(f"\n{'model':40s} {'pooled':>7s} {'fold mean±sd':>15s} {'within-trial':>13s}")
    for name, s in blocks.items():
        print(f"{name:40s} {s['pooled_auc']:7.3f} {s['fold_auc_mean']:7.3f} ± {s['fold_auc_sd']:.3f} "
              f"{s['within_trial_auc']:13.3f}")

    # ---- the deployable fit: same features, no class weighting ------------------------------
    deployable = {'m5_v3_cursor_bands.json': ('cursor_M4_7_plus_bands_3',
                                              list(APPROACH_7) + list(BANDS)),
                  'm5_v3_cursor_bands_rank.json': ('cursor_M4_7_plus_bands_3_plus_rank',
                                                   list(APPROACH_7) + list(BANDS) + [RANK])}
    unweighted, u_folds, u_oof = {}, {}, {}
    print("\nunweighted (class_weight=None) refits, same rows and folds")
    for block, feats in deployable.values():
        s_u, f_u, p_u = model_block_cw(records, feats, y, pool, pid, tids_arr, None)
        unweighted[block], u_folds[block], u_oof[block] = s_u, f_u, p_u
        print(f"{block:40s} {s_u['pooled_auc']:7.3f} {s_u['fold_auc_mean']:7.3f} ± {s_u['fold_auc_sd']:.3f} "
              f"{s_u['within_trial_auc']:13.3f}  (balanced {blocks[block]['pooled_auc']:.3f} / "
              f"{blocks[block]['within_trial_auc']:.3f})")

    # The balanced score's own calibration and operating points, kept as evidence for why it is
    # the gate and the science comparison but not the exported artifact.
    balanced_score = {}
    for block, feats in deployable.values():
        pb, _ = loso_proba_cw(records, feats, y, pool, 'balanced')
        selb = pool & np.isfinite(pb)
        yj_b = youden(y, pb, pool)
        balanced_score[block] = {
            'note': 'not exported: this fit ranks the same as the deployed one but its score is not a '
                    'probability, because class_weight=balanced fits as if the prior were 0.5',
            'calibration': calibration(y[selb], pb[selb]),
            'youden_j': yj_b,
            'operating_points': operating_points(y[selb], pb[selb], yj_b['threshold'],
                                                 float(y[pool].mean())),
        }
        print(f"  balanced {block:38s} Brier {balanced_score[block]['calibration']['brier_score']:.4f} "
              f"max gap {balanced_score[block]['calibration']['max_abs_gap_mean_score_minus_observed_rate']:.3f}")

    paired_block = {
        'method': 'per-participant LOSO fold AUC differences; 10,000-draw bootstrap of the participant mean '
                  'plus two-sided Wilcoxon (m4_cursor_only_downstream.paired)',
        'cursor_plus_bands_minus_cursor': paired(folds['cursor_M4_7_plus_bands_3'], folds['cursor_M4_7']),
        'cursor_plus_bands_plus_rank_minus_cursor_plus_bands':
            paired(folds['cursor_M4_7_plus_bands_3_plus_rank'], folds['cursor_M4_7_plus_bands_3']),
        'cursor_plus_vp_any_plus_bands_minus_cursor_plus_bands':
            paired(folds['cursor_M4_7_plus_vp_any_plus_bands_3'], folds['cursor_M4_7_plus_bands_3']),
    }
    for block in unweighted:
        paired_block[f'unweighted_minus_balanced__{block}'] = paired(u_folds[block], folds[block])
        paired_block[f'unweighted_minus_balanced__{block}']['pooled_auc_delta'] = (
            unweighted[block]['pooled_auc'] - blocks[block]['pooled_auc'])
    for k, v in paired_block.items():
        if isinstance(v, dict) and 'mean_delta' in v:
            print(f"  {k:56s} Δ {v['mean_delta']:+.4f} "
                  f"CI [{v['bootstrap_ci95'][0]:+.4f}, {v['bootstrap_ci95'][1]:+.4f}] "
                  f"p={v['wilcoxon_two_sided_p']:.2e}")

    # ---- aggregate use: is the same SERP page seen by several participants? ------------------
    pool_tids = sorted({t for t, m in zip(tids_arr, pool) if m})
    pages = page_identity(pool_tids, ROOT / 'AdSERP/data/trial-metadata')
    if pages['max_participants_per_page'] >= 5:
        aggregate_use = {'status': 'computable_but_not_run',
                         'reason': 'pages are shared; the per-page aggregation was not implemented', **pages}
    else:
        aggregate_use = {
            'status': 'not_established',
            'reason': 'AdSERP generates one SERP per trial: across the '
                      f'{pages["trials"]:,} pool trials there are {pages["distinct_pages"]:,} distinct pages '
                      f'and {pages["distinct_task_ids"]:,} distinct task ids, and no page or task id is seen by '
                      f'more than {pages["max_participants_per_page"]} participant. The claim that a 0.69 '
                      'per-instance score becomes a clean separation when averaged over participants viewing '
                      'the same result cannot be tested on this dataset; it needs a corpus where one page is '
                      'served to many sessions.',
            **pages,
        }
    print(f"\naggregate_use: {aggregate_use['status']} "
          f"(max participants per page {pages['max_participants_per_page']})")

    # ---- exports ------------------------------------------------------------------------------
    prov = {
        'producer': 'attentional-foraging/scripts/export_m5_v3.py',
        'producer_sha256': sha256(__file__),
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'feature_cache': rel(args.feature_cache), 'feature_cache_sha256': sha256(args.feature_cache),
        'feature_cache_condition': f'buf{args.buffer}',
        'anchor_event': cache['anchor_event'], 'sampling': cache['sampling'], 'flavor': args.flavor,
        'label_cache': rel(args.label_cache), 'label_cache_sha256': sha256(args.label_cache),
        'label_alignment_rows': rel(args.lab_rows), 'lab_rows_sha256': sha256(args.lab_rows),
        'bands_sidecar': rel(args.bands_sidecar), 'bands_sidecar_sha256': sha256(args.bands_sidecar),
        'pool': 'approached (min_dist < 100 px) and not clicked, with bands resolved',
        'gate': gate,
        'sklearn': __import__('sklearn').__version__, 'python': sys.version.split()[0],
    }
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    written, selfchecks = {}, {}
    for fname, (block, feats) in deployable.items():
        ref = {'note': 'the balanced fit is the gate and the science comparison; it is not exported '
                       'because its score is not a probability',
               'class_weight': 'balanced', 'loso_auc': blocks[block]['pooled_auc'],
               'loso_within_trial_auc': blocks[block]['within_trial_auc']}
        model, err = refit_export(records, feats, y, pool, u_oof[block], unweighted[block],
                                  fname, prov, None, balanced_reference=ref)
        (out_dir / fname).write_text(json.dumps(model, indent=2, allow_nan=False) + '\n')
        written[block] = {'file': rel(out_dir / fname), 'class_weight': None,
                          'training_prior': model['training_prior'],
                          'platt': model['platt'],
                          'operating_points': model['operating_points'],
                          'calibration': model['calibration']}
        selfchecks[fname] = err
        yjp = next(p for p in model['operating_points'] if p['method'].startswith('Youden'))
        prp = next(p for p in model['operating_points'] if p['method'].startswith('prior'))
        print(f"\n{fname}: class_weight={model['class_weight']}, refit selfcheck {err:.1e}, "
              f"Brier {model['calibration']['brier_score']:.4f}, {model['calibration']['verdict']}"
              f"{'' if model['platt'] is None else ' [after Platt]'}")
        for tag, p in (('youden ', yjp), ('prior  ', prp)):
            print(f"  {tag} t={p['threshold']:.3f} share {p['predicted_deferred_share']:.3f} "
                  f"def P/R {p['deferred_precision']:.3f}/{p['deferred_recall']:.3f} "
                  f"rej P/R {p['rejected_precision']:.3f}/{p['rejected_recall']:.3f}")

    summary = {
        'schema_version': 1,
        'generated_utc': prov['generated_utc'],
        'regime': '[LAB, AdSERP, typed, cursor-only + viewport bands]',
        'population': {'records': len(records), 'trials': n_trials, 'trials_with_bands': n_band_trials,
                       'participants': int(len(np.unique(pid))),
                       'shipped_pool': int(shipped_pool.sum()), 'pool': int(pool.sum()),
                       'deferred': int(y[pool].sum()),
                       'eval_rejected': int(pool.sum() - y[pool].sum()),
                       'rows_dropped_from_shipped_pool': int((shipped_pool & ~have).sum()),
                       'band_trial_skips': skips},
        'gate': gate,
        'loso_balanced': blocks,
        'loso_unweighted_deployed': unweighted,
        'fold_aucs_balanced': folds,
        'fold_aucs_unweighted_deployed': u_folds,
        'paired_by_participant': paired_block,
        'balanced_score_not_exported': balanced_score,
        'exported': written,
        'refit_selfcheck_max_abs_err': selfchecks,
        'aggregate_use': aggregate_use,
        'provenance': {k: v for k, v in prov.items() if k != 'gate'},
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=1, allow_nan=False) + '\n')
    print(f'\nwrote {out_dir}/summary.json')
    if args.ar_models_dir:
        args.ar_models_dir.mkdir(parents=True, exist_ok=True)
        for fname in deployable:
            shutil.copyfile(out_dir / fname, args.ar_models_dir / fname)
            print(f'wrote {args.ar_models_dir / fname}')


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--lab-rows', type=Path, default=ROOT / 'AdSERP/data/cursor-approach-features-typed.json')
    ap.add_argument('--label-cache', type=Path,
                    default=ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--bands-sidecar', type=Path,
                    default=ROOT / 'scripts/output/viewport_bands_cursor_only/summary.json')
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'scripts/output/m5_v3')
    ap.add_argument('--ar-models-dir', type=Path, default=AR_ROOT / 'scripts/models')
    args = ap.parse_args()
    if args.ar_models_dir is not None and str(args.ar_models_dir) == '':
        args.ar_models_dir = None
    return args


if __name__ == '__main__':
    run(parse_args())
