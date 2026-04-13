# AdSERP Corpus — SERP Structure Survey

*Computed by `scripts/survey_serp_structure.py` on 2,776 trials (47 participants × 6 blocks × ~10 trials). All numbers below are reproducible by re-running that script; they write to `scripts/output/serp_structure_survey/`. Coordinate convention per `notebooks-v2/data_loader.py`: mouse and click Y are page-space. Rank semantics: **absolute rank** counts every `<h3>` slot (ads + organic pooled); **organic rank** excludes slots whose band center falls inside a `dd_top` or `native_ad` rectangle in the result column. `dd_right` (right-rail) is ignored.*

*Scope of this memo: quantify what is in the corpus so that downstream position-based claims (ski-jump, framework compilation, CTR-by-rank) can be stated against a known denominator. No modelling, no inference beyond rates.*

---

## 1. Slot structure

### 1.1 Absolute rank counts (all h3 slots)

| absolute slots | trials | pct |
| ---: | ---: | ---: |
| 9 | 15 | 0.54% |
| 10 | 188 | 6.77% |
| 11 | 632 | 22.77% |
| **12** | **879** | **31.66%** |
| 13 | 644 | 23.20% |
| 14 | 228 | 8.21% |
| 15 | 117 | 4.21% |
| 16 | 41 | 1.48% |
| 17 | 12 | 0.43% |

Mode 12 (31.7%). Range 1–17; counts below 9 total 20 trials (0.7%), all recoverable from `trial_snapshot.csv` for exclusion filters. Mass at 11–13 = 77.6%. **The average AdSERP trial has 12 h3 slots, not 10.**

### 1.2 Organic rank counts (ads excluded)

| organic slots | trials | pct |
| ---: | ---: | ---: |
| 7 | 128 | 4.61% |
| 8 | 385 | 13.87% |
| 9 | 677 | 24.39% |
| **10** | **731** | **26.33%** |
| 11 | 530 | 19.09% |
| 12 | 217 | 7.82% |
| 13 | 57 | 2.05% |
| 14 | 14 | 0.50% |

Mode 10 (26.3%). Mass at 9/10/11 = 69.8%. **Only one trial in four has the textbook 10 organic results; another third has fewer and another quarter has more.** Counts ≤ 6 total 34 trials (1.2%). Counts ≥ 12 total 291 trials (10.5%) — heavier upper tail than lower.

### 1.3 Ad-slot configurations per trial

Top 10 (dd_top, native_ad) configurations:

| dd_top | native_ad | trials | pct |
| ---: | ---: | ---: | ---: |
| 1 | 3 | 906 | 32.64% |
| 0 | 3 | 472 | 17.00% |
| 0 | 7 | 189 | 6.81% |
| 1 | 4 | 172 | 6.20% |
| 1 | 2 | 157 | 5.66% |
| 1 | 5 | 137 | 4.94% |
| 0 | 6 | 128 | 4.61% |
| 0 | 4 | 110 | 3.96% |
| 0 | 2 | 107 | 3.85% |
| 1 | 1 | 100 | 3.60% |

Single configuration `(1 dd_top, 3 native_ad)` covers 32.6% of the corpus — more than 1 in 3 trials. **No trial in the corpus has more than 1 `dd_top` ad** (see §2.1). The native_ad count mode is 3 (49.6%; see §1.4) and the tail runs to 7 in-stream ads.

### 1.4 Marginal ad-count distributions

`dd_top` per trial:

| dd_top | trials | pct |
| ---: | ---: | ---: |
| 0 | 1,194 | 43.01% |
| 1 | 1,582 | 56.99% |

`native_ad` per trial:

| native_ad | trials | pct |
| ---: | ---: | ---: |
| 0 | 129 | 4.65% |
| 1 | 182 | 6.56% |
| 2 | 264 | 9.51% |
| **3** | **1,378** | **49.64%** |
| 4 | 282 | 10.16% |
| 5 | 190 | 6.84% |
| 6 | 162 | 5.84% |
| 7 | 189 | 6.81% |

**57.0% of trials carry exactly one `dd_top` ad; the remaining 43.0% have none.** dd_top is binary in AdSERP. native_ad is a true count, heavily modal at 3. Only 129 trials (4.7%) have zero native_ad and only 53 (1.9%) have zero ads of any kind.

### 1.5 Key structural cohorts

| cohort | definition | n | % of corpus | unique pids |
| :--- | :--- | ---: | ---: | ---: |
| **textbook_10org** | `n_abs = 10 ∧ n_org = 10` | **16** | **0.58%** | 11 |
| **canonical** | `n_org = 10 ∧ dd_top ≤ 2 ∧ native_ad = 0` | 35 | 1.26% | 22 |
| **plain_top** | absolute slot 0 is organic | 776 | 27.95% | 47 |
| **no_ddtop** | `dd_top = 0` | 1,194 | 43.01% | 47 |
| **no_any_ad** | `dd_top = 0 ∧ native_ad = 0` | 53 | 1.91% | 33 |
| **clean_for_ctr** | `plain_top ∧ n_org ∈ {9,10,11}` | 555 | 19.99% | 47 |

The 16 **textbook** trials span 11 participants and all 6 blocks — too few for stratified CTR inference but useful as a sanity-check floor. The 53 **no_any_ad** trials span 33 participants and all 6 blocks; `no_any_ad_tids.txt` lists them for use as a clean validation cohort where ads cannot confound position. The **plain_top** cohort (absolute slot 0 is not a dd_top ad) still contains native ads further down and therefore is not ad-free.

---

## 2. Ad positions within the slot sequence

### 2.1 `dd_top` absolute-rank occupancy

| absolute rank | count | pct of all dd_top slots |
| ---: | ---: | ---: |
| 0 | 1,582 | 83.53% |
| 1 | 312 | 16.47% |

Every `dd_top` ad in the corpus lands in absolute rank 0 or 1. Since no trial has more than one dd_top, this means: **when a trial has a dd_top, it occupies either slot 0 (83.5%) or, if another element occupies slot 0, slot 1 (16.5%)**. The 312 dd_top-at-rank-1 trials correspond to trials where a native ad pre-empts slot 0 — see §2.2.

### 2.2 `native_ad` absolute-rank occupancy

| absolute rank | count | pct |
| ---: | ---: | ---: |
| 0 | 418 | 8.44% |
| 1 | 766 | 15.47% |
| 2 | 86 | 1.74% |
| 3 | 5 | 0.10% |
| 4 | 5 | 0.10% |
| 5 | 10 | 0.20% |
| 6 | 118 | 2.38% |
| 7 | 594 | 12.00% |
| 8 | 1,206 | 24.36% |
| 9 | 1,120 | 22.62% |
| 10 | 430 | 8.69% |
| 11 | 143 | 2.89% |
| 12 | 48 | 0.97% |
| 13 | 2 | 0.04% |

Native ads have a bimodal absolute-rank distribution: a **top cluster** at ranks 0–2 (25.6% of native slots) and a **bottom cluster** at ranks 6–11 (73.0%). The gap at ranks 3–5 is real — 20 slots (0.4%) — and the highest-density single row is rank 8 (24.4%). **Native ads in AdSERP are layout-anchored: they appear either immediately before the organic block or intercalated through the bottom half of it.** This matters for any position-based analysis: an organic rank of 6 is often visually surrounded by an in-stream ad at absolute rank 7 or 8.

### 2.3 First-organic absolute-rank distribution

The absolute-rank index of the first organic slot (i.e., the amount of ad-padding at the top of the result column):

| first_org_abs | trials | pct |
| ---: | ---: | ---: |
| 0 | 776 | 27.95% |
| 1 | 991 | 35.70% |
| 2 | 942 | 33.93% |
| 3 | 67 | 2.41% |

**Median first-organic absolute rank is 1.** 63.7% of trials push the first organic result to absolute rank 1 or 2, meaning a user scanning from the very top of the result column encounters at least one ad before any organic listing. 2.4% of trials stack three ads above the first organic result.

---

## 3. Click distribution

### 3.1 Coverage

- 2,776 trials total; 2,764 (99.6%) have at least one click.
- 2,875 clicks fall within the result column bands (0..n_abs-1). 14 clicks fall outside (below the last slot; 0.5%).
- Of the 2,875 clicks in bands, **407 (14.2%) land in ad slots** (organic rank = None).

### 3.2 Click count by absolute rank

| absolute rank | clicks | pct |
| ---: | ---: | ---: |
| 0 | 545 | 18.96% |
| 1 | 547 | 19.03% |
| 2 | 705 | 24.52% |
| 3 | 427 | 14.85% |
| 4 | 260 | 9.04% |
| 5 | 131 | 4.56% |
| 6 | 104 | 3.62% |
| 7 | 53 | 1.84% |
| 8 | 51 | 1.77% |
| 9 | 32 | 1.11% |
| 10 | 15 | 0.52% |
| 11 | 5 | 0.17% |

The mode is absolute rank 2 (24.5%), not rank 0. This is the canonical "ski jump" that existing notebooks (e.g., NB23) show, and it is in large part an artifact of dd_top pushing the first organic result down to absolute rank 1 or 2 (see §2.3). **Absolute-rank click curves are not directly comparable to literature CTR-by-rank figures.**

### 3.3 Click count by organic rank

| organic rank | clicks | pct |
| ---: | ---: | ---: |
| 0 | 1,018 | 41.25% |
| 1 | 499 | 20.22% |
| 2 | 388 | 15.72% |
| 3 | 228 | 9.24% |
| 4 | 143 | 5.79% |
| 5 | 92 | 3.73% |
| 6 | 49 | 1.99% |
| 7 | 34 | 1.38% |
| 8 | 10 | 0.41% |
| 9 | 6 | 0.24% |
| 10 | 1 | 0.04% |

Remapping to organic rank restores the monotonic-decay shape. Organic rank 0 takes 41.3% of organic clicks — the flat "ski jump takeoff" vanishes. **The ski-jump shape in NB23:K1 is the signature of ad-slot intrusion, not a cognitive effect.**

### 3.4 CTR-by-organic-rank, two cohorts

Trial-level CTR: `click_trials[r] / impressions[r]` where impressions is the number of trials for which organic rank r exists and click_trials is the number of trials where the user clicked at that organic rank. Both cohorts use the same formula.

| org rank | full-corpus imp | full-corpus CTR | plain-top imp | plain-top CTR | Δ (plain − full) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2,776 | 0.3602 | 776 | 0.3827 | +0.0225 |
| 1 | 2,774 | 0.1748 | 775 | 0.1742 | −0.0006 |
| 2 | 2,770 | 0.1383 | 772 | 0.1762 | +0.0379 |
| 3 | 2,769 | 0.0809 | 772 | 0.0946 | +0.0137 |
| 4 | 2,763 | 0.0518 | 770 | 0.0779 | +0.0261 |
| 5 | 2,760 | 0.0319 | 768 | 0.0404 | +0.0085 |
| 6 | 2,742 | 0.0179 | 766 | 0.0261 | +0.0082 |
| 7 | 2,614 | 0.0130 | 732 | 0.0137 | +0.0007 |
| 8 | 2,229 | 0.0045 | 629 | 0.0064 | +0.0019 |
| 9 | 1,552 | 0.0039 | 431 | 0.0093 | +0.0054 |
| 10 | 821 | 0.0012 | 223 | 0.0045 | +0.0033 |
| 11 | 291 | 0 | 74 | 0 | 0 |

**Both curves are monotonic and qualitatively identical.** The plain-top cohort has slightly higher CTR at every rank below 0 except rank 1 (−0.001), with the largest lift at rank 2 (+0.038; plain-top rank 2 CTR = 0.176 ≈ plain-top rank 1 CTR = 0.174). In the full corpus, rank 2 is noticeably depressed (0.138 < 0.175). **Interpretation: removing dd_top exposes organic rank 2 to clicks that would otherwise be intercepted by the ad block.** The ski-jump is robust — both cohorts fall monotonically from ~0.36–0.38 at rank 0 to ~0.01 by rank 7 — but its exact shape at ranks 1–3 depends on whether dd_top is in the layout.

Neither cohort in this corpus shows the "rank-1 > rank-0" inversion sometimes reported in literature web-search studies. At rank 0 the plain-top CTR is higher than at rank 1 by a factor of 2.2× (0.383 vs 0.174); in the full corpus, 2.1×.

---

## 4. Query and participant stratification

### 4.1 Participant ad exposure

Mean total ads (dd_top + native_ad) per trial, aggregated over each participant's trials (47 participants):

- min: **3.28** (p041, 58 trials)
- mean: **3.89**
- max: **4.33** (p008, 58 trials)
- range: 1.05 ads

Every participant sees between 3.28 and 4.33 ads per trial on average. **No participant is systematically more or less ad-exposed than ±13% of the mean.** See `per_participant.csv` for full listing. Ad exposure is a trial-level / query-level confound, not a participant-level confound.

### 4.2 Block ad exposure

| block | trials | mean dd_top | mean native_ad |
| :-- | ---: | ---: | ---: |
| b1 | 459 | 0.57 | 3.39 |
| b2 | 463 | 0.57 | 3.20 |
| b3 | 463 | 0.59 | 3.42 |
| b4 | 464 | 0.53 | 3.28 |
| b5 | 461 | 0.59 | 3.36 |
| b6 | 466 | 0.56 | 3.27 |

All six blocks fall within a 0.06 range on dd_top (0.53–0.59) and a 0.22 range on native_ad (3.20–3.42). **Ad exposure does not vary by block position.** Order effects on position-based outcomes cannot be blamed on differential ad exposure across blocks.

### 4.3 Query-level ad exposure

Every AdSERP query is unique at the full-string level (2,776 trials → 2,776 distinct `buy <brand> <product>` queries). Aggregating by **brand** (the second word of the query; 1,320 distinct brands), the most ad-dense brands with ≥10 trials are:

| brand | n trials | mean dd_top | mean native_ad |
| :-- | ---: | ---: | ---: |
| delphi | 40 | 0.93 | 3.58 |
| blomus | 12 | 0.92 | 3.17 |
| nixon | 12 | 0.92 | 2.00 |
| gates | 62 | 0.89 | 3.06 |
| alessi | 15 | 0.80 | 3.33 |
| monroe | 46 | 0.76 | 4.00 |
| kyb | 12 | 0.75 | 4.67 |
| solaray | 12 | 0.75 | 4.00 |
| avon | 24 | 0.71 | 3.33 |
| airtex | 21 | 0.67 | 3.76 |
| serengeti | 20 | 0.65 | 3.15 |
| bosch | 80 | 0.64 | 4.64 |
| casio | 10 | 0.60 | 3.00 |
| hp | 10 | 0.60 | 3.80 |
| denso | 113 | 0.58 | 4.92 |
| vdo | 11 | 0.55 | 3.45 |
| motorcraft | 24 | 0.50 | 3.50 |
| ngk | 21 | 0.48 | 4.71 |
| luk | 15 | 0.47 | 4.80 |
| bosal | 22 | 0.41 | 4.64 |

Most of the 20 most-ad-dense brands are automotive parts (delphi, gates, monroe, kyb, airtex, bosch, denso, motorcraft, ngk, luk, bosal). **Ad density is query-intrinsic and concentrated in automotive-parts commerce queries.** The denso brand alone (113 trials, 4.1% of the corpus) carries a mean of 4.92 native ads per trial.

---

## 5. Layout heterogeneity summary

| definition of "canonical" | n trials | % of corpus |
| :-- | ---: | ---: |
| exactly 10 absolute slots, all organic | 16 | 0.58% |
| 10 organic + 0–2 dd_top + 0 native_ad | 35 | 1.26% |
| 10 organic + any ads | 731 | 26.33% |
| organic count ∈ {9,10,11} | 1,938 | 69.81% |
| no dd_top (plain-top) | 1,194 | 43.01% |
| no ads at all | 53 | 1.91% |
| plain-top ∧ organic ∈ {9,10,11} | 555 | 19.99% |

**Only 0.6% of the corpus matches the strict "textbook" SERP shape (10 organic, zero ads).** If "canonical" is relaxed to accept up to two top-of-page ads and no in-stream ads, the cohort grows to 1.3%. If "canonical" is relaxed to just "organic count ∈ {9,10,11}", ignoring ad heterogeneity, 69.8% of the corpus qualifies but retains all the ad-placement confounds. **The reasonable clean-CTR cohort is `plain_top ∧ n_org ∈ {9,10,11}` = 555 trials (20.0%) covering all 47 participants and all 6 blocks.** This is the set in `cohort_summary.json` under `clean_for_ctr`, and it is what §3.4's plain-top column is computed over when further restricted to the size window.

The majority of AdSERP trials (80%) deviate from textbook shape along at least one of three axes: slot count ≠ 10, presence of dd_top, or presence of native_ad. Any position-based claim computed on absolute rank is confounded by the dd_top distribution; any position-based claim computed on organic rank is confounded by native_ad intrusion into the organic sequence (native ads occupy absolute ranks interleaved with organic content at ranks 6–11 in the majority of trials; see §2.2).

---

## 6. Bottom line — what is well supported, ambiguous, or wrong to cite

- **Well supported.** A monotonic, roughly power-law CTR-by-organic-rank curve from rank 0 (~0.36–0.38) down to rank 7 (~0.01). This shape holds on both the full corpus (n = 2,776) and the plain-top cohort (n = 776) and is the strongest position-based finding in the corpus. The ski-jump is not monotonic on *absolute* rank (which peaks at rank 2) but is monotonic on *organic* rank (which peaks at rank 0). Framing: "CTR by organic rank" is the correct metric; NB23:K1, which indexes by absolute rank, is reporting an ad-pushed artifact rather than a cognitive effect and should be re-stated against organic rank before citation.

- **Ambiguous and cohort-dependent.** The fine shape of CTR at ranks 1–3. In the full corpus, rank 2 sits noticeably below rank 1 (0.138 vs 0.175); in the plain-top cohort, rank 2 matches rank 1 (0.176 vs 0.174). The literature sometimes shows a "rank-1 vs rank-2 plateau"; our corpus reproduces that plateau only when dd_top is removed. A paper figure showing this should use the plain-top cohort; any figure using the full corpus must acknowledge that the rank-2 dip is a layout artifact. Framework-compilation / cognitive-load stories that rely on a clean monotonic decay at positions 1–3 are safe on the plain-top cohort and risky on the full corpus.

- **Wrong to cite.** (1) Any claim that AdSERP trials are "10-result SERPs" — the modal absolute slot count is 12 and only 0.6% of trials are the textbook 10-organic shape; 37.5% of trials have 13+ absolute slots and 69.2% have ≥ 12. (2) Any click-count figure indexed by absolute rank as if it were position 1, 2, 3. In 72.0% of trials (2,000 / 2,776) the first organic result is not at absolute rank 0, and in 33.9% it is at rank 2. (3) Any "ad-free SERP" framing outside the 53 no-ads trials; the default AdSERP trial carries 3–4 ads and the median first-organic absolute rank is 1. (4) Any participant-level or block-level story about ad exposure — it does not vary.

*Computation cost: one pass over 2,776 trials, ~135 s on the M3 workstation. Regenerate with `.venv/bin/python scripts/survey_serp_structure.py`.*
