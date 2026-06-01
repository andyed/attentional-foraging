# OSEC-Phase Markov over Typed-AOI Episodes
## A Discovery Prospectus

**Status:** Pure discovery. Not a paper outline. No venue commitment.
**Anchor:** OSEC (Orient → Survey → Evaluate → Commit, with Regression re-entry) is the guiding principle. Everything in this document is organized around the question: *what does each OSEC phase look like at the typed-AOI/episode grain, and how does it shift across common SERP compositions?*

---

## 1. The blend in one sentence

The Markov work over SERP composition (`dd_top`, `dd_right`, `organic_cell`, etc.) and the per-AOI sessionization work share a substrate: **per-AOI episodes are the natural Markov states, OSEC phases are the natural conditioning regime, and SERP composition is the natural exogenous variable.**

Stated as a single object:

> *A composition-conditioned, phase-stratified Markov chain over typed-AOI episodes.*
> States: typed-AOI episodes (entry → dwell → exit, with derived features).
> Transitions: estimated separately within each OSEC phase × SERP composition cell.

Each piece earns its keep:

| Layer | What it contributes | Why it's needed |
|---|---|---|
| OSEC phase | Within-trial regime label (Orient/Survey/Evaluate/Commit/Regression) | The transition structure is known to differ — survey saccades are wide, evaluate saccades are narrow. A single Markov matrix would average over these and hide the structure that OSEC already established (p = 10⁻¹²⁸ for the saccade-amplitude break alone). |
| Typed-AOI episode | Markov state | Per-fixation states are too noisy (within-AOI re-fixations dominate). Per-trial states are too coarse. Episodes are the grain at which the four-class taxonomy works and at which `c7dd202f` showed 90% of the canonical LTR boost. |
| SERP composition | Conditioning factor | `8f1c7f67` showed substantial composition diversity. `a3ac66ad` showed within-carousel sub-cell promiscuity in `dd_top`. A single matrix collapsed across compositions would hide what is plainly a layout-conditional process. |
| Cell-aware bboxes | State refinement | Where useful — within `dd_top`, the cellsplit boost suggests the interesting transitions are sub-cell, not whole-AOI. For organic regions, the cell ≈ AOI. |

---

## 2. What OSEC predicts about the Markov structure

OSEC is a phase model. Each phase has known behavioral and pupillometric signatures. The Markov structure should inherit these:

### Orient (fixations 1–2)
- **Prediction:** Trivial Markov — nearly deterministic landing on the first content-bearing AOI. 58% of first fixations already land directly on a result.
- **Discovery question:** Does the landing distribution shift systematically across SERP compositions? `dd_top` lands on the carousel; `organic_cell` lands on position 1. If yes, this is a *layout-driven motor program*, not a content-driven decision.
- **Why it matters:** The CHI 2027 stored-motor-plan claim is currently supported only by within-corpus learning-effect nulls (ρ = 0.02, p = 0.30). A composition-conditional landing distribution would be a positive test of the stored-plan hypothesis.

### Survey (fixations 3–5)
- **Prediction:** High-entropy transitions. Wide saccades, low per-state dwell, broad coverage of the AOI set. Median amplitude 108px vs 74px during evaluate.
- **Discovery question:** Is the survey-phase transition matrix *uniform* over visible AOIs (true gist sampling), or is it *layout-biased* (peripheral salience pulls)? A uniform survey matrix supports the "content-independent, stored routine" claim. A layout-biased one demotes survey from "cognitive routine" to "peripheral-driven attention capture."
- **Falsifiable comparison:** Survey-phase transition entropy should *not* differ significantly by SERP composition if the survey is content-independent. If it does, the OSEC claim of content-independence needs softening.

### Evaluate (fixations 6–20)
- **Prediction:** Low-entropy, near-diagonal transition matrix. Most transitions are within-AOI (re-fixation) or to the next adjacent AOI (sequential reading). Saccade amplitude narrows to ~74px.
- **Discovery question:** How does the evaluate transition matrix's off-diagonal mass differ between `dd_top` (carousel — lateral transitions expected) and `organic_cell` (linear — vertical transitions expected)?
- **Stronger prediction:** The within-carousel promiscuity finding (`a3ac66ad`) should appear as *off-diagonal mass within the carousel block* of the evaluate-phase matrix, specifically when the SERP composition is `dd_top`.

### Commit (terminal segment) and Regression (re-entry)
- **Prediction:** Two regimes. Satisficer trajectories terminate from a low-rank AOI with short tail. Optimizer trajectories include scroll-regression re-entry (69% of trials) and terminate from a high-rank AOI.
- **Discovery question:** Does the regression-re-entry transition matrix differ from the original evaluate matrix? See §6 for the substructure decomposition (targeted / sweep / long-organic) — the surface question of "are regressions a re-run of evaluate" is too coarse given the existing AF findings.

---

## 3. Per-AOI sessionization — episode boundaries

The sessionization substrate provides the Markov states. Definitions to commit to before any extraction:

1. **Episode boundary = AOI entry/exit**, not click. (Critical to avoid the structural leak documented in [§4.1 leakage note](../../docs/null-findings/) — `final_dist`/`retreat_dist` cannot be features.)
2. **Episode is per-(trial, typed-AOI, contiguous-presence-interval).** A trial that enters AOI₃ → leaves → re-enters AOI₃ produces *two* episodes for AOI₃ in that trial. This is required for the Markov to see re-entry as a transition rather than collapse it.
3. **OSEC phase label is assigned per-episode**, by the phase that contains the episode's *entry fixation*. Episodes that straddle a phase boundary are flagged and counted in both phases (with a stratification flag) — a minority case; do not silently double-count.
4. **Cell-aware refinement** is applied only where the cellsplit work showed payoff (`dd_top` carousel). For organic, the cell ≈ the AOI.

This is the same substrate that `567833cd` (NB15, 2026-04-05) materialized for AR. The blend re-uses it; it does not require new extraction infrastructure, only OSEC-phase tagging and composition tagging on top.

---

## 4. Composition conditioning — what to estimate

The dd_top extractor (`ddb15d21`) already produces sequences for one composition. The layout-diversity sweep (`8f1c7f67`) tells us which other compositions have enough trials to support stable estimation.

Discovery scope (minimal viable):
- **Top-3 compositions by trial count** (likely `organic_cell`, `dd_top`, `dd_right`).
- **3 phases × 3 compositions × episode-state space = 9 transition matrices** to estimate.
- **Comparison object:** within-row KL divergence across compositions, per-phase. A composition-invariant phase has KL ≈ 0. A composition-driven phase has high KL.

**The headline discovery question:**

> *Which OSEC phases are layout-invariant (cognitive routine), and which are layout-driven (perception-coupled)?*

A prediction grounded in the existing OSEC story: **Survey is the most layout-invariant; Evaluate is the most layout-driven.** If this falls out cleanly, it sharpens the OSEC claim from "content-independent survey" to "layout-independent survey" — a stronger and more falsifiable statement.

If the opposite falls out, OSEC needs revision: maybe survey is more layout-coupled than the within-corpus pupil signature suggested, and the apparent content-independence is a corpus-level artifact (all SERPs share a header band).

---

## 5. Saccade direction as a behavioral fingerprint

The OSEC saccade-amplitude break (108px survey vs 74px evaluate, p = 10⁻¹²⁸) is currently a *scalar* claim. Decomposing each saccade into horizontal and vertical components gives a finer fingerprint that maps directly onto SERP layout — and explains the F-pattern's two limbs as direction signatures of the two phases.

### Direction signatures by OSEC phase (predictions)

| Phase | Expected H component | Expected V component | What the direction profile means |
|---|---|---|---|
| Orient | low | low | first landing; no prior saccade |
| Survey | **high (wide H sweeps)** | moderate | the horizontal bar of the F — wide lateral sampling across the result band |
| Evaluate | **moderate (within-result reading)** | **moderate (between-result steps)** | two superimposed processes: ~210px H reading inside a snippet, ~rank-step V to the next |
| Commit | terminal — short | terminal — short | small corrective saccade to clicked element |
| Regression | **low–moderate H** | **high negative V (upward)** | the defining signature — upward V jump |

This sharpens the OSEC claim. "Survey has wide saccades" is true but agnostic about direction. **"Survey has wide *horizontal* saccades; Evaluate has *vertical* steps between results plus small horizontal reading inside each"** is a stronger, testable claim that directly explains the F-pattern's two limbs as direction signatures rather than a single fading scan pattern.

### Direction × composition

The dd_top within-carousel promiscuity finding (`a3ac66ad`) is — explicitly — *horizontal* off-diagonal transition mass in the evaluate matrix when the SERP composition is `dd_top`. This is the prediction in concrete form:

- **`dd_top` evaluate:** higher H/V transition ratio than `organic_cell` evaluate. Within-carousel lateral sampling shows up here.
- **`dd_right` evaluate:** elevated H component on transitions *between* the organic column and the right-rail ads. (A different kind of horizontality than the carousel — a column-jump, not within-row sampling.)
- **`organic_cell` evaluate:** classic vertical reading; H component dominated by within-result horizontal reading only.

Per-composition H/V profiles per phase give a 4-dimensional fingerprint (phase × composition × H × V) — small enough to visualize as a grid, large enough to reveal layout-conditional behavior.

### Operational definition

Per saccade between fixation *i* and *i+1*:
- `dx = x[i+1] - x[i]`, `dy = y[i+1] - y[i]`
- `H_component = |dx|`, `V_component = |dy|`
- `dir_class`: one of `{horizontal, vertical, diagonal, micro}` by `|dx| vs |dy|` ratio and amplitude floor (micro = below saccade threshold).
- `V_sign`: down / up (regressions = up).

Reported per-(trial, OSEC phase, SERP composition).

---

## 6. Regression substructure

Existing AF findings already constrain the regression discovery space:

- `b2be6270` — **long organic regressions are a distinct event class** (not a heavy tail of normal regressions).
- `68525e7f` — regressions are mostly *relative-distance* (local re-checks), but **long ones have absolute top-pull** (return to a fixed top-of-page target, not a fixed step size).
- `dc0f04e5` — forward dwell does *not* predict regression distance (null).
- `af20d406` — long-regression rate is **not** an individual-difference trait (null — it's a within-trial state, not a stable participant property).

These four findings already say: short and long regressions are different operations, long ones are absolute (target-driven), short ones are relative (context-driven), and neither is a participant trait. The blend's job is to express this in transition-matrix language and stratify by phase × composition.

### Three regression subtypes (operationally defined)

| Subtype | Operational definition | Hypothesized cognitive role |
|---|---|---|
| **Local re-check** | regression to an AOI within the last ~3 fixations, small V displacement | active comparison against immediately prior candidate |
| **Sweep** | regression that traverses ≥3 AOI episodes upward, short per-episode dwell | re-orientation / loss of place |
| **Long-organic / top-pull** | regression to position 0–1 or the top control band, large V displacement, longer post-regression dwell | wholesale reconsideration (re-evaluate the set) |

These map onto distinct Markov signatures. *Local re-checks* concentrate transition mass on the most recently visited AOI (high diagonal-adjacent re-entry). *Sweeps* spread transition mass across multiple upward AOIs (high entropy upward fan). *Long-organic regressions* concentrate transition mass on a fixed target (low-entropy snap to top).

### Phase- and composition-conditional questions

1. **Are long-organic regressions phase-distinct?** If they cluster at a recoverable point in the trial (e.g., always *after* an Evaluate→Commit attempt that aborted), they're a recoverable OSEC sub-phase, not a re-run of Evaluate. Candidate label: **Reconsider** (between Evaluate and Commit in the OSEC graph).
2. **Do regressions inherit the H/V profile of their phase, or have a distinct one?** Prediction: distinct. A regression's V component is upward (by definition); its H component should be *smaller than evaluate's*, because the goal is positional re-access, not within-result reading. Falsifiable.
3. **Do compositions differ in regression mix?** `dd_top` likely has more local re-checks (lateral within-carousel "regressions" that aren't really re-checks — they're sampling). `organic_cell` likely has more long-organic top-pulls (more positional structure to return to).

### Connection to OSEC's multi-pass claim

OSEC's distinguishing claim against single-pass click models is that **examination is multi-pass and the interesting decision-making happens at the re-evaluation point** (69% of trials regress at least once; regression rate correlates r=0.66 with decision time). The blend operationalizes this: if `Long-organic / top-pull` regressions cluster pre-commit and have a distinctive transition signature, that's the *Reconsider* point made testable.

If instead all regression subtypes occur uniformly throughout the trial, the multi-pass story is weaker than OSEC currently states. Either outcome is a real finding.

---

## 7. What we explicitly do *not* claim at this stage

- **No click prediction.** The episode-Markov is a behavioral model. Hanging click outcomes off it brings the structural leak back. Reserve click-conditional analyses for a downstream object built on this one.
- **No causal claim about phase as a cognitive primitive.** OSEC is a useful decomposition with strong statistical support; the Markov work tests whether the decomposition is also Markov-coherent. If the within-phase matrices are well-mixed and the across-phase matrices are not, that's evidence the phases are *behaviorally distinct generative regimes*, which is a stronger statement than the current decomposition supports. But this is a discovery, not a presupposition.
- **No four-paper-track commitment.** This is a discovery object that could feed any of CHI 2027 (task model), Gavindya RIPA2 (regression structure), or a fresh fourth track (composition-conditional behavioral model). Resist premature venue framing.

---

## 8. Minimum viable experiment

A single re-extraction pass that yields all downstream consumers (RIPA, LFHF, AOI-episode Markov, H/V direction profiles, regression subtype tagging) — see the prior turn on bbox sequencing. The extraction needs to emit:

**Per episode:**
- `trial_id`, `participant_id`
- `aoi_type`, `cell_id` (if applicable)
- `entry_fixation_idx`, `exit_fixation_idx`
- `osec_phase_at_entry` (Orient/Survey/Evaluate/Commit/Regression/Reconsider-candidate)
- `serp_composition` (trial-level, from `8f1c7f67` taxonomy)
- `regression_subtype` if applicable (local / sweep / long-organic)
- Episode-internal features (dwell, n_fixations, mean pupil, mean LF/HF) — *not* relative-to-click features

**Per saccade (between consecutive fixations):**
- `dx`, `dy`, `H_component`, `V_component`, `dir_class`, `V_sign`
- `from_episode_id`, `to_episode_id` (most saccades are within-episode)
- `osec_phase` (inherited from the source fixation)

From this, the downstream consumers fall out:
- **RIPA (Gavindya):** episode-level regression structure, cell-aware, with subtype labels.
- **LFHF (post-ETTAC):** phase-stratified pupil signatures at episode grain.
- **AOI-episode Markov:** 9 transition matrices and their KL comparison (phase × composition).
- **H/V direction fingerprint:** per-saccade direction profile aggregated by phase × composition; ~24-cell visualization grid.
- **Regression subtype validation:** confirms or rejects the three-subtype taxonomy using transition-mass distribution as the criterion.

**Estimated effort:** one extraction script (~1–2 days; saccade-level emission adds complexity beyond episode-only), one analysis notebook per consumer (~1–2 days each). No new instrumentation, no new data. Saccade-direction tagging is mechanical (dx/dy already computable from fixation centroids); regression-subtype tagging is the only piece that requires committed operational thresholds.

---

## 9. What would be surprising

Outcomes that would meaningfully shift the OSEC story:

1. **Survey is layout-driven.** Forces a revision from "content-independent stored routine" to "layout-driven peripheral capture."
2. **Survey's wide saccades are not predominantly horizontal.** OSEC currently implicitly maps Survey to the F's horizontal bar. If Survey-phase H/V profiles are roughly balanced (or V-dominant), the F-decomposition story needs softening — the horizontal bar may be composition-specific rather than a Survey signature.
3. **Long-organic regressions cluster at a recoverable phase point.** Promotes them from "tail of regressions" to a named OSEC sub-phase (candidate: *Reconsider*). Direct sharpening of OSEC's multi-pass claim from "happens" to "happens here, with this signature."
4. **Regression subtypes are *not* separable by transition-mass distribution.** Collapses the three-subtype taxonomy back to a continuum — `b2be6270`'s "distinct event class" finding for long-organic regressions would need re-explanation.
5. **A composition has no detectable phase structure.** Most likely candidate: a composition where the SERP is so visually flat that survey and evaluate are not distinguishable by transition entropy or H/V profile. Would indicate OSEC has a layout precondition.
6. **`dd_top` evaluate is *not* H-dominant.** Would contradict the within-carousel promiscuity finding's natural Markov interpretation — needs investigation of whether `a3ac66ad` measured something other than what it appeared to.

Outcomes that would be deflationary:

1. **All three phases have similar transition matrices across compositions.** Suggests the Markov substrate is the wrong grain — episodes wash out the phase structure.
2. **Per-trial estimation is too noisy.** Forces aggregation across participants, weakening within-trial claims.
3. **The phase labels are dominated by their boundary fixations.** If 30%+ of episodes straddle phase boundaries, the per-episode phase label is statistically unstable and the design needs revisiting.
4. **H and V components are highly correlated in every phase.** Would mean saccade-direction decomposition adds no information beyond saccade amplitude — the existing scalar story is sufficient and the directional refinement is empty.

---

## 10. Open questions for the next session

1. Are there compositions outside the top-3 with enough trials to be worth estimating? (`8f1c7f67` outputs should answer this.)
2. Is the OSEC phase boundary already implemented as a per-fixation tag in NB15 or downstream, or does it need to be derived from the saccade-amplitude / pupil signatures during extraction?
3. Does AR's `567833cd` per-AOI grain already include cell-aware bboxes, or does it need to be re-materialized?
4. Where does this object live — `attentional-foraging`, a new repo, or as a cross-cutting analysis under `cikm-leakycursor-replicate`-style scaffolding?
5. Are the operational thresholds for the three regression subtypes (`local re-check` / `sweep` / `long-organic`) already pinned in the AF code from the `b2be6270` / `68525e7f` findings, or do they need to be re-derived for the blend? (Worth grepping the regression-related scripts before re-deriving.)
6. For H/V direction class boundaries: is there a prior AF convention (saccade-amplitude floor, H-vs-V ratio cutoff), or are we picking thresholds fresh? If fresh, pre-register them before estimation.
7. Does the existing F-pattern decomposition pipeline already emit per-saccade dx/dy in a form we can reuse, or only aggregated heatmap-style outputs?

---

*Written 2026-05-24 as a discovery prospectus. No deliverables committed. Revisit after the one-pass extraction lands.*
