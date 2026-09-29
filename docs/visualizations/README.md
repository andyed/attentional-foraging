# Search process: two linked posters

**LAB · AdSERP · typed AOIs · 2,650 trials · 47 participants**

[One clock, many views](information-space-poster/index.html) follows time budgets
into a trial and its final seconds. [While the mouse waits, the eyes travel](gaze-cursor-echo/index.html)
follows sequence and timing aggregates into a gaze excursion during cursor rest.
Read the [“not a cascade” account](../not-a-cascade.md) alongside them.

| Artifact | Print / preview | Evidence |
| --- | --- | --- |
| Information space | [A0 PDF](information-space-poster/poster.pdf) · [PNG](information-space-poster/poster-preview.png) | [Methods](information-space-poster/methods.md) · [time budgets](information-space-poster/time-budgets.csv) · [aggregates](information-space-poster/summary.json) |
| Gaze–cursor sequences | [A0 PDF](gaze-cursor-echo/poster.pdf) · [PNG](gaze-cursor-echo/poster-preview.png) | [Methods](gaze-cursor-echo/methods.md) · [aggregates](gaze-cursor-echo/summary.json) · [checks and sensitivities](gaze-cursor-echo/checks.json) |
| Resting cursor | — | [aggregates and cursor-hold sensitivities](evidence/resting-cursor/summary.json) |

## Measures and scope

Both posters start at the first native mousemove and stop at the final physical
press. Spatial partitions include missing coverage in the full duration
denominator. Motion uses complete 100-ms windows. Initial-fold position is a
page-coordinate measure, not current viewport visibility. The sequence poster
also uses event counts and a common-coverage time denominator; those are labeled
separately. A recorded fixation is not proof of comprehension, and gaze-return
counts are not cursor-return counts.

Three sensitivities qualify headline numbers. The cursor logger records only
movement and a position is held for at most 2 s, so long stillness is
unavailable rather than rest; holding until the next move raises the
different-AOI share of rest time from 23.8% to 27.6%. Every first cursor visit
starts at the clock origin, so matched visit pairs that start there are
reported separately; without them gaze arrives first in 55.3% of pairs rather
than 50.1%. The illustrated pause is selected for a gaze return; 10.7% of
2–8 s cursor pauses show that pattern.

The earlier first-visit evidence in [not a cascade](../not-a-cascade.md) uses
2,606 trials and runs of consecutive fixations. Its snapshot lives in
[evidence/next-action-by-position.json](evidence/next-action-by-position.json).
It is supporting context, not another partition of the poster cohort.

## View locally

From the repository root:

```sh
python3 -m http.server 63832 --bind 127.0.0.1 --directory docs/visualizations
```

Open [the atlas](http://127.0.0.1:63832/). The HTML is self-contained and uses
relative local links. GitHub's source viewer cannot render the HTML; use the
PDF or PNG there. No publication or deployment is required to view locally.

## Rebuild and verify

The sources live in [scripts/attention_atlas](../../scripts/attention_atlas/README.md)
and run in the repository's [canonical environment](../canonical-environment.md).
Saved per-trial records (`*/trials.json.gz`) and the prior aggregate baselines
are included; raw AdSERP recordings remain in their separately downloaded dataset.

```sh
.venv/bin/python scripts/attention_atlas/verify-atlas.py
.venv/bin/python -m unittest discover -s scripts -p test_attention_atlas.py
```

`verify-atlas.py` needs no raw data. It checks links, clock conservation, the
reproduction gates in both directions, a recomputation of the common-coverage
counts, that the numbers in the pages and prose match the JSON, and that the
shipped values match [the evidence pin](evidence-pin.json). A full rebuild from
the raw recordings, and when to re-pin, are described in the scripts' README.

The [import manifest](import-manifest.json) preserves checksums of the session
artifacts as first imported on 29 September 2026. It is provenance, not a
runtime dependency. The shared website build copies the pages, figures and
summaries to `site/attention-atlas/`; per-trial records and Markdown stay in
the repository. Deployment is separate.
