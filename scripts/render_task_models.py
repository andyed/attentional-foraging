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
        out_path = src_path.with_suffix(".svg")
        out_path.write_text(d.svg)
        print(f"OK    {src_path.name} → {out_path.name} ({d.width:.0f}×{d.height:.0f})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
