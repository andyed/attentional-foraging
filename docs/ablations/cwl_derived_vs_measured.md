# C/W/L's two derived terms, measured — W(i) and L(i) against the single-descent shortcut

**Tags:** `[LAB, AdSERP, typed]` · positions 0–9 on the typed map · 2,151 trials with viewport opportunity known on every slot (the continuation producer's denominator) · 47 participants · **kernel-independent** (fixation, first-pass and click only)
**Producer:** `scripts/cwl_derived_vs_measured.py` → `scripts/output/cwl_derived_vs_measured/gate_200px/summary.json` (primary) and `gate_200px_press_truncated/summary.json` (robustness: fixations at or after the last `mousedown` dropped, 14,444 of them)
**Gates (both asserted before anything is written):** G1 the first-pass reach recomputed here equals `engagement_continuation/gate_200px/summary.json` `reach.fixation_first_pass` to 1e-9 at every position (max diff 0.0); G2 per-slot gaze dwell summed under the label producer's assignment rule equals the census `total_dwell_ms` on all 28,416 slots (max diff 0.000 ms).
**Key Claims:** none yet (rows owed; cite this note and the sidecar until then)
**Generated:** 2026-09-15. Follows `engagement_continuation.md` §(a).

## Why this exists

C/W/L describes a searcher by one continuation function C(i) and derives
two further terms from it under a single forward pass: the attention weight
W(i), proportional to the probability of reaching rank i (each viewed item
gets one unit of attention), and the stopping distribution L(i), the reach
mass that does not continue. Metrics are expected gain under W. The
continuation note showed that "viewed" has five operationalisations here
and that only first-pass fixation gives C the shape the framework assumes.
This note asks the next question: given the first-pass C, do the two
*derived* terms match what the corpus measures directly? Attention is
fixation time per rank; the stop is the clicked rank, which forced choice
makes observable.

The framework is not being revised. The evaluation arithmetic needs only a
W that sums to one and an L; what is under test is the shortcut from C to
both, which assumes the searcher descends once.

## (1) W four ways

Normalised over ranks 0–9. `derived_first_pass` is the C/W/L shortcut on the
strict first-pass order; `derived_any_time` is the same shortcut on any-time
fixation reach; `measured_first_visit` is the share of fixation time that
falls in each rank's *first* visit; `measured_any_time` is the share of all
fixation time.

| rank | derived, first pass | derived, any time | measured, first visit | measured, any time | any-time − derived |
|---|---|---|---|---|---|
| 0 | 0.150 | 0.140 | 0.259 | **0.300** | +0.149 |
| 1 | 0.136 | 0.136 | 0.123 | 0.177 | +0.040 |
| 2 | 0.128 | 0.133 | 0.126 | 0.138 | +0.010 |
| 3 | 0.121 | 0.123 | 0.113 | 0.111 | −0.010 |
| 4 | 0.113 | 0.111 | 0.105 | 0.091 | −0.022 |
| 5 | 0.095 | 0.095 | 0.078 | 0.059 | −0.036 |
| 6 | 0.080 | 0.081 | 0.067 | 0.045 | −0.035 |
| 7 | 0.068 | 0.070 | 0.049 | 0.032 | −0.036 |
| 8 | 0.059 | 0.060 | 0.045 | 0.028 | −0.031 |
| 9 | 0.049 | 0.050 | 0.035 | 0.020 | −0.029 |

| gap (total variation distance) | value | participant-cluster 95 % CI |
|---|---|---|
| derived (first pass) vs measured (any time) | **0.200** | [0.173, 0.224] |
| derived (first pass) vs measured (first visit) — dwell heterogeneity | 0.109 | [0.085, 0.134] |
| measured first visit vs measured any time — what returns add | 0.107 | [0.089, 0.126] |
| derived first pass vs derived any time | 0.012 | — |

Expected rank under W: 3.55 derived (first pass), 3.60 derived (any time),
2.95 measured (first visit), **2.34 measured (any time)**. Share of all
fixation time on results that falls after a result's first visit: **0.706**.

**Reading.** The shortcut spreads attention almost flat across the top five
ranks because first-pass reach declines slowly (0.91 → 0.68). Measured
attention is twice as concentrated on rank 1 and falls faster. The gap
splits evenly: half is that a viewed item is not one unit of attention
(rank 1's first visit is longer, deep ranks' first visits are shorter), and
half is the time returns add, which lands on the top three ranks. The choice
of first-pass versus any-time reach for the shortcut barely matters (0.012);
what matters is that seven tenths of examination time is revisit time, and
the shortcut has no term for it.

## (2) L two ways, and the click against the deepest rank examined

On the same 2,151 trials, every one of which ends in a click on a typed
slot. Ranks bucketed at "9 or deeper" for both distributions. The derived
stop is the deepest first-pass rank per trial, which is exactly the
single-descent stopping point; the reach-difference form R(i) − R(i+1) is
kept in the sidecar as a secondary field because it mixes page lengths
(2,107–2,151 trials have a slot at each position).

| rank | derived stop (deepest first-pass rank) | measured stop (clicked rank) |
|---|---|---|
| 0 | 0.006 | 0.162 |
| 1 | 0.019 | 0.227 |
| 2 | 0.059 | 0.152 |
| 3 | 0.081 | 0.142 |
| 4 | 0.108 | 0.132 |
| 5 | 0.093 | 0.061 |
| 6 | 0.083 | 0.042 |
| 7 | 0.074 | 0.023 |
| 8 | 0.076 | 0.025 |
| 9+ | **0.402** | 0.033 |

Total variation 0.542. Expected stop rank: **6.51 derived vs 2.71 clicked**.

| per-trial comparison | value |
|---|---|
| click above the deepest rank fixated | **0.845** [0.806, 0.881] (1,818 of 2,151) |
| click above the deepest first-pass rank | 0.845 |
| click above the deepest rank on screen | 0.975 |
| gap, deepest fixated − clicked rank | mean 4.65, median 4 |
| per participant, share of trials with the click above the deepest rank | median 0.87, IQR [0.79, 0.93] (47 participants) |

Figure: `scripts/output/figures/cwl_stop_vs_click.png` (renderer
`scripts/render_cwl_stop_vs_click.py`; panel (a) the two distributions, panel
(b) the per-trial gap).

**Reading.** Under a single descent the searcher stops where they stop
looking, and on this corpus that is rank 10 or deeper in four trials of ten.
The harvest is three to four ranks above it in five trials of six, in every
participant. The stop the framework derives is the end of the survey; the
stop the searcher makes is a return to a result already examined. This is
the same fact as the return being the modal move from rank 2 down
(`next_action_by_position.md`) seen from the evaluation side.

**Forced-choice caveat, stated with the result.** The click here is a stop
by construction: every trial ends in one, no trial is abandoned, no query is
reformulated. L_click is therefore the harvest rank, not an abandonment
rank, and the 2018 measure's give-up decision is unobservable on AdSERP. The
comparison says where the descent ends versus where the harvest lands; it
does not say anything about stopping without a harvest, which is Sara
Allawati's corpus and paper.

## (3) Does one C generate both measured terms? (added 2026-09-17)

C/W/L is an identity: any one of C, W, L fixes the other two ($W(i{+}1)/W(i)
= C(i)$, $L(i) = W(i) - W(i{+}1)$). So the framework cannot "break" as
bookkeeping. What can fail is the assumption that the three observables
(descent, attention, harvest) are one behaviour. Reading C and L off the
*measured* any-time W:

| i → i+1 | C from first-pass reach | C implied by measured W | L implied by measured W | L clicked |
|---|---|---|---|---|
| 0 → 1 | 0.906 | **0.589** | **0.411** | 0.162 |
| 1 → 2 | 0.943 | 0.783 | 0.128 | 0.227 |
| 2 → 3 | 0.943 | 0.804 | 0.090 | 0.152 |
| 3 → 4 | 0.933 | 0.819 | 0.067 | 0.142 |
| 4 → 5 | 0.842 | 0.647 | 0.107 | 0.132 |
| 5 → 6 | 0.839 | 0.765 | 0.046 | 0.061 |
| 6 → 7 | 0.854 | 0.705 | 0.044 | 0.042 |
| 7 → 8 | 0.864 | 0.873 | 0.013 | 0.023 |
| 8 → 9 | 0.833 | 0.706 | 0.027 | 0.025 |
| 9+ | — | — | 0.065 | 0.033 |

Expected stop: 6.51 from first-pass C, **2.34 from measured W, 2.71 clicked**.
TVD between the L implied by measured W and the clicked L is 0.285 (vs 0.542
for the first-pass-derived L). RBP fits: measured W is $p = 0.748$ (TVD to
the fit 0.042); derived first-pass W is $p = 0.883$ (TVD 0.030).

**Reading.** Attention and harvest agree with each other on depth (2.3 vs
2.7 ranks) and both are well described by a geometric decay near
$p \approx 0.75$. The odd one out is the first-pass C: it describes the
survey descent, which goes to rank 10+ in 40 % of trials, and it is the term
a click-log or descent model would infer. So the formulation holds on
aggregate *if C is read as attention continuation*, and fails if C is read
as descent continuation, because the descent and the harvest are different
acts joined by a return. The residual disagreement at rank 1 (0.41 implied
vs 0.16 clicked) is what revisit-inflated attention does to a stopping term
derived from W: a quarter of all fixation time on results sits on rank 1,
much of it re-reading and survey time, and the identity reads that as
stopping there. Press truncation: expected stop 2.36 implied vs 2.71
clicked; RBP $p$ unchanged to two decimals.

## Robustness: press truncation

Fixations at or after the last `mousedown` (14,444; every trial has one) are
part of the evtrack record because the click stamp is a navigation stamp
about 1.3 s later. Dropping them:

| quantity | primary | press-truncated |
|---|---|---|
| TVD, derived vs measured any-time W | 0.200 [0.173, 0.224] | 0.194 [0.167, 0.219] |
| share of fixation time after the first visit | 0.706 | 0.689 |
| expected rank under measured W | 2.34 | 2.36 |
| TVD, derived vs clicked L | 0.542 | 0.529 |
| expected stop, derived vs clicked | 6.51 vs 2.71 | 6.45 vs 2.71 |
| click above the deepest rank fixated | 0.845 [0.806, 0.881] | 0.821 [0.779, 0.858] |
| per-participant median | 0.87 | 0.85 |

Nothing moves by more than the width of its interval. The gates are asserted
on the untruncated walk in both runs, so the truncated variant is a
re-measurement, not a re-gating.

## What this is for

Two sentences for the CHIIR §5, in the order the evidence supports them: the
framework's continuation term is well defined on the first pass, and its
per-element cost term (Azzopardi, Thomas & Craswell 2018) absorbs the returns
as cost (`engagement_continuation.md` §b: 1.7 s over four visits for a
deferred result against 0.5 s for a rejection); the two terms it usually
derives by shortcut, W and L, are where the single descent fails on this
corpus, by 0.20 of attention mass and by four ranks of stopping depth, and
the failure is the return in both cases. That is a measurement the framework
invites rather than a critique of it, and the derived-versus-measured
comparison is the evaluation-theory contribution on offer to a coauthor who
owns the framework.

**Not established.** Anything about stopping without a click; anything
about W on an informational task (relevance here is near-uniform, which is
part of why attention concentrates on rank 1); transfer of the 0.20 or the
four ranks to any other layout. The AO-SERP corpus can run this producer
unchanged once its census exists there; it has not been run.
