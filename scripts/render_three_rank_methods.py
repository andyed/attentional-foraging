"""Three-rank-methods comparison figure for the README and paper.

Produces a single multi-panel figure comparing absolute / organic /
organic_hybrid rank attribution across:
  Panel A: click share by position
  Panel B: time-to-click distribution per attribution
  Panel C: % regressed clicks per attribution (clicks where the user
           scrolled back to that position before clicking)

Output:
  scripts/output/figures/three_rank_methods_comparison.{png,pdf}
  scripts/output/figures/three_rank_methods_comparison_summary.json

Run:
  .venv/bin/python scripts/render_three_rank_methods.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    DATA_DIR,
    load_mouse_events,
    get_trial_meta,
)


FEAT_PATHS = {
    'absolute': ROOT / 'AdSERP/data/cursor-approach-features.json',
    'organic': ROOT / 'AdSERP/data/cursor-approach-features-organic.json',
    'organic_hybrid': ROOT / 'AdSERP/data/cursor-approach-features-organic-hybrid.json',
}

OUT_DIR = ROOT / 'scripts/output/figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)

INK = '#1a1a2e'
MUTED = '#5a5a6a'
COLORS = {
    'absolute':       '#888888',  # neutral grey — legacy
    'organic':        '#2ca25f',  # green — primary post-cascade
    'organic_hybrid': '#e08214',  # amber — deployment-aware variant
}
LABELS = {
    'absolute': 'absolute (legacy)',
    'organic': 'organic (post-cascade primary)',
    'organic_hybrid': 'organic_hybrid',
}

mpl.rcParams.update({
    'figure.dpi': 120,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.facecolor': 'white',
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 11,
    'axes.titlesize': 12.5,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'axes.edgecolor': INK,
    'axes.labelcolor': INK,
    'text.color': INK,
    'xtick.color': INK,
    'ytick.color': INK,
    'axes.spines.top': False,
    'axes.spines.right': False,
})


def load_records(attribution: str) -> list[dict]:
    return json.load(open(FEAT_PATHS[attribution]))


def click_share_by_position(records: list[dict], max_pos: int = 10):
    """Return per-position arrays: n records, n clicked, click rate (%)."""
    by_pos = defaultdict(lambda: {'n': 0, 'clicked': 0})
    for r in records:
        pos = r.get('position')
        if pos is None or pos < 0 or pos > max_pos:
            continue
        by_pos[pos]['n'] += 1
        if r.get('was_clicked'):
            by_pos[pos]['clicked'] += 1
    positions = sorted(by_pos.keys())
    n = np.array([by_pos[p]['n'] for p in positions])
    clicked = np.array([by_pos[p]['clicked'] for p in positions])
    rate_pp = np.where(n > 0, 100 * clicked / np.maximum(n, 1), np.nan)
    return positions, n, clicked, rate_pp


_TRIAL_T0_CACHE: dict[str, int] = {}


def _trial_t0(trial_id: str) -> int | None:
    """True trial start = earliest cursor event timestamp from raw mouse data.

    Cached because load_mouse_events is expensive.
    """
    if trial_id in _TRIAL_T0_CACHE:
        return _TRIAL_T0_CACHE[trial_id]
    try:
        events, _, _ = load_mouse_events(trial_id)
    except Exception:
        _TRIAL_T0_CACHE[trial_id] = None
        return None
    if not events:
        _TRIAL_T0_CACHE[trial_id] = None
        return None
    t0 = int(events[0][0])
    _TRIAL_T0_CACHE[trial_id] = t0
    return t0


def time_to_click(records: list[dict]) -> np.ndarray:
    """For clicked records, return time from true trial start to click in ms.

    True trial start comes from the raw mouse-event stream (first event).
    """
    times = []
    for r in records:
        if not r.get('was_clicked'):
            continue
        t0 = _trial_t0(r['trial_id'])
        if t0 is None:
            continue
        times.append(int(r['entry_t']) - t0)
    return np.array(times)


def regressed_clicks(records: list[dict]) -> tuple[int, int, float]:
    """% of clicked records where the user scrolled back to that position.

    Heuristic: per trial, sort recorded records by entry_t. A clicked record
    at position P is "regressed" if any later record (entry_t > clicked
    record's exit_t? — or entry_t > clicked entry_t) is at position < P
    (scrolled back upward) and then a later record is at P again. Simpler:
    use scroll trajectory from load_mouse_events to detect scroll direction
    reversals before the click event.

    For this figure we use a simpler proxy: a click is "regressed" if the
    clicked record's entry_t > some other record's entry_t at a later
    position number. I.e., a click happened on an earlier-rank result after
    later-rank results were also visited — implying the user scrolled back
    up to click.
    """
    by_trial = defaultdict(list)
    for r in records:
        by_trial[r['trial_id']].append(r)
    n_click = 0
    n_regressed = 0
    for tid, recs in by_trial.items():
        clicked_records = [r for r in recs if r.get('was_clicked')]
        if not clicked_records:
            continue
        for c in clicked_records:
            n_click += 1
            # Was this clicked position visited AFTER some later-rank position
            # had its first visit? That means: any other record with
            # position > c['position'] AND entry_t < c['entry_t'].
            for other in recs:
                if other is c:
                    continue
                if (other.get('position', -1) > c['position']
                        and other.get('entry_t', 1e18) < c['entry_t']):
                    n_regressed += 1
                    break
    rate_pp = 100 * n_regressed / n_click if n_click > 0 else 0.0
    return n_click, n_regressed, rate_pp


def main():
    print('[load] features per attribution', file=sys.stderr)
    data = {attr: load_records(attr) for attr in FEAT_PATHS}
    for attr, recs in data.items():
        print(f'  {attr}: {len(recs):,} records', file=sys.stderr)

    summary = {}
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6))

    # Panel A: click rate by position
    print('\n[A] click share by position', file=sys.stderr)
    ax = axes[0]
    width = 0.27
    max_pos = 10
    for i, attr in enumerate(['absolute', 'organic', 'organic_hybrid']):
        positions, n, clicked, rate_pp = click_share_by_position(data[attr], max_pos)
        x = np.array(positions, dtype=float) + (i - 1) * width
        ax.bar(x, rate_pp, width=width, label=LABELS[attr], color=COLORS[attr],
               edgecolor=INK, linewidth=0.4)
        summary.setdefault(attr, {})['click_share_by_position'] = {
            'positions': list(positions), 'n': n.tolist(),
            'clicked': clicked.tolist(), 'rate_pp': rate_pp.tolist(),
        }
    ax.set_xlabel('Position (rank in the result column)')
    ax.set_ylabel('Click rate (%)')
    ax.set_title('(a) Click share by position', loc='left', fontweight='bold')
    ax.legend(loc='upper right', framealpha=0.9, fontsize=9)
    ax.set_xticks(range(0, max_pos + 1))
    ax.grid(axis='y', alpha=0.25)

    # Panel B: time-to-click distribution
    print('\n[B] time-to-click distribution', file=sys.stderr)
    ax = axes[1]
    bins = np.linspace(0, 60_000, 31)  # 0–60s in 2s bins
    for attr in ['absolute', 'organic', 'organic_hybrid']:
        times_ms = time_to_click(data[attr])
        if len(times_ms) == 0:
            continue
        # Cap at 60 s for the plot; report median + N
        clipped = np.clip(times_ms, 0, 60_000)
        med = float(np.median(times_ms))
        n_clicks = len(times_ms)
        ax.hist(clipped / 1000, bins=bins / 1000, density=True,
                histtype='step', linewidth=2, color=COLORS[attr],
                label=f'{LABELS[attr]} (median {med/1000:.1f} s, N={n_clicks:,})')
        summary[attr]['time_to_click_ms'] = {
            'n_clicks': n_clicks,
            'median_ms': med,
            'p25_ms': float(np.percentile(times_ms, 25)),
            'p75_ms': float(np.percentile(times_ms, 75)),
            'mean_ms': float(np.mean(times_ms)),
        }
    ax.set_xlabel('Time from trial start to click (s)')
    ax.set_ylabel('Density')
    ax.set_title('(b) Time-to-click distribution', loc='left', fontweight='bold')
    ax.legend(loc='upper right', framealpha=0.9, fontsize=9)
    ax.grid(axis='y', alpha=0.25)

    # Panel C: % regressed clicks
    print('\n[C] % regressed clicks', file=sys.stderr)
    ax = axes[2]
    attrs_order = ['absolute', 'organic', 'organic_hybrid']
    rates = []
    labels = []
    for attr in attrs_order:
        n_click, n_regressed, rate_pp = regressed_clicks(data[attr])
        rates.append(rate_pp)
        labels.append(LABELS[attr])
        summary[attr]['regressed_clicks'] = {
            'n_clicks': n_click,
            'n_regressed': n_regressed,
            'rate_pp': rate_pp,
        }
    bars = ax.bar(range(len(attrs_order)), rates,
                  color=[COLORS[a] for a in attrs_order],
                  edgecolor=INK, linewidth=0.4)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f'{rate:.1f}%', ha='center', va='bottom', fontsize=10, color=INK)
    ax.set_xticks(range(len(attrs_order)))
    ax.set_xticklabels([LABELS[a].replace(' (', '\n(') for a in attrs_order], fontsize=9)
    ax.set_ylabel('% of clicks where user visited a later position first')
    ax.set_title('(c) Regressed clicks (scrolled back to click)', loc='left', fontweight='bold')
    ax.grid(axis='y', alpha=0.25)
    ax.set_ylim(0, max(rates) * 1.20 + 1)

    fig.suptitle('Three rank-attribution methods on AdSERP — click structure differs',
                 fontsize=13.5, color=INK, y=1.03)
    fig.text(0.5, -0.06,
             'Each panel reads click behavior under one of three rank-attribution '
             'flavors: absolute (h3 + ads pooled, legacy), organic (bbox-extracted '
             'organic results only, post-cascade primary), or organic_hybrid (organics + '
             'dd_top + native_ad in display order). The dd_top click-rate finding '
             '(17.1 % vs organic 14.6 %) appears in panel (a) at position 0 of the '
             'hybrid bars.',
             ha='center', fontsize=9.5, color=MUTED, style='italic', wrap=True)

    out_png = OUT_DIR / 'three_rank_methods_comparison.png'
    out_pdf = OUT_DIR / 'three_rank_methods_comparison.pdf'
    fig.savefig(out_png, dpi=200, facecolor='white', bbox_inches='tight')
    fig.savefig(out_pdf, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'\nwrote {out_png.relative_to(ROOT)}')
    print(f'wrote {out_pdf.relative_to(ROOT)}')

    out_json = OUT_DIR / 'three_rank_methods_comparison_summary.json'
    out_json.write_text(json.dumps(summary, indent=2))
    print(f'wrote {out_json.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
