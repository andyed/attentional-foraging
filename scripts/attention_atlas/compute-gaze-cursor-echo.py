"""Gaze/cursor sequence producer: visit timing, rank changes and cursor pauses.

Exploratory and descriptive; it does not infer causal following. Uses the
poster cohort, clock and occupancy rules from atlas_core. Before writing, it
reproduces five resting-cursor totals; a failed gate exits non-zero.

Writes gaze-cursor-echo/summary.json and trials.json.gz.
Run after compute-resting-cursor.py.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

import atlas_core as core
from atlas_core import ATLAS, ROOT

OUT = ATLAS / 'gaze-cursor-echo'
REST_SUMMARY = ATLAS / 'evidence/resting-cursor/summary.json'
# The illustrated pause: 2-8 s, at least three gaze AOIs and one gaze return,
# at least 60% gaze-in-AOI coverage; duration nearest 4 s, then trial ID, then onset.
EXAMPLE_RULE = {'min_ms': 2000, 'max_ms': 8000, 'min_distinct': 3, 'min_returns': 1, 'min_coverage': .6, 'target_ms': 4000}
EXAMPLE_SELECTION = ('Among 2–8 s same-AOI cursor rests with >=3 gaze AOIs, >=1 gaze return, and >=60% gaze-in-AOI '
                     'coverage, choose duration nearest 4 s; tie by trial ID then onset. Illustrative, not representative.')
METHOD = {
    'clock': 'first native mousemove to final press; same 2650-trial poster cohort',
    'aoi': 'strict typed main-column xy rectangles; -1 off AOIs, -2 unobserved',
    'resting': '<50 screenshot px/s over 100 ms endpoint windows, scroll windows excluded, no >=1s requirement for earlier '
               'occupancy fraction; pause illustration >=1s contiguous',
    'visits': 'same-AOI segments bridged across <=100ms gap, never across intervening AOI; >=100ms observed occupancy '
              'primary; 0/200ms sensitivity',
    'first_entry': 'first qualifying gaze and cursor visit to each trial-AOI visited by both; lag = cursor onset minus gaze '
                   'onset; no time-window restriction',
    'matching': 'monotone one-to-one same-AOI visit matching; maximize count within +/-window then minimize total absolute '
                'onset lag; primary +/-2s; 0.5/1/5s sensitivity',
    'sequence': 'AOI transitions/reversals only between qualifying visits separated by <=500ms; separate channel coverage '
                'and sampling remain different',
    'limitations': 'Page-space cursor held up to 2s without scroll reconstruction; gaze fixation intervals exact. First '
                   'entry at observation start may be left-censored. Matching does not establish causal following; '
                   'analyses are exploratory.'}


def compute(row):
    tr = core.Trial(row)
    cards, start = tr.cards, tr.start
    cs = core.window_speed(core.cursor_endpoints(tr))
    valid = np.isfinite(cs) & ~core.scroll_windows(tr)
    edges = core.interval_edges(tr, tr.windows)
    o = core.occupancy(tr, edges)
    dt, mid, cv, gv = o['dt'], o['mid'], o['cv'], o['gv']
    ca, ga = core.aoi(o['cx'], o['cy'], cards), core.aoi(o['gx'], o['gy'], cards)
    ca[~cv] = core.UNOBSERVED
    ga[~gv] = core.UNOBSERVED
    mv, speed = core.window_lookup(tr, mid, cs, valid)
    resting = (ca >= 0) & mv & (speed < core.REST_PX_S)
    gseg, cseg = core.segments(edges - start, ga), core.segments(edges - start, ca)
    click = max(tr.clicks, key=lambda c: c[0])
    hits = [c for c in cards if core.inside(click[1] * tr.sx, click[2] * tr.sy, c)]
    core.gate(hits, f'{tr.trial_id}: final click falls outside every mapped AOI')
    totals = {'cursor_covered_ms': float(dt[cv].sum()), 'cursor_in_aoi_ms': float(dt[ca >= 0].sum()),
              'cursor_rest_in_aoi_ms': float(dt[resting].sum()),
              'different_aoi_ms': float(dt[resting & (ga >= 0) & (ga != ca)].sum()), 'full_clock_ms': float(dt.sum())}
    result = {'trial_id': tr.trial_id, 'pid': tr.pid, 'span_ms': tr.end - start, 'totals': totals,
              'gaze_segments': gseg, 'cursor_segments': cseg, 'sensitivity': {}, 'pauses': [],
              'target': int(hits[0]['position'])}
    for minimum in core.VISIT_MIN_SENSITIVITY_MS:
        g, c = core.visits(gseg, minimum), core.visits(cseg, minimum)
        fg, fc = {}, {}
        for v in g:
            fg.setdefault(v['aoi'], v['start'])
        for v in c:
            fc.setdefault(v['aoi'], v['start'])
        common = sorted(set(fg) & set(fc))
        result['sensitivity'][str(minimum)] = {
            'gaze': core.sequence_stats(g), 'cursor': core.sequence_stats(c),
            'first_lags_ms': [fc[k] - fg[k] for k in common], 'both_visited': len(common),
            'gaze_only_aois': len(set(fg) - set(fc)), 'cursor_only_aois': len(set(fc) - set(fg))}
        if minimum == core.VISIT_MIN_MS:
            result['gaze_visits'], result['cursor_visits'] = g, c
            result['first_arrivals'] = [{'aoi': k, 'gaze_ms': fg[k], 'cursor_ms': fc[k], 'lag_ms': fc[k] - fg[k]} for k in common]
            result['matches'] = {str(w): core.match(g, c, w) for w in core.MATCH_WINDOWS_MS}
    # Continuous low-motion intervals inside one cursor AOI; gaps split pauses.
    for a, b, k in core.segments(edges - start, np.where(resting, ca, core.OFF_AOI)):
        if k < 0 or b - a < core.PAUSE_MIN_MS:
            continue
        overlap = [{'start': max(a, x), 'end': min(b, y), 'aoi': z} for x, y, z in gseg if z >= 0 and x < b and y > a]
        seq = []
        for v in overlap:
            if not seq or seq[-1] != v['aoi']:
                seq.append(v['aoi'])
        matched = sum(v['end'] - v['start'] for v in overlap)
        different = sum(v['end'] - v['start'] for v in overlap if v['aoi'] != k)
        result['pauses'].append({'start': a, 'end': b, 'cursor_aoi': k, 'gaze_sequence': seq, 'distinct': len(set(seq)),
                                 'gaze_aoi_coverage': matched / (b - a), 'different_ms': different,
                                 'returns': len(seq) - len(set(seq))})
    return result


def example_candidates(trials):
    r = EXAMPLE_RULE
    out = [(tr, pa) for tr in trials for pa in tr['pauses']
           if r['min_ms'] <= pa['end'] - pa['start'] <= r['max_ms'] and pa['distinct'] >= r['min_distinct']
           and pa['returns'] >= r['min_returns'] and pa['gaze_aoi_coverage'] >= r['min_coverage']]
    out.sort(key=lambda q: (abs((q[1]['end'] - q[1]['start']) - r['target_ms']), q[0]['trial_id'], q[1]['start']))
    return out


def main():
    rows = core.load_cohort()
    trials = []
    with ThreadPoolExecutor(max_workers=core.WORKERS) as pool:
        for i, r in enumerate(pool.map(compute, rows)):
            trials.append(r)
            if (i + 1) % 500 == 0:
                print(f'{i + 1}/{len(rows)} trials', flush=True)
    old = core.read_json(REST_SUMMARY)
    agg = Counter()
    for tr in trials:
        agg.update(tr['totals'])
    gates = []
    for k, v in agg.items():
        expected = old['results'][str(core.REST_PX_S)]['milliseconds'][k]
        core.gate(abs(v - expected) < core.GATE_TOLERANCE_MS, f'{k}: {v} reproduced vs {expected} in the rest summary')
        gates.append({'status': 'ok', 'source': core.rel(REST_SUMMARY), 'source_path': f'results.50.milliseconds.{k}',
                      'shipped': expected, 'reproduced': v, 'delta': v - expected, 'tolerance': core.GATE_TOLERANCE_MS})
    core.gate(len(gates) == 5, f'expected 5 rest-to-sequence gates, found {len(gates)}')
    pids = sorted(set(t['pid'] for t in trials))
    boot = core.bootstrap_indices(len(pids), core.SEED_SEQUENCES)
    summary = {'trials': len(trials), 'participants': len(pids), 'gates': gates, 'totals_ms': dict(agg),
               'visit_sensitivity': {}, 'matching_sensitivity': {}}
    for minimum in [str(m) for m in core.VISIT_MIN_SENSITIVITY_MS]:
        lag, tot, gfirst, both, sequences = [], Counter(), Counter(), Counter(), defaultdict(list)
        for tr in trials:
            s = tr['sensitivity'][minimum]
            lag.extend(s['first_lags_ms'])
            gfirst[tr['pid']] += sum(x > 0 for x in s['first_lags_ms'])
            both[tr['pid']] += s['both_visited']
            for k in ['both_visited', 'gaze_only_aois', 'cursor_only_aois']:
                tot[k] += s[k]
            for ch in ['gaze', 'cursor']:
                for k, v in s[ch].items():
                    tot[ch + '_' + k] += v
                    sequences[ch + '_' + k].append(v)
        summary['visit_sensitivity'][minimum] = {
            'totals': dict(tot), 'first_entry_lag_median_ms': float(np.median(lag)),
            'first_entry_lag_iqr_ms': np.percentile(lag, [25, 75]).tolist(),
            'gaze_first_share': core.ratio_ci(gfirst, both, pids, boot),
            'trial_medians': {k: float(np.median(v)) for k, v in sequences.items()},
            'equal_first_entries': sum(x == 0 for x in lag)}
    for w in [str(w) for w in core.MATCH_WINDOWS_MS]:
        lag, n, d, cseen, gseen, returnlags = [], Counter(), Counter(), 0, 0, []
        for tr in trials:
            pp = tr['matches'][w]
            lag.extend(z[2] for z in pp)
            n[tr['pid']] += sum(z[2] > 0 for z in pp)
            d[tr['pid']] += len(pp)
            cseen += len(tr['cursor_visits'])
            gseen += len(tr['gaze_visits'])
            for gi, ci, delta in pp:
                k = tr['gaze_visits'][gi]['aoi']
                if any(v['aoi'] == k for v in tr['gaze_visits'][:gi]) and any(v['aoi'] == k for v in tr['cursor_visits'][:ci]):
                    returnlags.append(delta)
        summary['matching_sensitivity'][w] = {
            'matched_pairs': len(lag), 'gaze_visits': gseen, 'cursor_visits': cseen,
            'gaze_unmatched_visits': gseen - len(lag), 'cursor_unmatched_visits': cseen - len(lag),
            'lag_median_ms': float(np.median(lag)), 'lag_iqr_ms': np.percentile(lag, [25, 75]).tolist(),
            'gaze_first_share': core.ratio_ci(n, d, pids, boot), 'both_return_pairs': len(returnlags),
            'both_return_lag_median_ms': float(np.median(returnlags)) if returnlags else None,
            'both_return_gaze_first_pct': 100 * sum(x > 0 for x in returnlags) / len(returnlags) if returnlags else None}
    candidates = example_candidates(trials)
    core.gate(candidates, 'no pause satisfies the illustration rule; revise EXAMPLE_RULE explicitly')
    tr, pa = candidates[0]
    summary['example'] = {'trial_id': tr['trial_id'], 'pause': pa, 'qualifying_pauses': len(candidates),
                          'selection': EXAMPLE_SELECTION}
    summary['method'] = METHOD
    summary['source_hashes'] = core.source_hashes([Path(__file__), Path(core.__file__), REST_SUMMARY,
                                                   ROOT / 'notebooks-v2/data_loader.py', ROOT / 'data/aoi-typed/substrate.json'])
    OUT.mkdir(parents=True, exist_ok=True)
    core.write_json(OUT / 'summary.json', summary)
    core.write_json_gz(OUT / 'trials.json.gz', trials)
    (OUT / 'trials.json').unlink(missing_ok=True)
    print(json.dumps({'trials': len(trials), 'participants': len(pids), 'gates_passed': len(gates),
                      'example': summary['example']['trial_id'], 'qualifying_pauses': len(candidates)}, indent=2))


if __name__ == '__main__':
    main()
