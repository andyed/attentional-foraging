"""LF/HF argmax → click prediction over chance baseline (organic_hybrid).

Information-theoretic frame: given a SERP consideration set of size N (the
positions the user actually visited during the trial), how often does
argmax(first-pass LF/HF) coincide with the click position?

Baseline: chance prediction = 1/N (uniform over visited positions).

Reports:
  - Hit rate (argmax matches click_pos)
  - Chance baseline (mean of 1/N over trials)
  - Lift over chance, per consideration-set size, and pooled

Output: scripts/output/lfhf_argmax_predicts_click/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_argmax_predicts_click.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.signal import butter, sosfiltfilt

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_argmax_predicts_click'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

# Butterworth params (Duchowski 2026)
FS = 150
LF_SOS = butter(4, 1.6, btype='low', fs=FS, output='sos')
HF_SOS = butter(4, (1.6, 4.0), btype='band', fs=FS, output='sos')
MIN_SAMPLES = 150


def visit_segments_first_only(fix, tops, n_res):
    first = {}
    max_seen = -1
    for f in fix:
        pos = assign_fixation_to_position(f['y'], tops, n_res)
        if pos is None or pos < 0:
            continue
        win = (f['t'], f['t'] + f['d'])
        if pos >= max_seen:
            first.setdefault(pos, []).append(win)
            if pos > max_seen:
                max_seen = pos
    return first


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    return float(lf_p / hf_p) if hf_p >= 1e-20 else None


def process_trial(tid):
    """Return (click_pos, {pos: lfhf}, n_visited) or None."""
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return None
    ts = np.asarray(pupil['ts'])
    pd = np.asarray(pupil['clean_pd'])
    if len(pd) < MIN_SAMPLES * 2:
        return None
    lf_sig = sosfiltfilt(LF_SOS, pd)
    hf_sig = sosfiltfilt(HF_SOS, pd)

    fix = load_fixations(tid)
    if not fix:
        return None
    tops = typed_aoi_tops(tid)
    if not tops:
        return None
    n_res = len(tops)

    first = visit_segments_first_only(fix, tops, n_res)
    if not first:
        return None

    lfhf_by_pos = {}
    for pos, windows in first.items():
        v = lfhf_for_windows(lf_sig, hf_sig, ts, windows)
        if v is not None:
            lfhf_by_pos[pos] = v
    return lfhf_by_pos


def click_pos_hybrid(features_by_trial, tid):
    """Get hybrid-display-order click position from features file."""
    rows = features_by_trial.get(tid, [])
    if not rows:
        return None
    return rows[0].get('click_pos')


def main():
    print('[argmax] LF/HF first-pass argmax vs click_pos (organic_hybrid)', file=sys.stderr)

    # Load click_pos per trial from hybrid features
    feats = json.load(open(DATA / 'cursor-approach-features-typed.json'))
    by_trial = {}
    for r in feats:
        by_trial.setdefault(r['trial_id'], []).append(r)
    print(f'  trials in features: {len(by_trial):,}', file=sys.stderr)

    # Trial set: those with first-pass LF/HF data
    trial_ids = sorted(by_trial.keys())

    hits = 0
    misses = 0
    chance_baselines = []
    by_n = {}  # consideration-set size → list of (hit, chance)
    n_skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)} trials, hits so far: {hits}', file=sys.stderr)
        click_pos = click_pos_hybrid(by_trial, tid)
        if click_pos is None or click_pos < 0:
            n_skipped += 1
            continue
        lfhf_by_pos = process_trial(tid)
        if not lfhf_by_pos:
            n_skipped += 1
            continue
        n_visited = len(lfhf_by_pos)
        if n_visited < 1:
            n_skipped += 1
            continue
        # Argmax: pick highest-LF/HF position
        argmax_pos = max(lfhf_by_pos.keys(), key=lambda p: lfhf_by_pos[p])
        hit = (argmax_pos == click_pos)
        chance = 1.0 / n_visited
        if hit:
            hits += 1
        else:
            misses += 1
        chance_baselines.append(chance)
        by_n.setdefault(n_visited, []).append((hit, chance))

    n_total = hits + misses
    hit_rate = hits / n_total if n_total else 0.0
    mean_chance = float(np.mean(chance_baselines)) if chance_baselines else 0.0
    lift_pct_pts = (hit_rate - mean_chance) * 100
    lift_fold = hit_rate / mean_chance if mean_chance > 0 else float('nan')

    print(f'\n  trials with both click_pos and LF/HF argmax: {n_total:,}', file=sys.stderr)
    print(f'  trials skipped: {n_skipped:,}', file=sys.stderr)
    print(f'  hit rate (argmax = click): {hit_rate:.3f}', file=sys.stderr)
    print(f'  mean chance baseline (1/N over trials): {mean_chance:.3f}', file=sys.stderr)
    print(f'  lift: +{lift_pct_pts:.1f} pp absolute, {lift_fold:.2f}× chance', file=sys.stderr)

    # Significance test: paired comparison of hit (0/1) vs chance per trial
    # using exact binomial against pooled chance
    p_binom = float(stats.binomtest(hits, n_total, mean_chance,
                                     alternative='greater').pvalue) if n_total else float('nan')
    print(f'  binomial test p (greater than chance): {p_binom:.2e}', file=sys.stderr)

    # By consideration-set size
    by_n_summary = {}
    for n_vis, results in sorted(by_n.items()):
        n_t = len(results)
        if n_t < 5:
            continue
        h = sum(1 for r in results if r[0])
        ch = float(np.mean([r[1] for r in results]))
        hr = h / n_t
        p = float(stats.binomtest(h, n_t, ch, alternative='greater').pvalue) if n_t else float('nan')
        by_n_summary[str(n_vis)] = {
            'n_trials': n_t, 'hit_rate': hr, 'chance': ch,
            'lift_pp': (hr - ch) * 100, 'lift_fold': hr / ch if ch > 0 else float('nan'),
            'p_greater_chance': p,
        }

    out = {
        'attribution': 'typed',
        'predictor': 'argmax(first-pass LF/HF) over visited positions',
        'n_trials_eligible': n_total,
        'n_trials_skipped': n_skipped,
        'hit_rate': hit_rate,
        'mean_chance_baseline': mean_chance,
        'lift_pp': lift_pct_pts,
        'lift_fold': lift_fold,
        'p_binom_vs_chance': p_binom,
        'by_consideration_set_size': by_n_summary,
    }

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(out, indent=2))

    lines = [
        '# LF/HF argmax → click prediction (organic_hybrid)\n',
        '_Generated 2026-05-03 by `scripts/lfhf_argmax_predicts_click.py`._\n',
        '## Question\n',
        'Given a SERP consideration set of size N (positions the user visited),',
        'does the position with the highest first-pass LF/HF coincide with the',
        'click position more often than chance (1/N)?\n',
        '## Headline\n',
        f'**n trials eligible**: {n_total:,} (skipped: {n_skipped:,})\n',
        f'- **hit rate** (argmax = click): **{hit_rate:.3f}**',
        f'- **mean chance baseline** (1/N): **{mean_chance:.3f}**',
        f'- **lift**: +{lift_pct_pts:.1f} pp absolute, {lift_fold:.2f}× chance',
        f'- *p* (binomial, greater than chance): **{p_binom:.2e}**',
        '',
        '## By consideration-set size N',
        '',
        '| N visited | n trials | hit rate | chance | lift (pp) | lift (×) | p |',
        '|---|---|---|---|---|---|---|',
    ]
    for n_vis in sorted(by_n_summary.keys(), key=int):
        s = by_n_summary[n_vis]
        lines.append(f'| {n_vis} | {s["n_trials"]} | {s["hit_rate"]:.3f} | {s["chance"]:.3f} | '
                     f'+{s["lift_pp"]:.1f} | {s["lift_fold"]:.2f}× | {s["p_greater_chance"]:.2e} |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
