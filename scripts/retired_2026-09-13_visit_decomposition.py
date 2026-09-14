"""Per-(trial, AOI) visit decomposition on AdSERP: first visit vs subsequent visits.

WHY THIS EXISTS
---------------
The Leaky Cursor's dwell baseline, `total_dwell_ms`, sums EVERY fixation
attributed to an AOI -- including the return fixations that define the
`deferred` label it is being compared against. The baseline is therefore
partly computed from its own target. Measured first on Allawati's AO-SERP
corpus (collab/allawati-ai-overviews/abandonment-2026-09-13/FINDINGS.md):
LOSO AUC for deferred-vs-evaluated-rejected fell from 0.789 (total dwell) to
0.459 (first-visit dwell only), i.e. to chance.

This producer builds the same decomposition on AdSERP so the paper's own
dwell baseline can be re-quoted honestly, and so the first-vs-subsequent
visit distinction -- the paper's central construct -- is emitted as data
others can interrogate rather than inferred from an aggregate.

WHAT A "VISIT" IS
-----------------
Fixations are assigned to AOI positions with the substrate's own rule
(typed_gapfill by default). Unassigned fixations are skipped, matching
compute_regression_labels.py. A VISIT is a maximal run of consecutive
assigned fixations on the same position. n_visits >= 2 means the gaze left
for another AOI and came back.

TWO NOTIONS OF RETURN, DELIBERATELY BOTH EMITTED
------------------------------------------------
  `deferred`      -- the paper's label, ported verbatim from
                     compute_regression_labels.regressed_positions: the
                     position was fixated, max_seen advanced PAST it, and it
                     was fixated again. A return to the deepest-so-far result
                     does NOT count.
  `plain_revisit` -- n_visits >= 2, any return whatsoever.
These are not the same set and the difference is reported. A reviewer will
ask; the answer should be in the dump, not in a footnote.

OUTPUT
------
scripts/output/visit_decomposition/records.json  (one record per trial x AOI)
scripts/output/visit_decomposition/provenance.json

Run:
    .venv/bin/python scripts/visit_decomposition.py --attribution typed_gapfill
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# RETIRED 2026-09-13. DO NOT RUN. DO NOT CITE ITS NUMBERS.
#
# Built on the lineage retired from the paper on 2026-09-06: features from
# compute_cursor_approach_features.py / m4_nb21_hybrid_rerun.py (whose
# identically-named fields are gaze-cursor distances over fixation-selected
# rows) and labels from compute_regression_labels.py. Its outputs look
# canonical and are not.
#
# Canonical replacement: scripts/deferred_dwell_carve.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/deferred_dwell_carve.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")


import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_fixations,
    get_trial_meta,
    assign_fixation_to_position,
    typed_alignment_exclusions,
    typed_gapfill_aoi_tops,
    typed_gapfill_aoi_etypes,
    typed_aoi_tops,
    organic_aoi_tops,
    attribute_click_to_typed_gapfill,
    load_mouse_events,
)

OUT_DIR = ROOT / "scripts" / "output" / "visit_decomposition"


def tops_for(trial_id, attribution):
    if attribution == "typed_gapfill":
        return typed_gapfill_aoi_tops(trial_id), typed_gapfill_aoi_etypes(trial_id)
    if attribution == "typed":
        return typed_aoi_tops(trial_id), None
    return organic_aoi_tops(trial_id), None


def segment_visits(fixations, tops, n_res):
    """Return (visits_by_pos, pos_seq).

    visits_by_pos[pos] = [{'dwell_ms', 'n_fix', 't_start', 't_end'}, ...] in
    temporal order. A visit is a maximal run of consecutive assigned
    fixations on the same position.
    """
    visits_by_pos = defaultdict(list)
    pos_seq = []
    cur_pos, cur = None, None
    for f in fixations:
        p = assign_fixation_to_position(f["y"], tops, n_res)
        if p is None or p < 0:
            continue
        pos_seq.append(p)
        d = float(f.get("d", 200) or 200)
        if p != cur_pos:
            if cur is not None:
                visits_by_pos[cur_pos].append(cur)
            cur_pos = p
            cur = {"dwell_ms": 0.0, "n_fix": 0,
                   "t_start": float(f["t"]), "t_end": float(f["t"])}
        cur["dwell_ms"] += d
        cur["n_fix"] += 1
        cur["t_end"] = float(f["t"])
    if cur is not None:
        visits_by_pos[cur_pos].append(cur)
    return visits_by_pos, pos_seq


def deferred_positions(pos_seq):
    """Verbatim port of compute_regression_labels.regressed_positions."""
    visited, regressed, max_seen = set(), set(), -1
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressed.add(p)
        visited.add(p)
        max_seen = max(max_seen, p)
    return regressed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attribution", default="typed_gapfill",
                    choices=["typed_gapfill", "typed", "organic"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    excluded = set(typed_alignment_exclusions())
    trial_ids = get_trial_ids()
    if args.limit:
        trial_ids = trial_ids[: args.limit]

    records = []
    skipped = defaultdict(int)
    for i, trial_id in enumerate(trial_ids, 1):
        if i % 400 == 0:
            print(f"  {i}/{len(trial_ids)}", flush=True)
        if trial_id in excluded:
            skipped["alignment_exclusion"] += 1
            continue
        meta = get_trial_meta(trial_id)
        if meta is None or not meta[0]:
            skipped["no_meta"] += 1
            continue
        try:
            tops, etypes = tops_for(trial_id, args.attribution)
        except Exception:
            skipped["no_tops"] += 1
            continue
        if not tops:
            skipped["no_tops"] += 1
            continue
        n_res = len(tops)
        fixations = load_fixations(trial_id)
        if not fixations:
            skipped["no_fixations"] += 1
            continue

        visits_by_pos, pos_seq = segment_visits(fixations, tops, n_res)
        if not pos_seq:
            skipped["no_assigned_fixations"] += 1
            continue
        deferred = deferred_positions(pos_seq)

        # load_mouse_events returns (all_events, scrolls, clicks); clicks are
        # (t, x, y) tuples. AOI comparison REQUIRES screenshot space -- the
        # typed maps are 1280-wide screenshot space while evtrack records
        # 1403-wide document space, and mixing them is a silent error (see the
        # loader docstring: it put 22% of final clicks outside their AOI).
        try:
            _all, _scrolls, clicks = load_mouse_events(trial_id, space="screenshot")
        except Exception:
            clicks = []
        click_pos = None
        if clicks:
            # Signature is (click_x, click_y, trial_id) and it returns
            # (position, etype) or None -- NOT a bare int. Getting either wrong
            # raises inside, and a blanket except turns the whole corpus into
            # "no clicks" silently. Count failures instead of swallowing them.
            hit = attribute_click_to_typed_gapfill(
                clicks[-1][1], clicks[-1][2], trial_id)
            if hit is None:
                skipped["click_unattributed"] += 1
            else:
                click_pos = hit[0]

        for pos, visits in visits_by_pos.items():
            dwells = [v["dwell_ms"] for v in visits]
            first = dwells[0]
            total = sum(dwells)
            # Gap between leaving on the first visit and returning.
            gap_ms = (visits[1]["t_start"] - visits[0]["t_end"]) if len(visits) > 1 else None
            records.append({
                "trial_id": trial_id,
                "participant": trial_id.split("-")[0],
                "position": int(pos),
                "etype": (etypes[pos] if etypes and pos < len(etypes) else None),
                "n_results": n_res,
                "was_clicked": bool(click_pos is not None and click_pos == pos),
                "trial_has_click": bool(clicks),
                "deferred": bool(pos in deferred),
                "plain_revisit": bool(len(visits) > 1),
                "n_visits": len(visits),
                "first_visit_dwell_ms": float(first),
                "subsequent_dwell_ms": float(total - first),
                "total_dwell_ms": float(total),
                "n_fix_first_visit": int(visits[0]["n_fix"]),
                "n_fix_total": int(sum(v["n_fix"] for v in visits)),
                "return_gap_ms": (float(gap_ms) if gap_ms is not None else None),
                # Needed to apply the first-visit carve to VIEWPORT residence,
                # which has the same circular structure as total_dwell_ms: the
                # AOI must be on screen for the return fixation to happen, so
                # residence measured over the whole trial contains the label.
                "first_visit_start_ms": float(visits[0]["t_start"]),
                "first_visit_end_ms": float(visits[0]["t_end"]),
                "visit_dwells_ms": [float(d) for d in dwells],
            })

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        sha = "unknown"
    prov = {
        "produced_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "scripts/visit_decomposition.py",
        "attribution": args.attribution,
        "repo_head": sha,
        "n_trials_considered": len(trial_ids),
        "n_records": len(records),
        "n_trials_emitted": len({r["trial_id"] for r in records}),
        "skipped": dict(skipped),
        "label_port": "compute_regression_labels.regressed_positions (verbatim)",
    }
    json.dump(records, open(OUT_DIR / "records.json", "w"))
    json.dump(prov, open(OUT_DIR / "provenance.json", "w"), indent=1)
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main()
