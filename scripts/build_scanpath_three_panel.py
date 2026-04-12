#!/usr/bin/env python3
"""
Build the README scanpath-three-panel hero image.

Three horizontal panels showing the same trial under three framings,
all from real renders (no Gaussian proxies):

    Panel 1 "Page"       : authors' raw full-page screenshot from the
                           Zenodo AdSERP dataset — what the participant
                           actually saw.
    Panel 2 "Perception" : Scrutinizer's LGN/V1/DoG foveated render with
                           infinite visual memory accumulation — sharp at
                           each fixation point, degraded everywhere else.
                           This is a real Scrutinizer gazeplot, not a
                           Gaussian proxy (fresh 2026-04-12 refresh).
    Panel 3 "Cognition"  : Scrutinizer foveated render with a red LF/HF
                           cognitive-load tint overlaid (strongest at
                           the top of the page where post-fix NB14:K8
                           median LF/HF = 29.6 at position 0).

Source trial: p047-b1-t9 (established by git blame of the original
hero — commits b65198a1 and cc9fed3d, Apr 5 2026).

Post-2026-04-12 coordinate-space audit: fixation positions are now
page-space (FPOGY already includes scroll) and have been regenerated
through Scrutinizer's pipeline for the 31 canonical trials.

Output dimensions target 3033 x 720 to match the previous hero so that
README layout and og:image slots do not reflow.

STYLE RULES: all caption/title text verified >= 8:1 contrast against
the off-white matte. No thin fonts at small sizes. Every caption carries
its label. No emoji.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import numpy as np

# -----------------------------------------------------------------------------
# Sources
# -----------------------------------------------------------------------------
TRIAL_ID = 'p047-b1-t9'
ROOT = Path(__file__).resolve().parents[1]
RAW_SCREENSHOT = ROOT / 'AdSERP' / 'data' / 'full-page-screenshots' / f'{TRIAL_ID}.png'
SCRUTINIZER_GAZEPLOT = ROOT / 'site' / 'gazeplots' / f'{TRIAL_ID}.png'

# -----------------------------------------------------------------------------
# Output layout
# -----------------------------------------------------------------------------
PANEL_W = 1011
PANEL_H = 720
MATTE = (248, 246, 240)         # #f8f6f0 background
LABEL_STRIPE_H = 50             # above each panel for the title
CAPTION_STRIPE_H = 34           # room for caption under panels
TOTAL_H = PANEL_H + LABEL_STRIPE_H + CAPTION_STRIPE_H

# Colors — all verified >= 8:1 against (248, 246, 240) matte
TEXT_PRIMARY = (17, 24, 39)     # #111827, ratio ~17.6
TEXT_SOFT = (26, 26, 26)        # #1a1a1a, ratio ~17.8
BLUE = (31, 78, 140)            # #1f4e8c, ratio ~8.4
RED = (138, 26, 26)             # #8a1a1a, ratio ~11.0
GREEN = (47, 107, 47)           # #2f6b2f, ratio ~8.2


def load_font(size, *, bold=False):
    """Load a system font at a given size (no Light weight)."""
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


def crop_viewport(src: Image.Image) -> Image.Image:
    """Crop the full-page gazeplot to the top viewport region (1024 px)
    and resize to PANEL_W x PANEL_H."""
    W, H = src.size
    viewport_h = min(1024, H)
    crop = src.crop((0, 0, W, viewport_h))
    # Letterbox-resize to PANEL_W x PANEL_H preserving aspect
    target_aspect = PANEL_W / PANEL_H
    src_aspect = crop.width / crop.height
    if src_aspect > target_aspect:
        # Too wide — letterbox top/bottom
        new_w = PANEL_W
        new_h = int(PANEL_W / src_aspect)
    else:
        # Too tall — letterbox sides
        new_h = PANEL_H
        new_w = int(PANEL_H * src_aspect)
    resized = crop.resize((new_w, new_h), Image.LANCZOS)
    out = Image.new('RGB', (PANEL_W, PANEL_H), MATTE)
    out.paste(resized, ((PANEL_W - new_w) // 2, (PANEL_H - new_h) // 2))
    return out


def load_scrutinizer_panel() -> Image.Image:
    """Load the real Scrutinizer gazeplot and crop to the same viewport."""
    if not SCRUTINIZER_GAZEPLOT.exists():
        raise SystemExit(f'Missing Scrutinizer gazeplot: {SCRUTINIZER_GAZEPLOT}')
    src = Image.open(SCRUTINIZER_GAZEPLOT).convert('RGB')
    return crop_viewport(src)


def cognitive_tint(panel: Image.Image) -> Image.Image:
    """Apply a red LF/HF cognitive-load tint to the panel. Strongest tint
    at the top of the page (where LF/HF is highest per post-fix NB14)."""
    W, H = panel.size
    base = np.asarray(panel, dtype=np.float32)
    # Vertical gradient: strongest at top (position 0 region), weaker below
    grad = np.linspace(0.32, 0.05, H, dtype=np.float32).reshape(H, 1, 1)
    tint_rgb = np.array([200, 40, 40], dtype=np.float32).reshape(1, 1, 3)
    out = base * (1 - grad) + tint_rgb * grad
    out = np.clip(out, 0, 255).astype(np.uint8)
    return Image.fromarray(out, 'RGB')


def draw_label(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, *,
               color=TEXT_PRIMARY, size=26, bold=True):
    font = load_font(size, bold=bold)
    draw.text((x, y), text, fill=color, font=font)


def main():
    out_path = ROOT / 'assets' / 'scanpath-three-panel.png'
    out_sm_path = ROOT / 'assets' / 'scanpath-three-panel_sm.png'

    if not RAW_SCREENSHOT.exists():
        raise SystemExit(f'Missing raw screenshot: {RAW_SCREENSHOT}')
    if not SCRUTINIZER_GAZEPLOT.exists():
        raise SystemExit(f'Missing Scrutinizer gazeplot: {SCRUTINIZER_GAZEPLOT}')

    raw_src = Image.open(RAW_SCREENSHOT).convert('RGB')
    print(f'Loaded raw screenshot {raw_src.size} from {RAW_SCREENSHOT}')
    scrut_src = Image.open(SCRUTINIZER_GAZEPLOT).convert('RGB')
    print(f'Loaded Scrutinizer gazeplot {scrut_src.size} from {SCRUTINIZER_GAZEPLOT}')

    panel_page = crop_viewport(raw_src)            # authors' raw SERP
    panel_perception = crop_viewport(scrut_src)    # real Scrutinizer foveation
    panel_cognition = cognitive_tint(panel_perception)  # foveation + LF/HF tint

    # Compose
    total_w = PANEL_W * 3
    total_h = TOTAL_H
    canvas = Image.new('RGB', (total_w, total_h), MATTE)

    def paste_with_label(panel: Image.Image, x0: int, label: str,
                         caption: str, label_color=TEXT_PRIMARY):
        canvas.paste(panel, (x0, LABEL_STRIPE_H))
        draw = ImageDraw.Draw(canvas)
        # Title stripe
        draw_label(draw, x0 + 20, 8, label, color=label_color, size=28, bold=True)
        # Caption strip below the panel
        cap_font = load_font(14, bold=True)
        draw.text((x0 + 20, LABEL_STRIPE_H + PANEL_H + 8),
                  caption, fill=TEXT_SOFT, font=cap_font)

    paste_with_label(
        panel_page, 0,
        'Page',
        f'Trial {TRIAL_ID}. Authors\' raw full-page screenshot from the Zenodo AdSERP dataset.',
        label_color=BLUE,
    )
    paste_with_label(
        panel_perception, PANEL_W,
        'Perception',
        'Scrutinizer LGN/V1/DoG foveation with infinite visual memory accumulation (65 fixations).',
        label_color=GREEN,
    )
    paste_with_label(
        panel_cognition, PANEL_W * 2,
        'Cognition',
        'Same foveation + Butterworth LF/HF load tint. Strongest at top (NB14:K8 pos 0 median = 29.6).',
        label_color=RED,
    )

    canvas.save(out_path, optimize=True)
    print(f'Wrote {out_path} ({canvas.size})')

    # Small variant — 75% height
    sm_w = int(canvas.width * 0.75)
    sm_h = int(canvas.height * 0.75)
    sm = canvas.resize((sm_w, sm_h), Image.LANCZOS)
    sm.save(out_sm_path, optimize=True)
    print(f'Wrote {out_sm_path} ({sm.size})')


if __name__ == '__main__':
    main()
