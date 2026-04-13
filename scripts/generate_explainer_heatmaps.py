#!/usr/bin/env python3
"""Generate smooth gaussian heatmaps for the explainer page.

Uses typeset.render_heatmap() for Tobii-style pink gaussian density overlays.

Outputs to site/explainer/:
  - f-decomposition.png: Combined | Survey (fix 1-5) | Evaluate (fix 6-20)
  - f-dissection.png: All | -Survey | -Regressions | -Quick clickers | -Survivor bias

Usage:
    python scripts/generate_explainer_heatmaps.py
"""

import csv
import os
import sys
from pathlib import Path

# Add typeset to path
sys.path.insert(0, str(Path.home() / "Documents/dev/ascii-charts"))
from typeset import render_heatmap, find_font, luminance, check_contrast

from PIL import Image, ImageDraw, ImageFont

# Add notebooks-v2 to path for data_loader
sys.path.insert(0, str(Path(__file__).parent.parent / "notebooks-v2"))
from data_loader import get_trial_ids, load_fixations, load_mouse_events

ROOT = Path(__file__).parent.parent
EXPLAINER_DIR = ROOT / "site" / "explainer"
FIXATION_DIR = ROOT / "AdSERP" / "data" / "fixation-data"

# Screen dimensions from the eye tracker
SCREEN_W, SCREEN_H = 1280, 1024

# Heatmap panel size — each individual panel
PANEL_W, PANEL_H = 400, 800


def load_all_fixations():
    """Load all fixations across all trials with per-fixation index."""
    all_fix = []
    trial_ids = get_trial_ids()
    for tid in trial_ids:
        try:
            fixations = load_fixations(tid)
        except Exception:
            continue
        # Load scroll events for regression detection
        try:
            events, scrolls, clicks = load_mouse_events(tid)
        except Exception:
            scrolls = []

        # Track scroll direction for regression detection
        scroll_ts = [s[0] for s in scrolls] if scrolls else []
        scroll_ys = [s[1] for s in scrolls] if scrolls else []

        has_regression = False
        for i in range(1, len(scroll_ys)):
            if scroll_ys[i] < scroll_ys[i - 1]:
                has_regression = True
                break

        # Quick clicker: clicked within first 10 fixations
        is_quick = len(fixations) <= 10

        for i, f in enumerate(fixations):
            f['fix_index'] = i  # 0-based within trial
            f['trial_id'] = tid
            f['has_regression'] = has_regression
            f['is_quick'] = is_quick
            f['n_fixations'] = len(fixations)
            all_fix.append(f)

    print(f"Loaded {len(all_fix)} fixations from {len(trial_ids)} trials")
    return all_fix


def make_panel(fixations, title, subtitle=None):
    """Render a single heatmap panel."""
    heatmap = render_heatmap(
        fixations,
        canvas_size=(PANEL_W, PANEL_H),
        radius=18,
        blur=8,
        colormap="pink",
        desaturate=0,
        bg_opacity=0,
    )
    return heatmap


def add_labels(canvas, panels_info, total_w, total_h):
    """Add title labels and annotations to a multi-panel canvas."""
    draw = ImageDraw.Draw(canvas)
    try:
        title_font = find_font("helvetica", "bold", 22)
        sub_font = find_font("helvetica", "regular", 14)
    except FileNotFoundError:
        title_font = ImageFont.load_default()
        sub_font = title_font

    for info in panels_info:
        x_center = info['x'] + PANEL_W // 2
        # Title
        color = info.get('color', (100, 100, 100))
        # Verify contrast against white bg
        ratio, _, _ = check_contrast(color, (255, 255, 255))
        if ratio < 8.0:
            # Darken to meet 8:1
            factor = 0.5
            color = tuple(max(0, int(c * factor)) for c in color)
            ratio, _, _ = check_contrast(color, (255, 255, 255))
            if ratio < 8.0:
                color = (0, 0, 0)

        bbox = draw.textbbox((0, 0), info['title'], font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text((x_center - tw // 2, 15), info['title'], fill=color, font=title_font)

        # Subtitle
        if info.get('subtitle'):
            bbox = draw.textbbox((0, 0), info['subtitle'], font=sub_font)
            tw = bbox[2] - bbox[0]
            # Subtitle needs 8:1 too
            sub_color = (80, 80, 80)
            ratio, _, _ = check_contrast(sub_color, (255, 255, 255))
            if ratio < 8.0:
                sub_color = (50, 50, 50)
            draw.text((x_center - tw // 2, total_h - 35), info['subtitle'],
                      fill=sub_color, font=sub_font)

    return canvas


def add_connector(draw, x, y, text, font):
    """Draw a connector symbol between panels."""
    color = (50, 50, 50)  # 8:1+ on white
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw // 2, y), text, fill=color, font=font)


def generate_decomposition(all_fix):
    """f-decomposition.png: Combined = Survey + Evaluate"""
    print("\nGenerating f-decomposition.png...")

    # Filter fixations by phase
    survey = [f for f in all_fix if f['fix_index'] < 5]
    evaluate = [f for f in all_fix if 5 <= f['fix_index'] < 20]
    combined = [f for f in all_fix if f['fix_index'] < 20]

    print(f"  Combined: {len(combined)}, Survey: {len(survey)}, Evaluate: {len(evaluate)}")

    # Scale fixation coordinates to panel space
    def scale_fix(fixations):
        scaled = []
        for f in fixations:
            scaled.append({
                'x': f['x'] * PANEL_W / SCREEN_W,
                'y': f['y'] * PANEL_H / SCREEN_H,
                'd': f['d'],
            })
        return scaled

    panel_combined = make_panel(scale_fix(combined), "COMBINED F-SHAPE")
    panel_survey = make_panel(scale_fix(survey), "SURVEY PHASE")
    panel_evaluate = make_panel(scale_fix(evaluate), "EVALUATE PHASE")

    # Assemble: 3 panels with connectors
    gap = 60
    total_w = PANEL_W * 3 + gap * 2
    total_h = PANEL_H + 80  # room for labels
    canvas = Image.new('RGB', (total_w, total_h), (255, 255, 255))

    y_offset = 50
    canvas.paste(panel_combined.convert('RGB'), (0, y_offset))
    canvas.paste(panel_survey.convert('RGB'), (PANEL_W + gap, y_offset))
    canvas.paste(panel_evaluate.convert('RGB'), (PANEL_W * 2 + gap * 2, y_offset))

    # Labels
    panels_info = [
        {'x': 0, 'title': 'COMBINED F-SHAPE', 'subtitle': 'what the heatmap shows',
         'color': (60, 60, 60)},
        {'x': PANEL_W + gap, 'title': 'SURVEY PHASE', 'subtitle': 'fixations 1–5',
         'color': (180, 40, 40)},
        {'x': PANEL_W * 2 + gap * 2, 'title': 'EVALUATE PHASE', 'subtitle': 'fixations 6–20',
         'color': (30, 80, 180)},
    ]
    canvas = add_labels(canvas, panels_info, total_w, total_h)

    # Connectors
    draw = ImageDraw.Draw(canvas)
    try:
        conn_font = find_font("helvetica", "regular", 28)
    except FileNotFoundError:
        conn_font = ImageFont.load_default()

    add_connector(draw, PANEL_W + gap // 2, y_offset + PANEL_H // 2 - 14, "=", conn_font)
    add_connector(draw, PANEL_W * 2 + gap + gap // 2, y_offset + PANEL_H // 2 - 14, "+", conn_font)

    out = EXPLAINER_DIR / "f-decomposition.png"
    canvas.save(out)
    print(f"  Saved: {out} ({total_w}x{total_h})")


def generate_dissection(all_fix):
    """f-dissection.png: All → -Survey → -Regressions → -Quick clickers → -Survivor bias"""
    import random
    print("\nGenerating f-dissection.png...")

    # Panel 1: All fixations (first 20 per trial)
    all_first20 = [f for f in all_fix if f['fix_index'] < 20]

    # Panel 2: Evaluate only (subtract survey = fixations 6-20)
    evaluate_only = [f for f in all_fix if 5 <= f['fix_index'] < 20]

    # Panel 3: Evaluate, no regressions (forward-only scanners)
    no_regression = [f for f in evaluate_only if not f['has_regression']]

    # Panel 4: Deep evaluators — not quick clickers, no regressions
    deep = [f for f in no_regression if not f['is_quick']]

    # Panel 5: Subtract survivor bias — equalize contribution across fix indices.
    # The "deep" set still has 6 → 7 → 8 → … attrition: each successive fixation
    # index is reached by fewer trials (some clicked at fix 7, some at fix 12, …).
    # Downsample each fix index to the minimum count to remove that bias entirely.
    deep_by_idx = {}
    for f in deep:
        deep_by_idx.setdefault(f['fix_index'], []).append(f)
    if deep_by_idx:
        min_count = min(len(v) for v in deep_by_idx.values())
        rng = random.Random(42)
        normalized = []
        for idx in sorted(deep_by_idx):
            fixes_at_idx = deep_by_idx[idx]
            normalized.extend(rng.sample(fixes_at_idx, min_count))
        attrition_summary = (
            f"min count per index = {min_count} "
            f"(orig range {min(len(v) for v in deep_by_idx.values())}–"
            f"{max(len(v) for v in deep_by_idx.values())})"
        )
    else:
        normalized = []
        min_count = 0
        attrition_summary = "no deep fixations"

    print(f"  All: {len(all_first20)}, -Survey: {len(evaluate_only)}, "
          f"-Regressions: {len(no_regression)}, -Quick clickers: {len(deep)}, "
          f"-Survivor bias: {len(normalized)} ({attrition_summary})")

    def scale_fix(fixations):
        scaled = []
        for f in fixations:
            scaled.append({
                'x': f['x'] * PANEL_W / SCREEN_W,
                'y': f['y'] * PANEL_H / SCREEN_H,
                'd': f['d'],
            })
        return scaled

    panels = [
        make_panel(scale_fix(all_first20), "ALL FIXATIONS"),
        make_panel(scale_fix(evaluate_only), "SUBTRACT SURVEY"),
        make_panel(scale_fix(no_regression), "SUBTRACT REGRESSIONS"),
        make_panel(scale_fix(deep), "SUBTRACT QUICK CLICKERS"),
        make_panel(scale_fix(normalized), "SUBTRACT SURVIVOR BIAS"),
    ]

    # Assemble: 5 panels with arrows
    gap = 50
    total_w = PANEL_W * 5 + gap * 4
    total_h = PANEL_H + 80
    canvas = Image.new('RGB', (total_w, total_h), (255, 255, 255))

    y_offset = 50
    for i, panel in enumerate(panels):
        canvas.paste(panel.convert('RGB'), (i * (PANEL_W + gap), y_offset))

    panels_info = [
        {'x': 0, 'title': 'ALL FIXATIONS',
         'subtitle': f'the F-pattern as published\nN = {len(all_first20):,}',
         'color': (140, 30, 30)},
        {'x': PANEL_W + gap, 'title': 'SUBTRACT SURVEY',
         'subtitle': f'evaluate fixations only\nN = {len(evaluate_only):,}',
         'color': (60, 60, 60)},
        {'x': (PANEL_W + gap) * 2, 'title': 'SUBTRACT REGRESSIONS',
         'subtitle': f'forward-only saccades\nN = {len(no_regression):,}',
         'color': (60, 60, 60)},
        {'x': (PANEL_W + gap) * 3, 'title': 'SUBTRACT QUICK CLICKERS',
         'subtitle': f'deep evaluators only\nN = {len(deep):,}',
         'color': (60, 60, 60)},
        {'x': (PANEL_W + gap) * 4, 'title': 'SUBTRACT SURVIVOR BIAS',
         'subtitle': f'equal mass per fix index\nN = {len(normalized):,}',
         'color': (60, 60, 60)},
    ]
    canvas = add_labels(canvas, panels_info, total_w, total_h)

    # Arrow connectors
    draw = ImageDraw.Draw(canvas)
    try:
        conn_font = find_font("helvetica", "regular", 22)
    except FileNotFoundError:
        conn_font = ImageFont.load_default()

    for i in range(4):
        ax = (i + 1) * PANEL_W + i * gap + gap // 2
        add_connector(draw, ax, y_offset + PANEL_H // 2 - 11, "→", conn_font)

    out = EXPLAINER_DIR / "f-dissection.png"
    canvas.save(out)
    print(f"  Saved: {out} ({total_w}x{total_h})")


if __name__ == "__main__":
    all_fix = load_all_fixations()
    generate_decomposition(all_fix)
    generate_dissection(all_fix)
    print("\nDone.")
