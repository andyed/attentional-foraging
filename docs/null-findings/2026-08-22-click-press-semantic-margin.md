# Query-click semantic distance does not explain regressive click press duration

**2026-08-22.** `[LAB, AdSERP, typed_gapfill]`

## TL;DR

Neither query→clicked semantic distance nor local semantic ambiguity explains
the `mousedown`→`mouseup` duration of regressive-return clicks. The strongest
pattern is narrower: when a viewed organic alternative is more query-aligned
than the clicked result, first-forward holds are longer, while regressive holds
are not. The resulting pass × competitive-disadvantage interaction is −4.9%
per SD (95% participant-cluster bootstrap CI −10.5% to +0.4%, raw *p* = .070,
Holm *p* = .209). Its direction is stable under leaving out each participant,
but it is not a confirmed interaction. Semantic tie-closeness—the cleaner
ambiguity test—is essentially null.

## What was run

Producer:
[`scripts/click_press_semantic_margin_analysis.py`](../../scripts/click_press_semantic_margin_analysis.py)

The input is the primary organic-click subset from
[`click_press_latency_pass_analysis.py`](../../scripts/click_press_latency_pass_analysis.py):
same-XPath `mousedown`/`mouseup` pairs, gaze/pass state anchored at
`mousedown`, holds ≤1 s, and target fixations no more than 1.5 s old.

Behavioral positions remain canonical `typed_gapfill` **display ranks**. Each
typed organic AOI's `rso[k]` handle joins directly to absolute h3 position `k`
in `content-features-by-position.json`; the embedding cache position is never
substituted for display rank. This direct bridge joins all 1,225 primary
organic clicks. It avoids the older organic-cache mapping, which omits many
top h3 slots when its heuristic classifies them as ads.

Three prespecified semantic constructs form one Holm-corrected interaction
family:

1. **Query→clicked distance:** `1 − cosine(query, clicked result text)`;
2. **Viewed competitive disadvantage:** `max cosine(query, viewed other
   organic) − cosine(query, clicked)`;
3. **Viewed local ambiguity:** the negative absolute clicked-versus-best-other
   margin, so a larger value means a closer semantic tie.

“Viewed” means that the corresponding main-axis display slot received at least
one recorded fixation at or before `mousedown`. This is evidence of a gaze
encounter, not proof of conscious comparison. Structural sensitivities replace
the viewed set with every joinable organic result on the page.

Each log-duration model has participant fixed effects, categorical
`typed_gapfill` display-rank effects, log decision time, target-fixation
recency, and log pre-press cursor speed. Confidence intervals and raw
two-sided *p* values use 5,000 participant-cluster bootstrap resamples.

## Numbers

### Sample flow

- Primary organic clicks: **1,225 from 47 participants** — 166 first-forward
  and 1,059 regressive-return; 38 participants contribute both classes.
- Clicked-result embedding join: **1,225 / 1,225 (100%)**.
- A viewed organic competitor is available for **1,142 clicks** — 91
  first-forward and 1,051 regressive-return; 35 participants contribute both
  classes.
- Eighty-three clicks have no viewed other organic result and are excluded only
  from the viewed-competitor models. Three clicks have no other joinable
  organic result for the structural sensitivity.

### Primary pass × semantic interactions

Effects are percent change in button-hold duration per 1-SD increase in the
semantic feature.

| semantic feature | pass × feature | bootstrap 95% CI | raw *p* | Holm *p* | first-forward slope | regressive slope |
|---|---:|---:|---:|---:|---:|---:|
| query→clicked distance | −2.93% | [−6.99%, +1.27%] | .157 | .314 | +3.88% [−0.49%, +8.18%] | +0.83% [−0.56%, +2.34%] |
| viewed competitive disadvantage | −4.92% | [−10.47%, +0.38%] | .070 | .209 | +6.08% [+0.34%, +12.70%] | +0.86% [−0.92%, +2.64%] |
| viewed local ambiguity | +0.57% | [−6.13%, +7.22%] | .864 | .864 | −0.61% [−6.35%, +6.06%] | −0.04% [−2.01%, +1.93%] |

The first-forward competitive-disadvantage slope has an unadjusted bootstrap
*p* = .037, but it is a conditional component of an interaction whose CI
crosses zero and whose family-adjusted *p* is .209. It is therefore a lead for
replication, not a positive result.

The competitive-disadvantage interaction remains negative in all 47
leave-one-participant-out fits, ranging from −6.32% to −3.75%. That makes a
single-participant explanation unlikely, but it does not solve the limited
first-forward sample or multiplicity.

### Structural sensitivity

Using the best joinable organic result whether viewed or not gives the same
direction for competitive disadvantage: pass × feature = **−3.87%**, 95% CI
[−8.55%, +0.34%], raw *p* = .068. The first-forward slope is +4.66% [0.44%,
9.97%], while the regressive slope is +0.61% [−1.21%, 2.59%]. Structural
tie-closeness is also null: +3.03% [−1.46%, +9.02%], *p* = .158.

## Why this is a null

The ambiguity construct itself is flat: its interaction and both pass-specific
slopes are centered near zero. Query→clicked distance also has no detectable
regressive-click slope. The only suggestive pattern is a difference between a
small first-forward competitor subset (91 clicks) and a much larger regressive
subset (1,051 clicks). Its participant-bootstrap interval crosses zero and its
Holm-adjusted *p* is .209. Reporting only the first-forward conditional slope
would overstate the evidence.

The semantic features are model-based proxies. Query cosine is not a human
relevance grade, semantic closeness is not correctness, and AdSERP supplies no
accuracy ground truth. This analysis also covers organic result text only; the
current cache does not provide a defensible equivalent for `dd_top` or
`native_ad` clicked text, so it does not explain the previously observed
`dd_top` pass interaction.

## What was learned anyway

The useful lead is **competitive mismatch during first-forward choice**, not
ambiguity during regressive choice. A participant appears to hold the button
slightly longer on a first-forward click when another candidate—viewed or
merely present—is more query-aligned than the selected result. Once the target
is revisited on a regressive pass, that semantic-disadvantage slope is near
zero. A replication should preregister this directional interaction, balance
forward and regressive cases, and use independent relevance/correctness labels.

The direct `rso[k]`→absolute h3 join is also the correct technical path for
future typed-AOI semantic analyses. The typed position remains the behavioral
rank; the h3 position is only a content lookup key.

## Pointers

- Generated per-click records, full JSON summary, report, and forest plot:
  `scripts/output/click_press_semantic_margin/` (gitignored)
- Parent press-duration finding:
  [`2026-08-22-click-press-latency-pass-lfhf.md`](2026-08-22-click-press-latency-pass-lfhf.md)
- Typed AOI extraction and `rso[k]` semantics:
  [`../methodology/organic-result-aoi-extraction.md`](../methodology/organic-result-aoi-extraction.md)
- Surface-specific follow-up:
  [`../click-press-ad-moderation.md`](../click-press-ad-moderation.md)
- Peripheral-attention weighting follow-up:
  [`2026-08-22-click-press-pai-conflict.md`](2026-08-22-click-press-pai-conflict.md)
- Temporal sequence follow-up:
  [`2026-08-22-click-press-semantic-sequence.md`](2026-08-22-click-press-semantic-sequence.md)

## Reproduce

```bash
.venv/bin/python scripts/click_press_latency_pass_analysis.py
.venv/bin/python scripts/click_press_semantic_margin_analysis.py
.venv/bin/python scripts/click_press_pai_conflict_analysis.py
.venv/bin/python scripts/click_press_semantic_sequence_analysis.py
```
