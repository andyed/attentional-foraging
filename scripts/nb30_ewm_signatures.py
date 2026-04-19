"""Verify the EWM-predicted empirical signatures:
  - n_reversals: deferred > rejected (EWM reload action)
  - min_abs_velocity: deferred < rejected (slowed to re-examine)
On the approached ∧ ¬clicked sample from NB30.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.stats import mannwhitneyu, wilcoxon
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks-v2"))
from nb30_scroll_trajectory import compute_features_for_trial

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEATS = ROOT / "AdSERP/data/cursor-approach-features.json"
REG = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations/ewm_signatures.json"

raw = json.load(open(FEATS))
labels = np.array(json.load(open(REG)), dtype=bool)
trials = sorted({r["trial_id"] for r in raw})
per_trial = {}
for tid in trials:
    f = compute_features_for_trial(tid, n_positions=10)
    if f is not None:
        per_trial[tid] = f

rows, keep = [], []
for i, r in enumerate(raw):
    if r["trial_id"] not in per_trial or r["position"] >= 10:
        continue
    rows.append(per_trial[r["trial_id"]][r["position"]])
    keep.append(i)
keep = np.array(keep)
md = np.array([raw[i]["min_dist"] for i in keep])
wc = np.array([raw[i]["was_clicked"] for i in keep], dtype=bool)
subset = (md < 100) & ~wc
labels_k = labels[keep][subset]

def stats(name):
    vals = np.array([rows[i][name] for i in np.where(subset)[0]], dtype=float)
    deferred = vals[labels_k]
    rejected = vals[~labels_k]
    u, p = mannwhitneyu(deferred, rejected, alternative="two-sided")
    return {
        "feature": name,
        "deferred_n": int(len(deferred)),
        "rejected_n": int(len(rejected)),
        "deferred_mean": float(deferred.mean()),
        "rejected_mean": float(rejected.mean()),
        "deferred_median": float(np.median(deferred)),
        "rejected_median": float(np.median(rejected)),
        "U": float(u),
        "p": float(p),
        "direction": "deferred > rejected" if deferred.mean() > rejected.mean() else "deferred < rejected",
    }

out = []
for name in ("n_reversals", "min_abs_velocity", "vt_any", "vt_center_ms",
             "avg_viewport_y", "max_overlap_frac", "pause_ms"):
    s = stats(name)
    out.append(s)
    print(f"  {s['feature']:22s}  def={s['deferred_mean']:10.3f}  "
          f"rej={s['rejected_mean']:10.3f}  med_def={s['deferred_median']:8.2f}  "
          f"med_rej={s['rejected_median']:8.2f}  p={s['p']:.2e}  {s['direction']}")

OUT.write_text(json.dumps(out, indent=2))
print(f"\nwrote {OUT}")

# Specific EWM predictions
print("\n── EWM predictions ──")
nr = next(s for s in out if s["feature"] == "n_reversals")
pred1 = nr["deferred_mean"] > nr["rejected_mean"] and nr["p"] < 0.05
print(f"  n_reversals deferred > rejected, p < 0.05: {'HOLDS' if pred1 else 'FAILS'}  "
      f"(Δ = {nr['deferred_mean']-nr['rejected_mean']:+.3f}, p = {nr['p']:.2e})")
mv = next(s for s in out if s["feature"] == "min_abs_velocity")
pred2 = mv["deferred_mean"] < mv["rejected_mean"] and mv["p"] < 0.05
print(f"  min_abs_velocity deferred < rejected, p < 0.05: {'HOLDS' if pred2 else 'FAILS'}  "
      f"(Δ = {mv['deferred_mean']-mv['rejected_mean']:+.3f} px/s, p = {mv['p']:.2e})")
