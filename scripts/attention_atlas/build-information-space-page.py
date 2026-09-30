"""Build the information-space poster's linked page and measurement contract.

Displayed numbers come from the summaries (via page_values for values shared
with other pages); verify-atlas.py checks that the page was rebuilt after a change.
"""
from pathlib import Path
import html
from PIL import Image
import atlas_core as core
from atlas_core import ATLAS, ROOT
import page_values
REPO='https://github.com/andyed/attentional-foraging'
O=ATLAS/'information-space-poster';S=core.read_json(O/'summary.json');R=core.read_json(O/'render-manifest.json');A=S['aggregate_ms'];T=S['total_ms'];V=page_values.values()
def p(l,k):return 100*A[l].get(k,0)/sum(A[l].values())
methods=f'''# Information-space atlas: measurement contract

Generated 27 September 2026; producers consolidated 29 September 2026 with identical results. Descriptive re-analysis of the same {V['trials']}-trial, {V['participants']}-participant cohort as the final-approach readout. An earlier poster supplied the overview-to-trace structure.

## Clock and dependent measures

The primary clock starts at the first native mousemove and ends at the final mousedown associated with the final logged click. It totals **{T/3600000:.4f} hours**. Time before the first mousemove and the logged-click delay after mousedown are outside this clock. All spatial views partition this full clock, including unavailable intervals. Every cell reports a duration share, not a share of trials, AOIs or events.

We intersect cursor event times, cursor-coverage endings, fixation starts and ends, scroll events, approach onset and 20 equal-duration trial-bin edges. Exact interval durations provide the weights. Summing any complete spatial partition reproduces the clock to floating-point precision. All target-overlap durations from the prior final-approach computation reproduce with maximum absolute error **{S['previous_reproduction_max_error_ms']:.6f} ms**.

## 01: time inside / outside an AOI

AOIs are current typed main-column rectangles with nonnegative position, using their strict x and y bounds. Plot numbering is stored position + 1, from the top of the page, with ads and widgets numbered alongside results. Cursor document coordinates are scaled into screenshot coordinates using each trial's geometry. Recorded fixation coordinates already use screenshot page space. Outside AOIs means outside all included main-column rectangles: it can include gutters, spaces between results, headers and lateral content. It does not mean off-screen or missing gaze.

A cursor sample is held until the next native mousemove or final press, with a 2,000 ms maximum hold. Longer gaps are unavailable. The logger records the cursor only when it moves, so a cursor left still for more than 2 s counts as unavailable here rather than as a location; the resting-cursor sensitivities in the sequence methods relax this. The held page-space position is not reconstructed across scroll events; this is also the prior readout's convention. Fixation coordinates apply only over the recorded fixation duration. There is no +50 ms matching slack. For overlapping fixations, the latest-starting interval takes precedence. Unavailable (no recorded fixation, or an expired cursor hold) is a separate state, and the posters use that one name for it; it can include raw gaze between fixations and is not an eye-motion classifier or a claim of tracker failure.

## 02: time above / below the initial fold

The initial fold is page y = window height × screenshot/document y scale, with page-top origin. Above is 0 ≤ y < fold; below is fold ≤ y ≤ page height. Points outside the screenshot bounds are separate, as is unavailable signal time. This is a fixed initial-fold classification. It is not current viewport visibility: below-fold content may be visible after scrolling. The screen-relative coordinate used for motion subtracts the recorded scroll offset, initially zero, held until the next scroll event.

## 03: joint gaze / cursor motion

This view has a separate, explicit denominator. It uses complete, nonoverlapping 100 ms windows within the primary clock; final partial windows ({S['motion_tail_ms']/1000:.3f} seconds in total) are omitted. A displacement estimate uses the difference between smoothed endpoint locations divided by 100 ms.

Raw BPOGX/BPOGY samples are page coordinates. At each endpoint, take the median screen-relative x and y among samples within ±20 ms. Samples must be finite, within reconstructed viewport bounds, and have at least one valid pupil flag (LPV or RPV). These are pupil-validity flags, not a provided gaze-validity flag; this is an explicit quality screen. Windows without both endpoints are excluded windows. Cursor endpoints interpolate only across gaps ≤250 ms; otherwise hold the previous sample for at most 2 s. Any window containing a scroll event is an excluded window, preventing scroll-induced page displacement from being called eye or hand movement.

Operational moving thresholds are **300 screenshot px/s for gaze** and **50 screenshot px/s for cursor**. “Still” means below these thresholds, not physiologically motionless. This is neither a saccade detector nor a direct measure of muscular eye movement. The four-cell matrix divides by classifiable motion-window duration, **{R['motion_classifiable_pct']:.2f}%** of complete-window time. Excluded-window time is stated beside it. Sensitivity views halve and double both thresholds (150/25 and 600/100 px/s). Motion labels must be interpreted with their thresholds.

## 04: together / apart

Both signals must occupy an included AOI at the same instant. Same, adjacent (position difference 1), and other AOI states divide by that classifiable both-in-AOI duration. This differs from the original {V['legacy_table']} table: that table used cursor-sample weights before the final 500 ms, y-band gaze membership and +50 ms fixation matching. This poster uses exact xy rectangles, exact overlap, the full prepress interval, and explicit missing coverage. The two tables must not be substituted for one another.

## 05: the shared clock through normalized trial time

Each trial is divided into 20 equal-duration bins. The stack shows pooled elapsed-millisecond shares within each bin. Longer trials contribute more time; this is duration-weighted, not an equal-trial average. The full stack includes both-in-AOI identity, only one signal in an AOI, both outside AOIs, and unavailable intervals. Adjacent bin widths represent 5% of a trial's own duration, not a fixed number of seconds. The stack is a descriptive distribution, not a test of a time trend.

## 06: relation to the eventual clicked AOI

The final click must hit one unique main-column AOI, and the associated mousedown must hit that same target. “Both off” in this panel means both signals are off that target; either may be in another result. This is distinct from “both outside all AOIs” in panels 04–05.

The final-approach onset is the last prepress cursor distance-to-click local maximum with ≥50 px subsequent drop and distance ≥100 px. If none exists, use the latest sample at or above that trial's median cursor-to-click distance. This is a geometric rule, not a decision-onset label. Earlier and approach phase bars each divide by their own full elapsed time, including missingness. Their denominator therefore differs from the previous readout's fixation-matched-only rates of gaze on the target with the cursor off it ({V['prior_earlier']} earlier, {V['prior_approach']} in the approach), which are linked below.

## 07–08: observed trial and close-up

Trial p047-b6-t1 is an existing worked example, retained for continuity rather than chosen to typify a population rate. The actual full-page screenshot, current typed boxes, fixation durations, native cursor path, fixed initial fold and final press are shown. Cursor paths join samples only when the gap is ≤250 ms. The last three seconds are bracketed on the main trace and enlarged into target-occupancy and motion strips. Hatched areas represent unavailable location or excluded motion windows. One trace is an example, not evidence of the prevalence of its pattern.

## Uncertainty and reproducibility

Brackets on spatial summaries and error bars on pooled participant summaries are 95% percentile confidence intervals from 2,000 participant-cluster bootstrap resamples, seed 20260927. Resampling preserves each participant's full contribution and recomputes the pooled duration ratio. Raw participant points show between-participant variation. These do not supply causal interpretations or population prevalence outside the cohort. Source hashes, exact aggregate milliseconds, per-trial states, confidence intervals and exports are saved alongside this document.

The motion sensitivity chart reports conditional classifiable-window shares. The main spatial charts report unconditional full-clock shares. Missingness is not redistributed into observed categories. AOI coverage and motion thresholds answer different dependent measures.

## Sources

- [AdSERP dataset and field definitions](https://github.com/kayhan-latifzadeh/AdSERP): BPOG and FPOG screenshot coordinates, fixation durations, pupil flags, native cursor and scroll events.
- Current local typed AOI maps: content hash 2cb789eb8febd234.
- [Prior exact-overlap aggregate](../evidence/final-approach/summary.json) and [cohort / clocks](../evidence/final-approach/trial-summary.csv).
- [Gaze and cursor sequences](../gaze-cursor-echo/).
- [Search process and the two posters](../).
- Reproducible producers in scripts/attention_atlas/: compute-information-space.py (shared rules in atlas_core.py); render-information-space.py; build-information-space-page.py; verify-atlas.py.
'''
(O/'methods.md').write_text(methods)
# A compact static page with natural anchor links for semantic zoom.
parts=[('overview-1','01 · Inside and outside AOIs','Both bars divide by the full first-mousemove-to-press clock. The hatched part is unavailable time: no recorded fixation for gaze, or an expired cursor hold for the cursor.'),
 ('overview-2','02 · Above and below the initial fold','The fold stays at the initial viewport bottom in page coordinates. Below-fold content can become visible after scrolling. This is separate from AOI membership.'),
 ('overview-3','03 · Gaze and cursor motion','The matrix divides by classifiable complete 100 ms windows. These are explicit displacement thresholds, with raw gaze rather than gaps between fixations. See threshold sensitivity below.'),
 ('overview-4','04 · Shared and separate AOIs','Condition on both signals occupying mapped AOIs at the same instant. Same / adjacent / other are strict xy assignments on the exact overlap clock.'),
 ('time-course','05 · Reassemble the whole cohort in time','All spatial states return to the same duration denominator. Each column is one twentieth of trial time; longer trials contribute more milliseconds. Hatching preserves unavailable intervals.'),
 ('click-target','06 · Condition on the eventual click','Earlier and final-approach phases use their own full clocks. Here “both off” means off the eventual clicked AOI, which may still put either signal in another result.'),
 ('observed-trial','07 · Zoom to an observed trial','The page screenshot and timeline share vertical page coordinates, AOI bands, initial fold and target. The final three seconds are bracketed for the next zoom.'),
 ('final-seconds','08 · Inspect the final seconds','Target occupancy and motion are aligned to the final physical press. Dark = on the clicked AOI; pale = off it; hatching = unavailable. Motion colours match panel 03.')]
style='''*{box-sizing:border-box}html{scroll-behavior:auto}body{margin:0;background:#fafaf8;color:#222;font:500 19px/1.55 Arial,sans-serif}main{max-width:1800px;margin:auto;padding:34px 40px}h1{font-size:44px;line-height:1.08;margin:12px 0}h2{font-size:29px;line-height:1.2}p{max-width:84ch}a{color:#173f4b;text-underline-offset:4px}a:focus-visible{outline:3px solid #782650;outline-offset:4px}nav{display:flex;flex-wrap:wrap;gap:12px 30px;margin:24px 0}nav a{min-height:44px;display:inline-flex;align-items:center}.eyebrow{font-size:16px;letter-spacing:.05em}.poster{position:relative;line-height:0;margin:28px 0}.poster img{display:block;width:100%;height:auto}.hotspot{position:absolute;border:2px solid transparent;display:block}.hotspot:hover,.hotspot:focus-visible{border-color:#782650;background:#78265008}.detail{scroll-margin-top:25px;border-top:1px solid #8c8d86;padding:26px 0 40px;margin:22px 0}.detail img{display:block;max-width:100%;height:auto;max-height:850px;object-fit:contain;object-position:left}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px 48px}.detail p{font-size:18px}.wide{grid-column:1/-1}.fine{font-size:16px}table{border-collapse:collapse;font-size:17px}td,th{padding:8px 16px;border-bottom:1px solid #ccc;text-align:left}details{margin:25px 0}summary{cursor:pointer;font-size:23px;font-weight:bold;min-height:44px}footer{border-top:1px solid #8c8d86;padding:25px 0}@media(max-width:850px){main{padding:25px 18px}h1{font-size:33px}.grid{display:block}.detail img{max-height:none}nav{gap:8px 22px}}@media print{nav,.hotspot{display:none}main{padding:0}.poster{break-after:page}.detail{break-inside:avoid}}figure{margin:0}figcaption{font-size:18px;max-width:84ch;margin-top:10px}.zoom{display:block}@media print{nav,.hotspot,.back{display:none}.detail{break-inside:avoid}}'''
links=''.join(f'<a class="hotspot" href="#{k}" aria-label="Zoom to {html.escape(title)}" title="{html.escape(title)}" style="left:{x*100}%;top:{(1-y-h)*100}%;width:{w*100}%;height:{h*100}%"></a>' for k,(x,y,w,h) in R['regions'].items() for kk,title,cap in parts if kk==k)
sections=''.join(f'<section class="detail {"wide" if i>=4 else ""}" id="{key}"><h2>{title}</h2><figure><a class="zoom" href="{key}.png"><img src="{key}.png" alt="{html.escape(title)}" loading="lazy"></a><figcaption>{cap}</figcaption></figure><a class="back" href="#poster">Back to poster ↑</a></section>' for i,(key,title,cap) in enumerate(parts))
# Markdown is included as escaped preformatted prose in its own readable HTML page.
import mistune
methodbody=mistune.create_markdown(escape=False, plugins=['table'])(methods)
(O/'methods.html').write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Information-space atlas — methods</title><style>{style}main{{max-width:1050px}}</style><main><nav aria-label="Atlas"><a href="./">← Poster</a><a href="../">Search process</a></nav>{methodbody}</main></html>')
page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>One clock, many views — information-space poster</title><style>{style}</style></head><body><main>
<div class="eyebrow">LAB · ADSERP · TYPED AOIs · STATIC RESEARCH ATLAS</div><h1>One clock, many views.</h1><p>Read across the time budgets, follow them into a shared timeline, then zoom into one observed trial. Select any region of the poster for a larger, linked view.</p>
<nav aria-label="Exports and related views"><a href="poster.pdf">A0 landscape PDF</a><a href="poster.png">Full-resolution poster</a><a href="poster.svg">Vector SVG</a><a href="methods.html">Measures & methods</a><a href="../gaze-cursor-echo/">Gaze–cursor sequences</a><a href="../">Search process</a></nav>
<div class="poster" id="poster"><img src="poster-preview.png" alt="Eight linked views: AOI membership, initial fold, joint motion, AOI identity, normalized time, click-target phases, observed trial and final three-second zoom.">{links}</div>
<div class="grid">{sections}</div>
<section class="detail" id="variation"><h2>09 · Change the level of aggregation and the motion thresholds</h2><a class="zoom" href="variation.png"><img src="variation.png" alt="Participant AOI time budgets with pooled confidence intervals, and sensitivity of motion shares to half, primary and double thresholds." loading="lazy"></a><p>Participant dots expose variation hidden by the pooled time budget. The motion comparison makes the operational definition visible: halve or double the displacement thresholds while retaining the same classifiable windows.</p></section>
<footer><p><a href="methods.html">Full measurement contract</a> · <a href="time-budgets.csv">Time budgets (CSV)</a> · <a href="summary.json">Aggregate values and confidence intervals</a> · <a href="{REPO}/raw/main/docs/visualizations/information-space-poster/trials.json.gz">Per-trial data and example trace (gzip JSON)</a></p><p class="fine">Data: <a href="https://github.com/kayhan-latifzadeh/AdSERP">AdSERP</a>. Current typed AOI geometry and local exact-overlap analysis. An earlier poster supplies the visual lineage; these panels describe time, geometry and the course of examination.</p></footer></main></body></html>'''

import re
def add_dimensions(match):
 tag=match.group(0);src=re.search(r'src="([^"]+)"',tag).group(1)
 width,height=Image.open(O/src).size
 return tag.replace('<img ',f'<img width="{width}" height="{height}" ',1)
page=re.sub(r'<img [^>]+>',add_dimensions,page)
(O/'index.html').write_text(page)
# Producer sources live in scripts/attention_atlas; avoid duplicate stale copies.
print(O/'index.html')
