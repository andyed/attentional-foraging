"""Disentangle cursor hover-before-click from reading-shape engagement.

The cursor saccade-orientation Test 2 finding (clicked-pos frac_horizontal
0.381 vs 0.333 at non-clicked, p ≈ 10⁻³⁶) and the gaze-cursor coupling
extension (cursor Δ = +0.23 to +0.41 across tertiles) might be dominated
by the user's "park cursor near click target before clicking" geometry —
where micro-movements at the target form short horizontal vectors by the
result-region's aspect ratio, not by reading-shape engagement.

This script trims the cursor signal at the clicked position to EXCLUDE
events within a configurable window (1000 ms by default) before the click,
then re-runs the same comparison. If clicked-pos frac_horizontal stays
elevated after trimming, the signal is reading-shape. If it collapses to
non-clicked level, the signal is hover-before-click geometry.

We also vary the trim window (500 ms, 1000 ms, 1500 ms, 2000 ms) to see
how the effect size decays as we strip more pre-click cursor activity.

Output:
  scripts/output/cursor_hover_vs_reading/summary.json
  scripts/output/cursor_hover_vs_reading/decay_panel.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_mouse_events,
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)

OUT_DIR = ROOT / 'scripts/output/cursor_hover_vs_reading'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Same orientation thresholds as the other cursor / gaze pipelines
HORIZ_DEG = 30.0
VERT_DEG = 60.0
MIN_MAGNITUDE_PX = 10.0
HORIZ_RAD = math.radians(HORIZ_DEG)
VERT_RAD = math.radians(VERT_DEG)

TRIM_WINDOWS_MS = [0, 500, 1000, 1500, 2000, 3000]

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 9, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_CLICKED = "#7c4dff"
COLOR_NOTCLICKED = "#888888"


def classify(dx: float, dy: float) -> str | None:
    mag = math.hypot(dx, dy)
    if mag < MIN_MAGNITUDE_PX:
        return None
    theta = math.atan2(abs(dy), abs(dx))
    if theta <= HORIZ_RAD:
        return 'h'
    if theta >= VERT_RAD:
        return 'v'
    return 'o'


def compute_per_pos_with_trim(events, click_t, target_pos, trim_ms,
                               tops, n_results) -> dict[int, dict]:
    """Compute per-position saccade-orientation features.

    For the clicked position only, exclude mousemove events occurring
    within trim_ms before click_t. Non-clicked positions are unaffected.
    """
    moves = [(t, x, y) for (t, et, x, y) in events if et == 'mousemove']
    if len(moves) < 2:
        return {}

    per_pos_classes: dict[int, list[str]] = defaultdict(list)
    for (t1, x1, y1), (t2, x2, y2) in zip(moves[:-1], moves[1:]):
        cls = classify(x2 - x1, y2 - y1)
        if cls is None:
            continue
        # Position assignment based on origin point's y
        p = assign_fixation_to_position(y1, tops, n_results)
        if p is None or not (0 <= p < n_results):
            continue
        # Trim only the clicked position
        if p == target_pos and (click_t - t1) < trim_ms:
            continue
        per_pos_classes[int(p)].append(cls)

    out: dict[int, dict] = {}
    for p, cls in per_pos_classes.items():
        n = len(cls)
        n_h = cls.count('h')
        n_v = cls.count('v')
        out[p] = {
            'n_saccades': n,
            'frac_horizontal': n_h / n if n else 0.0,
            'ratio_h_to_v': n_h / n_v if n_v else (float('inf') if n_h else 0.0),
        }
    return out


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials  ×  {len(TRIM_WINDOWS_MS)} trim windows',
          file=sys.stderr)

    # Per (trim_ms, trial, pos): collect frac_horizontal (when ≥3 saccades)
    rows_by_trim: dict[int, list[dict]] = {t: [] for t in TRIM_WINDOWS_MS}

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        events, _, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        click_t = float(clicks[-1][0])
        click_y = float(clicks[-1][2])

        n_results = count_results_html(tid) or 11
        doc_h, _, _ = get_trial_meta(tid)
        if doc_h is None:
            continue
        tops = result_band_tops(n_results, doc_h)
        target_pos = assign_fixation_to_position(click_y, tops, n_results)
        if target_pos is None:
            continue

        for trim_ms in TRIM_WINDOWS_MS:
            per_pos = compute_per_pos_with_trim(events, click_t, target_pos,
                                                  trim_ms, tops, n_results)
            for pos, feats in per_pos.items():
                if feats['n_saccades'] < 3:
                    continue
                rows_by_trim[trim_ms].append({
                    'tid': tid, 'pos': pos,
                    'clicked': int(pos == target_pos),
                    'frac_horizontal': feats['frac_horizontal'],
                    'n_saccades': feats['n_saccades'],
                })

    print(f'\n  rows per trim window: '
          f'{[len(rows_by_trim[t]) for t in TRIM_WINDOWS_MS]}', file=sys.stderr)

    summary = {'trim_windows_ms': TRIM_WINDOWS_MS, 'tests': []}

    print('\n=== Cursor frac_horizontal: clicked-pos vs non-clicked, by trim window ===')
    print(f'{"trim_ms":>8s}  {"med_clk":>10s}  {"med_not":>10s}  {"Δ":>10s}  '
          f'{"r_rb":>8s}  {"p":>10s}  {"N_clk":>7s}  {"N_not":>9s}')

    delta_by_trim: list[float] = []
    rrb_by_trim: list[float] = []
    n_clk_by_trim: list[int] = []
    p_by_trim: list[float] = []
    for trim_ms in TRIM_WINDOWS_MS:
        rows = rows_by_trim[trim_ms]
        clk = np.array([r['frac_horizontal'] for r in rows if r['clicked'] == 1])
        nc = np.array([r['frac_horizontal'] for r in rows if r['clicked'] == 0])
        if len(clk) < 5 or len(nc) < 5:
            continue
        u, p = mannwhitneyu(clk, nc, alternative='two-sided')
        delta = float(np.median(clk) - np.median(nc))
        rrb = 2 * u / (len(clk) * len(nc)) - 1
        delta_by_trim.append(delta)
        rrb_by_trim.append(rrb)
        n_clk_by_trim.append(len(clk))
        p_by_trim.append(p)
        print(f'{trim_ms:>8d}  {np.median(clk):>10.4f}  {np.median(nc):>10.4f}  '
              f'{delta:>+10.4f}  {rrb:>+8.3f}  {p:>10.3g}  '
              f'{len(clk):>7,}  {len(nc):>9,}')
        summary['tests'].append({
            'trim_ms': trim_ms,
            'median_clicked': float(np.median(clk)),
            'median_notclicked': float(np.median(nc)),
            'delta': delta,
            'rank_biserial_r': float(rrb),
            'mw_p': float(p),
            'n_clicked': int(len(clk)),
            'n_notclicked': int(len(nc)),
        })

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Visualization: decay of effect size with trim window ────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    # Left: effect size (Δ frac_h) decay
    axes[0].plot(TRIM_WINDOWS_MS[:len(delta_by_trim)], delta_by_trim,
                 marker='o', color=COLOR_CLICKED, lw=2.0, ms=10,
                 markeredgecolor='#222222', markeredgewidth=0.6)
    axes[0].axhline(0, color='#222222', lw=0.6)
    axes[0].set_xlabel('trim window (ms before click excluded from clicked-pos cursor data)')
    axes[0].set_ylabel('Δ median frac_horizontal\n(clicked-pos − non-clicked)')
    axes[0].set_title("(A) effect size decay  —  reading-shape vs hover-before-click\n"
                      "if Δ stays elevated, signal is reading-shape; "
                      "if Δ → 0, signal is hover-before-click geometry",
                      fontsize=11)
    axes[0].grid(True, alpha=0.5)
    for tm, d, n in zip(TRIM_WINDOWS_MS, delta_by_trim, n_clk_by_trim):
        axes[0].text(tm, d + 0.005, f'{d:+.3f}\nN_clk={n:,}', ha='center', va='bottom',
                     fontsize=8.5, color='#444444')
    axes[0].set_xticks(TRIM_WINDOWS_MS[:len(delta_by_trim)])

    # Right: rank-biserial r decay (effect size as ranked probability)
    axes[1].plot(TRIM_WINDOWS_MS[:len(rrb_by_trim)], rrb_by_trim,
                 marker='s', color=COLOR_CLICKED, lw=2.0, ms=10,
                 markeredgecolor='#222222', markeredgewidth=0.6)
    axes[1].axhline(0, color='#222222', lw=0.6)
    axes[1].set_xlabel('trim window (ms before click excluded)')
    axes[1].set_ylabel('rank-biserial $r$  (clicked vs non-clicked)')
    axes[1].set_title("(B) rank-biserial r decay  —  same data, distribution-robust",
                      fontsize=11)
    axes[1].grid(True, alpha=0.5)
    for tm, r in zip(TRIM_WINDOWS_MS, rrb_by_trim):
        axes[1].text(tm, r + 0.01, f'{r:+.3f}', ha='center', va='bottom',
                     fontsize=8.5, color='#444444')
    axes[1].set_xticks(TRIM_WINDOWS_MS[:len(rrb_by_trim)])

    fig.suptitle("Cursor saccade-orientation: hover-before-click vs reading-shape engagement",
                 y=0.995, fontsize=13)
    fig.text(0.5, 0.005,
             "trim_ms = 0 → original Test 2 finding (full cursor signal at clicked-pos).  "
             "Larger trim → more pre-click cursor activity excluded.\n"
             "Decay rate tells us what fraction of the cursor signal is hover-before-click "
             "geometry (collapses with trim) vs reading-shape engagement (survives trim).",
             ha='center', va='bottom', fontsize=9.5, color='#444444',
             style='italic',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#fdf8f2',
                       edgecolor='#dddddd', lw=0.6))
    plt.tight_layout(rect=(0, 0.10, 1, 0.96))
    out_png = OUT_DIR / 'decay_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'decay_panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
