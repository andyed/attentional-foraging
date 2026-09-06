"""Cursor-only NB21 stream on post-collision typed AOIs.

This is a new, explicitly typed protocol, not a relabeling of the historical
organic_hybrid or fixation-gated results. Calls the actual approach-retreat
ResultFeatureTracker through Node; never loads fixation/pupil features or
conditions row inclusion on gaze. Does not modify the LAB feature caches.

Run from attentional-foraging:
  .venv/bin/python scripts/m4_cursor_aoi_rerun.py

Only aggregate metrics and hashes are saved. Default output is separate from
historical paper-output artifacts. --limit is for smoke tests, never claims.
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


def prepare_trial(tid, cards, events, clicks, geometry, buffers):
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
    cutoff = click[0] - max(buffers)
    if len({t for t, _ in samples if t < cutoff}) < 2:
        return None, 'insufficient_prebuffer_mousemove'
    return {
        'trial_id': tid, 'click_t': click[0], 'click_position': position,
        'buffers_ms': buffers, 'samples': samples,
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


def evaluate(records, features):
    X = np.asarray([[r[f] for f in features] for r in records], dtype=float)
    y = np.asarray([r['was_clicked'] for r in records], dtype=int)
    groups = np.asarray([r['trial_id'].split('-')[0] for r in records])
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
        'n_records': len(y), 'n_clicks': int(y.sum()),
    }, folds


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
    # No fixation loader is imported or called; gaze cannot select rows.
    import data_loader as dl
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
    last_move_gaps = []
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
        trial, reason = prepare_trial(tid, cards, events, clicks, geometry, args.buffers)
        counts[reason] += 1
        if trial is not None:
            geometry_counts[geometry['derived']] += 1
            geometry_hash.update(json.dumps([tid, geometry], sort_keys=True).encode())
            pre_click = [t for t, _ in trial['samples'] if t < trial['click_t']]
            last_move_gaps.append(trial['click_t'] - max(pre_click))
            for b in args.buffers:
                removed = sum(trial['click_t'] - b <= t < trial['click_t'] for t in pre_click)
                removed_samples[f'buf{b}'] += removed
                changed_trials[f'buf{b}'] += int(removed > 0)
            batch.append(trial)
        if len(batch) >= 25:
            flush()
        if (i + 1) % 500 == 0:
            print(f'{i + 1}/{len(tids)} trials inspected; {counts["included"]} included', flush=True)
    if batch:
        flush()
    metrics, fold_results = {}, {}
    keys = None
    for condition, records in conditions.items():
        current_keys = [(r['trial_id'], r['position'], r['was_clicked']) for r in records]
        if keys is not None and current_keys != keys:
            raise ValueError('Cross-buffer record/label population mismatch')
        keys = current_keys
        if len({(r['trial_id'], r['position']) for r in records}) != len(records):
            raise ValueError('Duplicate trial/AOI row')
        metrics[condition], fold_results[condition] = {}, {}
        for name, features in [('M1', ['position']), ('M4-7', APPROACH_7), ('M4-9', APPROACH_9)]:
            result, folds = evaluate(records, features)
            metrics[condition][name], fold_results[condition][name] = result, folds
            print(f'{condition} {name}: pooled AUC={result["pooled_auc"]:.6f}; '
                  f'fold mean={result["fold_auc_mean"]:.6f}', flush=True)
    paired = {f'{condition}_M4-7_vs_M1': paired_comparison(models['M4-7'], models['M1'])
              for condition, models in fold_results.items()}
    hashes_after = {k: sha256(p) for k, p in source_files.items()}
    if hashes_after != hashes_before:
        raise RuntimeError('Source changed during run; refusing to publish aggregate')
    payload = {
        'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'status': 'smoke_test' if args.limit else 'full_corpus',
        'protocol': {
            'regime': 'LAB dataset; cursor-only predictors and row selection',
            'rank_type': 'typed', 'feature_source': 'approach-retreat ResultFeatureTracker',
            'gaze_used': False, 'buffers_ms': args.buffers,
            'sample_events': 'native mousemove only; t < final click minus buffer',
            'coordinate_space': 'document CSS px; typed AOI centers divided by canonical ratio_y',
            'proximity_px': 100, 'candidate_population': 'all main-axis typed AOIs in included trials',
            'click_label': 'final click; strict unique X+Y typed-box containment; ambiguous/off-box trials excluded',
            'cross_buffer_population': 'identical; at least two distinct timestamps before largest buffer cutoff',
            'visibility_gate': 'none; offline all-AOI replay, not browser IntersectionObserver or 20 Hz lifecycle parity',
            'estimator': 'LOSO StandardScaler + balanced LogisticRegression(C=1, max_iter=5000)',
            'scope': 'new typed experiment; not a numeric replacement for historical organic_hybrid or gaze-gated M4',
        },
        'substrate': substrate, 'counts': {'discovered_trials': len(tids), **dict(counts)},
        'geometry_sources_included': dict(geometry_counts), 'conditions': metrics, 'paired': paired,
        'sampling_diagnostics': {
            'samples_removed_relative_to_buf0': removed_samples,
            'trials_changed_relative_to_buf0': changed_trials,
            'last_mousemove_to_click_ms_quantiles': dict(zip(
                ['min', 'q25', 'median', 'q75', 'max'],
                np.quantile(last_move_gaps, [0, .25, .5, .75, 1]).tolist())),
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
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if not args.buffers or min(args.buffers) < 0 or len(set(args.buffers)) != len(args.buffers):
        parser.error('buffers must be distinct nonnegative milliseconds')
    if args.limit < 0:
        parser.error('limit must be nonnegative')
    return args


if __name__ == '__main__':
    run(parse_args())
