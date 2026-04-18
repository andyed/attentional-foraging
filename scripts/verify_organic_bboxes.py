"""Render screenshot + bbox overlay so a human can verify organic detection.

Outputs to scripts/output/organic-bbox-verify/{trial}.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PNG_DIR = ROOT / "AdSERP" / "data" / "full-page-screenshots"
ORGANIC_DIR = ROOT / "AdSERP" / "data" / "organic-boundary-data"
OUT_DIR = ROOT / "scripts" / "output" / "organic-bbox-verify"

COLORS = {
    "organic_result": (0, 200, 80),   # green
    "native_ad":      (220, 60, 60),  # red
    "dd_top":         (220, 130, 30), # orange
    "dd_right":       (180, 60, 200), # purple
}


def render(trial_id: str) -> Path | None:
    png = PNG_DIR / f"{trial_id}.png"
    js = ORGANIC_DIR / f"{trial_id}.json"
    if not png.exists() or not js.exists():
        print(f"skip {trial_id}", file=sys.stderr)
        return None

    img = Image.open(png).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    data = json.loads(js.read_text())

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font = ImageFont.load_default()

    for kind, color in COLORS.items():
        for item in data.get(kind, []):
            x = item["location"]["x"]
            y = item["location"]["y"]
            w = item["size"]["width"]
            h = item["size"]["height"]
            draw.rectangle([x, y, x + w, y + h], outline=color + (255,), width=4)
            label = kind if "position" not in item else f"{kind}_{item['position']}"
            tw, th = draw.textbbox((0, 0), label, font=font)[2:]
            draw.rectangle([x, y, x + tw + 12, y + th + 8], fill=color + (220,))
            draw.text((x + 6, y + 4), label, fill=(255, 255, 255), font=font)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{trial_id}.png"
    img.save(out)
    return out


def main() -> int:
    trials = sys.argv[1:] or [p.stem for p in ORGANIC_DIR.glob("*.json")]
    for t in trials:
        out = render(t)
        if out:
            print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
