#!/usr/bin/env python3
"""EXPLORATORY first cut (2026-06-14) — Peter's question: predict cognitive load
from cursor trails?

Hypothesis (Andy's Slack mechanism): cursor proxies the eyes only where they're
coupled — top viewport + regressions. So cursor *kinematics* should track LHIPA
in the top viewport band and go null below the fold (forward evaluation), rather
than carrying load uniformly.

Test: cursor kinematics (NOT gaze-cursor lag, which is already null at NB02:K11)
x per-trial LHIPA, split by viewport band. Per-participant Spearman, then paired
across the 47 (Wilcoxon signed-rank) to ask whether band MODERATES the coupling.

Regime: [LAB, AdSERP, organic]. LHIPA -> Duchowski-sensitive (internal only).
NOT publication-grade: per-trial LHIPA is one scalar (cannot window load itself),
so the coupling-state split lives on the cursor side only. Sign-agnostic — the
claim is about WHERE the correlation lives, not its direction.
"""
import json
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr, wilcoxon

AD = "AdSERP/data"
MIN_TRIALS = 10          # per-participant min trials in a band to estimate rho
MIN_PARTICIPANTS = 20    # min participants contributing a rho to test it

def pid_of(trial_id):
    return trial_id.split("-")[0]

# ---- load -------------------------------------------------------------
cur = json.load(open(f"{AD}/cursor-approach-features-organic.json"))   # per (trial,pos)
vpt = json.load(open(f"{AD}/viewport-trajectory-features.json"))       # per (trial,pos)
lhipa = json.load(open(f"{AD}/trial-lhipa.json"))                      # per trial

lhipa_of = {t: v["lhipa"] for t, v in lhipa.items()
            if v.get("lhipa") is not None and np.isfinite(v["lhipa"])}

# viewport band per (trial,pos): argmax of time in top/mid/bot
band = {}
vpt_feat = {}
for r in vpt:
    key = (r["trial_id"], r["position"])
    tb = {"top": r.get("vt_top") or 0.0, "mid": r.get("vt_mid") or 0.0,
          "bot": r.get("vt_bot") or 0.0}
    if sum(tb.values()) <= 0:
        continue
    band[key] = max(tb, key=tb.get)
    vpt_feat[key] = r

# cursor-trail kinematic features (approach geometry + viewport scroll kinematics)
# deliberately excluding gaze-cursor lag (NB02:K11 null) and raw distances.
CUR_FEATS = ["mean_approach_velocity", "max_approach_velocity",
             "direction_changes", "frac_decreasing", "retreat_dist"]
VPT_FEATS = ["pause_ms", "n_reversals", "max_decel_near_center", "max_abs_velocity"]

# ---- per (trial, band) mean of each feature ---------------------------
# accum[trial][band][feat] -> list of per-position values
accum = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for r in cur:
    key = (r["trial_id"], r["position"])
    b = band.get(key)
    if b is None:
        continue
    for f in CUR_FEATS:
        v = r.get(f)
        if v is not None and np.isfinite(v):
            accum[r["trial_id"]][b][f].append(float(v))
    vf = vpt_feat.get(key, {})
    for f in VPT_FEATS:
        v = vf.get(f)
        if v is not None and np.isfinite(v):
            accum[r["trial_id"]][b][f].append(float(v))

# collapse below-fold = mid + bot
def trial_band_feat(trial, which, feat):
    bands = ["top"] if which == "top" else ["mid", "bot"]
    vals = []
    for b in bands:
        vals += accum[trial][b][feat]
    return float(np.mean(vals)) if vals else None

ALL_FEATS = CUR_FEATS + VPT_FEATS
trials = [t for t in accum if t in lhipa_of]
print(f"trials with LHIPA + cursor/vpt features: {len(trials)}")
print(f"participants: {len(set(pid_of(t) for t in trials))}\n")

# ---- per-participant Spearman(feature_band, lhipa), then test across ---
def per_participant_rhos(which, feat):
    by_p = defaultdict(lambda: ([], []))
    for t in trials:
        fv = trial_band_feat(t, which, feat)
        if fv is None:
            continue
        xs, ys = by_p[pid_of(t)]
        xs.append(fv); ys.append(lhipa_of[t])
    rhos = []
    for p, (xs, ys) in by_p.items():
        if len(xs) >= MIN_TRIALS and np.std(xs) > 0 and np.std(ys) > 0:
            rho, _ = spearmanr(xs, ys)
            if np.isfinite(rho):
                rhos.append(rho)
    return np.array(rhos)

hdr = f"{'feature':<24} {'band':<6} {'n_p':>4} {'med rho':>8} {'p vs0':>7}   {'moderation (top vs below)':>26}"
print(hdr); print("-" * len(hdr))
for feat in ALL_FEATS:
    rho_top = per_participant_rhos("top", feat)
    rho_bel = per_participant_rhos("below", feat)
    line = {}
    for tag, r in [("top", rho_top), ("below", rho_bel)]:
        if len(r) >= MIN_PARTICIPANTS:
            try:
                p = wilcoxon(r).pvalue
            except ValueError:
                p = float("nan")
            line[tag] = (len(r), float(np.median(r)), p)
        else:
            line[tag] = (len(r), float("nan"), float("nan"))
    # paired moderation test: only participants with both rho_top and rho_below
    mod = ""
    by_p_top = {}; by_p_bel = {}
    # recompute paired (need same participant set)
    def rho_map(which, feat):
        by_p = defaultdict(lambda: ([], []))
        for t in trials:
            fv = trial_band_feat(t, which, feat)
            if fv is None: continue
            xs, ys = by_p[pid_of(t)]; xs.append(fv); ys.append(lhipa_of[t])
        out = {}
        for p, (xs, ys) in by_p.items():
            if len(xs) >= MIN_TRIALS and np.std(xs) > 0 and np.std(ys) > 0:
                rho, _ = spearmanr(xs, ys)
                if np.isfinite(rho): out[p] = rho
        return out
    mt, mb = rho_map("top", feat), rho_map("below", feat)
    common = sorted(set(mt) & set(mb))
    if len(common) >= MIN_PARTICIPANTS:
        a = np.array([abs(mt[p]) for p in common])  # |rho|: magnitude, not sign
        b = np.array([abs(mb[p]) for p in common])
        try:
            pm = wilcoxon(a, b).pvalue
        except ValueError:
            pm = float("nan")
        mod = f"|rho| top {np.median(a):.3f} vs below {np.median(b):.3f}  p={pm:.3f} (n={len(common)})"
    for tag in ("top", "below"):
        n, med, p = line[tag]
        print(f"{feat:<24} {tag:<6} {n:>4} {med:>8.3f} {p:>7.3f}   {mod if tag=='top' else ''}")
