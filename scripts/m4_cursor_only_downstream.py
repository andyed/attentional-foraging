"""Downstream re-derivations on the cursor-only typed feature cache.

Re-runs, on the rows m4_cursor_aoi_rerun.py produced (press-anchored, buf500,
`[LAB, AdSERP, typed, cursor-only]`), the four analyses the CHIIR draft still
quoted from the fixation-selected LAB stream:

  §4.3  deployable deferred-class classifier: LOSO LR on the seven M4 features
        -> NB22 gaze-regression label, on approached (min_dist < 100 px)
        non-click rows; Youden-J operating point; leave-one-feature-out; and
        the matched-row diagnostic ceiling from the gaze-gated cache (same
        rows, cursor sampled at fixation onsets).
  §4.2  click-thresholded baseline: Youden-J on the LOSO M4-7 click classifier
        splits the same pool; disagreement with the gaze label and Jaccard on
        eval-rejected.
  NB11.5 chattiness terciles: per-participant events/s (mousemove family, raw
        evtrack) x per-participant LOSO M4-7 AUC; Spearman.
  per-etype slice of the M4-7 click classifier.

Gaze enters exactly where the paper says it does: the regression label and
the ceiling's sampling times. Row selection and features are cursor-only.
Aggregates only are written; the caches stay out of git.

Run from attentional-foraging:
  .venv/bin/python scripts/m4_cursor_only_downstream.py
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from scipy.stats import spearmanr, wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from m4_cursor_aoi_rerun import APPROACH_7, APPROACH_9  # noqa: E402

APPROACH_PX = 100


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def loso_proba(records, features, y, mask=None):
    """Out-of-fold LOSO probabilities on rows where mask is True (all rows if None)."""
    mask = np.ones(len(records), dtype=bool) if mask is None else mask
    X = np.asarray([[r[f] for f in features] for r in records], dtype=float)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    proba = np.full(len(records), np.nan)
    for p in np.unique(pid):
        train, test = mask & (pid != p), mask & (pid == p)
        if len(set(y[train])) < 2 or not test.any():
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
        m.fit(X[train], y[train])
        proba[test] = m.predict_proba(X[test])[:, 1]
    return proba, pid


def fold_aucs(y, proba, pid, mask):
    out = {}
    for p in np.unique(pid[mask]):
        sel = mask & (pid == p) & np.isfinite(proba)
        if len(set(y[sel])) == 2:
            out[str(p)] = float(roc_auc_score(y[sel], proba[sel]))
    return out


def summarize(y, proba, pid, mask):
    sel = mask & np.isfinite(proba)
    folds = fold_aucs(y, proba, pid, mask)
    a = np.array(list(folds.values()))
    return {'pooled_auc': float(roc_auc_score(y[sel], proba[sel])),
            'fold_auc_mean': float(a.mean()), 'fold_auc_sd': float(a.std(ddof=1)),
            'fold_auc_median': float(np.median(a)), 'n_folds': len(folds),
            'n_records': int(sel.sum()), 'n_positive': int(y[sel].sum())}, folds


def youden(y, proba, mask):
    sel = mask & np.isfinite(proba)
    fpr, tpr, thr = roc_curve(y[sel], proba[sel])
    j = int(np.argmax(tpr - fpr))
    t = float(thr[j])
    pred = proba[sel] >= t
    tp = int((pred & (y[sel] == 1)).sum()); fp = int((pred & (y[sel] == 0)).sum())
    fn = int((~pred & (y[sel] == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {'threshold': t, 'tpr': float(tpr[j]), 'fpr': float(fpr[j]), 'precision': prec,
            'recall': rec, 'f1': (2 * prec * rec / (prec + rec)) if prec + rec else 0.0}


def paired(a, b):
    pids = sorted(set(a) & set(b))
    d = np.asarray([a[p] - b[p] for p in pids])
    rng = np.random.default_rng(20260906)
    means = rng.choice(d, size=(10000, len(d)), replace=True).mean(axis=1)
    return {'n_participants': len(pids), 'mean_delta': float(d.mean()),
            'bootstrap_ci95': np.quantile(means, [.025, .975]).tolist(),
            'wilcoxon_two_sided_p': float(wilcoxon(d).pvalue) if np.any(d) else 1.0}


def chattiness_per_participant(dl, tids):
    """NB11.5 events_per_sec: mousemove-family samples / trial duration, averaged per participant."""
    pos_events = {'mousemove', 'mouseover', 'mouseout', 'mousedown', 'mouseup'}
    per_trial = defaultdict(list)
    for tid in tids:
        events, _, _ = dl.load_mouse_events(tid, space='document')
        moves = [t for t, evt, x, y in events if evt in pos_events]
        if len(moves) < 5:
            continue
        dur = (moves[-1] - moves[0]) / 1000.0
        if dur <= 0.5:
            continue
        per_trial[tid.split('-')[0]].append(len(moves) / dur)
    return {p: float(np.mean(v)) for p, v in per_trial.items()}


def gaze_return_counts(dl, tid, cards):
    """Distinct gaze returns per main-axis position, NB22's rule on the typed map:
    a fixation lands on a position already visited while a later position has
    been reached (p in visited and p < max_seen). Counted once per re-entry,
    not once per fixation, so a long dwell is one return."""
    bands = sorted(((c['y'], c['y'] + c['height'], c['position']) for c in cards if c.get('position', -1) >= 0))
    def pos_of(y):
        for top, bot, p in bands:
            if top <= y <= bot:
                return p
        return None
    visited, max_seen, returns, last = set(), -1, defaultdict(int), None
    for f in sorted(dl.load_fixations(tid), key=lambda f: f['t']):
        p = pos_of(f['y'])
        if p is None:
            last = None
            continue
        if p != last and p in visited and p < max_seen:
            returns[p] += 1
        visited.add(p); max_seen = max(max_seen, p); last = p
    return dict(returns)


def cursor_visit_counts(dl, tid, cards, margin_px=40, min_dwell_ms=100, reapproach_ms=5000):
    """Finalised cursor visits per main-axis position (cursor_arc_prevalence rule:
    enter the box +- margin, dwell >= min_dwell, exit; a re-entry within the
    reapproach window merges into the prior visit). Cursor converted into the
    maps' screenshot space first."""
    events, _, _ = dl.load_mouse_events(tid, space='screenshot')
    pos_events = {'mousemove', 'mouseover', 'mouseout', 'mousedown', 'mouseup'}
    cursor = sorted((t, x, y) for t, evt, x, y in events if evt in pos_events)
    boxes = [(c['position'], c['x'] - margin_px, c['x'] + c['width'] + margin_px,
              c['y'] - margin_px, c['y'] + c['height'] + margin_px)
             for c in cards if c.get('position', -1) >= 0]
    counts, last_exit = defaultdict(int), {}
    current, enter_t = None, None
    def finalize(pos, et, xt):
        if xt - et < min_dwell_ms:
            return
        prev = last_exit.get(pos)
        if prev is None or et - prev > reapproach_ms:
            counts[pos] += 1
        last_exit[pos] = xt
    for t, x, y in cursor:
        hit = next((p for p, x0, x1, y0, y1 in boxes if x0 <= x <= x1 and y0 <= y <= y1), None)
        if hit != current:
            if current is not None:
                finalize(current, enter_t, t)
            current, enter_t = hit, (t if hit is not None else None)
    if current is not None and cursor:
        finalize(current, enter_t, cursor[-1][0])
    return dict(counts)


def run(args):
    sys.path.insert(0, str(ROOT / 'notebooks-v2'))
    import data_loader as dl
    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    summary_sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    if summary_sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))
    keyed = {(r['trial_id'], r['position']): r for r in records}

    # NB22 gaze-regression label, re-keyed by (trial, position) exactly as the LTR producers do.
    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    assert len(lab_rows) == len(reg)
    label_by_key = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}
    gaze = np.asarray([int(label_by_key.get((r['trial_id'], r['position']), False)) for r in records])
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    etype = np.asarray([r['etype'] for r in records])
    pool = approached & (clicked == 0)
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'aggregate_sidecar': f'scripts/output/{args.summary_dir}/summary.json',
                      'regression_label_cache': 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json',
                      'regression_label_cache_sha256': sha256(ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'),
                      'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event'], 'sampling': cache['sampling']},
           'population': {'records': len(records), 'trials': len({r['trial_id'] for r in records}),
                          'participants': int(len(np.unique(pid))),
                          'four_class': {'clicked': int(clicked.sum()),
                                         'deferred': int((pool & (gaze == 1)).sum()),
                                         'eval_rejected': int((pool & (gaze == 0)).sum()),
                                         'not_approached': int((~approached & (clicked == 0)).sum())},
                          'approached_nonclick_pool': int(pool.sum())}}

    # ---- §4.3 deployable classifier -------------------------------------------------------
    p7, _ = loso_proba(records, APPROACH_7, gaze, pool)
    dep, dep_folds = summarize(gaze, p7, pid, pool)
    dep['youden_j'] = youden(gaze, p7, pool)
    p9, _ = loso_proba(records, APPROACH_9, gaze, pool)
    dep9, _ = summarize(gaze, p9, pid, pool)
    lofo = {}
    for f in APPROACH_7:
        pf, _ = loso_proba(records, [x for x in APPROACH_7 if x != f], gaze, pool)
        s, _ = summarize(gaze, pf, pid, pool)
        lofo[f] = {'pooled_auc': s['pooled_auc'], 'delta_pooled_auc_vs_full': s['pooled_auc'] - dep['pooled_auc']}
    minimal4 = ['mean_dist', 'dwell_in_proximity_ms', 'min_dist', 'direction_changes']
    pm, _ = loso_proba(records, minimal4, gaze, pool)
    dep_min, min_folds = summarize(gaze, pm, pid, pool)
    section43 = {'protocol': 'LOSO balanced LR on approached (min_dist < 100 px) non-click rows; target = NB22 gaze-regression label (deferred=1, eval-rejected=0)',
                 'deployable_M4_7': dep, 'deployable_M4_9_diagnostic': dep9,
                 'leave_one_feature_out': lofo,
                 'minimal_four': {'features': minimal4, **dep_min,
                                  'paired_vs_M4_7': paired(min_folds, dep_folds)}}
    if args.ceiling_cache and args.ceiling_cache.exists():
        gg = json.loads(args.ceiling_cache.read_text())['conditions'][f'buf{args.buffer}']
        gg_keyed = {(r['trial_id'], r['position']): r for r in gg}
        shared = [k for k in keyed if k in gg_keyed]
        idx = {k: i for i, k in enumerate((r['trial_id'], r['position']) for r in records)}
        m_shared = np.zeros(len(records), dtype=bool)
        for k in shared:
            m_shared[idx[k]] = True
        pool_shared = pool & m_shared
        # Deployable on the shared rows (so the gap is matched-row), and the ceiling.
        pd_, _ = loso_proba(records, APPROACH_7, gaze, pool_shared)
        d_shared, d_folds = summarize(gaze, pd_, pid, pool_shared)
        gg_records = [gg_keyed[(r['trial_id'], r['position'])] if m_shared[i] else r for i, r in enumerate(records)]
        pc, _ = loso_proba(gg_records, APPROACH_7, gaze, pool_shared)
        c_shared, c_folds = summarize(gaze, pc, pid, pool_shared)
        section43['matched_row_ceiling'] = {
            'ceiling_sampling': 'cursor y interpolated at fixation onsets (gaze-gated), same rows, same labels, same anchor and buffer',
            'ceiling_cache_sha256': sha256(args.ceiling_cache),
            'n_shared_pool_rows': int(pool_shared.sum()),
            'deployable_native_on_shared_rows': d_shared,
            'gaze_gated_ceiling': c_shared,
            'gap_ceiling_minus_deployable_pooled': c_shared['pooled_auc'] - d_shared['pooled_auc'],
            'capture_fraction_pooled': d_shared['pooled_auc'] / c_shared['pooled_auc'],
            'paired_ceiling_minus_deployable': paired(c_folds, d_folds)}
    out['section_4_3'] = section43

    # ---- §4.2 click-thresholded baseline ---------------------------------------------------
    pc7, _ = loso_proba(records, APPROACH_7, clicked, None)
    yj = youden(clicked, pc7, np.ones(len(records), dtype=bool))
    click_deferred = (pc7 >= yj['threshold']) & pool
    gaze_deferred = (gaze == 1) & pool
    n = int(pool.sum())
    er_click, er_gaze = pool & ~click_deferred, pool & ~gaze_deferred
    inter, union = int((er_click & er_gaze).sum()), int((er_click | er_gaze).sum())
    out['section_4_2'] = {
        'protocol': 'LOSO M4-7 click classifier over all rows; Youden-J threshold on its OOF probabilities partitions the approached non-click pool',
        'click_classifier_youden_j': yj,
        'pool': n,
        'click_thresholded_split': {'deferred': int(click_deferred.sum()), 'eval_rejected': int(er_click.sum()),
                                    'deferred_pct': 100 * click_deferred.sum() / n},
        'gaze_regression_split': {'deferred': int(gaze_deferred.sum()), 'eval_rejected': int(er_gaze.sum()),
                                  'deferred_pct': 100 * gaze_deferred.sum() / n},
        'disagreement_pct': 100 * float((click_deferred[pool] != gaze_deferred[pool]).mean()),
        'jaccard_eval_rejected': inter / union if union else 0.0,
        'deployable_disagreement_pct': 100 * float(((p7[pool] >= dep['youden_j']['threshold']) != (gaze[pool] == 1)).mean()),
        'deployable_disagreement_pct_at_0_5': 100 * float(((p7[pool] >= 0.5) != (gaze[pool] == 1)).mean()),
    }

    # ---- NB11.5 chattiness terciles ---------------------------------------------------------
    click_folds = fold_aucs(clicked, pc7, pid, np.ones(len(records), dtype=bool))
    chat = chattiness_per_participant(dl, sorted({r['trial_id'] for r in records}))
    shared_p = [p for p in click_folds if p in chat]
    vals = np.asarray([chat[p] for p in shared_p]); aucs = np.asarray([click_folds[p] for p in shared_p])
    order = np.argsort(vals); k = len(shared_p)
    terc = [order[:k // 3], order[k // 3:2 * k // 3], order[2 * k // 3:]]
    rho, pval = spearmanr(vals, aucs)
    out['chattiness_terciles'] = {
        'measure': 'events_per_sec (mousemove-family samples / trial duration; NB11.5 definition), per-participant mean over trials',
        'n_participants': k,
        'tercile_mean_auc': [float(aucs[t].mean()) for t in terc],
        'tercile_mean_events_per_sec': [float(vals[t].mean()) for t in terc],
        'spearman_rho': float(rho), 'spearman_p': float(pval),
        'events_per_sec_range': [float(vals.min()), float(vals.max())]}

    # ---- per-etype slice --------------------------------------------------------------------
    per_etype = {}
    for e in sorted(set(etype)):
        sel = etype == e
        if len(set(clicked[sel])) == 2 and sel.sum() >= 50:
            per_etype[e] = {'n_records': int(sel.sum()), 'n_clicks': int(clicked[sel].sum()),
                            'approach_rate': float(approached[sel].mean()),
                            'auc_M4_7_within_etype': float(roc_auc_score(clicked[sel], pc7[sel]))}
    out['per_etype_M4_7'] = per_etype
    # Four-class split by etype on the same rows (gaze label, cursor-defined approach).
    by_etype = {}
    for e in sorted(set(etype)):
        sel = etype == e
        pool_e = pool & sel
        by_etype[e] = {'n_records': int(sel.sum()), 'clicked': int(clicked[sel].sum()),
                       'approached_nonclick': int(pool_e.sum()),
                       'deferred': int((pool_e & (gaze == 1)).sum()),
                       'eval_rejected': int((pool_e & (gaze == 0)).sum()),
                       'deferred_pct_of_records': 100 * float((pool_e & (gaze == 1)).sum() / max(sel.sum(), 1)),
                       'deferred_pct_of_approached_nonclick': 100 * float((pool_e & (gaze == 1)).sum() / max(pool_e.sum(), 1))}
    out['four_class_by_etype'] = by_etype

    # ---- NB22 gaze-return counts on the deferred rows (typed map, fixation sequence) ----
    tids = sorted({r['trial_id'] for r in records})
    ret_by_key, visits_by_key = {}, {}
    for tid in tids:
        cards = dl.load_typed_aois(tid)
        for p, n in gaze_return_counts(dl, tid, cards).items():
            ret_by_key[(tid, p)] = n
        for p, n in cursor_visit_counts(dl, tid, cards).items():
            visits_by_key[(tid, p)] = n
    deferred_rows = [r for r, g, pl in zip(records, gaze, pool) if pl and g == 1]
    returns = np.asarray([ret_by_key.get((r['trial_id'], r['position']), 0) for r in deferred_rows])
    out['gaze_return_counts'] = {
        'rule': 'distinct re-entries of the fixation sequence into a main-axis typed AOI already visited while a later position had been reached (NB22 p in visited and p < max_seen), counted once per re-entry',
        'population': 'approached (cursor-only) non-click rows with gaze-regression label = deferred',
        'n': int(len(returns)),
        'pct_ge_1': 100 * float((returns >= 1).mean()), 'pct_ge_2': 100 * float((returns >= 2).mean()),
        'pct_ge_3': 100 * float((returns >= 3).mean()), 'pct_ge_5': 100 * float((returns >= 5).mean()),
        'median': float(np.median(returns)), 'mean': float(returns.mean())}

    # ---- K-leak: cursor-blind subset (clicked + approached + cursor visit_count == 1) ----
    visits = np.asarray([visits_by_key.get((r['trial_id'], r['position']), 0) for r in records])
    clicked_appr = (clicked == 1) & approached
    blind = clicked_appr & (visits == 1)
    y_regaze = gaze  # gaze-regressed at that position, independent of cursor revisit
    kl = {'protocol': 'cursor visits per typed AOI in screenshot space (40 px margin, >= 100 ms dwell, 5 s merge); '
                      'subset = clicked & approached & visit_count == 1; target = gaze-regression label; LOPO balanced LR',
          'clicked_and_approached': int(clicked_appr.sum()),
          'cursor_revisit_coverage': {'n_visit_ge_2': int((clicked_appr & (visits >= 2)).sum()),
                                      'pct': 100 * float((clicked_appr & (visits >= 2)).sum() / max(clicked_appr.sum(), 1))},
          'cursor_blind_subset': {'n': int(blind.sum()), 'participants': int(len(np.unique(pid[blind]))),
                                  'regaze_prevalence_pct': 100 * float(y_regaze[blind].mean()) if blind.any() else None}}
    if blind.sum() > 50 and len(set(y_regaze[blind])) == 2:
        pb, _ = loso_proba(records, APPROACH_7, y_regaze, blind)
        full7, f7 = summarize(y_regaze, pb, pid, blind)
        pmin, _ = loso_proba(records, minimal4, y_regaze, blind)
        min4, fm = summarize(y_regaze, pmin, pid, blind)
        a7 = np.array(list(f7.values()))
        kl['full_M4_7'] = {**full7, 'wilcoxon_vs_chance_one_sided_p': float(wilcoxon(a7 - 0.5, alternative='greater').pvalue),
                           'folds_at_or_below_0_5': int((a7 <= 0.5).sum())}
        kl['minimal_four'] = {**min4, 'paired_vs_M4_7': paired(fm, f7)}
    out['cursor_blind_regaze'] = kl

    out['provenance'] = {'producer_sha256': sha256(__file__), 'python': sys.version.split()[0]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, allow_nan=False) + '\n')
    print(f'wrote {args.output}')
    return out


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--feature-cache', type=Path, default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--ceiling-cache', type=Path, default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown-gazegated.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--output', type=Path, default=ROOT / 'scripts/output/m4_cursor_only_downstream/summary.json')
    return ap.parse_args()


if __name__ == '__main__':
    run(parse_args())
