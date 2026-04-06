# Margin Fixations and Parafoveal Preview on SERPs

**Status:** Completed — [notebook 19](../notebooks-v2/19_margin_fixations.ipynb)

## Original Hypothesis

Some fixations in the left gutter/margin serve as deliberate spatial encoding events ("margin plans") — bookmarking result positions to guide subsequent regressions. Prediction: trials with margin-plan fixations should have better regression landing precision regardless of cognitive load.

## Results

The notebook reframed the question around parafoveal preview: does peripheral content at result boundaries influence saccade planning?

| Test | Effect size | p-value | Interpretation |
|------|-------------|---------|----------------|
| Margin → p(land N+1) | 23.4% vs 7.7% | ≈ 0 | Geometric (trivial) |
| Raw preview benefit | Δ = −2 ms | 0.22 | Null |
| Amplitude-matched | Δ = −6 to +7 ms | n.s. | Null |
| Partial r (dist → next_dur \| cur_dur) | r = 0.013 | 0.05 | Negligible |
| 2×2 short+margin vs short+interior | Δ = −6 ms | 0.06 | Borderline, tiny |
| Survey phase preview | Δ = −5 ms | — | Null |
| Evaluate phase preview | Δ = −1 ms | — | Null |
| Left-margin saccade precision | SD 93 vs 97 px | 0.011 | Small |

**The parafoveal preview benefit — well-established in text reading (Rayner 1998, 2009) — does not transfer to SERP reading.** In text, the preview zone contains the next word with distinctive orthographic features. On a SERP, the preview zone shows another structurally identical result block. There's nothing distinctive to preview.

This strengthens the content-independence finding from notebook 13: survey saccades are ballistic, position-based, and structurally guided rather than content-guided. The eye knows where results ARE (structural regularity) but doesn't know what they SAY until foveating them.

## Design Implication

Making result boundaries more visually distinctive (color bands, icons, thumbnails) could potentially enable parafoveal pre-evaluation — giving the eye something to discriminate before landing. Current SERP designs are optimized for reading, not for peripheral scanning.

## Backlogged: Larger Foveal Radius Captures

Re-capture gazeplots with a larger foveal radius (e.g., 90px instead of 45px). Benefits:
1. More readable — shows more of the result text the participant was evaluating
2. Hides alignment imprecision — mask is larger than the offset error
3. Better matches the actual useful field of view during reading (~2° parafoveal)

Currently `TEST_RADIUS=45` in the capture script. Try 75–90px and compare.
