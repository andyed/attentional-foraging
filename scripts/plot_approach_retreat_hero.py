"""Regenerate approach-retreat-hero.png (CIKM 2026 Figure 1).

Two-panel figure: real cursor trajectories for one commit (clicked) episode
and one retreat (rejected) episode. Both drawn in page-space against result
band outlines estimated from the trial metadata. Uses only post-fix data —
everything comes from cursor-approach-features-organic.json (bbox-organic
attribution, post-2026-05-01 cascade) and the raw mouse-movement CSVs,
which are coordinate-safe in their own right.

Exemplars (re-picked 2026-05-02 from cursor-approach-features-organic.json):
    Commit:  p014-b4-t2  pos=0  min_dist=6 px   retreat_dist=26 px
    Retreat: p015-b4-t4  pos=0  min_dist=12 px  retreat_dist=1,077 px

The legacy absolute-attribution exemplars (p015-b1-t5 pos=2 commit /
p014-b5-t2 pos=0 retreat) reattribute under bbox-organic — p015-b1-t5
no longer carries was_clicked=True at organic position 2, breaking the
"Commit (clicked)" caption. The new pair is the closest equivalent
under bbox-organic by (min_dist, retreat_dist) geometry.

Outputs:
    docs/drafts/cikm-2026/figures/approach-retreat-hero.png
    docs/drafts/figures/approach-retreat-hero.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    load_trial,
    result_bands,
)

OUT_CIKM = ROOT / 'docs/drafts/cikm-2026/figures/approach-retreat-hero.png'
OUT_MAIN = ROOT / 'docs/drafts/figures/approach-retreat-hero.png'

FEATURES_JSON = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'

# Exemplar trials — re-picked 2026-05-02 from cursor-approach-features-organic.json
# under bbox-organic AOI attribution. See module docstring for legacy retirement note.
COMMIT = dict(trial_id='p014-b4-t2', position=0)
RETREAT = dict(trial_id='p015-b4-t4', position=0)

# ── Style ──────────────────────────────────────────────────────────────────
BG = '#ffffff'
INK = '#0b1220'             # 18.72:1
MUTED = '#394150'           # 10.26:1
BAND_OUTLINE = '#394150'    # result band outline (dark slate on white)
TRAJ_COMMIT = '#0b5d1e'     # 8.08:1 green
TRAJ_RETREAT = '#7c2d12'    # 9.37:1 deep red/brown
MARK_ENTRY = '#1446a0'      # 8.70:1 deep blue
MARK_NADIR = '#4a1a00'      # 14.59:1 very dark brown (closest approach)
MARK_EXIT = '#6d3009'       # 10.11:1


def _lum(hx: str) -> float:
    r, g, b = (int(hx[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(fg: str, bg: str = BG) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


for _name, _hx in (('INK', INK), ('MUTED', MUTED), ('BAND_OUTLINE', BAND_OUTLINE),
                    ('TRAJ_COMMIT', TRAJ_COMMIT), ('TRAJ_RETREAT', TRAJ_RETREAT),
                    ('MARK_ENTRY', MARK_ENTRY), ('MARK_NADIR', MARK_NADIR),
                    ('MARK_EXIT', MARK_EXIT)):
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


def _load_feature_row(trial_id: str, position: int) -> dict:
    with open(FEATURES_JSON) as f:
        feats = json.load(f)
    for row in feats:
        if row['trial_id'] == trial_id and row['position'] == position:
            return row
    raise ValueError(f'No feature row for {trial_id} pos={position}')


def _collect_cursor_path(trial: dict, entry_t: float, exit_t: float):
    """Extract cursor (x, y) path within the approach episode window.

    Pre-pads ~750 ms of trailing context so the entry arrow has runway.
    Post-pads ~500 ms after exit so the retreat tail is visible.
    """
    pad_before_ms = 750
    pad_after_ms = 500
    xs, ys = [], []
    position_events = {'mousemove', 'mouseover', 'mouseout',
                       'mousedown', 'mouseup', 'click'}
    for t, evt, x, y in trial['events']:
        if evt not in position_events:
            continue
        if t < entry_t - pad_before_ms or t > exit_t + pad_after_ms:
            continue
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)


def _result_band_rectangles(doc_h: int, positions_to_draw: list[int],
                             n_results: int = 10):
    bands = result_bands(n_results, doc_h)
    out = []
    for p in positions_to_draw:
        if 0 <= p < len(bands):
            top, bot = bands[p]
            out.append((p, top, bot))
    return out


def _draw_panel(ax, trial_id: str, position: int, title: str, traj_color: str,
                 feature_row: dict, is_commit: bool) -> dict:
    trial = load_trial(trial_id)
    assert trial is not None, f'Failed to load {trial_id}'
    doc_h = trial['doc_height']

    # Cursor path over approach episode
    cx, cy = _collect_cursor_path(trial, feature_row['entry_t'],
                                   feature_row['exit_t'])
    if len(cx) < 2:
        raise RuntimeError(f'Not enough cursor samples in window for {trial_id}')

    bands = result_bands(10, doc_h)
    target_top, target_bot = bands[position]

    # Zoom to the actual cursor action plus the target band, with tight
    # padding. Do NOT span the whole page — these are local episodes.
    min_y = float(cy.min())
    max_y = float(cy.max())
    y_lo = min(min_y - 80, target_top - 100)
    y_hi = max(max_y + 80, target_bot + 100)

    # X window — prefer a SERP-like column (~700 px wide) centered on the
    # activity, so the reader sees the trajectory inside a result-column
    # context rather than a full-desktop sprawl.
    cx_lo = float(cx.min())
    cx_hi = float(cx.max())
    mid_x = (cx_lo + cx_hi) / 2
    target_width = max(cx_hi - cx_lo + 180, 720)
    x_lo = mid_x - target_width / 2
    x_hi = mid_x + target_width / 2

    # Draw result bands within the y window (shaded, with highlighted target)
    for p, top, bot in _result_band_rectangles(doc_h, list(range(10))):
        if bot < y_lo or top > y_hi:
            continue
        rect = patches.Rectangle(
            (x_lo + 10, top), x_hi - x_lo - 20, bot - top,
            linewidth=1.0, edgecolor=BAND_OUTLINE,
            facecolor='none', linestyle=':', alpha=0.55,
        )
        ax.add_patch(rect)
        ax.text(x_lo + 22, top + 18, f'r{p}', fontsize=9,
                color=MUTED, va='top')

    # Highlight the target result with a solid box
    rect_target = patches.Rectangle(
        (x_lo + 10, target_top), x_hi - x_lo - 20, target_bot - target_top,
        linewidth=1.8, edgecolor=INK,
        facecolor='#f5f5f5', alpha=0.85, zorder=1,
    )
    ax.add_patch(rect_target)
    label = 'clicked' if is_commit else 'target (not clicked)'
    ax.text(x_lo + 22, target_top + 20, f'result {position} — {label}',
            fontsize=9, color=INK, va='top', fontweight='semibold')

    # Cursor path as a polyline. Taper width down the tail so eye follows
    # the temporal direction.
    ax.plot(cx, cy, color=traj_color, linewidth=2.4, alpha=0.95,
            zorder=3, solid_capstyle='round', solid_joinstyle='round',
            label='cursor path')

    # Entry / nadir / exit markers
    entry_xy = (cx[0], cy[0])
    exit_xy = (cx[-1], cy[-1])
    # Nadir = sample where distance to target band center is minimized
    target_center_y = (target_top + target_bot) / 2
    dists = np.sqrt((cy - target_center_y) ** 2)
    nadir_idx = int(np.argmin(dists))
    nadir_xy = (cx[nadir_idx], cy[nadir_idx])

    ax.scatter(*entry_xy, s=80, color=MARK_ENTRY, zorder=5,
                edgecolors=INK, linewidths=0.8, label='entry')
    ax.scatter(*nadir_xy, s=110, color=MARK_NADIR, zorder=5,
                edgecolors=INK, linewidths=0.8, marker='D',
                label=f"closest approach ({feature_row['min_dist']:.0f} px)")
    ax.scatter(*exit_xy, s=80, color=MARK_EXIT, zorder=5,
                edgecolors=INK, linewidths=0.8, marker='X', label='exit')

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_hi, y_lo)  # invert: top of page at top of plot
    # Do not force equal aspect — the commit episode is ~200 px tall while
    # the retreat episode is ~1000 px tall. Equal aspect either squashes one
    # into a sliver or spreads it across the whole figure. Pick a deliberate
    # y-per-x ratio that keeps both panels readable.
    ax.set_aspect('auto')

    ax.set_xlabel('Page X (px)')
    ax.set_ylabel('Page Y (px, top = 0)')
    ax.set_title(
        f'{title}\n'
        f"{trial_id}  |  retreat distance: {feature_row['retreat_dist']:.0f} px  "
        f"|  dwell in proximity: {feature_row['dwell_in_proximity_ms']:.0f} ms",
        fontsize=11,
    )

    return dict(
        n_samples=int(len(cx)),
        min_dist_px=float(feature_row['min_dist']),
        retreat_dist_px=float(feature_row['retreat_dist']),
        dwell_in_proximity_ms=float(feature_row['dwell_in_proximity_ms']),
        total_dwell_ms=float(feature_row['total_dwell_ms']),
        was_clicked=bool(feature_row['was_clicked']),
    )


def main() -> None:
    commit_feat = _load_feature_row(COMMIT['trial_id'], COMMIT['position'])
    retreat_feat = _load_feature_row(RETREAT['trial_id'], RETREAT['position'])

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 6.2))

    summary_commit = _draw_panel(
        axes[0],
        COMMIT['trial_id'], COMMIT['position'],
        'Commit (clicked)',
        TRAJ_COMMIT, commit_feat, is_commit=True,
    )
    summary_retreat = _draw_panel(
        axes[1],
        RETREAT['trial_id'], RETREAT['position'],
        'Retreat (rejected)',
        TRAJ_RETREAT, retreat_feat, is_commit=False,
    )

    # Single shared legend at the bottom
    handles, labels = axes[0].get_legend_handles_labels()
    # Deduplicate by label preserving order
    seen = set()
    uniq = []
    for h, l in zip(handles, labels):
        key = l.split(' (')[0]
        if key in seen:
            continue
        seen.add(key)
        uniq.append((h, l))
    fig.legend(
        [h for h, _ in uniq],
        [l for _, l in uniq],
        loc='lower center', ncol=len(uniq), bbox_to_anchor=(0.5, -0.02),
        frameon=False, fontsize=10,
    )

    fig.suptitle(
        'Cursor trajectories: commit vs retreat',
        fontsize=14, color=INK, y=1.02,
    )
    fig.tight_layout()

    for out in (OUT_CIKM, OUT_MAIN):
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=160, bbox_inches='tight')
        print(f'wrote {out}')
    plt.close(fig)

    print()
    print('=== Exemplar summary ===')
    print(f'  COMMIT  {COMMIT["trial_id"]} pos={COMMIT["position"]}: {summary_commit}')
    print(f'  RETREAT {RETREAT["trial_id"]} pos={RETREAT["position"]}: {summary_retreat}')


if __name__ == '__main__':
    main()
