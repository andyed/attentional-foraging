#!/usr/bin/env python3
"""Cursor marking: prevalence and a test of Rodden et al.'s marking pattern.

Rodden, Fu, Aula & Spiro (2008), "Eye-mouse coordination patterns on web
search results pages", CHI '08 Extended Abstracts, 2997-3002,
doi:10.1145/1358628.1358797, described three active mouse patterns from
manual inspection of 32 participants' eye and mouse paths. In one, the user
leaves the pointer on the most promising result read so far while the eyes go
on checking other results, and moves it when another result looks more
promising. The paper gives no prevalence. This producer measures how often the
pattern occurs and tests the two predictions it makes:

  A. the marked result (under the resting cursor) is the eventual click more
     often than the result the eyes examine most during the same pause;
  B. when the cursor moves from one parked result to another, the later one is
     the eventual click more often than the earlier one.

Substrate. The sequence poster's per-trial data
(docs/visualizations/gaze-cursor-echo/trials.json): cursor pauses are
continuous rest (< 50 screenshot px/s over complete 100 ms windows without
scroll) inside one strict typed AOI rectangle for at least 1 s, with exact
gaze occupancy segments over the same clock (first mousemove to final press).
The clicked result, clock start and final-approach onset come from the
information-space poster's trials.json. Either file may be gzipped.

Definitions.
  marking pause  a pause during which gaze occupies at least one other AOI for
                 >= --min-other-ms (default 100, the poster's minimum visit)
  pre-approach   the pause ends at or before the final-approach onset, so a
                 hover on the target while reaching to click is excluded
  most-gazed other  the AOI other than the cursor's with the most gaze time
                 in the pause (ties: earliest first entry)
  position-matched expectation  P(click at position p) over the cohort,
                 averaged over the pauses' positions; lift = observed / expected

Gate. Summed per-trial rest totals must equal the shipped totals_ms, and the
illustration rule must select the shipped example pause from the shipped
number of qualifying pauses.

Hold sensitivity (--hold-sensitivity; needs the raw AdSERP recordings and
screenshots). The poster holds a mousemove position for at most 2 s, and the
logger records the cursor only when it moves, so a pointer left completely
still for longer drops out of "rest" -- Rodden's prototypical mark. This mode
rebuilds every trial's pauses from the raw recordings through
scripts/attention_atlas/atlas_core.py under three cursor-hold rules: the
primary 2 s cap, no cap (held until the next mousemove), and no cap with the
held page position following page scroll. Gates: the capped rebuild must
reproduce the shipped per-trial pauses, gaze segments and rest totals exactly,
and each uncapped rebuild must reproduce the resting-cursor producer's
sensitivity totals. It then reruns the prevalence and both tests per rule.

Regime [LAB, AdSERP, typed]; rank type typed (all main-column elements).
Output: scripts/output/cursor_marking/summary.json
        scripts/output/cursor_marking/hold_sensitivity.json (--hold-sensitivity)
"""
import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / 'docs/visualizations'
ECHO_TRIALS = ATLAS / 'gaze-cursor-echo/trials.json'
ECHO_SUMMARY = ATLAS / 'gaze-cursor-echo/summary.json'
INFO_TRIALS = ATLAS / 'information-space-poster/trials.json'
OUT_DIR = ROOT / 'scripts/output/cursor_marking'

MIN_OTHER_MS = 100
MIN_OTHER_SENSITIVITY = (0, 100, 300)
LEAD_BINS_S = [(0, 2), (2, 5), (5, 10), (10, None)]   # approach onset minus pause end
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20260929
UNOBSERVED = (-1, -2)                                 # off every AOI, no fixation
REST_SUMMARY = ATLAS / 'evidence/resting-cursor/summary.json'
# name: (hold_ms, held page position follows scroll); keys 2-3 match compute-resting-cursor.py
HOLD_RULES = {'capped_2s': (2000, False), 'uncapped_hold': (None, False), 'uncapped_hold_scroll_shift': (None, True)}
LONG_PAUSE_MS = (2000, 4000, 8000)                    # duration thresholds reported per rule
WORKERS = 8


# ── Pure functions (unit-tested in test_cursor_marking.py) ──────────────────

def load_json(path):
    """Read path, or path + '.gz' when only the compressed copy exists."""
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text())
    gz = path.with_name(path.name + '.gz')
    with gzip.open(gz, 'rt') as f:
        return json.load(f)


def resolve(path):
    path = Path(path)
    return path if path.exists() else path.with_name(path.name + '.gz')


def gaze_by_aoi(segments, a, b):
    """Gaze occupancy (ms) per AOI inside [a, b], and each AOI's first entry time.

    segments: [start, end, aoi] with aoi < 0 meaning off-AOI or unobserved."""
    ms, first = Counter(), {}
    for s, e, k in segments:
        if k in UNOBSERVED or k < 0 or e <= a or s >= b:
            continue
        lo, hi = max(s, a), min(e, b)
        ms[k] += hi - lo
        first.setdefault(k, lo)
    return ms, first


def most_gazed_other(ms, first, cursor_aoi, min_ms):
    """The AOI other than cursor_aoi with the most gaze time >= min_ms, or None."""
    cands = [(k, v) for k, v in ms.items() if k != cursor_aoi and v >= min_ms and v > 0]
    if not cands:
        return None
    return min(cands, key=lambda kv: (-kv[1], first[kv[0]]))[0]


def lead_bin(lead_s):
    for lo, hi in LEAD_BINS_S:
        if lead_s >= lo and (hi is None or lead_s < hi):
            return f'{lo}-{hi}s' if hi is not None else f'>={lo}s'
    return None


def cluster_ci(num_by_pid, den_by_pid, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """Ratio of sums with a participant-cluster percentile bootstrap 95% CI."""
    pids = sorted(p for p in den_by_pid if den_by_pid[p] > 0)
    num = np.array([num_by_pid.get(p, 0) for p in pids], float)
    den = np.array([den_by_pid[p] for p in pids], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pids), size=(draws, len(pids)))
    boot = num[idx].sum(1) / den[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {'value': float(num.sum() / den.sum()), 'ci95': [float(lo), float(hi)],
            'n': float(den.sum()), 'participants': len(pids)}


def illustration_candidates(trials):
    """The sequence poster's selection rule for its example pause."""
    c = [(tr, pa) for tr in trials for pa in tr['pauses']
         if 2000 <= pa['end'] - pa['start'] <= 8000 and pa['distinct'] >= 3
         and pa['returns'] >= 1 and pa['gaze_aoi_coverage'] >= .6]
    c.sort(key=lambda q: (abs((q[1]['end'] - q[1]['start']) - 4000), q[0]['trial_id'], q[1]['start']))
    return c


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate(ok, msg):
    if not ok:
        raise SystemExit(f'GATE FAILED: {msg}')


# ── Analysis ────────────────────────────────────────────────────────────────

def pause_records(echo, info, min_other_ms):
    """One record per cursor pause, with its marking status and outcomes."""
    out = []
    for tr in echo:
        meta = info[tr['trial_id']]
        onset = meta['onset_ms'] - meta['start_ms']
        target = meta['target_position']
        for pa in tr['pauses']:
            a, b, k = pa['start'], pa['end'], pa['cursor_aoi']
            ms, first = gaze_by_aoi(tr['gaze_segments'], a, b)
            other = most_gazed_other(ms, first, k, min_other_ms)
            out.append({
                'trial_id': tr['trial_id'], 'pid': tr['pid'], 'start': a, 'end': b, 'aoi': k,
                'target': target, 'marking': other is not None, 'other': other,
                'others_n': sum(1 for x, v in ms.items() if x != k and v >= max(min_other_ms, 1e-9)),
                'pre_approach': b <= onset, 'lead_s': (onset - b) / 1000,
            })
    return out


def click_rate_by_position(info):
    c = Counter(m['target_position'] for m in info.values())
    n = sum(c.values())
    return {p: v / n for p, v in c.items()}


def marking_tests(recs, p_click):
    """Test A on pre-approach marking pauses."""
    pre = [r for r in recs if r['pre_approach'] and r['marking']]
    num = defaultdict(Counter)
    den = Counter()
    for r in pre:
        num[r['pid']]['marked_hit'] += int(r['aoi'] == r['target'])
        num[r['pid']]['other_hit'] += int(r['other'] == r['target'])
        num[r['pid']]['diff'] += int(r['aoi'] == r['target']) - int(r['other'] == r['target'])
        num[r['pid']]['marked_expected'] += p_click.get(r['aoi'], 0)
        num[r['pid']]['other_expected'] += p_click.get(r['other'], 0)
        den[r['pid']] += 1
    res = {k: cluster_ci({p: v[k] for p, v in num.items()}, den)
           for k in ('marked_hit', 'other_hit', 'diff', 'marked_expected', 'other_expected')}
    res['marked_lift'] = res['marked_hit']['value'] / res['marked_expected']['value']
    res['other_lift'] = res['other_hit']['value'] / res['other_expected']['value']
    by_lead = {}
    for lo, hi in LEAD_BINS_S:
        name = lead_bin(lo)
        sub = [r for r in pre if lead_bin(r['lead_s']) == name]
        if not sub:
            continue
        by_lead[name] = {'pauses': len(sub),
                         'marked_hit': float(np.mean([r['aoi'] == r['target'] for r in sub])),
                         'other_hit': float(np.mean([r['other'] == r['target'] for r in sub])),
                         'marked_expected': float(np.mean([p_click.get(r['aoi'], 0) for r in sub])),
                         'other_expected': float(np.mean([p_click.get(r['other'], 0) for r in sub]))}
    by_pos = {}
    for r in pre:
        key = str(min(r['aoi'], 3)) if r['aoi'] < 3 else '3+'
        by_pos.setdefault(key, []).append(r)
    by_pos = {k: {'pauses': len(v),
                  'marked_hit': float(np.mean([r['aoi'] == r['target'] for r in v])),
                  'other_hit': float(np.mean([r['other'] == r['target'] for r in v])),
                  'click_rate_at_marked_position': float(np.mean([p_click.get(r['aoi'], 0) for r in v]))}
              for k, v in sorted(by_pos.items())}
    return res, by_lead, by_pos


def remark_test(recs):
    """Test B: consecutive pre-approach pauses on different AOIs within a trial."""
    by_trial = defaultdict(list)
    for r in recs:
        if r['pre_approach']:
            by_trial[r['trial_id']].append(r)
    num, den = defaultdict(Counter), Counter()
    for rs in by_trial.values():
        rs.sort(key=lambda r: r['start'])
        for x, y in zip(rs, rs[1:]):
            if x['aoi'] == y['aoi']:
                continue
            num[y['pid']]['later_hit'] += int(y['aoi'] == y['target'])
            num[y['pid']]['earlier_hit'] += int(x['aoi'] == x['target'])
            num[y['pid']]['diff'] += int(y['aoi'] == y['target']) - int(x['aoi'] == x['target'])
            den[y['pid']] += 1
    if not den:
        return None
    return {k: cluster_ci({p: v[k] for p, v in num.items()}, den) for k in ('later_hit', 'earlier_hit', 'diff')}


def prevalence(recs, echo):
    all_by_pid, mark_by_pid = Counter(), Counter()
    t_all, t_mark = Counter(), Counter()
    trials_by_pid, trials_mark_by_pid = Counter(), Counter()
    marked_trials = {r['trial_id'] for r in recs if r['pre_approach'] and r['marking']}
    for tr in echo:
        trials_by_pid[tr['pid']] += 1
        trials_mark_by_pid[tr['pid']] += int(tr['trial_id'] in marked_trials)
    for r in recs:
        if not r['pre_approach']:
            continue
        d = r['end'] - r['start']
        all_by_pid[r['pid']] += 1
        mark_by_pid[r['pid']] += int(r['marking'])
        t_all[r['pid']] += d
        t_mark[r['pid']] += d * r['marking']
    pp = [trials_mark_by_pid[p] / trials_by_pid[p] for p in trials_by_pid]
    others = [r['others_n'] for r in recs if r['pre_approach'] and r['marking']]
    return {
        'pauses_all': len(recs),
        'pauses_pre_approach': int(sum(all_by_pid.values())),
        'marking_share_of_pre_approach_pauses': cluster_ci(mark_by_pid, all_by_pid),
        'marking_share_of_pre_approach_pause_time': cluster_ci(t_mark, t_all),
        'trials_with_marking_pause': cluster_ci(trials_mark_by_pid, trials_by_pid),
        'participants_with_marking_pause': int(sum(v > 0 for v in trials_mark_by_pid.values())),
        'per_participant_trial_share': {'median': float(np.median(pp)),
                                        'iqr': np.percentile(pp, [25, 75]).tolist()},
        'other_aois_per_marking_pause': {'mean': float(np.mean(others)) if others else None,
                                         'share_2_plus': float(np.mean([o >= 2 for o in others])) if others else None},
    }


def pause_durations(echo_like):
    d = [p['end'] - p['start'] for tr in echo_like for p in tr['pauses']]
    return {'pauses': len(d), 'median_ms': float(np.median(d)) if d else None,
            **{f'share_ge_{t // 1000}s': float(np.mean([x >= t for x in d])) if d else None for t in LONG_PAUSE_MS}}


def analyse(echo_like, info, p_click, min_other_ms=MIN_OTHER_MS):
    recs = pause_records(echo_like, info, min_other_ms)
    test_a, by_lead, by_pos = marking_tests(recs, p_click)
    long_marks = [r for r in recs if r['pre_approach'] and r['marking'] and r['end'] - r['start'] >= 4000]
    return {'pauses': pause_durations(echo_like),
            'prevalence': prevalence(recs, echo_like),
            'test_A_marked_vs_most_gazed_other': test_a,
            'test_A_by_lead_time': by_lead,
            'test_A_by_marked_position': by_pos,
            'test_B_later_vs_earlier_mark': remark_test(recs),
            'long_marks_ge_4s': {'pauses': len(long_marks),
                                 'marked_hit': float(np.mean([r['aoi'] == r['target'] for r in long_marks])) if long_marks else None,
                                 'other_hit': float(np.mean([r['other'] == r['target'] for r in long_marks])) if long_marks else None}}


def rebuild_trial(row, core):
    """Pauses, gaze segments and rest totals for one trial under every HOLD_RULES rule."""
    tr = core.Trial(row)
    edges = core.interval_edges(tr, tr.windows)
    click = max(tr.clicks, key=lambda c: c[0])
    hits = [c for c in tr.cards if core.inside(click[1] * tr.sx, click[2] * tr.sy, c)]
    out = {'trial_id': tr.trial_id, 'pid': tr.pid, 'start': float(tr.start),
           'target': int(hits[0]['position']) if hits else None, 'rules': {}}
    for name, (hold, shift) in HOLD_RULES.items():
        cs = core.window_speed(core.cursor_endpoints(tr, hold))
        valid = np.isfinite(cs) & ~core.scroll_windows(tr)
        o = core.occupancy(tr, edges, hold, shift)
        ca, ga = core.aoi(o['cx'], o['cy'], tr.cards), core.aoi(o['gx'], o['gy'], tr.cards)
        ca[~o['cv']] = core.UNOBSERVED
        ga[~o['gv']] = core.UNOBSERVED
        mv, speed = core.window_lookup(tr, o['mid'], cs, valid)
        resting = (ca >= 0) & mv & (speed < core.REST_PX_S)
        pauses = [{'start': a, 'end': b, 'cursor_aoi': k}
                  for a, b, k in core.segments(edges - tr.start, np.where(resting, ca, core.OFF_AOI))
                  if k >= 0 and b - a >= core.PAUSE_MIN_MS]
        if 'gaze_segments' not in out:          # gaze occupancy does not depend on the cursor rule
            out['gaze_segments'] = core.segments(edges - tr.start, ga)
        out['rules'][name] = {'pauses': pauses, 'rest_ms': float(o['dt'][resting].sum()),
                              'different_ms': float(o['dt'][resting & (ga >= 0) & (ga != ca)].sum())}
    return out


def hold_sensitivity(out_dir):
    """Rebuild pauses from raw recordings under each hold rule, gate, and rerun the tests."""
    import sys
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, str(ROOT / 'scripts/attention_atlas'))
    import atlas_core as core

    echo = {t['trial_id']: t for t in load_json(ECHO_TRIALS)}
    info = {t['trial_id']: t for t in load_json(INFO_TRIALS)}
    rest = json.loads(REST_SUMMARY.read_text())
    rows = core.load_cohort()
    gate(len(rows) == len(echo), f'cohort {len(rows)} vs sequence-poster trials {len(echo)}')
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        built = list(pool.map(lambda r: rebuild_trial(r, core), rows))

    # Gate 1: the capped rebuild is the shipped substrate.
    for b in built:
        ref, cap = echo[b['trial_id']], b['rules']['capped_2s']
        gate(b['target'] == info[b['trial_id']]['target_position'], f"{b['trial_id']}: target differs")
        gate(abs(b['start'] - info[b['trial_id']]['start_ms']) < 1e-6, f"{b['trial_id']}: clock start differs")
        gate([(p['start'], p['end'], p['cursor_aoi']) for p in ref['pauses']]
             == [(p['start'], p['end'], p['cursor_aoi']) for p in cap['pauses']], f"{b['trial_id']}: pauses differ")
        gate(ref['gaze_segments'] == b['gaze_segments'], f"{b['trial_id']}: gaze segments differ")
        gate(abs(ref['totals']['cursor_rest_in_aoi_ms'] - cap['rest_ms']) < 1e-6
             and abs(ref['totals']['different_aoi_ms'] - cap['different_ms']) < 1e-6, f"{b['trial_id']}: rest totals differ")
    # Gate 2: each uncapped rebuild reproduces the resting-cursor producer's sensitivity totals.
    for name in ('uncapped_hold', 'uncapped_hold_scroll_shift'):
        shipped = rest['sensitivity_cursor_hold'][name]['milliseconds']
        got_rest = sum(b['rules'][name]['rest_ms'] for b in built)
        got_diff = sum(b['rules'][name]['different_ms'] for b in built)
        gate(abs(got_rest - shipped['cursor_rest_in_aoi_ms']) < 1e-3, f'{name}: rest {got_rest} vs {shipped["cursor_rest_in_aoi_ms"]}')
        gate(abs(got_diff - shipped['different_aoi_ms']) < 1e-3, f'{name}: different {got_diff} vs {shipped["different_aoi_ms"]}')

    p_click = click_rate_by_position(info)
    rules = {}
    for name, (hold, shift) in HOLD_RULES.items():
        echo_like = [{'trial_id': b['trial_id'], 'pid': b['pid'], 'pauses': b['rules'][name]['pauses'],
                      'gaze_segments': b['gaze_segments']} for b in built]
        rules[name] = {'hold_ms': hold, 'shift_with_scroll': shift,
                       'rest_share_different_aoi': sum(b['rules'][name]['different_ms'] for b in built)
                       / sum(b['rules'][name]['rest_ms'] for b in built),
                       **analyse(echo_like, info, p_click)}
    # The capped rule must reproduce the primary summary's headline exactly.
    primary = json.loads((OUT_DIR / 'summary.json').read_text())['views'][f'min_other_{MIN_OTHER_MS}ms']
    gate(rules['capped_2s']['prevalence']['marking_share_of_pre_approach_pauses']
         == primary['prevalence']['marking_share_of_pre_approach_pauses'], 'capped rule does not reproduce the primary summary')

    rel = lambda p: str(Path(p).resolve().relative_to(ROOT))
    out = {'regime': '[LAB, AdSERP, typed]', 'rank_type': 'typed', 'min_other_ms': MIN_OTHER_MS,
           'gates': {'capped_rebuild_matches_shipped_trials': len(built),
                     'uncapped_totals_match_resting_cursor_sensitivity': 2,
                     'capped_reproduces_primary_summary': True, 'status': 'PASSED'},
           'inputs_sha256': {rel(resolve(p)): sha256(resolve(p)) for p in (ECHO_TRIALS, INFO_TRIALS, REST_SUMMARY)},
           'rules': rules}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'hold_sensitivity.json').write_text(json.dumps(out, indent=1) + '\n')
    pct = lambda r: f"{r['value'] * 100:.1f}% [{r['ci95'][0] * 100:.1f}, {r['ci95'][1] * 100:.1f}]"
    print(f'gates PASSED; {len(built)} trials rebuilt')
    for name, v in rules.items():
        pr, a, b = v['prevalence'], v['test_A_marked_vs_most_gazed_other'], v['test_B_later_vs_earlier_mark']
        print(f"{name:28s} pauses {v['pauses']['pauses']:5d} (≥4s {v['pauses']['share_ge_4s'] * 100:4.1f}%) "
              f"marking {pct(pr['marking_share_of_pre_approach_pauses'])} trials {pct(pr['trials_with_marking_pause'])} "
              f"| A marked {pct(a['marked_hit'])} lift {a['marked_lift']:.2f} other {pct(a['other_hit'])} diff {pct(a['diff'])} "
              f"| B diff {pct(b['diff'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out-dir', type=Path, default=OUT_DIR)
    ap.add_argument('--hold-sensitivity', action='store_true',
                    help='rebuild pauses from raw recordings under each cursor-hold rule (needs AdSERP data)')
    args = ap.parse_args()
    if args.hold_sensitivity:
        return hold_sensitivity(args.out_dir)

    echo = load_json(ECHO_TRIALS)
    info = {t['trial_id']: t for t in load_json(INFO_TRIALS)}
    shipped = json.loads(ECHO_SUMMARY.read_text())

    # Gate 1: per-trial rest totals sum to the shipped totals.
    totals = Counter()
    for tr in echo:
        totals.update(tr['totals'])
    for k, v in shipped['totals_ms'].items():
        gate(k in totals and abs(totals[k] - v) <= 1e-6, f'totals_ms.{k}: {totals.get(k)} vs shipped {v}')
    # Gate 2: the illustration rule selects the shipped example from the shipped pool.
    cands = illustration_candidates(echo)
    ex = shipped['example']
    gate(len(cands) == ex['qualifying_pauses'], f'{len(cands)} qualifying pauses vs shipped {ex["qualifying_pauses"]}')
    gate(cands[0][0]['trial_id'] == ex['trial_id'] and cands[0][1] == ex['pause'], 'example pause differs from shipped')
    gate(set(info) >= {t['trial_id'] for t in echo}, 'information-space trials lack some sequence-poster trials')
    gate(all(isinstance(info[t['trial_id']].get('target_position'), int) for t in echo), 'missing target_position')

    p_click = click_rate_by_position(info)
    views = {}
    for mo in MIN_OTHER_SENSITIVITY:
        recs = pause_records(echo, info, mo)
        test_a, by_lead, by_pos = marking_tests(recs, p_click)
        views[f'min_other_{mo}ms'] = {
            'min_other_ms': mo,
            'prevalence': prevalence(recs, echo),
            'test_A_marked_vs_most_gazed_other': test_a,
            'test_A_by_lead_time': by_lead,
            'test_A_by_marked_position': by_pos,
            'test_B_later_vs_earlier_mark': remark_test(recs),
        }
    # Unconditioned reference: all pauses including those inside the final approach.
    recs = pause_records(echo, info, MIN_OTHER_MS)
    in_approach = [r for r in recs if not r['pre_approach']]
    reference = {'pauses_overlapping_final_approach': len(in_approach),
                 'on_target_share': float(np.mean([r['aoi'] == r['target'] for r in in_approach])) if in_approach else None}

    rel = lambda p: str(Path(p).resolve().relative_to(ROOT))
    summary = {
        'regime': '[LAB, AdSERP, typed]', 'rank_type': 'typed',
        'method': 'Rodden et al. 2008 marking pattern (doi:10.1145/1358628.1358797): prevalence and two predictions',
        'cohort': {'trials': len(echo), 'participants': len({t['pid'] for t in echo})},
        'gates': {'totals_ms_reproduced': len(shipped['totals_ms']),
                  'example_pause_reproduced': ex['trial_id'], 'qualifying_pauses': len(cands), 'status': 'PASSED'},
        'inputs_sha256': {rel(resolve(p)): sha256(resolve(p)) for p in (ECHO_TRIALS, ECHO_SUMMARY, INFO_TRIALS)},
        'bootstrap': {'unit': 'participant', 'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED, 'statistic': 'ratio of sums'},
        'click_rate_by_position': {str(k): v for k, v in sorted(p_click.items())},
        'primary': f'min_other_{MIN_OTHER_MS}ms',
        'views': views,
        'reference_final_approach': reference,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')

    v = views[summary['primary']]
    pr, ta, tb = v['prevalence'], v['test_A_marked_vs_most_gazed_other'], v['test_B_later_vs_earlier_mark']
    pct = lambda r: f"{r['value'] * 100:.1f}% [{r['ci95'][0] * 100:.1f}, {r['ci95'][1] * 100:.1f}]"
    print(f"gates PASSED; {len(echo)} trials; {pr['pauses_all']} pauses, {pr['pauses_pre_approach']} pre-approach")
    print('marking share of pre-approach pauses', pct(pr['marking_share_of_pre_approach_pauses']))
    print('trials with a marking pause', pct(pr['trials_with_marking_pause']))
    print('A marked is target', pct(ta['marked_hit']), 'lift', round(ta['marked_lift'], 2),
          '| most-gazed other is target', pct(ta['other_hit']), 'lift', round(ta['other_lift'], 2))
    print('A difference', pct(ta['diff']))
    if tb:
        print('B later mark is target', pct(tb['later_hit']), '| earlier', pct(tb['earlier_hit']), '| diff', pct(tb['diff']))


if __name__ == '__main__':
    main()
