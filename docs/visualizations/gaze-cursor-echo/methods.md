# Measurement notes

## Scope and clocks

Exploratory analysis of the existing poster cohort: 2,650 trials, 47 participants. The clock starts at the first native mousemove and ends at final mousedown. The entire clock is 13.342 hours. No extrapolation is made into cursor or fixation gaps.

AOIs are the strict x/y rectangles of typed main-column results, including ads and widgets. Plot numbering is stored position + 1. Outside AOIs and unavailable location are distinct. Fixation membership applies only over recorded fixation durations, with the latest-starting fixation taking precedence in an overlap. Cursor samples are held in page coordinates until the next sample or up to 2 seconds. The inherited occupancy convention does not reconstruct page-space cursor location during scrolling; motion windows containing scroll are excluded.

## Rest and the worked example

Cursor rest means less than 50 screenshot pixels/second in endpoint displacement over a complete 100-ms window. Cursor endpoints interpolate only across gaps at most 250 ms, otherwise hold up to 2 seconds. This permits small movements and does not detect physiological immobility. A pause is a continuous sequence of such windows in the same AOI; gaps split it. The rest-overlap numerator and four denominator totals exactly reproduce the previously shipped resting-cursor results.

The logger records the cursor only when it moves, so under the 2-second hold a cursor that stays still for longer becomes unavailable rather than resting. Two sensitivities relax the hold. Holding each position until the next mousemove raises the different-AOI share of rest time from 23.8% to 27.6% (95% CI 25.8–29.1%); also moving the held page position with the scroll offset gives 25.0% (23.4–26.4%). The primary estimate is the conservative one.

Example selection: take pauses lasting 2–8 seconds, with at least three gaze AOIs, one return in the gaze sequence, and at least 60% gaze-in-AOI coverage. Choose the pause closest to 4 seconds; tie-break by trial ID and then onset. There are 63 candidates. The selected trial is p021-b1-t6, interval 4.4–8.4 seconds after first mousemove. This is an illustration, not a representative-trial claim: of 1,843 cursor pauses of 2–8 seconds, 10.7% contain three or more gaze AOIs and a return. No matched fixation occupies the gaps; it is not interpreted as gaze outside results.

## Visits and rank changes

For each signal, contiguous same-AOI occupancy segments form a visit. Same-AOI segments separated by at most 100 ms can merge if no other AOI intervenes. The primary minimum visit duration is 100 ms of observed occupancy; bridged gaps do not count toward that duration. Zero- and 200-ms minima provide sensitivity checks. Plotted traces retain every exact segment, including visits below the analytical threshold.

An AOI change requires successive qualifying visits to different AOIs, separated by at most 500 ms. Larger gaps break the chain. A backward step moves to a smaller position. A direction reversal changes the sign of successive rank changes; repeated occupancy of the same AOI does not reset the previous direction. It is a geometric sequence measure, not a cognitive-state label.

The rate chart intersects fixation coverage and cursor coverage first, then applies the same visit definition to both channels. Rates divide by the resulting 6.068 hours of common covered time. These intervals need not put either signal inside an AOI. Fixation gaps still fragment observations and the modalities have different native sampling, so the rates describe recorded AOI changes rather than a physiological movement-frequency ratio.

## First arrivals

For each trial–AOI visited by both channels, compare the first qualifying visit onset. Lag equals cursor onset minus gaze onset, in milliseconds. Positive means gaze entered first. No temporal matching window is used. Only jointly visited AOIs enter this distribution; the primary cohort contains 8,175 such pairs, 7,762 gaze-only trial–AOIs, and 1,046 cursor-only trial–AOIs.

A result occupied at the first-mousemove boundary may have been reached earlier. Excluding every pair where either first onset is exactly at that boundary is a sensitivity analysis, not a recovery of the true trial-onset order. Histogram tails outside ±10 seconds are included in the outer bins; the bin beginning at zero also includes exact ties. The separate three-way first-entry bar reports ties explicitly.

## Nearby visit pairs

Use all qualifying visits, including returns. Match same-AOI visits monotonically and one-to-one, with absolute onset differences no greater than the chosen window. Dynamic programming maximizes the number of pairs, then minimizes summed absolute onset differences. The primary window is ±2 seconds; ±0.5, ±1 and ±5 seconds show sensitivity. Matching never reuses a visit or crosses visit order. Both-return summaries further require that each matched visit has an earlier visit to that same AOI in its own channel.

Every trial's first cursor visit starts at the first mousemove, the origin of the clock. Pairs that start there are ties or favour the cursor, which pulls the gaze-first share toward 50%. Ties are 4.4% of all pairs; without pairs at the clock origin, gaze arrives first in 55.3% (95% CI 53.2–57.1%) and the median difference is +0.049 s.

This selection favors nearby onsets and can pair different physical excursions to a revisited AOI. A median near zero within matched visits does not establish that all cursor movements are synchronous or that gaze never leads. Unmatched visits remain in the chart and data. A more causal follower model would require an independently specified correspondence rule and validation against suitable within-trial controls.

## Uncertainty and reproducibility

95% confidence intervals use 2,000 participant-cluster bootstrap resamples, seed 20260929 (the reused rest estimate uses seed 20260927). Participant resampling retains all visits and durations for each selected participant. Pooled event proportions, pooled duration proportions, medians and per-minute rates have different denominators and are labeled separately. The reported IQR describes the lag distribution, not uncertainty in its median.

Five exact reproduction gates pass with zero millisecond discrepancy against the resting-cursor summary. Semantic tests cover visit-gap merging, an intervening different AOI, directional reversals across repeated same-AOI occupancy, and bounded one-to-one sequence matching (checked against exhaustive search). All generated pairs were checked for AOI equality, unique use, temporal bounds and monotone order. Producers: scripts/attention_atlas/compute-gaze-cursor-echo.py and check-gaze-cursor-echo.py. Source hashes, aggregate results, per-trial traces and sensitivities are stored beside the visual.
