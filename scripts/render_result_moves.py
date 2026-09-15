#!/usr/bin/env python3
"""Render the forward / backward moves between results on AdSERP.

Every consecutive fixation pair assigned to two different results is a move.
Panels: (a) rank-to-rank transition matrix, row-normalised (forward moves
above the diagonal, returns below); (b) ranks jumped, forward vs back, log
counts; (c) duration of the fixation before the move by amplitude bin,
forward vs back (the ambient-mode signature); (d) saccade amplitude by ranks
jumped. Regime [LAB, AdSERP, typed]. Output: scripts/output/figures/result_moves.png
"""
import sys, csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl

rows = list(csv.DictReader(open(ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv')))
tids = sorted({r['trial_id'] for r in rows})
MAXR = 10
T = np.zeros((MAXR, MAXR)); moves = []
for tid in tids:
    try:
        tops = dl.typed_aoi_tops(tid); fx_ = dl.load_fixations(tid)
    except Exception:
        continue
    if not tops or len(fx_) < 2:
        continue
    n = len(tops); pos = [dl.assign_fixation_to_position(f['y'], tops, n) for f in fx_]
    seen = set()
    for i in range(1, len(fx_)):
        p, q = pos[i], pos[i - 1]
        if p is None or q is None or p < 0 or q < 0 or p == q:
            if p is not None and p >= 0: seen.add(p)
            continue
        amp = float(np.hypot(fx_[i]['x'] - fx_[i - 1]['x'], fx_[i]['y'] - fx_[i - 1]['y']))
        moves.append({'from': q, 'to': p, 'jump': p - q, 'amp': amp, 'prev_dur': fx_[i - 1].get('d', 200) or 200,
                      'return': int(p in seen)})
        if q < MAXR and p < MAXR:
            T[q, p] += 1
        seen.add(p)
jump = np.array([m['jump'] for m in moves]); amp = np.array([m['amp'] for m in moves])
pdur = np.array([m['prev_dur'] for m in moves], float); ret = np.array([m['return'] for m in moves])
fwd = jump > 0; back = jump < 0
print(f'moves {len(moves):,}: forward {fwd.mean():.3f} back {back.mean():.3f}; back moves to an already-visited result {ret[back].mean():.3f}')

fig, ax = plt.subplots(2, 2, figsize=(13, 11))
fig.suptitle('Moves between results on AdSERP (2,608 trials, 47 participants; every fixation pair on two different results)', fontsize=13)
# (a) transition matrix
Tn = T / np.maximum(T.sum(axis=1, keepdims=True), 1)
im = ax[0, 0].imshow(Tn, cmap='Blues', vmin=0, vmax=0.6, origin='upper')
ax[0, 0].set_xlabel('to result (rank, 1 = top)'); ax[0, 0].set_ylabel('from result (rank)')
ax[0, 0].set_xticks(range(MAXR)); ax[0, 0].set_xticklabels(range(1, MAXR + 1)); ax[0, 0].set_yticks(range(MAXR)); ax[0, 0].set_yticklabels(range(1, MAXR + 1))
for i in range(MAXR):
    for j in range(MAXR):
        if T[i, j] >= 50:
            ax[0, 0].text(j, i, f'{Tn[i, j]:.2f}', ha='center', va='center', fontsize=7.5, color='white' if Tn[i, j] > 0.35 else 'black')
ax[0, 0].plot([-0.5, MAXR - 0.5], [-0.5, MAXR - 0.5], color='#444', lw=0.8)
ax[0, 0].set_title(f'(a) Where a move goes (row-normalised; n = {int(T.sum()):,} moves)\nabove the diagonal = forward, below = back', fontsize=10.5)
fig.colorbar(im, ax=ax[0, 0], fraction=0.046, label='share of moves from this rank')
# (b) ranks jumped
bins = np.arange(-9.5, 10.5, 1)
ax[0, 1].hist(jump[fwd], bins=bins, color='#1f77b4', alpha=0.85, label=f'forward (n = {fwd.sum():,})')
ax[0, 1].hist(jump[back], bins=bins, color='#d62728', alpha=0.85, label=f'back (n = {back.sum():,})')
ax[0, 1].set_yscale('log'); ax[0, 1].set_xlabel('ranks jumped (to − from)'); ax[0, 1].set_ylabel('moves (log scale)')
ax[0, 1].set_title('(b) How far a move jumps\n70 % of moves are one rank; long jumps occur both ways', fontsize=10.5); ax[0, 1].legend()
ax[0, 1].set_xticks(range(-9, 10))
# (c) preceding fixation duration by amplitude
abins = [(0, 100, '< 100'), (100, 300, '100–300'), (300, 600, '300–600'), (600, 1e9, '> 600')]
x = np.arange(len(abins)); w = 0.38
for off, mask, col, lab in ((-w / 2, fwd, '#1f77b4', 'forward'), (w / 2, back, '#d62728', 'back')):
    med = [np.median(pdur[mask & (amp >= lo) & (amp < hi)]) if (mask & (amp >= lo) & (amp < hi)).sum() > 30 else np.nan for lo, hi, _ in abins]
    q1 = [np.percentile(pdur[mask & (amp >= lo) & (amp < hi)], 25) if (mask & (amp >= lo) & (amp < hi)).sum() > 30 else np.nan for lo, hi, _ in abins]
    q3 = [np.percentile(pdur[mask & (amp >= lo) & (amp < hi)], 75) if (mask & (amp >= lo) & (amp < hi)).sum() > 30 else np.nan for lo, hi, _ in abins]
    ax[1, 0].bar(x + off, med, w, color=col, label=lab, yerr=[np.array(med) - np.array(q1), np.array(q3) - np.array(med)], capsize=3, error_kw={'lw': 0.8})
ax[1, 0].set_xticks(x); ax[1, 0].set_xticklabels([f'{l} px' for _, _, l in abins]); ax[1, 0].set_xlabel('saccade amplitude of the move')
ax[1, 0].set_ylabel('duration of the fixation BEFORE the move, ms (median, IQR)')
ax[1, 0].set_title('(c) The fixation before a long jump is shorter (ambient mode)\nshort fixation → long saccade; long fixation → short saccade', fontsize=10.5); ax[1, 0].legend()
# (d) amplitude by |ranks jumped|
aj = np.abs(jump); groups = [amp[aj == k] for k in range(1, 7)] + [amp[aj >= 7]]
ax[1, 1].boxplot(groups, showfliers=False, medianprops={'color': '#d62728'})
ax[1, 1].set_xticklabels(['1', '2', '3', '4', '5', '6', '7+']); ax[1, 1].set_xlabel('|ranks jumped|'); ax[1, 1].set_ylabel('saccade amplitude, px (median, IQR, whiskers 1.5 IQR)')
ax[1, 1].set_title('(d) Amplitude grows with ranks jumped\n(one rank ≈ one result block; 43 px ≈ 1° at 65 cm on the 17-inch 1707FP)', fontsize=10.5)
for a in ax.flat:
    a.tick_params(labelsize=9)
plt.tight_layout(rect=[0, 0, 1, 0.96])
out = ROOT / 'scripts/output/figures/result_moves.png'; out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=150); print(f'wrote {out}')
