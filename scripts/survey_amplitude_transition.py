#!/usr/bin/env python3
"""The survey-to-evaluate saccade-amplitude transition, as a gated producer.

Promotes NB13 (`notebooks-v2/13_survey_phase.ipynb`, cells 3/5/7/9, scroll-aware
refresh of 2026-06-03) to a sidecar so a paper can name a file rather than a
notebook. The Leaky Cursor manuscript (§3.3) grounds its fifth-fixation cut on
this transition and, until 2026-10-11, quoted the pre-scroll-aware clamped
values (107.8 / 69.4 px, N = 2,754) with a citation to the AllSERP paper, which
does not report them. This producer is the source for those numbers.

Mirrors the notebook exactly:
  - saccade = Euclidean distance between consecutive fixations in page space;
    a saccade whose time window contains a scroll event measures page motion,
    not eye motion, and is dropped (docs/methodology/scroll-aware-saccades.md)
  - survey = saccades 1-5 (1-based index of the landing fixation)
  - evaluate = saccades 6-30 under the per-trial first-30 cap (K6), and 6+
    with no cap (NB13 cell 11's cohort)
  - slope = Spearman(index, amplitude) over the first 20 saccades, trials with
    >= 10 saccades; one-sample t vs 0; fraction negative
  - within participant: median per-trial rho per participant (id = tid prefix),
    sign test and Wilcoxon on the per-participant medians

Two cohorts, because NB13 ran on every trial with a mouse CSV (2,776) while
the typed-AOI papers drop the 12 alignment-suspect trials
(data/aoi-typed/alignment-exclusions.json): `all` and `typed`. Quote the one
that matches the corpus the paper states.

Output: scripts/output/survey_amplitude_transition/summary.json
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    get_trial_ids, load_fixations, load_mouse_events, get_trial_meta,
    typed_alignment_exclusions,
)

SURVEY_END = 5      # NB13: survey is saccades 1-5
MAX_SAC = 30        # NB13 cell 5 per-trial cap for K5/K6
SLOPE_WINDOW = 20   # NB13 cell 7: first 20 saccades
MIN_SACCADES = 10   # NB13 cell 7: trials entering the slope test


def scroll_aware_amplitudes(fixations, scrolls):
    """[(index, amplitude)] with 1-based landing-fixation index; NB13 cell 3."""
    out = []
    scroll_t = sorted(st for st, _ in scrolls)
    for i in range(1, len(fixations)):
        f0, f1 = fixations[i - 1], fixations[i]
        if bisect.bisect_right(scroll_t, f1['t']) > bisect.bisect_left(scroll_t, f0['t']):
            continue
        out.append((i, float(np.hypot(f1['x'] - f0['x'], f1['y'] - f0['y']))))
    return out


def load_trials(exclude):
    trials = {}
    n_lt5 = n_nometa = 0
    for tid in get_trial_ids():
        if tid in exclude:
            continue
        fixations = load_fixations(tid)
        if len(fixations) < 5:
            n_lt5 += 1
            continue
        meta = get_trial_meta(tid)
        if meta[0] is None:
            n_nometa += 1
            continue
        _, scrolls, _ = load_mouse_events(tid)
        trials[tid] = scroll_aware_amplitudes(fixations, scrolls)
    return trials, {'skipped_lt5_fixations': n_lt5, 'skipped_no_meta': n_nometa}


def analyze(trials):
    amp_by_pos = defaultdict(list)
    survey, eval_cap, eval_nocap = [], [], []
    for sacs in trials.values():
        for idx, amp in sacs[:MAX_SAC]:
            amp_by_pos[idx].append(amp)
        for k, (idx, amp) in enumerate(sacs):
            if idx <= SURVEY_END:
                survey.append(amp)
            else:
                eval_nocap.append(amp)
                if k < MAX_SAC:
                    eval_cap.append(amp)
    # NB13 cell 5 takes survey/evaluate from the position buckets of the capped list
    survey_k5 = [a for p in range(1, SURVEY_END + 1) for a in amp_by_pos.get(p, [])]
    eval_k6 = [a for p in range(SURVEY_END + 1, MAX_SAC + 1) for a in amp_by_pos.get(p, [])]
    u, p_u = stats.mannwhitneyu(survey_k5, eval_k6, alternative='greater')

    medians_by_pos = {p: float(np.median(v)) for p, v in sorted(amp_by_pos.items()) if p <= MAX_SAC}
    # where the per-position median first drops below the midpoint of the two
    # phase medians: the "transition point" the manuscript says the cut sits at
    mid = (np.median(survey_k5) + np.median(eval_k6)) / 2
    transition_index = next((p for p, m in medians_by_pos.items() if m < mid), None)

    rhos, by_part = [], defaultdict(list)
    for tid, sacs in trials.items():
        win = sacs[:SLOPE_WINDOW]
        if len(win) < MIN_SACCADES:
            continue
        rho, _ = stats.spearmanr([i for i, _ in win], [a for _, a in win])
        if np.isfinite(rho):
            rhos.append(rho)
            by_part[tid.split('-')[0]].append(rho)
    rhos = np.array(rhos)
    t, p_t = stats.ttest_1samp(rhos, 0)
    part_med = np.array([np.median(v) for v in by_part.values()])
    n_part, n_neg = len(part_med), int((part_med < 0).sum())
    sign_p = stats.binomtest(n_neg, n_part, 0.5, alternative='greater').pvalue
    wil = stats.wilcoxon(part_med, alternative='less')

    return {
        'n_trials_loaded': len(trials),
        'K5_survey_median_px': float(np.median(survey_k5)),
        'K5_n_saccades': len(survey_k5),
        'K6_evaluate_median_px_cap30': float(np.median(eval_k6)),
        'K6_n_saccades_cap30': len(eval_k6),
        'evaluate_median_px_nocap': float(np.median(eval_nocap)),
        'evaluate_n_saccades_nocap': len(eval_nocap),
        'K7_ratio_cap30': float(np.median(survey_k5) / np.median(eval_k6)),
        'K8_mannwhitney_U': float(u),
        'K8_mannwhitney_p': float(p_u),
        'K8_p_underflows_to_zero': bool(p_u == 0.0),
        'median_by_saccade_index': medians_by_pos,
        'phase_midpoint_px': float(mid),
        'first_index_below_midpoint': transition_index,
        'K1_n_trials_ge10_saccades': int(len(rhos)),
        'K2_mean_rho_first20': float(rhos.mean()),
        'K3_t': float(t), 'K3_p': float(p_t), 'K3_df': int(len(rhos) - 1),
        'K4_frac_trials_rho_negative': float((rhos < 0).mean()),
        'K20_participants_median_rho_negative': n_neg,
        'K20_participants': n_part,
        'K21_sign_test_p': float(sign_p),
        'K21_wilcoxon_W': float(wil.statistic), 'K21_wilcoxon_p': float(wil.pvalue),
        'K22_median_of_participant_median_rho': float(np.median(part_med)),
        'K22_range': [float(part_med.min()), float(part_med.max())],
    }


def git_sha():
    try:
        return subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='scripts/output/survey_amplitude_transition/summary.json')
    args = ap.parse_args()
    excl_path = ROOT / 'data' / 'aoi-typed' / 'alignment-exclusions.json'
    exclusions = typed_alignment_exclusions()
    out = {
        'experiment': 'survey_amplitude_transition (NB13 K1-K8, K20-K22 as a producer)',
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'git_sha': git_sha(),
        'regime': '[LAB, AdSERP]',
        'method': 'scroll-aware saccades (docs/methodology/scroll-aware-saccades.md); survey = saccades 1-5; '
                  f'evaluate = 6-{MAX_SAC} (cap) and 6+ (no cap); slope over first {SLOPE_WINDOW} saccades, '
                  f'trials with >= {MIN_SACCADES}',
        'notebook': 'notebooks-v2/13_survey_phase.ipynb',
        'alignment_exclusions_file': str(excl_path.relative_to(ROOT)),
        'alignment_exclusions_sha256': hashlib.sha256(excl_path.read_bytes()).hexdigest(),
        'n_alignment_exclusions': len(exclusions),
        'cohorts': {},
    }
    for name, exclude in (('all', frozenset()), ('typed', exclusions)):
        trials, skipped = load_trials(exclude)
        res = analyze(trials)
        res.update(skipped)
        out['cohorts'][name] = res
        print(f"[{name}] trials {res['n_trials_loaded']}  K5 {res['K5_survey_median_px']:.1f} px (N {res['K5_n_saccades']})  "
              f"K6 {res['K6_evaluate_median_px_cap30']:.1f} px (N {res['K6_n_saccades_cap30']})  nocap {res['evaluate_median_px_nocap']:.1f}  "
              f"ratio {res['K7_ratio_cap30']:.2f}  slope N {res['K1_n_trials_ge10_saccades']} rho {res['K2_mean_rho_first20']:.3f} "
              f"p {res['K3_p']:.2e}  neg {res['K4_frac_trials_rho_negative']:.3f}  within {res['K20_participants_median_rho_negative']}/{res['K20_participants']}  "
              f"transition idx {res['first_index_below_midpoint']}")
    dest = ROOT / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(dest, 'w'), indent=1)
    print('wrote', dest.relative_to(ROOT))


if __name__ == '__main__':
    main()
