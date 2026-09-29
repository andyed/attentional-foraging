"""Build the sequence poster's linked page and its measurement notes.

Every displayed number comes from page_values, so the page cannot drift from
the evidence; verify-atlas.py checks that it was rebuilt after a change.
"""
import html

from PIL import Image

import atlas_core as core
from atlas_core import ATLAS
import page_values

O = ATLAS / 'gaze-cursor-echo'
REPO = 'https://github.com/andyed/attentional-foraging'
S = core.read_json(O / 'summary.json')
R = core.read_json(O / 'render-manifest.json')
V = page_values.values()
first = S['visit_sensitivity'][str(core.VISIT_MIN_MS)]

parts = [
    ('entry', 'First entry into a shared result',
     f"Gaze arrives first in {V['first_gaze_first']} of {V['first_pairs']} jointly visited trial–AOIs. The median "
     f"cursor-minus-gaze onset difference is {V['first_median_s']} seconds. This is a first-entry measure, not a "
     "tracking delay for every movement."),
    ('sparsity', 'How much stutter step?',
     f"Within {V['common_hours']} hours when both signals have location coverage, gaze changes result position "
     f"{V['ratio_transitions']} times as often as the cursor (95% CI {V['ratio_transitions_ci']}). Backward steps are "
     f"{V['ratio_backward']} times as frequent ({V['ratio_backward_ci']}). Both channels use the same 100 ms minimum "
     "observed occupancy; fixation segmentation and motion sampling still differ, and the ratio falls when the "
     f"minimum visit rises (full clock: {V['fullclock_ratio_100']} at 100 ms, {V['fullclock_ratio_200']} at 200 ms)."),
    ('rest', 'Where gaze goes while the cursor rests',
     f"During cursor rest inside an AOI, gaze occupies another result for {V['rest_share']} of that time "
     f"(95% CI {V['rest_ci']}%). Gaze is outside every included AOI for {V['rest_gaze_off']}, and no matched fixation "
     f"is available for {V['rest_unmatched']}. Those categories stay separate. The logger records the cursor only when "
     "it moves and a position is held for at most 2 s, so stillness beyond 2 s is not counted as rest; holding the "
     f"cursor until its next move gives {V['rest_uncapped']} ({V['rest_uncapped_ci']}%)."),
    ('trial', 'Two paths through one observed trial',
     f"Trial {V['pause_trial']}. Both panels share the same clock and AOI position scale. The shaded interval is "
     "enlarged in the next view. Solid segments show exact occupancy, including short visits; dashed links connect "
     "qualifying AOI visits no more than 500 ms apart. The unobserved row makes gaps explicit."),
    ('pause', 'A cursor pause with a gaze excursion',
     f"The cursor remains in AOI {V['pause_aoi']} for {V['pause_seconds']} seconds while gaze visits "
     f"{V['pause_sequence']}, spending {V['pause_different_s']} seconds in another AOI. A fixed rule chose this "
     f"example from {V['qualifying_pauses']} qualifying pauses, and the rule requires a gaze return, so the example "
     f"shows the pattern rather than a typical pause: {V['pauses_with_return_pct']} of the {V['pauses_2_to_8']} "
     f"cursor pauses of 2–8 s contain three or more gaze AOIs and a return, and {V['pauses_any_other_pct']} contain "
     "some gaze on another AOI."),
    ('first-lag', 'Who gets there first?',
     "For each result visited by both channels, compare the first qualifying cursor entry with the first qualifying "
     f"gaze entry. Positive values mean gaze arrived earlier. Median {V['first_median_s']} s; IQR {V['first_iqr_s']} s. "
     "The first-mousemove boundary can censor arrivals: excluding pairs where either onset falls exactly at that "
     f"boundary leaves {V['first_boundary_pairs']} pairs, with {V['first_boundary_gaze_first']} gaze first and median "
     f"{V['first_boundary_median_s']} s."),
    ('matched-lag', 'Nearby visits do not establish a constant follower delay',
     f"Match visits to the same AOI in order, one-to-one, within ±2 seconds. Among {V['matched_pairs']} pairs, the "
     f"median onset difference is {V['matched_median_s']} s and gaze arrives first in {V['matched_gaze_first']} "
     f"(95% CI {V['matched_ci']}%); {V['matched_ties']} are ties. Every trial's first cursor visit starts at the first "
     f"mousemove, so pairs that start there tie or favour the cursor. Without them ({V['origin_pairs']} pairs), gaze "
     f"arrives first in {V['origin_gaze_first']} ({V['origin_ci']}%), median {V['origin_median_s']} s. The matching rule "
     "selects nearby onsets; it cannot prove absence of a lag in the unpaired visits. Both-return pairs number "
     f"{V['both_return_pairs']}, with a median difference of {V['both_return_median_s']} s."),
    ('matching-detail', 'Keep the unmatched visits in view',
     f"At ±2 seconds, {V['matched_share_gaze']} of qualifying gaze visits and {V['matched_share_cursor']} of cursor "
     "visits receive a match. Unmatched means this pairing rule found no counterpart. It does not prove that one "
     "channel ignored or failed to follow the other. Widening the matching window changes both membership and "
     "estimated timing; the open marker shows the ±2 s estimate without clock-origin pairs.")]

style = open(core.ROOT / 'scripts/attention_atlas/page_style.css').read()


def img(name, alt, eager=False):
    """A detail image that opens its full-resolution file, so small print can be read on a phone."""
    w, h = Image.open(O / (name + '.png')).size
    loading = '' if eager else ' loading="lazy"'
    return (f'<a class="zoom" href="{name}.png"><img src="{name}.png" width="{w}" height="{h}" '
            f'alt="{html.escape(alt)}"{loading}></a>')


title_of = {k: title for k, title, _ in parts}
links = ''.join(f'<a class="hotspot" href="#{k}" aria-label="Enlarge {html.escape(title_of[k])}" '
                f'style="left:{100 * x}%;top:{100 * (1 - y - h)}%;width:{100 * w}%;height:{100 * h}%"></a>'
                for k, (x, y, w, h) in R['regions'].items())
sections = ''.join(f'<section class="detail {"wide" if k in ["trial", "matching-detail"] else ""}" id="{k}">'
                   f'<h2>{title}</h2><figure>{img(k, title)}<figcaption>{cap}</figcaption></figure>'
                   f'<a class="back" href="#poster">Back to poster ↑</a></section>' for k, title, cap in parts)

method = f'''# Measurement notes

## Scope and clocks

Exploratory analysis of the existing poster cohort: {V['trials']} trials, {V['participants']} participants. The clock starts at the first native mousemove and ends at final mousedown. The entire clock is {V['clock_hours']} hours. No extrapolation is made into cursor or fixation gaps.

AOIs are the strict x/y rectangles of typed main-column results, including ads and widgets. Plot numbering is stored position + 1. Outside AOIs and unavailable location are distinct. Fixation membership applies only over recorded fixation durations, with the latest-starting fixation taking precedence in an overlap. Cursor samples are held in page coordinates until the next sample or up to 2 seconds. The inherited occupancy convention does not reconstruct page-space cursor location during scrolling; motion windows containing scroll are excluded.

## Rest and the worked example

Cursor rest means less than 50 screenshot pixels/second in endpoint displacement over a complete 100-ms window. Cursor endpoints interpolate only across gaps at most 250 ms, otherwise hold up to 2 seconds. This permits small movements and does not detect physiological immobility. A pause is a continuous sequence of such windows in the same AOI; gaps split it. The rest-overlap numerator and four denominator totals exactly reproduce the previously shipped resting-cursor results.

The logger records the cursor only when it moves, so under the 2-second hold a cursor that stays still for longer becomes unavailable rather than resting. Two sensitivities relax the hold. Holding each position until the next mousemove raises the different-AOI share of rest time from {V['rest_share']} to {V['rest_uncapped']} (95% CI {V['rest_uncapped_ci']}%); also moving the held page position with the scroll offset gives {V['rest_uncapped_shift']} ({V['rest_uncapped_shift_ci']}%). The primary estimate is the conservative one.

Example selection: take pauses lasting 2–8 seconds, with at least three gaze AOIs, one return in the gaze sequence, and at least 60% gaze-in-AOI coverage. Choose the pause closest to 4 seconds; tie-break by trial ID and then onset. There are {V['qualifying_pauses']} candidates. The selected trial is {V['pause_trial']}, interval {V['pause_window']} seconds after first mousemove. This is an illustration, not a representative-trial claim: of {V['pauses_2_to_8']} cursor pauses of 2–8 seconds, {V['pauses_with_return_pct']} contain three or more gaze AOIs and a return. No matched fixation occupies the gaps; it is not interpreted as gaze outside results.

## Visits and rank changes

For each signal, contiguous same-AOI occupancy segments form a visit. Same-AOI segments separated by at most 100 ms can merge if no other AOI intervenes. The primary minimum visit duration is 100 ms of observed occupancy; bridged gaps do not count toward that duration. Zero- and 200-ms minima provide sensitivity checks. Plotted traces retain every exact segment, including visits below the analytical threshold.

An AOI change requires successive qualifying visits to different AOIs, separated by at most 500 ms. Larger gaps break the chain. A backward step moves to a smaller position. A direction reversal changes the sign of successive rank changes; repeated occupancy of the same AOI does not reset the previous direction. It is a geometric sequence measure, not a cognitive-state label.

The rate chart intersects fixation coverage and cursor coverage first, then applies the same visit definition to both channels. Rates divide by the resulting {V['common_hours']} hours of common covered time. These intervals need not put either signal inside an AOI. Fixation gaps still fragment observations and the modalities have different native sampling, so the rates describe recorded AOI changes rather than a physiological movement-frequency ratio.

## First arrivals

For each trial–AOI visited by both channels, compare the first qualifying visit onset. Lag equals cursor onset minus gaze onset, in milliseconds. Positive means gaze entered first. No temporal matching window is used. Only jointly visited AOIs enter this distribution; the primary cohort contains {V['first_pairs']} such pairs, {V['first_gaze_only_aois']} gaze-only trial–AOIs, and {V['first_cursor_only_aois']} cursor-only trial–AOIs.

A result occupied at the first-mousemove boundary may have been reached earlier. Excluding every pair where either first onset is exactly at that boundary is a sensitivity analysis, not a recovery of the true trial-onset order. Histogram tails outside ±10 seconds are included in the outer bins; the bin beginning at zero also includes exact ties. The separate three-way first-entry bar reports ties explicitly.

## Nearby visit pairs

Use all qualifying visits, including returns. Match same-AOI visits monotonically and one-to-one, with absolute onset differences no greater than the chosen window. Dynamic programming maximizes the number of pairs, then minimizes summed absolute onset differences. The primary window is ±2 seconds; ±0.5, ±1 and ±5 seconds show sensitivity. Matching never reuses a visit or crosses visit order. Both-return summaries further require that each matched visit has an earlier visit to that same AOI in its own channel.

Every trial's first cursor visit starts at the first mousemove, the origin of the clock. Pairs that start there are ties or favour the cursor, which pulls the gaze-first share toward 50%. Ties are {V['matched_ties']} of all pairs; without pairs at the clock origin, gaze arrives first in {V['origin_gaze_first']} (95% CI {V['origin_ci']}%) and the median difference is {V['origin_median_s']} s.

This selection favors nearby onsets and can pair different physical excursions to a revisited AOI. A median near zero within matched visits does not establish that all cursor movements are synchronous or that gaze never leads. Unmatched visits remain in the chart and data. A more causal follower model would require an independently specified correspondence rule and validation against suitable within-trial controls.

## Uncertainty and reproducibility

95% confidence intervals use 2,000 participant-cluster bootstrap resamples, seed {core.SEED_SEQUENCES} (the reused rest estimate uses seed {core.SEED_INFORMATION_SPACE}). Participant resampling retains all visits and durations for each selected participant. Pooled event proportions, pooled duration proportions, medians and per-minute rates have different denominators and are labeled separately. The reported IQR describes the lag distribution, not uncertainty in its median.

Five exact reproduction gates pass with zero millisecond discrepancy against the resting-cursor summary. Semantic tests cover visit-gap merging, an intervening different AOI, directional reversals across repeated same-AOI occupancy, and bounded one-to-one sequence matching (checked against exhaustive search). All generated pairs were checked for AOI equality, unique use, temporal bounds and monotone order. Producers: scripts/attention_atlas/compute-gaze-cursor-echo.py and check-gaze-cursor-echo.py. Source hashes, aggregate results, per-trial traces and sensitivities are stored beside the visual.
'''
(O / 'methods.md').write_text(method)


def para(block):
    if block.startswith('## '):
        return '<h2>' + html.escape(block[3:]) + '</h2>'
    if block.startswith('# '):
        return '<h1>' + html.escape(block[2:]) + '</h1>'
    return '<p>' + html.escape(block) + '</p>'


method_html = ''.join(para(x) for x in method.strip().split('\n\n'))
tables = ('<h2>Visit-duration sensitivity</h2><div class="table-wrap" tabindex="0"><table><tr><th>Minimum observed visit</th>'
          '<th>Jointly visited trial–AOIs</th><th>Gaze first</th><th>Median cursor − gaze</th></tr>')
for k, v in S['visit_sensitivity'].items():
    tables += (f'<tr><td>{k} ms</td><td>{v["totals"]["both_visited"]:,}</td><td>{v["gaze_first_share"]["percent"]:.1f}%</td>'
               f'<td>{page_values.signed(v["first_entry_lag_median_ms"] / 1000)} s</td></tr>')
tables += ('</table></div><h2>Pairing-window sensitivity</h2><div class="table-wrap" tabindex="0"><table><tr><th>Window</th>'
           '<th>Matched pairs</th><th>Gaze first</th><th>Median cursor − gaze</th></tr>')
for k, v in S['matching_sensitivity'].items():
    tables += (f'<tr><td>±{int(k) / 1000:g} s</td><td>{v["matched_pairs"]:,}</td><td>{v["gaze_first_share"]["percent"]:.1f}%</td>'
               f'<td>{page_values.signed(v["lag_median_ms"] / 1000)} s</td></tr>')
tables += '</table></div>'
(O / 'methods.html').write_text(
    f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>Gaze and cursor sequence methods</title><style>{style}main{{max-width:1100px}}</style>'
    f'<main><nav aria-label="Atlas"><a href="./">← Visual</a><a href="../">Search process</a></nav>{method_html}{tables}</main></html>')

page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>While the mouse waits, the eyes travel</title><style>{style}</style></head><body><main><div class="eyebrow">LAB · ADSERP · TYPED AOIs · SEQUENCES AND TIMING</div><h1>While the mouse waits, the eyes travel.</h1><p>Gaze reaches shared results first more often, and its recorded path has more rank changes. Nearby visit pairs have little median lag. Follow the cohort summaries into one trial and a four-second cursor pause.</p><nav aria-label="Exports and evidence"><a href="poster.pdf">A0 poster PDF</a><a href="poster.png">Full-resolution PNG</a><a href="poster.svg">Vector SVG</a><a href="methods.html">Measures & methods</a><a href="../information-space-poster/">Information-space atlas</a><a href="../">Search process</a></nav><div class="poster" id="poster">{img('poster-preview', 'Seven linked views: first-entry timing, AOI-change rates, resting-cursor overlap, observed gaze and cursor paths, a four-second pause, first-entry lag and nearby-visit lag.', eager=True)}{links}</div><div class="grid">{sections}</div><footer><p><a href="summary.json">Aggregate results</a> · <a href="checks.json">Common-coverage checks</a> · <a href="{REPO}/raw/main/docs/visualizations/gaze-cursor-echo/trials.json.gz">Per-trial visits and traces (gzip JSON)</a> · <a href="methods.html">Definitions and sensitivity tables</a></p><p class="fine">AdSERP / AllSERP · 29 September 2026 · Static figures, reproducible local analysis. The panels describe observed timing and movement within the search task.</p></footer></main></body></html>'''
(O / 'index.html').write_text(page)
print('Built linked static page and measurement notes.')
