# Cross-Cutting Forward/Regressive Split

**Status:** superseded by [docs/methodology/forward-regressive-split.md](../methodology/forward-regressive-split.md) on 2026-04-30. Implementation shipped 2026-04-08 (commit `0771e28`, `notebooks-v2/episode_classifier.py`); this plan is retained as design history. Canonical reference is the methodology doc.
**Owner:** Andy
**Date:** 2026-04-08

## Why

Most findings currently pool forward reading (moving downward through results sequentially) with regressive seeking (scrolling back up to re-examine). 1,465 of 2,341 tagged trials (63%) are `regressive_scroller`. The NB24 retreat geometry findings, NB23 rank effects, NB20 cursor approach features, and the approach-retreat library's "retreat as lateral displacement" framing all need a direction-aware split before the CIKM draft numbers freeze.

The approach-retreat brand visualization currently shows lateral retreats because NB24 Top Ad lateral ratio is 0.103 (pooled). Forward-only is likely lower — the lateral component may be partially from regressive re-examination arcs that curve sideways as the cursor returns from below.

## 1. Definition of the Split

Three candidate definitions, scoped to **retreat episodes** (a cursor enter-dwell-exit sequence on a single result):

| Level | Definition | Pros | Cons |
|---|---|---|---|
| A. Trial-level | Use `regressive_scroller` tag wholesale | Trivial, matches catalog | 63% of trials are tagged; most episodes inside them are still forward reads. Destroys signal. |
| **B. Episode-level (recommended)** | At entry time, compare scroll offset to trial high-water-mark: `forward` iff `entry_scroll >= hwm_at_entry - 50px`. Else `regressive`. | Matches retreat granularity. Reuses existing HWM machinery. Handles mixed trials. | Requires episode entry time — NB24 already tracks this. |
| C. Position-level (per-fixation) | Per-fixation `is_forward` via HWM (already exists) | Very fine-grained | Retreats are episode objects, not fixations. Ambiguous mid-arc transitions. |

**Recommendation: B.** Freeze direction at entry time. A regressive re-examination shouldn't get relabeled "forward" just because the participant later scrolls further down.

Precise rule:
```
forward iff scroll_offset(entry_t) >= max(scroll_offset(t) for t <= entry_t) - 50px
```

## 2. Partitioning Primitive

New file: `notebooks-v2/episode_classifier.py` (separate from `data_loader.py` to isolate the episode concept).

```python
def classify_episode(entry_t: int, exit_t: int, trial: dict,
                     tol_px: float = 50.0) -> dict:
    """
    Returns: {
      'direction': 'forward' | 'regressive',
      'entry_scroll': float,
      'hwm_at_entry': float,
      'hwm_deficit': float,     # hwm_at_entry - entry_scroll (0 if forward)
      'post_exit_dy': float,    # cursor net vertical motion 300ms after exit
      'confidence': float,      # 0..1, low near the tolerance band
    }
    """

def classify_trial_episodes(trial: dict, episodes: list[dict],
                            tol_px: float = 50.0) -> list[dict]:
    """Vectorized; also returns per-trial summary counts."""

def build_hwm_timeline(trial: dict) -> tuple[np.ndarray, np.ndarray]:
    """Returns (ts, hwm) — monotonic-nondecreasing HWM scroll per timestamp.
       Cached per trial_id via lru_cache."""
```

Episodes are passed in, not re-detected — every notebook defines them differently (NB20 uses approach features, NB24 uses arc extraction, NB17 uses scroll retreats). The primitive only answers the classification question.

Thin convenience wrapper in `data_loader.py`:
```python
from episode_classifier import classify_episode, classify_trial_episodes
```

## 3. Order of Notebook Updates

1. **NB24** (first) — highest-value validation. Lateral-ratio and arc-ratio claims are the brand of the retreat library. Existing episode objects with `entry_t`/`exit_t` make integration cheap.
2. **NB20** — approach-by-element. Classification colors approaches too (approach to an already-visited result = re-approach/regression). Validates NB24 from the entry side.
3. **NB23** — rank effects. Forward-only rank curves are the paper's dwell-by-rank story. Must split before CIKM numbers freeze.
4. **NB17** — scroll retreats (progenitor). Confirms definition consistency with pure scroll-based analysis.
5. **NB01** — convergence. Mouse-gaze distance likely differs between conditions.
6. **NB05** — LHIPA. Pupil dilation split last; effect sizes small and split halves N per cell.
7. **NB00** — hold. Click-position uptick is downstream; revisit after NB24 + NB23.

## 4. Specific Cells/Sections

- **NB24 §1 (arc extraction)**: after `arcs.append(...)`, add `arc['direction'] = classify_episode(...)['direction']`. Re-run §2 (arc ratio), §3 (Fitts ID × re-approach), §4 (dwell × arc) grouped by `(etype, direction)`. Add a "forward-only" column alongside pooled numbers.
- **NB24 §2 headline**: replace lateral-ratio table with 2×3 grid (direction × etype). Keep pooled row for continuity.
- **NB23 dwell/fixations by rank**: partition per-position aggregation on episode direction. Produce `plot_rank_effects_fwd_only.png` and `plot_rank_effects_regressive.png`.
- **NB20 approach features by element type**: add `direction` as a facet. Expect re-approach entries to show lower Fitts ID, shorter amplitude.
- **NB17 scroll retreat**: sanity-check that `episode_classifier` agrees with existing retreat detector on ≥95% of cases.
- **NB01**: add direction split to convergence curve. Regressive episodes likely show tighter convergence (user already knows where the result is).
- **NB05**: split LHIPA by direction only for aggregate plot; per-position split under-powered.

## 5. Sanity Checks

1. **Lateral ratio monotonicity**: forward-only Top Ad lateral ratio should be **lower** than pooled 0.103 (regressive retreats add lateral wobble). If forward-only exceeds 0.103, classifier is mislabeling.
2. **Re-approach asymmetry**: regressive episodes should have re-approach rate ≥ 40% (vs 8.2% pooled); forward episodes ≤ 8.2%.
3. **Trial coverage**: `regressive_scroller`-tagged trials should contain ≥1 regressive episode in ≥90% of cases. A tagged trial with zero regressive episodes is a red flag.
4. **Mass balance**: `forward_count + regressive_count == total_episodes` exactly; no NaN direction.

## 6. Downstream Impact on approach-retreat Library / CIKM Draft

- **"Retreat as lateral displacement"** framing is derived from pooled numbers. Expect forward-only Top Ad lateral ratio to drop from 0.103 toward ~0.04–0.06. Still nonzero and directional, but the headline claim needs softening from "retreat curves laterally around ads" to "retreat curves laterally around ads **when forward-committed**; regression produces a different signature."
- Library should expose `direction` as a first-class field on every retreat/approach object.
- Arc-ratio 2.36 for Top Ads may partially reflect regressive re-examination arcs that naturally curve because the cursor came back from below. Forward-only arc ratio is the defensible number for the paper.
- Re-approach rate 8.2% → two numbers: forward-only first-visit re-approach rate (~5%?) and regressive re-approach rate (~45%+). The Fitts-ID-predicts-re-approach finding should be re-tested on forward-only first visits; if it survives, it's a stronger claim.
- CIKM draft sections that cite pooled retreat geometry need footnoted disclaimers pending this refactor.

## 7. Risks and Open Questions

- **Tolerance parameter `tol_px=50`**: sweep {25, 50, 100, 200} and report sensitivity. If lateral ratio flips sign between 50 and 100, the finding is fragile.
- **Scroll events are sparse** (only on user scroll). HWM at arbitrary `entry_t` is interpolated. Between scrolls HWM is piecewise constant. Episodes in long no-scroll gaps might be mis-timed by up to a second. Mitigation: use last-known-scroll; log episodes where `entry_t - last_scroll_t > 2000ms` for audit.
- **Mixed-direction arcs**: an arc that enters while forward-committed but exits after a fast scroll-up is rare but possible. "Classify at entry" handles this consistently but loses the mid-arc transition. Accept; flag in validation.
- **Re-approach type refinement**: retain `re_approach` as "any second visit" and add `re_approach_type ∈ {fwd→fwd, fwd→reg, reg→fwd, reg→reg}`.
- **Selection bias**: forward-only cells may over-represent easy trials. Preserve per-participant clustered tests in NB24 §2 and split them too.
- **"Regressive = re-examination"** assumption: some regressions are navigational (scrolling back to click something already decided). These should arguably group with forward-commit. Out of scope for v1; flag as future work.
- **`regressive_scroller` tag** was derived from a different heuristic (scroll-sequence based). If episode-level classifier strongly disagrees with trial-level tag, decide which is canonical before paper freeze.

## Critical Files

- `notebooks-v2/data_loader.py`
- `notebooks-v2/episode_classifier.py` *(new)*
- `notebooks-v2/24_retreat_arc_geometry.ipynb`
- `notebooks-v2/23_rank_effects.ipynb`
- `notebooks-v2/20_approach_by_element.ipynb`
