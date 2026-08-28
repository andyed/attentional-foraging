"""Render screenshot + typed-AOI overlay so a human can verify the Phase-2 map.

Draws each entry of data/aoi-typed/<tid>.json (position >= 0, plus dd_right)
on the full-page screenshot: colored box, `pos:type` label, and the matched
heading text — so a shifted bbox<->card match is visible at a glance
(the failure mode: a maps/local-pack bbox labeled with the first organic's
heading, every heading below it one card off; see audit_local_pack_aois.py).

Outputs to scripts/output/typed-aoi-verify/{trial}.png

Run:
  .venv/bin/python scripts/verify_typed_aoi_map.py p040-b4-t6 p040-b1-t7
  .venv/bin/python scripts/verify_typed_aoi_map.py --sample-mis-shifted 6
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PNG_DIR = ROOT / "AdSERP" / "data" / "full-page-screenshots"
TYPED_DIR = ROOT / "data" / "aoi-typed"
OUT_DIR = ROOT / "scripts" / "output" / "typed-aoi-verify"
AUDIT_JSONL = ROOT / "scripts" / "output" / "aoi-typed" / "audit_local_pack_trials.jsonl"

COLORS = {
    "organic":          (0, 200, 80),     # green
    "top_places":       (30, 110, 255),   # blue — the maps/local pack
    "paa":              (150, 90, 255),   # violet
    "knowledge_panel":  (90, 170, 255),   # light blue
    "image_pack":       (0, 190, 190),    # teal
    "related_searches": (160, 160, 60),   # olive
    "dd_top":           (220, 130, 30),   # orange
    "native_ad":        (220, 60, 60),    # red
    "dd_right":         (180, 60, 200),   # purple
    "unknown_widget":   (140, 140, 140),  # gray
    "other_widget":     (140, 140, 140),
    "chrome":           (90, 90, 90),
    "pagination":       (90, 90, 90),
}
FALLBACK = (255, 200, 0)


def render(trial_id: str) -> Path | None:
    png = PNG_DIR / f"{trial_id}.png"
    js = TYPED_DIR / f"{trial_id}.json"
    if not png.exists() or not js.exists():
        print(f"skip {trial_id} (missing "
              f"{'png' if not png.exists() else 'typed json'})", file=sys.stderr)
        return None

    img = Image.open(png).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    entries = json.loads(js.read_text())

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        font = font_sm = ImageFont.load_default()

    for e in entries:
        if e.get("x") is None or e.get("y") is None:
            continue
        x, y, w, h = e["x"], e["y"], e["width"], e["height"]
        color = COLORS.get(e["type"], FALLBACK)
        draw.rectangle([x, y, x + w, y + h], outline=color + (255,), width=4)
        label = f"{e['position']}:{e['type']}"
        heading = (e.get("heading_text") or "")[:40]
        draw.rectangle([x, y - 30, x + 12 + 13 * len(label), y],
                       fill=color + (220,))
        draw.text((x + 6, y - 28), label, fill=(255, 255, 255), font=font)
        if heading:
            draw.text((x + w + 8, y), heading, fill=color, font=font_sm)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{trial_id}.png"
    img.save(out)
    print(f"wrote {out.relative_to(ROOT)}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trials", nargs="*", help="trial ids (e.g. p040-b4-t6)")
    ap.add_argument("--sample-pack-trials", type=int, default=0, metavar="N",
                    help="also render N random trials with an out-of-rso "
                         "local pack, from the audit JSONL (seeded)")
    args = ap.parse_args()

    trials = list(args.trials)
    if args.sample_pack_trials:
        tids = [json.loads(line)["tid"]
                for line in AUDIT_JSONL.read_text().splitlines()
                if "out_of_rso_main" in json.loads(line)["locations"]]
        rng = random.Random(40)  # stable sample across runs
        trials += rng.sample(tids, min(args.sample_pack_trials, len(tids)))

    if not trials:
        ap.error("no trials given")
    for tid in trials:
        render(tid)


if __name__ == "__main__":
    main()
