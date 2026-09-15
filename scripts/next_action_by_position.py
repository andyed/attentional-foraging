#!/usr/bin/env python3
"""Given the first fixation on result position p, what happens next?

Two grains, per typed position (1 = top of page, all element types unless
--organic-only):
  A. next fixation after the first-entry fixation: read on (same result),
     forward 1, forward 2+, back, off the result column, trial ends
  B. end of the first visit (the run of consecutive fixations on p that the
     first entry starts): where the gaze goes next, plus whether p is the
     trial's clicked result and how long the visit lasted
  C. same as B, restricted to the result the trial's fixations START on
Regime [LAB, AdSERP, typed]. Inputs: typed AOI tops via data_loader; clicked
result from the primary census states.csv (was_clicked).
Output: scripts/output/next_action_by_position/summary{_organic}.json
"""
import sys, csv, json, argparse, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl

ap = argparse.ArgumentParser()
ap.add_argument('--organic-only', action='store_true')
ap.add_argument('--max-pos', type=int, default=10)
args = ap.parse_args()
MAXP = args.max_pos

rows = list(csv.DictReader(open(ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv')))
clicked = {}; etype = {}
for r in rows:
    if r['was_clicked'] == '1':
        clicked[r['trial_id']] = int(r['position'])
    etype[(r['trial_id'], int(r['position']))] = r['etype']
tids = sorted({r['trial_id'] for r in rows})

ACTS = ['read on', 'forward 1', 'forward 2+', 'back', 'off results', 'trial ends']


def act(p, q, last):
    if last:
        return 'trial ends'
    if q is None or q < 0:
        return 'off results'
    if q == p:
        return 'read on'
    if q == p + 1:
        return 'forward 1'
    if q > p + 1:
        return 'forward 2+'
    return 'back'


A = defaultdict(Counter); B = defaultdict(Counter); C = defaultdict(Counter)
Bclick = defaultdict(list); Bfix = defaultdict(list); Bms = defaultdict(list); Bback_ret = defaultdict(list)
Cclick = defaultdict(list)
AFTER = defaultdict(Counter)   # back-ended first visits: what the back excursion resolves to
OFF = defaultdict(Counter)     # off-results landings for first visits: where
pids_by_pos = defaultdict(set)
n_trials = 0
for tid in tids:
    try:
        tops = dl.typed_aoi_tops(tid); fx = dl.load_fixations(tid)
    except Exception:
        continue
    if not tops or len(fx) < 2:
        continue
    n_trials += 1
    n = len(tops)
    pos = [dl.assign_fixation_to_position(f['y'], tops, n) for f in fx]
    pos = [p if (p is not None and p >= 0) else None for p in pos]
    if args.organic_only:
        pos = [p if (p is not None and etype.get((tid, p)) == 'organic') else (-1 if p is not None else None) for p in pos]
    pid = tid.split('-')[0]
    seen = set(); first_result = None
    i = 0
    while i < len(fx):
        p = pos[i]
        if p is None or p < 0 or p in seen or p >= MAXP:
            if p is not None and p >= 0:
                seen.add(p)
            i += 1; continue
        seen.add(p)
        if first_result is None:
            first_result = p
        pids_by_pos[p].add(pid)
        # A: next fixation
        q = pos[i + 1] if i + 1 < len(fx) else None
        A[p][act(p, q, i + 1 >= len(fx))] += 1
        # B: end of first visit
        j = i
        while j + 1 < len(fx) and pos[j + 1] == p:
            j += 1
        q = pos[j + 1] if j + 1 < len(fx) else None
        a = act(p, q, j + 1 >= len(fx))
        B[p][a] += 1
        Bfix[p].append(j - i + 1); Bms[p].append(sum((f.get('d') or 0) for f in fx[i:j + 1]))
        Bclick[p].append(int(clicked.get(tid) == p))
        if a == 'back':
            Bback_ret[p].append(int(q in seen))
            # follow the excursion: revisit p, enter a new result (p+1 or other), or the trial ends
            res = 'trial ends'; k = j + 1
            while k < len(fx):
                r = pos[k]
                if r == p:
                    res = 'returns to p'; break
                if r is not None and r >= 0 and r not in seen and r != p:
                    res = 'new: p+1' if r == p + 1 else ('new: beyond p+1' if r > p + 1 else 'new: above p'); break
                k += 1
            AFTER[p][res] += 1
        if a == 'off results':
            y = fx[j + 1]['y']; x = fx[j + 1]['x']
            OFF[p]['above results' if y < tops[0] else ('below results' if y > tops[-1] + 100 else ('right of column' if x > 620 else 'gap/between'))] += 1
        if p == first_result:
            C[p][a] += 1; Cclick[p].append(int(clicked.get(tid) == p))
        i = j + 1

out = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'regime': '[LAB, AdSERP, typed]',
       'organic_only': args.organic_only, 'trials': n_trials, 'acts': ACTS, 'A_next_fixation': {}, 'B_first_visit_end': {}, 'C_trial_start_result': {}}


def table(title, T, extra=None):
    print(f'\n{title}')
    hdr = f"{'pos':>3s} {'n':>6s} {'pids':>4s} " + ' '.join(f'{a:>11s}' for a in ACTS) + (''.join(f'{e:>12s}' for e in extra) if extra else '')
    print(hdr)
    for p in range(MAXP):
        c = T[p]; N = sum(c.values())
        if N < 30:
            continue
        line = f'{p + 1:3d} {N:6d} {len(pids_by_pos[p]):4d} ' + ' '.join(f'{c[a] / N:11.3f}' for a in ACTS)
        if extra:
            line += ''.join(f'{EX[e](p):12.3f}' for e in extra)
        print(line)


EX = {'P(clicked)': lambda p: np.mean(Bclick[p]), 'fix/visit': lambda p: np.median(Bfix[p]), 'ms/visit': lambda p: np.median(Bms[p]),
      'back→seen': lambda p: (np.mean(Bback_ret[p]) if Bback_ret[p] else np.nan), 'P(clicked) ': lambda p: np.mean(Cclick[p])}
table('A. first fixation on p → next fixation (share of first entries)', A)
table('B. first visit to p ends → next fixation; P(clicked) = p is the trial\'s clicked result; visit length (median)', B, ['P(clicked)', 'fix/visit', 'ms/visit', 'back→seen'])
table('C. p is where the trial\'s fixations start → first visit ends with', C, ['P(clicked) '])
for name, T in (('A_next_fixation', A), ('B_first_visit_end', B), ('C_trial_start_result', C)):
    for p in range(MAXP):
        N = sum(T[p].values())
        if N:
            out[name][p + 1] = {'n': N, 'participants': len(pids_by_pos[p]), **{a: T[p][a] / N for a in ACTS}}
for p in range(MAXP):
    if p + 1 in out['B_first_visit_end']:
        out['B_first_visit_end'][p + 1].update({'P_clicked': float(np.mean(Bclick[p])), 'fix_per_visit_median': float(np.median(Bfix[p])),
                                                'ms_per_visit_median': float(np.median(Bms[p])), 'P_back_to_seen': (float(np.mean(Bback_ret[p])) if Bback_ret[p] else None)})
    if p + 1 in out['C_trial_start_result']:
        out['C_trial_start_result'][p + 1]['P_clicked'] = float(np.mean(Cclick[p]))
AACTS = ['returns to p', 'new: p+1', 'new: beyond p+1', 'new: above p', 'trial ends']
print('\nD. first visit to p ended with a back move → the excursion resolves to (share of back-ended visits)')
print(f"{'pos':>3s} {'n':>6s} " + ' '.join(f'{a:>16s}' for a in AACTS))
for p in range(MAXP):
    N = sum(AFTER[p].values())
    if N >= 30:
        print(f'{p + 1:3d} {N:6d} ' + ' '.join(f'{AFTER[p][a] / N:16.3f}' for a in AACTS))
        out.setdefault('D_after_back', {})[p + 1] = {'n': N, **{a: AFTER[p][a] / N for a in AACTS}}
print('\nE. off-results landings after a first visit (share)')
for p in range(MAXP):
    N = sum(OFF[p].values())
    if N >= 30:
        print(f'{p + 1:3d} {N:6d} ' + ', '.join(f'{k} {v / N:.3f}' for k, v in OFF[p].most_common()))
        out.setdefault('E_off_results', {})[p + 1] = {'n': N, **{k: v / N for k, v in OFF[p].items()}}
print(f'\ntrials {n_trials}; trial starts on position: ' + ', '.join(f'{p + 1}: {sum(C[p].values())}' for p in range(MAXP) if sum(C[p].values())))
suffix = '_organic' if args.organic_only else ''
json.dump(out, open(ROOT / f'scripts/output/next_action_by_position/summary{suffix}.json', 'w'), indent=1)
