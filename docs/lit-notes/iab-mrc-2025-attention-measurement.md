# IAB and MRC Attention Measurement Guidelines (Nov 2025)

**Document:** IAB and MRC Attention Measurement Guidelines
**Version:** Final v1.0, published November 2025 (public-comment draft May 2025)
**Authority:** Interactive Advertising Bureau (IAB) in collaboration with Media Rating Council (MRC)
**Developed with:** 200+ contributors across brands, agencies, publishers, and measurement vendors. Section 1 references the IAB Attention Task Force.
**PDF:** https://www.iab.com/wp-content/uploads/2025/11/IAB_MRC_Attention_Measurement_Guidelines_November_2025.pdf

## What the document does

Establishes a measurement framework for **attention** across digital and cross-media surfaces, organized around **four measurement methods**:

1. **Data signals** — impression-level behavioral data: time-in-view, scroll depth, scroll velocity / direction-changes / pauses, pointer hover frequency, clicks, swipes, audible time, captions enabled (§5)
2. **Visual tracking** — eye-tracking, gaze-on-screen, focal vs peripheral attention (§6)
3. **Physiological and neurological observations** — biometrics, EEG, GSR (§7)
4. **Panel and survey-based measurement** (§8)

Across all four, the doc specifies minimum requirements, data-quality controls, transparency, auditing, privacy, and disclosure (§9–§15).

## The strategically important provision: attention before viewability

§4 includes an explicit carve-out for **measuring attention without or before the MRC viewability condition has been met**, under four conditions (paraphrased; quotes ≤125 chars):

1. Standard compliant attention measurement *with* viewability is reported in parallel and accrues only after viewability is met.
2. Attention without/before viewability is separately presented and labeled non-standard/diagnostic.
3. Ads qualifying for non-viewable attention measurement must be at least **visible** — "any portion of the ad is on screen or in the viewport for any non-zero time."
4. Such ads must be based on compliant begin-to-render impressions (and for video/audio, post-buffer playback).

The doc is explicit that "use of viewability as a base for attention measurement enforces a minimum time threshold (one second for display and two continuous seconds for video), whereas attention measurement without viewability includes no such minimum time threshold." (line ~422 of extracted text)

**This is the gap the per-AOI deliberation episode addresses.** The standard now formally invites attention measurement before the MRC binary viewability threshold is met, but does not prescribe *how* to do that beyond "any non-zero visible time." Our cursor episode is a candidate operationalization: it produces a graded ordinal label (clicked / deferred / eval-rejected / not-approached) on residence that has not yet satisfied the binary viewability gate, derived from cursor-derivative features over AOI-relative distance.

## Data-signal metrics the doc explicitly names

Relevant to our work, all defined in §4–§5:

- **Pointer hover frequency** over an ad — line 1749 of the extracted text: "Measures pointer hover frequency over an ad..." This is the deployed industrial recognition of cursor-side residence as an attention signal.
- **Time-in-view** — per-AOI dwell at the impression level.
- **Scroll depth, speed, direction changes, pauses** — explicitly listed as engagement metrics. The doc treats scroll *behavior* (not just position) as an attention signal — close kin to our cursor-derivative-ordered features.
- **Interaction Rate** (incl. hover as a top interaction type) — see example metrics around line 1793.

The doc also flags **limitations** for several media channels: "Lacks real-time viewability or interaction data," "No device-level data; static formats lack viewability signals." These are the gaps we don't address but worth noting.

## Connection to our work

The 2025 standard is the most strategically valuable cite of the three (Kim 2016, MRC 2014, this) because:

- It is a **current** standards document, not a settled one. Citing it positions the work as engaging an active industrial debate, not retrofitting onto a legacy spec.
- It **explicitly endorses** attention measurement before viewability, which is precisely what our episode-based approach does for SERPs (we recover deferred-class results that never satisfy the click-as-attention binary).
- It **explicitly names** cursor hover, scroll behavior, and time-in-view as data-signal attention metrics — placing our seven-feature M4 inside the standard's frame rather than orthogonal to it.
- The ad-asymmetry in §5.3.3 (+0.100 vs +0.047 ΔMRR on ad- vs organic-clicked trials) is **exactly** the kind of finer-grained attention layer this standard asks for: ads are where binary viewability governs measurement, where the deferred-class layer is most informative, and where graded operating points carry real money.

## How a v2/camera-ready citation would slot in

Single-sentence anchor in §6 mobile-extension paragraph OR §5.3.3 ad-asymmetry sentence:

> "Industrial attention measurement standards now explicitly endorse data-signal attention metrics including cursor hover, scroll behavior, and per-AOI time-in-view, and admit attention reporting before the binary viewability threshold is met [IAB/MRC 2025]; the per-result deliberation episode is a candidate operationalization of the graded layer the standard invites."

Or the ad-specific version for §5.3.3:

> "This asymmetry aligns with the industrial premise that ad impressions require a stronger residence signal than organic results to count as attended [MRC 2015]; the 2025 IAB/MRC standard now invites graded extensions of that binary threshold [IAB/MRC 2025], and the deferred-class layer is a candidate substrate."

Both cost two new bib entries (mrc2015viewable + iabmrc2025attention) and one or two body sentences. Page-count risk small but non-zero — defer to v2/camera-ready.

## BibTeX (stub — verify URL stability before camera-ready)

```bibtex
@techreport{iabmrc2025attention,
  author      = {{Interactive Advertising Bureau} and {Media Rating Council}},
  title       = {{IAB} and {MRC} Attention Measurement Guidelines, Final Version 1.0},
  institution = {Interactive Advertising Bureau and Media Rating Council},
  year        = {2025},
  month       = {11},
  note        = {URL: \url{https://www.iab.com/wp-content/uploads/2025/11/IAB_MRC_Attention_Measurement_Guidelines_November_2025.pdf}},
}
```
