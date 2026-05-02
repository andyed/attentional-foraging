"""R1 wr/nr dissociation — paired-density visual.

Replaces make_r1_2x2_visual.py (failed muriel-critique on centroid collapse).

Two panels side-by-side, one per metric. Each panel shows the will-regress
vs no-regress distribution as overlaid KDE curves with vertical median
markers. Effect size (Cohen's d) annotated. The opposite signs of d across
the two panels are the dissociation.

Output: scripts/output/ripa2_meet_visuals/r1_dissociation.{pdf,png}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'scripts/output/ripa2_meet_visuals'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Default to bbox-organic (post-2026-05-01 cascade). Drop the -organic suffix
# on both filenames to render the legacy absolute version.
LFHF_PATH = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json'
RIPA2_PATH = ROOT / 'AdSERP/data/ripa2-by-position-organic.json'
EVR_PATH = ROOT / 'AdSERP' / 'data' / 'encoding-vs-retrieval.json'

with open(LFHF_PATH) as f:
    LFHF = json.load(f)
with open(RIPA2_PATH) as f:
    RIPA2 = json.load(f)
with open(EVR_PATH) as f:
    EVR = json.load(f)

# Per-(tid, pos) records: lfhf, ripa2, wr label
records = []
for tid, et in EVR.items():
    if tid not in LFHF or tid not in RIPA2:
        continue
    lfhf_t = {p['pos']: p['lfhf'] for p in LFHF[tid]['positions'] if p['lfhf'] is not None}
    ripa2_t = {p['pos']: p['ripa2'] for p in RIPA2[tid]['positions'] if p.get('ripa2') is not None}
    wr_by_pos = {fp['pos']: fp.get('will_regress', False) for fp in et.get('first_pass', [])}
    for pos in set(lfhf_t) & set(ripa2_t) & set(wr_by_pos):
        records.append((lfhf_t[pos], ripa2_t[pos], wr_by_pos[pos]))

lfhf  = np.array([r[0] for r in records])
ripa2 = np.array([r[1] for r in records])
wr    = np.array([r[2] for r in records], dtype=bool)
n_wr  = int(wr.sum())
n_nr  = int((~wr).sum())
print(f'records: {len(records):,}; wr={n_wr:,}; nr={n_nr:,}', file=sys.stderr)


def cohens_d(a, b):
    a, b = np.asarray(a), np.asarray(b)
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


# Stats per metric
lf_d = cohens_d(lfhf[wr], lfhf[~wr])
rp_d = cohens_d(ripa2[wr], ripa2[~wr])
lf_u, lf_p = stats.mannwhitneyu(lfhf[wr], lfhf[~wr], alternative='two-sided')
rp_u, rp_p = stats.mannwhitneyu(ripa2[wr], ripa2[~wr], alternative='two-sided')
print(f'LF/HF: d={lf_d:+.3f}, p={lf_p:.3e}; medians wr={np.median(lfhf[wr]):.2f} vs nr={np.median(lfhf[~wr]):.2f}', file=sys.stderr)
print(f'RIPA2: d={rp_d:+.3f}, p={rp_p:.3e}; medians wr={np.median(ripa2[wr]):.6f} vs nr={np.median(ripa2[~wr]):.6f}', file=sys.stderr)


# ── Plot ────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.size': 10,
    'font.family': 'serif',
    'font.serif': ['Georgia', 'Times New Roman', 'DejaVu Serif'],
    'pdf.fonttype': 42,
    'figure.facecolor': '#fafaf8',
    'axes.facecolor': '#fafaf8',
    'savefig.facecolor': '#fafaf8',
    'axes.edgecolor': '#222222',
    'axes.labelcolor': '#222222',
    'xtick.color': '#222222',
    'ytick.color': '#222222',
    'text.color': '#222222',
})

COLOR_WR = '#5b3eb8'   # purple
COLOR_NR = '#b8722c'   # amber
TEXT     = '#222222'   # 8:1 against #fafaf8

fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.0, 3.8))


def panel(ax, vals, group_mask, name, label_dir, d, pv, log_x=False, scale_label=None):
    wr_v = vals[group_mask]
    nr_v = vals[~group_mask]

    # Use percentile bounds tuned for the metric's tail
    lo, hi = np.percentile(vals, [3, 92])
    if log_x:
        lo = max(lo, np.percentile(vals[vals > 0], 1))
    grid = np.linspace(lo, hi, 240)
    if log_x:
        grid = np.geomspace(max(lo, 1e-9), hi, 240)

    kde_wr = stats.gaussian_kde(wr_v, bw_method=0.18)
    kde_nr = stats.gaussian_kde(nr_v, bw_method=0.18)
    ax.fill_between(grid, kde_wr(grid), color=COLOR_WR, alpha=0.28, lw=0)
    ax.fill_between(grid, kde_nr(grid), color=COLOR_NR, alpha=0.28, lw=0)
    ax.plot(grid, kde_wr(grid), color=COLOR_WR, lw=1.4)
    ax.plot(grid, kde_nr(grid), color=COLOR_NR, lw=1.4)

    med_wr = float(np.median(wr_v))
    med_nr = float(np.median(nr_v))
    ax.axvline(med_wr, color=COLOR_WR, lw=1.3, ls='-', alpha=0.95, ymax=0.72)
    ax.axvline(med_nr, color=COLOR_NR, lw=1.3, ls='-', alpha=0.95, ymax=0.72)

    # Legend block in upper-right corner — stacked, colored, no collision
    fmt = lambda v: f'{v:.2f}' if v >= 1 else f'{v:.4g}'
    legend_lines = [
        (COLOR_WR, f'later returned (median: {fmt(med_wr)})'),
        (COLOR_NR, f'never returned (median: {fmt(med_nr)})'),
    ]
    ax.set_ylim(0, ax.get_ylim()[1] * 1.05)
    handles = []
    for color, text in legend_lines:
        handles.append(plt.Line2D([0], [0], color=color, lw=2.4, label=text))
    ax.legend(handles=handles, loc='upper right', frameon=False, fontsize=9,
              handlelength=1.4, handletextpad=0.6, borderaxespad=0.4)

    if log_x:
        ax.set_xscale('log')
    if scale_label:
        ax.set_xlabel(f'{name} {scale_label}')
    else:
        ax.set_xlabel(name)
    ax.set_ylabel('density')
    ax.set_title(f'{label_dir}\n$d = {d:+.3f}$,  $p = {pv:.1e}$',
                 loc='left', fontsize=10, color=TEXT, pad=6,
                 linespacing=1.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='both', length=3, pad=2)


panel(axL, lfhf, wr, 'LF/HF',
      'later-returned items had HIGHER LF/HF  (lingered first time)',
      lf_d, lf_p, log_x=True)
panel(axR, ripa2, wr, 'RIPA2',
      'later-returned items had LOWER RIPA2  (processed shallowly)',
      rp_d, rp_p, log_x=False, scale_label=r'($\times 10^{-4}$)')

# Re-scale RIPA2 ticks to ×1e-4 for readability
from matplotlib.ticker import FixedLocator, FuncFormatter
xt = axR.get_xticks()
axR.xaxis.set_major_locator(FixedLocator(xt))
axR.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v * 1e4:.1f}'))

# Headline above panels
fig.suptitle(
    f'Same (trial, position) records, opposite metric directions  '
    f'(later returned $n={n_wr:,}$;  never returned $n={n_nr:,}$)',
    fontsize=11.5, color=TEXT, y=1.02, ha='center'
)

# Footer synthesis line
fig.text(0.5, -0.02,
         'Items the user returned to were lingered-on but processed shallowly the first time',
         ha='center', va='top', fontsize=9.5, color=TEXT, style='italic')

plt.tight_layout()
out_pdf = OUT_DIR / 'r1_dissociation.pdf'
out_png = OUT_DIR / 'r1_dissociation.png'
plt.savefig(out_pdf, bbox_inches='tight')
plt.savefig(out_png, dpi=200, bbox_inches='tight')
print(f'wrote {out_pdf}', file=sys.stderr)
