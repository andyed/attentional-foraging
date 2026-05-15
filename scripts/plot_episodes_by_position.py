"""Regenerate episodes-by-position.png.

Two-panel figure showing reading-episode structure (fixations per episode
and episode duration ms) by SERP result position, faceted by SERP
difficulty tercile (Easy / Medium / Hard, split on Jaccard token overlap).

Episodes are pooled fixations: consecutive fixations on the same result
position connected by minor saccades (<100 px) form a single episode.
Durations include the inter-fixation saccade gaps (parafoveal preview).

Uses post-fix coordinate conventions from data_loader — FPOGY is page-space,
so fixation-to-position mapping uses page_y vs result_bands tops directly
(no `+ scroll`).

Output:
    docs/drafts/cikm-2026/figures/episodes-by-position.png
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    get_trial_ids,
    load_trial,
    classify_fixations,
)

OUT_CIKM = ROOT / 'docs/drafts/cikm-2026/figures/episodes-by-position.png'
DIFFICULTY_JSON = ROOT / 'AdSERP/data/serp-difficulty-measures.json'

MAX_POS = 10
MINOR_SACCADE_PX = 100
MIN_FIX_DUR_MS = 60

# ── Style ──────────────────────────────────────────────────────────────────
BG = '#ffffff'
INK = '#0b1220'      # 18.72:1
MUTED = '#394150'    # 10.26:1

# Difficulty tercile colors — all >= 8:1 on white
C_EASY = '#0b5d1e'   # 8.08:1 deep green
C_MED = '#6a2c0a'    # 10.62:1 dark amber
C_HARD = '#9a1e1e'   # 8.14:1 deep red

TERCILE_COLORS = {'Easy': C_EASY, 'Medium': C_MED, 'Hard': C_HARD}


def _lum(hx: str) -> float:
    r, g, b = (int(hx[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg: str, bg: str = BG) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


for _name, _hx in (('INK', INK), ('MUTED', MUTED),
                    ('C_EASY', C_EASY), ('C_MED', C_MED), ('C_HARD', C_HARD)):
    _r = contrast(_hx)
    assert _r >= 8.0, f'{_name} {_hx} contrast {_r:.2f}:1 below 8:1 floor'


plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica Neue', 'Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 11,
    'font.weight': 'regular',
    'axes.edgecolor': INK,
    'axes.labelcolor': INK,
    'axes.titlecolor': INK,
    'text.color': INK,
    'xtick.color': INK,
    'ytick.color': INK,
    'axes.titleweight': 'semibold',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 1.1,
    'xtick.major.width': 1.1,
    'ytick.major.width': 1.1,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
    'legend.fontsize': 10,
    'legend.frameon': False,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
    'savefig.dpi': 160,
})


# ── Episode extraction ─────────────────────────────────────────────────────

def compute_episodes(classified_fix: list) -> list[dict]:
    """Pool consecutive fixations on the same result into reading episodes.

    An episode breaks when (a) the next fixation lands on a different result
    position, or (b) the inter-fixation saccade distance is >= MINOR_SACCADE_PX
    (a 'major' saccade out of the result region). Episodes on position -1
    (outside any result band) are discarded.

    Each episode is a dict with pos, n_fixations, duration_ms.
    """
    episodes: list[dict] = []
    current_pos: int | None = None
    current_fixs: list[dict] = []

    def _flush() -> None:
        if current_fixs and current_pos is not None and current_pos >= 0:
            first = current_fixs[0]
            last = current_fixs[-1]
            # Duration: from first fixation start to last fixation end
            dur = (last['t'] + last['d']) - first['t']
            episodes.append({
                'pos': current_pos,
                'n_fixations': len(current_fixs),
                'duration_ms': float(dur),
            })

    prev = None
    for f in classified_fix:
        if f['d'] < MIN_FIX_DUR_MS:
            continue
        if prev is not None:
            dx = f['x'] - prev['x']
            dy = f['y'] - prev['y']
            sacc_dist = (dx * dx + dy * dy) ** 0.5
        else:
            sacc_dist = 0.0

        same_pos = (current_pos is not None and f['position'] == current_pos)
        minor = sacc_dist < MINOR_SACCADE_PX

        if same_pos and minor:
            current_fixs.append(f)
        else:
            _flush()
            current_pos = f['position']
            current_fixs = [f]
        prev = f
    _flush()
    return episodes


# ── Main compute ───────────────────────────────────────────────────────────

def compute() -> tuple[dict, dict, int]:
    with open(DIFFICULTY_JSON) as f:
        diff = json.load(f)

    # Build difficulty terciles on Jaccard (canonical difficulty metric used
    # by the notebook — token overlap ∈ [0, 1], higher = harder).
    jaccards = np.array(
        [v['jaccard'] for v in diff.values() if v['jaccard'] is not None]
    )
    t_lo, t_hi = np.percentile(jaccards, [33.33, 66.67])
    print(f'  Jaccard terciles: Easy <= {t_lo:.3f} < Medium <= {t_hi:.3f} < Hard')

    def _group(j: float) -> str:
        if j <= t_lo:
            return 'Easy'
        if j <= t_hi:
            return 'Medium'
        return 'Hard'

    # pos_data[group][pos] = {'nfix': [...], 'dur': [...]}
    pos_data: dict = {g: {p: {'nfix': [], 'dur': []} for p in range(MAX_POS)}
                      for g in ('Easy', 'Medium', 'Hard')}
    trial_counts: dict = {g: 0 for g in ('Easy', 'Medium', 'Hard')}
    total_episodes = 0

    tids = get_trial_ids()
    for i, tid in enumerate(tids):
        if i % 250 == 0:
            print(f'  [{i}/{len(tids)}] {tid}', flush=True)
        d = diff.get(tid)
        if d is None or d.get('jaccard') is None:
            continue
        trial = load_trial(tid)
        if trial is None:
            continue
        fix = classify_fixations(trial, hwm_tolerance=50)
        episodes = compute_episodes(fix)
        group = _group(d['jaccard'])
        trial_counts[group] += 1
        for ep in episodes:
            pos = ep['pos']
            if 0 <= pos < MAX_POS:
                pos_data[group][pos]['nfix'].append(ep['n_fixations'])
                pos_data[group][pos]['dur'].append(ep['duration_ms'])
                total_episodes += 1

    return pos_data, trial_counts, total_episodes


def plot(pos_data: dict, trial_counts: dict, total_episodes: int) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.2))

    positions = list(range(MAX_POS))

    print()
    print('=== Episode structure by position × difficulty ===')
    print(f'{"":>4s}' + ''.join(f'{g+" nfix":>14s}' for g in ('Easy', 'Medium', 'Hard')))
    for p in positions:
        line = f'{p:>4d}'
        for g in ('Easy', 'Medium', 'Hard'):
            vals = pos_data[g][p]['nfix']
            m = float(np.mean(vals)) if vals else float('nan')
            line += f'{m:>14.2f}'
        print(line)
    print()
    print(f'{"":>4s}' + ''.join(f'{g+" dur_ms":>14s}' for g in ('Easy', 'Medium', 'Hard')))
    for p in positions:
        line = f'{p:>4d}'
        for g in ('Easy', 'Medium', 'Hard'):
            vals = pos_data[g][p]['dur']
            m = float(np.mean(vals)) if vals else float('nan')
            line += f'{m:>14.0f}'
        print(line)

    # Per-position episode counts summed across tercile groups
    per_pos_n = [
        sum(len(pos_data[g][p]['nfix']) for g in ('Easy', 'Medium', 'Hard'))
        for p in positions
    ]

    # Drop positions whose total episode count is below this threshold from
    # the lines (still plot as hollow markers with a note). Position 9 in
    # particular has very few episodes because most trials click before
    # reaching the last result.
    SPARSE_CUTOFF = 100

    for ax, metric, ylabel in [
        (axes[0], 'nfix', 'Fixations per episode'),
        (axes[1], 'dur', 'Episode duration (ms)'),
    ]:
        for group in ('Easy', 'Medium', 'Hard'):
            color = TERCILE_COLORS[group]
            means_solid = []
            sems_solid = []
            means_sparse = []
            sems_sparse = []
            for p in positions:
                vals = pos_data[group][p][metric]
                if not vals:
                    means_solid.append(float('nan'))
                    sems_solid.append(0.0)
                    means_sparse.append(float('nan'))
                    sems_sparse.append(0.0)
                    continue
                m = float(np.mean(vals))
                s = float(np.std(vals) / max(len(vals) ** 0.5, 1))
                if per_pos_n[p] >= SPARSE_CUTOFF:
                    means_solid.append(m)
                    sems_solid.append(s)
                    means_sparse.append(float('nan'))
                    sems_sparse.append(0.0)
                else:
                    means_solid.append(float('nan'))
                    sems_solid.append(0.0)
                    means_sparse.append(m)
                    sems_sparse.append(s)
            n_trials = trial_counts[group]
            ax.errorbar(
                positions, means_solid, yerr=sems_solid,
                marker='o', color=color, capsize=3, linewidth=2.2,
                markersize=6, label=f'{group} (N = {n_trials:,} trials)',
            )
            # Sparse points plotted in the same color but hollow and
            # disconnected so the eye doesn't follow the spurious line
            ax.errorbar(
                positions, means_sparse, yerr=sems_sparse,
                marker='o', color=color, capsize=2,
                linestyle='none', markersize=6,
                markerfacecolor='white', markeredgewidth=1.8,
            )
        ax.set_xlabel('SERP result position (0 = top)')
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel + ' by position')
        ax.set_xticks(positions)
        # Annotate per-position n below the axis
        labels = [f'{p}\n(n={per_pos_n[p]:,})' for p in positions]
        ax.set_xticklabels(labels, fontsize=8.5)
        ax.legend(loc='best')
        # Mark sparse positions with a note
        sparse_positions = [p for p in positions if per_pos_n[p] < SPARSE_CUTOFF]
        if sparse_positions:
            ax.text(
                0.99, 0.02,
                f'hollow markers: n < {SPARSE_CUTOFF} episodes',
                transform=ax.transAxes, ha='right', va='bottom',
                fontsize=9, color=MUTED,
            )

    fig.suptitle(
        'Reading-episode structure by SERP position and difficulty tercile  '
        f'({total_episodes:,} episodes total; Jaccard difficulty split)',
        fontsize=12, y=1.03, color=INK,
    )
    fig.tight_layout()

    OUT_CIKM.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_CIKM, dpi=160, bbox_inches='tight')
    print(f'\nwrote {OUT_CIKM}')
    plt.close(fig)


def main() -> None:
    print('computing episodes by position × difficulty...')
    pos_data, trial_counts, total_episodes = compute()
    print(f'  {total_episodes:,} episodes across '
          f'{sum(trial_counts.values())} trials')
    plot(pos_data, trial_counts, total_episodes)


if __name__ == '__main__':
    main()
