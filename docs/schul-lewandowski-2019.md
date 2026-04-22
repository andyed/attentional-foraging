# Schultheiß & Lewandowski 2019 — mobile-layout SERP eye-tracking dataset

**Zenodo:** <https://zenodo.org/records/3407551> — DOI `10.5281/zenodo.3407551`
**Paper:** Schultheiß, S. & Lewandowski, D. (2019). *How users' knowledge of advertisements influences their viewing and selection behaviour in search engines.*
**Investigation:** 2026-04-21 scout + schema validation; 2026-04-22 mobile caveat discovered.

## Why we pulled it

Approach-retreat on AdSERP is desktop-only. We wanted a second dataset with a **mobile-layout** arm to see whether AR signatures transfer across viewport widths. This is the closest available match on Zenodo — n=100, same queries across PC and "smartphone" SERPs, same participants within-subject.

## What landed (~43 GB total)

| File | Size | Purpose |
|---|---|---|
| `AOI metrics.xlsx` | 2.7 MB | Per-(respondent × stimulus × AOI) summary metrics (TTFF, dwell, revisits). Summary layer only — no temporal streams. |
| `Clicks.zip` | 50 KB | Per-trial terminal click as AOI code. |
| `SERPs and Image Maps.zip` | 26 MB | Reference SERP PNGs + HTML `<map>` AOI polygons, per (Qxx × device × block). |
| `Questionnaire.zip` | 38 KB | Questionnaire responses. |
| `D1_Students.zip` | 682 MB | Scout pull. Desktop condition. 26 subjects, validated schema. |
| `M1_Students.zip` | 10.6 GB | Mobile block 1, students cohort. |
| `M1_noStudents.zip` | 8.7 GB | Mobile block 1, non-students cohort. |
| `M2_Students.zip` | 9.3 GB | Mobile block 2, students cohort. |
| `M2_noStudents.zip` | 8.4 GB | Mobile block 2, non-students cohort. |
| D2 × {Students, noStudents} | ~3 GB | Not pulled. Desktop block 2. |

Destination on disk: `~/Downloads/schultheiss-lewandowski-2019/` on galactica (the iMac). All files MD5-verified against Zenodo.

## Validated schema

**Export platform:** iMotions Attention Tool v7.0 (Lab64 study export), Tobii hardware.

**Unit of recording is the session (per participant × per block), not the stimulus.** One session covers all ~10 stimuli in that block back-to-back. iMotions writes:

- **One WMV per session** (`Capture/sc_r{PID}__s{SID}.wmv`). For M1 participant 1042, a single 166.8 s recording covers all 10 Mobile Block 1 stimuli. `wmv3` codec, ffmpeg decodes fine. **~15–17 fps.**
  - Desktop: 1280×1024 (screen res).
  - Mobile: **1600×896 desktop capture** with a mobile-width browser window (~650 px wide) centered in frame — see caveat below.

- **One RawGaze recording per session, duplicated byte-for-byte into each `Qxx_{D,M}/Gaze/RawGaze.{PID}.csv`.** Verified 2026-04-22: for participant 1042, all 10 copies (Q01_M..Q10_M) share identical data rows; only the first-line stimulus-reference header differs (`M1_Scene[1].jpg` vs `M1_Scene[5].jpg` etc.). This is iMotions' AOI-analysis export format — one copy per AOI context, not one per trial. Three columns: `time_ms, gaze_x_px, gaze_y_px`. Screen coordinates. ~60 Hz (17 ms median interval). 99% valid samples. `-1, -1` = missing gaze.

- **Processed gaze `.../Qxx_{D,M}/Gaze/{PID}.csv`** — iMotions AOI-hit intervals. **Effectively empty.** `MovingAOIType=2` used SIFT-like image-feature tracking against the static reference JPG, which never matches because the study displayed *live Google SERPs*, not the reference images. Every row is `False` across probed subjects. Do not rely on these.

- **Per-stimulus segmentation is in `scripts/schul_fragments.py`** (implemented 2026-04-22). `Data.xml` carries 243 `<SceneFragment>` blocks in M1 (25 subjects × ~10 stimuli, minus skips). Each has `<SceneId>` (= stimulus ID), `<RespondentId>`, `<FragmentStart>`, `<FragmentEnd>` (ms in session clock). The 11 `<Stimuli>` blocks map stimulus ID → display name (`1016` → `Q01_M`, ..., `1025` → `Q10_M`, `1000` → whole-block "M1" scene container). The replay builder uses this to slice session recordings down to single-stimulus windows.

- **Completeness note:** many subjects viewed fewer than 10 stimuli. Participant 1042 in M1 has 8 fragments (skipped Q02 and Q09). Filter for complete subjects or tolerate missingness depending on analysis.

- **Stimulus-ID in WMV filename** (`sc_r001042__s001000.wmv`) is the *session/scene-recording ID*, not a per-stimulus reference. Don't try to read `s001000` as "stimulus 1000 = Q01".

- `Data.xml` — iMotions study metadata. Contains `MouseClicks`, `KeyStroke`, `Marker`, `FragmentStart/End` (trial boundaries), `SampleRate`, `EyeTrackerModel`. **Zero `Scroll` tags** — no native scroll log anywhere in the export.

**Clock sync is free.** WMV duration and RawGaze duration match to within 50 ms on the same (participant, stimulus). Both on the iMotions study clock.

**File naming:** `sc_r001042__s001000.wmv` = respondent 1042, stimulus 1000. Joins 1:1 with `RawGaze.1042.csv` under the corresponding `Qxx_M` folder (stimulus-ID → Q-label mapping empirically recoverable via duration match).

## AOI geometry (the rich surprise)

From `ImageMaps_{Mobile,Desktop}_Block{1,2}.txt`: standard HTML `<map>` format, one `<map>` per stimulus. **Coordinates are page-space pixels** (mobile pages reach y=7076 on Q05 — ~10 screens of scroll).

AOI vocabulary goes well beyond organic rank:

| Prefix | Meaning |
|---|---|
| `tt01`, `tt02` | Top text ads |
| `tt01a`-`tt01d` | Sitelinks / sub-elements within an ad |
| `tto2`, `tto2a`-`b` | Second text-ad cluster |
| `o01`-`o10` | Organic results |
| `o01a`-`o01c` etc. | Rich snippet segments (PAA chunks, inline cards) |
| `o02a`-`o02g` (Q05) | Detailed breakdown of a featured organic result |
| `s01`-`s03` | Shopping carousel elements |
| `tb01`, `tb02` | Related-searches / bottom blocks |

Mobile pages are **~720 px wide** (x-max ≤ 706). Desktop width matches 1280×1024 capture.

## The critical caveat: "mobile" ≠ mobile device

Verified 2026-04-22 via M1 scout:

- Mobile WMVs are **1600×896 desktop captures**, not phone-native recordings.
- RawGaze x range for mobile sample (1042, Q05_M): 491–1140 (~650 px span, centered in frame).
- Mobile gaze stays within the central ~650-px band of a 1600-px desktop display.

**The setup:** Tobii desktop eye-tracker watching participants view a phone-width browser window centered on a PC monitor. Participants scrolled with **mouse wheel / keyboard**, not touch. `MouseClicks` + `KeyStroke` entries in `Data.xml` literally *are* the scroll events.

**Valid uses of the "mobile" arm:**
- Narrow-viewport ranked-list attention
- Mobile-layout AOI dwell distribution
- Scroll-driven AR in a mobile UI
- **Direct within-subject comparison of mobile-layout vs desktop-layout,** controlling input modality

**Invalid uses:**
- Claims about touch trajectory
- Flick/inertia scroll physics
- Thumb-reach ergonomics
- "Mobile device behavior" in any in-the-wild sense

**Paper framing:** call it **"mobile-layout SERP under desktop input"** — not "mobile device behavior." 2019 lab-eye-tracking was technologically constrained; this is standard for the era. It still isolates viewport width from input modality cleanly, which is its own analytic asset.

## Usable signal inventory

| Signal | Source | Status |
|---|---|---|
| Raw gaze (x, y, t) screen-coords, ~60 Hz | `RawGaze.*.csv` | ✅ clean, 99% valid |
| Scroll position over time | **Must derive via CV from WMV frames** | ⚠️ standard phase-correlate / template-match pipeline |
| Tap/click on AOI | `Clicks.zip` (one terminal click per trial) | ✅ |
| AOI polygon geometry | `ImageMaps_*.txt` | ✅ rich sub-elements |
| Mouse + keyboard events | `Data.xml` (`MouseClicks`, `KeyStroke`) | ✅ this is how "mobile" scroll happens |
| Trial start/end sync | `Markers` / `FragmentStart/End` in `Data.xml` | ✅ |

## iMotions ID ↔ external P/W code mapping (reconstructed)

The Zenodo deposit does not ship a direct mapping between iMotions numeric respondent IDs (1013..1043) and the external P/W study codes (P02, W15, etc.) used in `Clicks.zip`, `Questionnaire.zip`, and `AOI metrics.xlsx`. We've reconstructed it via a dwell-sum constraint.

**Method** (`scripts/schul_code_mapping.py`, implemented 2026-04-22):

For each iMotions respondent, define the per-stimulus *fragment duration* from `Data.xml` `<SceneFragment>` blocks. For each external code, compute the per-stimulus *sum of TimeSpent-G* across all AOIs from AOI metrics.xlsx. For the true match:

- Every shared (stimulus) gap = xlsx_sum − fragment_duration must be ≤ 0, because xlsx sums only count gaze time *inside defined AOIs*, which must be less than or equal to the total time the stimulus was on screen.
- Among constraint-satisfying candidates, the true match has the smallest total |gap|, typically 2-5 s per trial (representing time gaze was valid but outside any defined AOI — whitespace, margins).

**Validation:** on M1_Students (25 subjects), 22 of 25 match with ≥ 2 s margin to second-best (high confidence). 3 are ambiguous (margin < 2 s) — primarily subjects with sparse fragments (e.g. 1013, 1023, 1030 have 6 fragments). The worst iMotions glitch (respondent 1030 with session order [3,4,5,6,7,8,9,10,1,2]) has 858 s total |gap|, suggesting corrupted fragment data for that subject specifically.

**Aufgabe ↔ Qxx.** The `Aufgabe` column in Clicks CSVs is Q-number: Aufgabe 5 corresponds to Q05_M on M1, Q05_D on D1, etc. This is inferred from the consistency of the dwell-sum match + the semantics of "Aufgabe" (German "task").

**Click lookup:** once the mapping is known, a single participant × stimulus click is `clicks[external_code][Aufgabe=stim_num]`. Example: iMotions 1042 ↔ P14 ↔ `P14_m1_tasks.csv` row where Aufgabe=5 → clicked `o01` on Q05_M.

## AR pipeline (implemented)

1. ✅ **`scripts/schul_fragments.py`** — parse `Data.xml` `<SceneFragment>` blocks → per-(participant × block) stimulus boundaries.
2. ✅ **`scripts/schul_code_mapping.py`** — reconstruct iMotions ID ↔ external P/W code mapping via dwell-sum constraint (22/25 M1 subjects high-confidence).
3. ✅ **`scripts/schul_scroll_recovery.py`** — per-frame scroll offset via high-pass grayscale template match + DP continuity path. Output at ~15 fps; match scores 0.15–0.30 (low absolute but temporally stable after DP).
4. ✅ **`scripts/schul_aoi_hits.py`** — projects 60 Hz gaze into page space via interpolated scroll offset, runs smallest-area-contains point-in-polygon against AOI rects, emits per-sample AOI id + summary (dwell, visits, revisits, transitions, visit_log per AOI). Includes AOI rank annotation (organic / text_ad / shopping / tail + numeric rank).
5. ✅ **`build_schul_replay.py`** + **`docs/schul-replay/index.html`** — slices session to one (participant × stimulus) trial, transcodes WMV → H.264, wires everything together. UI: WMV with native-coord gaze overlay on the left; reference SERP with AOI polygons + click highlight + moving viewport rect + page-space gaze dot on the middle; live AOI-highlight + dwell/visits/transitions table on the right.

### First real AR pattern from this dataset

Q05_M, respondent 1042 = P14 (clicked `o01`, 10.1 s trial): 245 gaze samples, 3261 ms in AOIs, 7 filtered visits, 49 raw transitions.

- `o01` (clicked target, organic rank 1): 2703 ms dwell, 4 visits, **3 revisits** — participant kept coming back.
- `tt01d` (ad sitelink): 445 ms, 2 visits, 1 revisit.
- `o02` (organic rank 2): 113 ms, 1 late brief visit.

Classic approach-retreat around the eventual winner: early alternation with ad sitelinks, one late glance at o02, repeated re-landing on o01 before committing.

### Open

- Aggregate AR analysis across all subjects × all stimuli (the CIKM-relevant step).
- AR directionality metric: transitions to lower-rank vs higher-rank AOIs at fixation-to-fixation cadence.
- Mobile-layout vs desktop-layout within-subject comparison (run the full pipeline on D1/D2 arms too — only Phase 2 desktop scout is downloaded so far; full D1/D2 zips are ~3 GB additional).
- Interpolate scroll at fixation boundaries rather than raw 60 Hz samples (reduces scroll-mid-saccade aliasing).

## Scroll-recovery notes

The phone-mirror setup is a physical phone on a dark stand recorded by a webcam (not a captured phone screen). This means:

- Reference PNG (720w × up to ~8800h, clean Google SERP) differs materially from the live SERP rendered on the phone (blue tint, dynamic ads, compressed JPEG artifacts).
- Raw NCC scores are intrinsically low (0.13–0.31 on Q05_M_1042). Per-frame argmax alone is unreliable — spurious y=5000+ jumps early in the sequence.
- **Robustness comes from temporal continuity.** `schul_scroll_recovery.py` collects top-K candidate offsets per frame (K=8, NMS gap 80 px) and runs a Viterbi-style DP minimizing `Σ −score + w × |Δy|` across frames. After DP + median smoothing, the trajectory is clean (y=321..917 over 10 s, consistent with the click target `o01` at page y=1030..1196 = center of viewport).
- The phone screen is auto-detected per-session (fixed physical setup); chrome regions (status bar, nav buttons) are stripped with a fixed padding (top 50, bottom 50 px) before matching.

## LAB / WILD positioning

Per the project's LAB/WILD convention (see `CLAUDE.md`), neither existing label covers Schul cleanly:

- LAB is currently defined as **AdSERP** (Latifzadeh, Gwizdka, Leiva SIGIR 2025). Gazepoint GP3 HD 150 Hz, pupil, full scroll signal, SERP HTML + ad bboxes.
- WILD is currently **ACD** (Leiva & Arapakis 2020). Cursor + click only, crowdsourced.

Schul is a *third regime:* lab-grade eye tracking (Tobii via iMotions, ~60 Hz, no pupil exported), desktop-input on a mobile-layout browser window, HTML image-maps with sub-element AOIs, no native scroll log. Proposed tag convention: **`[LAB-SCHUL]`** when citing a Schul-specific number, reserving plain **`[LAB]`** for AdSERP until/unless we re-tag. Use `[LAB, LAB-SCHUL]` when a claim has been verified in both.

Use cases where `[LAB-SCHUL]` adds genuine leverage:

- **Viewport-width as an independent variable** (AdSERP and ACD are both desktop-wide only).
- **Sub-element AOIs** (`o02a-g`, `tt01a-d`, shopping `s01-03`) — finer than AdSERP's ad/organic bboxes.
- **Scroll as explicit input** — `MouseClicks` + `KeyStroke` in Data.xml *are* the scroll sequence, so scroll can be analyzed as a discrete action stream rather than a continuous signal.

## What this dataset can support in the CIKM 2026 paper

- Generalization of AR from AdSERP (desktop, mouse) → Schul (desktop, mouse, mobile-layout).
- Bands vs continuous viewport analytics: mobile layout has longer pages (up to 7076 px = ~10 viewports) — much more AR runway than AdSERP.
- Sub-element AOI resolution (PAA, sitelinks, carousels) gives finer-grained retreat targets than AdSERP's rank-level AOIs.
- Within-subject mobile-layout vs desktop-layout is the only clean viewport-width comparison available.

## What it cannot support

- Real touch-mobile behavior claims — gap still open on Zenodo as of 2026-04-21 search.
- Sample-rate studies below 60 Hz (gaze is already near floor).
- Anything depending on native scroll events — must be CV-derived.

## Replay

A minimal gaze-on-video replay app lives at `docs/schul-replay/`. Run `scripts/build_schul_replay.py` once to stage one trial's assets; open `docs/schul-replay/index.html` to inspect. See that README for usage.
