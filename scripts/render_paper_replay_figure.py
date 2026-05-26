"""Render the methods paper hero figure: same gaze sequence under two color codings.

Drives the existing AF site (`site/<trial>.html`) via Playwright. For each
trial, captures the SERP container (1280×3435 image stack with gazeplot
overlay) twice — once with the default `sequence` color mode, once with
`lfhf` color mode — and composites a 2-row × N-column grid.

Output: `scripts/output/paper-output/figure_replay_lfhf.png` plus
`scripts/output/paper-output/figure_replay_lfhf_<trial>_<mode>.png`
per-trial intermediates.

Usage:
    python3 scripts/render_paper_replay_figure.py
    python3 scripts/render_paper_replay_figure.py --trials p020-b6-t10 p035-b4-t2 p045-b2-t6
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
OUT_DIR = REPO_ROOT / "scripts" / "output" / "paper-output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TRIALS = ["p035-b4-t2", "p016-b3-t1", "p045-b2-t6"]
COLOR_MODES = ["sequence", "load", "lfhf", "ripa2", "saliency"]


async def capture_trial(playwright, trial: str, mode: str, scroll_y: int = 0,
                         viewport_h: int = 1100, window_seconds: float | None = None,
                         bg_mode: str = "serp") -> Path:
    """Open trial HTML, set color mode, capture viewer region as PNG.

    bg_mode: 'serp' hides the gazeplot heatmap overlay (clean SERP background
    suitable for paper figures); 'gazeplot' keeps the heatmap (default in the
    site UI but smears the SERP).

    window_seconds: if not None, only show fixations whose time-from-first
    falls within this window. Implemented by computing the cutoff fixation
    index from F[].t and setting ci + ws.value accordingly.
    """
    html_path = SITE_DIR / f"{trial}.html"
    if not html_path.exists():
        raise FileNotFoundError(f"trial HTML missing: {html_path}")

    browser = await playwright.chromium.launch()
    context = await browser.new_context(
        viewport={"width": 1300, "height": viewport_h},
        device_scale_factor=2,
    )
    page = await context.new_page()
    await page.goto(html_path.as_uri())
    await page.wait_for_load_state("networkidle")
    await page.wait_for_function("typeof F !== 'undefined' && F.length > 0")

    # Switch background mode. Default site state is 'gazeplot' (heatmap on);
    # 'serp' gives a clean SERP image which is what we want for paper figures.
    # Sidestep setMode() because some trial pages lack #prog-btn and the
    # function dereferences it unconditionally — we only need to hide the
    # heatmap overlay for clean-SERP mode.
    if bg_mode == "serp":
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

    # Cycle color button until colorMode matches `mode`.
    target_idx = COLOR_MODES.index(mode)
    for _ in range(len(COLOR_MODES) + 1):
        current = await page.evaluate("colorMode")
        if current == COLOR_MODES[target_idx]:
            break
        await page.click("#color-btn")
        await page.wait_for_timeout(80)

    # Apply time-window if requested. The slider is in fixation-count units;
    # we compute the index whose F[i].t - T0 just exceeds window_seconds*1000
    # and clamp ci + ws.value so only the first wn fixations render.
    if window_seconds is not None:
        window_ms = int(window_seconds * 1000)
        await page.evaluate(f"""
            (() => {{
                const cut_ms = {window_ms};
                let idx = F.length - 1;
                for (let i = 0; i < F.length; i++) {{
                    if (F[i].t - T0 > cut_ms) {{ idx = Math.max(0, i - 1); break; }}
                }}
                ci = idx;
                const slider = document.getElementById('window-size');
                slider.value = idx + 1;
                document.getElementById('ws-label').textContent =
                    (idx + 1) >= N ? 'All' : (idx + 1);
                if (typeof uv === 'function') uv();
            }})()
        """)
        await page.wait_for_timeout(150)

    # Force a recolor pass for the chosen colorMode.
    await page.evaluate("typeof recolor === 'function' && recolor()")
    await page.wait_for_timeout(200)

    # Scroll the viewer to the requested y.
    await page.evaluate(f"document.getElementById('viewer').scrollTop = {scroll_y}")
    await page.wait_for_timeout(150)

    viewer = await page.query_selector("#viewer")
    suffix = mode if window_seconds is None else f"{mode}_w{int(window_seconds)}s"
    out = OUT_DIR / f"figure_replay_lfhf_{trial}_{suffix}.png"
    await viewer.screenshot(path=str(out))
    await browser.close()
    return out


async def render_all(trials: list[str], scroll_y: int,
                     window_seconds: float | None, bg_mode: str) -> dict:
    from playwright.async_api import async_playwright
    out: dict[tuple[str, str], Path] = {}
    async with async_playwright() as p:
        for t in trials:
            for mode in ("sequence", "lfhf"):
                path = await capture_trial(
                    p, t, mode, scroll_y=scroll_y,
                    window_seconds=window_seconds, bg_mode=bg_mode,
                )
                out[(t, mode)] = path
                w_tag = f" / {int(window_seconds)}s" if window_seconds else ""
                print(f"  captured {t} / {mode}{w_tag}")
    return out


def _draw_gradient_bar(draw, x0, y0, x1, y1, stops):
    """Draw a horizontal gradient bar by interpolating between stops.
    stops = [(t0, (r,g,b)), (t1, (r,g,b)), ...] with t in [0,1]."""
    w = x1 - x0
    for px in range(w):
        t = px / max(1, w - 1)
        # Find segment
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0) if t1 > t0 else 0
                color = tuple(int(c0[k] + (c1[k] - c0[k]) * u) for k in range(3))
                break
        else:
            color = stops[-1][1]
        draw.line((x0 + px, y0, x0 + px, y1), fill=color)


def composite_grid(captures: dict, trials: list[str], out_path: Path,
                   pad: int = 12, header_h: int = 280, footer_h: int = 320) -> Path:
    """N rows × 2 cols, tightly packed. Each row is one trial; left = temporal,
    right = LFHF. Bold column-header strip at top; trial IDs as inline badges
    in the panel corner. Fonts scaled for 2× device-scale capture so they read
    clearly when the figure is rendered at paper-figure dpi."""
    panels = {key: Image.open(p) for key, p in captures.items()}
    sample = next(iter(panels.values()))
    pw, ph = sample.size
    n = len(trials)

    grid_w = 2 * pw + 3 * pad
    grid_h = header_h + n * ph + (n + 1) * pad + footer_h
    canvas = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Helvetica-Bold.ttc does NOT exist on macOS; Pillow silently falls back
    # to a 10px bitmap font when load fails. Use Arial Bold (always present
    # under Supplemental/) so text actually renders at the requested size.
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]

    def _load(size):
        for p in font_paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        return ImageFont.load_default()

    font_h = _load(180)
    font_badge = _load(110)
    font_legend = _load(90)
    font_legend_small = _load(72)

    # Header strip — light gray fill so it reads as a header band, not whitespace.
    draw.rectangle((0, 0, grid_w, header_h), fill=(232, 234, 238))

    # Column headers — bold, large, dark. Vertically centered.
    header_text_y = (header_h - 180) // 2 - 8
    draw.text((pad + 32, header_text_y),
              "Temporal coding",
              fill=(20, 20, 25), font=font_h)
    draw.text((pad + pw + pad + 32, header_text_y),
              "LF/HF coding (cognitive load)",
              fill=(20, 20, 25), font=font_h)

    # Header bottom rule.
    draw.line(
        (0, header_h - 1, grid_w, header_h - 1),
        fill=(60, 60, 60), width=6,
    )

    y_cursor = header_h + pad
    for i, t in enumerate(trials):
        canvas.paste(panels[(t, "sequence")], (pad, y_cursor))
        canvas.paste(panels[(t, "lfhf")], (pad + pw + pad, y_cursor))

        # Trial-ID badge — bottom-left corner of left panel, well clear of the
        # SERP search bar and the first scan-path glyphs (which cluster top).
        bbox_t = draw.textbbox((0, 0), t, font=font_badge)
        text_w = bbox_t[2] - bbox_t[0]
        text_h = bbox_t[3] - bbox_t[1]
        bw = text_w + 36
        bh = text_h + 28
        bx = pad + 24
        by = y_cursor + ph - bh - 24
        draw.rectangle(
            (bx, by, bx + bw, by + bh),
            fill=(255, 255, 255), outline=(20, 20, 20), width=5,
        )
        draw.text((bx + 18, by + 8), t, fill=(15, 15, 15), font=font_badge)

        y_cursor += ph + pad

    # ── Footer with color legends ─────────────────────────────────────
    # Same gray strip as header, two gradient bars (one per column).
    footer_top = grid_h - footer_h
    draw.rectangle((0, footer_top, grid_w, grid_h), fill=(232, 234, 238))
    draw.line((0, footer_top, grid_w, footer_top), fill=(60, 60, 60), width=6)

    # Stops sourced from site/<trial>.html cF and cLFHF functions:
    # cF: t=0 → (50,50,255) blue;  t=0.5 → (152,150,152) gray;  t=1 → (255,50,50) red
    # cLFHF: t=0 → (200,160,40) amber;  t=1 → (255,50,10) red
    temporal_stops = [(0.0, (50, 50, 255)), (0.5, (152, 150, 152)), (1.0, (255, 50, 50))]
    lfhf_stops = [(0.0, (200, 160, 40)), (1.0, (255, 50, 10))]

    bar_h = 90
    bar_y0 = footer_top + 60
    bar_y1 = bar_y0 + bar_h
    label_y = bar_y1 + 24

    # Left column legend — Temporal
    bar_x0 = pad + 32
    bar_x1 = pad + pw - 32
    _draw_gradient_bar(draw, bar_x0, bar_y0, bar_x1, bar_y1, temporal_stops)
    draw.rectangle((bar_x0, bar_y0, bar_x1, bar_y1), outline=(40, 40, 40), width=4)
    draw.text((bar_x0, label_y), "fixation 1", fill=(20, 20, 25), font=font_legend)
    bbox_t = draw.textbbox((0, 0), "last fixation", font=font_legend)
    text_w = bbox_t[2] - bbox_t[0]
    draw.text((bar_x1 - text_w, label_y), "last fixation",
              fill=(20, 20, 25), font=font_legend)
    # Mid label
    mid_text = "(diverging — rainbow time order)"
    bbox_m = draw.textbbox((0, 0), mid_text, font=font_legend_small)
    mid_w = bbox_m[2] - bbox_m[0]
    draw.text((bar_x0 + (bar_x1 - bar_x0 - mid_w) // 2, label_y + 110),
              mid_text, fill=(80, 80, 90), font=font_legend_small)

    # Right column legend — LF/HF
    bar_x0 = pad + pw + pad + 32
    bar_x1 = pad + pw + pad + pw - 32
    _draw_gradient_bar(draw, bar_x0, bar_y0, bar_x1, bar_y1, lfhf_stops)
    draw.rectangle((bar_x0, bar_y0, bar_x1, bar_y1), outline=(40, 40, 40), width=4)
    draw.text((bar_x0, label_y), "low load", fill=(20, 20, 25), font=font_legend)
    bbox_t = draw.textbbox((0, 0), "high load", font=font_legend)
    text_w = bbox_t[2] - bbox_t[0]
    draw.text((bar_x1 - text_w, label_y), "high load",
              fill=(20, 20, 25), font=font_legend)
    mid_text = "(sequential — pupillometric LF/HF magnitude)"
    bbox_m = draw.textbbox((0, 0), mid_text, font=font_legend_small)
    mid_w = bbox_m[2] - bbox_m[0]
    draw.text((bar_x0 + (bar_x1 - bar_x0 - mid_w) // 2, label_y + 110),
              mid_text, fill=(80, 80, 90), font=font_legend_small)

    canvas.save(out_path, optimize=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", nargs="+", default=DEFAULT_TRIALS,
                    help="trial IDs from site/<trial>.html (must have lfhf data)")
    ap.add_argument("--scroll", type=int, default=0,
                    help="scrollTop for the #viewer (px)")
    ap.add_argument("--window-seconds", type=float, default=None,
                    help="limit fixations to first N seconds of trial")
    ap.add_argument("--bg-mode", choices=("serp", "gazeplot"), default="serp",
                    help="serp = clean SERP background; gazeplot = with heatmap overlay")
    ap.add_argument("--out", type=str, default=str(OUT_DIR / "figure_replay_lfhf.png"))
    args = ap.parse_args()

    captures = asyncio.run(render_all(
        args.trials, args.scroll,
        window_seconds=args.window_seconds, bg_mode=args.bg_mode,
    ))
    out = composite_grid(captures, args.trials, Path(args.out))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
