# AdSERP vs the AI-Overview corpus — what differs, and which results should move

Opened 2026-09-14 after the first cross-corpus reversal (the fixation before a
long saccade is short on AdSERP and long on the AI-Overview pages). Until then
the two corpora had been treated as "a second lab corpus". They differ on
seven axes, and each result the CHIIR paper wants to carry across them should
be read against the axes it is sensitive to. Design facts only; every
AI-Overview *number* stays in `collab/` (Sara Allawati's data, RMIT Ethics
28583, publication needs McKay / Sanderson / Trippas permission). This table
records direction and replication status only; the collab README holds the values.

## The seven axes

| axis | AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025) | AI-Overview SERPs (Allawati et al., SIGIR 2026) |
|---|---|---|
| **task** | transactional product queries, forced choice: one final click required, no reformulation, no abandonment | informational backstory queries; abandonment with zero clicks allowed; AI Overview not clickable |
| **page top** | ranked results from the top (ads and typed widgets interleaved) | an AI Overview block above the ranked links; links start at or below the fold |
| **result geometry** | typed AOI bands, contiguous, 540 × ~80 px; ads and widgets as their own types | one rect per ranked link, taller than an AdSERP band, plus one large AI-Overview rect |
| **participants × trials** | 47 × ~60 (2,776 trials); practiced scanning by the end | 36 × 10 (342 trials); little practice |
| **tracker** | Gazepoint GP3 HD, 150 Hz; evtrack mouse and scroll telemetry | Tobii, 120 Hz (I-VT fixation filter); scroll from a browser-extension viewport-Y stream; mouse position in the same export |
| **screen** | 1280 × 1024 screen, 1403 px document, screenshot ratio ≈ 0.91 | 1920 × 1080, 1036 px viewport |
| **relevance structure** | near-uniform: every snippet matches a commercial query, bold in 92 % of snippets, cosine spread 0.02 | informational, heterogeneous by design; not yet measured with the same proxy |

Baseline fixation durations agree between the corpora (AdSERP median 191 ms;
the AI-Overview figure is in `collab/`).

**Pixels per degree, from the papers (2026-09-14).** AdSERP: a 17-inch Dell
1707FP at 1280 × 1024, pixel pitch 0.264 mm (Dell spec); the paper does not
state viewing distance, and the Gazepoint GP3 HD's operating range is 50–80 cm
with 65 cm the ideal, so **1° ≈ 43 px at 65 cm** (33 px at 50 cm, 53 px at
80 cm). Screenshot space equals screen pixels (full-screen 1280 wide), so this
applies to every AdSERP coordinate in the repo. AI-Overview corpus: Tobii Pro
Fusion, participants "sat 65 cm away", 1920 × 1080; the monitor's physical size
is not stated (asked of Sara). The Fusion mounts on panels up to 24 inches; a
24-inch 16:9 panel at 65 cm gives **1° ≈ 41 px**, a 27-inch 36 px. So the two
corpora are probably comparable at about 41–43 px per degree, and the 200 px
gate used throughout is ≈ 4.6–4.9° on both, not the 8° the repo's older 24 px/°
convention implied. That convention (findings.md §3d-ii, "48 px ≈ 2°") was an
underestimate by about 1.8×; 48 px is ≈ 1.1°.

## Which results are sensitive to which axis

| result (2026-09-14) | replicates? | axis it depends on | reading |
|---|---|---|---|
| survey phase: amplitude compression after ~5 fixations, ~1.5 s, three-phase pupil | yes, weaker | page top | the survey is spent on the overview there; the mechanism survives, its target does not |
| five-state taxonomy and peripheral tier share | yes | geometry, tracker (gate in px) | shares within a few points; a larger never-on-screen share there is the page top pushing links down |
| examination cost tiers | yes | task, practice | the tier ordering holds on both; the tiers are not a product-SERP artefact |
| continuation four ways, viewport-vs-fixation gap | yes | page top, task | same ordering and a gap of the same size on both |
| returns memory-guided (long returns, no ramp, precision ⟂ intake) | yes, with somewhat worse precision | geometry (rect height), task | the mechanism holds; the precision cost may be rect size or the informational task |
| survey leaves a proximity map (96 % vs 49 % on AdSERP) | **not testable** | page top | links are below the fold during the survey and almost none receive survey intake |
| ambient timing before long jumps (short fixation → long saccade) | **reverses** | task, practice, or page top — unseparated | forward-only on AdSERP; on the AI-Overview pages long jumps follow *longer* fixations, within the link list too |
| survey vs the block above the fold (ad block / AI Overview) | yes | page top | on both, the first five fixations are spent on the top block and skip-over is rare; the overview is the more absorbing block |
| skip is reading order + opportunity, not content | not run there | relevance structure | the AdSERP null on content is expected under uniform relevance; the informational corpus is the place the content test has power |
| bold density null | not run there | relevance structure | same |

## Consequences

1. **State the corpus with every timing or content claim.** Amplitude-conditioned
   timing and anything about content evaluation are AdSERP statements until
   shown otherwise. Structural claims (states, costs, continuation, returns) have
   replicated and can be stated as mechanisms.
2. **The informational corpus is where the content tests belong.** Every
   content-by-state test was null on AdSERP, and the relevance-structure axis
   says why: there is nothing to discriminate. If the periphery evaluates
   anything, the AI-Overview corpus, or a corpus like it, is where it would show.
   That is a replication for the RMIT paper to run, not for CHIIR to claim.
3. **Task and practice are confounded with page top across these two corpora.**
   No two-corpus comparison separates them. A third corpus that holds the page
   top fixed and varies the task, or vice versa, is the design that would.
4. **Pixels per degree is now derived, not measured.** ≈ 43 px/° on AdSERP at
   the tracker's ideal 65 cm (distance unstated in the paper), ≈ 41 px/° on the
   AI-Overview corpus if the panel is 24 inches (size unstated, asked). Gates
   stay in pixels with the conversion beside them; the degree labels in the
   2026-09-14 notes were written under 24 px/° and read about 1.8× too large.
