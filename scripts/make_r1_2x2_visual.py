"""R1 wr/nr dissociation, 2x2 cognitive-quadrant view.

Each quadrant of (LF/HF, RIPA2) corresponds to a cognitive interpretation;
the empirical centroids of will-regress and no-regress (trial, position)
records sit in opposite diagonal quadrants — the joint signature is the
finding.

Output: scripts/output/ripa2_meet_visuals/r1_2x2_dissociation.{pdf,png}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

# Build per-(tid, pos) records: median LF/HF, median RIPA2, wr label
records = []  # (tid, pos, lfhf_med, ripa2_med, wr)
for tid, et in EVR.items():
    if tid not in LFHF or tid not in RIPA2:
        continue
    lfhf_t = {p['pos']: p['lfhf'] for p in LFHF[tid]['positions'] if p['lfhf'] is not None}
    ripa2_t = {p['pos']: p['ripa2'] for p in RIPA2[tid]['positions'] if p.get('ripa2') is not None}

    # wr label per position from EVR's first_pass
    wr_by_pos = {}
    for fp in et.get('first_pass', []):
        wr_by_pos[fp['pos']] = fp.get('will_regress', False)

    for pos in set(lfhf_t) & set(ripa2_t) & set(wr_by_pos):
        records.append((tid, pos, lfhf_t[pos], ripa2_t[pos], wr_by_pos[pos]))

print(f'records: {len(records):,}', file=sys.stderr)

lfhf = np.array([r[2] for r in records])
ripa2 = np.array([r[3] for r in records])
wr = np.array([r[4] for r in records], dtype=bool)

# Centroids (medians)
wr_lfhf_med = float(np.median(lfhf[wr]))
nr_lfhf_med = float(np.median(lfhf[~wr]))
wr_ripa2_med = float(np.median(ripa2[wr]))
nr_ripa2_med = float(np.median(ripa2[~wr]))
print(f'wr (n={wr.sum():,}): LFHF={wr_lfhf_med:.2f}, RIPA2={wr_ripa2_med:.6f}', file=sys.stderr)
print(f'nr (n={(~wr).sum():,}): LFHF={nr_lfhf_med:.2f}, RIPA2={nr_ripa2_med:.6f}', file=sys.stderr)

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
})

COLOR_WR = '#5b3eb8'  # purple — will-regress
COLOR_NR = '#b8722c'  # amber  — no-regress

fig, ax = plt.subplots(figsize=(7.0, 5.6))

# Use percentile-based axis bounds to avoid outlier squashing
lf_lo, lf_hi = np.percentile(lfhf, [2, 98])
rp_lo, rp_hi = np.percentile(ripa2[ripa2 > 0], [2, 98])
ax.set_xlim(rp_lo, rp_hi)
ax.set_ylim(lf_lo, lf_hi)

# Quadrant dividers — split at the medians (the natural reference)
lf_mid = float(np.median(lfhf))
rp_mid = float(np.median(ripa2))
ax.axvline(rp_mid, color='#aaaaaa', lw=0.8, ls='--')
ax.axhline(lf_mid, color='#aaaaaa', lw=0.8, ls='--')

# Quadrant labels (cognitive interpretation)
def q_label(x, y, name, sub, color='#444444'):
    ax.text(x, y, name, ha='center', va='center', fontsize=10,
            color=color, fontweight='bold')
    ax.text(x, y - (lf_hi - lf_lo) * 0.07, sub, ha='center', va='center',
            fontsize=8.5, color=color, style='italic')

# Top-left (low RIPA2, high LF/HF) — slow + shallow → wr signature
q_label(rp_lo + (rp_mid - rp_lo) * 0.5, lf_mid + (lf_hi - lf_mid) * 0.6,
        'lingered but shallow', 'must return', color=COLOR_WR)
# Top-right (high RIPA2, high LF/HF) — deep + careful
q_label(rp_mid + (rp_hi - rp_mid) * 0.5, lf_mid + (lf_hi - lf_mid) * 0.6,
        'deep + careful', '(engaged on both scales)', color='#888888')
# Bottom-left (low RIPA2, low LF/HF) — skipped
q_label(rp_lo + (rp_mid - rp_lo) * 0.5, lf_lo + (lf_mid - lf_lo) * 0.4,
        'skipped', '(quick disengagement)', color='#888888')
# Bottom-right (high RIPA2, low LF/HF) — quick + sharp → nr signature
q_label(rp_mid + (rp_hi - rp_mid) * 0.5, lf_lo + (lf_mid - lf_lo) * 0.4,
        'quick + sharp', 'cleaner encoding', color=COLOR_NR)

# Empirical centroids
ax.scatter([wr_ripa2_med], [wr_lfhf_med], s=220, color=COLOR_WR,
           edgecolor='white', linewidth=1.2, zorder=4,
           label=f'will-regress centroid (n={wr.sum():,})')
ax.scatter([nr_ripa2_med], [nr_lfhf_med], s=220, color=COLOR_NR,
           edgecolor='white', linewidth=1.2, zorder=4,
           label=f'no-regress centroid (n={(~wr).sum():,})')

# Diagonal arrow connecting nr → wr to emphasise the dissociation
ax.annotate('', xy=(wr_ripa2_med, wr_lfhf_med),
            xytext=(nr_ripa2_med, nr_lfhf_med),
            arrowprops=dict(arrowstyle='-|>', color='#444444', lw=1.0,
                            mutation_scale=14, alpha=0.55,
                            shrinkA=10, shrinkB=10))

ax.set_xlabel('RIPA2 (per-fixation arousal amplitude)')
ax.set_ylabel('LF/HF (sustained autonomic engagement)')
ax.set_title('R1 — joint signature: same fixations, opposite metric directions',
             fontsize=11, loc='left', pad=8)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.legend(loc='lower left', frameon=False, fontsize=8.5)
ax.grid(False)

plt.tight_layout()
out_pdf = OUT_DIR / 'r1_2x2_dissociation.pdf'
out_png = OUT_DIR / 'r1_2x2_dissociation.png'
plt.savefig(out_pdf)
plt.savefig(out_png, dpi=200)
print(f'wrote {out_pdf}', file=sys.stderr)
print(f'wrote {out_png}', file=sys.stderr)
