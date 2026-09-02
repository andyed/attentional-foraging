# Scroll-aware saccade computation

*Established 2026-06-03. Applies to any saccade-level metric (amplitude, direction) computed from AdSERP fixations.*

## The trap

AdSERP fixations (`FPOGX/FPOGY`) are **page-space** — coordinates relative to the full-page
screenshot, with scroll already included (see `data_loader.py` docstring and root `CLAUDE.md`). This
is **correct and intended for fixation→AOI attribution**: a fixation's page-space `y` bisects directly
against page-space result-band tops.

It is a **silent trap for saccade-level metrics.** A saccade computed as the difference between two
consecutive fixations that straddle a scroll event measures **the page moving**, not the eye. The
page-space `Δy` for such a "saccade" is dominated by the scroll displacement — a vertical jump that no
eye actually made.

## Quantified impact (AdSERP, NB13)

- **~9.2%** of evaluate-phase (fixation ≥ 6) saccades span a scroll event.
- Including them **inflates the primarily-vertical fraction** and, on the survey-vs-evaluate contrast,
  **reverses its sign**:

| evaluate-phase % primarily vertical | construct |
|---|---|
| 39.2% | OLD: clamped FPOGY (below-fold gaze squashed to screen bottom → artificially *horizontal*) |
| 51.2% | naive page-space (scroll motion folded in → artificially *vertical*) |
| **48.7%** | **scroll-aware (exclude scroll-spanning saccades) — the honest value** |

- Median amplitude is far more robust: survey 107.4 px (clean) is unchanged; evaluate is 64.0 (clamp) /
  73.9 (naive page-space) / **68.9 (scroll-aware)**. The amplitude **compression** (survey ≫ evaluate)
  and the per-trial slope (ρ ≈ −0.13, 46/47 participants) hold under every construct.

## The fix

Compute saccade amplitude/direction **scroll-aware**: exclude any saccade whose time window
`(t[i-1], t[i]]` contains a scroll event. For the surviving (non-scroll-spanning) saccades,
page-space `Δy` equals the true on-screen eye-movement `Δy` exactly (no scroll happened, so the
constant scroll offset cancels in the difference). Implemented in `notebooks-v2/13_survey_phase.ipynb`
cell 3 (`bisect` over the scroll-event timestamps from `load_mouse_events`). An equivalent alternative
is to subtract the scroll offset per fixation (viewport coordinates) before differencing.

This is a conservative rule for consumers who receive page-mapped fixations rather than raw gaze.
The closest direct prior art, `eyeScrollR`, recommends inferring fixations and saccades before mapping
raw screen-space gaze into page coordinates; it warns that mapping first can turn stationary gaze
during a scroll into an apparent saccade. See the focused literature review:
[`docs/lit-notes/scroll-compensation-gaze-kinematics.md`](../lit-notes/scroll-compensation-gaze-kinematics.md).

Fixation→AOI attribution, click-rate-by-position, and pupillometry are **unaffected** — this is only
about differencing fixation positions into saccade vectors.

## Consequences

- **Retracted:** the F-pattern *verticality* decomposition (NB13 K13–K19 prior interpretation; the
  "survey is the vertical descender, evaluate is the horizontal reading cap" framing). On clean
  saccades the phases are orientation-balanced; the apparent F-shape was a coordinate artifact. This
  matches the prior `f_scan_farce` result (SERP scanning is multi-cycle back-and-forth, not a clean
  F-sweep) — the artifact is its mechanism.
- **Robust (unchanged):** the survey-phase **amplitude compression** is the real signature, and it
  survives within 46/47 participants (NB13 K20–K22).

## Cross-references

- `notebooks-v2/13_survey_phase.ipynb` — scroll-aware saccade computation + Key Claims K1–K22.
- `docs/findings.md` §3b-ii.1 — corrected narrative.
- `docs/lit-notes/scroll-compensation-gaze-kinematics.md` — focused review of HCI prior art,
  reporting gaps, and the claim boundary for AllSERP.
- `~/Documents/dev/allserp-paper/TODO.md` — proposed AllSERP §Methods/Usage caveat (the data substrate
  warning for downstream users; AllSERP is the resource paper that should document this gotcha).
- `scripts/make_f_scan_farce*.py`, `render_scan_epoch_staircase.py` — the F-pattern-as-farce evidence,
  now with a coordinate mechanism for the verticality limb.
