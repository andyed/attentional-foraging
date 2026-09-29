# Information-space atlas: measurement contract

Generated 27 September 2026; producers consolidated 29 September 2026 with identical results. Descriptive re-analysis of the same 2,650-trial, 47-participant cohort as the final-approach readout. An earlier poster supplied the overview-to-trace structure.

## Clock and dependent measures

The primary clock starts at the first native mousemove and ends at the final mousedown associated with the final logged click. It totals **13.3423 hours**. Time before the first mousemove and the logged-click delay after mousedown are outside this clock. All spatial views partition this full clock, including unavailable intervals. Every cell reports a duration share, not a share of trials, AOIs or events.

We intersect cursor event times, cursor-coverage endings, fixation starts and ends, scroll events, approach onset and 20 equal-duration trial-bin edges. Exact interval durations provide the weights. Summing any complete spatial partition reproduces the clock to floating-point precision. All target-overlap durations from the prior final-approach computation reproduce with maximum absolute error **0.000000 ms**.

## 01: time inside / outside an AOI

AOIs are current typed main-column rectangles with nonnegative position, using their strict x and y bounds. Cursor document coordinates are scaled into screenshot coordinates using each trial's geometry. Recorded fixation coordinates already use screenshot page space. Off-AOI means outside all included main-column rectangles: it can include gutters, spaces between results, headers and lateral content. It does not mean off-screen or missing gaze.

A cursor sample is held until the next native mousemove or final press, with a 2,000 ms maximum hold. Longer gaps are unavailable. The logger records the cursor only when it moves, so a cursor left still for more than 2 s counts as unavailable here rather than as a location; the resting-cursor sensitivities in the sequence methods relax this. The held page-space position is not reconstructed across scroll events; this is also the prior readout's convention. Fixation coordinates apply only over the recorded fixation duration. There is no +50 ms matching slack. For overlapping fixations, the latest-starting interval takes precedence. No matched fixation is a separate state; it can include raw gaze between fixations and is not an eye-motion classifier or a claim of tracker failure.

## 02: time above / below the initial fold

The initial fold is page y = window height × screenshot/document y scale, with page-top origin. Above is 0 ≤ y < fold; below is fold ≤ y ≤ page height. Points outside the screenshot bounds are separate, as is unavailable signal time. This is a fixed initial-fold classification. It is not current viewport visibility: below-fold content may be visible after scrolling. The screen-relative coordinate used for motion subtracts the recorded scroll offset, initially zero, held until the next scroll event.

## 03: joint gaze / cursor motion

This view has a separate, explicit denominator. It uses complete, nonoverlapping 100 ms windows within the primary clock; final partial windows (130.125 seconds in total) are omitted. A displacement estimate uses the difference between smoothed endpoint locations divided by 100 ms.

Raw BPOGX/BPOGY samples are page coordinates. At each endpoint, take the median screen-relative x and y among samples within ±20 ms. Samples must be finite, within reconstructed viewport bounds, and have at least one valid pupil flag (LPV or RPV). These are pupil-validity flags, not a provided gaze-validity flag; this is an explicit quality screen. Missing endpoint windows are unclassified. Cursor endpoints interpolate only across gaps ≤250 ms; otherwise hold the previous sample for at most 2 s. Any window containing a scroll event is unclassified, preventing scroll-induced page displacement from being called eye or hand movement.

Operational moving thresholds are **300 screenshot px/s for gaze** and **50 px/s for cursor**. “Still” means below these thresholds, not physiologically motionless. This is neither a saccade detector nor a direct measure of muscular eye movement. The four-cell matrix divides by classifiable motion-window duration, **57.10%** of complete-window time. Unclassified time is stated beside it. Sensitivity views halve and double both thresholds (150/25 and 600/100 px/s). Motion labels must be interpreted with their thresholds.

## 04: together / apart

Both signals must occupy an included AOI at the same instant. Same, adjacent (position difference 1), and other AOI states divide by that classifiable both-in-AOI duration. This differs from the original 33.1/17.4/9.0/40.5 table: that table used cursor-sample weights before the final 500 ms, y-band gaze membership and +50 ms fixation matching. This poster uses exact xy rectangles, exact overlap, the full prepress interval, and explicit missing coverage. The two tables must not be substituted for one another.

## 05: the shared clock through normalized trial time

Each trial is divided into 20 equal-duration bins. The stack shows pooled elapsed-millisecond shares within each bin. Longer trials contribute more time; this is duration-weighted, not an equal-trial average. The full stack includes both-in-AOI identity, only one signal in an AOI, both outside AOIs, and unavailable intervals. Adjacent bin widths represent 5% of a trial's own duration, not a fixed number of seconds. The stack is a descriptive distribution, not a test of a time trend.

## 06: relation to the eventual clicked AOI

The final click must hit one unique main-column AOI, and the associated mousedown must hit that same target. “Both off” in this panel means both signals are off that target; either may be in another result. This is distinct from “both outside all AOIs” in panels 04–05.

The final-approach onset is the last prepress cursor distance-to-click local maximum with ≥50 px subsequent drop and distance ≥100 px. If none exists, use the latest sample at or above that trial's median cursor-to-click distance. This is a geometric rule, not a decision-onset label. Earlier and approach phase bars each divide by their own full elapsed time, including missingness. Their denominator therefore differs from the previous readout's fixation-matched-only 11.7% and 12.2% rates, which are linked below.

## 07–08: observed trial and close-up

Trial p047-b6-t1 is an existing worked example, retained for continuity rather than chosen to typify a population rate. The actual full-page screenshot, current typed boxes, fixation durations, native cursor path, fixed initial fold and final press are shown. Cursor paths join samples only when the gap is ≤250 ms. The last three seconds are bracketed on the main trace and enlarged into target-occupancy and motion strips. Hatched areas represent unavailable classifications. One trace is an example, not evidence of the prevalence of its pattern.

## Uncertainty and reproducibility

Brackets on spatial summaries and error bars on pooled participant summaries are 95% percentile confidence intervals from 2,000 participant-cluster bootstrap resamples, seed 20260927. Resampling preserves each participant's full contribution and recomputes the pooled duration ratio. Raw participant points show between-participant variation. These do not supply causal interpretations or population prevalence outside the cohort. Source hashes, exact aggregate milliseconds, per-trial states, confidence intervals and exports are saved alongside this document.

The motion sensitivity chart reports conditional classifiable-window shares. The main spatial charts report unconditional full-clock shares. Missingness is not redistributed into observed categories. AOI coverage and motion thresholds answer different dependent measures.

## Sources

- [AdSERP dataset and field definitions](https://github.com/kayhan-latifzadeh/AdSERP): BPOG and FPOG screenshot coordinates, fixation durations, pupil flags, native cursor and scroll events.
- Current local typed AOI maps: content hash 2cb789eb8febd234.
- [Prior exact-overlap aggregate](../evidence/final-approach/summary.json) and [cohort / clocks](../evidence/final-approach/trial-summary.csv).
- [Gaze and cursor sequences](../gaze-cursor-echo/).
- [Search process and the two posters](../).
- Reproducible producers in scripts/attention_atlas/: compute-information-space.py (shared rules in atlas_core.py); render-information-space.py; build-information-space-page.py; verify-atlas.py.
