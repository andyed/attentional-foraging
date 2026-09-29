"""Strict cursor-in-AOI dwell versus M4 on its unchanged click cohort.

Run: .venv/bin/python scripts/m4_raw_aoi_dwell.py
Requires the verified m4_return_scroll_ablation derived cache for geometry.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from sklearn.metrics import roc_auc_score

from m4_cursor_aoi_rerun import APPROACH_7, evaluate, paired_comparison, sha256, within_trial_ranking
from m4_return_scroll_ablation import check_raw_sources, holm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'notebooks-v2'))
import data_loader as dl

OUT = ROOT/'scripts/output/m4_raw_aoi_dwell'
SOURCE = ROOT/'scripts/output/m4_cursor_aoi_mousedown/summary.json'
CACHE = ROOT/'AdSERP/data/cursor-only-typed-features-mousedown.json'
PREVIOUS = ROOT/'scripts/output/m4_return_scroll_ablation'
DWELL = 'raw_aoi_dwell_ms'
LOG = 'log1p_raw_aoi_dwell_ms'
MODELS = {
    'position': ['position'],
    'AOI dwell': [DWELL],
    'AOI dwell + position': [DWELL, 'position'],
    'log AOI dwell': [LOG],
    'log AOI dwell + position': [LOG, 'position'],
    'proximity dwell': ['dwell_in_proximity_ms'],
    'M4': APPROACH_7,
    'M4 + position': ['position'] + APPROACH_7,
    'M4 + AOI dwell': APPROACH_7 + [DWELL],
    'M4 replacing proximity dwell': [f for f in APPROACH_7 if f != 'dwell_in_proximity_ms'] + [DWELL],
    'AOI dwell held to cutoff': ['raw_aoi_dwell_to_cutoff_ms'],
    'AOI dwell without scroll updates': ['raw_aoi_dwell_no_scroll_ms'],
}


def integrate_dwell(events, cards, cutoff, extend_to_cutoff=False, adjust_scroll=True):
    """Zero-order-hold XY containment, document CSS coordinates.

    Stop at the last retained native mousemove by default, matching M4's
    observed duration. No dwell is inferred before the first mousemove.
    Scroll events update document Y while holding the cursor's viewport Y.
    No margin, dwell threshold, visit merging, or gaze is used.
    """
    mm = [(t, e, x, y) for t, e, x, y in events if e == 'mousemove' and t < cutoff
          and all(math.isfinite(v) for v in (t, x, y))]
    if len({e[0] for e in mm}) < 2:
        raise ValueError('Need two retained native mousemove times')
    if any(b[0] < a[0] for a, b in zip(mm, mm[1:])):
        raise ValueError('Nonmonotonic mousemove stream')
    start, end = mm[0][0], cutoff if extend_to_cutoff else mm[-1][0]
    # Stable timestamp order is necessary to align mouse and scroll. A single
    # known nonmonotonic scroll trace is retained and reported, not dropped.
    stream = sorted((e for e in events if e[1] in ('mousemove', 'scroll')
                     and e[0] < cutoff and all(math.isfinite(v) for v in (e[0], e[3]))),
                    key=lambda e: e[0])
    totals = {c['position']: 0.0 for c in cards}
    scroll_y, pointer = 0.0, None
    previous_t = start

    def accumulate(stop):
        if pointer is None or stop <= previous_t:
            return
        x, viewport_y, fixed_page_y = pointer
        y = viewport_y+scroll_y if adjust_scroll else fixed_page_y
        for c in cards:
            if c['x'] <= x <= c['x']+c['width'] and c['y'] <= y <= c['y']+c['height']:
                totals[c['position']] += stop-previous_t

    for t, event, x, y in stream:
        if t > end:
            break
        if t >= start:
            accumulate(t)
            previous_t = t
        if event == 'scroll':
            scroll_y = y
        elif math.isfinite(x):
            pointer = (x, y-scroll_y, y)
    accumulate(end)
    assert all(0 <= v <= end-start for v in totals.values())
    return totals


def extract(arg):
    tid, info = arg
    events, scrolls, clicks = dl.load_mouse_events(tid, space='document')
    final_click = max(clicks, key=lambda c: c[0])
    cutoff = max(t for t, event, x, y in events if event == 'mousedown' and t <= final_click[0])-500
    assert cutoff == info['cutoff_ms']
    g = info['geometry']
    cards = [{**c, 'x': c['x']/g['ratio_x'], 'width': c['width']/g['ratio_x'],
              'y': c['y']/g['ratio_y'], 'height': c['height']/g['ratio_y']}
             for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0]
    primary = integrate_dwell(events, cards, cutoff)
    extended = integrate_dwell(events, cards, cutoff, extend_to_cutoff=True)
    no_scroll = integrate_dwell(events, cards, cutoff, adjust_scroll=False)
    reverse = sum(b[0] < a[0] for a, b in zip(scrolls, scrolls[1:]) if a[0] < cutoff and b[0] < cutoff)
    return tid, {p: {DWELL: value, LOG: float(np.log1p(value)),
                     'raw_aoi_dwell_to_cutoff_ms': extended[p],
                     'raw_aoi_dwell_no_scroll_ms': no_scroll[p]} for p, value in primary.items()}, reverse


def direct_dwell_score(records):
    """Unfitted baseline: rank results directly by their raw dwell milliseconds."""
    y = np.array([r['was_clicked'] for r in records], dtype=int)
    score = np.array([r[DWELL] for r in records])
    tids = [r['trial_id'] for r in records]
    groups = np.array([tid.split('-')[0] for tid in tids])
    folds = {str(p): float(roc_auc_score(y[groups == p], score[groups == p])) for p in sorted(set(groups))}
    values = np.array(list(folds.values()))
    return {'features': [DWELL], 'estimator': 'Unfitted raw dwell milliseconds as score',
            'pooled_auc': float(roc_auc_score(y, score)), 'fold_auc_mean': float(values.mean()),
            'fold_auc_sd': float(values.std(ddof=1)), 'n_folds': len(folds),
            'n_records': len(records), 'n_clicks': int(y.sum()),
            **within_trial_ranking(tids, y, score)}, folds


def main():
    source = json.loads(SOURCE.read_text())
    old = json.loads((PREVIOUS/'summary.json').read_text())
    assert sha256(PREVIOUS/'features.json') == old['provenance']['derived_features_sha256']
    info = json.loads((PREVIOUS/'features.json').read_text())['trial_info']
    records = json.loads(CACHE.read_text())['conditions']['buf500']
    feature_hash = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    assert feature_hash == source['provenance']['feature_records_sha256']['buf500']
    assert sha256(SOURCE) == old['provenance']['source_summary_sha256']
    digest = hashlib.sha256()
    for path in sorted((ROOT/'data/aoi-typed').glob('p*.json')):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    assert digest.hexdigest()[:16] == source['substrate']['typed_maps_content_hash']
    baseline, folds = evaluate(records, APPROACH_7)
    shipped = source['conditions']['buf500']['M4-7']['pooled_auc']
    gate = {'status': 'ok', 'shipped': shipped, 'reproduced': baseline['pooled_auc'],
            'delta': baseline['pooled_auc']-shipped, 'tolerance': 1e-8,
            'source': '../m4_cursor_aoi_mousedown/summary.json', 'source_path': 'conditions.buf500.M4-7.pooled_auc'}
    assert abs(gate['delta']) <= gate['tolerance']
    print(f'M4 reproduction gate passed: {baseline["pooled_auc"]:.12f}', flush=True)
    raw_hash = check_raw_sources(source)
    tids = list(dict.fromkeys(r['trial_id'] for r in records))
    geometry_digest = hashlib.sha256()
    for tid in tids:
        geometry_digest.update(json.dumps([tid, info[tid]['geometry']], sort_keys=True).encode())
    assert geometry_digest.hexdigest() == source['provenance']['geometry_values_sha256']
    by_trial, anomalies = {}, {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (tid, values, reverse) in enumerate(pool.map(extract, ((tid, info[tid]) for tid in tids)), 1):
            by_trial[tid] = values
            if reverse:
                anomalies[tid] = reverse
            if i % 500 == 0:
                print(f'Extracted {i}/{len(tids)} trials', flush=True)
    for r in records:
        r.update(by_trial[r['trial_id']][r['position']])
    metrics, all_folds = {'M4': baseline}, {'M4': folds}
    for name, features in MODELS.items():
        if name == 'M4':
            continue
        metrics[name], all_folds[name] = evaluate(records, features)
        print(f'{name}: AUC={metrics[name]["pooled_auc"]:.9f}, MRR={metrics[name]["mrr_at_10"]:.6f}', flush=True)
    metrics['AOI dwell direct score'], all_folds['AOI dwell direct score'] = direct_dwell_score(records)
    pairs = [('M4', 'AOI dwell'), ('M4', 'AOI dwell + position'),
             ('AOI dwell + position', 'AOI dwell'), ('M4 + position', 'M4'),
             ('M4', 'log AOI dwell'), ('M4', 'log AOI dwell + position'),
             ('log AOI dwell + position', 'log AOI dwell'), ('M4 + AOI dwell', 'M4'),
             ('M4 replacing proximity dwell', 'M4'), ('M4', 'AOI dwell held to cutoff'),
             ('M4', 'AOI dwell without scroll updates'), ('M4', 'AOI dwell direct score')]
    contrasts = {a+' vs '+b: paired_comparison(all_folds[a], all_folds[b]) for a, b in pairs}
    primary = [a+' vs '+b for a, b in pairs[:4]]
    for key, p in holm({k: contrasts[k]['wilcoxon_two_sided_p'] for k in primary}).items():
        contrasts[key]['holm_p_primary_family_4'] = p
    values = np.array([r[DWELL] for r in records])
    payload = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': 'full_corpus', 'gate': gate,
        'protocol': {'target': 'Final-clicked typed main-axis AOI (one positive per trial)',
                     'rows': len(records), 'trials': len(tids), 'participants': len(folds),
                     'cutoff': 'All input timestamps strictly before final mousedown minus 500 ms',
                     'raw_AOI_dwell': 'Sum of milliseconds of cursor containment in strict XY typed rectangles, no margin or minimum visit duration. Zero-order hold of native mousemove viewport coordinates, updated into document space at scroll events. Observation interval: first through last retained native mousemove, matching M4 temporal extent. No gaze.',
                     'sensitivities': 'log1p(dwell); holding final cursor position through cutoff; no scroll updates between mousemove samples. Log transform is a prespecified sensitivity, not selected by performance.',
                     'estimator': 'Canonical participant LOSO StandardScaler + balanced LogisticRegression(C=1,max_iter=5000); additional unfitted direct-dwell score baseline uses the same rows and participant groups',
                     'uncertainty': 'Paired participant AUC differences, 10000 bootstrap resamples seed 20260904; two-sided Wilcoxon with Holm adjustment across four primary contrasts. Training folds overlap. Other contrasts exploratory.',
                     'primary_contrasts': primary,
                     'limits': 'Estimated from event samples, not directly logged DOM hover duration. Assumes cursor stays at its last viewport location between observations; off-window pointer absence cannot be identified. AOI dwell is distinct from proximity dwell and from gaze fixation duration.'},
        'scroll_timestamp_reversals': anomalies,
        'scroll_alignment_rule': 'Stable timestamp sort for joint mouse/scroll integration; preserve every row. One known backwards scroll timestamp affects p043-b1-t5. No-scroll sensitivity avoids this alignment.',
        'feature_summary': {'nonzero_AOI_rows': int((values>0).sum()), 'zero_AOI_rows': int((values==0).sum()),
                            'quantiles_ms': dict(zip(['min','p25','p50','p75','max'], np.quantile(values,[0,.25,.5,.75,1]).tolist()))},
        'models': metrics, 'fold_aucs': all_folds, 'contrasts': contrasts,
        'provenance': {'source_summary_sha256': sha256(SOURCE), 'canonical_feature_hash': feature_hash,
                       'mouse_and_metadata_sha256': raw_hash, 'geometry_sha256': geometry_digest.hexdigest(),
                       'typed_maps_content_hash': digest.hexdigest()[:16], 'producer_sha256': sha256(__file__),
                       'evaluator_sha256': sha256(ROOT/'scripts/m4_cursor_aoi_rerun.py'),
                       'data_loader_sha256': sha256(ROOT/'notebooks-v2/data_loader.py'),
                       'previous_features_sha256': sha256(PREVIOUS/'features.json')},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'features.json').write_text(json.dumps(records, allow_nan=False))
    payload['provenance']['derived_features_sha256'] = sha256(OUT/'features.json')
    (OUT/'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {OUT}/summary.json', flush=True)


if __name__ == '__main__':
    main()
