#!/usr/bin/env python3
"""Confound check for the scroll-hesitation -> LHIPA signal (2026-06-14).

pause_ms / n_reversals scale with trial length; LHIPA may too. Per-participant
partial Spearman of (feature, lhipa | duration) to see if the signal is a genuine
motor-load channel or just trial-time. Duration proxy = sum of total_dwell_ms
across positions (independent of the scroll-kinematic features themselves).
[LAB, AdSERP, organic]. Internal — touches LHIPA.
"""
import json
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr, rankdata, wilcoxon

AD = "AdSERP/data"
MIN_TRIALS, MIN_P = 10, 20

def pid_of(t): return t.split("-")[0]

cur = json.load(open(f"{AD}/cursor-approach-features-organic.json"))
vpt = json.load(open(f"{AD}/viewport-trajectory-features.json"))
lh = json.load(open(f"{AD}/trial-lhipa.json"))
lhipa_of = {t: v["lhipa"] for t, v in lh.items()
            if v.get("lhipa") is not None and np.isfinite(v["lhipa"])}

# per-trial aggregates (all positions pooled)
dwell = defaultdict(float)       # duration proxy
nfix = defaultdict(float)
for r in cur:
    if r.get("total_dwell_ms"): dwell[r["trial_id"]] += r["total_dwell_ms"]
    if r.get("n_fixations"): nfix[r["trial_id"]] += r["n_fixations"]

feat = defaultdict(lambda: defaultdict(list))
for r in vpt:
    for f in ["pause_ms", "n_reversals", "max_abs_velocity"]:
        v = r.get(f)
        if v is not None and np.isfinite(v):
            feat[r["trial_id"]][f].append(float(v))
trial_feat = {t: {f: np.mean(vs) for f, vs in d.items()} for t, d in feat.items()}

def partial_spearman(x, y, z):
    """partial corr of x,y controlling z, all via Spearman ranks."""
    x, y, z = rankdata(x), rankdata(y), rankdata(z)
    rxy = np.corrcoef(x, y)[0, 1]
    rxz = np.corrcoef(x, z)[0, 1]
    ryz = np.corrcoef(y, z)[0, 1]
    d = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    return (rxy - rxz * ryz) / d if d > 0 else np.nan

trials = [t for t in trial_feat if t in lhipa_of and t in dwell]
print(f"trials: {len(trials)}  participants: {len(set(map(pid_of,trials)))}\n")
print(f"{'feature':<18} {'raw med rho':>12} {'partial|dwell':>14} {'partial|nfix':>13}  {'p(partial|dwell)':>16}")
print("-" * 78)

for f in ["pause_ms", "n_reversals", "max_abs_velocity"]:
    raw, pdw, pnf = [], [], []
    by_p = defaultdict(list)
    for t in trials:
        if f in trial_feat[t]:
            by_p[pid_of(t)].append(t)
    for p, ts in by_p.items():
        if len(ts) < MIN_TRIALS: continue
        xf = np.array([trial_feat[t][f] for t in ts])
        yl = np.array([lhipa_of[t] for t in ts])
        zd = np.array([dwell[t] for t in ts])
        zn = np.array([nfix[t] for t in ts])
        if np.std(xf) == 0 or np.std(yl) == 0: continue
        raw.append(spearmanr(xf, yl)[0])
        if np.std(zd) > 0: pdw.append(partial_spearman(xf, yl, zd))
        if np.std(zn) > 0: pnf.append(partial_spearman(xf, yl, zn))
    raw, pdw, pnf = map(lambda a: np.array([v for v in a if np.isfinite(v)]),
                        (raw, pdw, pnf))
    pval = wilcoxon(pdw).pvalue if len(pdw) >= MIN_P else float("nan")
    print(f"{f:<18} {np.median(raw):>12.3f} {np.median(pdw):>14.3f} "
          f"{np.median(pnf):>13.3f}  {pval:>16.4f}")
