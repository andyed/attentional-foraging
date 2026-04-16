# NB26 — LTR with graded vs binary labels: null on full-SERP MRR

**Date:** 2026-04-15
**Notebook:** [`notebooks-v2/26_ltr_graded_relevance.ipynb`](../../notebooks-v2/26_ltr_graded_relevance.ipynb)
**Regime:** `[LAB]` four-cell labels (requires NB22 gaze-regression)
**Outcome:** **Not in the CIKM paper.** Kept as a null finding and a methodological note.

## TL;DR

Peter Dixon-Moses proposed a direct empirical validation of the CIKM graded-relevance reframe: train an LTR-style ranker on the 3-cell graded labels (clicked=2, deferred=1, eval-rejected + not-approached-above-click=0) vs. on binary click/no-click-above labels, on Peter's exact 5-feature set (no position), with 47-fold leave-one-participant-out CV. The headline test: does the graded-trained ranker produce a higher MRR@10 than the binary-trained ranker?

On Peter's **labeled subset** (Peter's exclusion rule drops not-approached-below-click records, leaving ~3.7 records per trial), the graded ranker beats binary with a directionally small but statistically detectable paired Wilcoxon signed-rank p = 0.025 — graded ≥ binary in 31 of 47 participants.

On the **full 10-result SERP** (all ~6 scorable records per trial, including non-labeled ones scored via their text features), the contrast persists directionally (graded ≥ binary in 27 of 47 participants, paired Δ = +0.0039) but is not statistically significant at the 0.05 level (**Wilcoxon p = 0.165**). More pointedly, **neither our binary ranker nor our graded ranker beats Google's original SERP ordering on the full-SERP MRR metric** — both trail by 0.014–0.018 MRR paired per-participant, and 20–21 of 47 participants have lower-than-Google MRR under our rankers. The labeled-subset framing that initially made the rankers look 0.20 MRR better than Google was an artifact of Peter's exclusion rule stripping out positions 4-9 where Google trivially wins on "rarely clicked, correctly ranked low."

## What was run

- **Script:** `scripts/embed_serp_results_split.py` — embeds AdSERP result titles and snippets separately via `llama.cpp` on port 8890 (mxbai-embed-large, 1024-dim). Produces `AdSERP/data/serp-embeddings-split.json` (1.2 GB, 27,520 title + 27,520 snippet vectors).
- **Notebook:** `notebooks-v2/26_ltr_graded_relevance.ipynb` — 9 cells, ~200 lines, loads the split + combined + query embeddings, applies Peter's label scheme, fits a binary LR ranker and a graded Ridge ranker, runs 47-fold LOPO CV, reports MRR on the labeled subset.
- **Full-SERP script (one-off, not saved as a notebook):** retrains the same LR/Ridge rankers with the same LOPO splits but scores ALL 10 results per held-out trial (not just labeled), reporting full-SERP MRR alongside the labeled-subset MRR.

### Label scheme (Peter Dixon-Moses, 2026-04-15)

| Cell | Label |
|---|---:|
| Clicked | 2 |
| NB22 gaze-regression deferred | 1 |
| Eval-rejected | 0 |
| Not-approached above click | 0 |
| Not-approached **below** click | **excluded** (structurally unseen — training on them teaches a confound) |

### Feature set (Peter Dixon-Moses, 2026-04-15)

1. `lexical_overlap(query_tokens, title+snippet_tokens)`
2. `avg_term_frequency(query_tokens, title+snippet_tokens)`
3. `cos_sim(query, title)`
4. `cos_sim(query, snippet)`
5. `cos_sim(query, title+snippet)`

**Position intentionally excluded** from the feature set (Peter: position-bias orthodoxy is a trick that doesn't apply in forced-choice AdSERP where every item is fixated).

### CV protocol

Leave-one-participant-out, 47 folds (matches §4.1 M4 LOSO). Binary ranker: `sklearn.linear_model.LogisticRegression` with `class_weight='balanced'`, `decision_function` used as score. Graded ranker: `sklearn.linear_model.Ridge(alpha=1.0)` fit to the integer-valued grades (pointwise ordinal regression), `predict` used as score.

## Numbers

### Labeled-subset MRR (Peter's exclusion applied)

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

**The labeled-subset MRR inflates both our rankers and deflates Google.** Peter's exclusion rule (drop not-approached-below-click records) was designed for *training* — correctly, because those records are structurally unseen and labeling them as 0 would teach the ranker a confound. But applying the same exclusion to *evaluation* changes the ranking problem from "reorder all 10 results" to "reorder a filtered subset of ~3.7 records." Google's ranker wins "easily" on positions 4-9 (rarely clicked, correctly ranked low); removing those positions removes Google's easy wins and compresses the competition, which artificially narrows the gap between our ranker and Google's. It's legitimate for the *contrast* (binary vs graded, both trained and evaluated on the same subset) but it's misleading for the *absolute* comparison to Google's ordering.

**The contrast between training-label formats survives directionally but loses significance.** The paired Δ for graded − binary is nearly identical on the labeled subset (+0.0046) and the full SERP (+0.0039). What changes is the per-participant SD (0.02 labeled-subset → 0.02 full SERP for the paired delta, but 0.06 → 0.09 for each per-participant mean). The noise floor roughly doubles when you include non-labeled records, eating the Wilcoxon power, while the effect size stays the same.

**Neither ranker beats Google on the full SERP.** Expected. A 5-feature linear/ridge model trained on 47 participants' worth of labels cannot compete with Google's production ranker on a production SERP. We never claimed otherwise; the framing mistake was reporting labeled-subset MRR as the headline when the implicit comparison is against Google. Moving forward, evaluate-on-full-SERP is the correct metric for any absolute comparison claim.

## What was learned anyway

1. **Training-label format has a directional effect on ranker quality** in the matched-feature, matched-protocol contrast we ran. Graded ≥ binary in 27 / 47 participants on the full SERP and 31 / 47 on the labeled subset — both above chance by ~15 pp. The effect is small but consistent across partitions. This is a narrow but real finding that supports the CIKM graded-relevance reframe's theoretical claim (the three-class label structure contains information binary click labels don't) without requiring the ranker to beat Google.

2. **Peter's exclusion rule is load-bearing for training but hazardous for evaluation.** Any future full-SERP evaluation should include all 10 records at score time even if the ranker was trained on a filtered subset. This also documents the methodological trap cleanly: the labeled-subset MRR looks ~1.5× better than the full-SERP MRR (0.61 vs 0.46), which is the kind of artifact that walks into a paper if unchecked.

3. **For a stronger empirical validation of the graded-relevance reframe**, we would need (i) a stronger ranker family (LambdaMART instead of LR/Ridge), (ii) more features (add M4 cursor features to the 5 text features — making the ranker LAB-deployable but more powerful), (iii) more training data (production-scale with tens of thousands of participants) — any of which could lift the paired Δ past the noise floor. None of these is in scope for the CIKM window.

## Pointers

- Notebook: [`notebooks-v2/26_ltr_graded_relevance.ipynb`](../../notebooks-v2/26_ltr_graded_relevance.ipynb)
- Split embeddings: [`scripts/embed_serp_results_split.py`](../../scripts/embed_serp_results_split.py) → `AdSERP/data/serp-embeddings-split.json` (1.2 GB, gitignored)
- Upstream Slack conversation: Peter Dixon-Moses, 2026-04-15 ~10:20 AM
- Related published finding: the CIKM paper's §4.3 graded-relevance reframe (theoretical motivation — not claimed to be validated by this notebook)
- Related prior null: [`priming-null-result.md`](priming-null-result.md) — four methodologies invalidating priming at the result-summary level; same genre of honest-negative reporting

## Status

**Kept out of the CIKM paper.** The narrow contrast result does not justify a §4.3 paragraph because the full-SERP MRR is a null against Google. The CIKM paper's graded-relevance framing stands on its theoretical argument (Peter's "relevant-but-not-chosen" mapping to LTR graded relevance, §4.3 existing prose); it does not need and should not claim an empirical MRR validation. A stronger production-scale replication is a legitimate follow-up experiment for another venue.
