"""Does a resumed scan pass carry the Survey amplitude signature?

Motivating question (2026-07-25): README claimed regressions "loop from
evaluate back to survey". The OSEC Markov pass (2026-05-31) showed
regressions are 99.6% Evaluate-phase, but that test is partly definitional
— Survey is operationalized in NB13 as trial saccades 1-5, so no mid-trial
segment *can* be labeled Survey. This script runs the non-circular version.

The Survey signature is amplitude, not index: NB13 K5/K6 give survey
107.4 px vs evaluate 69.9 px (1.54x). If a regress-then-resume cycle
re-enters Survey, the opening saccades of epoch 2+ should rebound toward
~107 px. If regression is a within-Evaluate transition, they should stay
at evaluate level.

Two anchors, because "where the new pass starts" is arguable:
  A. Epoch onset  — the HWM advance that resumes forward scanning
                    (same state machine as scan_epochs_per_trial.py).
  B. Regression landing — the first fixation after the backward jump.

Saccades are computed scroll-aware per docs/methodology/scroll-aware-saccades.md:
any saccade whose time window contains a scroll event measures page motion,
not eye motion, and is dropped.

Output: scripts/output/figures/epoch_saccade_amplitude_summary.json
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    get_trial_ids, load_fixations, load_mouse_events, get_trial_meta,
    organic_aoi_tops, assign_fixation_to_position,
)
from scan_epochs_per_trial import _hybrid_aoi_tops  # noqa: E402

OPENING_N = 5  # NB13's survey window: first 5 saccades of a pass
OUT = ROOT / 'scripts' / 'output' / 'figures' / 'epoch_saccade_amplitude_summary.json'


def scroll_aware_saccades(fixations, scrolls):
    """Amplitude per saccade, keyed by the index of its *landing* fixation.

    Mirrors notebooks-v2/13_survey_phase.ipynb cell 3 exactly.
    """
    out = {}
    scroll_t = sorted(st for st, _ in scrolls)
    for i in range(1, len(fixations)):
        f0, f1 = fixations[i - 1], fixations[i]
        if bisect.bisect_right(scroll_t, f1['t']) > bisect.bisect_left(scroll_t, f0['t']):
            continue  # spans a scroll event — measures the page, not the eye
        dx = f1['x'] - f0['x']
        dy = f1['y'] - f0['y']
        out[i] = float(np.hypot(dx, dy))
    return out


def walk_epochs(pos_by_fix):
    """Return (epoch_starts, regression_landings) as fixation indices.

    epoch_starts[0] is the first HWM advance (epoch 1); each later entry is a
    HWM advance that follows a regression — i.e. the user resumed scanning
    past where they had been. State machine identical to
    scan_epochs_per_trial.count_epochs, instrumented to emit the indices.
    """
    hwm = -1
    in_epoch = True
    n_epochs = 0
    regressed_since_advance = False
    epoch_starts = []
    landings = []
    prev_was_regression = False

    for fix_idx, p in pos_by_fix:
        if prev_was_regression:
            landings.append(fix_idx)
            prev_was_regression = False
        if p > hwm:
            if not in_epoch and regressed_since_advance:
                n_epochs += 1
                epoch_starts.append(fix_idx)
                in_epoch = True
                regressed_since_advance = False
            elif n_epochs == 0:
                n_epochs = 1
                epoch_starts.append(fix_idx)
                in_epoch = True
            hwm = p
        elif p < hwm:
            in_epoch = False
            regressed_since_advance = True
            prev_was_regression = True
    return epoch_starts, landings


def window_amps(sac_by_idx, start_fix_idx, n, stop_idx=None):
    """First `n` surviving saccades at or after start_fix_idx (exclusive of stop)."""
    amps = []
    for idx in sorted(k for k in sac_by_idx if k >= start_fix_idx):
        if stop_idx is not None and idx >= stop_idx:
            break
        amps.append(sac_by_idx[idx])
        if len(amps) >= n:
            break
    return amps


def analyze(attribution):
    opening = defaultdict(list)   # epoch number -> amplitudes (anchor A)
    body = defaultdict(list)      # epoch number -> amplitudes after the opening
    landing_open = []             # anchor B: post-regression-landing openings
    paired = []                   # (epoch1_body_median, epoch2_opening_median)
    n_trials = n_multi = 0

    for tid in get_trial_ids():
        fixations = load_fixations(tid)
        if len(fixations) < 10:
            continue
        meta = get_trial_meta(tid)
        if meta is None or meta[0] is None:
            continue
        tops = _hybrid_aoi_tops(tid) if attribution == 'hybrid' else organic_aoi_tops(tid)
        if not tops:
            continue
        n_res = len(tops)

        pos_by_fix = []
        for i, f in enumerate(fixations):
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is not None and p >= 0:
                pos_by_fix.append((i, p))
        if not pos_by_fix:
            continue

        _, scrolls, _ = load_mouse_events(tid)
        sac = scroll_aware_saccades(fixations, scrolls)
        if not sac:
            continue

        starts, landings = walk_epochs(pos_by_fix)
        if not starts:
            continue
        n_trials += 1
        if len(starts) >= 2:
            n_multi += 1

        for e, s in enumerate(starts, start=1):
            nxt = starts[e] if e < len(starts) else None
            op = window_amps(sac, s, OPENING_N, stop_idx=nxt)
            opening[min(e, 3)].extend(op)
            after = sorted(k for k in sac if k >= s and (nxt is None or k < nxt))[OPENING_N:]
            body[min(e, 3)].extend(sac[k] for k in after)

        # Paired within-trial: epoch 1 body (evaluate baseline) vs epoch 2 opening
        if len(starts) >= 2:
            e1_body = [sac[k] for k in sorted(sac) if starts[0] + OPENING_N <= k < starts[1]]
            e2_open = window_amps(sac, starts[1], OPENING_N,
                                  stop_idx=starts[2] if len(starts) > 2 else None)
            if len(e1_body) >= 3 and len(e2_open) >= 3:
                paired.append((float(np.median(e1_body)), float(np.median(e2_open))))

        for lf in landings:
            landing_open.extend(window_amps(sac, lf, OPENING_N))

    return {
        'attribution': attribution,
        'n_trials': n_trials,
        'n_trials_multi_epoch': n_multi,
        'opening': {k: v for k, v in opening.items()},
        'body': {k: v for k, v in body.items()},
        'landing_open': landing_open,
        'paired': paired,
    }


def _med(v):
    return float(np.median(v)) if len(v) else float('nan')


def report(r):
    print(f"\n=== {r['attribution']} ===")
    print(f"  trials: {r['n_trials']:,}   multi-epoch: {r['n_trials_multi_epoch']:,} "
          f"({100*r['n_trials_multi_epoch']/r['n_trials']:.1f}%)")

    e1_open = r['opening'].get(1, [])
    print(f"\n  {'window':<34s} {'median px':>10s} {'N':>10s}")
    for e in (1, 2, 3):
        o, b = r['opening'].get(e, []), r['body'].get(e, [])
        tag = f'epoch {e}' if e < 3 else 'epoch 3+'
        print(f"  {tag+' opening (sac 1-5)':<34s} {_med(o):>10.1f} {len(o):>10,}")
        print(f"  {tag+' body (sac 6+)':<34s} {_med(b):>10.1f} {len(b):>10,}")
    lo = r['landing_open']
    print(f"  {'post-regression-landing (sac 1-5)':<34s} {_med(lo):>10.1f} {len(lo):>10,}")

    print('\n  --- the test: does a resumed pass re-open wide? ---')
    for e in (2, 3):
        o = r['opening'].get(e, [])
        if len(o) < 30 or len(e1_open) < 30:
            continue
        u, p = stats.mannwhitneyu(e1_open, o, alternative='greater')
        ratio = _med(e1_open) / _med(o) if _med(o) else float('nan')
        tag = f'epoch {e}' if e < 3 else 'epoch 3+'
        print(f"  epoch 1 opening > {tag} opening: "
              f"{_med(e1_open):.1f} vs {_med(o):.1f} px ({ratio:.2f}x), "
              f"Mann-Whitney p = {p:.3e}")

    e1b = r['body'].get(1, [])
    e2o = r['opening'].get(2, [])
    if len(e1b) >= 30 and len(e2o) >= 30:
        u, p = stats.mannwhitneyu(e2o, e1b, alternative='greater')
        print(f"  epoch 2 opening > epoch 1 body (evaluate baseline): "
              f"{_med(e2o):.1f} vs {_med(e1b):.1f} px, Mann-Whitney p = {p:.3e}")

    if len(r['paired']) >= 20:
        a = np.array([p[0] for p in r['paired']])  # epoch 1 body
        b = np.array([p[1] for p in r['paired']])  # epoch 2 opening
        w, p = stats.wilcoxon(b, a)
        frac = (b > a).mean()
        lo, hi = stats.binomtest(int((b > a).sum()), len(a)).proportion_ci(0.95)
        print(f"  within-trial paired (N = {len(a):,} trials): "
              f"epoch2 opening {np.median(b):.1f} vs epoch1 body {np.median(a):.1f} px, "
              f"Wilcoxon W = {w:.0f}, p = {p:.3e}")
        print(f"    trials that rebound at all: {100*frac:.1f}% "
              f"[95% CI {100*lo:.1f}-{100*hi:.1f}] (coin flip = 50%)")

    # Effect size that actually matters: what fraction of the survey->evaluate
    # gap does a resumed pass recover? 1.0 = full re-entry into Survey, 0 = none.
    print('\n  --- fraction of the survey/evaluate amplitude gap recovered ---')
    base = _med(r['body'].get(1, []))       # evaluate baseline
    surv = _med(r['opening'].get(1, []))    # canonical survey
    gap = surv - base
    rng = np.random.default_rng(20260725)

    def boot_frac(vals):
        vals = np.asarray(vals)
        draws = [(np.median(rng.choice(vals, len(vals))) - base) / gap for _ in range(2000)]
        return np.percentile(draws, [2.5, 97.5])

    for label, vals in (('epoch 2 opening', r['opening'].get(2, [])),
                        ('epoch 3+ opening', r['opening'].get(3, [])),
                        ('post-regression landing', r['landing_open'])):
        if len(vals) < 30:
            continue
        f = (_med(vals) - base) / gap
        lo, hi = boot_frac(vals)
        print(f"  {label:<26s} {100*f:>6.1f}%  [95% CI {100*lo:.1f}-{100*hi:.1f}]")
    print(f"  (baseline = epoch1 body {base:.1f} px; survey = epoch1 opening {surv:.1f} px; "
          f"gap = {gap:.1f} px)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', default='both', choices=['organic', 'hybrid', 'both'])
    args = ap.parse_args()
    flavors = ['organic', 'hybrid'] if args.attribution == 'both' else [args.attribution]

    out = {}
    for f in flavors:
        r = analyze(f)
        report(r)
        out[f] = {
            'n_trials': r['n_trials'],
            'n_trials_multi_epoch': r['n_trials_multi_epoch'],
            'median_opening_by_epoch': {str(k): _med(v) for k, v in r['opening'].items()},
            'n_opening_by_epoch': {str(k): len(v) for k, v in r['opening'].items()},
            'median_body_by_epoch': {str(k): _med(v) for k, v in r['body'].items()},
            'n_body_by_epoch': {str(k): len(v) for k, v in r['body'].items()},
            'median_post_landing_opening': _med(r['landing_open']),
            'n_post_landing_opening': len(r['landing_open']),
            'n_paired_trials': len(r['paired']),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=2)
    print(f'\nWrote {OUT}')


if __name__ == '__main__':
    main()
