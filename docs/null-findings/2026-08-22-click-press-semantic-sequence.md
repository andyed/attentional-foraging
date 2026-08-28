# Pre-press semantic return sequences do not explain click holds

**2026-08-22.** `[LAB, AdSERP, typed_gapfill]`

## TL;DR

The semantic-mismatch lead does not become stronger when expressed as a gaze
sequence immediately before the press. In a fixed 2 s pre-`mousedown` window,
the pass × final better-organic→clicked-organic transition is **−0.40%** (95%
participant-cluster bootstrap CI **−22.55% to +26.18%**, *p* = .996). The
stricter clicked→better-organic→clicked chain appears only on regressive passes;
within those clicks its adjusted effect is **+1.25%** (CI **−8.27% to +10.86%**,
*p* = .829). Both Holm-adjusted primary *p* values are 1.0. Sequence direction
adds no detectable press-duration information beyond generic switching,
returning, and the unweighted semantic-disadvantage lead.

## What was run

Producer:
[`scripts/click_press_semantic_sequence_analysis.py`](../../scripts/click_press_semantic_sequence_analysis.py)

The input is the 1,225 primary organic-click records and direct `rso[k]`
semantic joins from
[`click_press_semantic_margin_analysis.py`](../../scripts/click_press_semantic_margin_analysis.py).
Fixations are assigned by strict X+Y containment in page-space
`typed_gapfill` rectangles. Consecutive fixations on the same display position
are collapsed into AOI runs. Unassigned gaze gaps do not create a run, but any
intervening assigned AOI breaks adjacency.

The primary window is the fixed 2,000 ms ending at `mousedown`; 1, 3, and 5 s
windows are sensitivities. Two tests form one Holm-corrected family:

1. **Final better return × pass.** The last two assigned AOI runs are a
   semantically better organic result followed by the clicked organic result.
   Nested any-AOI-return and any-organic-return terms, plus their pass
   interactions, separate semantic direction from generic switching and
   returning. The model also retains the unweighted all-candidate semantic-
   disadvantage interaction.
2. **Strict chain within regressive clicks.** The last three assigned runs are
   clicked target → better organic result → clicked target. Because no
   first-forward click has this strict chain, it is tested within regressive
   clicks rather than misrepresented as a pass interaction. Nested generic and
   organic three-run chain indicators again isolate semantic direction.

Models use participant fixed effects, categorical clicked `typed_gapfill`
display-rank effects, log decision time, target-fixation recency, and log
pre-press cursor speed. Inference uses 5,000 participant-cluster bootstrap
resamples.

## Numbers

### Sequence prevalence

The adjusted models contain 1,222 clicks with an alternative organic semantic
comparison: 166 first-forward and 1,056 regressive-return.

| sequence in fixed 2 s window | first-forward | regressive-return |
|---|---:|---:|
| any AOI → clicked target | 52 | 514 |
| organic result → clicked target | 24 | 345 |
| better organic → clicked target | **13** | **164** |
| target → any AOI → target | 0 | 218 |
| target → organic → target | 0 | 144 |
| target → better organic → target | **0** | **76** |

The strict chain's absence from first-forward clicks is structurally sensible:
leaving and returning to the clicked target is itself a revisit pattern. It
also means the cross-pass better-return interaction is driven by only 13
first-forward cases and cannot be estimated precisely.

### Primary estimates

| test | adjusted effect | bootstrap 95% CI | raw *p* | Holm *p* |
|---|---:|---:|---:|---:|
| pass × final better return | −0.40% | [−22.55%, +26.18%] | .996 | 1.000 |
| strict better-return chain, regressive only | +1.25% | [−8.27%, +10.86%] | .829 | 1.000 |

Participant-paired descriptives agree with the null after participant
composition is removed:

- Final better return among first-forward clicks: median within-participant
  difference **+0.75 ms**, 10 paired participants, Wilcoxon *p* = .770.
- Final better return among regressive clicks: **−2.00 ms**, 46 paired
  participants, *p* = .334.
- Strict clicked→better→clicked chain among regressive clicks: **−3.00 ms**, 38
  paired participants, *p* = .292.

An exploratory dose test on the 369 clicks whose final return came from another
organic result is also flat: previous-result semantic advantage × pass =
**−1.78% per SD**, CI [−11.67%, +9.74%], *p* = .759. It additionally controls
the previous result's categorical display rank.

### Window sensitivities

| fixed window | pass × better-return transition | strict regressive chain |
|---|---:|---:|
| 1 s | −10.39% [−30.69%, +20.77%], *p* = .434 | −7.74% [−21.19%, +9.00%], *p* = .307 |
| 3 s | −2.15% [−23.70%, +24.25%], *p* = .894 | +3.39% [−4.56%, +11.62%], *p* = .428 |
| 5 s | −4.18% [−23.40%, +19.34%], *p* = .771 | +2.36% [−5.28%, +10.68%], *p* = .535 |

No window yields a resolved effect, and the strict-chain point estimate changes
sign between 1 and 2 s.

## Why this is a null

The primary estimates are close to zero, their intervals are broad in both
directions, and participant-paired differences are only a few milliseconds.
The cross-pass model is especially underpowered because just 13 first-forward
clicks have the final better-return transition. The stricter hypothesis has 76
regressive cases across 38 paired participants and is still flat, so its null
cannot be attributed only to the first-forward scarcity.

Raw pooled medians can look larger because better-return sequences are unevenly
distributed across participants, ranks, and generic return structures. The
focal adjusted terms deliberately ask whether the **semantic direction** of a
return adds information beyond leaving and returning at all. It does not.

This remains observational gaze evidence. A “semantically better” embedding
score is not an independent relevance judgment, and an AOI transition is not
proof of conscious comparison or conflict.

## What was learned anyway

Neither total peripheral attention mass nor immediate semantic return order
accounts for the first-forward competitive-disadvantage lead. The simplest
surviving description remains page-level opportunity: first-forward holds are
somewhat longer when a better query-aligned alternative exists, whether or not
the recorded gaze sequence or PAI mass shows an immediate comparison. That is
a narrow replication target, not an established mechanism.

For further click-hold work, more semantic slicing is unlikely to pay off in
this cohort. The better next direction is the clicked element's motor/
affordance structure—especially the unresolved `dd_top` surface contrast—or a
new balanced task with independent relevance and accuracy labels.

## Pointers

- Generated records, summary, report, and coefficient plot:
  `scripts/output/click_press_semantic_sequence/` (gitignored)
- Parent semantic-margin analysis:
  [`2026-08-22-click-press-semantic-margin.md`](2026-08-22-click-press-semantic-margin.md)
- PAI-weighting follow-up:
  [`2026-08-22-click-press-pai-conflict.md`](2026-08-22-click-press-pai-conflict.md)
- Surface-specific follow-up:
  [`../click-press-ad-moderation.md`](../click-press-ad-moderation.md)

## Reproduce

```bash
.venv/bin/python scripts/click_press_latency_pass_analysis.py
.venv/bin/python scripts/click_press_semantic_margin_analysis.py
.venv/bin/python scripts/click_press_semantic_sequence_analysis.py
```
