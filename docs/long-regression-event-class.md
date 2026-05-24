# Long organic regressions are a distinct event class

**Date:** 2026-05-24
**Stable ID:** F:long-regression-event-class
**Source:** `scripts/dd_top_regression_event_signals.py` → `scripts/output/dd_top_regression_event_signals/{events.jsonl, summary.json}`
**Companion to:** [`null-findings/2026-05-24-long-regression-rate-not-trait.md`](./null-findings/2026-05-24-long-regression-rate-not-trait.md) — the null on the per-participant signature. The event-level finding stands; the per-participant trait doesn't.

---

## TL;DR

Per-event signal extraction across **5,738 organic→organic regression events** in the dd_top-topped substrate (1,581 trials) shows that **long regressions (|delta| ≥ 4 positions) are quantitatively distinct from short ones (|delta| ∈ {1, 2}) on saccade geometry and cursor-eye sync** — even though [the *mix* of long vs short is not a per-participant trait](./null-findings/2026-05-24-long-regression-rate-not-trait.md). Long regressions are near-pure vertical saccades, ~7.5× longer in magnitude, with the cursor ~100 px further from gaze at landing. LF/HF is too sparse per-event to discriminate confidently.

---

## §1 Headline contrasts (medians, permutation p two-sided)

| Signal | Short (1–2) | Long (≥ 4) | long − short | p |
|---|---:|---:|---:|---:|
| `saccade_mag` (px) | 115.3 | 674.4 | **+559 [536, 596]** | <0.001 |
| `saccade_dy_abs` (px) | 88.0 | 659.0 | **+571 [542, 591]** | <0.001 |
| `saccade_dx_abs` (px) | 35.0 | 75.0 | +40 [23, 56] | <0.001 |
| `saccade_horiz_frac` | 0.296 | 0.103 | **−0.19 [−0.22, −0.17]** | <0.001 |
| `cursor_eye_offset` (px) | 380.4 | 483.2 | **+103 [62, 149]** | <0.001 |
| `dest_fix_duration_ms` | 174 | 167 | −7 [−20, +13] | 0.43 |
| `lfhf_src` | 19.5 | 12.6 | −6.8 [−8.7, +2.7] | 0.09 |
| `lfhf_dst` | 19.3 | 21.9 | +2.6 [−2.6, +10.2] | 0.29 |
| `lfhf_delta` | +0.6 | +15.8 | +15.2 [−5.8, +26.9] | 0.04 |

n short = 5,159; n long = 305; n mid (|delta|=3) = 274. LF/HF rows use the subset of events where both source-position and destination-position had ≥ 80 valid pupil samples for the Welch window (1,156 short / 20 long for `lfhf_delta`).

---

## §2 The saccade-geometry signature

The vertical component does essentially all the work. From short to long regressions:

- Horizontal jump grows modestly: 35 → 75 px (~2×)
- **Vertical jump grows 7.5×**: 88 → 659 px
- Horizontal share of the saccade drops from 30% to 10%

Long regressions are *near-pure vertical re-fixations* — gaze drops directly up the page to a much earlier organic result, with minimal lateral excursion. Short regressions retain substantial horizontal component (~30%), consistent with intra-line scanning or adjacent-line jitter. The horizontal axis is where you do *reading*; the vertical axis is where you do *navigation*.

This is the cleanest empirical handle on the population-level forward/regression asymmetry from the Markov substrate (forward jumps cap at 7 positions; regressions reach 9). It's not just that long jumps exist asymmetrically — they have a different *visual signature*.

---

## §3 Cursor-eye desync grows with regression size

The destination fixation lands at a gaze coordinate that's **103 px further from the cursor** for long vs short regressions (CI [62, 149]). The cursor is on average 380 px from gaze during short regressions, 483 px during long ones.

Consistent with: gaze decides first, cursor catches up. Long regressions are gaze-initiated re-evaluations where the eyes leap to a remembered earlier result faster than the cursor can track — the cursor stays "behind" the decision. Short regressions are smaller corrections where cursor and gaze move closer together in time.

This is a candidate signature of *cognitive re-commitment vs continuous scanning* expressed in the cursor-gaze coupling — the same kind of dissociation Stone & Chapman (2023) flag as a UX-friction marker.

---

## §4 LF/HF: signal exists, sample size doesn't

The per-position Butterworth LF/HF (the per-fixation-window dataset doesn't exist in this corpus) requires ≥ 80 valid pupil samples in the position window. That's a severe filter for long regressions, where source and destination positions are each individually rarely visited long enough. Only 20 long regression events have both ends valid for `lfhf_delta`.

What the n = 20 fragment suggests:
- `lfhf_delta`: short events show a near-zero change in load on landing (median +0.6); long events show **+15.8** (p = 0.04, but n_long = 20 — fragile).
- `lfhf_src` trends *lower* for long regressions (12.6 vs 19.5, p = 0.09), suggesting users were operating at modestly lower load *before* the long regression.

Read with appropriate skepticism: long regressions *may* be associated with a "load spike on landing" pattern (which would fit a commit-evaluation interpretation — they re-fixate the target and effort jumps), but the per-event sample is too small to claim it. A re-analysis on the broader corpus (not just dd_top-topped) would multiply n by ~1.75; still not enough for confidence at p ≈ 0.04.

---

## §5 Dest fixation duration is invariant

Both short and long regressions land for ~170 ms (medians within 4% of each other, p = 0.43). **The difference between the two event classes is in what got the eyes there, not how long they stay.** The landing fixation reads/inspects the target similarly regardless of how far the user just jumped.

This rules out a simple "longer-distance jumps land for longer to re-orient" story — the cognitive work appears to happen in the saccade-planning phase, not the post-landing inspection.

---

## §6 What this means together with the null

[The null on `long_regression_rate`](./null-findings/2026-05-24-long-regression-rate-not-trait.md) says participants don't differ in their *preference* for long vs short regressions; the mix is task-structural. **This finding says the long regressions themselves are event-class distinct.** Both can be true:

- Across participants: the regression-size mix is invariant (everyone draws from roughly the same size distribution)
- Across events: short vs long differ on saccade geometry, cursor-eye sync, and (weakly) LF/HF dynamics

The natural read is that long regressions are **task-state events** (something about a specific SERP × time-in-trial state triggers them) rather than **participant-state events** (a stable individual difference). When the task elicits a commit-jump, every participant produces the same signature. They just differ in how often the task elicits one.

This generalizes the chattiness/regression-distribution pattern: **rate is per-participant; event signature is per-event.** Useful for the task model — long regressions can be modeled as a within-trial state without needing a participant-level latent.

**Mechanism note (added 2026-05-24): not dwell-anchored.** A follow-up test ([`null-findings/2026-05-24-long-regression-rate-not-trait.md` addendum](./null-findings/2026-05-24-long-regression-rate-not-trait.md#addendum-2026-05-24-forward-dwell-does-not-predict-regression-distance)) shows that the destination's prior forward-scan dwell does **not** predict regression distance (ρ = +0.004, n = 5,738). Combined with the near-pure-vertical saccade signature here, long regressions are **position-as-landmark** events (eyes navigate to a remembered page location), not **dwell-as-anchor** events (returning to a deliberated candidate). The destination is "back up there somewhere," not "back to that specific candidate I was considering."

---

## §7 Implications

- **For the task model**: long regression as a discrete within-trial transition with characteristic kinematics (near-vertical saccade + transient cursor desync) is a clean predicted event-class for a state-based model. It doesn't need a "long-jumper" participant cluster.
- **For prior elicitation**: the gaze-saccade signature differs from the click signature. A user can be a low-ad-clicker but a high-vertical-leaper; these are different observation windows on the same cursor-gaze stream.
- **For the AllSERP arxiv update**: this complements the cell-promiscuity finding. CIKM headline = per-AOI labels at result level. arxiv += two within-event characterizations (cell sub-bbox engagement; long-regression saccade geometry) that the v1.0.0 substrate doesn't expose.

---

## §8 Limitations

- LF/HF per-event analysis underpowered (n_long = 20 with both-end valid pupil windows). The geometry and cursor-eye sync findings are robust (n_long = 305 for full-coverage signals).
- Only dd_top-topped substrate. A pooled analysis across dd_right-topped + organic-only trials would 2× the n but mix different scan geometries.
- Population-level effects; no per-participant random effect partialled out. The within-participant variance is presumably substantial; the population-median contrast is what's reported.
- Cursor-eye offset is computed at fixation start time, not throughout the fixation. A within-fixation cursor trajectory analysis would resolve when during the fixation the cursor "catches up."

---

## §9 Files

- `scripts/dd_top_regression_event_signals.py` — extractor + analysis driver
- `scripts/output/dd_top_regression_event_signals/events.jsonl` — 5,738 per-event records with all signals
- `scripts/output/dd_top_regression_event_signals/summary.json` — per-group summaries + permutation tests
