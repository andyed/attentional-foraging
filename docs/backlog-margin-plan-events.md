# Backlog: Margin Plan Events (Spatial Indexing Before Targeted Selection)

## Observation

Fixation 47 in p011-b3-t2 lands in the left margin, away from result content. It looks like the eye is "bookmarking" a result position — collecting spatial index data to guide a subsequent targeted selection via regression.

## Hypothesis

Some fixations in the left gutter/margin serve as deliberate spatial encoding events ("margin plans"). These are distinct from content-reading fixations:
- Low saliency (no content to process)
- Short dwell (spatial encoding, not reading)
- Positioned in left gutter (x < 100px or in margin area)
- Followed by a forward scroll, then a regression that lands precisely on the indexed result

**Prediction:** Trials with margin-plan fixations should have *better* regression landing precision regardless of cognitive load, because the user explicitly encoded spatial position rather than relying on incidental encoding during content reading. This would explain some of the null result in notebook 12 — the load-precision relationship is moderated by encoding strategy.

## Detection Criteria (Draft)

```
margin_plan_fixation:
  x < 100px OR x > result_right_edge
  saliency_mean < 0.1 (low visual content)
  duration < 200ms (quick spatial sample)
  NOT the first fixation on a page (not orientation)
  followed within 5s by a regression to within ±1 result position
```

## Analysis Plan

1. Detect margin-plan fixations across all 2,776 trials
2. Compute: prevalence (% trials), frequency (per trial), timing (when in trial)
3. Test: regression precision WITH margin plan vs WITHOUT (within-participant)
4. Test: interaction with LHIPA — does margin planning compensate for high load?
5. Connect to Rayner: this is a deliberate preview strategy, not incidental parafoveal processing

## Connection to Existing Notebooks

- **07b (regression triggers):** Margin plans may be a detectable pre-regression signal
- **07c (regression kinematics):** Do regressions after margin plans have different velocity profiles? (more ballistic = more confident target)
- **12 (precision by load):** Margin plans as a moderator variable — split the null result
- **Scrutinizer:** Foveation mask at margin-plan fixations should show minimal content processing — the eye is there for spatial coordinates, not visual features

## Priority

Medium — requires new notebook (13?). The margin-plan hypothesis explains individual differences in regression precision better than cognitive load alone.

---

# Also backlogged: Larger foveal radius captures

Re-capture gazeplots with a larger foveal radius (e.g., 90px instead of 45px). Benefits:
1. More readable — shows more of the result text the participant was evaluating
2. Hides alignment imprecision — mask is larger than the offset error
3. Better matches the actual useful field of view during reading (~2° parafoveal)

Currently `TEST_RADIUS=45` in the capture script. Try 75-90px and compare.
