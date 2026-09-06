# Feature-extractor lineage

**Source audit: 2026-09-04.** The same M4 label and nine field names have been
used for different measurements. Their outputs must retain the producer,
sensor requirements, row population, AOI version, coordinate convention, and
time window. A successful arithmetic parity test does not establish all six.

## Current cursor-only typed replay

[`m4_cursor_aoi_rerun.py`](../../scripts/m4_cursor_aoi_rerun.py) calls the
actual `ResultFeatureTracker` exported by the sibling approach-retreat library
through [`m4_cursor_tracker.mjs`](../../scripts/m4_cursor_tracker.mjs).
There is no copied Python implementation to drift from the accumulator.

The experiment uses the post-collision typed maps and their exclusion list.
It verifies the maps' content hash before extraction. Mouse events remain in
document CSS pixels; AOI centers are converted from screenshot coordinates
using the existing per-trial geometry helper. The 100 px proximity threshold
therefore has the same units as the browser tracker.

Every main-axis typed AOI receives a row, whether the cursor or gaze visited it
or not. Trials require at least two AOIs, a uniquely attributable final click
under strict X+Y containment, and two distinct mousemove timestamps before
the largest buffer cutoff. Off-box or ambiguous clicks are excluded and
counted, rather than snapped to a Y band or labeled as known non-click trials.
The entire alignment-eligible corpus is considered, but these additional
quality gates make the analyzed denominator smaller.

Only native `mousemove` events enter features; click/hover/gaze observations do
not. The final click supplies the outcome and the cutoff, not a predictor.
The 0 and 500 ms conditions use identical trial/AOI rows and labels. M1 is
position alone; M4-7 drops final and retreat distances; M4-9 retains them as
a diagnostic. Scaling and balanced logistic regression are fit separately
inside each leave-one-participant-out training fold.

The output at `scripts/output/m4_cursor_aoi/summary.json` contains only
aggregate results, participant-paired uncertainty, coverage counts, source
hashes, and sampling diagnostics. NB21's independent reader checks the source
and substrate before displaying results and generating current K rows.

This is **[LAB, AdSERP, typed, cursor-only] offline replay**. The accumulator is
the real JS implementation; browser lifecycle equivalence is not established.
In particular, all-AOI replay has no IntersectionObserver eligibility gate or
browser sampling throttle. It is a new protocol, not a replacement numeric
value for the old organic experiment.

## Active gaze-dependent LAB stream

[`compute_cursor_approach_features.py`](../../scripts/compute_cursor_approach_features.py)
loads fixations and groups them into AOI positions. Only those positions emit
records. Cursor locations are interpolated at fixation timestamps; distance
fields come from `gaze_cursor_distance(fix['x'], fix['y'], mx, my)`.
`dwell_in_proximity_ms` sums fixation durations when the cursor is near the
estimated result center. These are not the browser's cursor-to-center
distance and mousemove-interval dwell measurements.

Its `cursor-approach-features-*.json` caches remain useful for gaze–cursor
coupling, load analyses, and gaze-grounded taxonomy. They also feed
[`click_buffer_ablation.py`](../../scripts/click_buffer_ablation.py), the
constant-sensitivity harness, and the approach-truncation ablation. Those
analyses must be labeled gaze-dependent LAB diagnostics, even when a model's
feature list contains no field named `gaze`. The August 31 M4-7 AUC 0.9040
belongs to this stream. Removing explicit gaze columns cannot undo gaze-based
row selection or feature construction.

## Historical cursor-only reconstruction

[`m4_nb21_hybrid_rerun.py`](../../scripts/m4_nb21_hybrid_rerun.py) computes
vertical distances from positional mouse events to centers estimated using
XPath observations or linear page bands. It derives its row lattice from an
older feature cache and has neither an `organic_hybrid` AOI option nor a
500 ms buffer. Here, “hybrid” describes XPath plus linear reconstruction.

Earlier versions of this document claimed that script produced the buffered
organic 0.847 headline. The current source does not support that attribution.
Synthetic parity files are in **approach-retreat/scripts/**, not this repo's
scripts directory. They check feature arithmetic on a supplied trace, not the
data selection or geometry that produced a reported AUC. The new typed stream
therefore calls the actual accumulator and records its source hash.

## What remains to validate

- Inspect how many cursor samples each buffer removes. Equal scores from an
  unchanged trace do not establish robustness to removal of the terminal
  approach. The new summary reports both removed samples and affected trials.
- Run full terminal-approach excision on the cursor-only stream; existing
  gaze-dependent excision results cannot stand in for this control.
- Evaluate browser visibility/sampling policies before claiming end-to-end
  browser parity, and preserve matched populations when comparing protocols.
- Reconcile historical claims by producer and rank type. Preserve their K IDs
  and dates; do not silently overwrite them with a new typed result.
- Keep cell-resolved analyses pending until the separate carousel-cell
  producer is rebuilt and verified. Parent-card repairs do not validate cells.
