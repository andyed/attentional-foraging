"""Validate the paper §5.1 linear-fallback AOI approximation against CV bboxes.

The §5.1 click-prediction headline uses the hybrid extractor
(m4_nb21_hybrid_rerun.py). For the ~69% of records with no xpath-resolved
cursor event, it places the AOI center by linear page-height banding:
absolute_rank_band_tops(10, doc_h) — header=200, per_res=(doc_h-400)/10,
band center i = 200 + (i+0.5)*per_res.

This script asks how far those band centers sit from the CV-detected organic
result bboxes (AdSERP/data/organic-boundary-data/). The features use vertical
cursor-to-AOI distance, so vertical center error |dy| is what matters; the
100 px proximity threshold is the reference scale.

Index-free by construction: compares sorted-by-y, never assumes the hybrid's
rso-div index matches the CV organic_result index.

  nearest : each CV organic result -> min |dy| to any band center
            (lower bound; "is every real result near some band")
  aligned : sorted CV[i] vs band[i] for i < min(n_cv, 10)
            ("is the i-th real result at the i-th band" — the honest test)

Run:
  .venv/bin/python scripts/validate_linear_fallback_vs_cv.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import get_trial_ids, get_trial_meta, absolute_rank_band_tops  # noqa: E402

CV_DIR = ROOT / "AdSERP/data/organic-boundary-data"
OUT = ROOT / "scripts/output/validate_linear_fallback_vs_cv/summary.json"
HYBRID_FEATURES = ROOT / "scripts/output/m4_nb21_hybrid_rerun/hybrid_features.json"
LAB_FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
N_BANDS = 10          # m4_nb21_hybrid_rerun.py N_RESULTS_DEFAULT
PROX = 100            # m4_nb21_hybrid_rerun.py PROX_THRESHOLD


def band_centers(doc_h):
    """The hybrid's 10 linear-fallback y-centers for a trial."""
    tops = absolute_rank_band_tops(N_BANDS, doc_h)
    per = tops[1] - tops[0] if len(tops) > 1 else 100.0
    return [t + per / 2.0 for t in tops]


# The hybrid bands ABSOLUTE rank (all main-column slots, ads pooled with
# organic — see data_loader.absolute_rank_band_tops). So band i must be
# compared against the i-th main-column slot, not the i-th organic result:
# ~76% of position-0 slots are ads. Main-column slot types (dd_right /
# right-rail and *_cell sub-cells excluded):
ABSOLUTE_SLOT_KEYS = ("organic_result", "native_ad", "dd_top", "widget")


def _ycenters(tid, keys):
    """Sorted y-centers of the given CV slot types, or None."""
    p = CV_DIR / f"{tid}.json"
    if not p.exists():
        return None
    d = json.load(open(p))
    ys = []
    for key in keys:
        for o in d.get(key, []):
            loc, sz = o.get("location", {}), o.get("size", {})
            if "y" in loc and "height" in sz:
                ys.append(loc["y"] + sz["height"] / 2.0)
    return sorted(ys) if ys else None


def cv_slot_ycenters(tid):
    """Sorted y-centers of all CV-detected main-column slots (absolute rank)."""
    return _ycenters(tid, ABSOLUTE_SLOT_KEYS)


def cv_organic_ycenters(tid):
    """Sorted y-centers of CV-detected organic results only (secondary check)."""
    return _ycenters(tid, ("organic_result",))


def stats(arr):
    a = np.asarray(arr, dtype=float)
    if len(a) == 0:
        return {"n": 0}
    return {
        "n": int(len(a)),
        "median": round(float(np.median(a)), 1),
        "iqr": [round(float(np.percentile(a, 25)), 1),
                round(float(np.percentile(a, 75)), 1)],
        "p90": round(float(np.percentile(a, 90)), 1),
        "mean": round(float(a.mean()), 1),
        f"frac_within_{PROX}px": round(float(np.mean(a < PROX)), 4),
    }


def functional_check():
    """The geometric error above is rank-confounded (band drift grows with
    rank). The decisive question is whether it reaches the records §5.1
    relies on. Join was_clicked onto the hybrid feature records and report,
    per grounding, the fraction of CLICKED records (the positive class)
    whose nearest cursor approach lands within the 100 px proximity zone of
    the AOI center. Clicks concentrate at shallow ranks, where the band
    model still holds.
    """
    hy = json.load(open(HYBRID_FEATURES))
    lab = json.load(open(LAB_FEATURES))
    clicked = {(r["trial_id"], r["position"]) for r in lab if r["was_clicked"]}
    out = {}
    n_tot = n_in = 0
    for g in ("xpath", "linear"):
        recs = [r for r in hy if r["grounding"] == g
                and (r["trial_id"], r["position"]) in clicked]
        md = np.array([r["min_dist"] for r in recs], dtype=float)
        frac = float(np.mean(md < PROX)) if len(md) else 0.0
        out[g] = {
            "n_clicked": len(recs),
            "min_dist_median": round(float(np.median(md)), 1) if len(md) else None,
            f"frac_within_{PROX}px": round(frac, 4),
        }
        n_tot += len(recs)
        n_in += frac * len(recs)
    out["overall_clicked_within_prox"] = round(n_in / n_tot, 4) if n_tot else None
    return out


def main():
    # absolute-rank (all main-column slots) — the indexing the bands use
    nearest_err, aligned_err, slot_counts = [], [], []
    # organic-only secondary check
    org_nearest_err, org_counts = [], []
    n_ok = n_skip = 0

    for i, tid in enumerate(get_trial_ids()):
        if (i + 1) % 500 == 0:
            print(f"  {i + 1} trials...", file=sys.stderr)
        meta = get_trial_meta(tid)
        slots = cv_slot_ycenters(tid)
        if meta is None or slots is None:
            n_skip += 1
            continue
        doc_h = meta[0]
        if not doc_h or doc_h <= 400:
            n_skip += 1
            continue
        bc = band_centers(doc_h)
        n_ok += 1
        slot_counts.append(len(slots))
        for y in slots:
            nearest_err.append(min(abs(y - b) for b in bc))
        for k in range(min(len(slots), N_BANDS)):
            aligned_err.append(abs(slots[k] - bc[k]))
        org = cv_organic_ycenters(tid)
        if org:
            org_counts.append(len(org))
            for y in org:
                org_nearest_err.append(min(abs(y - b) for b in bc))

    sc = np.asarray(slot_counts, dtype=int)
    oc = np.asarray(org_counts, dtype=int)
    summary = {
        "trials_used": n_ok,
        "trials_skipped": n_skip,
        "cv_absolute_slot_count": {
            "median": int(np.median(sc)) if len(sc) else 0,
            "mean": round(float(sc.mean()), 2) if len(sc) else 0,
            "frac_eq_10": round(float(np.mean(sc == N_BANDS)), 4) if len(sc) else 0,
            "min": int(sc.min()) if len(sc) else 0,
            "max": int(sc.max()) if len(sc) else 0,
        },
        "cv_organic_count_median": int(np.median(oc)) if len(oc) else 0,
        "vertical_center_error_px": {
            "absolute_nearest_band": stats(nearest_err),
            "absolute_rank_aligned": stats(aligned_err),
            "organic_nearest_band": stats(org_nearest_err),
        },
        "functional_clicked_records": functional_check(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(OUT, "w"), indent=2)

    print("\n" + "=" * 64)
    print("Linear-fallback AOI approximation vs CV-detected bboxes")
    print("=" * 64)
    print(f"trials used: {n_ok:,}   skipped (no meta / no CV): {n_skip:,}")
    c = summary["cv_absolute_slot_count"]
    print(f"CV main-column slot count (organic+ads+widget): median {c['median']}, "
          f"mean {c['mean']}, range [{c['min']}, {c['max']}], "
          f"=10 in {c['frac_eq_10']:.1%} of trials")
    print(f"CV organic-only count: median {summary['cv_organic_count_median']}")
    for name, s in summary["vertical_center_error_px"].items():
        print(f"\n{name}: n={s['n']:,}  |dy| median {s['median']} px  "
              f"IQR {s['iqr']}  p90 {s['p90']}  "
              f"within {PROX}px: {s[f'frac_within_{PROX}px']:.1%}")
    fc = summary["functional_clicked_records"]
    print(f"\nfunctional check — clicked records within {PROX}px proximity:")
    for g in ("xpath", "linear"):
        print(f"  {g:7s} n={fc[g]['n_clicked']:5d}  "
              f"min_dist median {fc[g]['min_dist_median']} px  "
              f"within {PROX}px: {fc[g][f'frac_within_{PROX}px']:.1%}")
    print(f"  overall clicked within {PROX}px: {fc['overall_clicked_within_prox']:.1%}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
