#!/usr/bin/env python3
"""C/W/L's two derived terms, measured directly -- W(i) and L(i) against the
single-descent shortcut that derives them from C(i).

The C/W/L framework describes a searcher by a continuation function C(i)
and derives the attention weight W(i) and the stopping distribution L(i)
from it under a single forward pass:

    W(i) ∝ ∏_{j<i} C(j)          (each viewed item gets one unit of attention)
    L(i)  = W-mass that stops at i = P(reach i) − P(reach i+1)

Both derived quantities can be measured on AdSERP without the shortcut:
attention as fixation time per rank, stopping as the clicked rank (forced
choice makes the stop observable). This producer reports the derived and the
measured versions side by side and sizes the gap. It does not revise the
framework; it instruments its two derived terms.

Regime [LAB, AdSERP, typed]. Positions 0..MAXP-1 on the typed map; the
known-opportunity trial set of engagement_continuation.py so every curve
shares the continuation producer's denominator.

Gate (both must hold before anything is emitted):
  G1  the first-pass reach R_fp(i) recomputed here equals the shipped
      continuation['reach']['fixation_first_pass'] of the consumed
      continuation summary to 1e-9 at every position;
  G2  per-slot gaze dwell summed from fixations under the label producer's
      assignment rule equals states.csv total_dwell_ms (max abs diff < 1 ms)
      on every slot, so the visit walk below is on the label's own map.

(1) W four ways, positions 0..MAXP-1, normalised to sum to 1:
      derived_first_pass   R_fp(i) / Σ_k R_fp(k)      the C/W/L shortcut on the strict order
      derived_any_time     R_any(i) / Σ_k R_any(k)    the shortcut on any-time reach
      measured_first_visit share of first-visit fixation time at rank i
      measured_any_time    share of all fixation time at rank i
    measured_any_time − measured_first_visit is the attention returns add;
    measured_first_visit − derived_first_pass is dwell heterogeneity across
    ranks (the shortcut gives every viewed item one unit). Gaps are total
    variation distance with a participant-cluster bootstrap CI.
(2) L two ways on trials whose click lands on a typed slot, ranks bucketed
    at "MAXP-1 or deeper" for both:
      derived_first_pass   P(deepest first-pass rank = i)   the single-descent stop, per trial
                           (R_fp(i) − R_fp(i+1) kept as a secondary field; it mixes page lengths)
      measured_click       P(clicked rank = i)
    plus the per-trial gap between the deepest rank fixated and the clicked
    rank: share of trials where the click is above the deepest rank examined,
    the distribution of that gap in ranks, and the per-participant share.

Output: scripts/output/cwl_derived_vs_measured/<variant>/summary.json
Run:    .venv/bin/python scripts/cwl_derived_vs_measured.py
        (defaults to the gate_200px primary census / continuation variant)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl  # noqa: E402

MAXP = 10
CENSUS_ROOT = ROOT / 'scripts/output/engagement_state_census'
CONT_ROOT = ROOT / 'scripts/output/engagement_continuation'
OUT_ROOT = ROOT / 'scripts/output/cwl_derived_vs_measured'


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tvd(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(0.5 * np.abs(a - b).sum())


def normalise(v):
    v = np.asarray(v, float)
    s = v.sum()
    return (v / s).tolist() if s > 0 else [None] * len(v)


def walk_trial(tid, tops, cutoff_t=None):
    """Per-position first-entry time, first-visit dwell, total dwell, using the
    label producer's assignment rule. A visit is a run of consecutive fixations
    assigned to the same position; the first visit is the run the first entry
    starts. cutoff_t drops fixations starting at or after it (press truncation)."""
    fixs = dl.load_fixations(tid)
    if cutoff_t is not None:
        fixs = [f for f in fixs if float(f['t']) < cutoff_t]
    n = len(tops)
    first_t, first_dwell, total = {}, defaultdict(float), defaultdict(float)
    prev = None
    in_first = {}
    for f in fixs:
        q = dl.assign_fixation_to_position(f['y'], tops, n)
        if q is None or q < 0:
            prev = q
            continue
        total[q] += float(f['d'])
        if q not in first_t:
            first_t[q] = float(f['t'])
            in_first[q] = True
            first_dwell[q] += float(f['d'])
        elif in_first.get(q) and prev == q:
            first_dwell[q] += float(f['d'])
        else:
            in_first[q] = False
        prev = q
    return first_t, first_dwell, total, n


def first_pass_flags(first_t, n):
    deeper_min, cur = {}, float('inf')
    for q in range(n - 1, -1, -1):
        deeper_min[q] = cur
        if q in first_t:
            cur = min(cur, first_t[q])
    return {q: (q in first_t and first_t[q] <= deeper_min[q]) for q in range(n)}


def cluster_boot(per_pid_stats, fn, n=3000, seed=20260915):
    """per_pid_stats: dict pid -> object; fn: list of objects -> scalar."""
    rng = np.random.default_rng(seed)
    pids = list(per_pid_stats)
    out = []
    for _ in range(n):
        pick = rng.integers(0, len(pids), len(pids))
        out.append(fn([per_pid_stats[pids[k]] for k in pick]))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='gate_200px',
                    help='census / continuation sub-directory (default: the primary)')
    ap.add_argument('--truncate-at-press', action='store_true',
                    help='robustness: drop fixations at or after the last mousedown; the gates '
                         'are still asserted on the untruncated walk, results go to <variant>_press_truncated/')
    args = ap.parse_args()
    census_dir = CENSUS_ROOT / args.variant
    cont_dir = CONT_ROOT / args.variant
    out_dir = OUT_ROOT / (args.variant + ('_press_truncated' if args.truncate_at_press else ''))
    states_csv = census_dir / 'states.csv'
    cont_json = cont_dir / 'summary.json'
    if not states_csv.exists():
        states_csv = CENSUS_ROOT / 'states.csv'
    rows = list(csv.DictReader(open(states_csv)))
    cont = json.loads(cont_json.read_text())
    shipped_fp = cont['continuation']['reach']['fixation_first_pass']

    by = defaultdict(dict)
    for r in rows:
        r['position'] = int(r['position'])
        r['fixated'] = r['fixated'] == '1'
        r['was_clicked'] = r['was_clicked'] == '1'
        r['total_dwell_ms'] = float(r['total_dwell_ms'])
        by[r['trial_id']][r['position']] = r
    known = sorted(t for t, d in by.items()
                   if all(x['state'] != 'unknown_opportunity' for x in d.values()))

    # ---- walk every known trial once ---------------------------------------
    fp_reach = np.zeros(MAXP); fp_tot = np.zeros(MAXP)
    any_reach = np.zeros(MAXP); any_tot = np.zeros(MAXP)
    W_first = np.zeros(MAXP); W_any = np.zeros(MAXP)
    per_pid = defaultdict(lambda: {'first': np.zeros(MAXP), 'any': np.zeros(MAXP),
                                   'fp_reach': np.zeros(MAXP), 'fp_tot': np.zeros(MAXP),
                                   'stop_click': np.zeros(MAXP), 'n_click': 0,
                                   'click_above_deepest': 0, 'deepest_gap': []})
    n_walked = 0
    g1_reach = np.zeros(MAXP); g1_tot = np.zeros(MAXP)
    n_no_press = 0; n_fix_dropped = 0
    max_dwell_diff = 0.0
    n_dwell_checked = 0
    L_trials = []   # (pid, clicked_pos, deepest_fixated, deepest_first_pass, deepest_viewport)
    for t in known:
        d = by[t]
        pid = d[next(iter(d))]['pid']
        try:
            tops = dl.typed_aoi_tops(t)
        except Exception:
            continue
        if not tops:
            continue
        first_t, first_dwell, total, n = walk_trial(t, tops)
        if not first_t:
            continue
        n_walked += 1
        # G2: the walk reproduces the census's per-slot dwell
        for p, r in d.items():
            if p < n:
                diff = abs(total.get(p, 0.0) - r['total_dwell_ms'])
                max_dwell_diff = max(max_dwell_diff, diff)
                n_dwell_checked += 1
        fp_untrunc = first_pass_flags(first_t, n)
        for i in range(min(MAXP, n)):
            g1_tot[i] += 1; g1_reach[i] += fp_untrunc[i]
        if args.truncate_at_press:
            try:
                ev, _, _ = dl.load_mouse_events(t)
                md = [float(e[0]) for e in ev if e[1] == 'mousedown']
            except Exception:
                md = []
            if not md:
                n_no_press += 1
                continue
            n_fix_dropped += sum(1 for f in dl.load_fixations(t) if float(f['t']) >= md[-1])
            first_t, first_dwell, total, n = walk_trial(t, tops, cutoff_t=md[-1])
            if not first_t:
                continue
        fp = first_pass_flags(first_t, n)
        for i in range(min(MAXP, n)):
            fp_tot[i] += 1; fp_reach[i] += fp[i]
            per_pid[pid]['fp_tot'][i] += 1; per_pid[pid]['fp_reach'][i] += fp[i]
            any_tot[i] += 1; any_reach[i] += ((i in total) if args.truncate_at_press else (i in d and d[i]['fixated']))
            W_first[i] += first_dwell.get(i, 0.0); W_any[i] += total.get(i, 0.0)
            per_pid[pid]['first'][i] += first_dwell.get(i, 0.0)
            per_pid[pid]['any'][i] += total.get(i, 0.0)
        # stopping: clicked typed slot, if any and within range
        # stopping: the clicked typed slot. Ranks are bucketed at MAXP-1 ("9 or
        # deeper") for BOTH distributions so the derived L's tail is not an
        # artefact of truncation; deepest-rank comparisons use the full page.
        clicked = [p for p, r in d.items() if r['was_clicked']]
        if len(clicked) == 1:
            c = clicked[0]
            fixated = [p for p in total] if args.truncate_at_press else [p for p, r in d.items() if r['fixated']]
            onscreen = [p for p, r in d.items() if r['state'] != 'never_onscreen']
            if fixated:
                deepest = max(fixated)
                deepest_fp = max(q for q in range(n) if fp[q]) if any(fp.values()) else deepest
                deepest_vp = max(onscreen) if onscreen else deepest
                L_trials.append((pid, c, deepest, deepest_fp, deepest_vp))
                per_pid[pid]['stop_click'][min(c, MAXP - 1)] += 1
                per_pid[pid]['n_click'] += 1
                per_pid[pid]['click_above_deepest'] += int(c < deepest)
                per_pid[pid]['deepest_gap'].append(deepest - c)

    # ---- gates ---------------------------------------------------------------
    R_fp = (fp_reach / fp_tot).tolist()
    g1 = max(abs(a - b) for a, b in zip((g1_reach / g1_tot).tolist(), shipped_fp))
    assert g1 < 1e-9, f'G1 failed: first-pass reach differs from shipped by {g1}'
    assert max_dwell_diff < 1.0, f'G2 failed: per-slot dwell differs from census by {max_dwell_diff} ms'
    R_any = (any_reach / any_tot).tolist()

    # ---- (1) W four ways ---------------------------------------------------
    W = {'derived_first_pass': normalise(R_fp),
         'derived_any_time': normalise(R_any),
         'measured_first_visit': normalise(W_first),
         'measured_any_time': normalise(W_any)}
    share_return_time = float(1.0 - W_first.sum() / W_any.sum())

    def pid_tvd(key_a, key_b):
        def fn(objs):
            A = np.sum([o[key_a] for o in objs], axis=0); B = np.sum([o[key_b] for o in objs], axis=0)
            A = A / A.sum(); B = B / B.sum()
            return tvd(A, B)
        return fn

    def pid_tvd_derived_vs(key_meas):
        def fn(objs):
            reach = np.sum([o['fp_reach'] for o in objs], axis=0) / np.sum([o['fp_tot'] for o in objs], axis=0)
            A = reach / reach.sum()
            B = np.sum([o[key_meas] for o in objs], axis=0); B = B / B.sum()
            return tvd(A, B)
        return fn
    gaps = {
        'derived_fp_vs_measured_any': {'tvd': tvd(W['derived_first_pass'], W['measured_any_time']),
                                       'ci': cluster_boot(per_pid, pid_tvd_derived_vs('any'))},
        'derived_fp_vs_measured_first_visit': {'tvd': tvd(W['derived_first_pass'], W['measured_first_visit']),
                                               'ci': cluster_boot(per_pid, pid_tvd_derived_vs('first'))},
        'measured_first_visit_vs_measured_any': {'tvd': tvd(W['measured_first_visit'], W['measured_any_time']),
                                                 'ci': cluster_boot(per_pid, pid_tvd('first', 'any'))},
        'derived_fp_vs_derived_any': {'tvd': tvd(W['derived_first_pass'], W['derived_any_time'])},
    }
    W_by_rank_diff = {'measured_any_minus_derived_fp': (np.array(W['measured_any_time']) - np.array(W['derived_first_pass'])).tolist(),
                      'measured_any_minus_measured_first_visit': (np.array(W['measured_any_time']) - np.array(W['measured_first_visit'])).tolist()}
    expected_rank = {k: float(np.dot(np.arange(MAXP), v)) for k, v in W.items()}

    # ---- (2) L two ways -----------------------------------------------------
    # derived (primary): the single-descent stop IS the deepest first-pass rank,
    # taken per trial on the same clicked trials and bucketed at "9 or deeper".
    # The reach-difference form R_fp(i) − R_fp(i+1) is kept as a secondary
    # field; it mixes denominators because pages differ in typed slot count.
    stop_counts = np.zeros(MAXP)
    for _, _, _, dfp, _ in L_trials:
        stop_counts[min(dfp, MAXP - 1)] += 1
    L_derived_n = normalise(stop_counts)
    L_derived_reach_diff = normalise([R_fp[i] - R_fp[i + 1] for i in range(MAXP - 1)] + [R_fp[MAXP - 1]])
    click_counts = np.zeros(MAXP)
    for _, c, *_ in L_trials:
        click_counts[min(c, MAXP - 1)] += 1
    L_click = normalise(click_counts)
    n_L = len(L_trials)
    above = sum(1 for _, c, dp, *_ in L_trials if c < dp)
    above_fp = sum(1 for _, c, _, dfp, _ in L_trials if c < dfp)
    above_vp = sum(1 for _, c, _, _, dvp in L_trials if c < dvp)
    gap = np.array([dp - c for _, c, dp, *_ in L_trials])
    pid_share = {p: o['click_above_deepest'] / o['n_click'] for p, o in per_pid.items() if o['n_click'] >= 5}
    pid_vals = np.array(list(pid_share.values()))

    def fn_above(objs):
        num = sum(o['click_above_deepest'] for o in objs); den = sum(o['n_click'] for o in objs)
        return num / den if den else np.nan
    L = {'n_trials': n_L,
         'L_derived_first_pass': L_derived_n,
         'L_derived_first_pass_reach_difference_secondary': L_derived_reach_diff,
         'L_measured_click': L_click,
         'tvd': tvd(L_derived_n, L_click),
         'expected_stop_rank_derived': float(np.dot(np.arange(MAXP), L_derived_n)),
         'expected_stop_rank_click': float(np.dot(np.arange(MAXP), L_click)),
         'click_above_deepest_fixated': {'share': above / n_L, 'ci': cluster_boot(per_pid, fn_above),
                                         'n': above},
         'click_above_deepest_first_pass': {'share': above_fp / n_L, 'n': above_fp},
         'click_above_deepest_viewport': {'share': above_vp / n_L, 'n': above_vp},
         'gap_ranks_deepest_minus_click': {'mean': float(gap.mean()), 'median': float(np.median(gap)),
                                           'histogram': {str(k): int((gap == k).sum()) for k in range(0, int(gap.max()) + 1)}},
         'per_participant_share_click_above_deepest': {'n_participants': len(pid_vals),
                                                       'median': float(np.median(pid_vals)),
                                                       'iqr': [float(np.percentile(pid_vals, 25)), float(np.percentile(pid_vals, 75))],
                                                       'min': float(pid_vals.min()), 'max': float(pid_vals.max())}}

    # ---- (3) consistency: does one C generate both measured terms? ---------
    # Under C/W/L, W(i+1)/W(i) = C(i) and L(i) = W(i) - W(i+1) (last bucket W(9)).
    # Read C and L off the MEASURED any-time W and compare with the first-pass
    # C and the clicked L. Also fit RBP (W ∝ p^i) to each W by least squares
    # on log W over ranks 0..9.
    Wm = np.array(W['measured_any_time']); Wd = np.array(W['derived_first_pass'])
    C_fp = [R_fp[i + 1] / R_fp[i] for i in range(MAXP - 1)]           # reach ratio (unconditional first pass)
    C_from_Wm = [float(Wm[i + 1] / Wm[i]) for i in range(MAXP - 1)]
    L_from_Wm = normalise([Wm[i] - Wm[i + 1] for i in range(MAXP - 1)] + [Wm[MAXP - 1]])
    def rbp_fit(w):
        i = np.arange(MAXP); lw = np.log(np.asarray(w, float))
        slope = np.polyfit(i, lw, 1)[0]
        p_ = float(np.exp(slope)); pred = normalise(p_ ** i)
        return {'p': p_, 'tvd_to_W': tvd(w, pred)}
    consistency = {
        'C_first_pass_reach_ratio': C_fp,
        'C_implied_by_measured_W': C_from_Wm,
        'C_shipped_conditional_first_pass': cont['continuation']['continuation']['fixation_first_pass'],
        'L_implied_by_measured_W': L_from_Wm,
        'L_measured_click': L_click,
        'tvd_L_impliedW_vs_click': tvd(L_from_Wm, L_click),
        'expected_stop_L_impliedW': float(np.dot(np.arange(MAXP), L_from_Wm)),
        'rbp_fit_measured_W': rbp_fit(Wm), 'rbp_fit_derived_W': rbp_fit(Wd),
        'note': 'no single C reproduces both measured terms: the C implied by measured attention and the L it '
                'implies are compared with first-pass C and clicked L; RBP fit is least squares on log W, ranks 0..9'}

    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]', 'variant': args.variant, 'maxp': MAXP,
           'inputs': {'states_csv': str(states_csv.relative_to(ROOT)), 'states_csv_sha256': sha256(states_csv),
                      'continuation_summary': str(cont_json.relative_to(ROOT)), 'continuation_sha256': sha256(cont_json),
                      'continuation_generated_utc': cont['generated_utc']},
           'gate': {'G1_first_pass_reach_max_abs_diff': g1,
                    'G2_per_slot_dwell_max_abs_diff_ms': max_dwell_diff, 'G2_slots_checked': n_dwell_checked},
           'truncated_at_press': args.truncate_at_press,
           'truncation': {'trials_without_mousedown': n_no_press, 'fixations_dropped': n_fix_dropped} if args.truncate_at_press else None,
           'population': {'trials_opportunity_known': len(known), 'trials_walked': n_walked,
                          'n_by_position': fp_tot.astype(int).tolist(), 'participants': len(per_pid)},
           'reach': {'first_pass': R_fp, 'any_time': R_any},
           'W': {'vectors': W, 'gaps_tvd': gaps, 'by_rank_diff': W_by_rank_diff,
                 'expected_rank_under_W': expected_rank,
                 'share_of_fixation_time_after_first_visit': share_return_time,
                 'note': 'positions 0..9 on the typed map, normalised within that range; derived = the C/W/L shortcut '
                         'W(i) ∝ ∏_{j<i} C(j) evaluated as reach; measured = share of fixation time at rank i'},
           'L': L, 'consistency': consistency}
    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_dir / 'summary.json', 'w'), indent=1)

    if args.truncate_at_press:
        print(f"PRESS-TRUNCATED: {n_fix_dropped:,} fixations dropped at/after the last mousedown; {n_no_press} trials without a mousedown skipped")
    print(f"variant {args.variant}; trials known {len(known):,}, walked {n_walked:,}; G1 {g1:.1e}, G2 {max_dwell_diff:.3f} ms over {n_dwell_checked:,} slots")
    print('\nW(i): derived_fp  derived_any  meas_first  meas_any   (any − derived_fp)')
    for i in range(MAXP):
        print(f"  {i:2d}   {W['derived_first_pass'][i]:.3f}      {W['derived_any_time'][i]:.3f}       "
              f"{W['measured_first_visit'][i]:.3f}      {W['measured_any_time'][i]:.3f}    {W_by_rank_diff['measured_any_minus_derived_fp'][i]:+.3f}")
    for k, v in gaps.items():
        print(f"  TVD {k}: {v['tvd']:.3f} {v.get('ci', '')}")
    print(f"  expected rank under W: " + ', '.join(f"{k} {v:.2f}" for k, v in expected_rank.items()))
    print(f"  share of fixation time after the first visit: {share_return_time:.3f}")
    print(f"\nL(i) on {n_L:,} clicked trials (last row = 9 or deeper): derived_fp  click")
    for i in range(MAXP):
        print(f"  {i:2d}{'+' if i == MAXP - 1 else ' '}  {L_derived_n[i]:.3f}   {L_click[i]:.3f}")
    print(f"  TVD {L['tvd']:.3f}; E[stop] derived {L['expected_stop_rank_derived']:.2f} vs click {L['expected_stop_rank_click']:.2f}")
    print(f"  click above deepest fixated rank: {L['click_above_deepest_fixated']['share']:.3f} {L['click_above_deepest_fixated']['ci']}; "
          f"above deepest first-pass {L['click_above_deepest_first_pass']['share']:.3f}; above deepest on-screen {L['click_above_deepest_viewport']['share']:.3f}")
    print(f"  gap (deepest − click) mean {gap.mean():.2f} median {np.median(gap):.0f}; per-participant share median "
          f"{L['per_participant_share_click_above_deepest']['median']:.2f} IQR {L['per_participant_share_click_above_deepest']['iqr']}")
    print('\nCONSISTENCY: C implied by measured W vs first-pass reach ratio; L implied by measured W vs click')
    for i in range(MAXP - 1):
        print(f"  {i}->{i+1}  C_fp {C_fp[i]:.3f}   C(Wm) {C_from_Wm[i]:.3f}   |  L(Wm) {L_from_Wm[i]:.3f}   L_click {L_click[i]:.3f}")
    print(f"  L(Wm) 9+ {L_from_Wm[-1]:.3f} vs click {L_click[-1]:.3f}; TVD {consistency['tvd_L_impliedW_vs_click']:.3f}; "
          f"E[stop] implied {consistency['expected_stop_L_impliedW']:.2f} vs click {L['expected_stop_rank_click']:.2f}")
    print(f"  RBP fit: measured W p={consistency['rbp_fit_measured_W']['p']:.3f} (TVD {consistency['rbp_fit_measured_W']['tvd_to_W']:.3f}); "
          f"derived W p={consistency['rbp_fit_derived_W']['p']:.3f} (TVD {consistency['rbp_fit_derived_W']['tvd_to_W']:.3f})")
    print(f"\nwrote {out_dir / 'summary.json'}")


if __name__ == '__main__':
    main()
