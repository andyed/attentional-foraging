"""Preview evaluate-reject LF/HF spike candidates side by side.

Three candidates centered on the spike fixation:
- p037-b2-t5: peak LF/HF 447 at fix 16 (~4.3 s), 38 reject-spikes
- p020-b6-t10: peak 429 at fix 67 (~22.7 s), click 2,892 px away
- p016-b3-t1: peak 420 at fix 52 (~15.5 s), 13 reject-spikes
- p045-b2-t6: peak 103 at fix 10 (~1.5 s) — current ETTAC primary, included for comparison

Each panel auto-scrolls the viewer to the spike-fixation centroid and
windows fixations to a tight ~6 s slice around the peak.

Output: scripts/output/ettac/preview_evaluate_reject_candidates.png
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT_DIR = REPO / "scripts" / "output" / "ettac"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (trial_id, window_start_ms, window_end_ms, label)
CANDIDATES = [
    ("p037-b2-t5", 1500, 7000, "peak 447, fix 16 @ 4.3 s · 523 px from click"),
    ("p020-b6-t10", 19000, 26000, "peak 429, fix 67 @ 22.7 s · 2,892 px from click"),
    ("p016-b3-t1", 12000, 19000, "peak 420, fix 52 @ 15.5 s · 780 px from click"),
    ("p045-b2-t6", 0, 3000, "peak 103, fix 10 @ 1.5 s · current ETTAC primary"),
]


async def capture(trial: str, win_start: int, win_end: int) -> tuple[Path, int]:
    from playwright.async_api import async_playwright
    html = SITE / f"{trial}.html"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1300, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto(html.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.wait_for_function("typeof F !== 'undefined' && F.length > 0")

        # Hide gazeplot heatmap.
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

        # Switch to LFHF coloring.
        modes = ["sequence", "load", "lfhf", "ripa2", "saliency"]
        for _ in range(len(modes) + 1):
            cur = await page.evaluate("colorMode")
            if cur == "lfhf":
                break
            await page.click("#color-btn")
            await page.wait_for_timeout(60)

        # Window the slider + auto-scroll.
        await page.evaluate(f"""
            (() => {{
                const ws = {win_start};
                const we = {win_end};
                let s = 0, e = F.length - 1;
                for (let i = 0; i < F.length; i++) {{
                    if (F[i].t - T0 < ws) s = i + 1;
                    if (F[i].t - T0 > we) {{ e = Math.max(0, i - 1); break; }}
                }}
                s = Math.min(s, F.length - 1);
                e = Math.max(e, s);
                ci = e;
                const wn = e - s + 1;
                const slider = document.getElementById('window-size');
                slider.value = wn;
                document.getElementById('ws-label').textContent =
                    wn >= N ? 'All' : wn;
                if (typeof uv === 'function') uv();
                // Auto-scroll viewer to fixation centroid in window.
                const win = F.filter(f => {{
                    const t = f.t - T0; return t >= ws && t <= we;
                }});
                if (win.length) {{
                    const cy = win.reduce((a, f) => a + f.y, 0) / win.length;
                    const v = document.getElementById('viewer');
                    v.scrollTop = Math.max(0, Math.round(cy - v.clientHeight / 2));
                }}
            }})()
        """)
        await page.wait_for_timeout(180)
        await page.evaluate("typeof recolor === 'function' && recolor()")
        await page.wait_for_timeout(120)

        # Bump fixation numerals + circles for legibility.
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
        await page.wait_for_timeout(80)

        scroll_top = await page.evaluate("document.getElementById('viewer').scrollTop")
        viewer = await page.query_selector("#viewer")
        out = OUT_DIR / f"preview_lfhf_{trial}.png"
        await viewer.screenshot(path=str(out))
        await browser.close()
        return out, int(scroll_top)


async def main_async():
    results = []
    for trial, ws, we, label in CANDIDATES:
        print(f"capturing {trial} window {ws/1000:.1f}–{we/1000:.1f} s ...")
        path, scroll = await capture(trial, ws, we)
        results.append((trial, label, path))
    return results


def composite(results, out_path: Path):
    panels = [(t, label, Image.open(p)) for t, label, p in results]
    sample = panels[0][2]
    pw, ph = sample.size
    # 2 rows × 2 cols.
    pad = 16
    label_h = 110
    cols = 2
    rows = 2
    grid_w = cols * pw + (cols + 1) * pad
    grid_h = rows * (ph + label_h) + (rows + 1) * pad
    canvas = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    fp = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
          "/System/Library/Fonts/Helvetica.ttc"]
    fp_reg = ["/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]
    def _ld(paths, sz):
        for p in paths:
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    font_h = _ld(fp, 56)
    font_b = _ld(fp_reg, 38)

    for i, (trial, label, im) in enumerate(panels):
        row, col = i // cols, i % cols
        x = pad + col * (pw + pad)
        y = pad + row * (ph + label_h + pad)
        # Trial label band.
        draw.rectangle((x, y, x + pw, y + label_h), fill=(232, 234, 238))
        draw.line((x, y + label_h - 1, x + pw, y + label_h - 1),
                   fill=(60, 60, 60), width=3)
        draw.text((x + 16, y + 12), trial, fill=(15, 15, 15), font=font_h)
        draw.text((x + 16, y + 64), label, fill=(60, 60, 70), font=font_b)
        canvas.paste(im, (x, y + label_h))

    canvas.save(out_path, optimize=True)
    return out_path


def main():
    results = asyncio.run(main_async())
    out = composite(results, OUT_DIR / "preview_evaluate_reject_candidates.png")
    print(f"\npreview grid: {out}")


if __name__ == "__main__":
    main()
