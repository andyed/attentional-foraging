"""Within-trial drift control for the LF/HF first-vs-return paired finding.

Hypothesis being controlled: the +9.75 LF/HF return-vs-first paired Δ could
reflect within-trial pupil drift (autonomic regulation, fatigue, baseline
shift) rather than cognitive content. If LF/HF rises with within-trial time
*independent of return-status*, the paired finding is contaminated.

Test: WITHIN each trial, compare LF/HF at the EARLIEST forward-pass position
vs the LATEST forward-pass position (forward-only, no return). If LF/HF
DROPS as forward-pass time progresses (matching the existing rank gradient
which finds ρ = −0.927 across trials), drift cannot explain the paired
finding's +9.75 elevation on returns.

Output: scripts/output/lfhf_within_trial_drift_control/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_within_trial_drift_control.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_within_trial_drift_control'
OUT.mkdir(parents=True, exist_ok=True)

# bbox-organic: the post-cascade primary attribution (single rank ordering for ETTAC)
LFHF_PATH = DATA / 'butterworth-lfhf-by-position-organic.json'


def main():
    print('[drift] Within-trial LF/HF first-pass time gradient', file=sys.stderr)
    lfhf = json.load(open(LFHF_PATH))
    print(f'  trials: {len(lfhf):,}', file=sys.stderr)

    # For each trial, sort positions by `pos` (= time order under HWM gating);
    # take earliest and latest with valid LF/HF. Δ = latest − earliest.
    deltas = []
    pid_deltas = {}
    n_trials_with_2plus = 0
    n_trials_with_3plus = 0

    for tid, payload in lfhf.items():
        positions = sorted(
            [p for p in payload.get('positions', []) if p.get('lfhf') is not None],
            key=lambda p: p['pos'],
        )
        if len(positions) < 2:
            continue
        n_trials_with_2plus += 1
        if len(positions) >= 3:
            n_trials_with_3plus += 1

        early_lfhf = float(positions[0]['lfhf'])
        late_lfhf = float(positions[-1]['lfhf'])
        early_pos = positions[0]['pos']
        late_pos = positions[-1]['pos']
        delta = late_lfhf - early_lfhf
        deltas.append({
            'trial_id': tid,
            'pid': tid.split('-')[0],
            'early_pos': early_pos, 'late_pos': late_pos,
            'early_lfhf': early_lfhf, 'late_lfhf': late_lfhf,
            'delta': delta,
            'rank_span': late_pos - early_pos,
        })
        pid_deltas.setdefault(tid.split('-')[0], []).append(delta)

    delta_arr = np.array([d['delta'] for d in deltas])
    n = len(delta_arr)
    print(f'  trials with ≥2 forward-pass positions: {n_trials_with_2plus:,}', file=sys.stderr)
    print(f'  trials with ≥3 forward-pass positions: {n_trials_with_3plus:,}', file=sys.stderr)

    # ── Obs-level: paired Wilcoxon over trials ──
    p_two = float(stats.wilcoxon(delta_arr, alternative='two-sided').pvalue)
    p_less = float(stats.wilcoxon(delta_arr, alternative='less').pvalue)  # rank-gradient pred
    p_greater = float(stats.wilcoxon(delta_arr, alternative='greater').pvalue)
    pct_neg = float(100 * (delta_arr < 0).mean())
    median_d = float(np.median(delta_arr))
    mean_d = float(delta_arr.mean())

    print(f'\n  TRIAL-LEVEL Δ = LF/HF(latest forward pos) − LF/HF(earliest forward pos)', file=sys.stderr)
    print(f'  n trials: {n:,}  median Δ: {median_d:+.3f}  mean Δ: {mean_d:+.3f}', file=sys.stderr)
    print(f'  % Δ < 0: {pct_neg:.1f}%  (drift hypothesis predicts ≈ 50%; '
          f'rank-gradient predicts >> 50%)', file=sys.stderr)
    print(f'  Wilcoxon p (two-sided): {p_two:.2e}', file=sys.stderr)
    print(f'  Wilcoxon p (less than 0): {p_less:.2e}', file=sys.stderr)

    # ── Participant-level ──
    ppt_means = []
    for pid, vals in pid_deltas.items():
        if vals:
            ppt_means.append(float(np.mean(vals)))
    ppt_arr = np.array(ppt_means)
    p_two_ppt = float(stats.wilcoxon(ppt_arr, alternative='two-sided').pvalue)
    p_less_ppt = float(stats.wilcoxon(ppt_arr, alternative='less').pvalue)
    pct_neg_ppt = float(100 * (ppt_arr < 0).mean())

    print(f'\n  PARTICIPANT-LEVEL (mean of trial deltas per participant)', file=sys.stderr)
    print(f'  n participants: {len(ppt_arr)}  '
          f'mean of means: {ppt_arr.mean():+.3f}  median of means: {np.median(ppt_arr):+.3f}',
          file=sys.stderr)
    print(f'  % participants Δ < 0: {pct_neg_ppt:.1f}%', file=sys.stderr)
    print(f'  Wilcoxon p (less than 0): {p_less_ppt:.2e}', file=sys.stderr)

    # ── Per-rank-span sub-stratification (large rank spans more likely to
    # show the gradient if rank is the driver, less likely if time is) ──
    by_span = {}
    for d in deltas:
        bucket = min(d['rank_span'], 7)
        by_span.setdefault(bucket, []).append(d['delta'])
    span_summary = {}
    for span, vals in sorted(by_span.items()):
        if len(vals) >= 5:
            arr = np.array(vals)
            p_l = float(stats.wilcoxon(arr, alternative='less').pvalue)
            span_summary[str(span)] = {
                'n': len(arr),
                'median_delta': float(np.median(arr)),
                'mean_delta': float(arr.mean()),
                'pct_negative': float(100 * (arr < 0).mean()),
                'p_less_than_zero': p_l,
            }

    out = {
        'attribution': 'absolute',
        'n_trials': n,
        'trial_level': {
            'mean_delta': mean_d,
            'median_delta': median_d,
            'pct_negative': pct_neg,
            'p_two_sided': p_two,
            'p_less_than_zero': p_less,
            'p_greater_than_zero': p_greater,
        },
        'participant_level': {
            'n_participants': int(len(ppt_arr)),
            'mean_of_means': float(ppt_arr.mean()),
            'median_of_means': float(np.median(ppt_arr)),
            'pct_negative': pct_neg_ppt,
            'p_two_sided': p_two_ppt,
            'p_less_than_zero': p_less_ppt,
        },
        'per_rank_span': span_summary,
    }

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(out, indent=2))

    # Markdown report
    lines = [
        '# Within-trial LF/HF drift control\n',
        '_Generated 2026-05-03 by `scripts/lfhf_within_trial_drift_control.py`._\n',
        '## Question\n',
        'Could the +9.75 LF/HF return-vs-first paired Δ reflect within-trial pupil',
        'drift (autonomic regulation, fatigue, baseline shift) rather than cognitive',
        'content of the return moment?\n',
        '## Test\n',
        'WITHIN each trial, compare LF/HF at the **earliest forward-pass position**',
        '(early in trial time) vs the **latest forward-pass position** (later in trial',
        'time). Forward-only — no return visits in this control.\n',
        '## Decision rule\n',
        '- If Δ ≈ 0 (later time ≠ different LF/HF): drift hypothesis cannot explain',
        '  the paired finding. Paired finding is genuine cognitive content.',
        '- If Δ > 0 (later time = higher LF/HF, mirroring the paired Δ): drift',
        '  hypothesis is plausible. Paired finding may be confounded.',
        '- If Δ < 0 (later time = lower LF/HF, matching the cross-trial rank',
        '  gradient): drift hypothesis is decisively rejected.\n',
        '## Result\n',
        f'**Trial-level paired Wilcoxon, n = {n:,} trials with ≥2 forward-pass positions**',
        '',
        f'- median Δ = **{median_d:+.3f}**',
        f'- mean Δ = {mean_d:+.3f}',
        f'- {pct_neg:.1f}% of trials show Δ < 0',
        f'- *p* (two-sided) = {p_two:.2e}',
        f'- *p* (less than 0, rank-gradient prediction) = {p_less:.2e}',
        '',
        f'**Participant-level**',
        '',
        f'- {len(ppt_arr)} participants, mean-of-means = {ppt_arr.mean():+.3f}',
        f'- {pct_neg_ppt:.1f}% of participants show Δ < 0',
        f'- *p* (less than 0) = {p_less_ppt:.2e}',
        '',
        '## Per-rank-span sensitivity',
        '',
        '| rank span | n | median Δ | mean Δ | % Δ < 0 | p (less than 0) |',
        '|---|---|---|---|---|---|',
    ]
    for span, s in sorted(span_summary.items(), key=lambda kv: int(kv[0])):
        label = f'{span}' if int(span) < 7 else '7+'
        lines.append(f'| {label} | {s["n"]} | {s["median_delta"]:+.3f} | '
                     f'{s["mean_delta"]:+.3f} | {s["pct_negative"]:.1f}% | '
                     f'{s["p_less_than_zero"]:.2e} |')

    out_md = OUT / 'report.md'
    out_md.write_text('\n'.join(lines))
    print(f'\nwrote {out_json.relative_to(ROOT)}', file=sys.stderr)
    print(f'wrote {out_md.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
