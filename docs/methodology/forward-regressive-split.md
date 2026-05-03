# Forward / Regressive Episode Split

**Stable ID:** M:forward-regressive-split
**Status:** current as of 2026-05-03; canonical implementation: `notebooks-v2/episode_classifier.py`. 2026-05-03 update adds regression-episode geometry (§5.3), scroll-velocity asymmetry (§5.4), and trial-level n_epochs (§5.5) as derived constructs built on the same HWM substrate.

---

## 1. The rule, in one line

An episode is **forward** iff its scroll offset at entry time is within `tol_px` of the trial's running maximum scroll offset; otherwise it is **regressive**. Direction is frozen at entry and never relabeled.

## 2. Why this rule

Most AdSERP findings pool forward reading (moving down through results sequentially) with regressive seeking (scrolling back up to re-examine). 1,465 of 2,341 tagged trials (63%) are `regressive_scroller`, but most episodes inside those trials are still forward reads. The retreat-arc geometry, rank effects, approach features, and convergence claims all need a direction-aware split before any of those numbers can be cited cleanly.

Three candidates were considered:

| Level | Definition | Why rejected / accepted |
|---|---|---|
| Trial-level | Use `regressive_scroller` tag wholesale | 63% of trials are tagged; most episodes inside them are forward. Destroys signal. **Rejected.** |
| **Episode-level (this rule)** | Compare entry scroll offset to high-water mark at entry, with tolerance band | Matches the granularity at which retreats are extracted. Reuses the per-fixation HWM rule. Handles mixed trials. **Accepted.** |
| Position-level (per-fixation) | Per-fixation `is_forward` via HWM | Retreats are episode objects, not fixations; mid-arc transitions become ambiguous. **Rejected as the episode classifier**, retained as the per-fixation primitive. |

Freezing direction at entry is the load-bearing choice: a regressive re-examination must not get relabeled "forward" merely because the participant later scrolls further down. The same fixation may be forward or regressive depending on what came before, but never on what comes after.

## 3. Where this lives in code

| Function | File | Role |
|---|---|---|
| `classify_fixations(trial, hwm_tolerance=50)` | `notebooks-v2/data_loader.py:915` | **Per-fixation primitive.** Walks fixations in time order; returns `is_forward` for each. The canonical statement of the rule. |
| `build_hwm_timeline(trial)` | `notebooks-v2/episode_classifier.py:32` | Episode-level cache of `(fix_ts, fix_scroll, fix_hwm)`. Computed once per trial, keyed by `trial_id`. |
| `classify_episode(entry_t, trial, tol_px=50.0)` | `notebooks-v2/episode_classifier.py:110` | **Episode classifier.** Wraps the per-fixation rule at episode granularity. Returns `direction`, `entry_scroll`, `hwm_at_entry`, `hwm_deficit`, `confidence`. |
| `classify_trial_episodes(trial, episodes, tol_px=50.0, entry_t_key='entry_t')` | `notebooks-v2/episode_classifier.py:166` | Vectorized wrapper. Returns classified episodes plus a `(forward_count, regressive_count, total)` summary. Asserts mass balance. |

`episode_classifier` does **not** detect episodes; every notebook defines them differently (NB17 scroll-based retreats, NB20 approach features, NB24 retreat arcs). The classifier only answers the direction question for an already-defined episode entry time.

The HWM lookup uses last-known-value scroll sampling — no linear interpolation between scroll events — to maintain bit-for-bit parity with `classify_fixations`.

## 4. Parameters

| Parameter | Default | Range explored | What it controls |
|---|---|---|---|
| `tol_px` | 50 px | {25, 50, 100, 200} (planned) | Pixels below the running scroll maximum that still count as forward. Wider values relax the forward criterion. |
| `entry_t_key` | `'entry_t'` | n/a | Key on each episode dict that names the entry timestamp. Provided for callers that use a different field name. |
| HWM seed | 0.0 | n/a | The scroll high-water mark begins at zero, not at the first scroll sample. Trials with an immediate downward scroll at t=0 are not affected; trials with a `scroll_ys[0] > 0` (rare in AdSERP) would have their first fixation classified against HWM=0 then HWM=`scroll_ys[0]`. |
| Scroll lookup | last-known-value | linear-interp not used | Scroll events are sparse; a fixation between scrolls inherits the most recent scroll sample. |
| Confidence ramp | linear over `[0, tol_px]` | n/a | `confidence` is 1.0 outside the ±`tol_px` band around the boundary, ramps linearly to 0 inside. Used for flagging borderline episodes in audit, not for filtering. |

## 5. Sensitivity tested

### 5.1 Definition robustness on per-visit dwell by rank (2026-04-30)

`scripts/forward_classifier_robustness.py` swept four forward definitions over the full 2,775-trial corpus and checked whether per-visit dwell decreases with rank under each. Output: `scripts/output/f_scan_farce/classifier_robustness.json`.

| Definition | Rule | Spearman ρ (dwell × rank) | p | Range (ms) |
|---|---|---|---|---|
| A. first-arrival | First contiguous block of fixations at a position | **−0.950** | 8.8 × 10⁻⁵ | 653 → 849 |
| B. HWM visit (rank-space) | `pos ≥ running-max-rank`; visit boundary on `pos` change | **−1.000** | 0 | 638 → 936 |
| C. HWM strict-visit | Same as B; re-arrivals at HWM after regression count separately | **−1.000** | 0 | 638 → 936 |
| D. EvR `first_pass` | Pre-computed canonical first-pass list from `encoding-vs-retrieval.json` | +0.633 | 0.067 | 212 → 246 |

**What this establishes.** The qualitative claim — per-visit dwell falls with rank — is invariant under three independent forward definitions (A/B/C). All three give monotonic, near-perfect rank correlations with overlapping mean-dwell ranges. B and C are bit-for-bit identical on this metric (the conceptual difference between them does not materialize at the per-visit aggregate).

**What it does NOT establish.** The pre-segmented `encoding-vs-retrieval.json` first-pass list (D) gives a different metric scale (mean ~230 ms vs ~800 ms) and a non-significant *opposite-signed* correlation. This is a known property of the EvR pipeline, which segments first-pass at finer granularity and excludes consolidations: per-visit dwell on the EvR-curated list is not directly comparable to A/B/C, and any prose that mixes the two is wrong. If a paper cites EvR-first-pass dwell-by-rank, it should note the difference explicitly.

**Caveat: rank-space HWM ≠ scroll-space HWM.** This validation tests definitions in **rank space** (`pos ≥ running-max-rank`). The canonical episode classifier in §3 tests in **scroll space** (`entry_scroll ≥ hwm_at_entry − tol_px`). Position rank is monotonic with scroll Y in steady state, so the two rules are tightly coupled, but they can diverge when the participant scrolls past results without fixating, or when rapid scroll changes outpace fixation events. A direct rank-space-vs-scroll-space agreement check on the same trials has not yet been run — flagged in §6.

### 5.2 Regression-episode geometry (2026-05-03)

The per-episode forward/regressive classifier (§3) labels *each* episode entry. Aggregating one level up: a **regression episode** is a contiguous run of regressive AOI-fixations that ends when HWM advances or the trial ends. Per regression episode, four observables:

| Field | Definition |
|---|---|
| `hwm_onset` | the HWM at the moment the regression began |
| `dip_floor` | the minimum AOI rank reached during the episode |
| `tension` | `hwm_onset − dip_floor` (depth of the regression in ranks) |
| `n_fixations` | number of fixations in the regressive run |

Walking 2,681 trials under bbox-organic attribution yields 9,359 regression episodes. Tension is small for shallow HWM-onset and grows sharply past HWM ≈ 7. The high mean-to-SD ratio at deep HWM (mean ≈ SD) signals a bimodal mix of local re-evaluations + full anchor-returns, not a single Gaussian retreat distribution:

| HWM | n eps | tension mean ± sd | tension p25 / p50 / p75 / p95 | n_fix p50 / p95 | dip p50 | % to pos 0 |
|---:|---:|---|---|---|---:|---:|
| 1 | 2,154 | 1.00 ± 0.00 | 1 / 1 / 1 / 1 | 2 / 13 | 0 | 100% |
| 2 | 1,542 | 1.46 ± 0.50 | 1 / 1 / 2 / 2 | 3 / 21 | 1 | 46% |
| 3 | 1,209 | 1.82 ± 0.91 | 1 / 1 / 3 / 3 | 3 / 25 | 2 | 34% |
| 4 | 996 | 2.23 ± 1.32 | 1 / 2 / 4 / 4 | 3 / 28 | 2 | 30% |
| 5 | 728 | 2.44 ± 1.68 | 1 / 2 / 4 / 5 | 3 / 32 | 3 | 24% |
| 6 | 615 | 2.86 ± 2.13 | 1 / 2 / 5 / 6 | 3 / 41 | 4 | 24% |
| 7 | 607 | 3.75 ± 2.66 | 1 / 3 / 7 / 7 | 4 / 52 | 4 | 33% |
| **8** | 774 | **4.80 ± 3.08** | **1 / 5 / 8 / 8** | **7 / 52** | 3 | **40%** |
| **9** | 512 | **5.58 ± 3.51** | **1 / 7 / 9 / 9** | **9 / 56** | 2 | **44%** |
| **10** | 155 | **6.52 ± 3.95** | **2 / 9 / 10 / 10** | **11 / 50** | 1 | **50%** |
| 11 | 53 | 5.70 ± 4.50 | 1 / 4 / 11 / 11 | 4 / 42 | 7 | 36% |

**Reading the distribution stats.** At HWM ≤ 6, tension SD < 2 ranks — regressions are tightly clustered around their median. At HWM ≥ 8, tension SD ≈ 3–4 ranks with the IQR spanning 1 → 8/9/10 — i.e. trials in the deep stratum bifurcate into "short adjacent regression" (p25 = 1) and "full anchor return" (p75–p95 = 8–10). The "rubber-band" framing is a shorthand for this bimodality, not a single elastic retreat.

Under hybrid attribution (more positions per trial), the same phase transition appears at HWM ≈ 11 with deeper tail (15 ranks tension at HWM 15). The shape is attribution-independent; only the rank-axis location of the transition shifts.

**Two-mode structure.** Below the transition, regressions are local re-evaluation (median tension 1–3 ranks, ~3 fixations). Past it, regressions become long anchor-returns (40–50% land at position 0, 7+ fixations median, 50+ fixations p95). The "rubber band" snaps to a fixed anchor at the top of page rather than scaling proportionally with depth.

Source: `scripts/render_regression_tension.py` → `scripts/output/figures/regression_tension_{organic,hybrid}.png`. The arc-graph variant (`scripts/render_regressive_arcs.py`) gives the source-HWM × target-position joint distribution.

### 5.3 Scroll-velocity asymmetry — independent confirmation (2026-05-03)

The per-fixation rule above operates on *gaze-derived* HWM. The mouse-events stream provides an independent measurement channel: for every consecutive scroll-pair `(t1, y1) → (t2, y2)`, compute `Δy` and `|Δy|/Δt`, label the direction by sign of Δy.

| depth bin (frac of doc) | direction | n events | median speed (px/s) | median \|Δy\| (px) |
|---|---|---:|---:|---:|
| top (<20%) | forward | 115,803 | 740 | 12 |
| top (<20%) | regressive | 46,218 | 830 | 13 |
| mid (20–50%) | forward | 70,788 | 780 | 12 |
| **mid (20–50%)** | **regressive** | 35,475 | **970** | **16** |
| deep (50%+) | forward | 10,543 | 740 | 12 |
| **deep (50%+)** | **regressive** | 6,890 | **930** | **16** |

**Key observations.** Forward scroll velocity is near-constant across depth (740–780 px/s). Only regressive scroll accelerates (830 → 970 px/s) and uses larger per-event strides (16 vs 12 px). The gaze-side acceleration with depth (§5.3) is not an eye-tracking artifact; it lives in the scroll-velocity stream too. **This signal is rank-type-independent** (mouse-events stream; depth bins are fractions of doc-height).

Source: `scripts/render_scroll_velocity.py` → `scripts/output/figures/scroll_velocity.png`.

### 5.4 Trial-level n_epochs and multi-cycle prevalence (2026-05-03)

A second derived construct on the HWM substrate: an **epoch** is a contiguous forward push of the HWM. Epoch 1 begins at the first HWM advance. A new epoch begins when, after a regression below HWM, the user advances HWM beyond its prior max — i.e., resumes scanning into territory not yet visited.

Per trial, `n_epochs`:
- `n_epochs = 1` → pure forward (any regressions did not later push the HWM further).
- `n_epochs = 2` → one regress-scan-regress cycle.
- `n_epochs ≥ 3` → multiple regress-scan-regress cycles.

| Attribution | n_epochs = 1 | ≥ 2 | ≥ 3 |
|---|---:|---:|---:|
| bbox-organic | 38% | **62%** | 37% |
| organic_hybrid | 22% | **79%** | 54% |

**Modal trial structure.** Multi-cycle scanning (`n_epochs ≥ 2`) is the modal pattern under both attributions. The "F-pattern / forward sweep" framing — even with the hedge that regressions exist — under-counts how much of typical SERP scanning is back-and-forth. Per-participant median fraction of trials that are multi-cycle is 0.64 organic / 0.83 hybrid (47/47 participants show ≥1 multi-cycle trial; 95–100% show ≥5).

Sources: `scripts/scan_epochs_per_trial.py` (counts), `scripts/render_scan_epoch_staircase.py` (population staircase + small multiples by `n_epochs`), `scripts/render_staircase_by_strategy.py` (tercile split by per-participant regression rate).

### 5.5 Built-in invariants

- **Mass balance** (`forward_count + regressive_count == total_episodes`) is asserted at every call to `classify_trial_episodes`. No NaN direction is possible.
- **Confidence ramp** flags episodes within ±`tol_px` of the boundary. These should be inspected before any per-cell claim that depends on small forward/regressive deltas.
- **Cache parity** with `classify_fixations`: both implementations use the same last-known-value scroll lookup; episode classifier inherits per-fixation invariants.

## 6. Sensitivity NOT tested

Ordered by likelihood of changing a downstream result.

1. **`tol_px ∈ {25, 50, 100, 200}` sweep on the lateral-ratio claim.** If forward-only Top Ad lateral ratio flips sign between `tol_px=50` and `tol_px=100`, the headline claim is fragile. **Not yet run.**
2. **Long no-scroll-gap episodes.** When `entry_t - last_scroll_t > 2000ms`, the HWM lookup uses a stale scroll sample. The fraction of episodes affected and the per-cell impact on lateral / arc ratios is not yet quantified. Plan: log these episodes during NB24 integration and audit the fraction.
3. **Disagreement with `regressive_scroller` trial tag.** A trial tagged `regressive_scroller` whose episode classifier returns zero regressive episodes is a red flag. The disagreement rate is unknown.
4. **Mixed-direction arcs.** An arc that enters forward-committed but exits after a fast scroll-up is rare but possible. The classifier returns the entry-time direction; the mid-arc transition is silently lost. Frequency unmeasured.
5. **`re_approach_type` decomposition.** The current binary `direction` collapses `{fwd→fwd, fwd→reg, reg→fwd, reg→reg}` into two classes. The four-way split is not yet exposed.
6. **Navigational vs. examination regressions.** Some regressions are navigational (scrolling back to click an already-decided result); these arguably group with forward-commit. Out of scope for v1.

## 7. What's robust regardless of tweaking

- **Mass balance.** Every episode is classified into exactly one direction; the sum equals the input count by construction.
- **Direction is frozen at entry.** Any later scroll cannot relabel a classified episode. This holds independent of `tol_px`.
- **Per-fixation parity.** Episode classifier and `classify_fixations` use the same rule and the same scroll-lookup convention. Any per-fixation analysis on the same trial agrees with the episode-level call at the entry timestamp.
- **The dissociation between the trial-level `regressive_scroller` tag and the episode-level direction.** Most episodes in `regressive_scroller`-tagged trials are forward — this is true regardless of where `tol_px` lands within a reasonable range, because the tag is computed from a different, scroll-sequence-based heuristic.

## 8. Limitations to disclose in papers

- The classifier is **gaze-fixation-driven**, not scroll-event-driven: HWM is sampled at every fixation rather than at every scroll event. A paper that needs a scroll-only direction classifier (e.g., to transfer to ACD / WILD where there are no fixations) cannot use this rule unmodified.
- `tol_px=50` is a defensible default but has not yet been sensitivity-swept on the headline geometry claims. Any paper citing forward-only retreat geometry should note: "results held under `tol_px ∈ {25, 50, 100, 200}`" once the sweep ships, or "results reported at the canonical `tol_px=50`; sensitivity to this parameter has not been quantified" if it has not.
- Direction is binary by design. Papers should not claim a continuous "forward-ness" from this classifier; the `confidence` field is for audit, not for downstream regression.
- Long no-scroll-gap episodes (>2 s since the last scroll event) inherit a stale scroll sample. These should be excluded or flagged before any per-cell claim that depends on small forward/regressive deltas.

## 9. Where this rule appears in published / draft work

- **NB24 retreat arc geometry** — every per-`etype` lateral and arc claim depends on this split.
- **NB23 rank effects** — forward-only rank curves are the dwell-by-rank story.
- **NB20 approach by element** — direction is a facet on every approach claim.
- **NB17 scroll retreats** — sanity-checks classifier agreement with the scroll-only retreat detector.
- **NB01 convergence** — direction split on mouse-gaze distance.
- **NB05 LHIPA** — direction split on aggregate plot only (per-position split under-powered).
- **CIKM 2026 paper-v3, §4 (geometry) and §5 (deferred / eval-rejected split)** — pooled retreat geometry needs forward-only re-statement before numbers freeze.
- **`approach-retreat` library** — `direction` exposed as a first-class field on every retreat / approach object.

## 10. Status

**Status:** current as of 2026-04-30; canonical implementation: `notebooks-v2/episode_classifier.py`

History:

- 2026-04-08 — design captured in `docs/plans/forward-regressive-split.md`; same-day implementation shipped in commit `0771e28` (`notebooks-v2/episode_classifier.py`).
- 2026-04-30 — methodology doc created; plan doc retired in favor of this one.
