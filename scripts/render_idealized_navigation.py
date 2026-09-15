#!/usr/bin/env python3
"""Idealized stutter-step navigation on a results page.

Not data: a hand-authored trace whose parameters are the medians reported in
docs/ablations/major_saccade_selection.md, return_is_memory.md and
periphery_navigates.md (AdSERP, [LAB, typed]). It shows three channels on one
trial — fixations (with minor vs major saccades), the cursor, and a roving
near-peripheral field — across the survey, the serial evaluate phase, a major
forward jump, and a memory-guided return that ends in a click.

Left: the page (x, y in screen px, 80 px result bands). Right: the same trace
as vertical position over time, sharing the y axis, so the forward/back jumps
read as a staircase. Output: scripts/output/figures/idealized_navigation.{png,svg,pdf}
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch

OUT = Path('/Users/andyed/Documents/dev/attentional-foraging/scripts/output/figures')

# ---------------------------------------------------------------- palette
BG = '#fafaf8'
TEXT = '#222222'          # 15:1 on BG
GAZE = '#5b3eb8'          # purple, lines and markers only (7.1:1 — never text)
CURSOR = '#b8722c'        # amber, lines only
BAND = '#e9e6df'
BAND_EDGE = '#c9c4b8'
PERI = '#5b3eb8'


def rel_lum(hexcol):
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


assert contrast(TEXT, BG) >= 8, contrast(TEXT, BG)

plt.rcParams.update({
    'figure.facecolor': BG, 'axes.facecolor': BG, 'savefig.facecolor': BG,
    'axes.edgecolor': TEXT, 'axes.labelcolor': TEXT, 'xtick.color': TEXT,
    'ytick.color': TEXT, 'text.color': TEXT, 'font.size': 10,
    'font.family': 'sans-serif',
})

# ---------------------------------------------------------------- the page
BAND_H, GAP, TOP, W = 72, 8, 40, 540
N_BANDS = 8
band_top = [TOP + i * (BAND_H + GAP) for i in range(N_BANDS)]
band_mid = [t + BAND_H / 2 for t in band_top]
PAGE_H = band_top[-1] + BAND_H + 40
PERI_PX = 200                      # the hard gate used throughout; ≈ 5° at 43 px/°

# ---------------------------------------------------------------- the trace
# (x, y, duration ms, phase). Durations are the reported medians: ~150–170 ms
# in the survey and before a long forward jump (ambient), ~200–260 ms while
# reading (focal). Saccade duration is idealized from amplitude.
FIX = [
    (120, band_mid[0] - 4, 160, 'survey'),
    (70,  band_mid[2],     150, 'survey'),
    (150, band_mid[4],     160, 'survey'),
    (130, band_mid[6],     150, 'survey'),
    (110, band_mid[1] - 8, 180, 'survey'),     # survey ends where reading starts
    (230, band_mid[1] - 8, 240, 'read 1'),
    (350, band_mid[1] - 6, 230, 'read 1'),
    (160, band_mid[1] + 16, 200, 'read 1'),
    (120, band_mid[2] - 8, 230, 'read 2'),
    (270, band_mid[2] - 10, 250, 'read 2'),
    (170, band_mid[2] + 16, 220, 'read 2'),
    (130, band_mid[3] - 8, 190, 'reject 3'),
    (270, band_mid[3] - 8, 150, 'reject 3'),   # short: ambient, before the long jump
    (140, band_mid[7] - 8, 210, 'read 8'),
    (280, band_mid[7] - 8, 230, 'read 8'),
    (190, band_mid[7] + 16, 240, 'read 8'),    # normal length before the return
    (152, band_mid[2] - 6, 260, 'return 2'),   # lands within the band, as the first entry did
    (232, band_mid[2] - 6, 260, 'return 2'),
    (345, band_mid[2] + 18, 230, 'return 2'),
]


def sacc_ms(amp):
    return 20 + 0.045 * amp      # ~25 ms for a word-length saccade, ~40 ms for 400 px


t = 0.0
fx = []
for i, (x, y, d, ph) in enumerate(FIX):
    if i:
        amp = float(np.hypot(x - FIX[i - 1][0], y - FIX[i - 1][1]))
        t += sacc_ms(amp)
    fx.append(dict(x=x, y=y, d=d, t0=t, t1=t + d, phase=ph))
    t += d
T_END = t + 120
T_CLICK = fx[-1]['t1']

# cursor keyframes (ms, x, y): parked, then holds the deferred candidate while
# the gaze is 400 px away, then converges onto it for the click
CUR = [
    (0, 500, 96),
    (fx[8]['t0'] - 200, 500, 96),
    (fx[9]['t1'], 470, band_mid[2] + 4),
    (fx[16]['t0'] + 100, 470, band_mid[2] + 4),
    (fx[17]['t1'], 300, band_mid[2] + 4),
    (T_END, 300, band_mid[2] + 4),
]
CUR = np.array(CUR, float)


def cursor_at(ts):
    return np.interp(ts, CUR[:, 0], CUR[:, 1]), np.interp(ts, CUR[:, 0], CUR[:, 2])


def amp_class(a):
    return 'minor' if a < 100 else ('next' if a < 300 else 'major')


LW = {'minor': 0.9, 'next': 1.6, 'major': 2.8}

# ---------------------------------------------------------------- figure
fig = plt.figure(figsize=(15.5, 8.6))
gs = fig.add_gridspec(1, 2, width_ratios=[0.95, 1.85], wspace=0.05, left=0.045, right=0.985, top=0.83, bottom=0.10)
axp = fig.add_subplot(gs[0])
axt = fig.add_subplot(gs[1], sharey=axp)

# --- left: the page
axp.set_xlim(-30, W + 150)
axp.set_ylim(PAGE_H, -34)
axp.set_aspect('equal')
axp.set_xlabel('page x (px)')
axp.set_ylabel('page y (px)')
axp.tick_params(labelsize=8.5)
for i, top in enumerate(band_top):
    axp.add_patch(Rectangle((0, top), W, BAND_H, facecolor=BAND, edgecolor=BAND_EDGE, lw=0.8, zorder=1))
    # title bar and two snippet lines (placeholders, not text)
    axp.add_patch(Rectangle((14, top + 12), 300 - 18 * (i % 3), 11, facecolor='#b9b3a5', lw=0, zorder=2))
    axp.add_patch(Rectangle((14, top + 34), 480, 6, facecolor='#cfcabf', lw=0, zorder=2))
    axp.add_patch(Rectangle((14, top + 48), 400 + 30 * (i % 2), 6, facecolor='#cfcabf', lw=0, zorder=2))
    axp.text(-8, top + BAND_H / 2, f'{i + 1}', ha='right', va='center', fontsize=9.5, color=TEXT)

# peripheral halos at three moments: a survey fixation, the fixation before the
# long forward jump, the return landing
for k, lab in ((2, 'survey'), (12, 'before the\nlong jump'), (16, 'return')):
    f = fx[k]
    axp.add_patch(Circle((f['x'], f['y']), PERI_PX, facecolor=PERI, alpha=0.06, edgecolor=PERI, lw=0.9, ls=(0, (3, 3)), zorder=3))

# cursor path
cts = np.linspace(0, T_END, 400)
cx, cy = cursor_at(cts)
axp.plot(cx, cy, color=CURSOR, lw=1.8, ls=(0, (4, 2)), zorder=4)
for tk, xk, yk in CUR[[0, 2, 4]]:
    axp.plot(xk, yk, marker='o', ms=4.5, color=CURSOR, zorder=5)

# saccades
for i in range(1, len(fx)):
    a, b = fx[i - 1], fx[i]
    amp = float(np.hypot(b['x'] - a['x'], b['y'] - a['y']))
    axp.annotate('', xy=(b['x'], b['y']), xytext=(a['x'], a['y']),
                 arrowprops=dict(arrowstyle='-|>', color=GAZE, lw=LW[amp_class(amp)], shrinkA=4, shrinkB=4,
                                 mutation_scale=9 + 4 * (amp_class(amp) == 'major'), alpha=0.95), zorder=6)
# fixations: radius scales with duration
for i, f in enumerate(fx):
    r = f['d'] / 18
    axp.add_patch(Circle((f['x'], f['y']), r, facecolor='#ffffff', edgecolor=GAZE, lw=1.4, zorder=7))
    axp.text(f['x'], f['y'], f'{i + 1}', ha='center', va='center', fontsize=6.8, color=TEXT, zorder=8)
# click
axp.plot(CUR[4, 1], CUR[4, 2], marker='o', ms=11, mfc='none', mec=TEXT, mew=1.6, zorder=9)
axp.plot(CUR[4, 1], CUR[4, 2], marker='+', ms=9, color=TEXT, mew=1.4, zorder=9)

axp.set_title('(a) On the page', loc='left', fontsize=11, pad=8)
axp.text(W + 12, CUR[0, 2], 'cursor\nparked', ha='left', va='center', fontsize=8, color=TEXT)
axp.text(W + 12, CUR[2, 2], 'cursor holds\nthe candidate', ha='left', va='center', fontsize=8, color=TEXT)
axp.text(W + 12, fx[2]['y'], f'near periphery\n±{PERI_PX} px ≈ 5°', ha='left', va='center', fontsize=8, color=TEXT)
axp.text(W + 12, PAGE_H - 52, 'circle radius\n= duration', ha='left', va='center', fontsize=8, color=TEXT)

# --- right: position over time
XMAX = T_END / 1000 + 1.55
axt.set_xlim(-0.05, XMAX)
axt.set_xlabel('time on the page (s)')
axt.tick_params(labelleft=False, labelsize=8.5)
axt.set_title('(b) The same trace as a staircase: vertical position over time', loc='left', fontsize=11, pad=16)
for i, top in enumerate(band_top):
    axt.axhspan(top, top + BAND_H, color=BAND, lw=0, zorder=1)
    axt.text(XMAX + 0.04, top + BAND_H / 2, f'{i + 1}', ha='left', va='center', fontsize=9.5, color=TEXT, clip_on=False)

# gaze y as a function of time (hold during fixations, linear during saccades)
tg = np.linspace(0, T_END, 1600)
gy = np.empty_like(tg)
for j, tt in enumerate(tg):
    for i, f in enumerate(fx):
        if f['t0'] <= tt <= f['t1']:
            gy[j] = f['y']; break
        if i + 1 < len(fx) and f['t1'] < tt < fx[i + 1]['t0']:
            gy[j] = np.interp(tt, [f['t1'], fx[i + 1]['t0']], [f['y'], fx[i + 1]['y']]); break
    else:
        gy[j] = fx[-1]['y']
# roving periphery: a ribbon of ±200 px that travels with the fovea
axt.fill_between(tg / 1000, gy - PERI_PX, gy + PERI_PX, color=PERI, alpha=0.09, lw=0, zorder=2)
axt.plot(tg / 1000, gy - PERI_PX, color=PERI, lw=0.6, ls=(0, (3, 3)), alpha=0.6, zorder=2)
axt.plot(tg / 1000, gy + PERI_PX, color=PERI, lw=0.6, ls=(0, (3, 3)), alpha=0.6, zorder=2)

# cursor
cts = np.linspace(0, T_END, 600)
_, cy = cursor_at(cts)
axt.plot(cts / 1000, cy, color=CURSOR, lw=1.8, ls=(0, (4, 2)), zorder=4)

# fixations as bars, saccades as connectors weighted by amplitude
for i, f in enumerate(fx):
    axt.plot([f['t0'] / 1000, f['t1'] / 1000], [f['y'], f['y']], color=GAZE, lw=4.5, solid_capstyle='butt', zorder=6)
    if i:
        a = fx[i - 1]
        amp = float(np.hypot(f['x'] - a['x'], f['y'] - a['y']))
        axt.plot([a['t1'] / 1000, f['t0'] / 1000], [a['y'], f['y']], color=GAZE, lw=LW[amp_class(amp)], zorder=5)
axt.plot(T_CLICK / 1000, CUR[4, 2], marker='o', ms=11, mfc='none', mec=TEXT, mew=1.6, zorder=9)
axt.plot(T_CLICK / 1000, CUR[4, 2], marker='+', ms=9, color=TEXT, mew=1.4, zorder=9)

# phase brackets along the top
phases = [('survey', 0, 4), ('read 1', 5, 7), ('read 2', 8, 10), ('reject 3', 11, 12), ('read 8', 13, 15), ('return to 2', 16, 18)]
ybr = -14
for lab, i0, i1 in phases:
    x0, x1 = fx[i0]['t0'] / 1000, fx[i1]['t1'] / 1000
    axt.plot([x0, x1], [ybr, ybr], color=TEXT, lw=0.9, clip_on=False)
    axt.plot([x0, x0], [ybr - 5, ybr + 5], color=TEXT, lw=0.9, clip_on=False)
    axt.plot([x1, x1], [ybr - 5, ybr + 5], color=TEXT, lw=0.9, clip_on=False)
    axt.text((x0 + x1) / 2, ybr - 6, lab, ha='center', va='bottom', fontsize=8.5, color=TEXT, clip_on=False)

# annotations
ann = dict(fontsize=8.6, color=TEXT, ha='left', va='center',
           arrowprops=dict(arrowstyle='-', color=TEXT, lw=0.7, shrinkA=0, shrinkB=3))
axt.annotate('ambient survey: five short fixations,\nlong saccades, ~1.5 s; seeds a\nproximity map of five neighbourhoods',
             xy=(fx[2]['t0'] / 1000 + 0.08, fx[2]['y']), xytext=(fx[3]['t1'] / 1000 + 0.35, band_mid[4] + 30), **ann)
axt.annotate('focal reading: 200–250 ms fixations,\nminor saccades within a result,\none-result steps between',
             xy=(fx[6]['t1'] / 1000, fx[6]['y']), xytext=(fx[5]['t0'] / 1000 - 0.1, band_top[0] + 6), **ann)
axt.annotate('before a long forward jump the\nfixation is short (~150 ms): ambient\nmode. Its target is a result the eyes\nwere recently near, not one weighed\nin the periphery',
             xy=(fx[12]['t0'] / 1000 + 0.07, fx[12]['y']), xytext=(fx[8]['t0'] / 1000 - 0.32, band_top[6] + 30), **ann)
axt.annotate('the return is memory-guided:\na normal fixation before it,\none ballistic saccade,\nlanding at first-entry\nprecision',
             xy=(fx[16]['t0'] / 1000 - 0.02, band_mid[4]), xytext=(T_END / 1000 + 0.18, band_top[3] + 12), **ann)
axt.annotate('near-peripheral field:\n±200 px (≈ 5°) around the\nfovea; samples neighbours,\nguides the next fixation,\njudges nothing',
             xy=(fx[18]['t0'] / 1000 + 0.05, fx[18]['y'] + PERI_PX), xytext=(T_END / 1000 + 0.18, band_top[6] + 4), **ann)
axt.annotate('cursor: parked, then holds\nthe deferred candidate while\nthe gaze is 400 px away;\nconverges for the click',
             xy=(fx[14]['t0'] / 1000, CUR[2, 2] - 2), xytext=(fx[11]['t0'] / 1000 + 0.02, band_top[0] + 8), **ann)
axt.text(T_CLICK / 1000 + 0.09, CUR[4, 2], 'click', fontsize=8.6, color=TEXT, ha='left', va='center')

# legend (hand-built so the symbols match)
from matplotlib.lines import Line2D
handles = [
    Line2D([0], [0], color=GAZE, lw=4.5, label='fixation (bar length = duration; circle radius on the page)'),
    Line2D([0], [0], color=GAZE, lw=LW['minor'], label='minor saccade, < 100 px (within a result)'),
    Line2D([0], [0], color=GAZE, lw=LW['next'], label='100–300 px (to the next result)'),
    Line2D([0], [0], color=GAZE, lw=LW['major'], label='major saccade, ≥ 300 px (forward jump or return)'),
    Line2D([0], [0], color=PERI, lw=8, alpha=0.18, label='near-peripheral field, ±200 px around the fovea'),
    Line2D([0], [0], color=CURSOR, lw=1.8, ls=(0, (4, 2)), label='cursor'),
    Line2D([0], [0], marker='o', mfc='none', mec=TEXT, mew=1.5, ms=9, color='none', label='click'),
]
fig.legend(handles=handles, loc='lower center', ncol=4, fontsize=8.6, frameon=False, bbox_to_anchor=(0.5, 0.005), handlelength=2.6, columnspacing=1.6)

fig.suptitle('Stutter-step navigation on a results page: an idealized trial with three channels',
             fontsize=13.5, x=0.045, ha='left', y=0.975)
fig.text(0.045, 0.925,
         'Schematic, not data. Fixation durations, the ambient/focal contrast, the return precision and the 200 px field are the AdSERP medians\n'
         'in docs/ablations/major_saccade_selection.md, return_is_memory.md and periphery_navigates.md. Result bands are 80 px, as on the typed AOI map.',
         fontsize=8.8, color=TEXT, va='top')

for ext in ('png', 'svg', 'pdf'):
    fig.savefig(OUT / f'idealized_navigation.{ext}', dpi=170 if ext == 'png' else None)
print('wrote', OUT / 'idealized_navigation.png', f'T_END {T_END / 1000:.2f}s')
