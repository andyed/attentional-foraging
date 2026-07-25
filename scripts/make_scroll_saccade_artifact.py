#!/usr/bin/env python3
"""
Mechanism diagram: a saccade that straddles a scroll measures the page, not the eye.

Deterministic SVG (muriel: generated > drawn, reproducible > one-off, real data not placeholder).
Grounded on a real AdSERP fixation pair (p004-b5-t8) where the page-space vector is ~entirely
the scroll. Renders SVG + PNG into scripts/output/scroll_saccade_artifact/.

Palette: warm editorial (matches the F-explainer essay). All text in warm near-black ink
(>14:1 on the paper bg, clears the 8:1 floor); rust/teal used only for decorative arrows/markers.
"""
import sys, os, bisect, subprocess, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'notebooks-v2'))
from data_loader import load_fixations, get_trial_meta, load_mouse_events  # noqa

TRIAL = 'p004-b5-t8'
OUT = os.path.join(os.path.dirname(__file__), 'output', 'scroll_saccade_artifact')
os.makedirs(OUT, exist_ok=True)

# ---- pull the real fixation pair + scroll delta (honest, recomputed) ----
fix = load_fixations(TRIAL)
scr_h = get_trial_meta(TRIAL)[1]
_, scr, _ = load_mouse_events(TRIAL)
st = [t for t, _ in scr]; sy = [y for _, y in scr]
i = 18  # saccade between fixation 18 and 19 (1-based); f0=fix[17], f1=fix[18]
f0, f1 = fix[i - 1], fix[i]
t0, t1 = f0['t'], f1['t']
lo = bisect.bisect_right(st, t0); hi = bisect.bisect_right(st, t1)
dscroll = sy[hi - 1] - (sy[lo - 1] if lo > 0 else 0)
page_dx = f1['x'] - f0['x']; page_dy = f1['y'] - f0['y']
eye_dy = page_dy - dscroll                       # viewport residual = real eye motion
eye_disp = round((page_dx ** 2 + eye_dy ** 2) ** 0.5)
print(f"page (x,y) {f0['x']:.0f},{f0['y']:.0f} -> {f1['x']:.0f},{f1['y']:.0f} | "
      f"page dy={page_dy:.0f} dx={page_dx:.0f} | scroll={dscroll:.0f} | eye~{eye_disp}px")

# ---- palette (warm editorial) ----
PAPER = "#f3efe4"; INK = "#1f1b16"; CARD = "#e9e3d3"; LINE = "#c9c0aa"
RUST = "#b14026"; TEAL = "#1d6b5f"; GHOST = "#cfc6b2"
# Text variants of the accents, darkened to clear the 8:1 floor (vivid RUST/TEAL stay on arrows only).
RUST_TXT = "#7a1f12"; TEAL_TXT = "#154f45"; MUTED = "#443e30"

W, H = 1040, 600
S = []
def t(x, y, s, size=16, w="400", anchor="middle", fill=INK, ff="Georgia, serif"):
    S.append(f'<text x="{x}" y="{y}" font-family="{ff}" font-size="{size}" '
             f'font-weight="{w}" text-anchor="{anchor}" fill="{fill}">{s}</text>')

S.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
S.append(f'<rect width="{W}" height="{H}" fill="{PAPER}"/>')
# arrowheads
S.append(f'<defs>'
         f'<marker id="ar" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto">'
         f'<path d="M0,0 L7,3 L0,6 Z" fill="{RUST}"/></marker>'
         f'<marker id="at" markerWidth="11" markerHeight="11" refX="7" refY="3.5" orient="auto">'
         f'<path d="M0,0 L8,3.5 L0,7 Z" fill="{TEAL}"/></marker>'
         f'<marker id="ak" markerWidth="11" markerHeight="11" refX="7" refY="3.5" orient="auto">'
         f'<path d="M0,0 L8,3.5 L0,7 Z" fill="{INK}"/></marker></defs>')

# ---- title (asserts the finding) + subtitle ----
t(W/2, 46, "A saccade across a scroll measures the page, not the eye", size=27, w="700")
t(W/2, 74, "AdSERP page coordinates include scroll — so differencing two fixations that "
           "straddle a scroll folds page motion into the “saccade.”", size=16)

# ---------------- LEFT PANEL: page-space ----------------
lx0 = 56
t(lx0 + 220, 116, "What the data records  (page-space)", size=18, w="700")
# page document column
pgx0, pgx1 = lx0 + 150, lx0 + 250
S.append(f'<rect x="{pgx0}" y="150" width="{pgx1-pgx0}" height="300" rx="6" '
         f'fill="{CARD}" stroke="{LINE}" stroke-width="1.5"/>')
# ghost result rows on the page for context
for yy in (175, 235, 320, 405):
    S.append(f'<rect x="{pgx0+12}" y="{yy}" width="{pgx1-pgx0-24}" height="22" rx="3" fill="{GHOST}"/>')
# scale page-y [700,1040] -> svg-y [168,432]
def pgy(py): return 168 + (py - 700) * (432 - 168) / (1040 - 700)
y1, y2 = pgy(f0['y']), pgy(f1['y'])
cxa = pgx0 + 50
# big rust vector
S.append(f'<line x1="{cxa}" y1="{y1}" x2="{cxa}" y2="{y2-4}" stroke="{RUST}" '
         f'stroke-width="5" marker-end="url(#ar)"/>')
for (cy, lab) in ((y1, "fixation 18"), (y2, "fixation 19")):
    S.append(f'<circle cx="{cxa}" cy="{cy}" r="6.5" fill="{INK}"/>')
    t(cxa - 14, cy + 5, lab, size=15, anchor="end")
t(cxa + 18, (y1 + y2) / 2 - 6, f"Δy = +{page_dy:.0f} px", size=18, w="700", anchor="start", fill=RUST_TXT)
t(cxa + 18, (y1 + y2) / 2 + 14, "recorded as a large", size=15, anchor="start")
t(cxa + 18, (y1 + y2) / 2 + 32, "downward saccade", size=15, anchor="start")

# ---------------- RIGHT PANEL: viewport ----------------
rx0 = 560
t(rx0 + 185, 116, "What the eye did  (viewport)", size=18, w="700")
# screen rect (viewport) — narrow, leaving clear room on the right for the scroll arrow + label
scx0, scx1, scy0, scy1 = rx0 + 40, rx0 + 300, 162, 400
S.append(f'<rect x="{scx0}" y="{scy0}" width="{scx1-scx0}" height="{scy1-scy0}" rx="8" '
         f'fill="#fbf8f0" stroke="{INK}" stroke-width="2"/>')
t((scx0+scx1)/2, scy0 - 9, "the screen (fixed frame)", size=14)
# scroll arrow OUTSIDE the screen on the right; label rotated, clear of everything
sax = scx1 + 34
S.append(f'<line x1="{sax}" y1="{scy1-6}" x2="{sax}" y2="{scy0+6}" stroke="{INK}" '
         f'stroke-width="3" marker-end="url(#ak)"/>')
mid = (scy0 + scy1) / 2
S.append(f'<text x="{sax+17}" y="{mid}" font-family="Georgia, serif" font-size="15" '
         f'font-weight="700" text-anchor="middle" fill="{INK}" '
         f'transform="rotate(-90 {sax+17} {mid})">page scrolls ↑ {dscroll:.0f} px</text>')
# the two fixations: nearly the same screen spot (~11 px apart)
gx, gy = scx0 + 130, 286
S.append(f'<line x1="{gx}" y1="{gy}" x2="{gx-page_dx*0.7}" y2="{gy+eye_dy*0.9}" '
         f'stroke="{TEAL}" stroke-width="4" marker-end="url(#at)"/>')
S.append(f'<circle cx="{gx}" cy="{gy}" r="6.5" fill="{INK}"/>')
S.append(f'<circle cx="{gx-page_dx*0.7}" cy="{gy+eye_dy*0.9}" r="6.5" fill="{INK}"/>')
t(gx + 16, gy + 4, f"≈ {eye_disp} px", size=18, w="700", anchor="start", fill=TEAL_TXT)
# one clean annotation below the screen
t((scx0+scx1)/2, scy1 + 26, "Same screen position —", size=15, w="700")
t((scx0+scx1)/2, scy1 + 44, "the page moved, not the eye.", size=15)

# ---- bridge line ----
t(W/2, 478, f"The {page_dy:.0f} px “saccade” is the {dscroll:.0f} px scroll "
            f"— real eye motion is {eye_disp} px.", size=17, w="700")

# ---- consequence caption ----
t(W/2, 512, "Scrolling is always vertical, so the spurious vector reads as a downward gaze.",
  size=16)
t(W/2, 533, "Across AdSERP it pushed evaluate-phase saccades from 39% to 51% “primarily "
            "vertical” — and made the F-pattern’s vertical limb look real.", size=16)
t(W/2, 558, "Fix: drop saccades whose time window contains a scroll event (scroll-aware computation).",
  size=16, w="700", fill=TEAL_TXT)

# source + credit
t(lx0, 588, f"Source: AdSERP {TRIAL}, NB13 scroll-aware analysis (2026-06-03)",
  size=14, anchor="start", fill=MUTED)
t(W - 56, 588, "built with muriel", size=14, anchor="end", fill=MUTED)

S.append('</svg>')
svg = "\n".join(S)
svg_path = os.path.join(OUT, 'scroll_saccade_artifact.svg')
open(svg_path, 'w').write(svg)
print("wrote", svg_path)

# ---- SVG -> PNG ----
png_path = os.path.join(OUT, 'scroll_saccade_artifact.png')
done = False
try:
    import cairosvg
    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=2080, output_height=1200)
    done = True
except Exception as e:
    print("cairosvg unavailable:", e)
if not done:
    for tool, args in (("rsvg-convert", ["-w", "2080", "-o", png_path, svg_path]),
                       ("inkscape", [svg_path, "--export-filename=" + png_path, "-w", "2080"])):
        if shutil.which(tool):
            subprocess.run([tool] + args, check=True); done = True; break
print("wrote", png_path if done else "(PNG conversion skipped — no converter)")
