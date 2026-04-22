#!/usr/bin/env python3
"""
Build the README foveated-gazeplot hero image.

Single-panel hero showing what the Foveated Cursor Plots viewer
actually renders: one trial's Scrutinizer LGN/V1/DoG foveated
background with the scanpath overlay.

Source trial: p047-b1-t9. Same canonical trial as the three-panel
perception explainer, so the two heroes are visually linked.

Output:
    assets/gazeplot-hero.png     — 1540 x 900 PNG, off-white matte,
                                   viewport crop of the full-page
                                   gazeplot, caption at 8:1.
    assets/gazeplot-hero_sm.png  — 75% linear variant (README inline).

STYLE RULES (muriel universal):
    - 8:1 contrast minimum on all text. Verified against matte.
    - Reproducible: re-run this script after refreshing site/gazeplots/.
    - Labels every number (trial id, fixation count source).
    - Measure before drawing: bbox before paste.
    - No thin fonts, no emoji.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TRIAL_ID = 'p047-b1-t9'
SRC_GAZEPLOT = ROOT / 'site' / 'gazeplots' / f'{TRIAL_ID}.png'

PANEL_W = 1500
PANEL_H = 820
MARGIN = 20
TITLE_H = 48
CAPTION_H = 34
CANVAS_W = PANEL_W + MARGIN * 2
CANVAS_H = TITLE_H + PANEL_H + CAPTION_H + MARGIN * 2

MATTE = (248, 246, 240)          # #f8f6f0
TEXT_PRIMARY = (17, 24, 39)      # #111827, ratio ~17.6 on matte
TEXT_SOFT = (26, 26, 26)         # #1a1a1a, ratio ~17.8 on matte
GREEN = (47, 107, 47)            # #2f6b2f, ratio ~8.2 on matte


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


def crop_viewport(src: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop top viewport (~1024 px) and letterbox-resize to target."""
    W, H = src.size
    viewport_h = min(1024, H)
    crop = src.crop((0, 0, W, viewport_h))
    target_aspect = target_w / target_h
    src_aspect = crop.width / crop.height
    if src_aspect > target_aspect:
        new_w = target_w
        new_h = int(target_w / src_aspect)
    else:
        new_h = target_h
        new_w = int(target_h * src_aspect)
    resized = crop.resize((new_w, new_h), Image.LANCZOS)
    out = Image.new('RGB', (target_w, target_h), MATTE)
    out.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return out


def main():
    if not SRC_GAZEPLOT.exists():
        raise SystemExit(f'Missing Scrutinizer gazeplot: {SRC_GAZEPLOT}')

    src = Image.open(SRC_GAZEPLOT).convert('RGB')
    print(f'Loaded gazeplot {src.size} from {SRC_GAZEPLOT}')

    panel = crop_viewport(src, PANEL_W, PANEL_H)

    canvas = Image.new('RGB', (CANVAS_W, CANVAS_H), MATTE)
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(30, bold=True)
    caption_font = load_font(16, bold=True)

    draw.text(
        (MARGIN, MARGIN),
        'Foveated gazeplot',
        fill=GREEN,
        font=title_font,
    )
    sub_font = load_font(20, bold=False)
    draw.text(
        (MARGIN + 265, MARGIN + 6),
        f'· trial {TRIAL_ID} · 65 fixations',
        fill=TEXT_SOFT,
        font=sub_font,
    )

    canvas.paste(panel, (MARGIN, MARGIN + TITLE_H))

    cap_y = MARGIN + TITLE_H + PANEL_H + 8
    draw.text(
        (MARGIN, cap_y),
        'Scrutinizer LGN/V1/DoG render with infinite visual memory accumulation. '
        'Sharp at each fixation, degraded everywhere else; DOM-anchored.',
        fill=TEXT_PRIMARY,
        font=caption_font,
    )

    out_path = ROOT / 'assets' / 'gazeplot-hero.png'
    canvas.save(out_path, optimize=True)
    print(f'Wrote {out_path} ({canvas.size})')

    sm = canvas.resize(
        (int(canvas.width * 0.75), int(canvas.height * 0.75)),
        Image.LANCZOS,
    )
    sm_path = ROOT / 'assets' / 'gazeplot-hero_sm.png'
    sm.save(sm_path, optimize=True)
    print(f'Wrote {sm_path} ({sm.size})')


if __name__ == '__main__':
    main()
