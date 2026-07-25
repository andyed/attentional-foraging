#!/usr/bin/env python3
"""Validate the typed-AOI migration and map its tech debt.

The typed-AOI layer (full element typing, dd_top differentiation) is a migration in
progress. This auditor inventories the AOI maps, the canonical scanpath source, and the
downstream feature artifacts that depend on them, and flags integrity gaps + stale
provenance. The output doubles as a regression guard: re-run after each migration step.

Stdlib only -- runs anywhere. Read-only except for the report it writes to scripts/output/.

Position convention (per notebooks-v2/data_loader.py):
  position >= 0  -> card is on the main scroll axis (organic, ads, PAA, etc.)
  position == -1 -> off-axis by design (chrome, dd_right, #botstuff related-searches,
                    #rhs knowledge panel, below-fold html_only results). These legitimately
                    have NO CV bbox. So a null bbox at position == -1 is EXPECTED; a null
                    bbox at position >= 0 is the real defect ("anomalous null").

Checks
  1. Type histogram        : full per-type inventory of the canonical flavor.
  2. dd_top spotlight      : counts for the pending AllSERP dd_top documentation.
  3. Flavor comparison     : aoi-typed vs gapfill vs html-types; which carries dd_top.
  4. Null-bbox triage      : by-design (pos -1) vs ANOMALOUS (pos >= 0) -- the integrity flag.
  5. Scanpath source       : canonical = AdSERP/data/fixation-data (all trials); the
                             fixation-resolved/ dir is a 31-trial viewer export.
  6. Stale provenance      : downstream feature JSONs older than the AOI maps / producers.
"""

from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
FIX_RESOLVED = REPO / "fixation-resolved"            # viewer export (31 curated trials)
FIX_DATA = REPO / "AdSERP" / "data" / "fixation-data"  # canonical scanpath source (all trials)
ADSERP_DATA = REPO / "AdSERP" / "data"
OUT = REPO / "scripts" / "output" / "typed_aoi_migration_audit.md"

FLAVORS = ["aoi-typed", "aoi-typed-gapfill", "aoi-html-types"]

# Canonical AllSERP element types (the 13). dd_top differentiation is the migration's point.
CANONICAL_TYPES = {
    "organic", "dd_top", "native_ad", "dd_right", "top_places", "knowledge_panel",
    "paa", "image_pack", "related_searches", "pagination", "other_widget",
    "unknown_widget", "chrome",
}
BBOX_KEYS = ("x", "y", "width", "height")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text()), None
    except Exception as e:  # malformed JSON is itself a finding
        return None, f"{type(e).__name__}: {e}"


def inventory_flavor(name: str) -> dict:
    d = DATA / name
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    type_counts: Counter[str] = Counter()
    placed_by_type: Counter[str] = Counter()        # bbox present
    null_bbox_by_type: Counter[str] = Counter()     # bbox absent (any reason)
    anomalous_null: Counter[str] = Counter()        # bbox absent AND position >= 0 (real defect)
    unknown_types: Counter[str] = Counter()
    trials_with_type: Counter[str] = Counter()
    bad_files: list[tuple[str, str]] = []
    for f in files:
        raw, err = _load_json(f)
        if err is not None:
            bad_files.append((f.name, err))
            continue
        if not isinstance(raw, list):
            bad_files.append((f.name, f"top-level {type(raw).__name__}, expected list"))
            continue
        seen: set[str] = set()
        for a in raw:
            t = a.get("type", "<missing>")
            type_counts[t] += 1
            seen.add(t)
            if t not in CANONICAL_TYPES:
                unknown_types[t] += 1
            if any(a.get(k) is None for k in BBOX_KEYS):
                null_bbox_by_type[t] += 1
                pos = a.get("position", -1)
                if isinstance(pos, int) and pos >= 0:
                    anomalous_null[t] += 1
            else:
                placed_by_type[t] += 1
        for t in seen:
            trials_with_type[t] += 1
    return {
        "dir_exists": d.is_dir(),
        "n_files": len(files),
        "n_aois": sum(type_counts.values()),
        "type_counts": type_counts,
        "placed_by_type": placed_by_type,
        "null_bbox_by_type": null_bbox_by_type,
        "anomalous_null": anomalous_null,
        "unknown_types": unknown_types,
        "trials_with_type": trials_with_type,
        "bad_files": bad_files,
        "has_dd_top": type_counts.get("dd_top", 0) > 0,
    }


def scan_resolved() -> dict:
    files = sorted(FIX_RESOLVED.glob("*.json")) if FIX_RESOLVED.is_dir() else []
    bad: list[tuple[str, str]] = []
    for f in files:
        raw, err = _load_json(f)
        if err is not None:
            bad.append((f.name, err))
            continue
        if not isinstance(raw, list):
            bad.append((f.name, f"top-level {type(raw).__name__}, expected list"))
            continue
        for i, rec in enumerate(raw):
            if rec is None:
                bad.append((f.name, f"null fixation record at index {i}"))
                break
            if not (isinstance(rec, dict) and rec.get("x") is not None and rec.get("y") is not None):
                bad.append((f.name, f"malformed record at index {i}: {rec!r}"))
                break
    return {"n_files": len(files), "bad_files": bad}


def newest_mtime(paths: list[Path]) -> float:
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def check_provenance() -> dict:
    upstream_paths = list((DATA / "aoi-typed").glob("*.json"))
    for pat in ("build_typed_aoi_map.py", "build_aois.py", "build_typed_aoi*.py", "*typed*aoi*.py"):
        upstream_paths += [Path(p) for p in glob.glob(str(REPO / "scripts" / pat))]
    upstream = newest_mtime(upstream_paths)
    stale: list[tuple[str, float]] = []
    fresh = 0
    downstream = sorted(ADSERP_DATA.glob("*.json")) if ADSERP_DATA.is_dir() else []
    for f in downstream:
        if f.stat().st_mtime < upstream:
            stale.append((f.name, (upstream - f.stat().st_mtime) / 86400))
        else:
            fresh += 1
    stale.sort(key=lambda t: t[1], reverse=True)
    return {"n_downstream": len(downstream), "n_fresh": fresh, "stale": stale}


def main() -> None:
    invs = {name: inventory_flavor(name) for name in FLAVORS}
    resolved = scan_resolved()
    prov = check_provenance()

    present = {n: i for n, i in invs.items() if i["dir_exists"]}
    canon = "aoi-typed" if "aoi-typed" in present else (next(iter(present), None))
    cinv = present.get(canon)

    # Scanpath source coverage: canonical (AdSERP fixation-data) vs viewer export.
    fixdata_ids = {p.stem for p in FIX_DATA.glob("*.csv")} if FIX_DATA.is_dir() else set()
    aoi_ids = {p.stem for p in (DATA / "aoi-typed").glob("*.json")}

    lines: list[str] = []
    p = lines.append
    p("# Typed-AOI migration audit\n")
    p("_Generated by `scripts/validate_typed_aoi_migration.py`. Read-only; re-run as a "
      "regression guard after each migration step._\n")

    # ── 1. Type histogram (canonical) ──
    if cinv:
        p(f"## 1. Type histogram — canonical flavor `{canon}`\n")
        p("| type | AOIs | trials | placed (bbox) | null (pos −1, by-design) | **anomalous null (pos ≥ 0)** |")
        p("|---|--:|--:|--:|--:|--:|")
        for t, n in cinv["type_counts"].most_common():
            placed = cinv["placed_by_type"].get(t, 0)
            nullb = cinv["null_bbox_by_type"].get(t, 0)
            anom = cinv["anomalous_null"].get(t, 0)
            trials = cinv["trials_with_type"].get(t, 0)
            mark = f"**{anom}**" if anom else "0"
            p(f"| `{t}` | {n} | {trials} | {placed} | {nullb} | {mark} |")
        p("")

    # ── 2. dd_top spotlight (for the AllSERP documentation) ──
    if cinv:
        ddc = cinv["type_counts"].get("dd_top", 0)
        ddt = cinv["trials_with_type"].get("dd_top", 0)
        ddp = cinv["placed_by_type"].get("dd_top", 0)
        nf = cinv["n_files"]
        p("## 2. dd_top spotlight (AllSERP dd_top-differentiation documentation)\n")
        p(f"- dd_top AOIs: **{ddc}**  across **{ddt}** trials ({100*ddt/max(nf,1):.1f}% of {nf})")
        p(f"- placed with CV bbox: **{ddp}** ({100*ddp/max(ddc,1):.1f}%)  | null-bbox dd_top: {ddc-ddp}")
        p(f"- differentiated in: " + ", ".join(
            f"`{n}`={'YES' if i['has_dd_top'] else 'NO'}" for n, i in invs.items() if i["dir_exists"]))
        p("")

    # ── 3. Flavor comparison ──
    p("## 3. Flavor comparison\n")
    p("| flavor | files | AOIs | dd_top? | null-bbox | **anomalous null** |")
    p("|---|--:|--:|:--:|--:|--:|")
    for name, inv in invs.items():
        if not inv["dir_exists"]:
            p(f"| `{name}` | (missing) | | | | |")
            continue
        nb = sum(inv["null_bbox_by_type"].values())
        anom = sum(inv["anomalous_null"].values())
        p(f"| `{name}` | {inv['n_files']} | {inv['n_aois']} | "
          f"{'YES' if inv['has_dd_top'] else 'NO'} | {nb} | **{anom}** |")
    p(f"\n**Canonical:** `{canon}` (dd_top differentiated, CV bboxes). "
      "`aoi-html-types` is the pre-typing HTML-only layer (no dd_top, no bboxes).\n")

    # ── 4. Null-bbox triage ──
    if cinv:
        total_null = sum(cinv["null_bbox_by_type"].values())
        total_anom = sum(cinv["anomalous_null"].values())
        p("## 4. Null-bbox triage (canonical)\n")
        p(f"- total null-bbox AOIs: {total_null} — **{total_null - total_anom} by-design** "
          f"(position −1: off-axis chrome / dd_right / botstuff / rhs / below-fold html_only)")
        p(f"- **ANOMALOUS null (position ≥ 0, real defect): {total_anom}**")
        if cinv["anomalous_null"]:
            for t, n in cinv["anomalous_null"].most_common():
                p(f"  - `{t}`: {n}")
        else:
            p("  - none — every null-bbox AOI is a legitimately off-axis (position −1) element.")
        p("")

    # ── 5. Scanpath source ──
    p("## 5. Scanpath source\n")
    p(f"- **Canonical** (`AdSERP/data/fixation-data/*.csv`, FPOGX/FPOGY/FPOGD): "
      f"**{len(fixdata_ids)}** trials, with durations + timestamps. Load via "
      "`notebooks-v2/data_loader.load_fixations`.")
    p(f"- joinable with typed AOIs (`aoi-typed`): **{len(fixdata_ids & aoi_ids)}** trials")
    p(f"- `fixation-resolved/` is a viewer export only: {resolved['n_files']} trials, "
      f"{len(resolved['bad_files'])} with null/malformed records "
      + (f"({', '.join(f for f, _ in resolved['bad_files'])})" if resolved["bad_files"] else "")
      + ". Do NOT use as the analysis scanpath source.")
    p("")

    # ── 6. Stale provenance ──
    p("## 6. Stale provenance (downstream older than AOI maps / producers)\n")
    p(f"- downstream feature files in `AdSERP/data/`: {prov['n_downstream']}  | "
      f"fresh: {prov['n_fresh']}  | **stale (review): {len(prov['stale'])}**")
    p("- _mtime heuristic: a fresh `git checkout` resets mtimes, so treat as a review "
      "list, not proof. Verify against producer provenance._")
    for fn, age in prov["stale"][:30]:
        p(f"  - `{fn}` — {age:.1f} d older than newest upstream")
    if len(prov["stale"]) > 30:
        p(f"  - … and {len(prov['stale']) - 30} more")
    p("")

    report = "\n".join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report)
    print(report)
    print(f"\n[written] {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
