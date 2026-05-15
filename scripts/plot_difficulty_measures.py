"""Regenerate difficulty-measures.png.

2 × 5 scatter grid: two embedding-based difficulty measures (relevance
spread, distinctive density) crossed with five foraging behavior DVs
(trial duration, positions visited count, page coverage %, scroll
regression count, click Y). Each cell reports a Spearman ρ and its
significance star.

Output:
    docs/drafts/cikm-2026/figures/difficulty-measures.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    get_trial_ids,
    load_trial,
    classify_fixations,
    result_bands,
)

OUT_CIKM = ROOT / 'docs/drafts/cikm-2026/figures/difficulty-measures.png'
DIFFICULTY_JSON = ROOT / 'AdSERP/data/serp-difficulty-measures.json'


# ── Style ──────────────────────────────────────────────────────────────────
BG = '#ffffff'
INK = '#0b1220'
MUTED = '#394150'
COLOR_SPREAD = '#0a4a9e'      # deep blue — 8.45:1
COLOR_DENSITY = '#5a1f00'     # deep brown — 12.88:1 (replaces purple for WCAG)
FIT_LINE = '#0b1220'


def _lum(hx: str) -> float:
    r, g, b = (int(hx[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg: str, bg: str = BG) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


for _name, _hx in (('INK', INK), ('MUTED', MUTED),
                    ('COLOR_SPREAD', COLOR_SPREAD),
                    ('COLOR_DENSITY', COLOR_DENSITY),
                    ('FIT_LINE', FIT_LINE)):
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
    'axes.linewidth': 1.0,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'legend.fontsize': 9,
    'legend.frameon': False,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
    'savefig.dpi': 150,
})


# ── Data ───────────────────────────────────────────────────────────────────

def scroll_regression_count(scrolls: list, threshold_px: int = 30) -> int:
    """Turning-point counter: regressions >= threshold px, de-duplicated."""
    if not scrolls:
        return 0
    ys = [s[1] for s in scrolls]
    count = 0
    state = 'flat'
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


def _trial_duration_s(trial: dict) -> float:
    """Duration from first mouse event to last click or last event (seconds)."""
    events = trial['events']
    if not events:
        return float('nan')
    t0 = events[0][0]
    if trial['clicks']:
        t1 = trial['clicks'][-1][0]
    else:
        t1 = events[-1][0]
    return max(0.0, (t1 - t0) / 1000.0)


def _page_coverage_pct(fixations_classified: list, doc_h: int) -> float:
    """Fraction of the document (%) visited by fixations.

    Simple: fraction of 100-px vertical bins that contain >=1 fixation.
    Uses page-space fixation y (FPOGY), which is canonical post-fix.
    """
    if not fixations_classified or doc_h <= 0:
        return float('nan')
    bin_size = 100
    n_bins = max(1, doc_h // bin_size)
    visited = set()
    for f in fixations_classified:
        b = int(f['page_y'] // bin_size)
        if 0 <= b < n_bins:
            visited.add(b)
    return 100.0 * len(visited) / n_bins


def _positions_visited(fixations_classified: list) -> int:
    """Number of distinct result positions (0–9) fixated at least once."""
    return len({f['position'] for f in fixations_classified if f['position'] >= 0})


def _click_y_or_nan(trial: dict) -> float:
    if not trial['clicks']:
        return float('nan')
    return float(trial['clicks'][-1][2])


def compute_rows() -> list[dict]:
    with open(DIFFICULTY_JSON) as f:
        diff = json.load(f)
    rows: list[dict] = []
    tids = get_trial_ids()
    for i, tid in enumerate(tids):
        if i % 250 == 0:
            print(f'  [{i}/{len(tids)}] {tid}', flush=True)
        d = diff.get(tid)
        if d is None:
            continue
        trial = load_trial(tid)
        if trial is None:
            continue
        fix = classify_fixations(trial, hwm_tolerance=50)
        rows.append({
            'trial_id': tid,
            'relevance_spread': d['relevance_spread'],
            'distinctive_density': d['distinctive_density'],
            'duration_s': _trial_duration_s(trial),
            'position_count': _positions_visited(fix),
            'coverage_pct': _page_coverage_pct(fix, trial['doc_height']),
            'regressions': scroll_regression_count(trial['scrolls'], 30),
            'click_y': _click_y_or_nan(trial),
        })
    return rows


# ── Plot ───────────────────────────────────────────────────────────────────

def plot(rows: list[dict]) -> None:
    spread = np.array([r['relevance_spread'] for r in rows], dtype=float)
    density = np.array([r['distinctive_density'] for r in rows], dtype=float)

    dv_defs: list[tuple[str, str, np.ndarray]] = [
        ('Duration (s)', 'duration_s',
            np.array([r['duration_s'] for r in rows], dtype=float)),
        ('Position count', 'position_count',
            np.array([r['position_count'] for r in rows], dtype=float)),
        ('Coverage (%)', 'coverage_pct',
            np.array([r['coverage_pct'] for r in rows], dtype=float)),
        ('Scroll regressions', 'regressions',
            np.array([r['regressions'] for r in rows], dtype=float)),
        ('Click Y (page px)', 'click_y',
            np.array([r['click_y'] for r in rows], dtype=float)),
    ]

    measures = [
        ('Relevance spread', spread, COLOR_SPREAD),
        ('Distinctive density', density, COLOR_DENSITY),
    ]

    fig, axes = plt.subplots(2, 5, figsize=(18.5, 7.2))

    print()
    print('=== Spearman ρ table (difficulty vs DV) ===')
    header = f'{"":>22s}' + ''.join(f'{d[0]:>20s}' for d in dv_defs)
    print(header)
    for row_idx, (m_name, m_arr, m_color) in enumerate(measures):
        line = f'{m_name:>22s}'
        for col_idx, (dv_name, _dv_key, dv_arr) in enumerate(dv_defs):
            ax = axes[row_idx, col_idx]
            mask = np.isfinite(dv_arr) & np.isfinite(m_arr)
            x = m_arr[mask]
            y = dv_arr[mask]

            ax.scatter(x, y, s=9, color=m_color, alpha=0.25,
                        rasterized=True, edgecolors='none')

            if len(x) >= 10:
                rho, p = stats.spearmanr(x, y)
                slope, intercept = np.polyfit(x, y, 1)
                x_line = np.linspace(x.min(), x.max(), 100)
                ax.plot(x_line, slope * x_line + intercept,
                        color=FIT_LINE, linewidth=1.5)
                star = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'
                ax.set_title(f'ρ = {rho:+.3f}  {star}\nn = {len(x):,}',
                             fontsize=10)
                line += f'  ρ={rho:+.3f} {star:>4s}'
            else:
                ax.set_title('n < 10')
                line += '   (n < 10)       '

            ax.set_xlabel(m_name)
            if col_idx == 0:
                ax.set_ylabel(dv_name)
            else:
                ax.set_ylabel(dv_name, fontsize=9)

            # Clamp extreme outliers for readability of Y scale
            q_lo, q_hi = np.quantile(y, [0.01, 0.99])
            if q_hi > q_lo:
                ax.set_ylim(q_lo - 0.05 * (q_hi - q_lo),
                            q_hi + 0.05 * (q_hi - q_lo))
        print(line)

    fig.suptitle(
        'SERP difficulty measures vs trial-level foraging behavior '
        f'(N = {len(rows):,} trials)',
        fontsize=13, y=1.02, color=INK,
    )
    fig.tight_layout()

    OUT_CIKM.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_CIKM, dpi=150, bbox_inches='tight')
    print(f'\nwrote {OUT_CIKM}')
    plt.close(fig)


def main() -> None:
    print('computing trial DVs and loading difficulty measures...')
    rows = compute_rows()
    print(f'  {len(rows)} trials with paired difficulty + DVs')
    plot(rows)


if __name__ == '__main__':
    main()
