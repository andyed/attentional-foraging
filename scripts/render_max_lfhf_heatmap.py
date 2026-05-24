"""Render a max-LFHF-per-region Tobii heatmap with legend.

Uses muriel's contour-banded pink colormap conventions (per
`channels/heatmaps.md`) but keeps a *max* aggregation semantic so a single
high-load fixation lights up its region — the figure shows peak load per
neighborhood, not summed-density-weighted-by-duration.

Visual encoding:
- LFHF-equipped fixations: muriel-pink contour-banded ramp.
- Null-LFHF fixations (filter warmup, blink dropouts): light-grey
  unencoded blobs — visible but not coded — only where no LFHF heat is
  already present (representational integrity invariant).
- SERP background: desaturated 70% / 35% opacity per muriel default.
- Click marker: cursor-icon path. Canvas extends below the SERP if click
  sits below the rendered page region (with leader line + caption).
- Legend: title strip + horizontal contour-banded colorbar.

Usage:
    python3 scripts/render_max_lfhf_heatmap.py p020-b6-t10 [p045-b2-t6 ...]
"""

from __future__ import annotations
import re, json, sys, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
SERP_RENDERS = SITE / "serp-renders"
OUT_DIR = REPO / "scripts" / "output" / "ettac"
OUT_DIR.mkdir(parents=True, exist_ok=True)

KERNEL_SIGMA_PX = 110     # Gaussian falloff (1σ)
KERNEL_RADIUS_PX = 330    # 3σ truncation
GRID_DOWNSAMPLE = 4       # heatmap grid cell size in source-px
N_BANDS = 8               # contour quantization (muriel default)


def deposit_gaussian_max(grid: np.ndarray, fx: float, fy: float, value: float):
    """In-place: grid[i,j] = max(grid[i,j], value * gaussian)."""
    g_h, g_w = grid.shape
    cx = int(fx) // GRID_DOWNSAMPLE
    cy = int(fy) // GRID_DOWNSAMPLE
    if cx < 0 or cx >= g_w or cy < 0 or cy >= g_h:
        return
    sigma = KERNEL_SIGMA_PX / GRID_DOWNSAMPLE
    radius = int(KERNEL_RADIUS_PX / GRID_DOWNSAMPLE)
    two_sigma_sq = 2 * sigma * sigma
    x0, x1 = max(0, cx - radius), min(g_w, cx + radius + 1)
    y0, y1 = max(0, cy - radius), min(g_h, cy + radius + 1)
    ys, xs = np.ogrid[y0:y1, x0:x1]
    d2 = (xs - cx) ** 2 + (ys - cy) ** 2
    weight = np.exp(-d2 / two_sigma_sq)
    grid[y0:y1, x0:x1] = np.maximum(grid[y0:y1, x0:x1], value * weight)


def apply_pink_colormap(density_arr: np.ndarray) -> np.ndarray:
    """muriel pink colormap: light pink → hot pink → deep magenta.
    Lifted from muriel.typeset.render_heatmap, applied to a normalized
    density array and returns RGBA uint8 of shape (h, w, 4)."""
    h, w = density_arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    d_gamma = density_arr ** 0.7
    for c in range(3):
        low = [255, 210, 240][c]
        mid = [230, 60, 140][c]
        high = [180, 20, 80][c]
        rgba[:, :, c] = np.where(
            density_arr > 0.01,
            np.where(
                d_gamma < 0.5,
                (low + (mid - low) * d_gamma * 2).astype(np.uint8),
                (mid + (high - mid) * (d_gamma - 0.5) * 2).astype(np.uint8),
            ),
            0,
        )
    rgba[:, :, 3] = np.where(
        density_arr > 0.01,
        np.minimum(240, (d_gamma * 300).astype(np.uint16)).astype(np.uint8),
        0,
    )
    return rgba


def contour_band(density_arr: np.ndarray, n_bands: int = N_BANDS,
                  smooth_blur: int = 3) -> np.ndarray:
    """Quantize → re-smooth → renormalize. Per muriel.typeset.render_heatmap."""
    arr = np.floor(density_arr * n_bands) / n_bands
    band_img = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
    band_img = band_img.filter(ImageFilter.GaussianBlur(smooth_blur))
    arr = np.array(band_img, dtype=np.float64) / 255.0
    dmax = arr.max()
    if dmax > 0:
        arr /= dmax
    return arr


def _load_font(size: int):
    for p in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_heatmap(trial: str, auto_crop: bool = True,
                    crop_top_px: int | None = None,
                    crop_bottom_px: int | None = None) -> Path:
    """auto_crop: if True, trim the SERP to the bounding box of LFHF-equipped
    fixations (with margin) — drops the search-bar header and the empty
    bottom. crop_top_px / crop_bottom_px override auto-detect."""
    html = (SITE / f"{trial}.html").read_text()
    F = json.loads(re.search(r'const F=(\[.*?\])\s*,CK=', html, re.DOTALL).group(1))
    CK = json.loads(re.search(r'CK=(\{[^}]+\})', html).group(1))
    serp_path = SERP_RENDERS / f"{trial}.png"
    serp_full = Image.open(serp_path).convert("RGBA")
    W, H_full = serp_full.size

    # Determine crop bounds in source-SERP-y.
    # AdSERP-style pages have a search-bar header (~150-170px) plus "Ads"
    # row above the first product card. Skip past that — the first fixation
    # is often on the search box itself (not the result content).
    SERP_HEADER_FLOOR = 170
    ys_lfhf = [f["y"] for f in F if f.get("lfhf") is not None]
    if auto_crop and ys_lfhf:
        margin = 120  # source-px, gives ~one fixation worth of visual breathing room
        y_top = max(SERP_HEADER_FLOOR, int(min(ys_lfhf)) - margin)
        y_bot = min(H_full, int(max(ys_lfhf)) + margin)
        # Always include the click in the visible region if it's inside SERP.
        if 0 <= CK["y"] < H_full:
            y_bot = max(y_bot, int(CK["y"]) + 80)
    else:
        y_top, y_bot = 0, H_full
    if crop_top_px is not None:
        y_top = crop_top_px
    if crop_bottom_px is not None:
        y_bot = crop_bottom_px
    serp = serp_full.crop((0, y_top, W, y_bot))
    H = serp.size[1]
    print(f"  crop: y={y_top}–{y_bot} ({H_full}→{H} px, {100*H/H_full:.0f}%)")

    # Shift fixation y by crop offset so they land correctly on the cropped SERP.
    fix_with_lfhf = [(f["x"], f["y"] - y_top, f["lfhf"])
                     for f in F if f.get("lfhf") is not None]
    fix_null_lfhf = [(f["x"], f["y"] - y_top)
                     for f in F if f.get("lfhf") is None]
    CK_y_cropped = CK["y"] - y_top  # may go negative or past H — handled by canvas extension

    if not fix_with_lfhf:
        print(f"  {trial}: no LFHF-equipped fixations")
        return None

    lfhf_max = max(v for _, _, v in fix_with_lfhf)
    print(f"  {trial}: {len(fix_with_lfhf)} LFHF fixations (max {lfhf_max:.1f}), "
          f"{len(fix_null_lfhf)} null-LFHF fixations")

    # ── Aggregate grids (max, downsampled) ──────────────────────────────
    g_w = W // GRID_DOWNSAMPLE
    g_h = H // GRID_DOWNSAMPLE
    grid_lfhf = np.zeros((g_h, g_w), dtype=np.float32)
    grid_null = np.zeros((g_h, g_w), dtype=np.float32)
    for fx, fy, val in fix_with_lfhf:
        deposit_gaussian_max(grid_lfhf, fx, fy, val)
    for fx, fy in fix_null_lfhf:
        deposit_gaussian_max(grid_null, fx, fy, 1.0)

    # ── LFHF contour-banded layer (pink colormap) ───────────────────────
    grid_lfhf_norm = grid_lfhf / max(lfhf_max, 1e-6)
    grid_lfhf_norm = np.clip(grid_lfhf_norm, 0, 1)
    # Light pre-blur to soften peak granularity (muriel uses post-density blur)
    pre = Image.fromarray((grid_lfhf_norm * 255).astype(np.uint8), mode="L")
    pre = pre.filter(ImageFilter.GaussianBlur(3))
    grid_lfhf_norm = np.array(pre, dtype=np.float64) / 255.0
    if grid_lfhf_norm.max() > 0:
        grid_lfhf_norm /= grid_lfhf_norm.max()
    # Contour banding (the Tobii topo feel).
    banded = contour_band(grid_lfhf_norm, n_bands=N_BANDS, smooth_blur=3)
    rgba_lfhf = apply_pink_colormap(banded)

    # ── Null-LFHF light-grey layer ──────────────────────────────────────
    grid_null_norm = np.clip(grid_null, 0, 1)
    pre_n = Image.fromarray((grid_null_norm * 255).astype(np.uint8), mode="L")
    pre_n = pre_n.filter(ImageFilter.GaussianBlur(3))
    grid_null_norm = np.array(pre_n, dtype=np.float64) / 255.0
    if grid_null_norm.max() > 0:
        grid_null_norm /= grid_null_norm.max()
    banded_null = contour_band(grid_null_norm, n_bands=4, smooth_blur=3)
    # Show grey only where LFHF heat is absent.
    null_visible = (banded_null > 0.05) & (banded < 0.02)
    rgba_null = np.zeros((g_h, g_w, 4), dtype=np.uint8)
    rgba_null[..., 0] = np.where(null_visible, 200, 0)
    rgba_null[..., 1] = np.where(null_visible, 200, 0)
    rgba_null[..., 2] = np.where(null_visible, 200, 0)
    rgba_null[..., 3] = np.where(null_visible,
                                  (60 + 100 * banded_null).astype(np.uint8), 0)

    # Composite the two layers, upsample to SERP resolution.
    full = np.zeros((g_h, g_w, 4), dtype=np.uint8)
    enc_mask = rgba_lfhf[..., 3] > 0
    full[enc_mask] = rgba_lfhf[enc_mask]
    null_mask = (rgba_null[..., 3] > 0) & ~enc_mask
    full[null_mask] = rgba_null[null_mask]
    heatmap = Image.fromarray(full, mode="RGBA").resize((W, H), Image.BILINEAR)

    # ── SERP background: desaturate 70% / opacity 35% (muriel defaults) ─
    serp_rgb = serp.convert("RGB")
    gray = serp_rgb.convert("L").convert("RGB")
    serp_rgb = Image.blend(serp_rgb, gray, 0.7)
    serp_rgba = serp_rgb.convert("RGBA")
    bg_arr = np.array(serp_rgba)
    bg_arr[:, :, 3] = int(0.55 * 255)   # higher than muriel's 0.35 so SERP stays readable
    serp_pushback = Image.fromarray(bg_arr)

    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    composite_serp_heat = Image.alpha_composite(base, serp_pushback)
    composite_serp_heat = Image.alpha_composite(composite_serp_heat, heatmap)

    # ── Canvas extension if click is below the (cropped) SERP image ─────
    legend_h = 320
    pad = 30
    extra_below = max(0, int(CK_y_cropped) - H + 220)
    canvas_w = W
    canvas_h = legend_h + pad + H + extra_below + pad
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    canvas.paste(composite_serp_heat.convert("RGB"), (0, legend_h + pad))

    draw = ImageDraw.Draw(canvas)
    font_t = _load_font(48)
    font_b = _load_font(36)
    font_s = _load_font(28)

    # Legend strip
    draw.rectangle((0, 0, canvas_w, legend_h), fill=(245, 245, 248))
    draw.line((0, legend_h - 1, canvas_w, legend_h - 1), fill=(60, 60, 60), width=3)
    title = f"{trial} — peak LF/HF (cognitive load) per gaze region"
    draw.text((pad, 22), title, fill=(20, 20, 25), font=font_t)
    sub = f"max-aggregation Gaussian σ={KERNEL_SIGMA_PX}px · {N_BANDS} contour bands · {len(fix_with_lfhf)} LFHF fixations · {len(fix_null_lfhf)} null"
    draw.text((pad, 84), sub, fill=(80, 80, 90), font=font_s)

    # Color-bar — render N_BANDS stops of the pink colormap.
    bar_h = 60
    bar_y0 = 150
    bar_y1 = bar_y0 + bar_h
    bar_x0 = pad + 100
    bar_x1 = canvas_w - pad - 380   # leave room for null-swatch on right
    bar_w = bar_x1 - bar_x0
    band_w = bar_w / N_BANDS
    for i in range(N_BANDS):
        # Each band's mid-density.
        d_mid = (i + 0.5) / N_BANDS
        d_arr = np.array([[d_mid]], dtype=np.float64)
        rgba_band = apply_pink_colormap(d_arr)
        col = tuple(int(v) for v in rgba_band[0, 0, :3])
        x0 = int(bar_x0 + i * band_w)
        x1 = int(bar_x0 + (i + 1) * band_w)
        draw.rectangle((x0, bar_y0, x1, bar_y1), fill=col)
    draw.rectangle((bar_x0, bar_y0, bar_x1, bar_y1), outline=(40, 40, 40), width=3)

    # Tick labels at 0, max/4, max/2, 3max/4, max.
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        v = lfhf_max * frac
        x = int(bar_x0 + frac * bar_w)
        draw.line((x, bar_y1, x, bar_y1 + 14), fill=(40, 40, 40), width=3)
        s = f"{v:.0f}" if v >= 1 else f"{v:.1f}"
        bbox = draw.textbbox((0, 0), s, font=font_b)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2, bar_y1 + 22), s, fill=(20, 20, 25), font=font_b)
    # Bar caption
    draw.text((pad, bar_y0 + 14), "low",
              fill=(20, 20, 25), font=font_b)

    # Null swatch on the right of the legend.
    sw_x = bar_x1 + 40
    sw_y0 = bar_y0
    sw_y1 = bar_y1
    draw.rectangle((sw_x, sw_y0, sw_x + 70, sw_y1),
                   fill=(200, 200, 200), outline=(40, 40, 40), width=3)
    draw.text((sw_x + 84, sw_y0 + 4), "null LF/HF",
              fill=(20, 20, 25), font=font_b)
    draw.text((sw_x + 84, sw_y0 + 38),
              "(filter warmup / blink)",
              fill=(80, 80, 90), font=font_s)

    # ── Click marker (cursor icon) ──────────────────────────────────────
    SC = 4.0
    cx = int(CK["x"])
    cy = int(CK_y_cropped) + legend_h + pad
    cursor_path = [
        (cx,             cy),
        (cx,             cy + 22 * SC),
        (cx + 5.5 * SC,  cy + 17 * SC),
        (cx + 10 * SC,   cy + 28 * SC),
        (cx + 14 * SC,   cy + 26 * SC),
        (cx + 9 * SC,    cy + 16 * SC),
        (cx + 16 * SC,   cy + 16 * SC),
    ]
    draw.polygon(cursor_path, fill=(255, 51, 51), outline=(0, 0, 0))
    draw.text((cx + int(16 * SC + 16), cy + int(22 * SC + 8)),
              "click", fill=(220, 30, 30), font=_load_font(40))

    # If the click sits below the SERP image, draw a leader from the SERP
    # bottom up to the click + a caption explaining the gap.
    if CK_y_cropped > H:
        serp_bottom_y = legend_h + pad + H
        # Leader line from a representative gaze region near the bottom of
        # the SERP up to the click marker.
        draw.line((cx + 4, serp_bottom_y, cx + 4, cy),
                   fill=(180, 180, 180), width=4)
        draw.text((cx + 30, serp_bottom_y + 12),
                  "click target sits below the captured SERP region",
                  fill=(90, 90, 100), font=font_s)

    out = OUT_DIR / f"max_lfhf_heatmap_{trial}.png"
    canvas.save(out, optimize=True)
    print(f"  wrote: {out}  size={canvas.size}")
    return out


def main():
    trials = sys.argv[1:] if len(sys.argv) > 1 else ["p020-b6-t10"]
    for t in trials:
        print(f"\nrendering Tobii max-LFHF heatmap for {t}")
        render_heatmap(t)


if __name__ == "__main__":
    main()
