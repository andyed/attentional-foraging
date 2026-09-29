"""Matched click-prediction additions to cursor-only M4 (500 ms pre-press).

Run: .venv/bin/python scripts/m4_return_scroll_ablation.py
Outputs are separate from the canonical cache; no gaze-based row selection.
"""
from __future__ import annotations

import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.stats import spearmanr

from m4_cursor_aoi_rerun import APPROACH_7, evaluate, paired_comparison, prepare_trial, sha256

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl

OUT = ROOT / 'scripts/output/m4_return_scroll_ablation'
SOURCE = ROOT / 'scripts/output/m4_cursor_aoi_mousedown/summary.json'
CACHE = ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json'
CURSOR = 'cursor_return_count_5s'
SCROLL = 'scroll_regression_count'
GAZE = 'gaze_return_count'
NODWELL = [f for f in APPROACH_7 if f != 'dwell_in_proximity_ms']
MODELS = {
    'M4': APPROACH_7,
    'M3': ['position'] + APPROACH_7,
    'M4+cursor_returns': APPROACH_7 + [CURSOR],
    'M4+scroll_regressions': APPROACH_7 + [SCROLL],
    'M4+cursor+scroll': APPROACH_7 + [CURSOR, SCROLL],
    'M4-dwell': NODWELL,
    'M4-dwell+cursor': NODWELL + [CURSOR],
    'M4-dwell+scroll': NODWELL + [SCROLL],
    'M4-dwell+cursor+scroll': NODWELL + [CURSOR, SCROLL],
    'M4+cursor_returns_unmerged': APPROACH_7 + ['cursor_return_count_unmerged'],
    'M4+upward_scroll_gestures': APPROACH_7 + ['upward_scroll_gesture_count'],
    'M4+gaze_returns': APPROACH_7 + [GAZE, 'gaze_unavailable'],
    'M4+gaze_regressive_returns': APPROACH_7 + ['gaze_regressive_return_count', 'gaze_unavailable'],
}


def cursor_returns(samples, cards, merge_ms):
    """Native mousemove, screenshot XY boxes +40 px, >=100 ms episodes.

    Consistent with downstream visit finalization: a return within merge_ms
    of the previous qualifying exit is merged; counts are max(visits-1, 0).
    Stop the final episode at the last retained mousemove, never at the press.
    Overlapping expanded boxes use the lowest display position, explicitly.
    """
    boxes = [(c['position'], c['x']-40, c['x']+c['width']+40,
              c['y']-40, c['y']+c['height']+40) for c in sorted(cards, key=lambda c: c['position'])]
    visits, last_exit = Counter(), {}
    current, entered = None, None

    def finish(pos, start, end):
        if end-start < 100:
            return
        previous = last_exit.get(pos)
        if previous is None or merge_ms is None or start-previous > merge_ms:
            visits[pos] += 1
        last_exit[pos] = end

    for t, x, y in samples:
        hit = next((p for p, x0, x1, y0, y1 in boxes if x0 <= x <= x1 and y0 <= y <= y1), None)
        if hit != current:
            if current is not None:
                finish(current, entered, t)
            current, entered = hit, t
    if current is not None and samples:
        finish(current, entered, samples[-1][0])
    return {p: max(n-1, 0) for p, n in visits.items()}


def scroll_counts(scrolls):
    """Historical NB09 down-to-up reversals (>5 CSS px/event) plus NB07a sensitivity."""
    previous, reversals = None, 0
    for (_, a), (_, b) in zip(scrolls, scrolls[1:]):
        dy = b-a
        direction = 'up' if dy < -5 else ('down' if dy > 5 else None)
        if direction is None:
            continue
        reversals += int(direction == 'up' and previous == 'down')
        previous = direction
    runs = []
    for item in scrolls:
        if not runs or not 0 <= item[0]-runs[-1][-1][0] <= 200:
            runs.append([item])
        else:
            runs[-1].append(item)
    upward = sum(run[-1][1]-run[0][1] < -10 for run in runs)
    return reversals, upward


def gaze_returns(fixations, cards, cutoff):
    """All re-entries and NB22 regressive re-entries, using typed Y bands.

    Off-band fixations break a visit. No claim of strict XY fixation assignment.
    Only fixation onsets before cutoff enter counts; duration is not a feature.
    """
    bands = sorted((c['y'], c['y']+c['height'], c['position']) for c in cards)
    seen, last, max_seen = set(), None, -1
    returns, regressive = Counter(), Counter()
    for fix in sorted(fixations, key=lambda f: f['t']):
        if fix['t'] >= cutoff:
            continue
        p = next((p for top, bottom, p in bands if top <= fix['y'] <= bottom), None)
        if p is None:
            last = None
            continue
        if p != last and p in seen:
            returns[p] += 1
            regressive[p] += int(p < max_seen)
        seen.add(p)
        max_seen, last = max(max_seen, p), p
    return returns, regressive


def extract(tid):
    events, scrolls, clicks = dl.load_mouse_events(tid, space='document')
    cards = [c for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0]
    geometry = dl.get_trial_geometry(tid)
    trial, reason = prepare_trial(tid, cards, events, clicks, geometry, [0, 250, 500, 1000], anchor='mousedown')
    if trial is None:
        raise ValueError(f'Canonical included trial no longer included: {tid}: {reason}')
    cutoff = trial['anchor_t']-500
    sx, sy = geometry['ratio_x'], geometry['ratio_y']
    mouse = [(t, x*sx, y*sy) for t, event, x, y in events
             if event == 'mousemove' and t < cutoff and all(math.isfinite(v) for v in (t, x, y))]
    scroll = [(t, y) for t, y in scrolls if t < cutoff and math.isfinite(y)]
    # The canonical cohort rejects nonmonotonic mousemove streams, not scroll
    # streams. Preserve logged scroll order for the historical direction count;
    # never silently sort the trace or drop a matched trial. Gesture runs split
    # at a backwards timestamp, and every such boundary is reported.
    scroll_time_reversals = [{'from_ms': a[0], 'to_ms': b[0],
                             'latest_endpoint_before_cutoff_ms': cutoff-max(a[0], b[0])}
                            for a, b in zip(scroll, scroll[1:]) if b[0] < a[0]]
    merged = cursor_returns(mouse, cards, 5000)
    unmerged = cursor_returns(mouse, cards, None)
    reversals, gestures = scroll_counts(scroll)
    fix_path = dl.FIXATION_DIR / f'{tid}.csv'
    fixes = dl.load_fixations(tid) if fix_path.exists() else []
    valid_fixes = [f for f in fixes if all(math.isfinite(f[k]) for k in ('t', 'y')) and f['t'] < cutoff]
    gaze, regaze = gaze_returns(valid_fixes, cards, cutoff)
    rows = {c['position']: {
        CURSOR: merged.get(c['position'], 0),
        'cursor_return_count_unmerged': unmerged.get(c['position'], 0),
        SCROLL: reversals, 'upward_scroll_gesture_count': gestures,
        GAZE: gaze.get(c['position'], 0),
        'gaze_regressive_return_count': regaze.get(c['position'], 0),
        'gaze_unavailable': int(not valid_fixes),
    } for c in cards}
    return tid, rows, {'cutoff_ms': cutoff, 'click_position': trial['click_position'],
                       'geometry': geometry, 'scroll_time_reversals': scroll_time_reversals,
                       'gaze_file_exists': fix_path.exists(),
                       'gaze_unavailable': int(not valid_fixes),
                       'fixation_sha256': sha256(fix_path) if fix_path.exists() else None}


def check_raw_sources(source):
    """Match canonical raw mouse/metadata inputs, including its rejected trials."""
    exclusions = dl.typed_alignment_exclusions()
    files = [p for tid in dl.get_trial_ids() if tid not in exclusions
             for p in (dl.MOUSE_DIR/f'{tid}.csv', dl.METADATA_DIR/f'{tid}.xml')]
    digest = hashlib.sha256()
    with ThreadPoolExecutor(max_workers=8) as pool:
        for path, content in zip(files, pool.map(lambda p: p.read_bytes(), files)):
            digest.update(path.name.encode())
            digest.update(content)
    actual = digest.hexdigest()
    assert actual == source['provenance']['mouse_and_metadata_sha256'], 'Raw inputs changed since baseline'
    return actual


def holm(ps):
    ordered = sorted(ps, key=ps.get)
    adjusted, running = {}, 0.0
    for i, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered)-i)*ps[key]))
        adjusted[key] = running
    return adjusted


def main():
    source = json.loads(SOURCE.read_text())
    cache = json.loads(CACHE.read_text())
    assert (cache['anchor_event'], cache['sampling'], cache['window'], cache['downsample_hz']) == ('mousedown', 'native', 'all', 0)
    records = cache['conditions']['buf500']
    feature_hash = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    assert feature_hash == source['provenance']['feature_records_sha256']['buf500']
    keys = [(r['trial_id'], r['position'], r['was_clicked']) for r in records]
    assert hashlib.sha256(json.dumps(keys).encode()).hexdigest() == source['provenance']['record_keys_and_labels_sha256']
    assert len(set((tid, p) for tid, p, _ in keys)) == len(records)
    digest = hashlib.sha256()
    for path in sorted((ROOT/'data/aoi-typed').glob('p*.json')):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    assert digest.hexdigest()[:16] == source['substrate']['typed_maps_content_hash']
    baseline, folds = evaluate(records, APPROACH_7)
    shipped = source['conditions']['buf500']['M4-7']['pooled_auc']
    gate = {'status': 'ok', 'shipped': shipped, 'reproduced': baseline['pooled_auc'],
            'delta': baseline['pooled_auc']-shipped, 'tolerance': 1e-8,
            'source': str(SOURCE.relative_to(ROOT)), 'source_path': 'conditions.buf500.M4-7.pooled_auc'}
    assert abs(gate['delta']) <= gate['tolerance'], gate
    print(f'Reproduction gate passed: M4 AUC {baseline["pooled_auc"]:.12f}; delta {gate["delta"]}', flush=True)
    raw_hash = check_raw_sources(source)
    print('Canonical raw mouse/metadata hash matched.', flush=True)
    tids = list(dict.fromkeys(r['trial_id'] for r in records))
    by_trial, trial_info = {}, {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (tid, rows, info) in enumerate(pool.map(extract, tids), 1):
            by_trial[tid], trial_info[tid] = rows, info
            if i % 400 == 0:
                print(f'Extracted {i}/{len(tids)} trials', flush=True)
    geometry_hash = hashlib.sha256()
    for tid in tids:
        geometry_hash.update(json.dumps([tid, trial_info[tid]['geometry']], sort_keys=True).encode())
    assert geometry_hash.hexdigest() == source['provenance']['geometry_values_sha256'], 'Geometry changed'
    for row in records:
        tid, p = row['trial_id'], row['position']
        assert bool(row['was_clicked']) == (p == trial_info[tid]['click_position'])
        row.update(by_trial[tid][p])
    assert all(set(by_trial[tid]) == {r['position'] for r in records if r['trial_id'] == tid} for tid in tids)
    metrics, all_folds = {'M4': baseline}, {'M4': folds}
    for name, features in MODELS.items():
        if name == 'M4':
            continue
        metrics[name], all_folds[name] = evaluate(records, features)
        print(f'{name}: AUC={metrics[name]["pooled_auc"]:.9f}; MRR={metrics[name]["mrr_at_10"]:.6f}', flush=True)
    assert abs(metrics['M3']['pooled_auc']-source['conditions']['buf500']['M3']['pooled_auc']) < 1e-8
    contrasts = {}
    for name in MODELS:
        if name == 'M4':
            continue
        contrasts[name+' vs M4'] = paired_comparison(all_folds[name], all_folds['M4'])
    for addition in ('cursor', 'scroll', 'cursor+scroll'):
        name = 'M4-dwell+'+addition
        contrasts[name+' vs M4-dwell'] = paired_comparison(all_folds[name], all_folds['M4-dwell'])
        with_dwell = {'cursor': 'M4+cursor_returns', 'scroll': 'M4+scroll_regressions', 'cursor+scroll': 'M4+cursor+scroll'}[addition]
        interaction = {p: (all_folds[name][p]-all_folds['M4-dwell'][p]) -
                           (all_folds[with_dwell][p]-all_folds['M4'][p]) for p in folds}
        contrasts['dwell attenuation: '+addition] = paired_comparison(interaction, dict.fromkeys(folds, 0.0))
    primary = ['M4+cursor_returns vs M4', 'M4+scroll_regressions vs M4', 'M4+cursor+scroll vs M4']
    adjusted = holm({k: contrasts[k]['wilcoxon_two_sided_p'] for k in primary})
    for key in primary:
        contrasts[key]['holm_p_primary_family_3'] = adjusted[key]
    feature_summary = {}
    for feature in (CURSOR, 'cursor_return_count_unmerged', SCROLL, 'upward_scroll_gesture_count', GAZE, 'gaze_regressive_return_count'):
        values = np.array([r[feature] for r in records])
        feature_summary[feature] = {
            'nonzero_AOI_rows': int((values > 0).sum()),
            'trials_with_nonzero': len({r['trial_id'] for r in records if r[feature] > 0}),
            'max': int(values.max()),
            'spearman_with_dwell_all_AOI_rows': float(spearmanr(values, [r['dwell_in_proximity_ms'] for r in records]).statistic),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    definitions = {
        CURSOR: 'Per AOI: max(qualifying cursor visits - 1, 0); native mousemove only; screenshot XY typed box expanded 40 px; >=100 ms residence; qualifying visits separated by <=5000 ms merge. Expanded-box overlap assigned to lowest position. Last episode ends at last retained mousemove.',
        'cursor_return_count_unmerged': 'Same definition, but no gap merging; each qualifying re-entry counts. Sensitivity analysis.',
        SCROLL: 'Per trial: number of down-to-up transitions in consecutive scroll deltas; abs(delta)>5 document CSS px; smaller deltas ignored. Same value assigned to every AOI in the trial. Historical NB09 definition.',
        'upward_scroll_gesture_count': 'Per trial sensitivity: scroll samples grouped by gaps 0..200 ms; count groups with net delta < -10 document CSS px (NB07a). Timestamp reversals break a group.',
        GAZE: 'Per AOI: fixation-sequence re-entry to an already visited typed Y band; intervening other-band or off-band fixation breaks visit. Fixation onset strictly before cutoff; no duration feature; not strict XY assignment.',
        'gaze_regressive_return_count': 'Same gaze returns restricted to p < maximum previously visited position (NB22).',
        'gaze_unavailable': 'One when no valid fixation onset exists before cutoff, zero otherwise. Missing gaze counts encoded zero plus this explicit indicator; gaze never filters rows.',
    }
    payload = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': 'full_corpus', 'gate': gate,
        'protocol': {'target': 'Whether each typed main-axis AOI received the final click',
                     'cutoff': 'All added observations t < final mousedown - 500 ms',
                     'rows': len(records), 'trials': len(tids), 'participants': len(folds), 'clicks': sum(r['was_clicked'] for r in records),
                     'estimator': 'Unchanged canonical evaluate(): participant LOSO; train-fold StandardScaler + balanced LogisticRegression(C=1,max_iter=5000)',
                     'definitions': definitions,
                     'primary_models': primary, 'uncertainty': 'Paired participant AUC differences; 10000 participant bootstrap resamples, seed 20260904; two-sided Wilcoxon, Holm adjustment over three primary contrasts. Other contrasts exploratory. Training folds overlap; intervals summarize participant variability conditional on this corpus.',
                     'gaze_models': ['M4+gaze_returns', 'M4+gaze_regressive_returns'],
                     'interpretation': 'Incremental predictive performance, not conditional independence or causal mediation. Nonsignificance does not establish equivalence. No practical equivalence margin was prespecified. Trial-wide scroll count provides no direct within-trial ordering; refitting can still alter other coefficients.'},
        'gaze_coverage': {'unavailable_trials': [tid for tid in tids if trial_info[tid]['gaze_unavailable']],
                          'missing_files': [tid for tid in tids if not trial_info[tid]['gaze_file_exists']]},
        'scroll_timestamp_reversals': {tid: trial_info[tid]['scroll_time_reversals'] for tid in tids if trial_info[tid]['scroll_time_reversals']},
        'models': metrics, 'fold_aucs': all_folds, 'contrasts': contrasts, 'feature_summary': feature_summary,
        'provenance': {'source_summary_sha256': sha256(SOURCE), 'canonical_feature_hash': feature_hash,
                       'mouse_and_metadata_sha256': raw_hash, 'geometry_sha256': geometry_hash.hexdigest(),
                       'typed_maps_content_hash': digest.hexdigest()[:16],
                       'producer_sha256': sha256(__file__), 'evaluator_sha256': sha256(ROOT/'scripts/m4_cursor_aoi_rerun.py'),
                       'data_loader_sha256': sha256(ROOT/'notebooks-v2/data_loader.py'),
                       'fixation_manifest_sha256': hashlib.sha256(json.dumps({tid: trial_info[tid]['fixation_sha256'] for tid in tids}, sort_keys=True).encode()).hexdigest()},
    }
    (OUT/'features.json').write_text(json.dumps({'records': records, 'trial_info': trial_info}, allow_nan=False))
    payload['provenance']['derived_features_sha256'] = sha256(OUT/'features.json')
    (OUT/'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {OUT}/summary.json', flush=True)


if __name__ == '__main__':
    main()
