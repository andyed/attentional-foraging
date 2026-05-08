"""Gaze-cursor coupling × cursor-saccade-orientation transfer test.

Hypothesis (Navalpakkam & Churchill CHI 2012; Huang/White/Buscher CHI 2012;
Liebling & Dumais CIKM 2014): a subset of users (~25-40%) shows tight
gaze-cursor coupling on SERPs. For that subset, cursor saccade-orientation
should mimic gaze saccade-orientation including the reading-shape signature
at clicked positions (saccade_orientation Test 2).

Procedure:
  1. Per-trial gaze-cursor coupling: time-align gaze fixations and cursor
     positions to a 100ms grid; compute median Euclidean distance per trial.
  2. Per-participant coupling: median across the participant's trials.
     Lower = tighter coupling.
  3. Tertile-split participants by coupling.
  4. Within each tertile, replicate the gaze Test 2 finding using:
     (a) gaze-derived saccade orientation (control / sanity check)
     (b) CURSOR-derived saccade orientation (the new test)
  5. Report frac_horizontal at clicked-pos vs non-clicked-pos within each tier.

If cursor signal recovers in the high-coupling tier and degrades in the
low-coupling tier, that's evidence for the WILD-bridge story: saccade-
orientation features are partially recoverable from cursor data when the
user-level coupling is high enough.

Output:
  scripts/output/gaze_cursor_coupling/summary.json
  scripts/output/gaze_cursor_coupling/coupling_panel.png
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
    get_trial_ids, load_fixations, load_mouse_events,
)

GAZE_SACC = ROOT / 'AdSERP/data/saccade-orientation-by-position.json'
CURSOR_SACC = ROOT / 'AdSERP/data/cursor-saccade-orientation-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'  # has click_pos
OUT_DIR = ROOT / 'scripts/output/gaze_cursor_coupling'
OUT_DIR.mkdir(parents=True, exist_ok=True)

GRID_MS = 100  # time-alignment grid

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
COLOR_GAZE = "#7c4dff"
COLOR_CURSOR = "#117733"


def trial_coupling(tid: str) -> tuple[float, int] | None:
    """Median Euclidean distance between time-aligned gaze and cursor (px).
    Lower = tighter coupling. Returns (median_dist, n_aligned_pts).
    """
    fixations = load_fixations(tid)
    if not fixations:
        return None
    events, _, _ = load_mouse_events(tid)
    moves = [(t, x, y) for (t, et, x, y) in events if et == 'mousemove']
    if not moves:
        return None
    fix_t = np.array([f['t'] for f in fixations], dtype=float)
    fix_x = np.array([f['x'] for f in fixations], dtype=float)
    fix_y = np.array([f['y'] for f in fixations], dtype=float)
    mv_t = np.array([m[0] for m in moves], dtype=float)
    mv_x = np.array([m[1] for m in moves], dtype=float)
    mv_y = np.array([m[2] for m in moves], dtype=float)

    # Build a common time grid spanning the overlap
    t_lo = max(fix_t.min(), mv_t.min())
    t_hi = min(fix_t.max(), mv_t.max())
    if t_hi - t_lo < 500:
        return None
    grid = np.arange(t_lo, t_hi, GRID_MS)
    if len(grid) < 5:
        return None

    # Step interpolation (use latest position before grid time)
    # Numpy searchsorted gives the insertion point
    fx_idx = np.searchsorted(fix_t, grid, side='right') - 1
    mv_idx = np.searchsorted(mv_t, grid, side='right') - 1
    fx_idx = np.clip(fx_idx, 0, len(fix_t) - 1)
    mv_idx = np.clip(mv_idx, 0, len(mv_t) - 1)

    dx = fix_x[fx_idx] - mv_x[mv_idx]
    dy = fix_y[fx_idx] - mv_y[mv_idx]
    dist = np.sqrt(dx * dx + dy * dy)
    return float(np.median(dist)), int(len(grid))


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials for coupling computation', file=sys.stderr)

    pid_to_couplings: dict[str, list[float]] = defaultdict(list)
    n_skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        res = trial_coupling(tid)
        if res is None:
            n_skipped += 1
            continue
        med_dist, n_pts = res
        pid = tid.split('-')[0]
        pid_to_couplings[pid].append(med_dist)

    # Per-participant: median trial-coupling
    pid_coupling: dict[str, float] = {
        pid: float(np.median(v)) for pid, v in pid_to_couplings.items() if v
    }
    pids = sorted(pid_coupling.keys(), key=lambda p: pid_coupling[p])
    coupling_vals = np.array([pid_coupling[p] for p in pids])
    print(f'\n  {len(pids)} participants with coupling estimates  '
          f'(skipped {n_skipped} trials)', file=sys.stderr)
    print(f'  coupling distance (px) — lower = tighter coupling:',
          file=sys.stderr)
    print(f'    median = {np.median(coupling_vals):.0f}  '
          f'q25 = {np.percentile(coupling_vals, 25):.0f}  '
          f'q75 = {np.percentile(coupling_vals, 75):.0f}', file=sys.stderr)

    # Tertile split
    t1, t2 = np.percentile(coupling_vals, [33.3, 66.7])
    tier_of = {}
    for pid in pids:
        v = pid_coupling[pid]
        tier_of[pid] = 'tight' if v < t1 else ('mid' if v < t2 else 'loose')
    n_tight = sum(1 for v in tier_of.values() if v == 'tight')
    n_mid = sum(1 for v in tier_of.values() if v == 'mid')
    n_loose = sum(1 for v in tier_of.values() if v == 'loose')
    print(f'  tertile cuts: tight<{t1:.0f}px, mid<{t2:.0f}px, loose≥{t2:.0f}px',
          file=sys.stderr)
    print(f'  participants per tier: tight={n_tight} mid={n_mid} loose={n_loose}',
          file=sys.stderr)

    # Load saccade-orientation features (gaze + cursor) per (trial, pos)
    print('[load] gaze + cursor saccade-orientation', file=sys.stderr)
    gaze = json.load(open(GAZE_SACC))
    cursor = json.load(open(CURSOR_SACC))
    rcache = json.load(open(RIPA2))

    # Build long table per (trial, pos) with both feature sources
    rows = []
    for tid, gblock in gaze.items():
        cblock = cursor.get(tid)
        if cblock is None:
            continue
        click_pos = rcache.get(tid, {}).get('click_pos')
        pid = tid.split('-')[0]
        tier = tier_of.get(pid)
        if tier is None:
            continue
        gby_pos = {p['pos']: p for p in gblock.get('positions', [])}
        cby_pos = {p['pos']: p for p in cblock.get('positions', [])}
        for pos in set(gby_pos.keys()) | set(cby_pos.keys()):
            g = gby_pos.get(pos)
            c = cby_pos.get(pos)
            row = {
                'tid': tid, 'pid': pid, 'pos': pos, 'tier': tier,
                'clicked': int(click_pos == pos) if click_pos is not None else 0,
                'gaze_frac_h':   g.get('frac_horizontal') if g else None,
                'gaze_n_sacc':   g.get('n_saccades') if g else 0,
                'cursor_frac_h': c.get('frac_horizontal') if c else None,
                'cursor_n_sacc': c.get('n_saccades') if c else 0,
            }
            rows.append(row)
    print(f'  {len(rows):,} (trial, pos) rows', file=sys.stderr)

    # ── Replicate Test 2 within each tier × source ────────────────────
    summary = {
        'n_pids_total': len(pids),
        'tertile_cuts_px': {'tight_max': float(t1), 'mid_max': float(t2)},
        'n_pids_per_tier': {'tight': n_tight, 'mid': n_mid, 'loose': n_loose},
        'tests': {},
    }
    print('\n=== Test 2 replication: clicked-pos frac_horizontal vs non-clicked, by tier and source ===')
    print(f'{"tier":>8s}  {"source":>7s}  {"med_clk":>10s}  {"med_not":>10s}  '
          f'{"Δ":>10s}  {"MW p":>10s}  {"N_clk":>7s}  {"N_not":>9s}')
    for tier in ('tight', 'mid', 'loose'):
        for source, key_h, key_n in [('gaze', 'gaze_frac_h', 'gaze_n_sacc'),
                                       ('cursor', 'cursor_frac_h', 'cursor_n_sacc')]:
            sub = [r for r in rows if r['tier'] == tier
                   and r[key_h] is not None and r[key_n] >= 3]
            clk = np.array([r[key_h] for r in sub if r['clicked'] == 1])
            nc  = np.array([r[key_h] for r in sub if r['clicked'] == 0])
            if len(clk) < 5 or len(nc) < 5:
                print(f'{tier:>8s}  {source:>7s}  insufficient n ({len(clk)}/{len(nc)})')
                continue
            u, p = mannwhitneyu(clk, nc, alternative='two-sided')
            delta = float(np.median(clk) - np.median(nc))
            print(f'{tier:>8s}  {source:>7s}  '
                  f'{np.median(clk):>10.4f}  {np.median(nc):>10.4f}  '
                  f'{delta:>+10.4f}  {p:>10.3g}  '
                  f'{len(clk):>7,}  {len(nc):>9,}')
            summary['tests'][f'{tier}_{source}'] = {
                'median_clicked': float(np.median(clk)),
                'median_notclicked': float(np.median(nc)),
                'delta': delta,
                'n_clicked': int(len(clk)),
                'n_notclicked': int(len(nc)),
                'mw_p': float(p),
            }

    out = OUT_DIR / 'summary.json'
    out.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {out.relative_to(ROOT)}', file=sys.stderr)

    # ── Visualization ─────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left: coupling distance distribution
    axes[0].hist(coupling_vals, bins=15, color='#888888', edgecolor='#444444',
                 alpha=0.7)
    axes[0].axvline(t1, color='#117733', ls='--', lw=1.2, label=f'tight/mid cut = {t1:.0f} px')
    axes[0].axvline(t2, color='#cc6677', ls='--', lw=1.2, label=f'mid/loose cut = {t2:.0f} px')
    axes[0].set_xlabel('per-participant median gaze-cursor distance (px, time-aligned)')
    axes[0].set_ylabel('# participants')
    axes[0].set_title(f"(A) Gaze-cursor coupling distribution\n"
                      f"N = {len(pids)} participants  —  lower = tighter coupling")
    axes[0].legend(loc='upper right', frameon=True, framealpha=0.92, edgecolor='#cccccc')
    axes[0].grid(True, axis='y', alpha=0.5)

    # Right: Δ frac_horizontal at clicked-pos by tier × source
    tiers = ['tight', 'mid', 'loose']
    gaze_deltas = []
    cursor_deltas = []
    gaze_ps = []
    cursor_ps = []
    for tier in tiers:
        g = summary['tests'].get(f'{tier}_gaze', {})
        c = summary['tests'].get(f'{tier}_cursor', {})
        gaze_deltas.append(g.get('delta', 0))
        cursor_deltas.append(c.get('delta', 0))
        gaze_ps.append(g.get('mw_p', 1))
        cursor_ps.append(c.get('mw_p', 1))

    x = np.arange(len(tiers))
    width = 0.38
    axes[1].bar(x - width/2, gaze_deltas, width, color=COLOR_GAZE, alpha=0.8,
                edgecolor='#222222', linewidth=0.6, label='gaze-derived')
    axes[1].bar(x + width/2, cursor_deltas, width, color=COLOR_CURSOR, alpha=0.8,
                edgecolor='#222222', linewidth=0.6, label='cursor-derived')
    axes[1].axhline(0, color='#222222', lw=0.6)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f'{t}\nn={[n_tight, n_mid, n_loose][i]} pids'
                             for i, t in enumerate(tiers)])
    axes[1].set_ylabel('Δ frac_horizontal (clicked − not clicked)')
    axes[1].set_title("(B) Saccade-orientation Test 2 replication by coupling tier\n"
                      "gaze-derived (control) vs cursor-derived (WILD-bridge candidate)")
    axes[1].legend(loc='upper right', frameon=True, framealpha=0.92, edgecolor='#cccccc')
    axes[1].grid(True, axis='y', alpha=0.5)

    # Significance markers
    for i, (gp, cp) in enumerate(zip(gaze_ps, cursor_ps)):
        for off, p, val in [(-width/2, gp, gaze_deltas[i]), (width/2, cp, cursor_deltas[i])]:
            if p < 0.001: mark = '***'
            elif p < 0.01: mark = '**'
            elif p < 0.05: mark = '*'
            else: mark = 'ns'
            axes[1].text(i + off, val + (0.001 if val >= 0 else -0.003),
                         mark, ha='center', va='bottom' if val >= 0 else 'top',
                         fontsize=10,
                         color='#222222' if mark != 'ns' else '#888888')

    fig.suptitle("Gaze-cursor coupling × cursor-saccade-orientation transfer  —  "
                 "the WILD-bridge test", y=0.995, fontsize=14)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / 'coupling_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'coupling_panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
