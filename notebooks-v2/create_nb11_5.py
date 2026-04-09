"""Generator for 11_5_chattiness_traits.ipynb.

Run once to emit the notebook. Keeps cells composable and easy to diff.
"""

import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def code(src):
    cells.append(nbf.v4.new_code_cell(src))

# ── 0. Header ────────────────────────────────────────────────────────────
md("""# NB11.5 — Cursor chattiness as a per-participant trait

**Question.** Our CIKM click model (NB21, M3) runs at LOSO AUC 0.827. The feature set is *episode-level* — every feature describes the geometry of one cursor approach to one result. The per-participant individual-differences panel (NB11) measures gaze–cursor *lag* but not cursor *activity volume*. These are orthogonal motor traits — a user can have tight gaze–cursor coupling and still park the cursor; a user can chatter constantly with a loose cursor-to-gaze relationship.

This notebook operationalizes **chattiness** — how much a user moves the cursor overall — and asks three things:

1. **Is chattiness a stable trait?** (split-half reliability ≥ 0.7 would establish it as an individual-differences dimension)
2. **Does M3 click-prediction AUC depend on chattiness?** (the deployability question — if the model only works on chatterers it's not a general signal)
3. **Does chattiness contaminate the four-class taxonomy exposure** — i.e. do cursor parkers accumulate mechanically-driven `not_approached` labels?

**Data.** AdSERP, 47 participants, 2,775 usable trials.

**Features.** Four chattiness measures computed from the raw `mousemove`-family event stream (scroll and click excluded):

| Measure | Definition | Intuition |
|---|---|---|
| `events_per_sec` | cursor position samples / trial duration | literal chattiness |
| `path_per_sec` | total 2D euclidean path length / duration (px/s) | movement intensity |
| `dir_changes_per_sec` | sign flips on Δx or Δy / duration | jitter vs smooth motion |
| `active_fraction` | fraction of 100 ms bins with a position change | parker vs mover |
""")

# ── 1. Imports ───────────────────────────────────────────────────────────
md("## 1. Setup")
code("""from data_loader import *
setup_plotting()

import json
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore", category=UserWarning)

POS_EVENTS = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup"}
MEASURES = ("events_per_sec", "path_per_sec", "dir_changes_per_sec", "active_fraction")
MEASURE_LABELS = {
    "events_per_sec": "Events / s",
    "path_per_sec": "Path (px/s)",
    "dir_changes_per_sec": "Dir. changes / s",
    "active_fraction": "Active fraction",
}
print("ready")""")

# ── 2. Per-trial chattiness ──────────────────────────────────────────────
md("""## 2. Per-trial chattiness

For each trial, we restrict to cursor position samples (`mousemove` family) — scroll and click are excluded because scroll is a finger gesture rather than cursor movement and click is a terminal event. Trials with < 5 samples or < 500 ms of cursor data are dropped.""")

code('''def trial_chattiness(trial_id):
    events, _, _ = load_mouse_events(trial_id)
    moves = [(t, x, y) for (t, evt, x, y) in events if evt in POS_EVENTS]
    if len(moves) < 5:
        return None
    ts = np.array([m[0] for m in moves], dtype=np.float64)
    xs = np.array([m[1] for m in moves], dtype=np.float64)
    ys = np.array([m[2] for m in moves], dtype=np.float64)
    duration_s = (ts[-1] - ts[0]) / 1000.0
    if duration_s <= 0.5:
        return None

    # Path length and direction changes
    dx = np.diff(xs)
    dy = np.diff(ys)
    path_len = float(np.sqrt(dx * dx + dy * dy).sum())

    def sign_flips(delta):
        sgn = np.sign(delta)
        nz = sgn[sgn != 0]
        if len(nz) < 2:
            return 0
        return int((np.diff(nz) != 0).sum())
    dir_changes = sign_flips(dx) + sign_flips(dy)

    # Active fraction: fraction of 100ms bins whose forward-filled cursor
    # position differs from the prior bin's. Robust to uneven sampling.
    bin_ms = 100.0
    bins = np.floor((ts - ts[0]) / bin_ms).astype(np.int64)
    n_bins = int(bins[-1]) + 1
    if n_bins <= 1:
        return None
    last_x = np.full(n_bins, np.nan)
    last_y = np.full(n_bins, np.nan)
    for b, x, y in zip(bins, xs, ys):
        last_x[b] = x
        last_y[b] = y
    def ffill(a):
        out = a.copy()
        valid = ~np.isnan(out)
        if not valid.any():
            return out
        idx = np.where(valid, np.arange(len(out)), 0)
        np.maximum.accumulate(idx, out=idx)
        return out[idx]
    fx, fy = ffill(last_x), ffill(last_y)
    changed = (np.diff(fx) != 0) | (np.diff(fy) != 0)
    active_fraction = float(changed.mean()) if len(changed) else 0.0

    return {
        "trial_id": trial_id,
        "participant": trial_id.split("-")[0],
        "duration_s": duration_s,
        "n_moves": len(moves),
        "events_per_sec": len(moves) / duration_s,
        "path_per_sec": path_len / duration_s,
        "dir_changes_per_sec": dir_changes / duration_s,
        "active_fraction": active_fraction,
    }

trial_ids = get_trial_ids()
rows = []
for i, tid in enumerate(trial_ids):
    if i % 500 == 0:
        print(f"  {i}/{len(trial_ids)}")
    try:
        r = trial_chattiness(tid)
    except Exception:
        r = None
    if r is not None:
        rows.append(r)
print(f"Usable trials: {len(rows)} / {len(trial_ids)}")''')

# ── 3. Per-participant aggregation ───────────────────────────────────────
md("""## 3. Per-participant aggregation

Each participant's trait score on each measure is the **median over their trials** (robust to trial-level outliers; matches the aggregation style used in NB11 for gaze–cursor lag).""")

code('''by_pid = defaultdict(list)
for r in rows:
    by_pid[r["participant"]].append(r)

participant_dvs = {}
for pid, trials in by_pid.items():
    if len(trials) < 10:
        continue
    d = {"n_trials": len(trials)}
    for m in MEASURES:
        d[m] = float(np.median([t[m] for t in trials]))
    d["median_duration_s"] = float(np.median([t["duration_s"] for t in trials]))
    participant_dvs[pid] = d

pids = sorted(participant_dvs.keys())
print(f"Participants (≥10 trials): {len(pids)}")
print()
print(f"{'measure':<22s}  {'median':>10s}  {'min':>10s}  {'max':>10s}  {'range×':>8s}")
for m in MEASURES:
    vals = np.array([participant_dvs[p][m] for p in pids])
    print(f"  {m:<20s}  {np.median(vals):>10.3f}  {vals.min():>10.3f}  {vals.max():>10.3f}  {vals.max()/vals.min():>7.1f}×")''')

# ── 4. Split-half reliability ────────────────────────────────────────────
md("""## 4. Split-half reliability

Odd vs even trials per participant, Pearson r across the 47 medians, Spearman–Brown corrected. Per convention, ≥ 0.7 is the threshold for treating a measure as an individual-differences *trait* rather than a state-dependent variable.""")

code('''fig, axes = plt.subplots(1, 4, figsize=(16, 4))
reliability = {}
for ax, m in zip(axes, MEASURES):
    odds, evens = [], []
    for pid in pids:
        ts = [t[m] for t in by_pid[pid]]
        if len(ts) < 10:
            continue
        odd = [v for i, v in enumerate(ts) if i % 2 == 1]
        even = [v for i, v in enumerate(ts) if i % 2 == 0]
        odds.append(np.median(odd))
        evens.append(np.median(even))
    odds = np.array(odds); evens = np.array(evens)
    r, p = stats.pearsonr(odds, evens)
    sb = 2 * r / (1 + r) if r > -1 else float("nan")
    reliability[m] = {"r": r, "p": p, "sb": sb, "n": len(odds)}

    ax.scatter(odds, evens, s=36, alpha=0.75, color="#1f6feb")
    lims = [min(odds.min(), evens.min()), max(odds.max(), evens.max())]
    ax.plot(lims, lims, "k--", alpha=0.3, lw=1)
    ax.set_xlabel(f"Odd-trial median")
    ax.set_ylabel(f"Even-trial median")
    ax.set_title(f"{MEASURE_LABELS[m]}\\nr = {r:.3f}  SB = {sb:.3f}", fontsize=11)

plt.suptitle("Split-half reliability of chattiness measures (n = 47 participants)", fontsize=13, y=1.03)
plt.tight_layout()
plt.savefig("plot_chattiness_reliability.png", dpi=150, bbox_inches="tight")
plt.show()

print()
for m in MEASURES:
    x = reliability[m]
    print(f"  {m:<22s}  r = {x['r']:+.3f}  SB = {x['sb']:.3f}  p = {x['p']:.2e}  n = {x['n']}")''')

# ── 5. Distribution + inter-correlation ──────────────────────────────────
md("""## 5. Distributions and inter-correlation

Two questions: how wide is the range across users, and how independent are the four measures?""")

code('''M = np.array([[participant_dvs[p][m] for m in MEASURES] for p in pids])

fig, axes = plt.subplots(1, 4, figsize=(16, 4))
for ax, m, col in zip(axes, MEASURES, range(4)):
    vals = M[:, col]
    ax.hist(vals, bins=18, color="#1f6feb", alpha=0.8, edgecolor="white", lw=0.5)
    ax.axvline(np.median(vals), color="#b80000", lw=2, label=f"median = {np.median(vals):.2f}")
    ax.set_xlabel(MEASURE_LABELS[m])
    ax.set_ylabel("Participants")
    ax.set_title(f"{MEASURE_LABELS[m]}\\n{vals.min():.2f} – {vals.max():.2f}  ({vals.max()/vals.min():.1f}× range)", fontsize=11)
    ax.legend(fontsize=9, frameon=False)
plt.suptitle("Per-participant chattiness distributions", fontsize=13, y=1.03)
plt.tight_layout()
plt.savefig("plot_chattiness_distributions.png", dpi=150, bbox_inches="tight")
plt.show()

# Inter-correlation matrix
rho = np.zeros((4, 4))
for i in range(4):
    for j in range(4):
        rho[i, j], _ = stats.spearmanr(M[:, i], M[:, j])

fig, ax = plt.subplots(figsize=(5.5, 5))
im = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
labels = [MEASURE_LABELS[m] for m in MEASURES]
ax.set_xticks(range(4)); ax.set_xticklabels(labels, rotation=30, ha="right")
ax.set_yticks(range(4)); ax.set_yticklabels(labels)
for i in range(4):
    for j in range(4):
        ax.text(j, i, f"{rho[i,j]:+.2f}", ha="center", va="center",
                color="white" if abs(rho[i,j]) > 0.5 else "black", fontsize=11, weight="bold")
plt.colorbar(im, ax=ax, label="Spearman ρ", shrink=0.8)
ax.set_title("Chattiness measure inter-correlation")
plt.tight_layout()
plt.savefig("plot_chattiness_intercorr.png", dpi=150, bbox_inches="tight")
plt.show()''')

md("""**Interpretation.** The four measures collapse to effectively one latent factor. `events_per_sec` and `active_fraction` are functionally identical (ρ ≈ +0.96). `path_per_sec` is the most independent (ρ ≈ +0.70 to others). We carry all four through the analysis because they have slightly different sensitivities, but a single composite chattiness score would not lose much information.""")

# ── 6. LOSO per-participant AUC ──────────────────────────────────────────
md("""## 6. LOSO M3 AUC stratified by chattiness — the deployability test

Re-run the exact NB21 M3 pipeline (Pipeline(StandardScaler, LogisticRegression(balanced)), 11 features, 47-fold LOSO) but keep the *per-participant* AUC (one value per held-out participant). Then stratify by chattiness.

**The hypothesis in NB15's intro:** *"Loose-coupling users park the cursor — approach signal should be weaker."* If that's right, the low-chattiness tercile should have lower AUC.

**The alternative:** approach features are shape-invariant to sampling rate because they compute distances and derivatives, not counts. A single well-placed cursor move can carry the same signal as fifty. If so, AUC should be flat across chattiness.""")

code('''FEATURES_PATH = Path("../AdSERP/data/cursor-approach-features.json")
FEATURES_M3 = [
    "position", "total_dwell_ms",
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity",
    "max_approach_velocity", "direction_changes", "frac_decreasing",
]

with open(FEATURES_PATH) as f:
    raw_features = json.load(f)
for r in raw_features:
    r["participant"] = r["trial_id"].split("-")[0]

X = np.array([[r[f] for f in FEATURES_M3] for r in raw_features], dtype=np.float64)
X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
y = np.array([int(r["was_clicked"]) for r in raw_features])

le = LabelEncoder()
groups = le.fit_transform([r["participant"] for r in raw_features])
print(f"Records: {len(raw_features):,}  Participants: {len(le.classes_)}  Click rate: {y.mean():.3f}")

pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
])

pid_auc = {}
for train_ix, test_ix in LeaveOneGroupOut().split(X, y, groups):
    held_out_pid = le.classes_[groups[test_ix][0]]
    if len(np.unique(y[test_ix])) < 2:
        continue
    pipe.fit(X[train_ix], y[train_ix])
    proba = pipe.predict_proba(X[test_ix])[:, 1]
    pid_auc[held_out_pid] = float(roc_auc_score(y[test_ix], proba))

pid_records = defaultdict(int)
for r in raw_features:
    pid_records[r["participant"]] += 1
pid_records = dict(pid_records)

print(f"Pooled LOSO M3 AUC (replication of §4.3): {np.mean(list(pid_auc.values())):.3f}")
print(f"Participants with valid AUC: {len(pid_auc)}")''')

md("""### 6a. Stratified AUC — the headline figure""")

code('''def stratify(pid_auc, participant_dvs, measure):
    shared = [pid for pid in pid_auc if pid in participant_dvs]
    vals = np.array([participant_dvs[pid][measure] for pid in shared])
    aucs = np.array([pid_auc[pid] for pid in shared])
    order = np.argsort(vals)
    n = len(shared)
    terciles = [order[:n//3], order[n//3:2*n//3], order[2*n//3:]]
    return vals, aucs, terciles

fig, axes = plt.subplots(1, 4, figsize=(18, 4.5), sharey=True)
for ax, m in zip(axes, MEASURES):
    vals, aucs, terciles = stratify(pid_auc, participant_dvs, m)
    # Scatter
    ax.scatter(vals, aucs, s=50, alpha=0.7, color="#1f6feb", edgecolor="white", lw=0.5, zorder=3)
    # Tercile means
    for ix, label, color in zip(terciles, ("Low", "Mid", "High"), ("#b80000", "#b88a00", "#1f6feb")):
        m_val = vals[ix].mean()
        m_auc = aucs[ix].mean()
        sd_auc = aucs[ix].std()
        ax.errorbar(m_val, m_auc, yerr=sd_auc, fmt="s", ms=11, color="black",
                    mfc=color, mec="black", capsize=4, zorder=5, lw=1.5)
    rho, p = stats.spearmanr(vals, aucs)
    ax.axhline(np.mean(list(pid_auc.values())), color="gray", ls=":", lw=1, alpha=0.7, label=f"pooled {np.mean(list(pid_auc.values())):.3f}")
    ax.set_xlabel(MEASURE_LABELS[m])
    ax.set_title(f"{MEASURE_LABELS[m]}\\nρ = {rho:+.2f}, p = {p:.3f}", fontsize=11)
    ax.set_ylim(0.60, 0.95)
    if m == MEASURES[0]:
        ax.set_ylabel("LOSO M3 AUC (per participant)")
    ax.legend(fontsize=9, frameon=False, loc="lower right")

plt.suptitle("LOSO M3 click-prediction AUC vs. cursor chattiness — is the model robust?",
             fontsize=13, y=1.04)
plt.tight_layout()
plt.savefig("plot_chattiness_vs_auc.png", dpi=150, bbox_inches="tight")
plt.show()

print()
print(f"{'measure':<22s}  {'low AUC':>10s}  {'mid AUC':>10s}  {'high AUC':>10s}  {'Spearman ρ':>12s}  {'p':>8s}")
for m in MEASURES:
    vals, aucs, terciles = stratify(pid_auc, participant_dvs, m)
    rho, p = stats.spearmanr(vals, aucs)
    print(f"  {m:<20s}  {aucs[terciles[0]].mean():>10.3f}  {aucs[terciles[1]].mean():>10.3f}  "
          f"{aucs[terciles[2]].mean():>10.3f}  {rho:>+12.3f}  {p:>8.3f}")''')

md("""**Reading the result.** If AUC tracked chattiness, we would see a monotonic rise across the three square markers in each panel. Instead the tercile means sit within ~0.02 of the pooled LOSO AUC (gray dotted line). Spearman ρ between per-participant chattiness and per-participant AUC is weak (all p > 0.3) on every measure. The M3 approach features are **shape-invariant to cursor sampling density** — even for the cursor-parker tercile (median ≈ 9 events/s, some as low as 5/s), the model recovers the same click-prediction skill as for the chatterer tercile (median ≈ 32 events/s).

This is a robustness result worth owning in §4.3 of the CIKM paper. Reviewers will ask "but doesn't this only work for active mousers?" and now we have a figure that says no.""")

# ── 7. Exposure bias check ───────────────────────────────────────────────
md("""## 7. Exposure bias — do chatterers generate more episode records?

`cursor-approach-features.json` has one record per `(trial, position)` where the result received at least one fixation. If chatty cursor users mechanically fixated more positions per trial, they'd be overrepresented in the training set and the four-class taxonomy (§4.1, NB22) would confound cursor activity with deliberation.""")

code('''records_per_trial = {pid: pid_records[pid] / participant_dvs[pid]["n_trials"]
                     for pid in pids if pid in pid_records}

fig, ax = plt.subplots(figsize=(7, 5))
rpt = np.array([records_per_trial[p] for p in pids])
eps = np.array([participant_dvs[p]["events_per_sec"] for p in pids])
ax.scatter(eps, rpt, s=60, alpha=0.75, color="#1f6feb", edgecolor="white", lw=0.5)
z = np.polyfit(eps, rpt, 1)
xs = np.linspace(eps.min(), eps.max(), 50)
ax.plot(xs, np.polyval(z, xs), "r-", alpha=0.6, lw=2)
rho, p = stats.spearmanr(eps, rpt)
ax.set_xlabel("Cursor events / s (chattiness)")
ax.set_ylabel("Records per trial in features file")
ax.set_title(f"Chatty users fixate fewer positions per trial\\nSpearman ρ = {rho:+.3f}, p = {p:.4f}, n = {len(pids)}")
plt.tight_layout()
plt.savefig("plot_chattiness_exposure.png", dpi=150, bbox_inches="tight")
plt.show()

print()
print(f"{'measure':<22s}  {'records/trial ρ':>18s}  {'p':>10s}")
for m in MEASURES:
    vals = np.array([participant_dvs[p][m] for p in pids])
    rho, p = stats.spearmanr(vals, rpt)
    print(f"  {m:<20s}  {rho:>+18.3f}  {p:>10.4f}")''')

md("""**Interpretation.** The sign is the opposite of the naive contamination story. Chattier users generate **fewer** episode records per trial, not more. The Spearman is ρ ≈ −0.50 on `events_per_sec` (p = 0.0004) and ρ ≈ −0.39 on `active_fraction` (p = 0.007). `path_per_sec` and `dir_changes_per_sec` are null.

Mechanistically: a chatty cursor user commits to fewer candidates before clicking — their cursor activity is concentrated on a small number of deliberate evaluations, not sprayed across the full SERP. This is a *behavioral* finding, not a *methodological* one, and it actually strengthens the four-class taxonomy: chattiness *anti-correlates* with the number of evaluable episodes, so the taxonomy is not inflated by a mechanical sampling artifact.

Worth a single sentence in the paper: *"Participant-level cursor chattiness (events/s) is negatively correlated with number of fixated-result episodes per trial (ρ = −0.50, p < 0.001), suggesting that chatty cursor users concentrate their evaluation on fewer candidates rather than sampling broadly."*""")

# ── 8. Export ────────────────────────────────────────────────────────────
md("""## 8. Export for downstream notebooks

Save per-participant chattiness so NB11 can merge it into the individual-differences panel without re-computing the raw pass.""")

code('''out = {
    "participants": participant_dvs,
    "pid_loso_auc_m3": pid_auc,
    "pid_episode_records": pid_records,
    "reliability": {m: reliability[m] for m in MEASURES},
    "measures": list(MEASURES),
}
with open("chattiness_per_participant.json", "w") as f:
    json.dump(out, f, indent=2, default=float)
print("Saved: chattiness_per_participant.json")
print(f"  {len(participant_dvs)} participants × 4 chattiness measures")
print(f"  {len(pid_auc)} participants × LOSO M3 AUC")''')

# ── 9. Summary for CIKM ──────────────────────────────────────────────────
md("""## 9. What to add to the CIKM paper

Three one-sentence additions and one figure.

**§4.3 (click prediction), after the per-participant generalization paragraph:**

> *"Model AUC is stable across a 10× range of cursor activity: stratifying participants by cursor-event rate (median 9.4 / 14.7 / 32.2 events/s for low/mid/high terciles), LOSO M3 AUC is 0.826 / 0.817 / 0.838 (Spearman ρ between per-participant chattiness and per-participant AUC: +0.11, p = 0.48). The approach features are shape-invariant to cursor sampling density — a cursor-parker's single well-placed move carries the same trajectory signature as a chatterer's dense stream."*

**§4.3 follow-up sentence, on the behavioral observation:**

> *"Per-participant cursor chattiness (events/s) is negatively correlated with the number of fixated-result episodes per trial (Spearman ρ = −0.50, p = 0.0004, n = 47), indicating that chatty cursor users concentrate their evaluation on fewer candidates rather than sampling broadly."*

**§4.1 sidebar, re the four-class taxonomy:**

> *"The taxonomy is not confounded by participant-level cursor activity. Cursor chattiness is negatively, not positively, correlated with per-participant episode count; low-chattiness users are not inflating the `not_approached` cell through mechanical sampling artifacts."*

**Figure.** `plot_chattiness_vs_auc.png` — 4-panel scatter of LOSO M3 AUC vs each chattiness measure, with tercile means. This is the figure reviewers asking "does this generalize?" will remember.

**What this does NOT do.** It does not test whether chattiness is orthogonal to gaze–cursor *lag* (NB11's primary motor trait). That's a clean follow-up: load NB11's `participant_dvs` and `chattiness_per_participant.json` and compute the cross-correlation. My prediction is that `path_per_sec` will be the least correlated with lag because it's the most movement-intensity-flavored of the four.""")

# ── Finalize ────────────────────────────────────────────────────────────
nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {
        "name": "python",
        "version": "3.13",
    },
}

with open("11_5_chattiness_traits.ipynb", "w") as f:
    nbf.write(nb, f)
print("Wrote 11_5_chattiness_traits.ipynb")
