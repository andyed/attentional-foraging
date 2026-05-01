# Wang et al. (SIGIR 2015) PSCM & Zhang et al. (WWW 2021) CBCM — Non-sequential click models

**Papers:**
- Chao Wang, Yiqun Liu, Meng Wang, Ke Zhou, Jian-Yun Nie, Shaoping Ma. *Incorporating Non-sequential Behavior into Click Models.* SIGIR '15, pp. 283–292. DOI: [10.1145/2766462.2767712](https://doi.org/10.1145/2766462.2767712). Code: [github.com/THUIR/PSCMModel](https://github.com/THUIR/PSCMModel).
- Jingtao Zhang, Yiqun Liu, Jiaxin Mao, Min Zhang, Shaoping Ma. *Constructing a Comparison-based Click Model for Web Search.* WWW '21. THUIR PDF: [www.thuir.cn/group/~YQLiu/publications/WWW2021Zhang.pdf](http://www.thuir.cn/group/~YQLiu/publications/WWW2021Zhang.pdf).

**Group:** Yiqun Liu / THUIR (Tsinghua). Same group as `liu2014skimming` (already cited).

**Found via:** lit search 2026-04-30 prompted by Jacek Gwizdka / RIPA2 team meeting prep, when verifying OSEC §2.7's claim that forward/regressive evaluation has not been decomposed at task-model granularity. Both papers DO decompose direction at click-model granularity. The §2.7 claim still holds *for task-model granularity* but only with explicit acknowledgment of these two as the IR-side prior art.

---

## PSCM — Partially Sequential Click Model (Wang 2015)

### Key claims

- Most click models follow the *sequential examination hypothesis* — users examine results top-to-bottom in linear fashion. PSCM rejects this assumption based on eye-tracking experiments.
- Two new behavioral assumptions:
  1. Between adjacent clicks, examination is **locally unidirectional** but users may **skip** a few results and examine results at some distance from the current one, following a certain direction.
  2. Between adjacent clicks, users tend to examine in a **single direction** without changes; the direction is usually **consistent with the click direction**.
- Eye-tracking is the empirical anchor — they don't just propose the model, they ground it in observed gaze behavior.
- Improves click prediction over cascade/DBN/UBM on log data.

### What it does NOT do

- Treats direction as a **feature in the click likelihood**, not as a cognitive task state.
- No motor signatures (cursor-gaze coupling).
- No pupillometric signatures.
- No kinematic decomposition of scroll regression.
- No within-evaluation phase concept.

---

## CBCM — Comparison-Based Click Model (Zhang 2021)

### Key claims

- Builds on PSCM. Adds explicit **revisit and compare** primitives.
- Users don't just examine sequentially or even non-sequentially in a single direction — they actively *compare* between results, which involves alternating attention between candidates.
- The comparison is a behavioral primitive in the click likelihood.

### What it does NOT do

- Same gaps as PSCM: click-model framing only. Compare/revisit are features in the click likelihood, not separable cognitive states with their own motor/pupillometric signatures.

---

## Connection to OSEC

Both papers are **closest IR-side prior art** for OSEC's forward/regressive decomposition (§2.7, §5.7). They establish that:
- Non-sequential examination is empirically real and ubiquitous.
- Direction matters — there is a "with-click-direction" tendency.
- Revisits and comparisons are observable behaviors that improve click prediction.

What OSEC adds that they do not have:
- **Task-state framing.** Forward and regressive are cognitive states with separable motor (cursor-gaze tighter under regression), pupillometric (LF/HF and RIPA2 dissociation on will-regress records), and geometric (ballistic backward scrolling, ρ = 0.867; 87% to positions 0–4) signatures.
- **Kinematic decomposition.** PSCM/CBCM treat the SERP as a position vector; OSEC treats scroll regression as a single ballistic motor program with a measurable velocity profile.
- **Within-evaluation axis.** PSCM's locally-unidirectional examination is between adjacent clicks; OSEC's forward/regressive is within a single evaluation episode against a single result band.
- **Click-model independence.** OSEC's claims (e.g., per-fixation duration flat across positions; cursor-gaze reversal across phases) cannot be derived from click logs alone; PSCM/CBCM are built on click logs + sparse eye-tracking validation.

The §5.7 paragraph already pre-empts the click-model absorption argument: *"A click model can in principle absorb a 'regressive' feature as another input, but then it loses the structural point: the two modes are not two features on the same user state — they are two cognitive states with different motor kinematics, different pupillometric load profiles, different arc geometries, and different exit actions."* This is the exact response to "PSCM already does this."

---

## Adjacent and downstream

- **Borisov et al. SIGIR '18** — *A Click Sequence Model.* Neural seq2seq absorbing non-sequential patterns end-to-end without explicit direction modeling.
- **Wardenaar et al.** — Non-Sequential Neural Click Model variant.
- **Lin et al. 2022** — F-Shape Click Model for mobile multi-block pages. Explicit non-sequential structure for mobile SERPs.
- **De León Martínez et al. SIGIR '25** — RecGaze, eye-tracking on carousel interfaces; directly tests where cascade-style assumptions break.
- **Carousel paper (arXiv 2026)** — *Following the Eye-Tracking Evidence: Established Web-Search Assumptions Fail in Carousel Interfaces.* Empirical refutation of cascade for carousel UI.

---

## What to do in our papers

### Task-model paper (OSEC)

Revise §2.4 and §2.7 to cite Wang 2015 PSCM and Zhang 2021 CBCM as the click-model lane on non-sequential examination. Sample insertion in §2.4 ("Click models as implicit cost models"):

> Subsequent click models extended cascade to non-sequential examination [Wang et al. SIGIR '15 PSCM; Zhang et al. WWW '21 CBCM] using eye-tracking experiments as the empirical grounding for direction-conditioned moves and comparison primitives. These models acknowledge that strict cascade is wrong but treat direction as a feature in the click likelihood — direction is absorbed into a parameterized examination policy, not represented as a cognitive task state with separable motor or pupillometric signatures.

Then §2.7 narrative becomes:

> Within-SERP forward and regressive evaluation has been decomposed at *click-model* granularity by Wang et al. [PSCM, SIGIR '15] and Zhang et al. [CBCM, WWW '21], but not at task-model granularity by either tradition this paper draws on. PSCM/CBCM treat direction as a feature in the click likelihood; OSEC reframes forward and regressive as task states with separable motor signatures (§5.7), separable pupillometric profiles, and separable kinematic geometry (§3.5).

### CIKM 2026 paper

The §1 cascade/DBN/UBM/sequence-model paragraph needs to add PSCM/CBCM. Sample insertion after the existing "Cascade [Craswell et al., WSDM 2008], DBN [Chapelle & Zhang, WWW 2009], and UBM [Dupret & Piwowarski, SIGIR 2008]" line:

> Subsequent extensions in the THUIR/Liu lineage [Wang et al. SIGIR '15 PSCM; Zhang et al. WWW '21 CBCM] relax the strict-sequential assumption with eye-tracking-grounded direction primitives and revisit/compare moves at the click-model layer. The non-click class remains a single bin in all of them; what these models predict the user did *between* clicks is structurally a behavioral feature, not a task state.

### Approach-retreat regressions lit review

This is *the* foundational pair to cite when characterizing the relationship between approach-retreat episodes and click-model literature. PSCM's "between adjacent clicks" framing is exactly the temporal window approach-retreat operates on. The episodes approach-retreat measures are what PSCM tries to model with parameterized direction.

---

## Defensive script for Jacek's "have you read PSCM?"

> *"Yes — Wang and Liu's group decomposed forward and non-sequential examination at click-model granularity with eye-tracking grounding. Their PSCM and the 2021 CBCM treat direction as a feature in the click likelihood. My contribution is to reframe forward and regressive as cognitive task states with separable motor signatures (cursor-gaze tighter under regression), separable pupillometric profiles (LF/HF and RIPA2 dissociation on will-regress records), and separable kinematic geometry (ballistic backward scrolling, 58% of variance in apparent position effects). The click-model literature absorbs direction; the task-model layer makes it interpretable."*

---

## Open questions worth pressing on

1. Do PSCM's parameter estimates for the with-click-direction tendency align with OSEC's 87% regression-targets-to-positions-0–4 finding? (Different framings, possibly the same phenomenon.)
2. Is CBCM's revisit primitive operationalized at the AOI/result level or the position level? If the former, it's structurally closer to approach-retreat than PSCM is.
3. Has anyone in the THUIR group run PSCM/CBCM against AdSERP? (Same eye-tracking-grounded framing as the dataset, no public re-analysis I've found.)
