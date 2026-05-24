"""Dressed-up ETTAC asset (v2): 'LF/HF spikes on rejected items' for p045-b2-t6.

Layout (top → bottom, single left margin, ≥24 px gutters everywhere):
    1. Headline strip (title + subtitle)
    2. SERP body — clean (rectangles only, no tags overlapping the page)
       - Red dashed rectangle on the rejected product card (no label inline)
       - Green solid rectangle on the clicked product card (no label inline)
    3. Annotation strip — both REJECTED and CLICKED tags side-by-side BELOW the
       SERP, mirrored layout (kills the asymmetry the v1 had)
    4. Chart strip — LF/HF per-fixation bars with:
       - 'filter warmup (fix 1-6)' hatched band (replaces 6 null-bar labels)
       - peak callout at fix 10 only (no per-bar numerics — kills the
         54/55/54.9 numeric drift the v1 had)
       - explicit y-axis label 'LF/HF ratio'
       - single rounding convention: 54.85
    5. Footer caption (separated ≥24 px from chart x-axis labels)

Output: scripts/output/ettac/p045_evaluate_reject_story.png
"""

from __future__ import annotations
import asyncio, re, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site" / "p045-b2-t6.html"
OUT_DIR = REPO / "scripts" / "output" / "ettac"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Source-px AOI rectangles for the 5-product carousel. Verified against
# fix 10 = (176, 349) and click = (434, 426).
AOI_REJECTED = {"x": 110, "y": 305, "w": 130, "h": 320}    # leftmost (€5.71)
AOI_CLICKED  = {"x": 378, "y": 305, "w": 132, "h": 320}    # 3rd (€17.38)

# Single rounding convention.
PEAK_LFHF = 54.85
PEAK_FIX  = 10
CLICK_T   = 34.6
SPIKE_T   = 1.5


def _load_font(size, bold=True):
    fp = ([
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ] if bold else [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ])
    for p in fp:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


async def capture_base():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1300, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(SITE.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.wait_for_function("typeof F !== 'undefined' && F.length > 0")

        await page.evaluate("""
            (() => {
                const gp = document.getElementById('gazeplot-img');
                if (gp) gp.style.display = 'none';
                const pc = document.getElementById('prog-canvas');
                if (pc) pc.style.display = 'none';
                if (typeof bgMode !== 'undefined') bgMode = 'serp';
            })()
        """)
        for _ in range(6):
            cur = await page.evaluate("colorMode")
            if cur == "lfhf":
                break
            await page.click("#color-btn")
            await page.wait_for_timeout(60)

        # 0-3s window
        await page.evaluate("""
            (() => {
                const cut = 3000;
                let idx = F.length - 1;
                for (let i = 0; i < F.length; i++) {
                    if (F[i].t - T0 > cut) { idx = Math.max(0, i - 1); break; }
                }
                ci = idx;
                const slider = document.getElementById('window-size');
                slider.value = idx + 1;
                document.getElementById('ws-label').textContent =
                    (idx + 1) >= N ? 'All' : (idx + 1);
                if (typeof uv === 'function') uv();
            })()
        """)
        await page.wait_for_timeout(150)
        await page.evaluate("typeof recolor === 'function' && recolor()")
        await page.evaluate("""
            (() => {
                const svg = document.getElementById('scanpath-svg');
                if (!svg) return;
                svg.querySelectorAll('text').forEach(t => {
                    t.setAttribute('font-size', 22);
                    t.setAttribute('font-weight', '700');
                    t.setAttribute('stroke-width', 2.5);
                });
                svg.querySelectorAll('circle').forEach(c => {
                    const r = parseFloat(c.getAttribute('r')) || 0;
                    if (r > 0 && r < 60) {
                        c.setAttribute('r', r * 1.5);
                        c.setAttribute('fill-opacity', 0.45);
                        c.setAttribute('stroke-width', 3);
                    }
                });
            })()
        """)
        await page.wait_for_timeout(120)

        fix = await page.evaluate("""
            F.filter(f => f.t - T0 <= 3000).map(f => ({
                t: f.t - T0, x: f.x, y: f.y, lfhf: f.lfhf
            }))
        """)
        await page.evaluate("document.getElementById('viewer').scrollTop = 0")
        await page.wait_for_timeout(150)

        viewer = await page.query_selector("#viewer")
        raw = OUT_DIR / "p045_story_raw.png"
        await viewer.screenshot(path=str(raw))
        await browser.close()
        return raw, fix


def annotate(raw_path: Path, fixations: list, out_path: Path):
    base = Image.open(raw_path).convert("RGB")
    BW, BH = base.size  # device-scale 2× → 2× source coords

    # ── Layout grid (single left margin, equal gutters) ─────────────
    LEFT = 36                # single content left margin (applied everywhere)
    RIGHT = LEFT
    GUTTER = 28              # vertical spacing between strips
    HEADLINE_H = 200
    ANNOT_H = 200            # below-SERP annotation strip with both tags
    CHART_H = 360
    FOOTER_H = 100
    CONTENT_W = BW           # canvas width = base width (no extra margins beyond LEFT/RIGHT padding shown via blocks)

    H = (HEADLINE_H + GUTTER + BH + GUTTER + ANNOT_H +
         GUTTER + CHART_H + GUTTER + FOOTER_H)
    canvas = Image.new("RGB", (CONTENT_W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    f_h1   = _load_font(60, bold=True)
    f_h2   = _load_font(40, bold=True)
    f_b    = _load_font(34, bold=False)
    f_lbl  = _load_font(38, bold=True)
    f_sub  = _load_font(28, bold=False)
    f_chart= _load_font(32, bold=True)
    f_axis = _load_font(28, bold=True)

    # ── 1. Headline strip ───────────────────────────────────────────
    y_cursor = 0
    draw.rectangle((0, y_cursor, CONTENT_W, y_cursor + HEADLINE_H),
                   fill=(245, 245, 248))
    draw.line((0, y_cursor + HEADLINE_H - 1, CONTENT_W, y_cursor + HEADLINE_H - 1),
              fill=(60, 60, 60), width=4)
    draw.text((LEFT, y_cursor + 32),
              "Cognitive load spikes on a result the user rejected",
              fill=(15, 15, 20), font=f_h1)
    draw.text((LEFT, y_cursor + 110),
              "AdSERP trial p045-b2-t6 · 0–3 s · LF/HF coding (amber → red)",
              fill=(60, 60, 70), font=f_b)
    y_cursor += HEADLINE_H + GUTTER

    # ── 2. SERP body ─ clean (rectangles only, NO tags inline) ──────
    serp_y = y_cursor
    canvas.paste(base, (0, serp_y))

    # Coordinate transforms (source → canvas).
    sx = lambda x: int(2 * x)
    sy = lambda y: int(2 * y) + serp_y

    # Rejected — dashed red rectangle.
    rx0, ry0 = sx(AOI_REJECTED["x"]), sy(AOI_REJECTED["y"])
    rx1 = sx(AOI_REJECTED["x"] + AOI_REJECTED["w"])
    ry1 = sy(AOI_REJECTED["y"] + AOI_REJECTED["h"])
    dash, gap = 18, 12
    def dashed_rect(x0, y0, x1, y1, color, width):
        for x in range(x0, x1, dash + gap):
            draw.line((x, y0, min(x + dash, x1), y0), fill=color, width=width)
            draw.line((x, y1, min(x + dash, x1), y1), fill=color, width=width)
        for y in range(y0, y1, dash + gap):
            draw.line((x0, y, x0, min(y + dash, y1)), fill=color, width=width)
            draw.line((x1, y, x1, min(y + dash, y1)), fill=color, width=width)
    dashed_rect(rx0, ry0, rx1, ry1, (220, 30, 30), 6)
    # Ⓡ marker glyph in the rectangle's top-left corner.
    badge_w = 64
    draw.ellipse((rx0 - badge_w // 2, ry0 - badge_w // 2,
                  rx0 + badge_w // 2, ry0 + badge_w // 2),
                 fill=(220, 30, 30), outline=(255, 255, 255), width=4)
    bbox_r = draw.textbbox((0, 0), "R", font=f_lbl)
    draw.text((rx0 - (bbox_r[2] - bbox_r[0]) // 2,
               ry0 - (bbox_r[3] - bbox_r[1]) // 2 - 8),
              "R", fill=(255, 255, 255), font=f_lbl)

    # Clicked — solid green rectangle.
    cx0, cy0 = sx(AOI_CLICKED["x"]), sy(AOI_CLICKED["y"])
    cx1 = sx(AOI_CLICKED["x"] + AOI_CLICKED["w"])
    cy1 = sy(AOI_CLICKED["y"] + AOI_CLICKED["h"])
    draw.rectangle((cx0, cy0, cx1, cy1), outline=(20, 130, 60), width=8)
    draw.ellipse((cx1 - badge_w // 2, cy0 - badge_w // 2,
                  cx1 + badge_w // 2, cy0 + badge_w // 2),
                 fill=(20, 130, 60), outline=(255, 255, 255), width=4)
    bbox_c = draw.textbbox((0, 0), "C", font=f_lbl)
    draw.text((cx1 - (bbox_c[2] - bbox_c[0]) // 2,
               cy0 - (bbox_c[3] - bbox_c[1]) // 2 - 8),
              "C", fill=(255, 255, 255), font=f_lbl)

    y_cursor = serp_y + BH + GUTTER

    # ── 3. Annotation strip — both tags side-by-side, mirrored ──────
    annot_y = y_cursor
    draw.rectangle((0, annot_y, CONTENT_W, annot_y + ANNOT_H),
                   fill=(248, 248, 250))
    draw.line((0, annot_y, CONTENT_W, annot_y), fill=(60, 60, 60), width=2)
    draw.line((0, annot_y + ANNOT_H - 1, CONTENT_W, annot_y + ANNOT_H - 1),
              fill=(60, 60, 60), width=2)

    # Two equal columns with center divider.
    col_w = (CONTENT_W - 2 * LEFT) // 2 - 16
    # Left column — REJECTED.
    L_x = LEFT
    draw.ellipse((L_x, annot_y + 32, L_x + 64, annot_y + 96),
                 fill=(220, 30, 30), outline=(0, 0, 0), width=2)
    draw.text((L_x + 16, annot_y + 36), "R",
              fill=(255, 255, 255), font=f_lbl)
    draw.text((L_x + 88, annot_y + 36),
              "REJECTED — €5.71 hose, leftmost card",
              fill=(160, 20, 20), font=f_lbl)
    draw.text((L_x + 88, annot_y + 92),
              f"peak LF/HF {PEAK_LFHF:.2f} at fix {PEAK_FIX} (t = {SPIKE_T:.1f} s)",
              fill=(40, 40, 50), font=f_b)
    draw.text((L_x + 88, annot_y + 138),
              "user evaluated this result heavily — then left it",
              fill=(60, 60, 70), font=f_sub)

    # Right column — CLICKED.
    R_x = LEFT + col_w + 32
    draw.ellipse((R_x, annot_y + 32, R_x + 64, annot_y + 96),
                 fill=(20, 130, 60), outline=(0, 0, 0), width=2)
    draw.text((R_x + 18, annot_y + 36), "C",
              fill=(255, 255, 255), font=f_lbl)
    draw.text((R_x + 88, annot_y + 36),
              "CLICKED — €17.38 hose, third card",
              fill=(20, 100, 50), font=f_lbl)
    draw.text((R_x + 88, annot_y + 92),
              f"click at t = {CLICK_T:.1f} s · 33 s after the spike",
              fill=(40, 40, 50), font=f_b)
    draw.text((R_x + 88, annot_y + 138),
              "user committed to a candidate they evaluated less",
              fill=(60, 60, 70), font=f_sub)

    # Vertical divider between the two columns.
    div_x = (CONTENT_W // 2)
    draw.line((div_x, annot_y + 24, div_x, annot_y + ANNOT_H - 24),
              fill=(180, 180, 190), width=2)
    y_cursor = annot_y + ANNOT_H + GUTTER

    # ── 4. Chart strip ──────────────────────────────────────────────
    chart_y = y_cursor
    draw.rectangle((0, chart_y, CONTENT_W, chart_y + CHART_H),
                   fill=(252, 252, 254))
    draw.line((0, chart_y, CONTENT_W, chart_y), fill=(60, 60, 60), width=2)

    # Title.
    draw.text((LEFT, chart_y + 16),
              "LF/HF ratio per fixation (first 3 s)",
              fill=(20, 20, 30), font=f_h2)

    # Plot area — same left margin as headline.
    n = len(fixations)
    plot_left = LEFT + 80         # leave room for y-axis label
    plot_right = CONTENT_W - RIGHT - 80
    plot_w = plot_right - plot_left
    plot_top = chart_y + 90
    plot_bot = chart_y + CHART_H - 80
    plot_h = plot_bot - plot_top
    bar_w = plot_w / max(n, 1)

    # Y-axis with explicit tick at peak.
    y_max = max((f.get("lfhf") or 0) for f in fixations) or 1
    y_max_ceil = 60               # round up to 60 for clean ticks
    draw.line((plot_left - 4, plot_bot, plot_left - 4, plot_top),
              fill=(40, 40, 40), width=3)
    for v in [0, 15, 30, 45, 60]:
        ty = int(plot_bot - (v / y_max_ceil) * plot_h)
        draw.line((plot_left - 12, ty, plot_left - 4, ty),
                  fill=(40, 40, 40), width=2)
        s = str(v)
        bbox = draw.textbbox((0, 0), s, font=f_axis)
        draw.text((plot_left - 24 - (bbox[2] - bbox[0]), ty - (bbox[3] - bbox[1]) // 2),
                  s, fill=(30, 30, 35), font=f_axis)
    # Y-axis label.
    draw.text((LEFT, plot_top + plot_h // 2 - 14),
              "LF/HF",
              fill=(30, 30, 35), font=f_axis)

    # Filter-warmup band (fix 1-6) — hatched grey region replaces the
    # six null-bar labels that collided in v1.
    warmup_x0 = int(plot_left)
    warmup_x1 = int(plot_left + 6 * bar_w)
    # Hatched fill — diagonal lines.
    for d in range(-plot_h, int(warmup_x1 - warmup_x0), 18):
        draw.line(
            (warmup_x0 + d, plot_top, warmup_x0 + d + plot_h, plot_bot),
            fill=(220, 220, 226), width=2,
        )
    # Border + label.
    draw.rectangle((warmup_x0, plot_top, warmup_x1, plot_bot),
                   outline=(160, 160, 170), width=2)
    draw.text((warmup_x0 + 16, plot_top + 18),
              "filter warmup",
              fill=(80, 80, 90), font=f_chart)
    draw.text((warmup_x0 + 16, plot_top + 56),
              "(fix 1–6, LF/HF undefined)",
              fill=(110, 110, 120), font=f_sub)

    # Bars for fix 7+.
    peak_idx = max(range(n), key=lambda i: fixations[i].get("lfhf") or 0)
    for i, f in enumerate(fixations):
        v = f.get("lfhf")
        if v is None:
            continue  # rendered by warmup band above
        x0 = int(plot_left + i * bar_w + bar_w * 0.12)
        x1 = int(plot_left + (i + 1) * bar_w - bar_w * 0.12)
        h = int((v / y_max_ceil) * plot_h)
        color = (220, 35, 35) if i == peak_idx else (245, 140, 30)
        draw.rectangle((x0, plot_bot - h, x1, plot_bot),
                       fill=color, outline=(0, 0, 0), width=2)

    # X-axis tick labels (fix 1, 6, 10, 16) — sparse, no overprint risk.
    for tick_i in [0, 5, peak_idx, n - 1]:
        x = int(plot_left + tick_i * bar_w + bar_w / 2)
        draw.line((x, plot_bot, x, plot_bot + 8), fill=(40, 40, 40), width=2)
        s = str(tick_i + 1)
        bbox = draw.textbbox((0, 0), s, font=f_axis)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2, plot_bot + 14), s,
                  fill=(30, 30, 35), font=f_axis)
    # X-axis label.
    draw.text(((plot_left + plot_right) // 2 - 60, plot_bot + 50),
              "fixation #",
              fill=(30, 30, 35), font=f_axis)

    # Single peak callout — no per-bar numerics, no rounding drift.
    px = int(plot_left + peak_idx * bar_w + bar_w / 2)
    py = int(plot_bot - (PEAK_LFHF / y_max_ceil) * plot_h)
    draw.line((px, py - 12, px, plot_top + 36),
              fill=(160, 30, 30), width=3)
    draw.text((px + 12, plot_top + 18),
              f"peak {PEAK_LFHF:.2f} at fix {PEAK_FIX}",
              fill=(160, 30, 30), font=f_chart)

    y_cursor = chart_y + CHART_H + GUTTER

    # ── 5. Footer caption ───────────────────────────────────────────
    foot_y = y_cursor
    draw.rectangle((0, foot_y, CONTENT_W, foot_y + FOOTER_H),
                   fill=(255, 255, 255))
    draw.line((0, foot_y, CONTENT_W, foot_y), fill=(60, 60, 60), width=2)
    draw.text((LEFT, foot_y + 22),
              "The user evaluated the cheapest hose (€5.71, fix 6–11) at high",
              fill=(40, 40, 50), font=f_b)
    draw.text((LEFT, foot_y + 58),
              "cognitive load — then committed to a different result (€17.38) 33 s later.",
              fill=(40, 40, 50), font=f_b)

    canvas.save(out_path, optimize=True)
    return out_path


def main():
    print("capturing base render...")
    raw, fixations = asyncio.run(capture_base())
    print(f"  fixations in window: {len(fixations)}")
    out = annotate(raw, fixations, OUT_DIR / "p045_evaluate_reject_story.png")
    im = Image.open(out)
    print(f"  → {out}  size: {im.size}")


if __name__ == "__main__":
    main()
