#!/usr/bin/env python3
"""PAI per-etype census + anticipation horizon (track worklist items 2–3).

Kernel: **spec_eq2** (the authors' Eq. 2 via `pai_spec.rect_alpha_grid`) —
bare "PAI" per the 2026-08-31 kernel policy. Regime
[LAB, AdSERP, organic_hybrid, full-trial].

Q3 — peripheral intake without entry (banner blindness, measured).
  The feature producer only emits records for AOIs that received >=1
  fixation, so never-fixated slots are enumerated here from
  build_hybrid_aois() directly. Per etype: entry rate, click rate, and
  full-trial peripheral PAI mass split by entered vs never-entered.
  Distinguishes "peripherally sampled then skipped" from "never sampled
  at all" via the never-entered mass distribution.

Q2 — anticipation horizon.
  For entered AOIs, cumulative spec_eq2 mass as a function of time before
  first fixation entry (500 ms bins over [-8000, 0) ms), clicked vs
  entered-non-clicked. Median cumulative-share curves: how far ahead of
  foveation does the clicked item's peripheral mass separate?

Output: scripts/output/ablations/pai_etype_census.json + stdout tables.
Run: .venv/bin/python scripts/pai_etype_census.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from data_loader import load_fixations  # noqa: E402
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402
from pai_spec import rect_alpha_grid  # noqa: E402

FEATURES = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid.json"
OUT = ROOT / "scripts/output/ablations/pai_etype_census.json"

BIN_MS = 500
HORIZON_MS = 8000
N_BINS = HORIZON_MS // BIN_MS


def trial_alpha(trial_id):
    """(ft, fd, alpha_spec[fix, aoi], outside[fix, aoi], etypes) or None."""
    try:
        fixations = load_fixations(trial_id)
    except Exception:
        return None
    if not fixations:
        return None
    tops, bottoms, etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
    a_top = np.asarray(tops, dtype=float)
    a_bot = np.asarray(bottoms, dtype=float)
    ft = np.array([f["t"] for f in fixations], dtype=float)
    fx = np.array([f["x"] for f in fixations], dtype=float)
    fy = np.array([f["y"] for f in fixations], dtype=float)
    fd = np.array([f.get("d", 200) or 200 for f in fixations], dtype=float)
    dx = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
    dyg = np.maximum.reduce([
        a_top[None, :] - fy[:, None],
        np.zeros((len(fy), len(tops))),
        fy[:, None] - a_bot[None, :],
    ])
    ogd = np.hypot(np.repeat(dx[:, None], len(tops), axis=1), dyg)
    alpha = rect_alpha_grid(fx, fy, x0, x1, a_top, a_bot,
                            weight_placement="eq2")
    return ft, fd, alpha, ogd > 0.0, etypes


def main():
    recs = json.load(open(FEATURES))
    by_trial = defaultdict(dict)
    for r in recs:
        by_trial[r["trial_id"]][r["position"]] = r

    # Q3 accumulators: etype -> lists
    census = defaultdict(lambda: {"n": 0, "entered": 0, "clicked": 0,
                                  "mass_entered": [], "mass_unentered": []})
    # Q2 accumulators: per-record cumulative mass by relative-time bin
    horizon = {"clicked": [], "nonclicked": []}

    n_fail = 0
    trials = sorted(by_trial)
    for i, tid in enumerate(trials):
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(trials)}", file=sys.stderr)
        res = trial_alpha(tid)
        if res is None:
            n_fail += 1
            continue
        ft, fd, alpha, outside, etypes = res
        rows = by_trial[tid]
        n_aoi = alpha.shape[1]
        # Full-trial peripheral mass per AOI (spec_eq2, outside-gated).
        mass = (fd[:, None] * np.where(outside, alpha, 0.0)).sum(axis=0)

        for pos in range(n_aoi):
            et = etypes[pos] if pos < len(etypes) else "unknown"
            c = census[et]
            c["n"] += 1
            r = rows.get(pos)
            if r is None:
                c["mass_unentered"].append(float(mass[pos]))
                continue
            c["entered"] += 1
            c["mass_entered"].append(float(mass[pos]))
            if r["was_clicked"]:
                c["clicked"] += 1

            # Q2: cumulative pre-entry mass by relative-time bin.
            entry_t = float(r["entry_t"])
            rel = ft - entry_t                       # <0 before entry
            m = (rel < 0) & (rel >= -HORIZON_MS) & outside[:, pos]
            if not m.any():
                continue
            contrib = fd[m] * alpha[m, pos]
            bins = ((rel[m] + HORIZON_MS) // BIN_MS).astype(int)
            binned = np.zeros(N_BINS)
            np.add.at(binned, np.clip(bins, 0, N_BINS - 1), contrib)
            cum = np.cumsum(binned)
            total = cum[-1]
            if total <= 0:
                continue
            horizon["clicked" if r["was_clicked"] else "nonclicked"].append(
                (cum / total).tolist())

    # ---- Q3 report ----
    print(f"\nPAI per-etype census (spec_eq2, full trial; {n_fail} trials failed)")
    print(f"{'etype':<14}{'n AOIs':>8}{'entry%':>8}{'click%':>8}"
          f"{'med mass entered':>18}{'med mass UNentered':>20}{'unent>entMed%':>15}")
    out_census = {}
    for et, c in sorted(census.items(), key=lambda kv: -kv[1]["n"]):
        me = float(np.median(c["mass_entered"])) if c["mass_entered"] else 0.0
        mu = float(np.median(c["mass_unentered"])) if c["mass_unentered"] else 0.0
        # among never-entered AOIs, share with mass above the entered median:
        # "peripherally sampled then skipped"
        skipped = (float(np.mean(np.array(c["mass_unentered"]) > me)) * 100
                   if c["mass_unentered"] and me > 0 else 0.0)
        print(f"{et:<14}{c['n']:>8}{100*c['entered']/c['n']:>8.1f}"
              f"{100*c['clicked']/c['n']:>8.1f}{me:>18.0f}{mu:>20.0f}"
              f"{skipped:>15.1f}")
        out_census[et] = {
            "n_aois": c["n"], "entry_rate": c["entered"] / c["n"],
            "click_rate": c["clicked"] / c["n"],
            "median_mass_entered_ms": me, "median_mass_unentered_ms": mu,
            "n_unentered": len(c["mass_unentered"]),
            "frac_unentered_above_entered_median": (skipped / 100),
            "mass_unentered_q": ([float(q) for q in np.percentile(
                c["mass_unentered"], [10, 25, 50, 75, 90])]
                if c["mass_unentered"] else None),
        }

    # ---- Q2 report ----
    print("\nAnticipation horizon (median cumulative share of pre-entry mass,"
          f" {BIN_MS} ms bins over [-{HORIZON_MS} ms, 0))")
    out_horizon = {}
    for label, curves in horizon.items():
        if not curves:
            continue
        med = np.median(np.array(curves), axis=0)
        out_horizon[label] = {"n_records": len(curves),
                              "median_cum_share": med.tolist()}
        # time (ms before entry) at which median cumulative share passes 50%
        idx = int(np.searchsorted(med, 0.5))
        t50 = -(HORIZON_MS - (idx + 0.5) * BIN_MS)
        print(f"  {label:<11} n={len(curves):>6}  median t50 ≈ {t50:+.0f} ms "
              f"(share at −4 s: {med[N_BINS // 2]:.2f}, at −1 s: "
              f"{med[N_BINS - 2]:.2f})")

    OUT.write_text(json.dumps({
        "_kernel": "spec_eq2", "_bin_ms": BIN_MS, "_horizon_ms": HORIZON_MS,
        "_features": str(FEATURES.name), "_n_trials_failed": n_fail,
        "census_by_etype": out_census, "horizon": out_horizon,
    }, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
