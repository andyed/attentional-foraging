"""Sanity-check content features against the saccade-orientation engagement
signature (frac_horizontal). Bhattacharya 2020's logic: reading-shaped
horizontal saccades = engaged-with-relevance behavior. If our content
features (TTR, query-overlap, embedding similarity) capture meaningful
"richness/relevance," they should predict frac_horizontal at the position.

If they don't survive position-residualization, the apparent correlation
is just position bleeding through.

Tests per content feature × frac_horizontal:
  - Pooled Spearman ρ
  - Partial Spearman | position (rank-residualized)
  - Per-position Spearman (within-position; controls position confound by
    construction)

Bonus: same tests against click outcome (binary). This is the cleanest
Pirolli selection test — content features × click probability — that the
RIPA2-rescue work deferred.

Output:
  scripts/output/content_features_sanity/summary.json
  scripts/output/content_features_sanity/correlation_table.png
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
from scipy.stats import spearmanr, rankdata, t as tdist, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'AdSERP/data/content-features-by-position.json'
SACCADE = ROOT / 'AdSERP/data/saccade-orientation-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'  # has click_pos
OUT_DIR = ROOT / 'scripts/output/content_features_sanity'
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONTENT_FEATURES = [
    'snippet_tokens', 'snippet_ttr', 'snippet_chars',
    'snippet_numerals', 'snippet_has_price',
    'title_tokens', 'title_chars', 'title_ttr',
    'q_overlap_count', 'q_overlap_jaccard', 'q_overlap_in_title',
    'q_text_cosine',
]

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}


def partial_rank_spearman(x: np.ndarray, y: np.ndarray, z: np.ndarray
                          ) -> tuple[float, float]:
    """Spearman ρ between x and y, partialling out z (also rank-transformed)."""
    rx = rankdata(x).astype(float)
    ry = rankdata(y).astype(float)
    rz = rankdata(z).astype(float)
    Z = np.column_stack([np.ones(len(x)), rz])
    bx, *_ = np.linalg.lstsq(Z, rx, rcond=None)
    by, *_ = np.linalg.lstsq(Z, ry, rcond=None)
    rx_r = rx - Z @ bx
    ry_r = ry - Z @ by
    if rx_r.std() == 0 or ry_r.std() == 0:
        return float('nan'), float('nan')
    rho = float(np.corrcoef(rx_r, ry_r)[0, 1])
    n = len(x)
    if abs(rho) >= 1 or n < 5:
        return rho, 0.0
    t = rho * math.sqrt((n - 3) / max(1 - rho ** 2, 1e-12))
    p = float(2 * (1 - tdist.cdf(abs(t), df=n - 3)))
    return rho, p


def main() -> None:
    print('[load] content + saccade + click data', file=sys.stderr)
    content = json.load(open(CONTENT))
    saccade = json.load(open(SACCADE))
    rcache = json.load(open(RIPA2))

    # Build long table: per-(trial, pos) join
    rows: list[dict] = []
    for tid, c in content.items():
        s = saccade.get(tid)
        click_pos = rcache.get(tid, {}).get('click_pos')
        if s is None:
            continue
        s_by_pos = {p['pos']: p for p in s.get('positions', [])}
        for cp in c['positions']:
            pos = cp['pos']
            sp = s_by_pos.get(pos)
            if sp is None:
                continue
            row = {'tid': tid, 'pos': pos,
                   'pid': tid.split('-')[0],
                   'frac_horizontal': sp.get('frac_horizontal', float('nan')),
                   'n_saccades': sp.get('n_saccades', 0),
                   'clicked': int(click_pos == pos) if click_pos is not None else 0}
            for k in CONTENT_FEATURES:
                row[k] = cp.get(k, float('nan'))
            rows.append(row)
    print(f'  joined: {len(rows):,} (trial, pos) rows', file=sys.stderr)

    # Filter to rows with ≥3 saccades (so frac_horizontal is meaningful)
    rows = [r for r in rows if r['n_saccades'] >= 3]
    print(f'  filtered to ≥3 saccades: {len(rows):,}', file=sys.stderr)

    summary: dict = {
        'n_rows': len(rows),
        'tests_vs_frac_horizontal': {},
        'tests_vs_click_outcome': {},
    }

    print('\n=== Sanity check: content features × frac_horizontal ===')
    print(f'{"feature":>22s}  {"pool ρ":>8s}  {"p":>8s}  {"partial|pos":>12s}  {"p":>8s}  {"n":>8s}')
    for feat in CONTENT_FEATURES:
        x = np.array([r[feat] for r in rows], dtype=float)
        y = np.array([r['frac_horizontal'] for r in rows], dtype=float)
        z = np.array([r['pos'] for r in rows], dtype=float)
        valid = ~(np.isnan(x) | np.isnan(y))
        if valid.sum() < 50 or np.std(x[valid]) == 0:
            continue
        rho_p, pv_p = spearmanr(x[valid], y[valid])
        rho_part, pv_part = partial_rank_spearman(x[valid], y[valid], z[valid])
        summary['tests_vs_frac_horizontal'][feat] = {
            'n': int(valid.sum()),
            'pooled_rho': float(rho_p), 'pooled_p': float(pv_p),
            'partial_pos_rho': float(rho_part), 'partial_pos_p': float(pv_part),
        }
        print(f'{feat:>22s}  {rho_p:>+8.4f}  {pv_p:>8.2g}  '
              f'{rho_part:>+12.4f}  {pv_part:>8.2g}  {valid.sum():>8,}')

    # ── Click outcome test (Pirolli's actual selection prediction) ──────
    print('\n=== Pirolli selection test: content features × click outcome ===')
    print(f'{"feature":>22s}  {"med_clicked":>12s}  {"med_not":>10s}  '
          f'{"MW p":>10s}  {"N_clk":>6s}  {"N_not":>8s}')
    clicked = [r for r in rows if r['clicked'] == 1]
    notclicked = [r for r in rows if r['clicked'] == 0]
    print(f'  (click sample N = {len(clicked):,};  non-click N = {len(notclicked):,})')
    for feat in CONTENT_FEATURES:
        c = np.array([r[feat] for r in clicked
                      if r[feat] == r[feat]], dtype=float)
        nc = np.array([r[feat] for r in notclicked
                       if r[feat] == r[feat]], dtype=float)
        if len(c) < 5 or len(nc) < 5 or (np.std(c) == 0 and np.std(nc) == 0):
            continue
        u, p = mannwhitneyu(c, nc, alternative='two-sided')
        summary['tests_vs_click_outcome'][feat] = {
            'median_clicked': float(np.median(c)),
            'median_notclicked': float(np.median(nc)),
            'n_clicked': len(c),
            'n_notclicked': len(nc),
            'u_two_sided_p': float(p),
        }
        print(f'{feat:>22s}  {np.median(c):>12.4f}  {np.median(nc):>10.4f}  '
              f'{p:>10.2g}  {len(c):>6,}  {len(nc):>8,}')

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Visualization: 2-panel correlation table ──────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))

    # Left panel: content × frac_horizontal (pooled and partial|pos)
    feats_used = list(summary['tests_vs_frac_horizontal'].keys())
    pool_rhos = [summary['tests_vs_frac_horizontal'][f]['pooled_rho'] for f in feats_used]
    part_rhos = [summary['tests_vs_frac_horizontal'][f]['partial_pos_rho'] for f in feats_used]
    pool_ps   = [summary['tests_vs_frac_horizontal'][f]['pooled_p']   for f in feats_used]
    part_ps   = [summary['tests_vs_frac_horizontal'][f]['partial_pos_p'] for f in feats_used]

    y_idx = np.arange(len(feats_used))
    axes[0].barh(y_idx - 0.2, pool_rhos, height=0.38, color='#7c4dff', alpha=0.5,
                 label='pooled ρ')
    axes[0].barh(y_idx + 0.2, part_rhos, height=0.38, color='#117733', alpha=0.7,
                 label='partial ρ | position')
    axes[0].set_yticks(y_idx)
    axes[0].set_yticklabels(feats_used, fontsize=9)
    axes[0].set_xlabel('Spearman ρ with frac_horizontal')
    axes[0].axvline(0, color='#222222', lw=0.6)
    axes[0].set_title("(A) content × frac_horizontal\n"
                      "(behavioral validator — does the feature predict reading-shape engagement?)")
    axes[0].legend(loc='lower right', frameon=True, framealpha=0.92, edgecolor='#cccccc')
    axes[0].grid(True, axis='x', alpha=0.5)
    # Mark ns features faintly
    for i, p in enumerate(part_ps):
        if p > 0.05:
            axes[0].text(0, y_idx[i] + 0.2, ' (ns | pos)', va='center',
                         fontsize=8, color='#888888', fontstyle='italic')

    # Right panel: click outcome — clicked vs notclicked medians
    clk_feats = list(summary['tests_vs_click_outcome'].keys())
    clk_dirs = []
    clk_ps = []
    for f in clk_feats:
        d = summary['tests_vs_click_outcome'][f]
        # log10 effect: relative difference normalized by overall median
        med_c = d['median_clicked']
        med_nc = d['median_notclicked']
        if abs(med_nc) > 1e-9:
            rel = (med_c - med_nc) / max(abs(med_nc), 1e-9)
        else:
            rel = med_c - med_nc
        clk_dirs.append(rel)
        clk_ps.append(d['u_two_sided_p'])

    y_idx = np.arange(len(clk_feats))
    colors = ['#cc6677' if d > 0 else '#117733' for d in clk_dirs]
    axes[1].barh(y_idx, clk_dirs, color=colors, alpha=0.6)
    axes[1].set_yticks(y_idx)
    axes[1].set_yticklabels(clk_feats, fontsize=9)
    axes[1].set_xlabel('relative diff (median_clicked − median_notclicked) / |median_notclicked|')
    axes[1].axvline(0, color='#222222', lw=0.6)
    axes[1].set_title("(B) Pirolli selection test:  content × click outcome\n"
                      "(do high-richness items get clicked more?)")
    axes[1].grid(True, axis='x', alpha=0.5)
    for i, p in enumerate(clk_ps):
        marker = '***' if p < 1e-10 else '**' if p < 1e-3 else '*' if p < 0.05 else 'ns'
        axes[1].text(clk_dirs[i] + (0.01 if clk_dirs[i] >= 0 else -0.01),
                     y_idx[i],
                     marker, va='center', fontsize=9,
                     color='#222222' if marker != 'ns' else '#888888',
                     ha='left' if clk_dirs[i] >= 0 else 'right')

    fig.suptitle("Content features — behavioral validation (saccade-orientation) + selection test (click outcome)",
                 y=0.995, fontsize=14)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / 'correlation_table.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'correlation_table.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
