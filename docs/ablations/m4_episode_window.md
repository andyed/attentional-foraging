# M4 cursor features cropped to per-AOI proximity episodes

**Tags:** `[LAB, AdSERP, typed]` · cursor-only, no gaze · press-anchored (`mousedown`), 500 ms buffer · LOSO by participant (47 folds)
**Producer:** `scripts/m4_episode_window.py` → `scripts/output/m4_episode_window/summary.json`. It drives the canonical producer `scripts/m4_cursor_aoi_rerun.py` three times, changing only `--window` (`all`, `episode`, `episode-pad`). The per-window producer summaries are under `scripts/output/m4_episode_window/runs/`. Generated 2026-10-14.
**Question:** The rewritten Introduction says the model captures "per-result AOI deliberation episodes, the contiguous interval during which attention and interaction are focused on a single result". The reported extractor (§3.2, §4.1) does no enter/exit segmentation. Does click prediction survive when each AOI's features are computed only from that AOI's own proximity episodes?

## Episode definition

For each AOI, after the press buffer has removed every sample at t ≥ mousedown − 500 ms:

- d_t = |pageY_t − AOI center y| in document CSS px. This is the vertical distance and the 100 px zone that §3.2 uses for its overlap statistics, and the zone that `dwell_in_proximity_ms` already uses.
- An **episode** is a maximal run of consecutive retained `mousemove` samples with d_t < 100 px. The inequality is strict, matching the tracker's dwell test.
- **episode**: only in-episode samples are fed to that AOI's `ResultFeatureTracker`.
- **episode-pad**: each run is extended by 500 ms on both sides, so the approach into the zone and the exit from it are kept. Padded runs that touch are merged.
- Each AOI is cropped independently. A sample can belong to several AOIs' episodes, which matches the multi-observer regime in §3.2.

Rows, labels and folds are the headline population: 2,608 trials and 34,328 rows. The record-key-and-label hash matches `scripts/output/m4_cursor_aoi_mousedown/summary.json`, and the driver refuses to write if it does not. Row inclusion needs two samples before the 1,000 ms cutoff, so the driver runs the full buffer grid (0, 250, 500, 1000 ms) and scores only the 500 ms condition.

## Empty rows

A row is **empty** when its AOI has no retained sample within 100 px of its center. An empty row is fed nothing, and the tracker returns its empty-state vector: every feature is 0, including `min_dist = 0` and `mean_dist = 0`. Nothing is imputed. Note that `min_dist = 0` is the value a cursor resting on the center would produce, so the empty state is not "far away". The logistic model has to learn that from the other zeros. A zone-entry control below shows how much of the result that indicator carries on its own.

| | rows | empty rows | share empty | rows with one kept sample | share of window samples kept |
|---|---|---|---|---|---|
| all | 34,328 | 21,936 | 63.9 % | 1,210 | 6.9 % |
| clicked | 2,608 | 146 | 5.6 % | 13 | 32.0 % |
| not clicked | 31,720 | 21,790 | 68.7 % | 1,197 | 4.8 % |

Empty rows are the same set under both crops: a padded episode exists exactly when an unpadded one does. With the pad, 11.7 % of window samples are kept overall, 46 % for clicked rows and 8.8 % for non-clicked rows. Rows with one kept sample drop to 610.

Among non-empty rows:

| | kept samples, median [IQR] | episodes per row, median [IQR] |
|---|---|---|
| clicked, episode | 47 [24, 91] | 2 [1, 2] |
| not clicked, episode | 15 [4, 40] | 1 [1, 2] |
| clicked, episode-pad | 70 [41, 127] | 2 [1, 2] |
| not clicked, episode-pad | 38 [11, 75] | 1 [1, 2] |

There are 20,283 episodes in total: 4,807 on clicked AOIs and 15,476 on the rest. For 146 clicked AOIs, 5.6 % of trials, the cursor never came within 100 px of the clicked result's center before the buffer.

## Results

Same rows, labels and folds for every line. M1 (rank position alone) is the reference floor.

| window | features | pooled AUC | participant median AUC [IQR] | MRR@10 | NDCG@1 |
|---|---|---|---|---|---|
| — | M1 position | 0.792 | 0.801 [0.751, 0.836] | 0.447 | 0.198 |
| whole | M4-7 | **0.935** | 0.939 [0.923, 0.955] | 0.777 | 0.634 |
| episode | M4-7 | **0.873** | 0.890 [0.872, 0.913] | 0.679 | 0.479 |
| episode-pad | M4-7 | **0.887** | 0.899 [0.880, 0.925] | 0.720 | 0.538 |
| whole | M3 = M4-7 + position | 0.935 | 0.939 | 0.775 | 0.630 |
| episode | M3 | 0.899 | 0.909 | 0.651 | 0.436 |
| episode-pad | M3 | 0.915 | 0.919 | 0.702 | 0.511 |

Position adds nothing to whole-stream features but adds about 0.03 pooled AUC to cropped features. Some of the rank information in the whole stream sits outside the episodes.

Paired comparison of participant fold AUCs. Each line uses 47 participants and 10,000 bootstrap resamples.

| comparison | mean Δ AUC | 95 % CI | Wilcoxon p |
|---|---|---|---|
| episode M4-7 − whole M4-7 | **−0.048** | **[−0.054, −0.041]** | 3e−14 |
| episode-pad M4-7 − whole M4-7 | −0.037 | [−0.045, −0.030] | 1e−13 |
| episode M4-7 − M1 position | +0.090 | [+0.074, +0.107] | 2e−12 |
| episode-pad M4-7 − M1 position | +0.101 | [+0.083, +0.118] | 3e−12 |

### Single-feature sweep

Each feature is fitted alone, on the same rows.

| feature | whole AUC | episode AUC | episode-pad AUC | whole MRR@10 | episode MRR@10 |
|---|---|---|---|---|---|
| min_dist | 0.872 | 0.710 | 0.710 | 0.624 | 0.450 |
| mean_dist | 0.872 | 0.789 | 0.774 | 0.589 | 0.467 |
| dwell_in_proximity_ms | 0.853 | 0.866 | 0.864 | 0.639 | 0.653 |
| mean_approach_velocity | 0.615 | 0.756 | 0.777 | 0.588 | 0.607 |
| max_approach_velocity | 0.549 | 0.844 | 0.829 | 0.533 | 0.619 |
| direction_changes | 0.509 | 0.843 | 0.842 | 0.555 | 0.662 |
| frac_decreasing | 0.579 | 0.846 | 0.856 | 0.581 | 0.605 |

`min_dist` and `mean_dist` no longer carry the signal. Under the crop, `min_dist` equals the whole-stream value when that value is under 100 px and 0 otherwise, so the feature is no longer monotone in closeness. The dynamics features look strong under the crop, but that is mostly the empty state: they are 0 for empty rows and nonzero otherwise, so they act as zone-entry flags and episode-length counters. `dwell_in_proximity_ms` is unchanged by construction, because it only ever counted in-zone time.

### Zone-entry control

`in_zone` = 1 when the AOI has at least one in-episode sample. This is the same as whole-stream `min_dist < 100 px`, and the driver checks that.

| model | pooled AUC | participant median AUC | MRR@10 | NDCG@1 |
|---|---|---|---|---|
| in_zone alone | 0.777 | 0.823 | 0.492 | 0.239 |
| position + in_zone | 0.855 | 0.865 | 0.492 | 0.239 |
| episode M4-7 + in_zone | 0.879 | 0.897 | 0.691 | 0.495 |
| episode-pad M4-7 + in_zone | 0.896 | 0.913 | 0.737 | 0.564 |

Episode M4-7 beats in_zone alone by +0.073 participant AUC, CI [+0.061, +0.085]. Whole M4-7 beats it by +0.120, CI [+0.109, +0.132]. Whole M4-7 beats position + in_zone by +0.079, CI [+0.070, +0.087].

### Non-empty subset: what the episode itself carries

This subset keeps trials whose clicked AOI had an episode, keeps rows with an episode, and drops trials left with fewer than two rows. That leaves 2,302 trials and 11,831 rows across 47 participants. Zone entry is constant here, so only the motion inside the episodes can separate the rows.

| features on the same rows | pooled AUC | participant median AUC | MRR@10 | NDCG@1 |
|---|---|---|---|---|
| M1 position | 0.578 | 0.550 | 0.469 | 0.199 |
| whole M4-7 | 0.834 | 0.832 | 0.793 | 0.655 |
| episode M4-7 | 0.740 | 0.752 | 0.694 | 0.491 |
| episode-pad M4-7 | 0.802 | 0.809 | 0.745 | 0.566 |

| comparison on the subset | mean Δ AUC | 95 % CI | Wilcoxon p |
|---|---|---|---|
| episode − whole | −0.082 | [−0.095, −0.070] | 1e−13 |
| episode-pad − whole | −0.022 | [−0.032, −0.013] | 5e−05 |

Single features inside the episodes on this subset: `mean_approach_velocity` 0.733, `direction_changes` 0.695, `dwell_in_proximity_ms` 0.684, `frac_decreasing` 0.662, `max_approach_velocity` 0.653, `min_dist` 0.642, `mean_dist` 0.572.

## Caveats

- **The episode is proximity on one axis, not attention.** The 100 px band on vertical distance is the paper's descriptive zone. Gaze is not used, so "focused attention" is not measured here. The episodes are cursor proximity intervals only.
- **The empty state is a modelling choice.** A different empty-row encoding, such as a missingness flag or a large-distance sentinel, would change the cropped `min_dist` and `mean_dist` numbers. The zone-entry control bounds this: adding an explicit `in_zone` flag moves episode M4-7 from 0.873 to 0.879.
- **Reproduction drift.** The whole-stream run reproduces the committed headline's rows and labels exactly (same record-key hash). Its pooled AUC is 0.9347 against the committed 0.9348, and its per-record feature hash differs. The tracker file (`approach-retreat` commit 6703ce3, 2026-09-18) and `notebooks-v2/data_loader.py` (2026-09-26) both changed after the 2026-09-06 headline run. Both values round to the paper's 0.935.
- The 500 ms pad is one choice. It was not tuned.

## Reading

The Introduction's claim that the model captures per-result deliberation episodes, and that the signal lives in those episodes, is **softened, not supported as written**. Cropping every AOI's features to its own 100 px proximity episodes keeps click prediction well above rank position: pooled AUC 0.873 against 0.792. But it costs a paired **−0.048 participant AUC against the whole-stream window (95 % CI [−0.054, −0.041], 47 participants)**, and −0.037 [−0.045, −0.030] with a 500 ms pad. Much of what survives is whether the cursor entered the AOI's zone at all, which alone scores 0.777. On rows where the zone was entered, in-episode motion scores 0.740 against 0.834 for whole-stream features on the same rows. The headline 0.935 therefore depends on cursor motion outside each result's episode, chiefly the approach into the zone, which the pad partly recovers, and distance to results the cursor never reached. The extractor is also not episode-segmented (§3.2). The Introduction should describe the representation as per-result observers that track cursor motion relative to every result across the trial. It can then say that the signal is concentrated in, but not confined to, the intervals when the cursor is near that result. Calling the unit a contiguous deliberation episode would describe a segmentation the reported model does not perform, and that this ablation shows loses about a third of the participant-level gain over position: 0.048 of the whole stream's +0.138 (95 % CI [+0.124, +0.151]).

Rerun:

```bash
.venv/bin/python scripts/m4_episode_window.py
```
