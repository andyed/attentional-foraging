#!/usr/bin/env python3
"""Where C/W/L says the searcher stopped, and where they clicked.

Reads scripts/output/cwl_derived_vs_measured/gate_200px/summary.json (primary)
and draws two panels:

  (a) the stopping distribution two ways over ranks 1-10 ("10+" = 10 or
      deeper): the single-descent stop (deepest rank reached on the first
      pass, the framework's derived L) beside the observed clicked rank;
  (b) the per-trial gap, deepest rank examined minus clicked rank, as a
      histogram, with the share of trials whose click sits above the deepest
      rank examined.

The producer is gated on the shipped first-pass reach (1e-9) and on the
census's per-slot dwell (0 ms); this renderer reads its sidecar only.
Regime [LAB, AdSERP, typed]. Ranks are shown 1-based in the figure; the
sidecar is 0-based.

Output: scripts/output/figures/cwl_stop_vs_click.{png,svg,pdf} + .meta.json
Run:    .venv/bin/python scripts/render_cwl_stop_vs_click.py
"""
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
SRC = ROOT / 'scripts/output/cwl_derived_vs_measured/gate_200px/summary.json'
TRUNC = ROOT / 'scripts/output/cwl_derived_vs_measured/gate_200px_press_truncated/summary.json'
OUT = ROOT / 'scripts/output/figures'
NAME = 'cwl_stop_vs_click'

S = json.load(open(SRC))
L = S['L']
MAXP = S['maxp']

BG, TEXT = '#fafaf8', '#222222'
DERIVED, CLICK, GAP = '#9a948a', '#5b3eb8', '#b8722c'


def rel_lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# every readable glyph is TEXT on BG; bars carry no text of their own colour
assert contrast(BG, TEXT) >= 8, contrast(BG, TEXT)
plt.rcParams.update({'figure.facecolor': BG, 'axes.facecolor': BG, 'savefig.facecolor': BG, 'axes.edgecolor': TEXT,
                     'axes.labelcolor': TEXT, 'xtick.color': TEXT, 'ytick.color': TEXT, 'text.color': TEXT,
                     'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})

derived = np.array(L['L_derived_first_pass'])
click = np.array(L['L_measured_click'])
n = L['n_trials']
above = L['click_above_deepest_fixated']
gap = L['gap_ranks_deepest_minus_click']['histogram']
gap_k = sorted(int(k) for k in gap)
gap_v = np.array([gap[str(k)] for k in gap_k]) / n
pp = L['per_participant_share_click_above_deepest']
e_der, e_clk = L['expected_stop_rank_derived'] + 1, L['expected_stop_rank_click'] + 1   # 1-based
trunc_note = ''
if TRUNC.exists():
    T = json.load(open(TRUNC))['L']
    trunc_note = f"; {T['click_above_deepest_fixated']['share']:.0%} with fixations after the mouse press removed"

fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.2, 4.9), gridspec_kw={'width_ratios': [1.25, 1], 'wspace': 0.3})
fig.subplots_adjust(left=0.07, right=0.98, top=0.72, bottom=0.19)

# ---- (a) two stopping distributions ----------------------------------------
x = np.arange(MAXP)
w = 0.4
ax.bar(x - w / 2, derived, width=w, color=DERIVED, lw=0, label='single-descent stop: deepest rank reached on the first pass')
ax.bar(x + w / 2, click, width=w, color=CLICK, lw=0, label='observed stop: the clicked rank')
for i in range(MAXP):
    ax.text(x[i] - w / 2, derived[i] + 0.008, f'{derived[i]:.0%}' if derived[i] >= 0.02 else '', ha='center', va='bottom', fontsize=7.6)
    ax.text(x[i] + w / 2, click[i] + 0.008, f'{click[i]:.0%}' if click[i] >= 0.02 else '', ha='center', va='bottom', fontsize=7.6)
ax.set_xticks(x)
ax.set_xticklabels([str(i + 1) for i in range(MAXP - 1)] + [f'{MAXP}+'])
ax.set_xlabel('rank (typed display order)')
ax.set_ylabel('share of trials')
ax.set_ylim(0, max(derived.max(), click.max()) * 1.22)
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
ax.set_title(f'(a) Framework stop vs clicked rank  (n = {n:,} trials)', loc='left', fontsize=10.5, pad=8)
ax.legend(loc='upper center', frameon=False, fontsize=8.4, handlelength=1.2, bbox_to_anchor=(0.5, 0.98))
ax.text(0.70, 0.66, f'expected stop rank\nderived {e_der:.1f}   clicked {e_clk:.1f}',
        transform=ax.transAxes, ha='center', va='top', fontsize=8.4, linespacing=1.4)

# ---- (b) per-trial gap ------------------------------------------------------
bx.bar(gap_k, gap_v, width=0.8, color=[DERIVED if k == 0 else GAP for k in gap_k], lw=0)
for k, v in zip(gap_k, gap_v):
    if v >= 0.015:
        bx.text(k, v + 0.006, f'{v:.0%}', ha='center', va='bottom', fontsize=7.6)
bx.set_xlabel('deepest rank examined − clicked rank  (ranks)')
bx.set_ylabel('share of trials')
bx.set_xticks(gap_k)
bx.set_xticklabels([str(k) if k % 2 == 0 or k <= 1 else '' for k in gap_k])
bx.set_ylim(0, gap_v.max() * 1.7)
bx.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
bx.set_title('(b) Deepest rank examined minus clicked rank', loc='left', fontsize=10.5, pad=8)
bx.text(0.98, 0.95,
        f"click above the deepest rank examined:\n{above['share']:.1%} of trials  [{above['ci'][0]:.1%}, {above['ci'][1]:.1%}]\n"
        f"median gap {L['gap_ranks_deepest_minus_click']['median']:.0f} ranks\n"
        f"per participant: median {pp['median']:.0%}, IQR {pp['iqr'][0]:.0%}–{pp['iqr'][1]:.0%}, min {pp['min']:.0%}",
        transform=bx.transAxes, ha='right', va='top', fontsize=8.4, linespacing=1.45)
bx.text(0, -0.2, '0 = clicked the deepest result examined', transform=bx.get_xaxis_transform(), ha='left', va='top', fontsize=7.6)

fig.suptitle('The searcher does not stop where they stop looking', fontsize=13.5, x=0.07, ha='left', y=0.97)
fig.text(0.07, 0.905,
         'C/W/L derives the stopping distribution from one descent: stop = deepest rank reached. Every AdSERP trial ends in a click,\n'
         'so the observed stop is the clicked rank; the two are compared per trial. Trials with viewport opportunity known on every\n'
         f'slot; ranks bucketed at {MAXP} or deeper for both distributions. Fixations are whole-trial{trunc_note}. [LAB, AdSERP, typed]',
         fontsize=8.4, va='top', linespacing=1.45)

OUT.mkdir(parents=True, exist_ok=True)
for ext in ('png', 'svg', 'pdf'):
    fig.savefig(OUT / f'{NAME}.{ext}', dpi=170 if ext == 'png' else None)

try:
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'scripts/render_cwl_stop_vs_click.py'], cwd=ROOT, text=True).strip())
except Exception:
    sha, dirty = None, None
meta = {'schema_version': 1, 'run_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'script_path': str(ROOT / 'scripts/render_cwl_stop_vs_click.py'), 'script_sha': sha, 'script_dirty': dirty,
        'dataset_path': str(SRC.relative_to(ROOT)), 'dataset_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'producer_generated_utc': S['generated_utc'], 'producer_gate': S['gate'],
        'nb_k_ids': [], 'h_ids': [], 'figure_version': 'gate_200px-v1',
        'notes': f"Stopping distribution derived (deepest first-pass rank) vs clicked rank, and the per-trial gap. "
                 f"[LAB, AdSERP, typed]; n_trials={n}; click above deepest {above['share']:.3f} CI {above['ci']}; "
                 f"expected stop derived {L['expected_stop_rank_derived']:.2f} vs click {L['expected_stop_rank_click']:.2f} (0-based)."}
for ext in ('png', 'pdf'):
    json.dump(meta, open(OUT / f'{NAME}.{ext}.meta.json', 'w'), indent=2)
print('wrote', OUT / f'{NAME}.png')
