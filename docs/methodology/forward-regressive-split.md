# Forward / Regressive Episode Split

**Stable ID:** M:forward-regressive-split
**Status:** current as of 2026-04-30; canonical implementation: `notebooks-v2/episode_classifier.py`

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

### 5.2 Built-in invariants

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

- 2026-04-08 — design captured in `docs/plans/forward-regressive-split.md`.
- *(date of episode_classifier.py first commit)* — implementation shipped.
- 2026-04-30 — methodology doc created; plan doc retired in favor of this one.
