"""Build the PAI explainer subsite figures — site/pai/fig-*.svg.

Every figure is generated from ONE real AdSERP trial (p007-b2-t4) with
AllSERP-typed hybrid AOIs (dd_top ad, 7 organics, native_ad), and every
alpha is computed by scripts/pai_spec.py (Eq. 2 canonical, per
Duchowski's 2026-08-31 guidance: cite the paper + qualifier). No
synthetic geometry; the SERP rendering is schematic but the boxes,
fixations, and alphas are data. Deterministic: same inputs, same SVG.

Run:  .venv/bin/python scripts/build-pai-site.py
Then: open site/pai/index.html (handwritten page referencing the SVGs).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_fixations  # noqa: E402
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402
from pai_spec import rect_alpha_grid  # noqa: E402

OUT = ROOT / "site/pai"
OUT.mkdir(parents=True, exist_ok=True)

TRIAL = "p007-b2-t4"
CLICKED_POS = 3          # from the buf500 grid records: was_clicked
CLICKED_ENTRY_T = 1671704780052.0   # entry_t of the clicked result

X0, X1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
PHI = (1 + np.sqrt(5)) / 2 - 1
P_LAMBDA = PHI ** 3      # demo kernel exponent, for the kernel figure

# ── palette (light editorial page: #fafaf8 ground) ────────────────────
INK = "#1a1a1a"          # primary text  (contrast vs #fafaf8 = 16.7:1)
INK2 = "#3d3d3d"         # secondary text (10.4:1)
PAPER = "#fafaf8"
BOX_STROKE = "#8a8578"   # AOI outline (graphic, not text)
CONTENT = "#dedbd2"      # schematic content bars
AD_ACCENT = "#a06020"    # ad marking stripe (graphic)
MASS = (36, 90, 122)     # peripheral-mass blue, fill via rgba
FIX = "#c23a2b"          # fixation marker red (graphic only)
FIX_TEXT = "#7a2013"     # red TEXT (9.8:1 — computed, 8:1 floor)
GOLD = "#b08050"         # explainer house accent (lines only)
GOLD_TEXT = "#5f4119"    # amber TEXT (8.9:1 — computed)


def caption(svg, x, y, lines, size=13):
    for i, ln in enumerate(lines):
        svg.text(x, y + i * (size + 5), ln, size=size, fill=INK2)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


class SVG:
    def __init__(self, w, h, title, desc):
        self.w, self.h = w, h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'role="img" font-family="Georgia, \'Times New Roman\', serif">',
            f"<title>{esc(title)}</title><desc>{esc(desc)}</desc>",
            f'<rect width="{w}" height="{h}" fill="{PAPER}"/>',
        ]

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=15, fill=INK, anchor="start", weight="normal",
             style="normal", family=None):
        fam = f' font-family="{family}"' if family else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
                 f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" '
                 f'font-style="{style}"{fam}>{esc(s)}</text>')

    def write(self, name):
        self.parts.append("</svg>")
        p = OUT / name
        p.write_text("\n".join(self.parts))
        print(f"  wrote {p.relative_to(ROOT)}")


class SerpPanel:
    """Schematic SERP at true page coordinates, scaled, with a labeled
    fold-break where a large content gap would waste the canvas."""

    def __init__(self, svg, ox, oy, scale, tops, bots, etypes,
                 break_after=None, break_gap=26):
        self.svg, self.ox, self.oy, self.s = svg, ox, oy, scale
        self.tops, self.bots, self.etypes = tops, bots, etypes
        self.break_after = break_after
        self.break_gap = break_gap
        self.y_shift = 0.0
        if break_after is not None:
            gap = tops[break_after + 1] - bots[break_after]
            self.y_shift = gap * scale - break_gap
        self.page_top = tops[0] - 40

    def Y(self, y):
        out = self.oy + (y - self.page_top) * self.s
        if (self.break_after is not None
                and y >= self.tops[self.break_after + 1] - 1):
            out -= self.y_shift
        return out

    def X(self, x):
        return self.ox + (x - X0 + 30) * self.s

    @property
    def width(self):
        return (X1 - X0 + 60) * self.s

    def height(self):
        return self.Y(self.bots[-1] + 40) - self.oy

    def draw(self, fills=None, labels=None, foveal=()):
        s, svg = self.s, self.svg
        for i, (t, b, e) in enumerate(zip(self.tops, self.bots, self.etypes)):
            x, y = self.X(X0), self.Y(t)
            w, h = (X1 - X0) * s, (b - t) * s
            fill = "none"
            if fills is not None and fills[i] is not None:
                r, g, bl = MASS
                fill = f"rgba({r},{g},{bl},{fills[i]:.3f})"
            stroke, sw = (INK, 2.0) if i in foveal else (BOX_STROKE, 1.1)
            svg.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
                    f'height="{h:.1f}" rx="3" fill="{fill}" '
                    f'stroke="{stroke}" stroke-width="{sw}"/>')
            if e != "organic":
                svg.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="3" '
                        f'height="{h:.1f}" fill="{AD_ACCENT}"/>')
            # schematic content: title bar + text lines, clipped to box
            if h > 14:
                ly = y + 7
                svg.add(f'<rect x="{x + 9:.1f}" y="{ly:.1f}" '
                        f'width="{w * 0.55:.1f}" height="4.5" rx="2" '
                        f'fill="{CONTENT}"/>')
                ly += 9
                while ly + 3 < y + h - 6 and ly < y + 46:
                    svg.add(f'<rect x="{x + 9:.1f}" y="{ly:.1f}" '
                            f'width="{w * 0.82:.1f}" height="3" rx="1.5" '
                            f'fill="{CONTENT}"/>')
                    ly += 6.5
            if labels is not None and labels[i] is not None:
                svg.text(x + w + 8, y + min(h, 16) / 2 + 5, labels[i],
                         size=13, fill=INK,
                         family="'SF Mono', Menlo, monospace")
        if self.break_after is not None:
            yb = self.Y(self.bots[self.break_after]) + self.break_gap * 0.45
            x, w = self.X(X0) - 6, (X1 - X0) * s + 12
            svg.add(f'<path d="M {x:.1f} {yb:.1f} l {w / 4:.1f} 4 '
                    f'l {w / 4:.1f} -7 l {w / 4:.1f} 6 l {w / 4:.1f} -5" '
                    f'stroke="{BOX_STROKE}" stroke-width="1" fill="none" '
                    f'stroke-dasharray="4 3"/>')

    def fixation(self, fx, fy, r=6, label=None):
        x, y = self.X(fx), self.Y(fy)
        self.svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                     f'fill="{FIX}" fill-opacity="0.85" stroke="{PAPER}" '
                     f'stroke-width="1.4"/>')
        if label:
            self.svg.add(
                f'<text x="{x - r - 6:.1f}" y="{y - r - 4:.1f}" '
                f'font-size="12.5" fill="{INK}" text-anchor="end" '
                f'font-style="italic" paint-order="stroke" '
                f'stroke="{PAPER}" stroke-width="3.5">{esc(label)}</text>')


def load_trial():
    tops, bots, etypes = build_hybrid_aois(TRIAL)
    fixations = load_fixations(TRIAL)
    ft = np.array([f["t"] for f in fixations], float)
    fx = np.array([f["x"] for f in fixations], float)
    fy = np.array([f["y"] for f in fixations], float)
    fd = np.array([f.get("d", 200) or 200 for f in fixations], float)
    return tops, bots, etypes, ft, fx, fy, fd


def alphas_at(px, py, tops, bots, kernel="eq2"):
    if kernel in ("eq2", "listing"):
        return rect_alpha_grid([px], [py], X0, X1, tops, bots,
                               weight_placement=kernel)[0]
    # demo kernel: boundary OGD, inverse-area weight (for the contrast fig)
    a_top, a_bot = np.asarray(tops, float), np.asarray(bots, float)
    areas = (X1 - X0) * np.maximum(a_bot - a_top, 1.0)
    w_a = (areas.max() / areas) ** P_LAMBDA
    dx = max(X0 - px, 0.0, px - X1)
    dy = np.maximum.reduce([a_top - py, np.zeros(len(a_top)), py - a_bot])
    ogd = np.hypot(dx, dy)
    cx, cy = (X0 + X1) / 2.0, (a_top + a_bot) / 2.0
    cgd = np.hypot(px - cx, py - cy)
    return np.clip(1.0 - np.sqrt(ogd / np.maximum(cgd, 1.0)) * w_a, 0.0, 1.0)


def inside(px, py, top, bot):
    return X0 <= px <= X1 and top <= py <= bot


def main():
    tops, bots, etypes, ft, fx, fy, fd = load_trial()
    n = len(tops)
    names = []
    org_i = 0
    for e in etypes:
        if e == "organic":
            org_i += 1
            names.append(f"Result {org_i}")
        else:
            names.append("AI/answer ad" if e == "dd_top" else "Native ad")

    # anchor fixation: longest fixation inside AOI 2 before the click entry
    cand = [i for i in range(len(ft))
            if ft[i] < CLICKED_ENTRY_T and inside(fx[i], fy[i], tops[2], bots[2])]
    anchor = max(cand, key=lambda i: fd[i])
    ax, ay = float(fx[anchor]), float(fy[anchor])
    al_eq2 = alphas_at(ax, ay, tops, bots, "eq2")
    al_demo = alphas_at(ax, ay, tops, bots, "demo")
    print(f"anchor fixation ({ax:.0f}, {ay:.0f}), {fd[anchor]:.0f} ms, in AOI 2")
    print("eq2 alphas:", np.round(al_eq2, 3))

    SCALE = 0.30
    BRK = 7  # fold break between last organic and the bottom native ad
    LABEL_W = 128
    p_w = (X1 - X0 + 60) * SCALE
    span = (bots[-1] + 40) - (tops[0] - 40)
    y_shift = (tops[BRK + 1] - bots[BRK]) * SCALE - 26
    pan_h = span * SCALE - y_shift
    OX1 = 28
    OX2 = OX1 + p_w + LABEL_W + 52
    W2 = OX2 + p_w + LABEL_W + 16   # two-panel canvas width
    OY = 64
    H2 = OY + pan_h + 74            # two-panel canvas height

    # ── Fig 1: binary hit vs PAI, same fixation ───────────────────────
    svg = SVG(W2, H2, "Binary AOI hit vs Peripheral Attention Index",
              "Two schematic SERPs from AdSERP trial p007-b2-t4. Left: the "
              "fixation scores only the AOI containing it. Right: PAI gives "
              "every AOI a soft alpha from the same fixation.")
    fov = int(np.argmax([inside(ax, ay, t, b)
                         for t, b in zip(tops, bots)]))
    for k, (ox, head) in enumerate(((OX1, "Binary point-in-AOI"),
                                    (OX2, "PAI, Eq. (2)"))):
        svg.text(ox + 8, 30, head, size=18, weight="bold")
        pan = SerpPanel(svg, ox, OY, SCALE, tops, bots, etypes,
                        break_after=BRK)
        if k == 0:
            fills = [1.0 if i == fov else None for i in range(n)]
            labels = ["hit" if i == fov else "0" for i in range(n)]
            svg.text(ox + 8, 50, "one AOI scores; eight are invisible",
                     size=13.5, fill=INK2, style="italic")
        else:
            fills = [None if i == fov else float(al_eq2[i]) for i in range(n)]
            labels = ["foveal hit" if i == fov else f"α {al_eq2[i]:.2f}"
                      for i in range(n)]
            svg.text(ox + 8, 50, "every distal AOI gets a graded alpha",
                     size=13.5, fill=INK2, style="italic")
        pan.draw(fills=fills, labels=labels, foveal={fov} if k else ())
        pan.fixation(ax, ay, label="fixation" if k == 0 else None)
    caption(svg, OX1, H2 - 52, [
        f"Same {fd[anchor]:.0f} ms fixation on Result 2 — the foveated AOI "
        "is a hit in both; PAI adds the other eight.",
        "Geometry: AdSERP trial p007-b2-t4 with AllSERP typed AOIs;",
        "α by Eq. (2), Duchowski, Gehrer & Svaldi (ETTAC 2026)."])
    svg.write("fig-binary-vs-pai.svg")

    # ── Fig 2: anatomy of Eq. (2) on the clicked AOI ──────────────────
    svg = SVG(900, 560, "Anatomy of the PAI alpha (Eq. 2)",
              "The gaze point, the vertex OGD, the centroid CGD, and the "
              "area weight on one real AOI.")
    pan = SerpPanel(svg, 40, 96, 0.34, tops[1:6], bots[1:6], etypes[1:6])
    fills = [None] * 5
    ci = CLICKED_POS - 1  # index within the slice [1:6]
    fills[ci] = float(al_eq2[CLICKED_POS])
    pan.draw(fills=fills, labels=None)
    pan.fixation(ax, ay)
    t3, b3 = tops[CLICKED_POS], bots[CLICKED_POS]
    gx, gy = pan.X(ax), pan.Y(ay)
    # OGD: nearest vertex = top-left corner here; CGD: centroid
    corners = [(X0, t3), (X1, t3), (X0, b3), (X1, b3)]
    vx, vy = min(corners, key=lambda c: np.hypot(ax - c[0], ay - c[1]))
    cxp, cyp = (X0 + X1) / 2, (t3 + b3) / 2
    svg.add(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{pan.X(vx):.1f}" '
            f'y2="{pan.Y(vy):.1f}" stroke="{FIX}" stroke-width="2"/>')
    svg.add(f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{pan.X(cxp):.1f}" '
            f'y2="{pan.Y(cyp):.1f}" stroke="{GOLD}" stroke-width="2" '
            f'stroke-dasharray="6 4"/>')
    svg.add(f'<circle cx="{pan.X(vx):.1f}" cy="{pan.Y(vy):.1f}" r="4" '
            f'fill="{FIX}"/>')
    svg.add(f'<circle cx="{pan.X(cxp):.1f}" cy="{pan.Y(cyp):.1f}" r="4" '
            f'fill="{GOLD}" stroke="{INK}" stroke-width="0.8"/>')
    ogd_v = float(np.hypot(ax - vx, ay - vy))
    cgd_v = float(np.hypot(ax - cxp, ay - cyp))
    x_r = pan.X(X1) + 40
    svg.text(30, 40, "One fixation, one distal AOI — the three "
             "ingredients", size=19, weight="bold")
    svg.text(x_r, 150, "OGD — distance to the nearest", size=15)
    svg.text(x_r, 170, "AOI vertex (corner)", size=15)
    svg.text(x_r, 190, f"= {ogd_v:.0f} px here", size=14, fill=FIX_TEXT,
             family="'SF Mono', Menlo, monospace")
    svg.text(x_r, 234, "CGD — distance to the", size=15)
    svg.text(x_r, 254, "AOI centroid", size=15)
    svg.text(x_r, 274, f"= {cgd_v:.0f} px here", size=14, fill=GOLD_TEXT,
             family="'SF Mono', Menlo, monospace")
    svg.text(x_r, 318, "A — the AOI's area, relative to the", size=15)
    svg.text(x_r, 338, "largest AOI on the page (A_ref):", size=15)
    a3 = (X1 - X0) * (b3 - t3)
    amax = (X1 - X0) * max(b - t for t, b in zip(tops, bots))
    svg.text(x_r, 358, f"min(1, A/A_ref) = {a3 / amax:.3f}", size=14,
             fill=INK, family="'SF Mono', Menlo, monospace")
    svg.text(x_r, 412, "α = 1 − √( OGD/CGD · "
             "min(1, A/A_ref) )", size=16.5, weight="bold",
             family="'SF Mono', Menlo, monospace")
    svg.text(x_r, 440, f"= {float(al_eq2[CLICKED_POS]):.2f} for this pair",
             size=14, fill=INK2, family="'SF Mono', Menlo, monospace")
    svg.text(x_r, 484, "Inside or at a vertex → α ≈ 1.", size=14, fill=INK2)
    svg.text(x_r, 504, "Far away → α → 0. Small AOIs decay", size=14, fill=INK2)
    svg.text(x_r, 524, "slower — they must not vanish.", size=14, fill=INK2)
    svg.text(30, 545, "Eq. (2) of Duchowski, Gehrer & Svaldi (ETTAC 2026), "
             "computed by scripts/pai_spec.py on trial p007-b2-t4.",
             size=13, fill=INK2)
    svg.write("fig-anatomy.svg")

    # ── Fig 3: pre-entry accumulation on the clicked result ───────────
    pre = ft < CLICKED_ENTRY_T
    al_all = rect_alpha_grid(fx, fy, X0, X1, tops, bots,
                             weight_placement="eq2")
    outside_g = np.zeros((len(ft), n), bool)
    for j, (t, b) in enumerate(zip(tops, bots)):
        outside_g[:, j] = ~np.array([inside(x, y, t, b)
                                     for x, y in zip(fx, fy)])
    mass = (fd[pre, None] * np.where(outside_g[pre], al_all[pre], 0)).sum(axis=0)
    binary_dwell_clicked = fd[pre & ~outside_g[:, CLICKED_POS]].sum()
    print("pre-entry peripheral mass (ms):", np.round(mass))
    print("binary pre-entry dwell on clicked:", binary_dwell_clicked)

    H3 = 66 + pan_h + 66
    svg = SVG(1040, H3, "Peripheral mass accrues before first fixation",
              "Left: the pre-entry scanpath. Right: accumulated peripheral "
              "PAI mass per AOI at the moment the clicked result is first "
              "fixated; its binary dwell is still zero.")
    svg.text(30, 36, "15 seconds before the click target is ever fixated",
             size=19, weight="bold")
    pan = SerpPanel(svg, 30, 66, SCALE, tops, bots, etypes, break_after=BRK)
    fills = [None] * n
    pan.draw(fills=fills, labels=None)
    idxs = np.where(pre)[0]
    pts = [(pan.X(fx[i]), pan.Y(fy[i])) for i in idxs]
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    svg.add(f'<path d="{d}" fill="none" stroke="{FIX}" stroke-width="1.1" '
            f'stroke-opacity="0.45"/>')
    for k, i in enumerate(idxs):
        r = 2.2 + 3.4 * (fd[i] / fd[idxs].max())
        svg.add(f'<circle cx="{pan.X(fx[i]):.1f}" cy="{pan.Y(fy[i]):.1f}" '
                f'r="{r:.1f}" fill="{FIX}" fill-opacity="0.5"/>')
    # highlight the clicked AOI
    y3, h3 = pan.Y(tops[CLICKED_POS]), (bots[CLICKED_POS] - tops[CLICKED_POS]) * SCALE
    svg.add(f'<rect x="{pan.X(X0) - 4:.1f}" y="{y3 - 4:.1f}" '
            f'width="{(X1 - X0) * SCALE + 8:.1f}" height="{h3 + 8:.1f}" '
            f'rx="4" fill="none" stroke="{INK}" stroke-width="1.8" '
            f'stroke-dasharray="5 4"/>')
    svg.text(pan.X(X1) + 10, y3 + h3 / 2 + 4, "will be clicked", size=13,
             fill=INK, style="italic")
    # right: mass bars
    bx = pan.width + 120
    svg.text(bx, 66, "Accumulated peripheral PAI mass at that moment",
             size=15.5, weight="bold")
    svg.text(bx, 86, "(soft α × fixation duration, summed; "
             "fixations inside an AOI excluded)", size=13, fill=INK2)
    bar_max = mass.max()
    for j in range(n):
        yb = 112 + j * 52
        svg.text(bx, yb + 13, names[j], size=14,
                 fill=INK if j == CLICKED_POS else INK2,
                 weight="bold" if j == CLICKED_POS else "normal")
        wb = 320 * mass[j] / bar_max
        r, g, bl = MASS
        svg.add(f'<rect x="{bx:.1f}" y="{yb + 20:.1f}" width="{wb:.1f}" '
                f'height="16" rx="2" fill="rgb({r},{g},{bl})" '
                f'fill-opacity="{0.95 if j == CLICKED_POS else 0.45}"/>')
        svg.text(bx + wb + 8, yb + 33, f"{mass[j] / 1000:.1f} s", size=13,
                 fill=INK, family="'SF Mono', Menlo, monospace")
        if j == CLICKED_POS:
            svg.text(bx + wb + 70, yb + 33,
                     "← binary dwell here: 0 ms", size=13, fill=FIX_TEXT)
    caption(svg, 30, H3 - 40, [
        "Trial p007-b2-t4: every fixation before the clicked result's first "
        "entry — its binary point-in-AOI dwell is 0 by construction",
        "in this window. Mass = Eq. (2) α × fixation duration, "
        "strictly-outside fixations only."])
    svg.write("fig-accumulation.svg")

    # ── Fig 4: the area weight decides between-AOI comparisons ────────
    H4 = OY + 6 + pan_h + 90
    svg = SVG(W2, H4, "Two area weights, two different rankings",
              "The same fixation scored by the published Eq. 2 weight and by "
              "an earlier demo kernel with the weight inverted; the AOI "
              "ranking reverses.")
    for k, (ox, head, al, note) in enumerate((
            (OX1, "Eq. (2): min(1, A/A_ref)", al_eq2,
             "small AOIs decay slower — published form"),
            (OX2, "Demo kernel: (A_ref/A)^0.236", al_demo,
             "small AOIs suppressed — pre-print approximation"))):
        svg.text(ox + 8, 30, head, size=16, weight="bold",
                 family="'SF Mono', Menlo, monospace")
        svg.text(ox + 8, 50, note, size=13.5, fill=INK2, style="italic")
        pan = SerpPanel(svg, ox, OY + 6, SCALE, tops, bots, etypes,
                        break_after=BRK)
        fov = int(np.argmax([inside(ax, ay, t, b)
                             for t, b in zip(tops, bots)]))
        distal = [j for j in range(n) if j != fov and al[j] > 0.005]
        order = sorted(distal, key=lambda j: -al[j])
        rank = {j: r for r, j in enumerate(order, 1)}
        labels = ["foveal — excluded" if j == fov
                  else (f"α {al[j]:.2f}  #{rank[j]}" if j in rank
                        else f"α {al[j]:.2f}") for j in range(n)]
        fills = [None if j == fov else float(al[j]) for j in range(n)]
        pan.draw(fills=fills, labels=labels, foveal={fov})
        pan.fixation(ax, ay)
    caption(svg, OX1, H4 - 58, [
        "Same fixation, same geometry — only the area weight differs, and "
        "the between-AOI ranking (#1 = highest α from this",
        "fixation) reverses. Naming the kernel is part of reporting a PAI "
        "number; per the authors, “Eq. (2) from [the paper]",
        "was used” is the canonical citation form."])
    svg.write("fig-kernels.svg")

    print("\nmanifest for captions:")
    print(f"  anchor fixation: ({ax:.0f}, {ay:.0f}) page px, "
          f"{fd[anchor]:.0f} ms, inside Result 2")
    print(f"  alpha(clicked Result 3) eq2 = {al_eq2[CLICKED_POS]:.3f}")
    print(f"  pre-entry mass clicked = {mass[CLICKED_POS] / 1000:.2f} s; "
          f"max over AOIs = {mass.max() / 1000:.2f} s")
    print(f"  pre-entry window = "
          f"{(CLICKED_ENTRY_T - ft.min()) / 1000:.1f} s, "
          f"{int(pre.sum())} fixations")


if __name__ == "__main__":
    main()
