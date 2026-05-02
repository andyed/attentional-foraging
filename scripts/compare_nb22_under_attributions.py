"""Side-by-side comparison: NB22 four-class taxonomy distribution under
absolute-rank vs organic-rank (bbox) attribution.

NB22 builds gaze-based regression labels per (trial, organic-position):
a position is "regressed" iff the user visited it, advanced past it
(max_seen progressed), and later revisited it. The four-class taxonomy
combines this gaze label with click data:
  - clicked = clicked position
  - deferred = visited + regressed (visited again after max_seen advanced)
  - evaluated_rejected = visited but not regressed, not clicked
  - not_approached = not visited

This script computes both label distributions and compares them.

Output:
  scripts/output/aoi-consumer-cascade/nb22_comparison.md
  scripts/output/aoi-consumer-cascade/nb22_comparison.json
"""
from __future__ import annotations

import json
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    get_trial_meta,
    count_results_html,
    result_band_tops,
    organic_aoi_tops,
    assign_fixation_to_position,
)

OUT = ROOT / "scripts" / "output" / "aoi-consumer-cascade"
OUT.mkdir(parents=True, exist_ok=True)


def regression_label_set(fixations, tops, n_res):
    """Return set of positions classified as 'regressed' per NB22's algorithm."""
    pos_seq = []
    for fix in fixations:
        p = assign_fixation_to_position(fix["y"], tops, n_res)
        if p is not None and p >= 0:
            pos_seq.append(p)

    max_seen = -1
    visited = set()
    regressed_pos = set()
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressed_pos.add(p)
        visited.add(p)
        max_seen = max(max_seen, p)
    return visited, regressed_pos


def four_class_for_trial(visited, regressed, click_pos, n_res):
    """Return Counter of {'clicked', 'deferred', 'evaluated_rejected', 'not_approached'}
    for the n_res positions on this trial."""
    c = Counter()
    for p in range(n_res):
        if click_pos is not None and p == click_pos:
            c["clicked"] += 1
        elif p in regressed:
            c["deferred"] += 1
        elif p in visited:
            c["evaluated_rejected"] += 1
        else:
            c["not_approached"] += 1
    return c


def main():
    tids = get_trial_ids()

    # Aggregate stats under each attribution
    stats = {
        "abs": {"counts": Counter(), "n_trials": 0, "n_visited": 0, "n_regressed": 0},
        "org": {"counts": Counter(), "n_trials": 0, "n_visited": 0, "n_regressed": 0},
    }
    # Per-trial label change tracking
    per_trial_diff = []  # {tid, abs_counts, org_counts}

    skipped = 0
    for tid in tids:
        try:
            fix = load_fixations(tid)
            if not fix:
                skipped += 1; continue
            meta = get_trial_meta(tid)
            if meta is None or not meta[0]:
                skipped += 1; continue
            doc_h = meta[0]
            _, scrolls, clicks = load_mouse_events(tid)

            n_abs = count_results_html(tid)
            tops_abs = result_band_tops(n_abs, doc_h) if n_abs else None
            tops_org = organic_aoi_tops(tid)
            n_org = len(tops_org)
            if not tops_abs or not tops_org:
                skipped += 1; continue

            # Click position under each attribution
            click_pos_abs = click_pos_org = None
            if clicks:
                cy = clicks[-1][2]
                cp_abs = bisect_right(tops_abs, cy) - 1
                cp_org = bisect_right(tops_org, cy) - 1
                if 0 <= cp_abs < n_abs:
                    click_pos_abs = cp_abs
                if 0 <= cp_org < n_org:
                    click_pos_org = cp_org

            # Regression labels under each
            v_abs, r_abs = regression_label_set(fix, tops_abs, n_abs)
            v_org, r_org = regression_label_set(fix, tops_org, n_org)

            c_abs = four_class_for_trial(v_abs, r_abs, click_pos_abs, n_abs)
            c_org = four_class_for_trial(v_org, r_org, click_pos_org, n_org)

            for k, n in c_abs.items(): stats["abs"]["counts"][k] += n
            for k, n in c_org.items(): stats["org"]["counts"][k] += n
            stats["abs"]["n_trials"] += 1
            stats["org"]["n_trials"] += 1
            stats["abs"]["n_visited"] += len(v_abs)
            stats["abs"]["n_regressed"] += len(r_abs)
            stats["org"]["n_visited"] += len(v_org)
            stats["org"]["n_regressed"] += len(r_org)

            per_trial_diff.append({
                "tid": tid,
                "abs": dict(c_abs), "org": dict(c_org),
                "abs_visited": len(v_abs), "org_visited": len(v_org),
                "abs_regressed": len(r_abs), "org_regressed": len(r_org),
            })

        except Exception as e:
            skipped += 1
            print(f"  SKIP {tid}: {e}", file=sys.stderr)

    n_used = stats["abs"]["n_trials"]
    print(f"Trials processed: {n_used} (skipped {skipped})")

    out_lines = []
    out_lines.append("# NB22 four-class taxonomy comparison: absolute rank vs organic rank")
    out_lines.append("")
    out_lines.append(f"Generated by `scripts/compare_nb22_under_attributions.py` on n={n_used} trials.")
    out_lines.append("")
    out_lines.append("## Tl;dr")
    out_lines.append("")
    out_lines.append("Per-AOI four-class label distribution under each attribution. The class **denominator** is `n_results` per trial, which differs between methods (absolute counts h3+ads; organic counts bbox-organic). So the raw counts differ by construction; the **share within trial** is the comparable quantity.")
    out_lines.append("")
    out_lines.append("Critical for AR demo rebuild: if a position's class changes (e.g., absolute label says 'clicked' but organic label says 'evaluated_rejected'), the curated examples in `approach-retreat/site/replay/data/curation.json` may have stale captions.")
    out_lines.append("")

    abs_total = sum(stats["abs"]["counts"].values())
    org_total = sum(stats["org"]["counts"].values())

    out_lines.append("## Class distribution (raw count + share)")
    out_lines.append("")
    out_lines.append("| Class | Absolute count | Absolute share | Organic count | Organic share |")
    out_lines.append("|---|---|---|---|---|")
    for cls in ["clicked", "deferred", "evaluated_rejected", "not_approached"]:
        ca = stats["abs"]["counts"][cls]
        co = stats["org"]["counts"][cls]
        sa = 100 * ca / abs_total if abs_total else 0
        so = 100 * co / org_total if org_total else 0
        out_lines.append(f"| {cls} | {ca:,} | {sa:.1f}% | {co:,} | {so:.1f}% |")
    out_lines.append(f"| **TOTAL** | **{abs_total:,}** | 100% | **{org_total:,}** | 100% |")
    out_lines.append("")

    avg_visited_abs = stats["abs"]["n_visited"] / n_used if n_used else 0
    avg_regressed_abs = stats["abs"]["n_regressed"] / n_used if n_used else 0
    avg_visited_org = stats["org"]["n_visited"] / n_used if n_used else 0
    avg_regressed_org = stats["org"]["n_regressed"] / n_used if n_used else 0
    out_lines.append("## Per-trial averages")
    out_lines.append("")
    out_lines.append("| | Absolute | Organic | Note |")
    out_lines.append("|---|---|---|---|")
    out_lines.append(f"| Mean visited positions / trial | {avg_visited_abs:.2f} | {avg_visited_org:.2f} | bbox tighter (ad/widget visits excluded) |")
    out_lines.append(f"| Mean regressed positions / trial | {avg_regressed_abs:.2f} | {avg_regressed_org:.2f} | |")
    out_lines.append(f"| % of visited that are regressed | {100*avg_regressed_abs/max(avg_visited_abs,1):.1f}% | {100*avg_regressed_org/max(avg_visited_org,1):.1f}% | |")
    out_lines.append("")

    # Trials where the four-class profile changed in a notable way
    n_trials_with_label_shift = 0
    n_trials_clicked_shifted = 0
    n_trials_deferred_shifted = 0
    for d in per_trial_diff:
        if d["abs"] != d["org"]:
            n_trials_with_label_shift += 1
            if d["abs"].get("clicked", 0) != d["org"].get("clicked", 0):
                n_trials_clicked_shifted += 1
            if d["abs"].get("deferred", 0) != d["org"].get("deferred", 0):
                n_trials_deferred_shifted += 1
    out_lines.append("## Per-trial label stability")
    out_lines.append("")
    out_lines.append(f"- Trials with any label-distribution change: **{n_trials_with_label_shift}/{n_used} = {100*n_trials_with_label_shift/n_used:.1f}%**")
    out_lines.append(f"- Trials where 'clicked' count differs (click attribution shifted between organic and ad/widget): {n_trials_clicked_shifted}")
    out_lines.append(f"- Trials where 'deferred' count differs (regression detection picked up different positions): {n_trials_deferred_shifted}")
    out_lines.append("")
    out_lines.append("**Implication for AR replay rebuild:** if X% of trials have shifted labels, the curated captions in curation.json may be stale for that fraction. Spot-check before re-publishing.")
    out_lines.append("")

    md_out = OUT / "nb22_comparison.md"
    md_out.write_text("\n".join(out_lines))
    json_out = OUT / "nb22_comparison.json"
    json_out.write_text(json.dumps({
        "n_trials_processed": n_used,
        "abs_class_counts": dict(stats["abs"]["counts"]),
        "org_class_counts": dict(stats["org"]["counts"]),
        "abs_total": abs_total,
        "org_total": org_total,
        "abs_avg_visited": avg_visited_abs,
        "org_avg_visited": avg_visited_org,
        "abs_avg_regressed": avg_regressed_abs,
        "org_avg_regressed": avg_regressed_org,
        "n_trials_with_label_shift": n_trials_with_label_shift,
        "n_trials_clicked_shifted": n_trials_clicked_shifted,
        "n_trials_deferred_shifted": n_trials_deferred_shifted,
    }, indent=2))
    print(f"Wrote {md_out}")
    print(f"Wrote {json_out}")
    print()
    print("\n".join(out_lines[:40]))


if __name__ == "__main__":
    raise SystemExit(main())
