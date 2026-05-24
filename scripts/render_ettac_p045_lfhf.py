"""ETTAC paper asset: p045-b2-t6 LF/HF-coded gaze, full trial.

Standalone single-panel render. Foundational figure for the ETTAC argument
that LF/HF cleanly separates the OSEC survey phase (uniformly low load on
fixations 1–5) from the deliberation phase, and that within deliberation
LF/HF spikes on reapproach to a previously-rejected result (fixation 10
in this trial: LF/HF=54.85, the peak across the first 12 fixations and
~3× the surrounding values).

Output: scripts/output/ettac/p045_lfhf_full.png
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
TRIAL = "p045-b2-t6"
SITE = REPO / "site" / f"{TRIAL}.html"
OUT_DIR = REPO / "scripts" / "output" / "ettac"
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def render(window_ms: tuple[int, int] = (0, 10000),
                  cursor_through_click: bool = True,
                  out_basename: str = "p045_lfhf"):
    """Render one frame.
    window_ms: (start_ms, end_ms) for the gaze fixations.
    cursor_through_click: if True, cursor trail extends through first
        click event regardless of window (gives the trail somewhere to land).
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1300, "height": 1100},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(SITE.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.wait_for_function("typeof F !== 'undefined' && F.length > 0")

        # Hide gazeplot heatmap; clean SERP background.
        await page.evaluate("""
            (() => {
                const gp = document.getElementById('gazeplot-img');
                if (gp) gp.style.display = 'none';
                const pc = document.getElementById('prog-canvas');
                if (pc) pc.style.display = 'none';
                if (typeof bgMode !== 'undefined') bgMode = 'serp';
            })()
        """)
        await page.wait_for_timeout(120)

        # Cycle to LFHF color mode.
        target = "lfhf"
        modes = ["sequence", "load", "lfhf", "ripa2", "saliency"]
        for _ in range(len(modes) + 1):
            cur = await page.evaluate("colorMode")
            if cur == target:
                break
            await page.click("#color-btn")
            await page.wait_for_timeout(80)

        # Window to [start_ms, end_ms]. Fixations outside the window are
        # hidden via the existing slider mechanism; we set ci = end_idx and
        # ws.value = end_idx - start_idx + 1 so only fixations in the
        # window's tail render.
        win_start, win_end = window_ms
        await page.evaluate(f"""
            (() => {{
                const start_ms = {win_start};
                const end_ms = {win_end};
                let start_idx = 0, end_idx = F.length - 1;
                for (let i = 0; i < F.length; i++) {{
                    if (F[i].t - T0 < start_ms) start_idx = i + 1;
                    if (F[i].t - T0 > end_ms) {{ end_idx = Math.max(0, i - 1); break; }}
                }}
                start_idx = Math.min(start_idx, F.length - 1);
                end_idx = Math.max(end_idx, start_idx);
                ci = end_idx;
                const wn = end_idx - start_idx + 1;
                const slider = document.getElementById('window-size');
                slider.value = wn;
                document.getElementById('ws-label').textContent =
                    wn >= N ? 'All' : wn;
                if (typeof uv === 'function') uv();
            }})()
        """)
        await page.wait_for_timeout(150)
        await page.evaluate("typeof recolor === 'function' && recolor()")
        await page.wait_for_timeout(200)

        # Auto-scroll the viewer so the fixation centroid is centered.
        # Source coords are in 1280×3435 serp space; the viewer is 70vh.
        # Compute centroid_y of fixations in window and scroll to put it
        # at viewer-center.
        await page.evaluate(f"""
            (() => {{
                const win_start = {win_start};
                const win_end = {win_end};
                const winFix = F.filter(f => {{
                    const t = f.t - T0;
                    return t >= win_start && t <= win_end;
                }});
                if (winFix.length === 0) return;
                const cy = winFix.reduce((s, f) => s + f.y, 0) / winFix.length;
                const v = document.getElementById('viewer');
                const target = Math.max(0, Math.round(cy - v.clientHeight / 2));
                v.scrollTop = target;
            }})()
        """)
        await page.wait_for_timeout(150)

        # Bump in-SVG fixation-number font size so offset numerals are
        # legible at paper render rez. The site uses 9–14 px per glyph.
        # Also enlarge the fixation circles by +50% so the LFHF color fill
        # still reads beyond the numeral; a too-thick stroke around the
        # text was obscuring the circle's color (Andy 2026-05-09).
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
                        // Skip the fix-10 callout ring (>60). Bump scanpath circles 1.5×.
                        c.setAttribute('r', r * 1.5);
                        c.setAttribute('fill-opacity', 0.45);
                        c.setAttribute('stroke-width', 3);
                    }
                });
            })()
        """)
        await page.wait_for_timeout(120)

        # Pull fixation positions for the active window. Coordinates are in
        # source SVG/serp space (1280 wide); device-scale-factor 2 means
        # we'll scale up by 2 for pixel coordinates in the PNG.
        fixations = await page.evaluate(f"""
            F.filter(f => {{
                const t = f.t - T0;
                return t >= {win_start} && t <= {win_end};
            }}).map(f => ({{t: f.t - T0, x: f.x, y: f.y, lfhf: f.lfhf}}))
        """)

        # Cursor (mouse) trajectory in the same window as the gaze fixations,
        # PLUS a tail extension up to the first click event if the click
        # falls just past the window end (so the trail shows where the
        # commit landed). For two-frame mode the windows are tight and the
        # commit frame already contains the click, so the tail extension
        # is a no-op in that case.
        cursor = await page.evaluate(f"""
            (() => {{
                const win_start = {win_start};
                const win_end = {win_end};
                let click_t = win_end;
                for (const m of ME) {{
                    if (m.e === 'mousedown' || m.e === 'click') {{
                        click_t = m.t;
                        break;
                    }}
                }}
                const tail_end = {1 if cursor_through_click else 0}
                    ? Math.max(win_end, click_t + 200)
                    : win_end;
                return ME
                    .filter(m => m.t >= win_start && m.t <= tail_end)
                    .map(m => ({{t: m.t, x: m.x, y: m.y, e: m.e}}));
            }})()
        """)

        scroll_top = await page.evaluate("document.getElementById('viewer').scrollTop")
        viewer = await page.query_selector("#viewer")
        raw_path = OUT_DIR / f"p045_lfhf_raw_{win_start}_{win_end}.png"
        await viewer.screenshot(path=str(raw_path))
        await browser.close()
        return raw_path, fixations, cursor, int(scroll_top)


def annotate(raw_path: Path, fixations: list, cursor: list, out_path: Path,
              draw_cursor: bool = True, bare: bool = False,
              scroll_top: int = 0):
    """Add ETTAC-specific annotations: survey-phase bracket and fixation-10 callout."""
    im = Image.open(raw_path).convert("RGB")
    pw, ph = im.size

    # In `bare` mode (used by the two-frame composite which provides its
    # own labels), skip the header/footer bands — caller will compose them.
    header_h = 0 if bare else 140
    footer_h = 0 if bare else 220
    canvas_w = pw
    canvas_h = header_h + ph + footer_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    canvas.paste(im, (0, header_h))

    draw = ImageDraw.Draw(canvas)

    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font_paths_reg = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    def _load(paths, sz):
        for p in paths:
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    font_h = _load(font_paths, 80)
    font_b = _load(font_paths_reg, 50)
    font_callout = _load(font_paths, 56)

    if not bare:
        draw.rectangle((0, 0, canvas_w, header_h), fill=(232, 234, 238))
        draw.line((0, header_h - 1, canvas_w, header_h - 1), fill=(60, 60, 60), width=4)
        draw.text((40, 28), f"{TRIAL} — gaze sequence with LF/HF cognitive-load coding",
                  fill=(15, 15, 15), font=font_h)
        foot_y = header_h + ph
        draw.rectangle((0, foot_y, canvas_w, canvas_h), fill=(248, 248, 250))
        draw.line((0, foot_y, canvas_w, foot_y), fill=(60, 60, 60), width=4)
        cap1 = "Fixations 1–6: LF/HF undefined (Butterworth filter warmup). Survey-phase low-load is documented separately via −3% pupil constriction, p=10⁻¹¹⁷ [findings.md §3b-iii]."
        cap2 = "Fixations 7–12 (deliberation): LF/HF rises sharply to peak 54.85 at fixation 10 — reapproach to a previously-rejected result."
        draw.text((40, foot_y + 30), cap1, fill=(20, 20, 25), font=font_b)
        draw.text((40, foot_y + 110), cap2, fill=(20, 20, 25), font=font_b)

    # Annotate the SERP image area:
    #   - Bracket-style label over fixations 1-5 saying "survey (low load)"
    #   - Arrow + text callout pointing to fixation 10
    # Coordinates: F.x / F.y are in serp-image space (1280×3435 source).
    # The viewer screenshot is at device-scale-factor=2, so pixel coords
    # in the PNG are 2× the source. Viewer scrollTop=0 so y_serp_in_image = 2*y_source.
    # Header offset: we pasted the image at y=header_h.
    sx = lambda x: int(2 * x)
    sy = lambda y: int(2 * (y - scroll_top)) + header_h

    # ── Cursor trail overlay ───────────────────────────────────────
    # Drawn BEFORE fixation annotations so that scanpath rings sit on top.
    if draw_cursor and cursor:
        pts = [(sx(c["x"]), sy(c["y"])) for c in cursor]
        # Light gray cursor trail — direction conveyed by an arrow at the
        # terminal sample, not by labels. Trail itself sits behind fixations.
        if len(pts) >= 2:
            draw.line(pts, fill=(110, 110, 110), width=4, joint="curve")
        # Terminal arrowhead pointing along the last segment. Direction is
        # toward the click target (we extended `cursor` past the 10s gaze
        # window through the first mousedown).
        if len(pts) >= 2:
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            import math
            dx, dy = x1 - x0, y1 - y0
            mag = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / mag, dy / mag
            tip = (x1 + ux * 14, y1 + uy * 14)
            wing = 40
            perp = (-uy, ux)
            base = (x1 - ux * wing, y1 - uy * wing)
            left = (base[0] + perp[0] * wing * 0.6,
                    base[1] + perp[1] * wing * 0.6)
            right = (base[0] - perp[0] * wing * 0.6,
                     base[1] - perp[1] * wing * 0.6)
            draw.polygon([tip, left, right], fill=(40, 40, 40),
                         outline=(0, 0, 0))

    # Annotations intentionally omitted — Andy 2026-05-09: the blue cluster
    # and orange spike read at-a-glance, precision location is not needed.
    # Caption references fixation offset numerals (boosted to 26 px bold in
    # the in-SVG render before capture).

    canvas.save(out_path, optimize=True)
    return out_path


def composite_two_frames(left_path, right_path, out_path,
                          left_label, right_label, pad=20):
    """Side-by-side composite of two frames with a top label band."""
    L = Image.open(left_path)
    R = Image.open(right_path)
    pw, ph = L.size
    # Resize R to match L's height if they differ slightly.
    if R.size[1] != ph:
        R = R.resize((int(R.size[0] * ph / R.size[1]), ph), Image.LANCZOS)

    label_h = 110
    canvas_w = pw + R.size[0] + 3 * pad
    canvas_h = ph + label_h + pad
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    def _load(sz):
        for p in font_paths:
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                continue
        return ImageFont.load_default()
    font_h = _load(80)

    # Header band
    draw.rectangle((0, 0, canvas_w, label_h), fill=(232, 234, 238))
    draw.line((0, label_h - 1, canvas_w, label_h - 1), fill=(60, 60, 60), width=4)
    draw.text((pad + 12, 18), left_label, fill=(15, 15, 15), font=font_h)
    draw.text((pad + pw + pad + 12, 18), right_label,
              fill=(15, 15, 15), font=font_h)

    canvas.paste(L, (pad, label_h + 4))
    canvas.paste(R, (pad + pw + pad, label_h + 4))
    canvas.save(out_path, optimize=True)
    return out_path


def main():
    # Two-frame composition — approach + commit.
    print("=== Frame A: approach (0–3 s, fixations through reapproach-rejected spike) ===")
    raw_a, fix_a, cur_a, scroll_a = asyncio.run(
        render(window_ms=(0, 3000), cursor_through_click=False))
    print(f"  cursor samples extending through click: {len(cur_a)}")
    print(f"  fixations in window: {len(fix_a)}")
    out_a = annotate(raw_a, fix_a, cur_a,
                     OUT_DIR / "p045_lfhf_approach.png",
                     draw_cursor=True, bare=True, scroll_top=scroll_a)

    print("\n=== Frame B: commit (32–36 s, fixations leading to click) ===")
    raw_b, fix_b, cur_b, scroll_b = asyncio.run(
        render(window_ms=(32000, 36000), cursor_through_click=True))
    print(f"  cursor samples extending through click: {len(cur_b)}")
    print(f"  fixations in window: {len(fix_b)}")
    out_b = annotate(raw_b, fix_b, cur_b,
                     OUT_DIR / "p045_lfhf_commit.png",
                     draw_cursor=True, bare=True, scroll_top=scroll_b)

    composite = composite_two_frames(
        out_a, out_b, OUT_DIR / "p045_lfhf_two_frame.png",
        left_label="Approach (0–3 s) — reapproach-rejected LF/HF spike",
        right_label="Commit (32–36 s) — calm fixations toward click",
    )
    print(f"\nside-by-side: {composite}")
    print("\nframe A fixations:")
    for i, f in enumerate(fix_a):
        lfhf = f.get("lfhf")
        lfhf_s = f"{lfhf:.2f}" if lfhf is not None else "  null"
        print(f"  fix {i+1:2d}: t={f['t']/1000:5.2f}s  ({f['x']:.0f},{f['y']:.0f})  LF/HF={lfhf_s}")
    print("\nframe B fixations:")
    for i, f in enumerate(fix_b):
        lfhf = f.get("lfhf")
        lfhf_s = f"{lfhf:.2f}" if lfhf is not None else "  null"
        print(f"  fix {i+1:2d}: t={f['t']/1000:5.2f}s  ({f['x']:.0f},{f['y']:.0f})  LF/HF={lfhf_s}")


if __name__ == "__main__":
    main()
