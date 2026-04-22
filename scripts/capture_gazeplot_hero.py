#!/usr/bin/env python3
"""
Capture the README foveated-gazeplot hero from the live viewer.

Screenshots the interactive cursor-plot page with all overlays visible
(scanpath SVG, recency glow, timeline tracks) so the README hero shows
what the actual tool renders — not a bare foveated background.

Source: https://andyed.github.io/attentional-foraging/p029-b2-t10.html
Output: assets/gazeplot-hero.png (+ _sm.png at 75% linear).

The viewer defaults to ``ci=N-1`` (all fixations visible, paused).
We reload, scroll to top, wait for images + fonts, then clip to the
viewer region.

STYLE RULES (muriel universal):
    - 8:1 contrast minimum on all text. Verified against matte.
    - Reproducible: re-run after upstream viewer changes.
    - Measure before drawing: bbox the clip region from the DOM.
    - No thin fonts, no emoji.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://andyed.github.io/attentional-foraging/p029-b2-t10.html'
TRIAL_ID = 'p029-b2-t10'

RAW_CAPTURE = ROOT / 'assets' / '.gazeplot-hero-raw.png'
OUT = ROOT / 'assets' / 'gazeplot-hero.png'
OUT_SM = ROOT / 'assets' / 'gazeplot-hero_sm.png'

MATTE = (248, 246, 240)
TEXT_PRIMARY = (17, 24, 39)
TEXT_SOFT = (26, 26, 26)
GREEN = (47, 107, 47)

# Target viewport-height crop (px of the 1280-wide viewer column)
CROP_WIDTH = 1280
CROP_HEIGHT = 1024


def load_font(size, *, bold=False):
    candidates = [
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold
        else '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={'width': 1440, 'height': 1600},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.goto(URL, wait_until='networkidle', timeout=60_000)
        page.wait_for_selector('#serp-img', state='attached')
        page.wait_for_function(
            "document.getElementById('serp-img').complete"
            " && document.getElementById('scanpath-svg').children.length > 0",
            timeout=30_000,
        )
        # Force viewer state: all fixations visible, paused, scrolled to top.
        # vw is the #viewer scrolling container (bound in the viewer JS).
        page.evaluate(
            "() => {"
            "  if (typeof pl !== 'undefined' && pl) {"
            "    document.getElementById('play-btn').click();"
            "  }"
            "  const btn = document.getElementById('reset-btn');"
            "  if (btn) btn.click();"
            "  const viewer = document.getElementById('viewer');"
            "  if (viewer) viewer.scrollTop = 0;"
            "  window.scrollTo(0, 0);"
            "}"
        )
        page.wait_for_timeout(400)
        # Clip spans top of #viewer through bottom of .timeline, full width.
        box = page.evaluate(
            "() => {"
            "  const v = document.getElementById('viewer').getBoundingClientRect();"
            "  const tEls = document.getElementsByClassName('timeline');"
            "  const t = tEls.length ? tEls[0].getBoundingClientRect() : v;"
            "  return {"
            "    x: v.left,"
            "    y: v.top,"
            "    width: v.width,"
            "    height: (t.bottom - v.top),"
            "  };"
            "}"
        )
        clip = {
            'x': max(0, box['x']),
            'y': max(0, box['y']),
            'width': box['width'],
            'height': box['height'],
        }
        RAW_CAPTURE.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(RAW_CAPTURE), clip=clip)
        browser.close()


def compose():
    raw = Image.open(RAW_CAPTURE).convert('RGB')
    rw, rh = raw.size
    # Target panel at 2x device scale → fit to 1500x820 for parity with prior hero
    PANEL_W, PANEL_H = 1500, 820
    target_aspect = PANEL_W / PANEL_H
    src_aspect = rw / rh
    if src_aspect > target_aspect:
        new_w = PANEL_W
        new_h = int(PANEL_W / src_aspect)
    else:
        new_h = PANEL_H
        new_w = int(PANEL_H * src_aspect)
    panel = Image.new('RGB', (PANEL_W, PANEL_H), MATTE)
    resized = raw.resize((new_w, new_h), Image.LANCZOS)
    panel.paste(resized, ((PANEL_W - new_w) // 2, (PANEL_H - new_h) // 2))

    MARGIN = 20
    TITLE_H = 48
    CAPTION_H = 34
    CW = PANEL_W + MARGIN * 2
    CH = TITLE_H + PANEL_H + CAPTION_H + MARGIN * 2
    canvas = Image.new('RGB', (CW, CH), MATTE)
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(30, bold=True)
    sub_font = load_font(20, bold=False)
    cap_font = load_font(16, bold=True)

    draw.text((MARGIN, MARGIN),
              'Foveated cursor plot',
              fill=GREEN, font=title_font)
    draw.text((MARGIN + 316, MARGIN + 6),
              f'· live viewer · trial {TRIAL_ID}',
              fill=TEXT_SOFT, font=sub_font)

    canvas.paste(panel, (MARGIN, MARGIN + TITLE_H))

    cap_y = MARGIN + TITLE_H + PANEL_H + 8
    draw.text(
        (MARGIN, cap_y),
        'Scrutinizer LGN/V1/DoG background + DOM-anchored scanpath, '
        'recency glow on last 5 fixations, multi-track cognitive timeline.',
        fill=TEXT_PRIMARY, font=cap_font,
    )

    canvas.save(OUT, optimize=True)
    print(f'Wrote {OUT} ({canvas.size})')

    sm = canvas.resize((int(CW * 0.75), int(CH * 0.75)), Image.LANCZOS)
    sm.save(OUT_SM, optimize=True)
    print(f'Wrote {OUT_SM} ({sm.size})')


def main():
    capture()
    compose()


if __name__ == '__main__':
    main()
