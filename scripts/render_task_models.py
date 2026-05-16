#!/usr/bin/env python3
"""Render the OSEC task-model and literature-background flowcharts.

Reads ``assets/task-model-*.mmd`` (Mermaid source), renders each via
:mod:`muriel.diagrams` (beautiful-mermaid Node bridge), and writes the
matched ``.svg`` and a 2x-DPI ``.png`` next to the source. Idempotent
and cached — repeat runs are O(stat) after the first render.

Usage::

    .venv/bin/python scripts/render_task_models.py

Requires muriel >= 0.7.1, ``cd ~/Documents/dev/muriel/muriel/diagrams && npm install``,
and ``rsvg-convert`` on PATH (``brew install librsvg``) for the PNG pass.
The PNG pass is skipped with a warning if rsvg-convert is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"

# Theme: zinc-light is a clean monochrome (#FFFFFF / #27272A ≈ 13:1
# contrast) — safe for paper figures and above the project's 8:1 floor.
THEME = "zinc-light"

DIAGRAMS = [
    ASSETS / "task-model-osec.mmd",
    ASSETS / "task-model-literature.mmd",
]


def _rasterize(svg_path: Path, width_px: int) -> bool:
    """Run rsvg-convert to produce ``svg_path.with_suffix('.png')``.

    Returns True on success. Skips (with a warning) if rsvg-convert
    isn't on PATH — the SVG remains the source of truth.
    """
    binary = shutil.which("rsvg-convert")
    if binary is None:
        print(
            "WARN  rsvg-convert not found; skipping PNG. "
            "Install with: brew install librsvg",
            file=sys.stderr,
        )
        return False
    png_path = svg_path.with_suffix(".png")
    proc = subprocess.run(
        [binary, "-w", str(width_px), str(svg_path), "-o", str(png_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"FAIL  rsvg-convert {svg_path.name}: {proc.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main() -> int:
    failures = 0
    for src_path in DIAGRAMS:
        if not src_path.exists():
            print(f"SKIP  missing source: {src_path}", file=sys.stderr)
            failures += 1
            continue
        source = src_path.read_text()
        try:
            d = render(source, theme=THEME, flatten=True)
        except Exception as e:
            print(f"FAIL  {src_path.name}: {e}", file=sys.stderr)
            failures += 1
            continue
        svg_path = src_path.with_suffix(".svg")
        svg_path.write_text(d.svg)
        # 2x retina PNG so figure exports stay crisp without bloating files.
        png_ok = _rasterize(svg_path, width_px=int(d.width * 2))
        png_note = " + .png" if png_ok else ""
        print(
            f"OK    {src_path.name} → {svg_path.name}{png_note} "
            f"({d.width:.0f}×{d.height:.0f})"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
