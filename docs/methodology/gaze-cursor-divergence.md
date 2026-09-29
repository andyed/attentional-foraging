# Gaze–cursor divergence on the cursor-only typed stream

**Stable ID:** M:gaze-cursor-divergence
**Status:** current as of 2026-09-13; canonical implementation: `scripts/gaze_cursor_divergence.py`

Full-corpus result. Regime `[LAB, AdSERP, typed]`.
Producer `scripts/gaze_cursor_divergence.py` → `scripts/output/gaze_cursor_divergence/summary.json`
(the summary is tracked; per-trial intermediates stay under the output policy).

## Question

Prior gaze–cursor work (Rodden 2008; Huang, White & Buscher 2012;
Navalpakkam 2013; Liebling & Dumais 2014) models the moments when cursor and
gaze part company as noise in a gaze proxy. This producer measures three
things the per-result construction lets us say about divergence instead:
where the cursor is when it is on no result, whether inter-result whitespace
time is a reading pointer or a place-keeper, and what the cursor carries
beyond dwell time on the click and the deferred targets.

## Protocol

- Typed main-axis AOIs, screenshot space via the per-trial ratios; native
  `mousemove` samples with `t < mousedown(final click) − 500 ms`; strict x+y
  click containment. 2,650 trials scanned; the modelled rows are joined to the
  canonical buf500 feature cache by (trial, position) and are exactly the
  paper's **34,328 rows / 2,608 trials / 47 participants** (hash-checked
  against the canonical sidecar).
- Each sample owns the interval to the next sample. *Uncapped* answers "where
  was the cursor"; *capped at 2 s* (the dwell accumulator's rule) answers
  "where was it while moving".
- Gaze enters only to locate the fixation containing a cursor sample
  (coupling descriptives), to set the fifth-fixation boundary (timing split),
  and as the NB22 deferred label (target only). No gaze quantity is a feature.
- All AUCs are 47-fold LOSO balanced logistic regression with per-fold
  StandardScaler; dwell-type scratch features enter as log1p, the M4-7
  features enter raw as in the paper.

## 1. Parking regime: 37 % of pre-press cursor time is on no result

| Location (time-weighted, uncapped) | Share |
|---|---:|
| Inside a main-axis AOI | 62.9 % |
| Right gutter beside a result | 16.4 % |
| Whitespace between results | 12.4 % |
| Left gutter beside a result | 6.1 % |
| Above first / below last | 2.1 % / 0.1 % |

Per-trial off-box share: median 22 %, IQR [6 %, 67 %]. Participant medians
run 1 %–94 %; **38 % of the variance is between participants** (Rodden's
"inactive cursor" pattern is a partial trait, mostly per-trial state).

**Parking does not dilute the per-result signal.** In-box dwell click AUC by
trial tercile of off-box share: low 0.864, mid 0.854, high 0.862.
Beside-box (gutter) dwell alone is 0.544; added to in-box dwell it moves
0.854 → 0.862. The paper's 1-D vertical-band dwell (0.848) is slightly below
strict 2-D containment (0.854) because it counts gutter time as on-AOI.
7.1 % of clicked AOIs had zero in-box dwell before the cutoff.

## 2. Whitespace: a reading pointer, not a place-keeper (null, NB19-shaped)

- Gap episodes are short by count (median 83 ms, n = 9,781) but the time mass
  is rests: 77 % of gap time is in episodes > 1 s, 55 % > 3 s; 77 % of it is
  inside the column x-range; its share rises from 5.8 % of cursor time before
  the fifth fixation to 13.0 % after.
- Cursor tracks gaze vertically as well in the gap as in a box
  (Pearson r = 0.917 vs 0.914; median gaze − cursor ≈ 0 px). While the cursor
  is in gap(k, k+1), gaze is on k 18 %, on k+1 17 %, another result 22 %, off
  every result 44 %. While the cursor is inside box k: on k 33 %, adjacent
  17 %, other 9 %, off 40 %.
- **Gap-adjacent dwell** (time in the gaps bordering AOI k, split half to each
  neighbour) predicts the click alone at 0.747 but adds nothing to M4-7:
  paired participant ΔAUC −0.0001 [−0.0002, +0.0001] for click and
  −0.0002 [−0.0004, +0.0000] for deferred. The 1-D distance terms already
  encode "resting just above or below k".

## 3. Beyond dwell time

| Feature set | Click | Deferred vs evaluated-rejected |
|---|---:|---:|
| `dwell_in_proximity_ms` only | 0.853 | 0.593 |
| `min_dist` only | 0.872 | 0.581 |
| `mean_dist` only | 0.872 | 0.665 |
| `mean_approach_velocity` only | 0.615 | 0.553 |
| `direction_changes` only | 0.509 | 0.505 |
| dwell + `mean_dist` | 0.884 | 0.682 |
| M4-7 minus dwell | 0.932 | 0.672 |
| M4-7 | 0.935 | 0.680 |

Deferred pool: 9,269 approached (`min_dist < 100 px`) non-click rows,
deferred rate 0.734. For the click, everything beyond dwell is worth +0.08
and is distance geometry plus approach velocity. For the deferred split,
dwell is near chance and **mean distance carries the class on its own**;
dropping dwell from the vector costs 0.003 on click and 0.008 on deferred.
This is the cursor-side signature of the divergence NB22 measures as drift
(deferred 202 px vs evaluated-rejected 53 px): the cursor moves on, the eyes
come back.

## Claim boundary

- Descriptive shares use 2,650 scanned trials; every AUC uses the paper's
  joined 34,328 rows. Populations are stated per number.
- Gaze coupling percentages depend on the 50 ms post-fixation slack and on
  band (y-only) containment for gaze; they are descriptive, not a proxy
  benchmark.
- Nothing here identifies a cognitive mechanism. "Reading pointer" names the
  measured coupling (r = 0.917), not an intention.
- Huang, White & Dumais 2011 could report hovered-but-not-clicked; the
  deferred/rejected split needs the gaze-return label to define and mean
  distance, not dwell, to recover. That is the "beyond dwell time" claim, and
  it is bounded at 0.68 AUC (gaze-gated ceiling on the same rows: 0.715).

## Reproduction

```bash
.venv/bin/python scripts/gaze_cursor_divergence.py
```

The summary records the producer hash, substrate stamp, feature-cache record
hash (checked against `m4_cursor_aoi_mousedown/summary.json`), label-cache
and label-row hashes, and the data-loader hash.
