"""build_aois.py — single public entry point for AdSERP AOI extraction.

Pipeline (in order):

  1. CV row-projection on full-page screenshot → organic bboxes (pixel-
     accurate to the screenshot, the truth source).
  2. Apply midpoint-split to fill inter-result Y gaps (`organic_gapfill`).
  3. HTML widget typing + spatial join → typed AOI map.
  4. Export per-trial CSV/JSONL for downstream consumers.

Default flavor is `typed_gapfill` — the recommended public API for the
AdSERP resource paper (Latifzadeh, Gwizdka & Leiva SIGIR '25). Legacy
flavors remain queryable via the underlying scripts (`organic`,
`organic_hybrid`, `typed`) for cascade audits and historical comparison;
they are not the documented public interface.

Usage
-----

  # Single trial, default flavor (typed_gapfill):
  .venv/bin/python scripts/build_aois.py --trial p005-b2-t2

  # Full corpus (2,776 trials):
  .venv/bin/python scripts/build_aois.py --all

  # Skip the bbox-extraction step if organic-boundary-data/ is already
  # populated (e.g., when the screenshot volume isn't mounted but cached
  # bboxes exist on disk):
  .venv/bin/python scripts/build_aois.py --all --skip-extract

Outputs
-------

  AdSERP/data/organic-boundary-data-gapfill/<tid>.json     # bboxes
  data/aoi-typed-gapfill/<tid>.json                        # typed AOI map
  scripts/output/adserp_aois_by_trial_id_typed_gapfill.csv # corpus export
  scripts/output/adserp_aois_by_trial_id_typed_gapfill.jsonl

For attribution-flavor history and the full cascade rationale, see:
  docs/methodology/attribution-cascade-synthesis.md
  docs/null-findings/2026-05-05-bbox-y-coverage.md

Regime tag: [LAB, AdSERP, typed_gapfill]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "bin" / "python"
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str], step: str) -> int:
    """Run a subprocess; abort on failure."""
    print(f"\n── step: {step} ──")
    print(f"$ {' '.join(str(c) for c in cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(f"\n!! {step} failed (rc={proc.returncode})", file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--trial", help="Single trial ID, e.g. p005-b2-t2")
    target.add_argument("--all", action="store_true",
                        help="Full corpus (every trial with a local PNG)")
    parser.add_argument(
        "--flavor", default="typed_gapfill",
        choices=["typed_gapfill", "typed"],
        help="Public flavor (default typed_gapfill). 'typed' kept for "
             "backward compat; legacy flavors organic/organic_hybrid/"
             "absolute are not exposed by this entry point — use the "
             "underlying scripts directly if you need them.",
    )
    parser.add_argument(
        "--skip-extract", action="store_true",
        help="Skip CV bbox extraction (use existing organic-boundary-data/). "
             "Useful when the screenshot volume isn't mounted but cached "
             "bboxes exist on disk.",
    )
    parser.add_argument(
        "--skip-export", action="store_true",
        help="Skip the CSV/JSONL export step.",
    )
    args = parser.parse_args()

    py = str(PYTHON)
    target_arg = ["--all-cached"] if args.all else [args.trial]

    # Step 1: extract organic bboxes (CV row-projection on screenshots)
    if not args.skip_extract:
        run([py, str(SCRIPTS / "extract_organic_bboxes.py"), *target_arg],
            step="extract organic bboxes (CV)")

    # Step 2: midpoint-split gap-fill (organic_gapfill flavor)
    if args.flavor == "typed_gapfill":
        run([py, str(SCRIPTS / "apply_gapfill_to_existing.py")],
            step="apply midpoint-split gap-fill")

    # Step 3: HTML widget typing + spatial join → typed AOI map
    source = "organic_gapfill" if args.flavor == "typed_gapfill" else "organic"
    run([py, str(SCRIPTS / "build_typed_aoi_map.py"), "--source", source],
        step=f"build typed AOI map (--source {source})")

    # Step 4: per-trial CSV / JSONL export
    if not args.skip_export:
        run([py, str(SCRIPTS / "export_aois_by_trial_id.py"),
             "--attribution", args.flavor],
            step=f"export typed CSV (--attribution {args.flavor})")

    print(f"\n✓ build_aois complete. Flavor: {args.flavor}.")
    print(f"  Outputs:")
    if args.flavor == "typed_gapfill":
        print(f"    AdSERP/data/organic-boundary-data-gapfill/")
        print(f"    data/aoi-typed-gapfill/")
        print(f"    scripts/output/adserp_aois_by_trial_id_typed_gapfill.csv")
    else:
        print(f"    AdSERP/data/organic-boundary-data/")
        print(f"    data/aoi-typed/")
        print(f"    scripts/output/adserp_aois_by_trial_id_typed.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
