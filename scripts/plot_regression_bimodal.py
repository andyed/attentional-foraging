"""Regenerate regression-bimodal.png (CIKM 2026 Figure 2) from post-fix data.

Two-panel histogram:
  (a) scroll regressions per trial (any descending scroll offset >= 30 px)
  (b) regressive fixation fraction per trial (HWM rule, 50 px tolerance)

Post-fix re-computation — numbers may differ from the paper's cached 69% /
22.8% values because fixation mapping and scroll timing both depend on the
coordinate fix applied 2026-04-12. Returns summary to stdout so the paper
caption can be reconciled.

Output:
    docs/drafts/cikm-2026/figures/regression-bimodal.png
"""
from __future__ import annotations

import sys
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

OUT_CIKM = ROOT / 'docs/drafts/cikm-2026/figures/regression-bimodal.png'

# ── Style ──────────────────────────────────────────────────────────────────
BG = '#ffffff'
INK = '#0b1220'       # near-black; >16:1 on white
MUTED = '#394150'     # dark slate; ~11:1 on white
BLUE = '#0b4a9e'      # deep blue; ~9.3:1 on white
ORANGE = '#7a3000'    # burnt orange; 9.33:1 on white
ACCENT_RED = '#9a1e1e'  # deep red for median marker; ~9:1 on white
ACCENT_BLUE = '#1446a0'  # deep blue for mean marker; ~10:1 on white


def _lum(hx: str) -> float:
    r, g, b = (int(hx[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg: str, bg: str = BG) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


def _enforce_contrast() -> None:
    for name, hx in (('INK', INK), ('MUTED', MUTED), ('BLUE', BLUE),
                     ('ORANGE', ORANGE), ('ACCENT_RED', ACCENT_RED),
                     ('ACCENT_BLUE', ACCENT_BLUE)):
        r = contrast(hx)
        assert r >= 8.0, f'{name} {hx} contrast {r:.2f}:1 below 8:1 floor'


_enforce_contrast()

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
    'axes.labelweight': 'regular',
    'axes.titleweight': 'semibold',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 1.1,
    'xtick.major.width': 1.1,
    'ytick.major.width': 1.1,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 12,
    'legend.fontsize': 10,
    'legend.frameon': False,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
    'savefig.dpi': 160,
})


# ── Compute ────────────────────────────────────────────────────────────────

def scroll_regression_count(scrolls: list, threshold_px: int = 30) -> int:
    """Number of discrete backward scroll excursions in a trial.

    Walks the scroll timeline and counts each time the trace makes a net
    downward excursion of at least threshold_px (i.e. scroll Y decreasing by
    >= threshold_px between successive local extrema). This is a simple
    turning-point counter — it matches the intuition of 'how many times did
    the user scroll back up' and produces the bimodal count distribution that
    the paper reports.
    """
    if not scrolls:
        return 0
    ys = [s[1] for s in scrolls]
    count = 0
    # Track local maxima and minima. A regression is a max -> min drop >=
    # threshold_px followed by a rise. Equivalently: each time the monotonic
    # state flips from 'ascending' to 'descending' after seeing >= threshold
    # of descent, count one.
    state = 'flat'  # 'asc', 'desc', 'flat'
    last_extreme = ys[0]
    for y in ys[1:]:
        dy = y - last_extreme
        if state == 'flat':
            if dy > 0:
                state = 'asc'
            elif dy < 0:
                state = 'desc'
            last_extreme = y
        elif state == 'asc':
            if y > last_extreme:
                last_extreme = y
            elif last_extreme - y >= threshold_px:
                # entered a regression
                count += 1
                state = 'desc'
                last_extreme = y
        elif state == 'desc':
            if y < last_extreme:
                last_extreme = y
            elif y - last_extreme >= threshold_px:
                state = 'asc'
                last_extreme = y
    return count


def compute() -> tuple[list[int], list[float]]:
    """Trial-level regression counts and within-trial regressive fractions.

    Filter: only trials with scroll activity (≥2 distinct scroll positions).
    Trials that never scrolled can't contain a scroll regression by
    construction, and padding panel (a) with their zeros would dominate the
    histogram and obscure the bimodal shape in the trials that *could* show
    regression.
    """
    reg_counts: list[int] = []
    reg_fracs: list[float] = []
    skipped_no_meta = 0
    skipped_no_scroll = 0
    tids = get_trial_ids()
    for i, tid in enumerate(tids):
        if i % 250 == 0:
            print(f'  [{i}/{len(tids)}] {tid}', flush=True)
        trial = load_trial(tid)
        if trial is None:
            skipped_no_meta += 1
            continue
        scrolls = trial['scrolls']
        distinct = {round(y) for _, y in scrolls}
        if len(distinct) < 2:
            skipped_no_scroll += 1
            continue
        reg_counts.append(scroll_regression_count(scrolls, threshold_px=30))
        # Regressive fixation fraction — HWM rule at 50 px
        fixations = classify_fixations(trial, hwm_tolerance=50)
        if not fixations:
            continue
        n_reg = sum(1 for f in fixations if not f['is_forward'])
        reg_fracs.append(100.0 * n_reg / len(fixations))
    print(f'  skipped {skipped_no_meta} trials (no metadata), '
          f'{skipped_no_scroll} trials (no scroll activity)')
    return reg_counts, reg_fracs


def plot(reg_counts: list[int], reg_fracs: list[float]) -> None:
    reg_counts_arr = np.array(reg_counts)
    reg_fracs_arr = np.array(reg_fracs)

    n_trials_a = len(reg_counts_arr)
    n_trials_b = len(reg_fracs_arr)
    pct_multi = 100.0 * np.mean(reg_counts_arr >= 1)
    pct_single = 100.0 - pct_multi
    median_frac = float(np.median(reg_fracs_arr))
    mean_frac = float(np.mean(reg_fracs_arr))

    print()
    print('=== Headline numbers ===')
    print(f'  (a) trials with N >= 1 scroll regression: {pct_multi:.1f}% '
          f'(single-pass: {pct_single:.1f}%)   N = {n_trials_a}')
    print(f'  (b) median regressive fixation fraction: {median_frac:.1f}%  '
          f'mean: {mean_frac:.1f}%   N = {n_trials_b}')
    print()

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))

    # Panel (a): scroll regressions per trial
    ax = axes[0]
    max_cnt = int(min(reg_counts_arr.max(), 13))
    bins = np.arange(-0.5, max_cnt + 1.5, 1.0)
    ax.hist(reg_counts_arr, bins=bins, color=BLUE,
            edgecolor=INK, linewidth=0.8)
    ax.set_title(f'(a) Trial-level prevalence (N = {n_trials_a:,})')
    ax.set_xlabel('Scroll regressions per trial (count)')
    ax.set_ylabel('Number of trials')
    ax.set_xticks(range(0, max_cnt + 1))

    # Annotate single-pass and multi-pass fractions
    ymax = ax.get_ylim()[1]
    ax.annotate(
        f'{pct_single:.0f}% single-pass\n(0 regressions)',
        xy=(0, (reg_counts_arr == 0).sum()), xytext=(2.2, ymax * 0.82),
        textcoords='data',
        color=INK, fontsize=10,
        arrowprops=dict(arrowstyle='-', color=MUTED, linewidth=1.0),
    )
    ax.annotate(
        f'{pct_multi:.0f}% multi-pass\n(≥1 regression)',
        xy=(4, (reg_counts_arr >= 4).sum()),
        xytext=(6.5, ymax * 0.55),
        textcoords='data',
        color=INK, fontsize=10,
        arrowprops=dict(arrowstyle='-', color=MUTED, linewidth=1.0),
    )

    # Panel (b): regressive fixation fraction
    ax = axes[1]
    bins = np.arange(0, 101, 2.5)
    ax.hist(reg_fracs_arr, bins=bins, color=ORANGE,
            edgecolor=INK, linewidth=0.8)
    ax.set_title(f'(b) Within-trial fraction (N = {n_trials_b:,})')
    ax.set_xlabel('Regressive fixation fraction (%)')
    ax.set_ylabel('Number of trials')
    ax.set_xlim(0, 100)
    ax.axvline(median_frac, color=ACCENT_RED, linewidth=2.0, linestyle='--',
               label=f'Median: {median_frac:.1f}%')
    ax.axvline(mean_frac, color=ACCENT_BLUE, linewidth=2.0, linestyle=':',
               label=f'Mean: {mean_frac:.1f}%')
    ax.legend(loc='upper right')

    fig.suptitle(
        'Scroll regressions and regressive-fixation fraction (HWM rule, 50 px tolerance)',
        fontsize=12, y=1.02, color=INK,
    )
    fig.tight_layout()

    OUT_CIKM.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_CIKM, dpi=160, bbox_inches='tight')
    print(f'wrote {OUT_CIKM}')
    plt.close(fig)


def main() -> None:
    print('computing trial-level regression counts and fractions...')
    reg_counts, reg_fracs = compute()
    plot(reg_counts, reg_fracs)


if __name__ == '__main__':
    main()
