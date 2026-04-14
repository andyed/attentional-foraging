# Approach-threshold sensitivity sweep — NB22 four-class taxonomy

**Question.** The canonical NB22 `approached` flag is `min_dist < 100 px`.
How much does the deferred-vs-evaluated-rejected motor-signature dissociation
depend on that single tuning point?

**Method.** Sweep `approach_threshold` over {50, 75, 100, 125, 150, 200} px,
holding the per-record regression labels (NB22 cell 5 algorithm) and motor
features (K5 retreat_dist, K6 total_dwell_ms, K7 dwell_in_proximity_ms) fixed.

**Note.** K7 proximity dwell is computed against a 100 px proximity radius
baked into `cursor-approach-features.json` at NB15 compute time. The K7 sweep
therefore reflects only the re-labeling of records into deferred/rejected sets
at each approach threshold, not a re-computation of proximity at that threshold.
A full K7 sweep would require regenerating cursor-approach-features.json at
each proximity radius and is out of scope.

| Threshold (px) | N deferred | N eval-rej | N clicked | N not-approached | K5 def / rej (px) | K5 *p* | K6 def / rej (ms) | K6 *p* | K7 def / rej (ms) | K7 *p* |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 | 771 | 143 | 2228 | 10277 | 243.3 / 121.8 | 7.70e-13 | 4619 / 2243 | 6.81e-19 | 1668 / 964 | 2.56e-06 |
| 75 | 1363 | 272 | 2228 | 9556 | 239.8 / 119.2 | 1.71e-21 | 4382 / 1898 | 5.48e-42 | 1416 / 833 | 3.22e-09 |
| 100 | 1916 | 439 | 2228 | 8836 | 234.5 / 90.8 | 1.76e-38 | 4137 / 1612 | 9.76e-70 | 1212 / 690 | 1.36e-16 |
| 125 | 2476 | 612 | 2228 | 8103 | 230.2 / 81.6 | 1.54e-52 | 3897 / 1528 | 1.18e-96 | 1049 / 588 | 2.36e-22 |
| 150 | 2970 | 780 | 2228 | 7441 | 224.4 / 74.3 | 4.87e-68 | 3646 / 1390 | 1.61e-123 | 923 / 508 | 2.37e-28 |
| 200 | 3798 | 1130 | 2228 | 6263 | 216.0 / 63.8 | 9.16e-98 | 3320 / 1275 | 2.20e-163 | 757 / 390 | 2.88e-38 |

