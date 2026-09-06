"""Cursor-only NB21 stream on post-collision typed AOIs.

This is a new, explicitly typed protocol, not a relabeling of the historical
organic_hybrid or fixation-gated results. Calls the actual approach-retreat
ResultFeatureTracker through Node; never loads fixation/pupil features or
conditions row inclusion on gaze. Does not modify the LAB feature caches.

Run from attentional-foraging:
  .venv/bin/python scripts/m4_cursor_aoi_rerun.py

Only aggregate metrics and hashes are saved. Default output is separate from
historical paper-output artifacts. --limit is for smoke tests, never claims.

Observation cutoff. evtrack stamps the final `click` record a median ~1.3 s
after the `mouseup` of the same physical press (the two share coordinates on
every trial checked), and the last native `mousemove` precedes even the
`mousedown` by a median ~0.2 s. Anchoring buffers at the logged click therefore
removes no cursor samples for any buffer below ~0.6 s. `--anchor mousedown`
anchors the cutoff at the last mousedown at or before the final click so a
buffer actually tests removal of the terminal approach; `--anchor click` is the
original protocol and remains the default so the committed aggregate stays
reproducible. The two anchors are separate experiments with separate outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

# This machine hosts other work. One BLAS thread and sequential LOSO fits.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

APPROACH_9 = [
    'min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
    'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
    'direction_changes', 'frac_decreasing',
]
APPROACH_7 = [f for f in APPROACH_9 if f not in ('final_dist', 'retreat_dist')]
MODELS = [('M1', ['position']), ('M3', ['position'] + APPROACH_7),
          ('M4-7', APPROACH_7), ('M4-9', APPROACH_9)]
ANCHORS = ('click', 'mousedown')
WINDOWS = ('all', 'pre5', 'post5')
SAMPLINGS = ('native', 'gaze-gated')
FEATURE_GROUPS = {
    'distance': ['min_dist', 'mean_dist', 'dwell_in_proximity_ms'],
    'velocity': ['mean_approach_velocity', 'max_approach_velocity'],
    'dynamics': ['direction_changes', 'frac_decreasing'],
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main_cards(cards):
    """Require usable typed boxes and unique display positions; no estimates."""
    out = []
    for c in cards:
        if c.get('position', -1) < 0:
            continue
        if any(not isinstance(c.get(k), (int, float)) or not math.isfinite(c[k])
               for k in ('x', 'y', 'width', 'height')):
            raise ValueError('Main-axis AOI has missing/nonfinite geometry')
        if c['width'] <= 0 or c['height'] <= 0:
            raise ValueError('Main-axis AOI has nonpositive dimensions')
        out.append(c)
    out.sort(key=lambda c: c['position'])
    if len({c['position'] for c in out}) != len(out):
        raise ValueError('Duplicate main-axis positions')
    return out


def strict_click_position(cards, x, y):
    """Strict X+Y containment; exclude overlap ambiguity, never Y-snap."""
    hits = [c['position'] for c in cards
            if c['x'] <= x <= c['x'] + c['width']
            and c['y'] <= y <= c['y'] + c['height']]
    return (hits[0], 'unique') if len(hits) == 1 else (
        None, 'ambiguous_click' if hits else 'click_outside_main_boxes')


def downsample_samples(samples, hz):
    """Greedy timestamp thinning of [t, y] samples to simulate an N Hz cursor
    rate (mirrors compute_cursor_approach_features.downsample_mouse_events).
    hz <= 0 is a no-op."""
    if not hz or hz <= 0:
        return samples
    min_gap = 1000.0 / float(hz)
    kept, last = [], None
    for t, y in samples:
        if last is None or t - last >= min_gap:
            kept.append([t, y]); last = t
    return kept


def gaze_gated_samples(samples, fixation_times):
    """Cursor y interpolated at each fixation onset: the §4.3 diagnostic
    ceiling's sampling policy (fixation-timed cursor), applied to the same
    rows and labels as the deployable native stream. Only fixation
    timestamps are used; fixation coordinates never enter."""
    if len(samples) < 2:
        return []
    ts = np.asarray([t for t, _ in samples], dtype=float)
    ys = np.asarray([y for _, y in samples], dtype=float)
    out = []
    for t in sorted(fixation_times):
        if t < ts[0] or t > ts[-1]:
            continue
        out.append([float(t), float(np.interp(t, ts, ys))])
    return out


def fifth_fixation_end(fixations, k=5):
    """End time of the k-th fixation: the paper's early-scan / deliberation
    boundary (§3.3). None when the trial has too few fixations for a boundary."""
    if len(fixations) <= k:
        return None
    f = sorted(fixations, key=lambda f: f['t'])[k - 1]
    return float(f['t']) + float(f.get('d', 200) or 200)


def prepare_trial(tid, cards, events, clicks, geometry, buffers, anchor='click',
                  downsample_hz=0, window='all', fixations=None):
    if anchor not in ANCHORS:
        raise ValueError(f'anchor must be one of {ANCHORS}')
    if window not in WINDOWS:
        raise ValueError(f'window must be one of {WINDOWS}')
    cards = main_cards(cards)
    if len(cards) < 2:
        return None, 'fewer_than_two_aois'
    if not clicks:
        return None, 'no_click'
    # Existing data convention: final click is the target; prior clicks are
    # not samples. Neither its location nor timestamp enters a predictor.
    click = max(clicks, key=lambda c: c[0])
    if not all(math.isfinite(v) for v in click):
        return None, 'invalid_click'
    sx, sy = geometry['ratio_x'], geometry['ratio_y']
    if not all(math.isfinite(v) and v > 0 for v in (sx, sy)):
        raise ValueError('Invalid coordinate transform')
    position, reason = strict_click_position(cards, click[1] * sx, click[2] * sy)
    if position is None:
        return None, reason
    # Keep native event order (the JS tracker handles duplicate timestamps).
    # A decreasing timestamp is a data error; sorting would alter the trace.
    samples = [[t, y] for t, event, x, y in events
               if event == 'mousemove' and all(math.isfinite(v) for v in (t, x, y))]
    if any(b[0] < a[0] for a, b in zip(samples, samples[1:])):
        return None, 'nonmonotonic_mouse_time'
    samples = downsample_samples(samples, downsample_hz)
    if window != 'all':
        boundary = fifth_fixation_end(fixations or [])
        if boundary is None:
            return None, 'no_fifth_fixation_boundary'
        samples = [s for s in samples if (s[0] >= boundary) == (window == 'post5')]
    anchor_t = click[0]
    if anchor == 'mousedown':
        # The press that produced the final click: last mousedown at or before
        # the logged click. Its location is not used; only its time.
        presses = [t for t, event, x, y in events
                   if event == 'mousedown' and math.isfinite(t) and t <= click[0]]
        if not presses:
            return None, 'no_mousedown_for_final_click'
        anchor_t = max(presses)
    cutoff = anchor_t - max(buffers)
    if len({t for t, _ in samples if t < cutoff}) < 2:
        return None, 'insufficient_prebuffer_mousemove'
    return {
        'trial_id': tid, 'click_t': click[0], 'anchor_t': anchor_t,
        'click_position': position, 'buffers_ms': buffers, 'samples': samples,
        # Convert boxes back to document CSS px: the browser's proximity
        # threshold and velocity clamp are expressed in that coordinate space.
        'aois': [{'position': c['position'], 'etype': c['type'],
                  'center_document_y': (c['y'] + c['height'] / 2) / sy}
                 for c in cards],
    }, 'included'


def track_batch(trials, bridge, tracker):
    proc = subprocess.run(
        ['node', str(bridge), str(tracker)],
        input=''.join(json.dumps(t, allow_nan=False) + '\n' for t in trials),
        text=True, capture_output=True, check=True)
    rows = [json.loads(line) for line in proc.stdout.splitlines() if line]
    if len(rows) != len(trials):
        raise RuntimeError('Tracker returned wrong trial count')
    return rows


def within_trial_ranking(trial_ids, y, proba):
    """Per-trial MRR@10 and top-1 hit rate (NDCG@1 with one relevant item).

    Each included trial has exactly one clicked AOI. AOIs are ranked by held-out
    probability, ties broken by lower position so a tie never flatters the model.
    """
    by_trial = {}
    for i, tid in enumerate(trial_ids):
        by_trial.setdefault(tid, []).append(i)
    rr, top1 = [], []
    for idx in by_trial.values():
        order = sorted(idx, key=lambda i: (-proba[i], i))
        clicked = [k for k, i in enumerate(order) if y[i] == 1]
        if len(clicked) != 1:
            raise ValueError('Expected exactly one clicked AOI per trial')
        rank = clicked[0] + 1
        rr.append(1.0 / rank if rank <= 10 else 0.0)
        top1.append(1.0 if rank == 1 else 0.0)
    return {'mrr_at_10': float(np.mean(rr)), 'ndcg_at_1': float(np.mean(top1)),
            'n_ranked_trials': len(rr)}


def evaluate(records, features):
    X = np.asarray([[r[f] for f in features] for r in records], dtype=float)
    y = np.asarray([r['was_clicked'] for r in records], dtype=int)
    trial_ids = [r['trial_id'] for r in records]
    groups = np.asarray([tid.split('-')[0] for tid in trial_ids])
    if not np.isfinite(X).all():
        raise ValueError('Nonfinite features')
    if len(set(groups)) < 3:
        raise ValueError('Need at least three participants for LOSO evaluation')
    proba = np.full(len(y), np.nan)
    for train, test in LeaveOneGroupOut().split(X, y, groups):
        model = make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=5000, class_weight='balanced', C=1.0))
        model.fit(X[train], y[train])
        proba[test] = model.predict_proba(X[test])[:, 1]
    if not np.isfinite(proba).all():
        raise ValueError('Missing held-out predictions')
    folds = {str(pid): float(roc_auc_score(y[groups == pid], proba[groups == pid]))
             for pid in sorted(set(groups)) if len(set(y[groups == pid])) == 2}
    aucs = np.array(list(folds.values()))
    return {
        'features': features, 'pooled_auc': float(roc_auc_score(y, proba)),
        'fold_auc_mean': float(aucs.mean()),
        'fold_auc_sd': float(aucs.std(ddof=1)), 'n_folds': len(folds),
        'fold_auc_median': float(np.median(aucs)),
        'fold_auc_iqr': np.quantile(aucs, [.25, .75]).tolist(),
        'n_records': len(y), 'n_clicks': int(y.sum()),
        **within_trial_ranking(trial_ids, y, proba),
    }, folds


def feature_ablation(records, full):
    """Leave-one-feature-out, single-feature, group, and greedy forward-addition
    LOSO sweeps on the M4-7 vector."""
    keep = ('pooled_auc', 'fold_auc_mean', 'mrr_at_10', 'ndcg_at_1')
    lofo, alone, groups = {}, {}, {}
    for feat in APPROACH_7:
        dropped, _ = evaluate(records, [f for f in APPROACH_7 if f != feat])
        lofo[feat] = {k: dropped[k] for k in keep}
        lofo[feat]['delta_pooled_auc_vs_M4-7'] = dropped['pooled_auc'] - full['pooled_auc']
        single, _ = evaluate(records, [feat])
        alone[feat] = {k: single[k] for k in keep}
    for name, feats in FEATURE_GROUPS.items():
        only, _ = evaluate(records, feats)
        without, _ = evaluate(records, [f for f in APPROACH_7 if f not in feats])
        groups[name] = {'features': feats,
                        'only': {k: only[k] for k in keep},
                        'without': {k: without[k] for k in keep}}
    # Greedy forward addition: at each step add the feature that maximises
    # pooled AUC; three steps is where the CIKM draft claimed saturation.
    forward, chosen = [], []
    for _ in range(3):
        best = None
        for feat in APPROACH_7:
            if feat in chosen:
                continue
            res, _ = evaluate(records, chosen + [feat])
            if best is None or res['pooled_auc'] > best[1]['pooled_auc']:
                best = (feat, res)
        chosen.append(best[0])
        forward.append({'features': list(chosen), **{k: best[1][k] for k in keep}})
    return {'leave_one_out': lofo, 'alone': alone, 'groups': groups, 'forward_addition': forward}


def paired_comparison(a, b):
    pids = sorted(set(a) & set(b))
    delta = np.asarray([a[p] - b[p] for p in pids])
    rng = np.random.default_rng(20260904)
    means = rng.choice(delta, size=(10000, len(delta)), replace=True).mean(axis=1)
    return {
        'n_participants': len(pids),
        'mean_participant_auc_delta': float(delta.mean()),
        'bootstrap_ci95': np.quantile(means, [.025, .975]).tolist(),
        'bootstrap_resamples': 10000, 'bootstrap_seed': 20260904,
        'wilcoxon_two_sided_p': float(wilcoxon(delta).pvalue) if np.any(delta) else 1.0,
    }


def run(args):
    root = args.repo_root.resolve()
    sys.path.insert(0, str(root / 'notebooks-v2'))
    # Fixations are read only when a gaze-defined policy is requested
    # (gaze-gated sampling times or the fixation-5 window boundary); they
    # never select rows or enter a feature. The default protocol reads none.
    import data_loader as dl
    needs_fixations = args.sampling == 'gaze-gated' or args.window != 'all'
    gaze_used_for = ([] if not needs_fixations else
                     (['cursor sampling times (fixation onsets)'] if args.sampling == 'gaze-gated' else [])
                     + (['window boundary (end of fifth fixation)'] if args.window != 'all' else []))
    tracker = args.tracker_js.resolve()
    bridge = Path(__file__).with_name('m4_cursor_tracker.mjs')
    source_files = {
        'producer': Path(__file__), 'bridge': bridge, 'tracker': tracker,
        'data_loader': root / 'notebooks-v2/data_loader.py',
        'substrate': root / 'data/aoi-typed/substrate.json',
        'exclusions': root / 'data/aoi-typed/alignment-exclusions.json',
    }
    hashes_before = {k: sha256(p) for k, p in source_files.items()}
    substrate = json.loads(source_files['substrate'].read_text())
    maps = sorted((root / 'data/aoi-typed').glob('p*.json'))
    digest = hashlib.sha256()
    for path in maps:
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    if digest.hexdigest()[:16] != substrate['typed_maps_content_hash']:
        raise ValueError('Typed AOI content differs from substrate stamp')
    exclusions = dl.typed_alignment_exclusions()
    if len(exclusions) != substrate['n_excluded'] or len(maps) != substrate['n_trial_maps']:
        raise ValueError('Substrate counts disagree with files/exclusions')
    tids = dl.get_trial_ids()
    if args.limit:
        # Spread smoke tests across participants rather than p001 only.
        by_pid = {}
        for tid in tids:
            by_pid.setdefault(tid.split('-')[0], []).append(tid)
        tids = [ts[i] for i in range(max(map(len, by_pid.values())))
                for ts in by_pid.values() if i < len(ts)][:args.limit]
    conditions = {f'buf{b}': [] for b in args.buffers}
    counts, geometry_counts = Counter(), Counter()
    removed_samples = {f'buf{b}': 0 for b in args.buffers}
    changed_trials = {f'buf{b}': 0 for b in args.buffers}
    last_move_gaps, last_move_to_anchor, anchor_to_click = [], [], []
    post_anchor_samples = 0
    geometry_hash = hashlib.sha256()
    input_hash = hashlib.sha256()
    batch = []

    def flush():
        for result in track_batch(batch, bridge, tracker):
            for condition, records in result.items():
                conditions[condition].extend(records)
        batch.clear()

    for i, tid in enumerate(tids):
        if tid in exclusions:
            counts['alignment_excluded'] += 1
            continue
        # Record consumed inputs (hashes only, no private telemetry in output).
        for p in (dl.MOUSE_DIR / f'{tid}.csv', dl.METADATA_DIR / f'{tid}.xml'):
            input_hash.update(p.name.encode()); input_hash.update(p.read_bytes())
        cards = dl.load_typed_aois(tid)
        geometry = dl.get_trial_geometry(tid)
        if geometry is None:
            raise ValueError(f'{tid}: missing coordinate geometry')
        events, _, clicks = dl.load_mouse_events(tid, space='document')
        fixations = dl.load_fixations(tid) if needs_fixations else None
        trial, reason = prepare_trial(tid, cards, events, clicks, geometry, args.buffers,
                                      anchor=args.anchor, downsample_hz=args.downsample_hz,
                                      window=args.window, fixations=fixations)
        if trial is not None and args.sampling == 'gaze-gated':
            trial['samples'] = gaze_gated_samples(
                trial['samples'], [f['t'] for f in fixations if math.isfinite(f['t'])])
            if len({t for t, _ in trial['samples'] if t < trial['anchor_t'] - max(args.buffers)}) < 2:
                trial, reason = None, 'insufficient_prebuffer_gaze_gated_samples'
        counts[reason] += 1
        if trial is not None:
            geometry_counts[geometry['derived']] += 1
            geometry_hash.update(json.dumps([tid, geometry], sort_keys=True).encode())
            anchor_t = trial['anchor_t']
            pre_click = [t for t, _ in trial['samples'] if t < trial['click_t']]
            pre_anchor = [t for t in pre_click if t < anchor_t]
            last_move_gaps.append(trial['click_t'] - max(pre_click))
            last_move_to_anchor.append(anchor_t - max(pre_anchor))
            anchor_to_click.append(trial['click_t'] - anchor_t)
            post_anchor_samples += len(pre_click) - len(pre_anchor)
            for b in args.buffers:
                removed = sum(anchor_t - b <= t < anchor_t for t in pre_anchor)
                removed_samples[f'buf{b}'] += removed
                changed_trials[f'buf{b}'] += int(removed > 0)
            batch.append(trial)
        if len(batch) >= 25:
            flush()
        if (i + 1) % 500 == 0:
            print(f'{i + 1}/{len(tids)} trials inspected; {counts["included"]} included', flush=True)
    if batch:
        flush()
    metrics, fold_results, ablations = {}, {}, {}
    keys = None
    for condition, records in conditions.items():
        current_keys = [(r['trial_id'], r['position'], r['was_clicked']) for r in records]
        if keys is not None and current_keys != keys:
            raise ValueError('Cross-buffer record/label population mismatch')
        keys = current_keys
        if len({(r['trial_id'], r['position']) for r in records}) != len(records):
            raise ValueError('Duplicate trial/AOI row')
        metrics[condition], fold_results[condition] = {}, {}
        for name, features in MODELS:
            result, folds = evaluate(records, features)
            metrics[condition][name], fold_results[condition][name] = result, folds
            print(f'{condition} {name}: pooled AUC={result["pooled_auc"]:.6f}; '
                  f'fold mean={result["fold_auc_mean"]:.6f}; MRR@10={result["mrr_at_10"]:.4f}',
                  flush=True)
        if not args.no_ablation:
            ablations[condition] = feature_ablation(records, metrics[condition]['M4-7'])
            print(f'{condition} feature ablation done', flush=True)
    if args.feature_cache:
        # Per-record features for downstream producers (§4.2/§4.3/§4.6 re-runs).
        # Derived aggregates only, like the existing LAB caches; kept out of git.
        args.feature_cache.parent.mkdir(parents=True, exist_ok=True)
        args.feature_cache.write_text(json.dumps({
            'protocol_note': 'per-(trial, position) records from m4_cursor_aoi_rerun.py; see summary.json in the matching output dir',
            'anchor_event': args.anchor, 'sampling': args.sampling, 'window': args.window,
            'downsample_hz': args.downsample_hz, 'conditions': conditions}, allow_nan=False))
        print(f'Wrote feature cache: {args.feature_cache}', flush=True)
    paired = {}
    for condition, models in fold_results.items():
        paired[f'{condition}_M4-7_vs_M1'] = paired_comparison(models['M4-7'], models['M1'])
        paired[f'{condition}_M3_vs_M4-7'] = paired_comparison(models['M3'], models['M4-7'])
    hashes_after = {k: sha256(p) for k, p in source_files.items()}
    quantiles = ['min', 'q25', 'median', 'q75', 'max']

    def q(values):
        return dict(zip(quantiles, np.quantile(values, [0, .25, .5, .75, 1]).tolist()))
    if hashes_after != hashes_before:
        raise RuntimeError('Source changed during run; refusing to publish aggregate')
    payload = {
        'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'status': 'smoke_test' if args.limit else 'full_corpus',
        'protocol': {
            'regime': 'LAB dataset; cursor-only predictors and row selection',
            'rank_type': 'typed', 'feature_source': 'approach-retreat ResultFeatureTracker',
            'gaze_used': bool(gaze_used_for), 'gaze_used_for': gaze_used_for,
            'buffers_ms': args.buffers, 'anchor_event': args.anchor,
            'sampling': args.sampling, 'downsample_hz': args.downsample_hz, 'window': args.window,
            'sample_events': (f'native mousemove only; t < {args.anchor} anchor minus buffer'
                              if args.sampling == 'native' else
                              f'cursor y interpolated from native mousemove at fixation onsets; t < {args.anchor} anchor minus buffer'),
            'coordinate_space': 'document CSS px; typed AOI centers divided by canonical ratio_y',
            'distance_axis': 'vertical |pageY - AOI center y|; the browser tracker is one-dimensional',
            'proximity_px': 100, 'candidate_population': 'all main-axis typed AOIs in included trials',
            'ranking_metrics': 'per-trial MRR@10 and top-1 hit rate (NDCG@1, one clicked AOI per trial) on held-out probabilities',
            'click_label': 'final click; strict unique X+Y typed-box containment; ambiguous/off-box trials excluded',
            'cross_buffer_population': 'identical; at least two distinct timestamps before largest buffer cutoff',
            'visibility_gate': 'none; offline all-AOI replay, not browser IntersectionObserver or 20 Hz lifecycle parity',
            'estimator': 'LOSO StandardScaler + balanced LogisticRegression(C=1, max_iter=5000)',
            'scope': 'new typed experiment; not a numeric replacement for historical organic_hybrid or gaze-gated M4',
        },
        'substrate': substrate, 'counts': {'discovered_trials': len(tids), **dict(counts)},
        'geometry_sources_included': dict(geometry_counts), 'conditions': metrics, 'paired': paired,
        'feature_ablation': ablations,
        'ablation_skipped': bool(args.no_ablation),
        'sampling_diagnostics': {
            'anchor_event': args.anchor,
            'samples_removed_relative_to_buf0': removed_samples,
            'trials_changed_relative_to_buf0': changed_trials,
            'post_anchor_samples_excluded_at_every_buffer': post_anchor_samples,
            'last_mousemove_to_click_ms_quantiles': q(last_move_gaps),
            'last_mousemove_to_anchor_ms_quantiles': q(last_move_to_anchor),
            'anchor_to_click_ms_quantiles': q(anchor_to_click),
            'interpretation': 'An unchanged stream does not test removal of terminal approach; time buffers alone may leave the entire approach intact.',
        },
        'provenance': {
            'sha256': hashes_after, 'mouse_and_metadata_sha256': input_hash.hexdigest(),
            'geometry_values_sha256': geometry_hash.hexdigest(),
            'feature_records_sha256': {c: hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
                                       for c, r in conditions.items()},
            'record_keys_and_labels_sha256': hashlib.sha256(json.dumps(keys).encode()).hexdigest(),
            'python': sys.version.split()[0], 'numpy': np.__version__,
            'node': subprocess.check_output(['node', '--version'], text=True).strip(),
        },
    }
    import sklearn
    payload['provenance']['sklearn'] = sklearn.__version__
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / 'summary.json'
    out.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(f'Wrote aggregate only: {out}')
    return payload


def parse_args():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=root)
    parser.add_argument('--tracker-js', type=Path,
                        default=root.parent / 'approach-retreat/src/approach-retreat.js')
    parser.add_argument('--output-dir', type=Path, default=root / 'scripts/output/m4_cursor_aoi')
    parser.add_argument('--buffers', type=int, nargs='+', default=[0, 500])
    parser.add_argument('--anchor', choices=ANCHORS, default='click',
                        help='event whose timestamp the buffer cutoff is measured from')
    parser.add_argument('--sampling', choices=SAMPLINGS, default='native',
                        help='native mousemove samples, or cursor interpolated at fixation onsets (§4.3 ceiling)')
    parser.add_argument('--downsample-hz', type=float, default=0,
                        help='greedy-thin native mousemove to this rate before extraction (0 = native)')
    parser.add_argument('--window', choices=WINDOWS, default='all',
                        help='restrict samples to before/after the end of the fifth fixation')
    parser.add_argument('--feature-cache', type=Path, default=None,
                        help='also write per-record features here (kept out of git)')
    parser.add_argument('--no-ablation', action='store_true',
                        help='skip the feature sweeps (sampling-rate and window runs)')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if not args.buffers or min(args.buffers) < 0 or len(set(args.buffers)) != len(args.buffers):
        parser.error('buffers must be distinct nonnegative milliseconds')
    if args.limit < 0 or args.downsample_hz < 0:
        parser.error('limit and downsample-hz must be nonnegative')
    return args


if __name__ == '__main__':
    run(parse_args())
