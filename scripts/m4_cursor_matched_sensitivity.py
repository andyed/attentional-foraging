"""Refit cursor-only window/rate sensitivities on whole-trial intersections.

Replays each September 6 sensitivity with the canonical producer and checks
its feature hash against the retained aggregate before matching anything.
Native features come from the press-grid cache. Only aggregates and hashes
leave the local temporary cache. No telemetry or per-participant scores are
written to the result. Run from attentional-foraging with its .venv Python.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from m4_cursor_aoi_claims import load_and_validate
from m4_cursor_aoi_rerun import APPROACH_7, evaluate, paired_comparison, run as replay


SPECS = {
    'pre5': ('m4_cursor_aoi_window_pre5', 'pre5', 0),
    'post5': ('m4_cursor_aoi_window_post5', 'post5', 0),
    '30hz': ('m4_cursor_aoi_rate_30hz', 'all', 30),
    '15hz': ('m4_cursor_aoi_rate_15hz', 'all', 15),
    '5hz': ('m4_cursor_aoi_rate_5hz', 'all', 5),
    '1hz': ('m4_cursor_aoi_rate_1hz', 'all', 1),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_cache(cache, summary):
    """Fail closed if a cache belongs to another stream or aggregate."""
    for key in ('anchor_event', 'sampling', 'window', 'downsample_hz'):
        if cache[key] != summary['protocol'][key]:
            raise ValueError(f'Cache protocol mismatch: {key}')
    records = cache['conditions']['buf500']
    if digest(records) != summary['provenance']['feature_records_sha256']['buf500']:
        raise ValueError('Cache feature hash differs from retained aggregate')
    return records


def match_trials(conditions):
    """Intersect trial IDs, then require complete identical AOI/label lattices.

    Dropping individual unmatched AOIs could remove negatives or targets and
    change the task. A shared trial with inconsistent rows therefore fails.
    """
    indexed = {}
    for name, records in conditions.items():
        trials = {}
        for row in records:
            trial = trials.setdefault(row['trial_id'], {})
            position = row['position']
            if position in trial:
                raise ValueError(f'Duplicate trial/AOI row in {name}')
            if row['was_clicked'] not in (0, 1):
                raise ValueError(f'Nonbinary click label in {name}')
            trial[position] = row
        for trial in trials.values():
            if len(trial) < 2 or sum(r['was_clicked'] for r in trial.values()) != 1:
                raise ValueError(f'Expected one click and at least two AOIs in {name}')
        indexed[name] = trials
    shared = sorted(set.intersection(*(set(t) for t in indexed.values())))
    if not shared:
        raise ValueError('No shared trials')
    reference = next(iter(indexed.values()))
    for tid in shared:
        lattice = {p: (r['was_clicked'], r['etype']) for p, r in reference[tid].items()}
        for name, trials in indexed.items():
            candidate = {p: (r['was_clicked'], r['etype']) for p, r in trials[tid].items()}
            if candidate != lattice:
                raise ValueError(f'AOI/label lattice mismatch in shared trial ({name})')
    matched = {
        name: [trials[tid][p] for tid in shared for p in sorted(trials[tid])]
        for name, trials in indexed.items()
    }
    rows = next(iter(matched.values()))
    population = {
        'n_trials': len(shared), 'n_records': len(rows),
        'n_participants': len({tid.split('-')[0] for tid in shared}),
        'shared_trial_ids_sha256': digest(shared),
        'shared_keys_and_labels_sha256': digest([
            [r['trial_id'], r['position'], r['was_clicked'], r['etype']] for r in rows]),
        'included_trials_before_matching': {n: len(t) for n, t in indexed.items()},
        'excluded_trials_by_intersection': {n: len(t) - len(shared) for n, t in indexed.items()},
        'matched_feature_sha256': {n: digest(r) for n, r in matched.items()},
    }
    return matched, population


def fit_group(conditions):
    matched, population = match_trials(conditions)
    # Position/labels are identical after matching, so fit M1 once per group.
    position, _ = evaluate(matched['native'], ['position'])
    metrics, folds = {}, {}
    for name, rows in matched.items():
        metrics[name], folds[name] = evaluate(rows, APPROACH_7)
        print(f"matched {name}: AUC={metrics[name]['pooled_auc']:.6f}; "
              f"trials={population['n_trials']}", flush=True)
    pairs = {}
    comparisons = [(n, 'native') for n in conditions if n != 'native']
    if 'pre5' in conditions:
        comparisons.append(('post5', 'pre5'))
    for a, b in comparisons:
        pairs[f'{a}_minus_{b}'] = {
            'pooled_auc_delta': metrics[a]['pooled_auc'] - metrics[b]['pooled_auc'],
            **paired_comparison(folds[a], folds[b]),
        }
    return {'population': population, 'M1_position': position,
            'M4_7': metrics, 'paired': pairs}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument('--cache-dir', type=Path, help='optional local scratch cache for resumable replay; do not commit')
    ap.add_argument('--output-dir', type=Path)
    args = ap.parse_args()
    root = args.repo_root.resolve()
    output = args.output_dir or root / 'scripts/output/m4_cursor_matched_sensitivity'
    tracker = root.parent / 'approach-retreat/src/approach-retreat.js'
    native_path = root / 'scripts/output/m4_cursor_aoi_mousedown/summary.json'
    native, _, _, _, native_sha = load_and_validate(
        native_path, [0, 250, 500, 1000], 'mousedown', repo_root=root)
    native_cache = root / 'AdSERP/data/cursor-only-typed-features-mousedown.json'
    records = {'native': validate_cache(json.loads(native_cache.read_text()), native)}
    inputs = {'native': {'summary': str(native_path.relative_to(root)),
                         'summary_sha256': native_sha,
                         'cache_sha256': sha256(native_cache),
                         'feature_sha256': digest(records['native'])}}
    script_sha = sha256(__file__)
    context = nullcontext(args.cache_dir) if args.cache_dir else tempfile.TemporaryDirectory(prefix='m4-matched-')
    with context as cache_dir:
        cache_dir = Path(cache_dir)
        for name, (directory, window, hz) in SPECS.items():
            expected_path = root / 'scripts/output' / directory / 'summary.json'
            expected = json.loads(expected_path.read_text())
            protocol = expected['protocol']
            if (expected['status'] != 'full_corpus' or expected['schema_version'] != 1
                    or expected['substrate'] != native['substrate']
                    or any(expected['provenance']['sha256'][k] != v
                           for k, v in native['provenance']['sha256'].items() if k != 'producer')
                    or protocol['anchor_event'] != 'mousedown' or protocol['rank_type'] != 'typed'
                    or protocol['sampling'] != 'native' or protocol['window'] != window
                    or protocol['downsample_hz'] != hz or protocol['buffers_ms'] != [0, 500]):
                raise ValueError(f'Unexpected retained sensitivity protocol/source: {name}')
            cache_path = cache_dir / name / 'features.json'
            if not cache_path.exists():
                replay(argparse.Namespace(
                    repo_root=root, tracker_js=tracker, output_dir=cache_path.parent,
                    buffers=[0, 500], anchor='mousedown', flavor='typed', sampling='native',
                    downsample_hz=hz, window=window, feature_cache=cache_path,
                    no_ablation=True, limit=0))
            # The flavor option was added after these sensitivity runs. Require
            # current-code replay plus identical retained feature hashes, not
            # an assumption that the producer edit leaves typed rows unchanged.
            replay_summary = json.loads((cache_path.parent / 'summary.json').read_text())
            if replay_summary['provenance']['sha256'] != native['provenance']['sha256']:
                raise ValueError(f'Stale replay cache source: {name}')
            cache = json.loads(cache_path.read_text())
            validate_cache(cache, replay_summary)
            records[name] = validate_cache(cache, expected)
            inputs[name] = {'summary': str(expected_path.relative_to(root)),
                            'summary_sha256': sha256(expected_path),
                            'retained_producer_sha256': expected['provenance']['sha256']['producer'],
                            'replay_producer_sha256': replay_summary['provenance']['sha256']['producer'],
                            'cache_sha256': sha256(cache_path),
                            'feature_sha256': digest(records[name])}
        groups = {
            'windows': fit_group({n: records[n] for n in ['native', 'pre5', 'post5']}),
            'rates': fit_group({n: records[n] for n in ['native', '30hz', '15hz', '5hz', '1hz']}),
        }
    # Refuse an output attributed to sources that changed during the fits.
    load_and_validate(native_path, [0, 250, 500, 1000], 'mousedown', repo_root=root)
    if sha256(__file__) != script_sha or any(
            sha256(root / item['summary']) != item['summary_sha256'] for item in inputs.values()):
        raise ValueError('Source or retained input changed during analysis')
    payload = {
        'schema_version': 1, 'status': 'full_corpus_matched_sensitivity',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'protocol': {
            'regime': 'LAB, AdSERP, typed; cursor-only predictors',
            'anchor_event': 'mousedown', 'buffer_ms': 500,
            'matching': 'whole-trial intersection within each comparison family; identical AOI positions, types and click labels',
            'eligibility': 'native retains the headline 1000 ms prebuffer quality gate; sensitivities retain their original 500 ms gate before intersection',
            'estimator': native['protocol']['estimator'],
            'features': APPROACH_7,
            'gaze_used_for': {'windows': ['end of fifth fixation defines the time boundary and window eligibility'], 'rates': []},
            'uncertainty': 'paired participant held-out AUC differences; 10000 bootstrap resamples and two-sided Wilcoxon; exploratory comparisons, no multiplicity correction',
            'limits': ['conditional on shared-trial eligibility; not a full-population estimate',
                       'windows differ in duration/sample count and post5 may retain terminal approach',
                       'no equivalence margin or test; small observed differences do not establish rate invariance',
                       'offline all-AOI replay; browser visibility/lifecycle parity untested'],
        },
        'groups': groups, 'inputs': inputs,
        'provenance': {'producer_sha256': script_sha,
                       'source_sha256': native['provenance']['sha256'],
                       'numpy': native['provenance']['numpy'],
                       'sklearn': native['provenance']['sklearn'],
                       'substrate': native['substrate']},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(f"Wrote {output / 'summary.json'}", flush=True)


if __name__ == '__main__':
    main()
