# Schul 2019 gaze-on-video replay (MVP)

A minimal HTML viewer for Schultheiß & Lewandowski 2019 trials. Shows a single
(participant × stimulus) trial with gaze dot overlaid on the WMV-sourced screen
recording, plus the reference SERP PNG with AOI polygons beside it.

See `docs/schul-lewandowski-2019.md` for the dataset write-up.

## Stage one trial

On the machine holding the dataset (iMac a.k.a. galactica, or copy the zip
over to this machine):

```bash
cd ~/Documents/dev/attentional-foraging

BASE=/path/to/schultheiss-lewandowski-2019   # where the zips and unzipped/ live

python3 scripts/build_schul_replay.py \
  --zip         "$BASE/M1_Students.zip" \
  --participant 1042 \
  --q           Q05_M \
  --imagemaps   "$BASE/unzipped/SERPs and Image Maps/SERPs and Image Maps/Mobile_Block1/ImageMaps_Mobile_Block1.txt" \
  --refpng      "$BASE/unzipped/SERPs and Image Maps/SERPs and Image Maps/Mobile_Block1/Q05_Mobile.png" \
  --xlsx        "$BASE/AOI metrics.xlsx" \
  --clicks-dir  "$BASE/unzipped/Clicks/Clicks"
```

The `--xlsx` + `--clicks-dir` args enable the click-AOI overlay by joining the
iMotions numeric respondent ID to the external P/W code used in Clicks.zip (the
Zenodo deposit doesn't ship this mapping — we derive it via a dwell-sum
constraint; see `scripts/schul_code_mapping.py` and `docs/schul-lewandowski-2019.md`).
Omit these args to skip click annotation.

This writes to `docs/schul-replay/data/`:
- `trial.mp4` — H.264 transcoded from the matched WMV
- `gaze.json` — `[[t_ms, x, y], ...]` from `RawGaze.{pid}.csv`
- `aois.json` — AOI polygons parsed from `ImageMaps_*.txt`
- `reference.png` — the static SERP reference image
- `meta.json` — widths, durations, paths

`data/` is git-ignored — regenerate on demand.

## Open the viewer

Browsers won't `fetch` files from `file://`. Serve the replay directory:

```bash
cd docs/schul-replay
python3 -m http.server 8791
# → http://localhost:8791/
```

(Pick any free port. 8765 is often already bound in Andy's session.)

## What you see

- **Left panel** — screen recording with the current gaze sample (cyan dot) and
  a 1.5 s trail. Coordinates are WMV-native pixels — what the Tobii actually
  reported, no projection. Playback controls + 0.5× / 1× / 2× speed.
- **Right panel** — reference SERP PNG with AOI polygons drawn from the
  ImageMap. Text ads red, organic cyan, shopping yellow, bottom blocks violet.
  Sub-element AOIs (`o02a`, `tt01b`, etc.) are labeled in place.

## How slicing works (implemented 2026-04-22)

iMotions writes one WMV and one RawGaze stream per (participant × block);
slicing to a single stimulus is post-processing. `scripts/schul_fragments.py`
parses `Data.xml`'s `<SceneFragment>` blocks — each carries
`(SceneId, RespondentId, FragmentStart, FragmentEnd)` — and `<Stimuli>` blocks
map `SceneId` → `StimuliDisplayName` (`Q04_M`, `Q05_M`, etc.). The replay
builder looks up the fragment for the requested (participant, stimulus), then
filters gaze timestamps and output-seeks ffmpeg to that window. Pass
`--no-slice` to skip it and stage the full session.

## Remaining MVP limitations

- **No gaze projection onto the reference SERP.** Gaze is in WMV screen coords;
  AOIs are in page coords of the reference PNG. Bridging requires scroll-offset
  recovery via CV frame-diff — next pipeline step.
- **No AOI-hit highlighting during playback** — blocked on scroll recovery.
  The terminal click *is* shown on the reference SERP (orange-bordered AOI).
- **Session completeness varies by subject.** In this dataset many subjects
  viewed only 8 of 10 stimuli (e.g. participant 1042 skipped Q02 and Q09).
  `build_schul_replay.py` errors with a helpful list if the requested pair is
  missing.
- **iMotions ↔ external-code mapping is derived, not authoritative.** High
  confidence (≥ 2 s margin) for 22 of 25 M1 subjects; 3 subjects are ambiguous
  (flagged as `mapping_confidence: "medium"` or `"low"` in meta.json). Ask
  Schultheiß/Lewandowski for the authoritative mapping before making causal
  claims that depend on per-subject identity.
