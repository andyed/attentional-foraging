#!/usr/bin/env python3
"""LF/HF version of the cursor->load first cut (2026-06-14).

LF/HF is per-(trial,position) (butterworth-lfhf-by-position-organic), so unlike
the per-trial LHIPA pass, load and cursor kinematics are matched at the SAME
position — the clean version of the band/regression moderation test.

Polarity (this dataset, computation-dominated): UP LF/HF = UP load
[notebook-key-claims polarity note]. So if the LHIPA result (more pause -> lower
LHIPA = more load) is real, pause-like features should flip POSITIVE here.
Cross-index validation built in.

Splits: (A) overall + duration-partial, (B) viewport band top vs below,
(C) will_regress True vs False ("returns in regressions"). Per-participant
Spearman at the position level, paired Wilcoxon across participants for moderation.
Includes dwell_in_proximity_ms = mouse-cursor pause, the WILD-deployable analog
of the scroll pause_ms that worked against LHIPA.
[LAB, AdSERP, organic]. Internal — LF/HF is Duchowski-sensitive.
"""
import json
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr, rankdata, wilcoxon

AD = "AdSERP/data"
MIN_N, MIN_P = 8, 20

def pid_of(t): return t.split("-")[0]

cur = json.load(open(f"{AD}/cursor-approach-features-organic.json"))
vpt = json.load(open(f"{AD}/viewport-trajectory-features.json"))
lfhf_raw = json.load(open(f"{AD}/butterworth-lfhf-by-position-organic.json"))
willreg = json.load(open("scripts/output/approach_threshold_sensitivity/"
                         "regression_labels_cache_organic.json"))  # bool list || cur

lfhf_of = {}
for tid, pl in lfhf_raw.items():
    for p in pl.get("positions", []):
        if p.get("lfhf") is not None and np.isfinite(p["lfhf"]):
            lfhf_of[(tid, p["pos"])] = p["lfhf"]

vpt_of = {(r["trial_id"], r["position"]): r for r in vpt}
def band_of(key):
    r = vpt_of.get(key)
    if not r: return None
    tb = {"top": r.get("vt_top") or 0., "mid": r.get("vt_mid") or 0., "bot": r.get("vt_bot") or 0.}
    return max(tb, key=tb.get) if sum(tb.values()) > 0 else None

CUR_F = ["mean_approach_velocity", "direction_changes", "frac_decreasing",
         "retreat_dist", "dwell_in_proximity_ms"]
VPT_F = ["pause_ms", "n_reversals", "max_abs_velocity"]
ALL_F = CUR_F + VPT_F

# build matched position-level rows
rows = []
for i, r in enumerate(cur):
    key = (r["trial_id"], r["position"])
    y = lfhf_of.get(key)
    if y is None:
        continue
    rec = {"pid": pid_of(r["trial_id"]), "lfhf": y, "band": band_of(key),
           "regress": bool(willreg[i]) if i < len(willreg) else None,
           "dur": r.get("total_dwell_ms"), "nfix": r.get("n_fixations")}
    for f in CUR_F:
        rec[f] = r.get(f)
    vr = vpt_of.get(key, {})
    for f in VPT_F:
        rec[f] = vr.get(f)
    rows.append(rec)

print(f"matched positions (cursor+vpt+lfhf): {len(rows)}  "
      f"participants: {len(set(r['pid'] for r in rows))}\n")

def finite(rs, *keys):
    return [r for r in rs if all(r.get(k) is not None and np.isfinite(r[k]) for k in keys)]

def per_p_rho(rs, f, partial=None):
    by_p = defaultdict(list)
    for r in rs: by_p[r["pid"]].append(r)
    out = {}
    for p, g in by_p.items():
        keys = [f, "lfhf"] + ([partial] if partial else [])
        g = finite(g, *keys)
        if len(g) < MIN_N: continue
        x = np.array([r[f] for r in g]); y = np.array([r["lfhf"] for r in g])
        if np.std(x) == 0 or np.std(y) == 0: continue
        if partial:
            z = np.array([r[partial] for r in g])
            if np.std(z) == 0: continue
            xr, yr, zr = rankdata(x), rankdata(y), rankdata(z)
            rxy, rxz, ryz = (np.corrcoef(a, b)[0, 1] for a, b in
                             [(xr, yr), (xr, zr), (yr, zr)])
            d = np.sqrt((1 - rxz**2) * (1 - ryz**2))
            rho = (rxy - rxz * ryz) / d if d > 0 else np.nan
        else:
            rho = spearmanr(x, y)[0]
        if np.isfinite(rho): out[p] = rho
    return out

def summ(m):
    a = np.array(list(m.values()))
    if len(a) < MIN_P: return f"n={len(a)} (insufficient)"
    p = wilcoxon(a).pvalue
    return f"n={len(a):2d}  med={np.median(a):+.3f}  p={p:.4f}"

def paired(m1, m2, label):
    common = sorted(set(m1) & set(m2))
    if len(common) < MIN_P: return f"  [{label}: n={len(common)} insufficient]"
    a = np.array([abs(m1[p]) for p in common]); b = np.array([abs(m2[p]) for p in common])
    p = wilcoxon(a, b).pvalue
    return f"  [{label} |rho|: {np.median(a):.3f} vs {np.median(b):.3f}  p={p:.3f} n={len(common)}]"

print("=== A. overall + duration/nfix partial (expect pause-like POSITIVE) ===")
print(f"{'feature':<22} {'raw':>22} {'partial|dur':>22}")
for f in ALL_F:
    print(f"{f:<22} {summ(per_p_rho(rows, f)):>22}   {summ(per_p_rho(rows, f, 'dur')):>22}")

print("\n=== B. viewport band: top vs below-fold ===")
top = [r for r in rows if r["band"] == "top"]
below = [r for r in rows if r["band"] in ("mid", "bot")]
for f in ALL_F:
    mt, mb = per_p_rho(top, f), per_p_rho(below, f)
    print(f"{f:<22} top {summ(mt):<34} below {summ(mb)}\n{'':<22}{paired(mt, mb, 'top vs below')}")

print("\n=== C. regression positions vs not (Andy: 'returns in regressions') ===")
reg = [r for r in rows if r["regress"] is True]
noreg = [r for r in rows if r["regress"] is False]
print(f"   regress positions={len(reg)}  non-regress={len(noreg)}")
for f in ALL_F:
    mr, mn = per_p_rho(reg, f), per_p_rho(noreg, f)
    print(f"{f:<22} reg {summ(mr):<34} norg {summ(mn)}\n{'':<22}{paired(mr, mn, 'reg vs norg')}")
