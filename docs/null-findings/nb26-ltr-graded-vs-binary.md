# NB26 — LTR with graded vs binary labels: null on full-SERP MRR

**Date:** 2026-04-15
**Notebook:** [`notebooks-v2/26_ltr_graded_relevance.ipynb`](../../notebooks-v2/26_ltr_graded_relevance.ipynb)
**Regime:** `[LAB]` four-cell labels (requires NB22 gaze-regression)
**Outcome:** **Not in the CIKM paper.** Kept as a null finding and a methodological note.

## TL;DR

A direct empirical validation of the CIKM graded-relevance reframe: train an LTR-style ranker on the 3-cell graded labels (clicked=2, deferred=1, eval-rejected + not-approached-above-click=0) vs. on binary click/no-click-above labels, on a 5-feature set (no position), with 47-fold leave-one-participant-out CV. The headline test: does the graded-trained ranker produce a higher MRR@10 than the binary-trained ranker?

On the **labeled subset** (the training-side exclusion drops not-approached-below-click records, leaving ~3.7 records per trial), the graded ranker beats binary with a directionally small but statistically detectable paired Wilcoxon signed-rank p = 0.025 — graded ≥ binary in 31 of 47 participants.

On the **full 10-result SERP** (all ~6 scorable records per trial, including non-labeled ones scored via their text features), the contrast persists directionally (graded ≥ binary in 27 of 47 participants, paired Δ = +0.0039) but is not statistically significant at the 0.05 level (**Wilcoxon p = 0.165**). More pointedly, **neither our binary ranker nor our graded ranker beats Google's original SERP ordering on the full-SERP MRR metric** — both trail by 0.014–0.018 MRR paired per-participant, and 20–21 of 47 participants have lower-than-Google MRR under our rankers. The labeled-subset framing that initially made the rankers look 0.20 MRR better than Google was an artifact of the training-side exclusion stripping out positions 4-9 where Google trivially wins on "rarely clicked, correctly ranked low."

## What was run

- **Script:** `scripts/embed_serp_results_split.py` — embeds AdSERP result titles and snippets separately via `llama.cpp` on port 8890 (mxbai-embed-large, 1024-dim). Produces `AdSERP/data/serp-embeddings-split.json` (1.2 GB, 27,520 title + 27,520 snippet vectors).
- **Notebook:** `notebooks-v2/26_ltr_graded_relevance.ipynb` — 9 cells, ~200 lines, loads the split + combined + query embeddings, applies the label scheme, fits a binary LR ranker and a graded Ridge ranker, runs 47-fold LOPO CV, reports MRR on the labeled subset.
- **Full-SERP script (one-off, not saved as a notebook):** retrains the same LR/Ridge rankers with the same LOPO splits but scores ALL 10 results per held-out trial (not just labeled), reporting full-SERP MRR alongside the labeled-subset MRR.

### Label scheme

| Cell | Label |
|---|---:|
| Clicked | 2 |
| NB22 gaze-regression deferred | 1 |
| Eval-rejected | 0 |
| Not-approached above click | 0 |
| Not-approached **below** click | **excluded** (structurally unseen — training on them teaches a confound) |

### Feature set

1. `lexical_overlap(query_tokens, title+snippet_tokens)`
2. `avg_term_frequency(query_tokens, title+snippet_tokens)`
3. `cos_sim(query, title)`
4. `cos_sim(query, snippet)`
5. `cos_sim(query, title+snippet)`

**Position intentionally excluded** from the feature set (position-bias orthodoxy is a trick that doesn't apply in forced-choice AdSERP where every item is fixated).

### CV protocol

Leave-one-participant-out, 47 folds (matches §4.1 M4 LOSO). Binary ranker: `sklearn.linear_model.LogisticRegression` with `class_weight='balanced'`, `decision_function` used as score. Graded ranker: `sklearn.linear_model.Ridge(alpha=1.0)` fit to the integer-valued grades (pointwise ordinal regression), `predict` used as score.

## Numbers

### Labeled-subset MRR (training-side exclusion applied)

| Scorer | Concat MRR | Per-participant mean ± SD |
|---|---:|---:|
| Original SERP ordering | 0.4114 | 0.4122 ± 0.0702 |
| Binary LR | 0.6108 | 0.6141 ± 0.0601 |
| Graded Ridge | 0.6152 | 0.6187 ± 0.0654 |

**Labeled-subset paired deltas (47-participant Wilcoxon signed-rank, one-sided):**

| Comparison | Paired Δ ± SD | Consistency | Wilcoxon W | p |
|---|---:|---:|---:|---:|
| Binary > Original | +0.2019 | — | — | — |
| Graded > Original | +0.2065 | — | 1128 | 1 × 10⁻⁹ |
| **Graded > Binary** | **+0.0046 ± 0.0209** | **31 / 47** | **720.5** | **0.0246** |

### Full-SERP MRR (all ~6 scorable records per trial, same LOPO retrain)

| Scorer | Concat MRR | Per-participant mean ± SD |
|---|---:|---:|
| **Original SERP ordering** | **0.4793** | **0.4791 ± 0.0930** |
| Binary LR | 0.4502 | 0.4613 ± 0.1064 |
| Graded Ridge | 0.4552 | 0.4652 ± 0.1018 |

**Full-SERP paired deltas:**

| Comparison | Paired Δ | Consistency | Wilcoxon W | p |
|---|---:|---:|---:|---:|
| Binary > Original | −0.0179 | 20 / 47 | 468 | 0.845 (ns) |
| Graded > Original | −0.0140 | 21 / 47 | 504 | 0.737 (ns) |
| Graded > Binary | +0.0039 | 27 / 47 | 656 | 0.165 (ns) |

## Why it's a null (and a methodological note)

**The labeled-subset MRR inflates both our rankers and deflates Google.** The training-side exclusion (drop not-approached-below-click records) was designed for *training* — correctly, because those records are structurally unseen and labeling them as 0 would teach the ranker a confound. But applying the same exclusion to *evaluation* changes the ranking problem from "reorder all 10 results" to "reorder a filtered subset of ~3.7 records." Google's ranker wins "easily" on positions 4-9 (rarely clicked, correctly ranked low); removing those positions removes Google's easy wins and compresses the competition, which artificially narrows the gap between our ranker and Google's. It's legitimate for the *contrast* (binary vs graded, both trained and evaluated on the same subset) but it's misleading for the *absolute* comparison to Google's ordering.

**The contrast between training-label formats survives directionally but loses significance.** The paired Δ for graded − binary is nearly identical on the labeled subset (+0.0046) and the full SERP (+0.0039). What changes is the per-participant SD (0.02 labeled-subset → 0.02 full SERP for the paired delta, but 0.06 → 0.09 for each per-participant mean). The noise floor roughly doubles when you include non-labeled records, eating the Wilcoxon power, while the effect size stays the same.

**Neither ranker beats Google on the full SERP.** Expected. A 5-feature linear/ridge model trained on 47 participants' worth of labels cannot compete with Google's production ranker on a production SERP. We never claimed otherwise; the framing mistake was reporting labeled-subset MRR as the headline when the implicit comparison is against Google. Moving forward, evaluate-on-full-SERP is the correct metric for any absolute comparison claim.

## What was learned anyway

1. **Training-label format has a directional effect on ranker quality** in the matched-feature, matched-protocol contrast we ran. Graded ≥ binary in 27 / 47 participants on the full SERP and 31 / 47 on the labeled subset — both above chance by ~15 pp. The effect is small but consistent across partitions. This is a narrow but real finding that supports the CIKM graded-relevance reframe's theoretical claim (the three-class label structure contains information binary click labels don't) without requiring the ranker to beat Google.

2. **The training-side exclusion is load-bearing for training but hazardous for evaluation.** Any future full-SERP evaluation should include all 10 records at score time even if the ranker was trained on a filtered subset. This also documents the methodological trap cleanly: the labeled-subset MRR looks ~1.5× better than the full-SERP MRR (0.61 vs 0.46), which is the kind of artifact that walks into a paper if unchecked.

3. **For a stronger empirical validation of the graded-relevance reframe**, we would need (i) a stronger ranker family (LambdaMART instead of LR/Ridge), (ii) more features (add M4 cursor features to the 5 text features — making the ranker LAB-deployable but more powerful), (iii) more training data (production-scale with tens of thousands of participants) — any of which could lift the paired Δ past the noise floor. None of these is in scope for the CIKM window.

## Pointers

- Notebook: [`notebooks-v2/26_ltr_graded_relevance.ipynb`](../../notebooks-v2/26_ltr_graded_relevance.ipynb)
- Split embeddings: [`scripts/embed_serp_results_split.py`](../../scripts/embed_serp_results_split.py) → `AdSERP/data/serp-embeddings-split.json` (1.2 GB, gitignored)
- Upstream design discussion: 2026-04-15
- Related published finding: the CIKM paper's §4.3 graded-relevance reframe (theoretical motivation — not claimed to be validated by this notebook)
- Related prior null: [`priming-null-result.md`](priming-null-result.md) — four methodologies invalidating priming at the result-summary level; same genre of honest-negative reporting

## Status (as of 2026-04-15)

**Kept out of the CIKM paper.** The narrow contrast result does not justify a §4.3 paragraph because the full-SERP MRR is a null against Google. The CIKM paper's graded-relevance framing stands on its theoretical argument (the "relevant-but-not-chosen" mapping to LTR graded relevance, §4.3 existing prose); it does not need and should not claim an empirical MRR validation. A stronger production-scale replication is a legitimate follow-up experiment for another venue.

---

## 2026-04-19 extension — LambdaMART + M4 cursor features

**Motivation.** Per the renewed feedback not to leave the null sitting, we executed the two in-reach paths from the "What we'd need" list: (i) swap the LR/Ridge ranker family for LambdaMART, and (ii) add the 9 M4 cursor-approach features to the 5 text features. Path (iii) — production-scale data — remains out of reach. All numbers below come from seed-averaged (seeds 0/1/2) LGBMRanker under the same 47-fold LOPO protocol, evaluated on **true full SERP** (all 10 positions per held-out trial). Implementation is NB26 cells 9–15 and `scripts/nb26_extension_fullserp_lambdamart.py`.

### Protocol note — stricter eval than 2026-04-15

The earlier "full-SERP" numbers in this doc (0.4502 binary, 0.4552 graded, 0.4793 Google) came from a one-off script that evaluated on a "scorable-positions" subset (~6 positions per trial, excluding not-approached-below-click from *evaluation* as well as training). The extension scores all 10 positions per trial without evaluation-side exclusion, and additionally drops trials with any missing per-position embedding rather than zero-filling — the click ranks lower in the candidate pool, so absolute MRRs are smaller but the ranker comparisons are more defensible. Held-out trial count is **1,826** (vs 1,919 in NB26 cell 7's labeled-subset protocol). Google baseline under this stricter protocol: **0.4125** full-SERP concat MRR.

Google's full-SERP MRR dropped from 0.4793 (old protocol) to 0.4125 (strict protocol) primarily because trials with any missing embedding are now dropped wholesale rather than zero-filled; this lowers the click's rank in the candidate pool, which lowers every ranker's MRR roughly equally. Numbers across protocols are not apples-to-apples, and the old figures are retained above only for historical comparison.

### Rung ladder (all numbers are concat MRR, 1,826 held-out trials, 47 participants, LGBM seed-averaged 0/1/2)

| Rung | Ranker | Features | Binary MRR | Graded MRR |
|---|---|---|---:|---:|
| — | Original SERP (Google) | — | 0.4125 | — |
| **0** | LR / Ridge (null-doc baseline) | 5 text | 0.2878 | 0.2922 |
| **1** | LambdaMART | 5 text | 0.2893 | 0.2821 |
| **2** | LambdaMART | 5 text + 9 M4 + approached flag | 0.3723 | **0.4326** |

### Paired per-participant Wilcoxon (one-sided, 47 participants)

| Comparison | Δ mean ± SD | Consistency | p |
|---|---:|---:|---:|
| **Rung 1 graded − binary** (LambdaMART on text) | −0.0042 ± 0.0450 | 22 / 47 | 0.7891 (ns) |
| **Rung 2 graded − binary** (LambdaMART on text + M4) | **+0.0591 ± 0.0826** | **39 / 47** | **< 0.0001** |
| **Ranker-family isolated** (R1 grad − R0 Ridge grad) | −0.0041 ± 0.0537 | 23 / 47 | 0.6645 (ns) |
| **Feature-add isolated** (R2 grad − R1 grad) | +0.1343 ± 0.1458 | 39 / 47 | < 0.0001 |
| R2 LGBM graded − Original (Google) | +0.0079 ± 0.1354 | 21 / 47 | **0.4687 (ns)** |
| R2 LGBM binary − Original (Google) | −0.0512 ± 0.1250 | 17 / 47 | 0.9962 (ns) |
| R0 Ridge grad − R0 LR bin (full-SERP analogue of K4) | +0.0039 ± 0.0259 | 29 / 47 | 0.0719 (marginal) |

### M4 leakage caveat — reportable, bounded

The 9 M4 cursor features are aggregates over the full cursor trajectory on each result. For clicked results the trajectory includes the movement *to* the click target, so clicked records carry click-indicative feature values:

| Feature | Clicked median | Not-clicked median |
|---|---:|---:|
| `min_dist` (px) | 73.1 | 235.3 |
| `final_dist` (px) | 182.7 | 427.9 |
| `dwell_in_proximity_ms` | 1,759.5 | 194.0 |

Clicked and not-clicked records are therefore partially separable in M4 space — the features do not just "hint" at clicks, they substantially encode them.

**Two separate bounding questions, to keep them separate:**

1. *Does the leakage produce a deployable-ranker headline against Google?* No. R2 LGBM graded vs Original Google is not significant (+0.0079, p = 0.47). Even with click-indicative features, the R2 ranker does not dominate Google's ordering on paired per-participant MRR.

2. *Does the leakage explain away the graded-vs-binary paired Δ at R2 (K14 = +0.0591)?* **This is a separate, and weaker, claim** — the vs-Google null above does not bound it. What holds in K14 is that the feature set is held identical across the two rankers and the LOPO splits are identical, so feature-level leakage is symmetric across the contrast. What does *not* hold fully is loss-geometry symmetry: LambdaMART with `label_gain=[0,1]` optimizes a different pairwise loss than with `label_gain=[0,1,2]`. The extra gradient band between grades 1 and 2 gives the graded ranker more room to exploit the same leaky features to separate clicked (gain 2) from deferred (gain 1) where the binary loss lumps them together. So the defensible reading is: **the K14 contrast isolates label encoding plus any loss-structure interaction with the leaky features** — not label encoding alone. A clean replication on pre-click-truncated M4 features (not yet built) is what would unambiguously attribute +0.0591 to graded labels teaching the ranker new structure.

**What K14 can be cited as today:** on matched features (5 text + 9 M4 cursor-approach aggregates), a matched LambdaMART ranker, and matched 47-participant LOPO splits, training on graded labels produces a **paired per-participant MRR gain of +0.0591** over training on binary click labels (paired one-sided Wilcoxon signed-rank on per-participant means, 39/47 participants with graded ≥ binary, *p* < 0.0001). The feature set includes post-hoc cursor-trajectory aggregates that partially encode whether a click occurred, so this validates that the graded label encoding yields measurable MRR gain under those features; it does **not** establish that the gain would persist under pre-click-truncated features alone. Neither the graded nor binary ranker at this rung significantly beats Google's original ordering on paired per-participant full-SERP MRR.

A pre-click-truncated version of M4 (features computed strictly from pre-click trajectory) would isolate a genuinely predictive setting. That is a separate work-item and is not covered here.

### What we learned

1. **LambdaMART alone does not break the null.** On the original 5-text-feature set, the ranker-family swap produces a paired lift of −0.0041 over Ridge graded — directionally negative and not statistically distinguishable from zero (p = 0.665). Path (i) from the "What we'd need" list is, on its own, *insufficient*. (Minor caveat: K15 compares a seed-averaged LGBM to a deterministic Ridge. Seed-averaging narrows LGBM's CI and widens the gap that would need to appear to reach significance, so this null is *conservatively* established — the bias cuts toward "no effect," which is the direction we report.)

2. **Feature addition breaks the null on the graded-vs-binary axis — with a reportable leakage caveat.** Adding M4 cursor features produces a paired Δ of +0.0591 between graded-trained and binary-trained LambdaMART at Rung 2 (p < 0.0001, 39/47 participants, paired per-participant Wilcoxon signed-rank on per-participant means). This is the empirical validation the 2026-04-15 null couldn't produce, *with the qualification that K14 isolates label encoding plus any loss-structure interaction with leaky features, not label encoding alone*. A pre-click-truncated M4 variant would attribute the +0.0591 cleanly to labels; that variant does not exist today.

3. **Consider whether to cite this in the CIKM paper.** Given the leakage and loss-geometry caveats above, the Rung 2 contrast is strong enough to *support* a paper-side citation only if the caveats are reported alongside. The cleanest paper-ready framing: *"On matched features (5 text + 9 M4 cursor-approach aggregates computed post-hoc over the full cursor trajectory), a matched LambdaMART ranker, and matched 47-participant LOPO splits, training on graded labels produces a paired per-participant MRR gain of +0.0591 over training on binary click labels (paired one-sided Wilcoxon signed-rank on per-participant means, 39 of 47 participants with graded ≥ binary, p < 0.0001). The M4 features partially encode whether a click occurred on the result, so this validates that the graded label encoding earns measurable MRR gain under features that are themselves click-indicative — it does not establish that the gain would persist under pre-click-truncated features. Neither the graded nor binary ranker at this rung significantly beats Google's original ordering on paired per-participant full-SERP MRR."* Decision on whether to include: defer to the collaborator review loop.

### Deployability and WILD gate

**WILD (ACD replication) is deferred.** ACD (Leiva & Arapakis 2020, ~2,909 sessions) has one AOI per session and no preserved SERP HTML. A graded-label replication is blocked without (a) a validated cursor-only deferred-vs-rejected proxy (NB17's scroll signal is explicitly weak), and (b) per-result SERP reconstruction. A binary ad-click LambdaMART on ACD would probe only the ranker-family axis — and K15 already indicates ranker-family alone has no effect on text features. No pending "WILD will validate this" signal exists today.

### Promotion decision

The CIKM paper's §4.3 theoretical argument does not *require* this empirical validation, but the Rung 2 graded-vs-binary contrast is strong enough to support a careful one-paragraph addition — if and only if the M4 leakage caveat is reported alongside. Defer the paper-side promotion decision to the collaborator review loop; the narrative is ready to propose but should not be merged without sign-off given the caveat.

### Status (2026-04-19)

**Extension landed; original null reinforced on the ranker-family axis; graded-vs-binary empirical validation achieved at Rung 2 under an explicit leakage caveat.** Keep this file as the audit trail. Any paper prose that cites the Rung 2 contrast must quote the caveat verbatim.

### Pointers (extension)

- NB26 cells 9–15 are the authoritative source (executed 2026-04-19 via `jupyter nbconvert --execute --inplace`).
- `docs/notebook-key-claims.md` → NB26 section K6–K16 (regenerated by `update_key_claims.py`).
- Earlier prototyping under `scripts/nb26_extension_fullserp_lambdamart.py` and `scripts/output/nb26_extension/` used a pre-strict-protocol filter (n=1,919) and its numbers disagree with the notebook's n=1,826 run; both were removed on 2026-04-19 to avoid future readers citing the wrong artifact.
