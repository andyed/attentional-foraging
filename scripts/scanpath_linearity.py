#!/usr/bin/env python3
"""Scanpath linearity on AdSERP: the three-way classification of Lorigo et al.

Lorigo, Pan, Hembrooke, Joachims, Granka & Gay (2006), "The influence of task
and gender on search and evaluation behavior using Google", Information
Processing & Management 42(4):1123-1131, doi:10.1016/j.ipm.2005.10.001,
classified each scanpath over the ten ranked organic abstracts (their AOIs;
ASL 504 at 60 Hz). Definitions from the paper, section 3, paraphrased:

  * scanpath -- the ordered sequence of abstracts fixated;
  * compressed sequence -- consecutive fixations on one abstract merged;
  * minimal sequence -- the compressed sequence with repeat visits removed,
    i.e. the order of first entries;
  * linear -- the minimal sequence increases in steps of exactly 1;
  * strictly linear -- the compressed sequence increases in steps of exactly 1
    (no skips, no regressions). A one-abstract path is strictly linear by
    default; no path is required to start at rank 1;
  * complete -- the path preceding a selection contains every abstract ranked
    at or above the selected one.

Reported over 600+ Google result pages (clicked or not): 19% strictly linear,
34% linear, 59% with a regression, 50% with a skip, mean path lengths 16 /
5.8 / 3.2 (scanpath / compressed / minimal), mean rank distance 1.67 between
sequential abstracts, and 67% of paths ending in a selection complete.

The linear-but-not-strictly class is reported as `linear_regression`: first
entries advance one rank at a time and at least one earlier result is
revisited. Nonlinear is split by the minimal sequence: `nonlinear_backfill`
when some result is entered for the first time after a lower-ranked one
(the path goes back for a result it passed over), `nonlinear_skip_only` when
first entries only move down but jump more than one rank.

Scanpath construction. Fixations in time order, which end at the final press
in AdSERP. Each fixation is assigned to a ranked result or to nothing; fixations
on nothing are dropped; consecutive fixations on the same result form a visit;
visits shorter than --min-visit-ms of summed fixation duration are dropped and
the neighbours re-merged. The remaining rank sequence is the compressed
scanpath.

Views (all computed in one pass):
  assignment  rect  strict x/y rectangle of the typed AOI (as the atlas posters)
              band  page-y bisection against typed AOI tops (as
                    next_action_by_position.py)
  ranking     organic  rank among organic results only (ads/widgets unranked);
                       closest to Lorigo's ten organic abstracts
              typed    display position of every main-column element
  min visit   0 ms and 100 ms

Gate. Before classifying, the band/typed view recomputes where the first visit
to each typed position 1-10 ends and must reproduce the shipped
scripts/output/next_action_by_position/summary.json (B_first_visit_end) exactly.

Regime [LAB, AdSERP, typed]; rank types `organic` and `typed` are both reported.
Output: scripts/output/scanpath_linearity/summary.json and trials.csv
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv'
NEXT_ACTION = ROOT / 'scripts/output/next_action_by_position/summary.json'
OUT_DIR = ROOT / 'scripts/output/scanpath_linearity'

CLASSES = ['strictly_linear', 'linear_regression', 'nonlinear_backfill', 'nonlinear_skip_only']
MIN_VISITS_MS = (0, 100)
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260929
GATE_TOL = 1e-12
GATE_MAX_POS = 10            # next_action_by_position.py default --max-pos
LENGTH_BINS = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (7, 99)]


# ── Pure functions (unit-tested in test_scanpath_linearity.py) ──────────────

def assign_rect(x, y, cards):
    """Display position of the first card whose rectangle contains (x, y), else None.
    Cards are page-space dicts with position/x/y/width/height, as load_typed_aois."""
    for c in cards:
        if c['x'] <= x <= c['x'] + c['width'] and c['y'] <= y <= c['y'] + c['height']:
            return int(c['position'])
    return None


def compress(labels, durations, min_visit_ms=0):
    """Rank labels per fixation (None = on no ranked result) -> compressed scanpath.

    Drop unlabelled fixations, merge consecutive equal labels into visits with
    summed duration, drop visits shorter than min_visit_ms, re-merge neighbours
    that became adjacent. Returns the list of visit labels."""
    runs = []
    for lab, d in zip(labels, durations):
        if lab is None:
            continue
        if runs and runs[-1][0] == lab:
            runs[-1][1] += d
        else:
            runs.append([lab, d])
    kept = [r[0] for r in runs if r[1] >= min_visit_ms]
    out = []
    for lab in kept:
        if not out or out[-1] != lab:
            out.append(lab)
    return out


def minimal(seq):
    """Lorigo's minimal sequence: the order of first entries."""
    seen, out = set(), []
    for r in seq:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _unit_steps(s):
    return all(b - a == 1 for a, b in zip(s, s[1:]))


def classify(seq):
    """Lorigo et al. (2006) linearity of a compressed scanpath of 1-based ranks,
    with the nonlinear class split by its minimal sequence.

    Returns one of CLASSES, or None for an empty path."""
    if not seq:
        return None
    if _unit_steps(seq):
        return 'strictly_linear'
    m = minimal(seq)
    if _unit_steps(m):
        return 'linear_regression'
    if all(b > a for a, b in zip(m, m[1:])):
        return 'nonlinear_skip_only'
    return 'nonlinear_backfill'


def jumps(seq):
    """Forward skips (b - a > 1) and regressions (a - b) between sequential
    abstracts of a compressed path, as distances in ranks."""
    skips = [b - a for a, b in zip(seq, seq[1:]) if b - a > 1]
    regressions = [a - b for a, b in zip(seq, seq[1:]) if b < a]
    return skips, regressions


def is_complete(seq, clicked_rank):
    """Every rank <= the clicked rank appears in the path (Lorigo's 'complete')."""
    if clicked_rank is None:
        return None
    return all(k in set(seq) for k in range(1, clicked_rank + 1))


def first_visit_end(pos, max_pos=GATE_MAX_POS):
    """Port of next_action_by_position.py section B, used only as the gate.

    pos: per-fixation typed position (0-based) or None. Returns
    {p: Counter(act)} for the end of the first visit to each position < max_pos."""
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
    out = defaultdict(Counter)
    seen = set()
    i, n = 0, len(pos)
    while i < n:
        p = pos[i]
        if p is None or p < 0 or p in seen or p >= max_pos:
            if p is not None and p >= 0:
                seen.add(p)
            i += 1
            continue
        seen.add(p)
        j = i
        while j + 1 < n and pos[j + 1] == p:
            j += 1
        q = pos[j + 1] if j + 1 < n else None
        out[p][act(p, q, j + 1 >= n)] += 1
        i = j + 1
    return out


def cluster_ci(num_by_pid, den_by_pid, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """Ratio of sums with a participant-cluster percentile bootstrap 95% CI."""
    pids = sorted(den_by_pid)
    num = np.array([num_by_pid.get(p, 0) for p in pids], float)
    den = np.array([den_by_pid[p] for p in pids], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pids), size=(draws, len(pids)))
    boot = num[idx].sum(1) / den[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {'value': float(num.sum() / den.sum()), 'ci95': [float(lo), float(hi)],
            'n': int(den.sum()), 'participants': len(pids)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── Per-trial extraction ────────────────────────────────────────────────────

def trial_paths(tid, dl, clicked_pos):
    """All views for one trial. Returns None when the trial has no typed map."""
    cards = sorted([c for c in dl.load_typed_aois(tid)
                    if c.get('position', -1) >= 0
                    and all(c.get(k) is not None and np.isfinite(c[k]) for k in ('x', 'y', 'width', 'height'))],
                   key=lambda c: c['position'])
    tops = dl.typed_aoi_tops(tid)
    fx = sorted(dl.load_fixations(tid), key=lambda f: f['t'])
    if not cards or not tops:
        return None
    etype_by_pos = {int(c['position']): c['type'] for c in cards}
    organic_rank = {}
    for c in cards:
        if c['type'] == 'organic':
            organic_rank[int(c['position'])] = len(organic_rank) + 1
    band = [dl.assign_fixation_to_position(f['y'], tops, len(tops)) for f in fx]
    band = [p if (p is not None and p >= 0) else None for p in band]
    rect = [assign_rect(f['x'], f['y'], cards) for f in fx]
    durs = [f.get('d') or 0.0 for f in fx]
    views, raw_len = {}, {}
    for assign, pos in (('rect', rect), ('band', band)):
        typed = [None if p is None else p + 1 for p in pos]
        org = [None if p is None else organic_rank.get(p) for p in pos]
        for ranking, labels in (('typed', typed), ('organic', org)):
            raw_len[(assign, ranking)] = sum(lab is not None for lab in labels)   # Lorigo's scanpath length
            for mv in MIN_VISITS_MS:
                views[(assign, ranking, mv)] = compress(labels, durs, mv)
    clicked = {'typed': None if clicked_pos is None else clicked_pos + 1,
               'organic': organic_rank.get(clicked_pos)}
    return {'views': views, 'raw_len': raw_len, 'band_pos': band, 'n_fix': len(fx), 'clicked': clicked,
            'clicked_etype': etype_by_pos.get(clicked_pos)}


# ── Main ────────────────────────────────────────────────────────────────────

def gate(ok, msg):
    if not ok:
        raise SystemExit(f'GATE FAILED: {msg}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out-dir', type=Path, default=OUT_DIR)
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / 'notebooks-v2'))
    import data_loader as dl

    rows = list(csv.DictReader(CENSUS.open()))
    clicked_pos = {r['trial_id']: int(r['position']) for r in rows if r['was_clicked'] == '1'}
    tids = sorted({r['trial_id'] for r in rows})

    per_trial, dropped = {}, Counter()
    gate_B = defaultdict(Counter)
    for tid in tids:
        try:
            t = trial_paths(tid, dl, clicked_pos.get(tid))
        except Exception as e:     # a missing file is a cohort exclusion, recorded below
            dropped[f'load_error:{type(e).__name__}'] += 1
            continue
        if t is None:
            dropped['no_typed_map'] += 1
            continue
        if t['n_fix'] < 2:
            dropped['fewer_than_2_fixations'] += 1
            continue
        per_trial[tid] = t
        for p, c in first_visit_end(t['band_pos']).items():
            gate_B[p].update(c)

    # Gate: reproduce the shipped first-visit table before computing anything new.
    shipped = json.loads(NEXT_ACTION.read_text())
    gate(shipped['organic_only'] is False, 'shipped next-action summary is not the all-element run')
    gate(shipped['trials'] == len(per_trial),
         f"cohort {len(per_trial)} trials vs shipped next-action {shipped['trials']}")
    gate_rows = 0
    for p_str, ref in shipped['B_first_visit_end'].items():
        p = int(p_str) - 1
        n = sum(gate_B[p].values())
        gate(n == ref['n'], f'position {p_str}: n {n} vs shipped {ref["n"]}')
        for a in shipped['acts']:
            got = gate_B[p][a] / n
            gate(abs(got - ref[a]) <= GATE_TOL, f'position {p_str} {a}: {got} vs shipped {ref[a]}')
        gate_rows += 1
    gate(gate_rows == GATE_MAX_POS, f'gate compared {gate_rows} positions, expected {GATE_MAX_POS}')

    # Classification per view.
    views_out = {}
    trial_rows = []
    for key in sorted(next(iter(per_trial.values()))['views']):
        assign, ranking, mv = key
        name = f'{assign}_{ranking}_min{mv}ms'
        cls_by_pid = defaultdict(Counter)
        flag_by_pid = defaultdict(Counter)     # has_regression / has_skip / starts_at_1
        n_by_pid = Counter()
        minimal_len, compressed_len, raw_len = [], [], []
        skip_d, regr_d, pair_d = [], [], []
        by_len = defaultdict(Counter)
        complete_by_pid, complete_n_by_pid = Counter(), Counter()
        empty = 0
        for tid, t in per_trial.items():
            seq = t['views'][key]
            c = classify(seq)
            if c is None:
                empty += 1
                continue
            pid = tid.split('-')[0]
            cls_by_pid[pid][c] += 1
            n_by_pid[pid] += 1
            sk, rg = jumps(seq)
            skip_d.extend(sk)
            regr_d.extend(rg)
            pair_d.extend(abs(b - a) for a, b in zip(seq, seq[1:]))
            flag_by_pid[pid]['has_regression'] += int(bool(rg))
            flag_by_pid[pid]['has_skip'] += int(bool(sk))
            flag_by_pid[pid]['starts_at_1'] += int(seq[0] == 1)
            k = len(minimal(seq))
            minimal_len.append(k)
            compressed_len.append(len(seq))
            raw_len.append(t['raw_len'][key[:2]])
            for lo, hi in LENGTH_BINS:
                if lo <= k <= hi:
                    by_len[f'{lo}' if lo == hi else f'{lo}-{hi if hi < 99 else "+"}'][c] += 1
            comp = is_complete(seq, t['clicked'][ranking])
            if comp is not None:
                complete_by_pid[pid] += int(comp)
                complete_n_by_pid[pid] += 1
            if (assign, mv) == ('rect', 0):
                trial_rows.append({'trial_id': tid, 'ranking': ranking, 'class': c,
                                   'minimal_length': k, 'compressed_length': len(seq),
                                   'clicked_rank': t['clicked'][ranking],
                                   'path': ' '.join(map(str, seq))})
        share = lambda cs: cluster_ci({p: sum(v[c] for c in cs) for p, v in cls_by_pid.items()}, n_by_pid)
        shares = {c: share([c]) for c in CLASSES}
        linear = share(['strictly_linear', 'linear_regression'])
        nonlinear = share(['nonlinear_backfill', 'nonlinear_skip_only'])
        pp_nonlinear = [(v['nonlinear_backfill'] + v['nonlinear_skip_only']) / n_by_pid[p] for p, v in cls_by_pid.items()]
        flags = {f: cluster_ci({p: v[f] for p, v in flag_by_pid.items()}, n_by_pid)
                 for f in ('has_regression', 'has_skip', 'starts_at_1')}
        skip_c = Counter(skip_d)
        mean_or_none = lambda xs: float(np.mean(xs)) if xs else None
        views_out[name] = {
            'assignment': assign, 'ranking': ranking, 'min_visit_ms': mv,
            'paths': int(sum(n_by_pid.values())), 'empty_paths': empty,
            'shares': shares,
            'lorigo_three_way': {'strictly_linear': shares['strictly_linear'],
                                 'linear_incl_strict': linear, 'nonlinear': nonlinear},
            'paths_with': flags,
            'per_participant_nonlinear': {'median': float(np.median(pp_nonlinear)),
                                          'iqr': np.percentile(pp_nonlinear, [25, 75]).tolist(),
                                          'participants_majority_nonlinear': int(sum(x > .5 for x in pp_nonlinear)),
                                          'participants': len(pp_nonlinear)},
            'path_length_mean': {'scanpath_fixations': mean_or_none(raw_len),
                                 'compressed': mean_or_none(compressed_len),
                                 'minimal': mean_or_none(minimal_len)},
            'minimal_length_median': float(np.median(minimal_len)),
            'rank_distance_between_sequential_abstracts': {'mean': mean_or_none(pair_d), 'pairs': len(pair_d)},
            'skip_distance': {'events': len(skip_d), 'mean': mean_or_none(skip_d),
                              'share_2_ranks': float(skip_c[2] / max(1, len(skip_d)))},
            'regression_distance': {'events': len(regr_d), 'mean': mean_or_none(regr_d)},
            'by_minimal_length': {b: {'n': int(sum(c.values())), **{k: float(c[k] / sum(c.values())) for k in CLASSES}}
                                  for b, c in by_len.items()},
            'complete_before_click': cluster_ci(complete_by_pid, complete_n_by_pid) if complete_n_by_pid else None,
        }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rel = lambda p: str(Path(p).resolve().relative_to(ROOT))
    summary = {
        'regime': '[LAB, AdSERP, typed]',
        'rank_types': ['organic', 'typed'],
        'method': 'Lorigo et al. 2006 (IP&M 42(4), doi:10.1016/j.ipm.2005.10.001) section 3 scanpath linearity',
        'cohort': {'trials': len(per_trial), 'participants': len({t.split('-')[0] for t in per_trial}),
                   'census_trials': len(tids), 'dropped': dict(dropped)},
        'gate': {'reproduces': rel(NEXT_ACTION), 'table': 'B_first_visit_end', 'positions': gate_rows,
                 'tolerance': GATE_TOL, 'status': 'PASSED'},
        'inputs_sha256': {rel(CENSUS): sha256(CENSUS), rel(NEXT_ACTION): sha256(NEXT_ACTION)},
        'bootstrap': {'unit': 'participant', 'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED, 'statistic': 'ratio of sums'},
        'lorigo_2006_reported': {
            'source': 'Lorigo et al. 2006, section 4.1; 23 subjects, 10 tasks, 600+ Google result pages incl. unclicked',
            'strictly_linear': 0.19, 'linear_incl_strict': 0.34, 'nonlinear': 0.66,
            'paths_with_regression': 0.59, 'paths_with_skip': 0.50,
            'path_length_mean': {'scanpath_fixations': 16, 'compressed': 5.8, 'minimal': 3.2},
            'rank_distance_between_sequential_abstracts_mean': 1.67,
            'complete_before_selection': 0.67},
        'views': views_out,
    }
    (args.out_dir / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    with (args.out_dir / 'trials.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(trial_rows[0]))
        w.writeheader()
        w.writerows(sorted(trial_rows, key=lambda r: (r['ranking'], r['trial_id'])))
    print(f"gate PASSED ({gate_rows} positions); {len(per_trial)} trials")
    for name, v in views_out.items():
        s = v['lorigo_three_way']
        print(f"{name:26s} strict {s['strictly_linear']['value']:.3f}  linear {s['linear_incl_strict']['value']:.3f}  "
              f"nonlinear {s['nonlinear']['value']:.3f}  minimal {v['path_length_mean']['minimal']:.2f}")


if __name__ == '__main__':
    main()
