"""Information-space poster producer: one observation clock, several spatial lenses.

Partitions each trial's clock (first native mousemove to final press) by AOI
membership, initial fold, joint gaze/cursor location and the eventual click
target, with exact interval overlap. Motion uses a separate denominator of
complete 100 ms displacement windows. Before writing anything it checks that
every partition conserves every trial's clock and that the earlier
target-overlap baseline is reproduced; a failed gate exits non-zero.

Writes information-space-poster/summary.json, trials.json.gz, time-budgets.csv.
Run: .venv/bin/python scripts/attention_atlas/compute-information-space.py
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import csv
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

import atlas_core as core
from atlas_core import ATLAS, ROOT

OUT = ATLAS / 'information-space-poster'
PRIOR = ATLAS / 'evidence/final-approach/summary.json'
JOINT = ['same', 'adjacent', 'other', 'gaze_only', 'cursor_only', 'both_off', 'no_fixation', 'no_cursor', 'neither_recorded']
OCCUPANCY_LENSES = ['joint', 'target', 'gaze_aoi', 'cursor_aoi', 'gaze_fold', 'cursor_fold', 'viewport']
# Trials whose raw traces are kept for the poster's close views.
EXAMPLE_TRIALS = ['p047-b6-t1', 'p004-b1-t1', 'p047-b6-t5']
PRIMARY_MOTION = f'{core.GAZE_MOVING_PX_S}|{core.CURSOR_MOVING_PX_S}'


def compute(row):
    tr = core.Trial(row)
    tid, cards, start, end = tr.trial_id, tr.cards, tr.start, tr.end
    onset = float(row['onset_ms'])
    span = end - start
    fold = tr.geo['window_height'] * tr.sy
    dh = tr.geo['doc_height'] * tr.sy
    dw = tr.geo['doc_width'] * tr.sx
    click = max(tr.clicks, key=lambda c: c[0])
    hits = [c for c in cards if core.inside(click[1] * tr.sx, click[2] * tr.sy, c)]
    core.gate(hits, f'{tid}: final click falls outside every mapped AOI')
    target = hits[0]

    edges = core.interval_edges(tr, onset, np.linspace(start, end, core.TIMECOURSE_BINS + 1))
    o = core.occupancy(tr, edges)
    a, b, dt, mid, cv, gv = o['a'], o['b'], o['dt'], o['mid'], o['cv'], o['gv']
    cx, cy, gx, gy = o['cx'], o['cy'], o['gx'], o['gy']
    ca, ga = core.aoi(cx, cy, cards), core.aoi(gx, gy, cards)
    co, go = ca >= 0, ga >= 0
    state = core.joint_states(ga, ca, gv, cv)
    target_g, target_c = core.inside(gx, gy, target), core.inside(cx, cy, target)
    targetstate = np.where(target_g, np.where(target_c, 'both_on', 'gaze_on_cursor_off'),
                           np.where(target_c, 'cursor_on_gaze_off', 'both_off')).astype('<U24')
    targetstate[~gv & cv] = 'no_fixation'
    targetstate[gv & ~cv] = 'no_cursor'
    targetstate[~gv & ~cv] = 'neither_recorded'
    stats = {'joint': core.durations(state, dt), 'target': core.durations(targetstate, dt)}
    for name, v, inside_aoi, x, y in [('gaze', gv, go, gx, gy), ('cursor', cv, co, cx, cy)]:
        k = np.where(v, np.where(inside_aoi, 'in_aoi', 'off_aoi'), 'unmatched')
        stats[name + '_aoi'] = core.durations(k, dt)
        k = np.where(v, np.where((x < 0) | (x > dw) | (y < 0) | (y > dh), 'outside_page',
                                 np.where(y < fold, 'above', 'below')), 'unmatched')
        stats[name + '_fold'] = core.durations(k, dt)
    for phase, sel in [('earlier', mid < onset), ('approach', mid >= onset)]:
        stats['target_' + phase] = core.durations(targetstate[sel], dt[sel])
        stats['joint_' + phase] = core.durations(state[sel], dt[sel])
    # Scroll position, rather than the point's location: has the viewport moved down?
    sc = core.scroll_at(mid, tr.st, tr.sv)
    stats['viewport'] = core.durations(np.where(sc > 1, 'scrolled', 'at_top'), dt)
    # Normalized-time bins retain elapsed milliseconds, so pooling stays time-weighted.
    nbins = core.TIMECOURSE_BINS
    bins = np.minimum(nbins - 1, ((mid - start) / span * nbins).astype(int))
    timecourse = np.zeros((nbins, len(JOINT)))
    for j, k in enumerate(JOINT):
        np.add.at(timecourse[:, j], bins, np.where(state == k, dt, 0))
    # Inputs to the reproduction gate against the earlier exact-overlap results.
    previous = {}
    for phase, sel in [('earlier', mid < onset), ('approach', mid >= onset)]:
        covered = sel & cv
        cs = targetstate[covered].copy()
        cs[cs == 'no_fixation'] = 'unmatched'
        previous[phase] = core.durations(cs, dt[covered])

    # Motion is operational endpoint displacement, NOT a saccade classifier.
    # Gaze endpoints are BPOG medians within +/-20 ms; at least one valid pupil
    # is a quality screen, not a gaze-validity flag. Windows containing a
    # scroll event are unclassified, so scrolling is not called eye or hand motion.
    raw = pd.read_csv(core.data_loader().PUPIL_DIR / (tid + '.csv'))
    rt, rx, ry = raw.timestamp.to_numpy(float), raw.BPOGX.to_numpy(float), raw.BPOGY.to_numpy(float)
    screen_y = ry - core.scroll_at(rt, tr.st, tr.sv)
    good = ((rt >= start) & (rt < end) & np.isfinite(rx) & np.isfinite(ry)
            & ((raw.LPV.to_numpy() == 1) | (raw.RPV.to_numpy() == 1))
            & (rx >= 0) & (rx <= dw) & (screen_y >= 0) & (screen_y <= fold))
    rt, rx, ry = rt[good], rx[good], screen_y[good]
    ii = np.argsort(rt)
    rt, rx, ry = rt[ii], rx[ii], ry[ii]
    me = tr.windows
    nt = len(me) - 1
    gpos = np.full((len(me), 2), np.nan)
    half = core.GAZE_ENDPOINT_HALF_WINDOW_MS
    lo, hi = np.searchsorted(rt, me - half), np.searchsorted(rt, me + half, side='right')
    for j in range(len(me)):
        if hi[j] > lo[j]:
            gpos[j] = [np.median(rx[lo[j]:hi[j]]), np.median(ry[lo[j]:hi[j]])]
    gs = core.window_speed(gpos)
    cs = core.window_speed(core.cursor_endpoints(tr))
    valid = np.isfinite(gs) & np.isfinite(cs) & ~core.scroll_windows(tr)
    motion = {}
    for gt, ct in core.MOTION_THRESHOLDS_PX_S:
        mk = np.where(gs >= gt, np.where(cs >= ct, 'both_move', 'gaze_moves'),
                      np.where(cs >= ct, 'cursor_moves', 'neither_moves')).astype('<U24')
        mk[~valid] = 'unclassified'
        motion[f'{gt}|{ct}'] = core.durations(mk, np.full(nt, float(core.MOTION_WINDOW_MS)))
        if f'{gt}|{ct}' == PRIMARY_MOTION:
            motionkeys = mk
    stats['motion'] = motion[PRIMARY_MOTION]
    trial = {'trial_id': tid, 'pid': tr.pid, 'span_ms': span, 'start_ms': start, 'press_ms': end, 'onset_ms': onset,
             'fold_px': fold, 'target_position': target['position'], 'no_recorded_fixations': tr.no_fixations,
             'stats': stats, 'motion_sensitivity': motion, 'motion_tail_ms': span - nt * core.MOTION_WINDOW_MS,
             'timecourse': timecourse.tolist(), 'previous': previous}
    if tid in EXAMPLE_TRIALS:
        # Exact segments and raw traces for the close views; times relative to first mousemove.
        moves, fix = tr.moves, tr.fix
        trial['example'] = {
            'cards': cards, 'target': target, 'geo': tr.geo,
            'moves': np.column_stack([moves[:, 0] - start, moves[:, 1:]]).tolist(),
            'fixations': np.column_stack([fix[:, 0] - start, fix[:, 1:]]).tolist(),
            'scrolls': [[t - start, y] for t, y in zip(tr.st, tr.sv)],
            'intervals': {'start': (a - start).tolist(), 'end': (b - start).tolist(),
                          'joint': state.tolist(), 'target': targetstate.tolist()},
            'motion': {'start': (me[:-1] - start).tolist(), 'state': motionkeys.tolist(),
                       'gaze_speed': np.where(np.isfinite(gs), gs, -1).tolist(),
                       'cursor_speed': np.where(np.isfinite(cs), cs, -1).tolist()}}
    return trial


def main():
    rows = core.load_cohort()
    trials = []
    with ThreadPoolExecutor(max_workers=core.WORKERS) as pool:
        futures = {pool.submit(compute, row): row['trial_id'] for row in rows}
        for i, f in enumerate(as_completed(futures)):
            try:
                trials.append(f.result())
            except SystemExit:
                raise
            except Exception as e:
                raise RuntimeError(futures[f]) from e
            if (i + 1) % 250 == 0:
                print(f'{i + 1}/{len(rows)} trials', flush=True)
    trials.sort(key=lambda x: x['trial_id'])
    agg, previous, motion = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    participants = defaultdict(lambda: defaultdict(Counter))
    for tr in trials:
        for lens, c in tr['stats'].items():
            agg[lens].update(c)
            participants[tr['pid']][lens].update(c)
        for k, c in tr['previous'].items():
            previous[k].update(c)
        for k, c in tr['motion_sensitivity'].items():
            motion[k].update(c)

    # Conservation: every spatial partition of every trial sums to its clock.
    for tr in trials:
        for k in OCCUPANCY_LENSES:
            core.gate(abs(sum(tr['stats'][k].values()) - tr['span_ms']) < core.CONSERVATION_TOLERANCE_MS,
                      f"{tr['trial_id']}: lens {k} does not conserve the trial clock")
        core.gate(abs(np.array(tr['timecourse']).sum() - tr['span_ms']) < core.CONSERVATION_TOLERANCE_MS,
                  f"{tr['trial_id']}: time course does not conserve the trial clock")
    # Reproduction: the earlier and approach target overlaps of the prior readout.
    prior = core.read_json(PRIOR)
    maxerr = 0
    for phase in ['earlier', 'approach']:
        expected = prior['results'][f'xy|cap2000|full|{phase}']['milliseconds']
        # Both directions: a state the prior never reported must also be zero here.
        for k in set(expected) | set(previous[phase]):
            maxerr = max(maxerr, abs(previous[phase].get(k, 0) - expected.get(k, 0)))
    core.gate(maxerr < core.GATE_TOLERANCE_MS, f'prior target-overlap baseline not reproduced (max error {maxerr} ms)')

    # Participant-cluster percentile CIs for duration-weighted state shares.
    pids = sorted(participants)
    boot = core.bootstrap_indices(len(pids), core.SEED_INFORMATION_SPACE)
    cis = {}
    for lens, c in agg.items():
        den = np.array([sum(participants[p][lens].values()) for p in pids])
        cis[lens] = {}
        for k in c:
            num = np.array([participants[p][lens][k] for p in pids])
            values = 100 * num[boot].sum(1) / den[boot].sum(1)
            cis[lens][k] = np.percentile(values, [2.5, 97.5]).tolist()
    summary = {'trials': len(trials), 'participants': len(pids), 'total_ms': sum(t['span_ms'] for t in trials),
               'aggregate_ms': dict(agg), 'ci95_pct': cis,
               'timecourse_ms': np.array([t['timecourse'] for t in trials]).sum(0).tolist(),
               'joint_state_order': JOINT, 'motion_sensitivity_ms': dict(motion),
               'motion_tail_ms': sum(t['motion_tail_ms'] for t in trials),
               'previous_reproduction_max_error_ms': maxerr,
               'source_hashes': core.source_hashes([Path(__file__), Path(core.__file__), PRIOR,
                                                    ROOT / 'notebooks-v2/data_loader.py', ROOT / 'data/aoi-typed/substrate.json'])}
    OUT.mkdir(parents=True, exist_ok=True)
    core.write_json(OUT / 'summary.json', summary)
    core.write_json_gz(OUT / 'trials.json.gz', trials)
    (OUT / 'trials.json').unlink(missing_ok=True)
    with (OUT / 'time-budgets.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['lens', 'state', 'seconds', 'percent_of_lens_time', 'ci95_low', 'ci95_high'])
        for lens, c in agg.items():
            for k, v in c.items():
                w.writerow([lens, k, v / 1000, 100 * v / sum(c.values()), *cis[lens][k]])
    print(json.dumps({'trials': len(trials), 'participants': len(pids), 'total_ms': summary['total_ms'],
                      'previous_reproduction_max_error_ms': maxerr}, indent=2))


if __name__ == '__main__':
    main()
