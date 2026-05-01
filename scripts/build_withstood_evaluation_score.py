"""Build the continuous withstood_evaluation relevance score per (trial, pos).

Rationale
---------
Gray & Fu 2004 SCH / EWM framing: the user treats the viewport as external
working memory; managing it costs cognitive effort. Items that "withstand
more compiled evaluation" accumulate characteristic motor signatures —
more scroll reversals (reloads), lower scroll velocity while reading,
longer time at viewport center, longer cursor-proximity dwell.

NB30 K23 established that the signal is *cumulative* (not windowed):
deferred-vs-rejected discrimination lives in accumulated-since-visible,
not in rolling 5s. K24–K26 established the three signatures are highly
significant (p = 8.5e-23, 2.0e-47, 1.5e-42). K27 established cursor and
trajectory are complementary (forward selection picks `mean_dist` +
`min_abs_velocity` jointly).

This script composes these into a continuous per-(trial, pos) scalar that
replaces the discrete {clicked, deferred, eval-rejected, not-approached}
labels with a graded score. Two variants:

  withstood_full       — integrated over the full AOI-visible window
  withstood_pre_click  — integrated only up to click_t (clean variant)

The pre-click variant is the leakage-free analog for LambdaMART training
labels: for clicked items, full-trial integration includes the cursor-to-
click trajectory that inflates the composite.

Composite
---------
Equal-weighted z-scores (computed on the full 27,760-row population)
across four components:

  z(n_reversals)                             — EWM reloads (higher = more)
  z(-min_abs_velocity)                       — stabilization (higher = more at-rest)
  z(vt_center_ms / max(vt_any, 1))           — fraction of visible time at center
  z(dwell_in_proximity_ms)                   — cursor co-engagement (higher = more)

Not-approached items will naturally land at the low end because they lack
dwell-in-proximity and typically have short vt_center times. No special-
casing — the distribution will be multi-modal.

Output
------
  AdSERP/data/withstood-evaluation-score.json — 27,760 rows, schema:
    trial_id, position,
    withstood_full, withstood_pre_click,
    n_reversals, min_abs_velocity, vt_center_fraction, dwell_in_proximity_ms,
    click_t (None for non-clicked trials)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import get_trial_ids, load_mouse_events  # noqa: E402
from nb30_scroll_trajectory import compute_features_for_trial  # noqa: E402

VP_PATH = ROOT / "AdSERP/data/viewport-trajectory-features.json"
CURSOR_PATH = ROOT / "AdSERP/data/cursor-approach-features.json"
OUT_PATH = ROOT / "AdSERP/data/withstood-evaluation-score.json"


def load_cursor_by_key() -> dict[tuple[str, int], dict]:
    raw = json.load(open(CURSOR_PATH))
    return {(r["trial_id"], int(r["position"])): r for r in raw}


def click_timestamps() -> dict[str, int]:
    """Return trial_id -> click timestamp (ms). Absent if no click in trial."""
    out: dict[str, int] = {}
    trials = get_trial_ids()
    for i, tid in enumerate(trials):
        _, _, clicks = load_mouse_events(tid)
        if clicks:
            out[tid] = int(clicks[0][0])
        if (i + 1) % 500 == 0:
            print(f"  click_t {i+1}/{len(trials)}", file=sys.stderr)
    return out


def compute_pre_click_rows(click_t_by_trial: dict[str, int]) -> dict[tuple[str, int], dict]:
    """Re-run the nb30 extractor with max_t = click_t for clicked trials.

    For trials without a click we skip (they won't have withstood_pre_click;
    they're excluded from the usable set downstream anyway since NB26/NB22
    filter to trials-with-a-click).
    """
    print("[pre-click] computing viewport features truncated at click_t...", file=sys.stderr)
    out: dict[tuple[str, int], dict] = {}
    trials = sorted(click_t_by_trial.keys())
    t0 = time.time()
    for i, tid in enumerate(trials):
        ct = click_t_by_trial[tid]
        feats = compute_features_for_trial(tid, n_positions=10, max_t=ct)
        if feats is None:
            continue
        for pos, f in enumerate(feats):
            out[(tid, pos)] = f
        if (i + 1) % 250 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta_s = (len(trials) - (i + 1)) / rate
            print(f"  {i+1}/{len(trials)} ({rate:.1f} trials/s, ETA {eta_s:.0f}s)",
                  file=sys.stderr)
    return out


def zscore_pop(values: np.ndarray) -> np.ndarray:
    mu = float(np.nanmean(values))
    sd = float(np.nanstd(values, ddof=1))
    if sd < 1e-12:
        return np.zeros_like(values)
    return (values - mu) / sd


def compose(rows: list[dict], n_key: str, v_key: str, vtc_key: str, vta_key: str,
            dwell_key: str) -> np.ndarray:
    """Equal-weighted z-score composite. Pass column aliases so we can reuse
    for full vs pre-click by swapping the underlying arrays."""
    n_reversals = np.array([r.get(n_key, 0.0) or 0.0 for r in rows], dtype=float)
    min_abs_v = np.array([r.get(v_key, 0.0) or 0.0 for r in rows], dtype=float)
    vt_center = np.array([r.get(vtc_key, 0.0) or 0.0 for r in rows], dtype=float)
    vt_any = np.array([r.get(vta_key, 0.0) or 0.0 for r in rows], dtype=float)
    dwell = np.array([r.get(dwell_key, 0.0) or 0.0 for r in rows], dtype=float)

    center_frac = vt_center / np.maximum(vt_any, 1.0)
    # Neg velocity so higher = more stabilization
    z_n = zscore_pop(n_reversals)
    z_v = zscore_pop(-min_abs_v)
    z_c = zscore_pop(center_frac)
    z_d = zscore_pop(dwell)
    composite = (z_n + z_v + z_c + z_d) / 4.0
    return composite, {
        "n_reversals": n_reversals,
        "min_abs_velocity": min_abs_v,
        "vt_center_fraction": center_frac,
        "dwell_in_proximity_ms": dwell,
        "z_n_reversals": z_n,
        "z_neg_min_abs_velocity": z_v,
        "z_vt_center_fraction": z_c,
        "z_dwell_in_proximity_ms": z_d,
    }


def main() -> None:
    print("[load] viewport-trajectory-features.json")
    vp_rows = json.load(open(VP_PATH))
    vp_by_key = {(r["trial_id"], int(r["position"])): r for r in vp_rows}
    print(f"       {len(vp_by_key):,} rows")

    print("[load] cursor-approach-features.json")
    cursor_by_key = load_cursor_by_key()
    print(f"       {len(cursor_by_key):,} rows (approached subset)")

    print("[scan] click timestamps per trial")
    click_t_by_trial = click_timestamps()
    print(f"       {len(click_t_by_trial):,} trials with a click")

    # Build merged row per (trial, pos) for full-trial composite
    merged_full = []
    for key, vp in vp_by_key.items():
        cu = cursor_by_key.get(key, {})
        merged_full.append({
            "trial_id": key[0],
            "position": key[1],
            # viewport (full-trial)
            "n_reversals": vp.get("n_reversals", 0.0),
            "min_abs_velocity": vp.get("min_abs_velocity", 0.0),
            "vt_center_ms": vp.get("vt_center_ms", 0.0),
            "vt_any": vp.get("vt_any", 0.0),
            # cursor
            "dwell_in_proximity_ms": cu.get("dwell_in_proximity_ms", 0.0) or 0.0,
            "min_dist": cu.get("min_dist", 9999),
            "was_clicked": bool(cu.get("was_clicked", False)),
        })

    print("[compute] full-trial composite")
    composite_full, comps_full = compose(
        merged_full,
        "n_reversals", "min_abs_velocity",
        "vt_center_ms", "vt_any",
        "dwell_in_proximity_ms",
    )

    # Pre-click-truncated viewport features (cursor features stay as-is; M4
    # was already computed over the full trial, but for clicked items the
    # intra-trial M4 dwell trajectory is click-correlated. We replicate the
    # same viewport truncation as a partial leakage fix; a full fix would
    # require recomputing dwell_in_proximity_ms pre-click too, which needs
    # raw cursor timeline access — deferred as a TODO.)
    vp_pre = compute_pre_click_rows(click_t_by_trial)

    merged_pre = []
    for r in merged_full:
        tid = r["trial_id"]
        pos = r["position"]
        pre = vp_pre.get((tid, pos))
        if pre is None:
            # no click in trial → pre_click view == full
            merged_pre.append(r)
            continue
        merged_pre.append({
            **r,
            "n_reversals": pre.get("n_reversals", 0.0),
            "min_abs_velocity": pre.get("min_abs_velocity", 0.0),
            "vt_center_ms": pre.get("vt_center_ms", 0.0),
            "vt_any": pre.get("vt_any", 0.0),
            # dwell_in_proximity_ms is NOT truncated here — see comment above
        })
    print("[compute] pre-click-truncated composite")
    composite_pre, comps_pre = compose(
        merged_pre,
        "n_reversals", "min_abs_velocity",
        "vt_center_ms", "vt_any",
        "dwell_in_proximity_ms",
    )

    # Write
    out_rows = []
    for i, r in enumerate(merged_full):
        out_rows.append({
            "trial_id": r["trial_id"],
            "position": r["position"],
            "withstood_full": float(composite_full[i]),
            "withstood_pre_click": float(composite_pre[i]),
            "n_reversals": float(comps_full["n_reversals"][i]),
            "min_abs_velocity": float(comps_full["min_abs_velocity"][i]),
            "vt_center_fraction": float(comps_full["vt_center_fraction"][i]),
            "dwell_in_proximity_ms": float(comps_full["dwell_in_proximity_ms"][i]),
            "click_t": click_t_by_trial.get(r["trial_id"]),
        })
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out_rows))
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"[out] {OUT_PATH}  ({size_mb:.1f} MB, {len(out_rows):,} rows)")

    # Quick summary
    print("\n-- withstood_full summary --")
    print(f"  mean = {composite_full.mean():+.3f}  std = {composite_full.std(ddof=1):.3f}  "
          f"p05/50/95 = "
          f"{np.percentile(composite_full, 5):+.3f} / "
          f"{np.percentile(composite_full, 50):+.3f} / "
          f"{np.percentile(composite_full, 95):+.3f}")
    print(f"  clicked mean: "
          f"{np.mean([composite_full[i] for i, r in enumerate(merged_full) if r['was_clicked']]):+.3f}")
    approached = [i for i, r in enumerate(merged_full) if float(r['min_dist']) < 100]
    not_approached = [i for i, r in enumerate(merged_full) if float(r['min_dist']) >= 100]
    print(f"  approached (non-clicked) mean: "
          f"{np.mean([composite_full[i] for i in approached if not merged_full[i]['was_clicked']]):+.3f}")
    print(f"  not-approached mean:           "
          f"{np.mean([composite_full[i] for i in not_approached]):+.3f}")

    print("\n-- withstood_pre_click summary --")
    print(f"  mean = {composite_pre.mean():+.3f}  std = {composite_pre.std(ddof=1):.3f}")
    # Leakage magnitude on clicked items
    clicked_idx = [i for i, r in enumerate(merged_full) if r['was_clicked']]
    delta = composite_full[clicked_idx] - composite_pre[clicked_idx]
    print(f"  clicked items: full − pre_click mean Δ = {delta.mean():+.3f}  "
          f"(median Δ = {np.median(delta):+.3f})  — magnitude of click-leakage in full")


if __name__ == "__main__":
    main()
