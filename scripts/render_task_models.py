#!/usr/bin/env python3
"""Render the OSEC task-model and literature-background flowcharts.

Reads ``assets/task-model-*.mmd`` (Mermaid source), renders each via
:mod:`muriel.diagrams` (beautiful-mermaid Node bridge), and writes the
matched ``.svg`` next to the source. Idempotent and cached — repeat
runs are O(stat) after the first render.

Usage::

    .venv/bin/python scripts/render_task_models.py

Requires muriel >= 0.7.1 and ``cd ~/Documents/dev/muriel/muriel/diagrams && npm install``
to have been run once.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# muriel is editable in Andy's dev layout but not pip-installed into every
# project venv. Fall back to ~/Documents/dev/muriel if the import fails.
try:
    from muriel.diagrams import render
except ModuleNotFoundError:
    candidate = Path(os.environ.get("MURIEL_REPO", Path.home() / "Documents/dev/muriel"))
    if not (candidate / "muriel" / "diagrams").exists():
        print(
            f"muriel.diagrams not importable and {candidate} doesn't contain it. "
            "Set MURIEL_REPO or pip install muriel.",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.path.insert(0, str(candidate))
    from muriel.diagrams import render


# ─── Color-variable flattening ────────────────────────────────────────
#
# beautiful-mermaid emits CSS custom properties + color-mix() so themes
# can be swapped live in a browser. That breaks every static rasterizer
# (librsvg, cairo, ImageMagick) — they don't resolve var()/color-mix.
# For paper figures we need concrete hex values. Flatten by precomputing
# every derived var from the same recipe beautiful-mermaid uses in
# src/theme.ts (MIX weights).

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c + c for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(c)))):02x}" for c in rgb)


def _mix(a_hex: str, b_hex: str, pct: float) -> str:
    """color-mix(in srgb, A pct%, B) — sRGB-space linear blend."""
    a = _hex_to_rgb(a_hex)
    b = _hex_to_rgb(b_hex)
    p = pct / 100.0
    return _rgb_to_hex(tuple(p * a[i] + (1 - p) * b[i] for i in range(3)))


def flatten_css_vars(svg: str, *, bg: str = "#FFFFFF", fg: str = "#27272A") -> str:
    """Replace every ``var(--X)`` reference with a concrete hex value.

    Mirrors beautiful-mermaid's ``MIX`` table verbatim so the flattened
    output is byte-equivalent to what a browser would render given the
    same bg/fg. Strips the now-redundant ``<style>`` block.
    """
    resolved = {
        "--bg": bg,
        "--fg": fg,
        "--line": _mix(fg, bg, 50),
        "--accent": _mix(fg, bg, 85),
        "--muted": _mix(fg, bg, 40),
        "--surface": _mix(fg, bg, 3),
        "--border": _mix(fg, bg, 20),
        "--_text": fg,
        "--_text-sec": _mix(fg, bg, 60),
        "--_text-muted": _mix(fg, bg, 40),
        "--_text-faint": _mix(fg, bg, 25),
        "--_line": _mix(fg, bg, 50),
        "--_arrow": _mix(fg, bg, 85),
        "--_node-fill": _mix(fg, bg, 3),
        "--_node-stroke": _mix(fg, bg, 20),
        "--_group-fill": bg,
        "--_group-hdr": _mix(fg, bg, 5),
        "--_inner-stroke": _mix(fg, bg, 12),
        "--_key-badge": _mix(fg, bg, 10),
    }

    def replace_var(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        name = body.split(",", 1)[0].strip()
        return resolved.get(name, match.group(0))

    svg = re.sub(r"var\(\s*(--[A-Za-z0-9_-]+(?:\s*,[^)]*)?)\s*\)", replace_var, svg)
    svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.DOTALL)
    svg = re.sub(r'\sstyle="[^"]*--[^"]*"', "", svg)
    return svg

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"

# Theme: zinc-light is a clean monochrome (#FFFFFF / #27272A ≈ 13:1
# contrast) — safe for paper figures and above the project's 8:1 floor.
THEME = "zinc-light"

DIAGRAMS = [
    ASSETS / "task-model-osec.mmd",
    ASSETS / "task-model-literature.mmd",
]


def main() -> int:
    failures = 0
    for src_path in DIAGRAMS:
        if not src_path.exists():
            print(f"SKIP  missing source: {src_path}", file=sys.stderr)
            failures += 1
            continue
        source = src_path.read_text()
        try:
            d = render(source, theme=THEME)
        except Exception as e:
            print(f"FAIL  {src_path.name}: {e}", file=sys.stderr)
            failures += 1
            continue
        out_path = src_path.with_suffix(".svg")
        out_path.write_text(flatten_css_vars(d.svg))
        print(f"OK    {src_path.name} → {out_path.name} ({d.width:.0f}×{d.height:.0f})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
