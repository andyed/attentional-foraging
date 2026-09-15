#!/usr/bin/env python3
"""Side by side: the idealized stutter-step trial and the population rates for
each of its stages.

Left: an authored single trial on an ad-topped page (78 % of AdSERP trials),
as vertical position over time, with six numbered stages. Right: for each
stage, the population distribution from the producers:
  1 survey composition            scripts/output/survey_above_fold/summary.json
  2-3 where a first visit ends    scripts/output/next_action_by_position/summary.json
  4 what a back excursion resolves to           (same)
  5 fixation before a first-entry move by amplitude
                                   docs/ablations/major_saccade_selection.md §2
                                   (inline analysis 2026-09-14; hard-coded here)
  6 landing offset, return vs first entry
                                   scripts/output/return_is_memory/summary_boundary_cm_24.json
Regime [LAB, AdSERP, typed]. Output: scripts/output/figures/idealized_vs_population.{png,svg,pdf}
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
OUT = ROOT / 'scripts/output/figures'
NA = json.load(open(ROOT / 'scripts/output/next_action_by_position/summary.json'))
SV = json.load(open(ROOT / 'scripts/output/survey_above_fold/summary.json'))
RM = json.load(open(ROOT / 'scripts/output/return_is_memory/summary_boundary_cm_24.json'))

BG, TEXT = '#fafaf8', '#222222'
GAZE, AMBER = '#5b3eb8', '#b8722c'
C = {'forward 1': '#5b3eb8', 'forward 2+': '#a897e0', 'back': '#b8722c', 'page top': '#9a948a', 'off results': '#9a948a',
     'trial ends': '#5c5c5c', 'ad': '#c9a56a', 'widget': '#d8d2c4', 'organic': '#5b3eb8',
     'returns to p': '#b8722c', 'new: p+1': '#5b3eb8', 'new: beyond p+1': '#a897e0', 'new: above p': '#e0b17a'}
BAND, ADBAND, QBAND = '#e9e6df', '#efe3cf', '#dcd8cf'


def rel_lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


assert (rel_lum(BG) + 0.05) / (rel_lum(TEXT) + 0.05) >= 8
plt.rcParams.update({'figure.facecolor': BG, 'axes.facecolor': BG, 'savefig.facecolor': BG, 'axes.edgecolor': TEXT,
                     'axes.labelcolor': TEXT, 'xtick.color': TEXT, 'ytick.color': TEXT, 'text.color': TEXT, 'font.size': 10})

# ------------------------------------------------------------ the idealized page
H = 72; G = 8
bands = [('query', 40, QBAND), ('ad 1', 120, ADBAND), ('ad 2', 200, ADBAND)] + [(f'result {k}', 280 + (k - 1) * (H + G), BAND) for k in range(1, 7)]
mid = {name: top + H / 2 for name, top, _ in bands}
PAGE_H = bands[-1][1] + H + 30
r = lambda k: mid[f'result {k}']
FIX = [  # (x, y, ms, stage)
    (200, mid['query'], 150, 1), (120, mid['ad 1'] - 6, 160, 1), (260, mid['ad 2'], 150, 1), (300, mid['ad 1'] + 8, 160, 1), (110, r(1) - 8, 180, 1),
    (230, r(1) - 8, 240, 2), (350, r(1) - 6, 230, 2), (160, r(1) + 16, 200, 2), (210, mid['query'] + 2, 170, 2),
    (120, r(2) - 8, 230, 3), (270, r(2) - 10, 250, 3), (170, r(2) + 14, 220, 3), (140, r(1) + 4, 220, 3),
    (150, r(2) - 8, 250, 4), (280, r(2) - 4, 240, 4), (130, r(3) - 8, 200, 4), (280, r(3) - 8, 150, 4),
    (140, r(6) - 8, 210, 5), (280, r(6) - 8, 230, 5), (190, r(6) + 16, 240, 5),
    (152, r(2) - 6, 260, 6), (232, r(2) - 6, 260, 6),
]
t = 0.0; fx = []
for i, (x, y, d, st) in enumerate(FIX):
    if i:
        t += 20 + 0.045 * float(np.hypot(x - FIX[i - 1][0], y - FIX[i - 1][1]))
    fx.append(dict(x=x, y=y, d=d, t0=t, t1=t + d, st=st)); t += d
T_END = t + 150
LW = lambda a: 0.9 if a < 100 else (1.6 if a < 300 else 2.8)

fig = plt.figure(figsize=(16, 9))
gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.15], wspace=0.14, left=0.05, right=0.985, top=0.86, bottom=0.07)
ax = fig.add_subplot(gs[0]); bx = fig.add_subplot(gs[1])

ax.set_ylim(PAGE_H, 0); ax.set_xlim(-0.05, T_END / 1000 + 0.05)
ax.set_xlabel('time on the page (s)'); ax.set_yticks([])
for name, top, col in bands:
    ax.axhspan(top, top + H, color=col, lw=0); ax.text(-0.08, top + H / 2, name, ha='right', va='center', fontsize=8.5, clip_on=False)
for i, f in enumerate(fx):
    ax.plot([f['t0'] / 1000, f['t1'] / 1000], [f['y'], f['y']], color=GAZE, lw=4.5, solid_capstyle='butt', zorder=5)
    if i:
        a = fx[i - 1]; amp = float(np.hypot(f['x'] - a['x'], f['y'] - a['y']))
        ax.plot([a['t1'] / 1000, f['t0'] / 1000], [a['y'], f['y']], color=GAZE, lw=LW(amp), zorder=4)
ax.plot(T_END / 1000 - 0.1, r(2), marker='o', ms=11, mfc='none', mec=TEXT, mew=1.6, zorder=9)
ax.plot(T_END / 1000 - 0.1, r(2), marker='+', ms=9, color=TEXT, mew=1.4, zorder=9)
ax.text(T_END / 1000 - 0.1, r(2) + 40, 'click', ha='center', va='top', fontsize=8.5)


def stage(n, tx, ty, label):
    ax.plot(tx, ty, marker='o', ms=15, mfc='#ffffff', mec=TEXT, mew=1.1, zorder=10, clip_on=False)
    ax.text(tx, ty, str(n), ha='center', va='center', fontsize=8.5, zorder=11, fontweight='bold')
    ax.text(tx, ty + 32, label, ha='center', va='top', fontsize=7.8, zorder=11, linespacing=1.15)


s = lambda k: (fx[k]['t0'] + fx[k]['t1']) / 2000
stage(1, s(2), mid['ad 2'] + 62, 'survey:\nthe top block')
stage(2, s(8) + 0.5, mid['query'] - 4, 'read 1, then\nre-read the query')
stage(3, s(12), r(1) - 62, 'bounce back\nto a seen result')
stage(4, s(15) - 0.45, r(3) + 70, 'return, then\nforward one')
stage(5, s(18), r(6) - 66, 'long jump\n(the minority)')
stage(6, s(21) - 0.5, r(2) + 118, 'memory-guided\nreturn, click')
ax.set_title('(a) Idealized trial on an ad-topped page', loc='left', fontsize=11.5, pad=10)

# ------------------------------------------------------------ the population, one row per stage
bx.set_xlim(0, 1); bx.set_ylim(0, 1); bx.axis('off')
bx.set_title('(b) The same stages in the population (AdSERP, 2,603 trials, 47 participants)', loc='left', fontsize=11.5, pad=10)
rows = []
sv = SV['composition_ad_top']
rows.append((1, f"survey: where the five fixations go on ad-topped pages (n {SV['ad_topped']['n']:,})",
             [('page top', sv['page top']['fix_share']), ('ad', sv['ad']['fix_share']), ('widget', sv['widget']['fix_share']), ('organic', sv['organic']['fix_share'])],
             f"first band fixated is the ad {SV['ad_topped']['P_first_band_is_ad']:.0%}; skip over it {SV['ad_topped']['P_skip_to_organic']:.0%}; "
             f"{SV['ad_topped']['ad_dwell_share_in_survey_median']:.0%} of the block's dwell is in the survey; {SV['ad_topped']['P_return_to_ad_after_survey_given_ever']:.0%} return to it"))
B = NA['B_first_visit_end']
def vrow(p):
    b = B[str(p)]
    return [('forward 1', b['forward 1']), ('forward 2+', b['forward 2+']), ('back', b['back']), ('page top', b['off results'])]
rows.append((2, f"first visit to result 1 ends (n {B['1']['n']:,})", vrow(1), f"median visit {B['1']['fix_per_visit_median']:.0f} fixations, {B['1']['ms_per_visit_median']:.0f} ms; 'page top' = the query box and header"))
for p in (2, 5, 10):
    b = B[str(p)]
    rows.append((3 if p == 2 else None, f"first visit to result {p} ends (n {b['n']:,})", vrow(p),
                 (f"the back move lands on an already-seen result {b['P_back_to_seen']:.0%}; median visit {b['fix_per_visit_median']:.0f} fixations, {b['ms_per_visit_median']:.0f} ms" if p == 2 else
                  f"back lands on a seen result {b['P_back_to_seen']:.0%}; P(this is the clicked result) {b['P_clicked']:.2f}")))
D = NA['D_after_back']
for p in (2, 10):
    d = D[str(p)]
    rows.append((4 if p == 2 else None, f"the back excursion from result {p} resolves to (n {d['n']:,})",
                 [('returns to p', d['returns to p']), ('new: p+1', d['new: p+1']), ('new: beyond p+1', d['new: beyond p+1']), ('new: above p', d['new: above p']), ('trial ends', d['trial ends'])], ''))

y = 0.965; DY = 0.075; BH = 0.028
for st, title, segs, note in rows:
    if st:
        bx.plot(0.012, y - 0.004, marker='o', ms=15, mfc='#ffffff', mec=TEXT, mew=1.1, clip_on=False)
        bx.text(0.012, y - 0.004, str(st), ha='center', va='center', fontsize=8.5, fontweight='bold')
    bx.text(0.04, y, title, ha='left', va='center', fontsize=9.2)
    x0 = 0.04; yb = y - 0.022
    small = []
    for name, v in segs:
        bx.barh(yb, v, left=x0, height=BH, color=C[name], align='center', lw=0)
        if v >= 0.085:
            bx.text(x0 + v / 2, yb - BH / 2 - 0.004, f'{name} {v:.0%}', ha='center', va='top', fontsize=7.8)
        elif v >= 0.005:
            small.append(f'{name} {v:.0%}')
        x0 += v
    if small:
        note = (note + '; ' if note else '') + 'also ' + ', '.join(small)
    if note:
        bx.text(0.04, yb - BH / 2 - 0.028, note, ha='left', va='top', fontsize=7.6, color=TEXT)
    y -= DY + (0.024 if note else 0.0)

# stage 5: fixation before a first-entry move, by amplitude (major_saccade_selection.md §2, inline 2026-09-14)
PRE = [('< 100 px', 200), ('100–300', 201), ('300–600', 180), ('> 600 px', 154)]
bx.plot(0.012, y - 0.004, marker='o', ms=15, mfc='#ffffff', mec=TEXT, mew=1.1, clip_on=False); bx.text(0.012, y - 0.004, '5', ha='center', va='center', fontsize=8.5, fontweight='bold')
bx.text(0.04, y, 'fixation before a first-entry move: median ms by saccade amplitude (15,130 moves)', ha='left', va='center', fontsize=9.2)
bx.text(0.04, y - 0.03 - BH / 2 - 0.028, 'shorter before long jumps in 35 of 43 participants (per-participant major − minor: −24 ms)', ha='left', va='top', fontsize=7.6)
for k, (lab, ms) in enumerate(PRE):
    x0 = 0.04 + k * 0.23
    bx.barh(y - 0.03, ms / 250 * 0.2, left=x0, height=BH, color=GAZE if ms >= 180 else AMBER, lw=0)
    bx.text(x0, y - 0.03 - BH / 2 - 0.004, f'{lab}: {ms} ms', ha='left', va='top', fontsize=7.8)
y -= DY + 0.044
# stage 6: landing offset return vs entry
lo = RM['paired_return_minus_entry']['landing_offset_px']; ll = RM['paired_return_minus_entry_long_returns']['landing_offset_px']
adj = RM['return_ranks_jumped_hist']['1'] / lo['n_rows']
bx.plot(0.012, y - 0.004, marker='o', ms=15, mfc='#ffffff', mec=TEXT, mew=1.1, clip_on=False); bx.text(0.012, y - 0.004, '6', ha='center', va='center', fontsize=8.5, fontweight='bold')
bx.text(0.04, y, f"returns: landing offset from the band centre, median px (n {lo['n_rows']:,} deferred rows)", ha='left', va='center', fontsize=9.2)
for k, (lab, v, col) in enumerate([('first entry, all', lo['entry_median'], GAZE), ('return, all', lo['return_median'], AMBER),
                                   ('first entry, ≥ 2 ranks', ll['entry_median'], GAZE), ('return, ≥ 2 ranks', ll['return_median'], AMBER)]):
    x0 = 0.04 + k * 0.23
    bx.barh(y - 0.03, v / 60 * 0.2, left=x0, height=BH, color=col, lw=0)
    bx.text(x0, y - 0.03 - BH / 2 - 0.004, f'{lab}: {v:.1f} px', ha='left', va='top', fontsize=7.8)
bx.text(0.04, y - 0.085, f'{adj:.0%} of returns come from the adjacent result; long returns land as precisely as first entries (diff +1.5 px, CI includes 0)\nwith no larger peripheral ramp before them: memory-guided',
        ha='left', va='top', fontsize=7.6)

fig.suptitle('The stutter step: one idealized trial, and the rate of each of its moves in the population', fontsize=13.5, x=0.05, ha='left', y=0.965)
fig.text(0.05, 0.915, 'Left is authored, not data; its parameters are AdSERP medians. Right reads the producers: survey_above_fold, next_action_by_position, return_is_memory, and the pre-saccadic durations in major_saccade_selection.md. [LAB, AdSERP, typed]',
         fontsize=8.6, va='top')
for ext in ('png', 'svg', 'pdf'):
    fig.savefig(OUT / f'idealized_vs_population.{ext}', dpi=170 if ext == 'png' else None)
print('wrote', OUT / 'idealized_vs_population.png')
