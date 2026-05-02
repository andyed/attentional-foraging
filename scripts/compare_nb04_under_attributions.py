"""Side-by-side comparison: NB04 fixation coverage and per-position
fixation budget under absolute-rank vs organic-rank (bbox) attribution.

K-IDs of interest:
  K4  Mean share of results-above-click fixated (94.7%)
  K6  Mean share of max-scroll-depth results fixated (82.8%)
  K7  FV clickers — share of first-screen results fixated (68.3%)
  K8  Scrollers — share of first-screen results fixated (91.7%)
  K13 FV clickers — position 0 fixation budget (42%)
  K14 FV clickers — position 1 fixation budget (32%)
  K15 Scrollers — position 0 fixation budget (21%)
  K16 Scrollers — position 1 fixation budget (15%)

Output:
  scripts/output/aoi-consumer-cascade/nb04_comparison.md
  scripts/output/aoi-consumer-cascade/nb04_comparison.json
"""
from __future__ import annotations

import json
import sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_trial,
    count_results_html,
    result_band_tops,
    organic_aoi_tops,
)

OUT = ROOT / "scripts" / "output" / "aoi-consumer-cascade"
OUT.mkdir(parents=True, exist_ok=True)


def analyze_trial(t, tops, n_res, scr_h):
    """Returns dict with coverage + per-position budget for one trial under
    a single attribution. Returns None if unprocessable."""
    fixs = t.get("fixations", [])
    clicks = t.get("clicks", [])
    scrolls = t.get("scrolls", [])
    if not clicks:
        return None
    if not tops or n_res == 0:
        return None

    fix_per = defaultdict(float)
    for fix in fixs:
        pos = bisect_right(tops, fix["y"]) - 1
        if 0 <= pos < n_res:
            fix_per[pos] += fix["d"]

    cy = clicks[-1][2]
    click_pos = bisect_right(tops, cy) - 1
    if not (0 <= click_pos < n_res):
        return None

    # First-viewport positions: those whose top is within scr_h of page top
    first_vp_n = sum(1 for top in tops if top < scr_h)

    # Max scroll depth → max position visible
    max_scroll_y = max((s[1] for s in scrolls), default=0) + scr_h
    max_scroll_pos = 0
    for pos, top in enumerate(tops):
        if top < max_scroll_y:
            max_scroll_pos = pos

    # First-viewport click? (no significant scroll before click)
    if scrolls:
        click_t = clicks[-1][0]
        max_scroll_before_click = max((sy for st, sy in scrolls if st < click_t), default=0)
    else:
        max_scroll_before_click = 0
    is_fv = max_scroll_before_click < 50

    # Coverage above click
    above_click = list(range(click_pos + 1))
    fixated_above = sum(1 for p in above_click if fix_per.get(p, 0) > 0)

    # Coverage within scroll
    within_scroll = list(range(max_scroll_pos + 1))
    fixated_within_scroll = sum(1 for p in within_scroll if fix_per.get(p, 0) > 0)

    # First-viewport scanning
    fv_fixated = sum(1 for p in range(first_vp_n) if fix_per.get(p, 0) > 0)

    total_fix_time = sum(fix_per.values())

    return {
        "is_fv": is_fv,
        "click_pos": click_pos,
        "first_vp_n": first_vp_n,
        "max_scroll_pos": max_scroll_pos,
        "fixated_above_click": fixated_above,
        "above_click_n": len(above_click),
        "fixated_within_scroll": fixated_within_scroll,
        "within_scroll_n": len(within_scroll),
        "fv_fixated": fv_fixated,
        "fix_per": dict(fix_per),
        "total_fix_time": total_fix_time,
    }


def aggregate(rows, label):
    """Compute K4/K6/K7/K8/K13-K16 from a list of per-trial dicts."""
    fv = [r for r in rows if r["is_fv"]]
    sc = [r for r in rows if not r["is_fv"]]
    n = len(rows)

    # K4: mean share of results-above-click fixated
    k4 = np.mean([r["fixated_above_click"] / r["above_click_n"]
                   for r in rows if r["above_click_n"] > 0])

    # K6: mean share of max-scroll-depth results fixated
    k6 = np.mean([r["fixated_within_scroll"] / r["within_scroll_n"]
                   for r in rows if r["within_scroll_n"] > 0])

    # K7/K8: FV scanners — share of first-screen results fixated
    k7 = np.mean([r["fv_fixated"] / r["first_vp_n"] for r in fv if r["first_vp_n"] > 0])
    k8 = np.mean([r["fv_fixated"] / r["first_vp_n"] for r in sc if r["first_vp_n"] > 0])

    # K13/K14: per-position budget for FV clickers
    fv_pos_budget = defaultdict(list)
    for r in fv:
        if r["total_fix_time"] > 0:
            for p, t in r["fix_per"].items():
                fv_pos_budget[p].append(t / r["total_fix_time"])
    sc_pos_budget = defaultdict(list)
    for r in sc:
        if r["total_fix_time"] > 0:
            for p, t in r["fix_per"].items():
                sc_pos_budget[p].append(t / r["total_fix_time"])

    return {
        "label": label,
        "n_total": n, "n_fv": len(fv), "n_sc": len(sc),
        "K4": k4, "K6": k6, "K7": k7, "K8": k8,
        "fv_pos_budget_mean": {p: float(np.mean(vs)) for p, vs in fv_pos_budget.items() if vs},
        "sc_pos_budget_mean": {p: float(np.mean(vs)) for p, vs in sc_pos_budget.items() if vs},
    }


def main():
    tids = get_trial_ids()
    abs_rows = []
    org_rows = []
    skipped = 0

    for tid in tids:
        try:
            t = load_trial(tid)
            if t is None:
                skipped += 1; continue
            doc_h = t.get("doc_height")
            scr_h = t.get("screen_height")
            if not doc_h or not scr_h:
                skipped += 1; continue

            n_abs = count_results_html(tid)
            tops_abs = result_band_tops(n_abs, doc_h) if n_abs else None
            tops_org = organic_aoi_tops(tid)

            r_abs = analyze_trial(t, tops_abs, n_abs, scr_h) if tops_abs else None
            r_org = analyze_trial(t, tops_org, len(tops_org), scr_h) if tops_org else None
            if r_abs:
                abs_rows.append(r_abs)
            if r_org:
                org_rows.append(r_org)
        except Exception as e:
            skipped += 1
            print(f"  SKIP {tid}: {e}", file=sys.stderr)

    abs_agg = aggregate(abs_rows, "absolute")
    org_agg = aggregate(org_rows, "organic")

    print(f"Trials processed: abs={len(abs_rows)}, org={len(org_rows)} (skipped {skipped})")

    out_lines = []
    out_lines.append("# NB04 K-ID comparison: absolute rank vs organic rank")
    out_lines.append("")
    out_lines.append(f"Generated by `scripts/compare_nb04_under_attributions.py`. abs_n={len(abs_rows)}, org_n={len(org_rows)}.")
    out_lines.append("")
    out_lines.append("## NB04 K-ID side-by-side")
    out_lines.append("")
    out_lines.append("| K | Claim | Absolute | Organic |")
    out_lines.append("|---|---|---|---|")
    out_lines.append(f"| K1 | Trials processed | {abs_agg['n_total']:,} | {org_agg['n_total']:,} |")
    out_lines.append(f"| K2 | First-viewport clickers | {abs_agg['n_fv']:,} ({100*abs_agg['n_fv']/abs_agg['n_total']:.1f}%) | {org_agg['n_fv']:,} ({100*org_agg['n_fv']/org_agg['n_total']:.1f}%) |")
    out_lines.append(f"| K3 | Scrollers | {abs_agg['n_sc']:,} | {org_agg['n_sc']:,} |")
    out_lines.append(f"| **K4** | Mean share of results-above-click fixated | **{100*abs_agg['K4']:.1f}%** | **{100*org_agg['K4']:.1f}%** |")
    out_lines.append(f"| K6 | Mean share of max-scroll-depth results fixated | {100*abs_agg['K6']:.1f}% | {100*org_agg['K6']:.1f}% |")
    out_lines.append(f"| **K7** | FV clickers — share of first-screen results fixated | **{100*abs_agg['K7']:.1f}%** | **{100*org_agg['K7']:.1f}%** |")
    out_lines.append(f"| **K8** | Scrollers — share of first-screen results fixated | **{100*abs_agg['K8']:.1f}%** | **{100*org_agg['K8']:.1f}%** |")
    out_lines.append("")

    out_lines.append("## Per-position fixation budget (mean share of total fixation time)")
    out_lines.append("")
    out_lines.append("### FV clickers")
    out_lines.append("")
    out_lines.append("| Position | Absolute % | Organic % |")
    out_lines.append("|---|---|---|")
    max_p = max(max(abs_agg["fv_pos_budget_mean"].keys(), default=0),
                max(org_agg["fv_pos_budget_mean"].keys(), default=0))
    for p in range(min(max_p + 1, 11)):
        a = 100 * abs_agg["fv_pos_budget_mean"].get(p, 0)
        o = 100 * org_agg["fv_pos_budget_mean"].get(p, 0)
        bold = "**" if p in (0, 1) else ""
        out_lines.append(f"| {bold}{p}{bold} | {bold}{a:.1f}%{bold} | {bold}{o:.1f}%{bold} |")
    out_lines.append("")
    out_lines.append("### Scrollers")
    out_lines.append("")
    out_lines.append("| Position | Absolute % | Organic % |")
    out_lines.append("|---|---|---|")
    for p in range(min(max_p + 1, 11)):
        a = 100 * abs_agg["sc_pos_budget_mean"].get(p, 0)
        o = 100 * org_agg["sc_pos_budget_mean"].get(p, 0)
        bold = "**" if p in (0, 1) else ""
        out_lines.append(f"| {bold}{p}{bold} | {bold}{a:.1f}%{bold} | {bold}{o:.1f}%{bold} |")
    out_lines.append("")

    md_out = OUT / "nb04_comparison.md"
    md_out.write_text("\n".join(out_lines))
    json_out = OUT / "nb04_comparison.json"
    json_out.write_text(json.dumps({"abs": abs_agg, "org": org_agg}, indent=2))
    print(f"Wrote {md_out}")
    print(f"Wrote {json_out}")
    print()
    print("\n".join(out_lines[:30]))


if __name__ == "__main__":
    raise SystemExit(main())
