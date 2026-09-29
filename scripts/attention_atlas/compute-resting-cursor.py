"""Resting-cursor producer: cursor at rest in one result, fixation in another.

Rest means the cursor endpoint moves below a speed threshold over a complete
100 ms window without a scroll event, while held inside a strict typed AOI
rectangle. The measure is the exact overlap with a recorded fixation in a
different AOI, over several denominators. Before writing, it reproduces the
information-space poster's cursor-AOI and joint totals; a failed gate exits
non-zero.

Two sensitivities relax the primary 2 s cursor hold. The logger records the
cursor only when it moves, so under the primary rule stillness beyond 2 s is
"no cursor coverage" and never counts as rest. `uncapped_hold` holds the last
position until the next mousemove; `uncapped_hold_scroll_shift` also moves the
held page position with scroll.

Writes evidence/resting-cursor/summary.json and trials.json.gz.
Run after compute-information-space.py.
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

OUT = ATLAS / 'evidence/resting-cursor'
SOURCE = ATLAS / 'information-space-poster/summary.json'
DENOMINATORS = ['full_clock_ms', 'cursor_covered_ms', 'cursor_in_aoi_ms', 'cursor_rest_in_aoi_ms',
                'cursor_rest_in_aoi_fixation_matched_ms', 'cursor_rest_both_in_aoi_ms']
SENSITIVITIES = {'uncapped_hold': (None, False), 'uncapped_hold_scroll_shift': (None, True)}
DEFINITION = ('Cursor < threshold screenshot px/s over complete 100 ms windows without scroll events; cursor held within '
              'strict typed AOI xy rectangle; exact overlap with fixation in a different AOI. Cursor and fixation holds use '
              'existing poster conventions; cursor page positions are not reconstructed during scroll. Motion validity does '
              'not require raw gaze endpoints. Full first-mousemove to final-press clock, 2000 ms cursor hold cap. Resting '
              'means low endpoint displacement, not a minimum-length stationary episode.')
SENSITIVITY_DEFINITIONS = {
    'uncapped_hold': 'As primary at 50 px/s, but each cursor position is held until the next mousemove or the press '
                     '(no 2 s cap), so long stillness counts as covered and can count as rest.',
    'uncapped_hold_scroll_shift': 'As uncapped_hold, and the held page position moves with the page scroll offset '
                                  '(a still cursor keeps its screen position while the page scrolls).'}


def partition(tr, hold_ms, shift_with_scroll, thresholds):
    """Rest partition of one trial under one cursor-hold rule, per speed threshold."""
    cs = core.window_speed(core.cursor_endpoints(tr, hold_ms))
    valid = np.isfinite(cs) & ~core.scroll_windows(tr)
    # Exact spatial intervals intersected with complete motion windows.
    edges = core.interval_edges(tr, tr.windows)
    o = core.occupancy(tr, edges, hold_ms, shift_with_scroll)
    dt, mid, cv, gv = o['dt'], o['mid'], o['cv'], o['gv']
    ca, ga = core.aoi(o['cx'], o['cy'], tr.cards), core.aoi(o['gx'], o['gy'], tr.cards)
    cursor = core.durations(np.where(cv, np.where(ca >= 0, 'in_aoi', 'off_aoi'), 'unmatched'), dt)
    joint = core.durations(core.joint_states(ga, ca, gv, cv), dt)
    mv, speed = core.window_lookup(tr, mid, cs, valid)
    out = {}
    for threshold in thresholds:
        rest = cv & (ca >= 0) & mv & (speed < threshold)
        states = np.full(len(mid), 'cursor_rest_aoi_gaze_unmatched', dtype='<U40')
        states[gv & (ga < 0)] = 'cursor_rest_aoi_gaze_off_aoi'
        states[gv & (ga >= 0) & (ga == ca)] = 'same_aoi'
        states[gv & (ga >= 0) & (abs(ga - ca) == 1)] = 'adjacent_aoi'
        states[gv & (ga >= 0) & (abs(ga - ca) > 1)] = 'other_aoi'
        states[~rest] = 'outside_resting_aoi_condition'
        part = core.durations(states, dt)
        vals = {'full_clock_ms': float(dt.sum()), 'cursor_covered_ms': float(dt[cv].sum()),
                'cursor_in_aoi_ms': float(dt[cv & (ca >= 0)].sum()), 'cursor_rest_in_aoi_ms': float(dt[rest].sum()),
                'cursor_rest_in_aoi_fixation_matched_ms': float(dt[rest & gv].sum()),
                'cursor_rest_both_in_aoi_ms': float(dt[rest & gv & (ga >= 0)].sum()),
                'different_aoi_ms': part.get('adjacent_aoi', 0) + part.get('other_aoi', 0),
                'adjacent_aoi_ms': part.get('adjacent_aoi', 0), 'other_aoi_ms': part.get('other_aoi', 0),
                'same_aoi_ms': part.get('same_aoi', 0), 'gaze_off_aoi_ms': part.get('cursor_rest_aoi_gaze_off_aoi', 0),
                'gaze_unmatched_ms': part.get('cursor_rest_aoi_gaze_unmatched', 0),
                'cursor_in_aoi_motion_unclassified_ms': float(dt[cv & (ca >= 0) & ~mv].sum())}
        parts = sum(vals[k] for k in ['same_aoi_ms', 'different_aoi_ms', 'gaze_off_aoi_ms', 'gaze_unmatched_ms'])
        core.gate(abs(vals['cursor_rest_in_aoi_ms'] - parts) < core.CONSERVATION_TOLERANCE_MS,
                  f'{tr.trial_id}: rest partition does not conserve rest time at {threshold} px/s')
        out[str(threshold)] = vals
    return cursor, joint, out


def compute(row):
    tr = core.Trial(row)
    cursor, joint, thresholds = partition(tr, core.CURSOR_HOLD_MS, False, core.REST_THRESHOLDS_PX_S)
    sensitivity = {name: partition(tr, hold, shift, (core.REST_PX_S,))[2][str(core.REST_PX_S)]
                   for name, (hold, shift) in SENSITIVITIES.items()}
    return {'trial_id': tr.trial_id, 'pid': tr.pid, 'cursor_aoi': cursor, 'joint': joint,
            'thresholds': thresholds, 'sensitivity': sensitivity}


def shares(bypid, total, pids, boot):
    out = {}
    for den in DENOMINATORS:
        n = {p: bypid[p]['different_aoi_ms'] for p in pids}
        d = {p: bypid[p][den] for p in pids}
        r = core.ratio_ci(n, d, pids, boot)
        out[den] = {'percent': 100 * total['different_aoi_ms'] / total[den], 'ci95': r['ci95']}
    return out


def main():
    rows = core.load_cohort()
    with ThreadPoolExecutor(max_workers=core.WORKERS) as pool:
        trials = []
        for i, r in enumerate(pool.map(compute, rows)):
            trials.append(r)
            if (i + 1) % 500 == 0:
                print(f'{i + 1}/{len(rows)} trials', flush=True)
    old = core.read_json(SOURCE)
    gates = []
    for lens in ['cursor_aoi', 'joint']:
        totals = Counter()
        for r in trials:
            totals.update(r[lens])
        for state in sorted(set(old['aggregate_ms'][lens]) | set(totals)):
            shipped, got = old['aggregate_ms'][lens].get(state, 0), totals[state]
            delta = got - shipped
            core.gate(abs(delta) < core.GATE_TOLERANCE_MS, f'{lens}.{state}: {got} reproduced vs {shipped} shipped')
            gates.append({'status': 'ok', 'source': core.rel(SOURCE), 'source_path': f'aggregate_ms.{lens}.{state}',
                          'shipped': shipped, 'reproduced': got, 'delta': delta, 'tolerance': core.GATE_TOLERANCE_MS})
    pids = sorted(set(r['pid'] for r in trials))
    boot = core.bootstrap_indices(len(pids), core.SEED_INFORMATION_SPACE)
    results = {}
    for th in [str(t) for t in core.REST_THRESHOLDS_PX_S]:
        bypid, total = defaultdict(Counter), Counter()
        for r in trials:
            total.update(r['thresholds'][th])
            bypid[r['pid']].update(r['thresholds'][th])
        results[th] = {'milliseconds': dict(total), 'different_aoi_share_by_denominator': shares(bypid, total, pids, boot)}
    sensitivity = {}
    for name in SENSITIVITIES:
        bypid, total = defaultdict(Counter), Counter()
        for r in trials:
            total.update(r['sensitivity'][name])
            bypid[r['pid']].update(r['sensitivity'][name])
        sensitivity[name] = {'threshold_px_s': core.REST_PX_S, 'definition': SENSITIVITY_DEFINITIONS[name],
                             'milliseconds': dict(total),
                             'different_aoi_share_by_denominator': shares(bypid, total, pids, boot)}
    summary = {'trials': len(trials), 'participants': len(pids), 'definition': DEFINITION,
               'primary_threshold': core.REST_PX_S, 'gates': gates, 'results': results,
               'sensitivity_cursor_hold': sensitivity,
               'source_hashes': core.source_hashes([Path(__file__), Path(core.__file__), SOURCE,
                                                    ROOT / 'notebooks-v2/data_loader.py', ROOT / 'data/aoi-typed/substrate.json'])}
    OUT.mkdir(parents=True, exist_ok=True)
    core.write_json(OUT / 'summary.json', summary)
    core.write_json_gz(OUT / 'trials.json.gz', trials)
    (OUT / 'trials.json').unlink(missing_ok=True)
    primary = results[str(core.REST_PX_S)]['different_aoi_share_by_denominator']['cursor_rest_in_aoi_ms']
    print(json.dumps({'trials': len(trials), 'participants': len(pids), 'gates_passed': len(gates),
                      'primary_different_aoi_share': primary,
                      'sensitivity': {k: v['different_aoi_share_by_denominator']['cursor_rest_in_aoi_ms']
                                      for k, v in sensitivity.items()}}, indent=2))


if __name__ == '__main__':
    main()
