"""create_nb12.py — generates 12_regression_precision_by_load.ipynb"""
import nbformat as nbf

nb = nbf.v4.new_notebook()

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

# ── Cell 0: Title + hypothesis ─────────────────────────────────────────────
nb.cells.append(md("""\
# 12. Regression Precision by Cognitive Load

**Hypothesis:** Higher cognitive load (LHIPA) during first-pass reading predicts
lower regression landing precision, because spatial memory encoding degrades under load.

**Mechanism:** Under high load, effective parafoveal preview narrows (Rayner 1998;
Henderson & Ferreira 2004), reducing spatial context encoded around the fixation target.
When the user later regresses to re-evaluate that result, impoverished spatial memory
produces a less precise landing saccade.

**Test:** Per-trial LHIPA vs regression landing offset from the clicked result's
click position.

| Measure | Source | Granularity |
|---------|--------|-------------|
| LHIPA | `lhipa_per_trial.json` | Per trial |
| Fixation page-Y | AdSERP Gazepoint GP3 HD + scroll interpolation | Per fixation |
| Scroll events | AdSERP mouse-movement-data | Per event |
| Click position | AdSERP mouse-movement-data (click events, page-space) | Per trial |

**Dataset:** AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025).
2,776 trials, 47 participants.
"""))

# ── Cell 1: Imports + loading ──────────────────────────────────────────────
nb.cells.append(code("""\
import sys, os
sys.path.insert(0, os.path.abspath('.'))   # notebooks-v2/ is cwd when running

from data_loader import (
    get_trial_ids, load_fixations, load_mouse_events,
    get_trial_meta, interpolate_scroll, load_lhipa,
)
import numpy as np
import matplotlib
matplotlib.rcParams.update({
    'figure.dpi': 150, 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
})
import matplotlib.pyplot as plt
from scipy import stats

lhipa_data = load_lhipa()          # dict: trial_id -> {lhipa, mean_pd, ...}
trial_ids  = get_trial_ids()

print(f"Total trials:  {len(trial_ids):,}")
print(f"LHIPA records: {len(lhipa_data):,}")
sample = list(lhipa_data.items())[0]
print(f"Example: {sample[0]} → {sample[1]}")
"""))

# ── Cell 2: page-Y computation ─────────────────────────────────────────────
nb.cells.append(code("""\
# page_y = screen_y (FPOGY) + scroll_offset_at_fixation_time
# scroll events in mouse-data have cumulative page scroll in ypos.
# data_loader.interpolate_scroll() does piecewise-linear interpolation.

# Demonstrate on one trial
tid = 'p004-b2-t3'
fixations = load_fixations(tid)
_, scrolls, clicks = load_mouse_events(tid)
doc_h, scr_h, _ = get_trial_meta(tid)

scroll_ts = [s[0] for s in scrolls]
scroll_ys = [s[1] for s in scrolls]

# Annotate first 5 fixations with page_y
print(f"Trial {tid}  doc_h={doc_h}  scr_h={scr_h}  scrolls={len(scrolls)}  clicks={len(clicks)}")
print(f"{'fix':>4}  {'t':>14}  {'screen_y':>9}  {'scroll':>8}  {'page_y':>8}")
for i, fx in enumerate(fixations[:5]):
    sc = interpolate_scroll(fx['t'], scroll_ts, scroll_ys)
    print(f"{i:>4}  {fx['t']:>14.0f}  {fx['y']:>9.1f}  {sc:>8.1f}  {fx['y']+sc:>8.1f}")

# Click position (page-space y from mouse event)
if clicks:
    ct, cx, cy = clicks[0]
    print(f"\\nClick at page_y={cy:.0f}  (t={ct})")
"""))

# ── Cell 3: first-pass identification (first backward scroll) ──────────────
nb.cells.append(code("""\
# First-pass = fixations before the first backward scroll gesture.
# A backward scroll gesture = scroll sequence where cumulative delta < -THRESHOLD.
# We segment scrolls by 200 ms gaps (same as 07c_regressions_kinematics).

BACKWARD_THRESHOLD = -50   # px cumulative scroll to count as regression gesture
GAP_MS = 200               # ms gap between scroll events to break gestures

def first_backward_scroll_time(scrolls):
    \"\"\"Return timestamp of first backward scroll gesture, or None.\"\"\"
    if len(scrolls) < 2:
        return None
    # Segment into gestures
    gestures = [[scrolls[0]]]
    for i in range(1, len(scrolls)):
        if scrolls[i][0] - scrolls[i-1][0] > GAP_MS:
            gestures.append([scrolls[i]])
        else:
            gestures[-1].append(scrolls[i])
    for g in gestures:
        delta = g[-1][1] - g[0][1]
        if delta < BACKWARD_THRESHOLD:
            return g[0][0]   # timestamp when regression begins
    return None

# Quick sanity-check
tid = 'p004-b2-t3'
_, scrolls, _ = load_mouse_events(tid)
t_reg = first_backward_scroll_time(scrolls)
print(f"First backward scroll at t={t_reg}")
fix = load_fixations(tid)
fp_fix = [f for f in fix if f['t'] < t_reg] if t_reg else fix
print(f"Total fixations: {len(fix)}  First-pass fixations: {len(fp_fix)}")
"""))

# ── Cell 4: regression landing offset ─────────────────────────────────────
nb.cells.append(code("""\
# For each trial:
#   1. Get click page_y (last click event, which is the result selection)
#   2. Find first backward scroll gesture start time
#   3. After the gesture ends, find first fixation within LANDING_WINDOW px of click
#   4. landing_offset = |fixation_page_y - click_page_y|

LANDING_WINDOW = 400   # px — must land within this radius to count

records = []

for tid in trial_ids:
    if tid not in lhipa_data:
        continue
    try:
        _, scrolls, clicks = load_mouse_events(tid)
        doc_h, scr_h, _ = get_trial_meta(tid)
        if doc_h is None or not clicks or len(scrolls) < 2:
            continue

        # Click position: last click (the result selection click)
        click_t, click_x, click_page_y = clicks[-1]

        # First backward scroll
        t_reg = first_backward_scroll_time(scrolls)
        if t_reg is None:
            continue   # no regression → skip

        # End of the backward scroll gesture (last scroll event before next gap)
        scroll_ts = [s[0] for s in scrolls]
        scroll_ys = [s[1] for s in scrolls]

        # Find gesture end: first scroll event after t_reg that is > GAP_MS apart
        gesture_end_t = t_reg
        for i, (st, sy) in enumerate(scrolls):
            if st < t_reg:
                continue
            if i + 1 < len(scrolls) and scrolls[i+1][0] - st > GAP_MS:
                gesture_end_t = st
                break
            gesture_end_t = st   # last scroll in gesture

        # Fixations after gesture ends
        fixations = load_fixations(tid)
        post_fix = [f for f in fixations if f['t'] > gesture_end_t]
        if not post_fix:
            continue

        # Find first fixation within LANDING_WINDOW of click position
        landing_fix = None
        for fx in post_fix:
            sc = interpolate_scroll(fx['t'], scroll_ts, scroll_ys)
            page_y = fx['y'] + sc
            if abs(page_y - click_page_y) < LANDING_WINDOW:
                landing_fix = (page_y, abs(page_y - click_page_y))
                break

        if landing_fix is None:
            continue

        # First-pass duration (proxy for encoding time)
        first_pass_dur = (t_reg - (fixations[0]['t'] if fixations else t_reg)) / 1000.0

        records.append({
            'trial_id': tid,
            'lhipa': lhipa_data[tid]['lhipa'],
            'landing_offset': landing_fix[1],
            'click_page_y': click_page_y,
            'first_pass_dur': first_pass_dur,
            'regression_distance': abs(scroll_ys[-1] - scroll_ys[0])
                                   if scroll_ys else 0,
        })
    except Exception:
        continue

print(f"Trials with regression landing data: {len(records):,}")
if records:
    offsets = [r['landing_offset'] for r in records]
    lhipas  = [r['lhipa'] for r in records]
    print(f"Landing offset: median={np.median(offsets):.0f}px  "
          f"mean={np.mean(offsets):.0f}px  max={max(offsets):.0f}px")
    print(f"LHIPA:          median={np.median(lhipas):.4f}  "
          f"range=[{min(lhipas):.4f}, {max(lhipas):.4f}]")
"""))

# ── Cell 5: LHIPA join + summary stats ───────────────────────────────────
nb.cells.append(code("""\
# records already has LHIPA joined (built in Cell 4).
# Build arrays and log-transform landing_offset (right-skewed).

lhipa_arr   = np.array([r['lhipa']          for r in records])
offset_arr  = np.array([r['landing_offset'] for r in records])
dur_arr     = np.array([r['first_pass_dur'] for r in records])
regdist_arr = np.array([r['regression_distance'] for r in records])

log_offset = np.log1p(offset_arr)   # log(1+x) to handle zeros

print(f"N = {len(records)}")
print(f"LHIPA    mean={lhipa_arr.mean():.4f}  sd={lhipa_arr.std():.4f}")
print(f"Offset   mean={offset_arr.mean():.1f}px  sd={offset_arr.std():.1f}px  "
      f"skew={stats.skew(offset_arr):.2f}")
print(f"log(offset+1)  skew={stats.skew(log_offset):.2f}")
"""))

# ── Cell 6: core test ─────────────────────────────────────────────────────
nb.cells.append(code("""\
# === Core test: Spearman ρ(LHIPA, landing_offset) ===

rho, p = stats.spearmanr(lhipa_arr, offset_arr)
print(f"Spearman ρ = {rho:.3f}  p = {p:.3e}  N = {len(records)}")

# Tercile split
tercile_cuts = np.percentile(lhipa_arr, [33.3, 66.7])
labels = np.digitize(lhipa_arr, tercile_cuts)          # 0=Low, 1=Med, 2=High
label_names = ['Low\\nLHIPA', 'Med\\nLHIPA', 'High\\nLHIPA']
colors = ['#4CAF50', '#FFC107', '#F44336']

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle('LHIPA vs Regression Landing Precision', fontsize=14, fontweight='bold')

# 1. Scatter
axes[0].scatter(lhipa_arr, offset_arr, alpha=0.25, s=12, color='steelblue')
m, b = np.polyfit(lhipa_arr, offset_arr, 1)
xs = np.linspace(lhipa_arr.min(), lhipa_arr.max(), 100)
axes[0].plot(xs, m * xs + b, color='firebrick', lw=1.5)
axes[0].set_xlabel('LHIPA (cognitive load)')
axes[0].set_ylabel('Landing offset (px)')
axes[0].set_title(f'Spearman ρ = {rho:.3f}\\np = {p:.3e}  N = {len(records)}')

# 2. Tercile bar chart (mean ± SE)
means = [offset_arr[labels == k].mean() for k in range(3)]
sems  = [offset_arr[labels == k].std() / np.sqrt((labels == k).sum()) for k in range(3)]
ns    = [(labels == k).sum() for k in range(3)]
bars  = axes[1].bar(range(3), means, yerr=sems, color=colors, capsize=5, alpha=0.85)
for i, (bar, n) in enumerate(zip(bars, ns)):
    axes[1].text(bar.get_x() + bar.get_width()/2, 2,
                 f'n={n}', ha='center', va='bottom', fontsize=9, color='white')
axes[1].set_xticks(range(3))
axes[1].set_xticklabels(label_names)
axes[1].set_ylabel('Mean landing offset (px)')
axes[1].set_title('Precision by Load Tercile\\n(mean ± SE)')

# 3. LHIPA distribution
axes[2].hist(lhipa_arr, bins=30, color='steelblue', alpha=0.75, edgecolor='white')
for cut in tercile_cuts:
    axes[2].axvline(cut, color='gray', lw=1, ls='--')
axes[2].set_xlabel('LHIPA')
axes[2].set_ylabel('Count')
axes[2].set_title('LHIPA Distribution\\n(regression trials)')

plt.tight_layout()
plt.savefig('plot12_regression_precision_by_load.png', dpi=150, bbox_inches='tight')
plt.show()
print("Saved → plot12_regression_precision_by_load.png")
"""))

# ── Cell 7: controls ──────────────────────────────────────────────────────
nb.cells.append(code("""\
# === Partial correlation: LHIPA → offset, controlling for regression distance
#     and first-pass duration ===
#
# Partial correlation via residuals: regress out the control from both
# LHIPA and offset, then correlate the residuals.

from scipy.linalg import lstsq

def partial_spearman(x, y, controls):
    \"\"\"Spearman correlation between x and y after removing controls linearly.\"\"\"
    C = np.column_stack([controls, np.ones(len(x))])
    x_resid = x - C @ lstsq(C, x)[0]
    y_resid = y - C @ lstsq(C, y)[0]
    return stats.spearmanr(x_resid, y_resid)

# Normalise controls
reg_dist_z = (regdist_arr - regdist_arr.mean()) / (regdist_arr.std() + 1e-9)
dur_z       = (dur_arr    - dur_arr.mean())     / (dur_arr.std()    + 1e-9)

rho_pc, p_pc = partial_spearman(lhipa_arr, offset_arr, [reg_dist_z, dur_z])
print(f"Partial Spearman ρ = {rho_pc:.3f}  p = {p_pc:.3e}  "
      f"(controlling for regression distance + first-pass duration)")

# Multiple regression: offset ~ lhipa + regression_distance + first_pass_dur
X = np.column_stack([lhipa_arr, reg_dist_z, dur_z, np.ones(len(lhipa_arr))])
coeffs, _, _, _ = lstsq(X, offset_arr)
pred = X @ coeffs
ss_res = ((offset_arr - pred) ** 2).sum()
ss_tot = ((offset_arr - offset_arr.mean()) ** 2).sum()
r2 = 1 - ss_res / ss_tot

print(f"\\nMultiple regression: offset ~ lhipa + regression_dist + first_pass_dur")
print(f"  β_lhipa            = {coeffs[0]:+.2f} px per unit LHIPA")
print(f"  β_regression_dist  = {coeffs[1]:+.2f} px (normalised)")
print(f"  β_first_pass_dur   = {coeffs[2]:+.2f} px (normalised)")
print(f"  R²                 = {r2:.3f}")

# Bivariate correlates (for context)
rho_dist, p_dist = stats.spearmanr(regdist_arr, offset_arr)
rho_dur,  p_dur  = stats.spearmanr(dur_arr,     offset_arr)
print(f"\\nBivariate: ρ(regression_distance, offset) = {rho_dist:.3f}  p={p_dist:.3e}")
print(f"Bivariate: ρ(first_pass_dur, offset)       = {rho_dur:.3f}  p={p_dur:.3e}")
"""))

# ── Cell 8: interpretation ────────────────────────────────────────────────
nb.cells.append(md("""\
## Interpretation

### If significant (LHIPA predicts landing offset)

**Spatial memory encoding degrades under cognitive load.** First-pass fixation on
the clicked result under high load produces a weaker position memory, leading to less
precise regression targeting.

**Parafoveal preview connection:** Under high load, the effective useful field of view
narrows (Henderson & Ferreira 2004). Less spatial context is encoded around the fixation
point. The regression saccade has fewer landmarks to guide it.

**Scrutinizer visualization:** This motivates load-modulated foveation. During replay,
LHIPA could dynamically adjust the V1 stage's eccentricity-dependent spatial pooling —
tighter effective fovea under high load, wider useful field under low load.

**AFE connection:** Cognitive load at the moment of encoding determines the quality of
the spatial memory that supports later re-evaluation (the regression). This is a
mechanism for how σ² (uncertainty in saccade planning) increases with encoding load.

### If null

- Regression landing precision may be dominated by scroll mechanics (ballistic return)
  rather than memory-guided saccades
- Per-trial LHIPA is too coarse — load at the specific moment of first-pass fixation
  on the clicked result matters, not trial average
- The ~6 corrective fixations after landing (Finding 9) may compensate for imprecise
  landings regardless of initial load

### Limitations and next steps

- **Coarse load measure:** Per-trial LHIPA is a proxy. First-pass-specific LHIPA
  (pupil samples from trial-start to first backward scroll) would be more precise.
- **Scroll mechanics confound:** Regression distance and ballistic scroll velocity
  likely dominate landing precision; partial correlation tests this.
- **Click as proxy for target:** We use click position as the "intended regression
  target." This is valid only when users are regressing specifically to re-evaluate
  the clicked result, not scrolling generally.
- **Next:** Segment pupil samples by first-pass period and recompute LHIPA on that
  window alone. Compare landing precision for clicked vs non-clicked regression targets.
"""))

# ── Write ──────────────────────────────────────────────────────────────────
out = 'notebooks-v2/12_regression_precision_by_load.ipynb'
with open(out, 'w') as f:
    nbf.write(nb, f)
print(f"Written: {out}  ({len(nb.cells)} cells)")
