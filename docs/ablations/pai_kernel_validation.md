# What the corpus says back to PAI — kernel validation against later fixation

**Tags:** `[LAB, AdSERP, typed]` · 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`) · survey = first 5 fixations (NB13)
**Producer:** `scripts/pai_kernel_validation.py` → `scripts/output/pai_kernel_validation/summary.json`
**Generated:** 2026-09-14. Companion to `engagement_state_census.md` §Read-this-first (the flat-kernel finding) and `periphery_navigates.md` (what the periphery does).

## The test

A peripheral membership kernel is a claim about what a fixation delivers to
a result it does not land on. That claim can be checked without any content
model: intake during the survey phase, on results *not* fixated during those
five fixations, should predict which of them the searcher fixates later in
the trial. A kernel that does this better than plain gaze distance is
carrying something about the periphery. One that does not is a distance
transform with a weight on it.

- Candidates: 16,436 on-screen, non-clicked slots not fixated in the first
  five fixations, over 2,322 trials; 13,288 fixated later.
- Per kernel: intake = Σ fixation duration × alpha over the five survey
  fixations, outside the band. Scored as a within-trial rank so position
  is removed. LOSO logistic regression by participant.
- Baselines: position; mean rect-boundary gaze distance during the survey
  (rank); position + distance.

## Result

| kernel | share of candidates with zero intake | intake rank alone | + position (Δ over position) | + position + distance (Δ over position + distance) |
|---|---|---|---|---|
| position only | — | — | 0.654 | — |
| gaze distance rank only | — | 0.748 | — | 0.752 |
| **published Eq. 2, ungated** | 0.00 | **0.520** | 0.663 (−0.001) | 0.759 (+0.009 [+0.006, +0.012]) |
| published Eq. 2, gated 400 / 200 / 100 px | 0.74 / 0.87 / 0.94 | 0.745 / 0.747 / 0.747 | +0.048 / +0.050 / +0.050 | +0.001 each |
| boundary 1/(1 + E/E2), E2 = 1° / 2° / 4°, ungated | 0.00 | 0.748 each | +0.051 / +0.050 / +0.050 | +0.001 / +0.001 / +0.001 |
| boundary 1/(1 + E/2°), gated 200 px | 0.87 | 0.747 | +0.050 | +0.001 |
| hard gate only, 200 / 100 px (duration within reach) | 0.87 / 0.94 | 0.747 / 0.747 | +0.049 / +0.050 | +0.000 / +0.001 |

Within trial, the candidate with the most survey intake is fixated later
in 96 % of trials, the one with the least in 49 % (`periphery_navigates`,
boundary kernel gated 200 px, n = 2,118).

## Reading

1. **The published kernel, as published, predicts nothing about where the
   eyes go next on a SERP.** Intake rank alone is 0.520 and it adds −0.001
   to position. Its +0.009 over position and distance is the area weight:
   larger results are fixated more, which is a layout term, not a
   peripheral one.
2. **Every eccentricity-aware kernel is the same kernel.** A hyperbolic
   falloff at 1°, 2° or 4°, a hard gate at 100 px or 200 px, the published
   alpha restricted to a gate, and duration-within-reach with no alpha at
   all: 0.745–0.748 alone, +0.050 over position, +0.001 over distance. The
   falloff shape is unidentifiable from fixation prediction on this layout.
   What matters is only that alpha decreases with distance.
3. **On a SERP, peripheral intake is gaze proximity.** Distance rank alone is
   0.748; no kernel adds more than 0.001 to it. Whatever the periphery
   contributes to navigation here, it is captured by "how close the eyes
   were", and a kernel's job reduces to normalising that into a
   per-element exposure with units.
4. **The survey covers little at near-peripheral reach.** Within 200 px (≈ 5°), 87 %
   of unfixated candidates receive zero intake from the five survey
   fixations. The survey's map is a map of five neighbourhoods, not of the
   page.

## What the paper itself says about time and probability (read 2026-09-14, Downloads/main.pdf)

PAI is defined as an **instantaneous** opacity per gaze point or fixation: "the
computation is done instantly, in real-time, not via accumulation over time"
(§2). Fixation duration appears nowhere in Eq. 1 or Eq. 2. The paper positions
this against Wang's VAI (OGD weighted by fixation duration) and Rim et al.'s
Weighted Sum Durations (Gaussian kernel × duration); it keeps the distance
term and drops the duration term. The only probabilistic language is the
rationale for the area weight in §4.1: "the probability of attention landing
in a given AOI is proportional to its size." Accumulation over time is
mentioned once, in the conclusion, as a visualisation option ("if buffered
… a decaying heatmap-like visualization"), undefined. The decay scale is the
AOI's own centroid distance ("the CGD serves as an intrinsic scale parameter
proportional to the AOI's effective radius"), not visual angle, and the
square-root profile is chosen for visualisation ("more aesthetically
pleasing"). So every duration × alpha "mass" in this repository is our
construction in the VAI / WSD convention, not the paper's; and the
AOI-relative scale is the conceptual root of the flatness on wide bands.

## What this offers the method's authors

- On wide, short AOIs the vertex-distance / centroid-distance ratio inside
  Eq. 2 does not decrease with eccentricity (corpus Spearman −0.08), and
  the area weight inside the square root makes alpha rise with distance
  for small bands. Boundary distance fixes the first; moving the area
  weight outside the distance term fixes the second.
- For prediction, no falloff shape beats a hard gate. The kernel's value on
  this kind of page is interpretability and units, not information, and a
  paper can say so with the table above.
- A shape *would* be identifiable on a layout with compact, well-separated
  AOIs, which is what PAI was designed for. That is the experiment the
  authors are better placed to run than this corpus is.

## Caveats

- Survey = first five fixations regardless of content, the NB13 definition.
- "Later fixated" is any later visit; the first-pass-only version would be
  stricter and is not run.
- 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`) is the repo's convention; at the derived 43 px/° the 200 and 100 px gates read 4.6° and 2.3°.
- `[LAB]` only.
