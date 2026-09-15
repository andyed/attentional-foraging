# Before a major saccade — ambient timing, target selection, and whether the periphery is accessed

**Tags:** `[LAB, AdSERP, typed]` · first-entry moves between results · 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`) · boundary-CM kernel ungated for intake, hard gate for "any intake"
**Producer:** `scripts/major_saccade_selection.py` → `scripts/output/major_saccade_selection/summary.json` (promoted 2026-09-15 from the inline analyses of 2026-09-14; the producer's numbers below supersede the inline ones, which differed by at most 6 ms, 0.5 px and 0.02 in selection rates from a slightly different on-screen candidate set). Inputs: typed bands, fixations by the label producer's rule, the primary census states for on-screen candidates (any viewport residence)
**Hypothesis (Andy):** peripheral access is more likely *preceding* major saccades than minor ones. Three signatures were tested.

## 1. Landing precision does not depend on amplitude, and prior intake does not buy it

15,625 first entries onto a result from a fixation on another result. Median landing offset from the band centre: 37.5 px (minor, < 100 px), 33.5 (100–300), 37.5 (300–600), 38.5 (> 600); as a fraction of band height 0.30–0.38 throughout. Within major saccades, Spearman between prior 1 s intake on the target and offset is +0.059 (300–600, p 0.001) and +0.010 (> 600, n.s.). Prior peripheral intake does not sharpen the landing of a long jump.

## 2. The fixation before a major saccade is shorter — the ambient-mode signature

Median duration of the preceding fixation: 200 ms before minor saccades, 200 before 100–300 px, 174 before 300–600, **154 before > 600 px**. Per participant the major-minus-minor difference is −23 ms and negative in **38 of 47**. Short fixation, long saccade is the ambient mode of Unema, Pannasch and colleagues, the mode associated with peripheral, layout-driven scanning; long fixation, short saccade is focal mode. The survey phase is ambient and the evaluate phase is focal, and the preceding-fixation duration tracks the amplitude of what follows.

**Forward only.** The figure `scripts/output/figures/result_moves.png` (panel c;
`scripts/render_result_moves.py`, all 57,706 moves between results) shows the
timing signature is a property of *forward* moves: the fixation before a forward
jump shortens from 193 ms (< 100 px) to 140 ms (> 600 px), while the fixation
before a backward move stays at 172–194 ms at every amplitude. Long returns are
not preceded by an ambient fixation, which is what memory-guided returns predict
and what `return_is_memory.md` found from the other side. The transition matrix
(panel a) shows the same asymmetry in where moves go: 79 % of moves from rank 1
go to rank 2, and back moves from deep ranks spread over several targets.

## 3. Where a major saccade goes — recency, and the kernel is inert

For each first-entry move from result q to result p, candidates = on-screen results not yet fixated. Was the landed result the top candidate by (a) near-peripheral intake over the prior window, (b) plain closeness to *any* fixation in the window, (c) closeness to the preceding fixation alone? Chance ≈ 0.17.

| amplitude | P(target = nearest to the preceding fixation) | P(target = top intake, 1 s) | P(target = closest to any fixation, 1 s) |
|---|---|---|---|
| minor < 100 px | 0.973 | 0.943 | 0.950 |
| 100–300 px | 0.819 | 0.802 | 0.801 |
| major 300–600 px | 0.550 | 0.550 | 0.548 |
| major > 600 px | 0.240 | 0.249 | 0.251 |

Across windows of 0.5, 1, 2 and 4 s, intake and recency-proximity agree within 0.003 in every cell (major saccades, ≥ 3 candidates: 0.545 / 0.543 at 0.5 s, 0.499 / 0.498 at 1 s, 0.481 / 0.478 at 2 s, 0.471 / 0.468 at 4 s; n 2,413–3,127). Far jumps land on the nearest candidate a quarter of the time, 1.5× chance; "top intake and not nearest" is 1.3 % for minor and 1.7 % for > 600 px moves (the inline analysis had reported a rise to 10.7 %, which the producer does not reproduce; the sentence is withdrawn). The intake ranking never beats "closest to any recent fixation": the kernel adds nothing, as in `pai_kernel_validation.md`.

## Reading

- **The timing signature is real.** Major saccades follow shorter fixations, in 38 of 47 participants. That is ambient mode, and it is consistent with the periphery being consulted before a long jump.
- **What the jump uses is recency, not a kernel.** Far targets are results the eyes were near within the last second or two, more often than chance. Whether that is peripheral sampling at the time or short-term spatial memory of where the eyes just were cannot be separated by intake, because every intake measure reduces to recency-proximity here.
- **Precision is not the channel.** Long jumps land as accurately as short ones and prior intake does not improve them, which matches the return-mechanism result: landing is memory-guided.

Net: "peripheral access precedes major saccades" survives as a mode statement (ambient timing, recently-near targets) and not as a kernel statement. The observable that carries it is the preceding fixation's duration and the target's recency, not any distance-weighted mass.

## Caveats

- First-entry moves only; returns are in `return_is_memory.md`.
- Each window in §3 is computed on the moves with that much history, so the longer windows select later-trial moves.
- Candidates are results with any viewport residence in the trial (census states other than never/brief on screen), not residence at the moment of the saccade; a time-resolved on-screen set would be stricter. Moves whose preceding fixation was off the result column are excluded by default (`--allow-prev-off-column` keeps them: 17,238 moves, same medians within 6 ms).
