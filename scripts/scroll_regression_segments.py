"""Scroll-regression gestures by SERP segment (ads vs ranked results), AdSERP.

CHI27 Sara ask (04-results §4.1): "Add scroll-regression by SERP segments, for
both datasets. So AI Overviews and ranked results plus AdSERP, Ads and ranked
results." This is the AdSERP half, built as the construct-parallel of her AO
statistic "60.7% of regressions resulted in re-fixations on AI Overviews":
for each upward scroll gesture, which element type does the first fixation
after the gesture land on (and which did the last fixation before it leave)?

Definitions (stated because the repo has three incompatible gesture rules):
- Scroll gesture: NB07a parity — document-space scroll samples segmented at
  inter-sample gaps > 200 ms; gesture direction from net delta (last y - first
  y): 'up' if < -10 px, 'down' if > +10 px, else neutral. This matches the
  definition Sara ported into data_loader_AO.py (200 ms / 10 px), so the two
  corpora are construct-comparable.
- Landing: first fixation with t >= the gesture's last scroll sample t
  (latency recorded; sensitivity split at <= 2000 ms). Origin: last fixation
  with t <= the gesture's first sample t.
- Element assignment: gap-free y-band bisection against typed_gapfill AOI
  tops (assign_fixation_to_position; FPOGY is page-space, no scroll
  arithmetic). Y-only, main-axis bands — same convention as the knee
  construct. pos -1 (above first band) reported as 'header/off'.
- Segments: ads = {dd_top, native_ad}; organic; other = remaining widget
  types; header/off.

Population: typed_gapfill corpus minus alignment exclusions, trials with
scroll data and fixations.

Run:    .venv/bin/python scripts/scroll_regression_segments.py
Output: scripts/output/scroll_regression_segments/{summary.json,report.md}
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    load_typed_gapfill_aois,
    typed_alignment_exclusions,
    typed_gapfill_aoi_etypes,
    typed_gapfill_aoi_tops,
)

OUT = ROOT / 'scripts' / 'output' / 'scroll_regression_segments'

GAP_MS = 200
NET_PX = 10
AD_TYPES = {'dd_top', 'native_ad'}


def gestures(scrolls):
    """NB07a-parity gesture segmentation over [(t, y)] document-space scrolls."""
    if len(scrolls) < 2:
        return []
    runs, cur = [], [scrolls[0]]
    for s in scrolls[1:]:
        if s[0] - cur[-1][0] > GAP_MS:
            runs.append(cur)
            cur = [s]
        else:
            cur.append(s)
    runs.append(cur)
    out = []
    for g in runs:
        delta = g[-1][1] - g[0][1]
        direction = 'down' if delta > NET_PX else ('up' if delta < -NET_PX else 'neutral')
        out.append({'t_start': g[0][0], 't_end': g[-1][0], 'delta': delta,
                    'direction': direction})
    return out


def seg_of(etype):
    if etype is None:
        return 'header/off'
    if etype in AD_TYPES:
        return 'ads'
    if etype == 'organic':
        return 'organic'
    return 'other_widget'


def substrate_stamp():
    stamp = {}
    sub = ROOT / 'data' / 'aoi-typed' / 'substrate.json'
    if sub.exists():
        stamp['substrate_json'] = json.loads(sub.read_text())
    try:
        sha = subprocess.run(['git', 'rev-parse', '--short=12', 'HEAD'],
                             cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
        stamp['allserp_git_sha'] = sha
    except Exception:
        stamp['allserp_git_sha'] = None
    stamp['n_excluded'] = len(typed_alignment_exclusions())
    return stamp


def main():
    excluded = typed_alignment_exclusions()
    trials = [t for t in get_trial_ids() if t not in excluded]

    n_no_map = n_no_scroll = n_no_fix = 0
    per_trial = []
    land_all, land_fast = Counter(), Counter()
    origin_all = Counter()
    etype_land = Counter()
    flow = Counter()  # (origin_seg -> landing_seg)
    latencies = []
    n_up_total = 0
    n_up_landed = 0

    for tid in trials:
        if not load_typed_gapfill_aois(tid):
            n_no_map += 1
            continue
        _, scrolls, _ = load_mouse_events(tid, space='document')
        if len(scrolls) < 2:
            n_no_scroll += 1
            continue
        fixes = load_fixations(tid)
        if not fixes:
            n_no_fix += 1
            continue
        tops = typed_gapfill_aoi_tops(tid)
        etypes = typed_gapfill_aoi_etypes(tid)
        n = len(tops)
        gs = gestures(scrolls)
        ups = [g for g in gs if g['direction'] == 'up']
        n_up_total += len(ups)
        per_trial.append({'tid': tid, 'n_gestures': len(gs), 'n_up': len(ups)})
        for g in ups:
            land = next((f for f in fixes if f['t'] >= g['t_end']), None)
            orig = next((f for f in reversed(fixes) if f['t'] <= g['t_start']), None)
            o_seg = 'none'
            if orig is not None:
                op = assign_fixation_to_position(orig['y'], tops, n)
                o_seg = seg_of(etypes[op] if op >= 0 else None)
            if land is None:
                flow[(o_seg, 'no-fixation-after')] += 1
                continue
            n_up_landed += 1
            lp = assign_fixation_to_position(land['y'], tops, n)
            l_ety = etypes[lp] if lp >= 0 else None
            l_seg = seg_of(l_ety)
            lat = land['t'] - g['t_end']
            latencies.append(lat)
            land_all[l_seg] += 1
            etype_land[l_ety or 'header/off'] += 1
            if lat <= 2000:
                land_fast[l_seg] += 1
            origin_all[o_seg] += 1
            flow[(o_seg, l_seg)] += 1

    n_trials = len(per_trial)
    with_reg = sum(1 for r in per_trial if r['n_up'] > 0)
    lat_sorted = sorted(latencies)

    def share(c):
        tot = sum(c.values())
        return {k: {'n': v, 'share': round(v / tot, 4)} for k, v in
                sorted(c.items(), key=lambda kv: -kv[1])} if tot else {}

    summary = {
        'experiment': 'Scroll-regression gestures by SERP segment (ads vs ranked results), AdSERP half of CHI27 Sara ask',
        'regime_tag': '[LAB, AdSERP, typed_gapfill]',
        'rank_type': 'typed_gapfill',
        'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'gesture_definition': 'NB07a parity: document-space scroll samples segmented at gaps > 200 ms; direction by net delta, up if < -10 px. Matches the definition ported into Sara data_loader_AO.py.',
        'landing_definition': 'First fixation with t >= gesture last sample t; element by gap-free y-band bisection against typed_gapfill AOI tops (Y-only, main-axis). Origin: last fixation with t <= gesture first sample t.',
        'segments': {'ads': sorted(AD_TYPES), 'organic': ['organic'], 'other_widget': 'all remaining widget types', 'header/off': 'above first band / pos -1'},
        'population': {
            'trials_analyzed': n_trials,
            'excluded_alignment': len(excluded),
            'skipped_no_gapfill_map': n_no_map,
            'skipped_no_scroll': n_no_scroll,
            'skipped_no_fixations': n_no_fix,
        },
        'prevalence': {
            'trials_with_up_gesture': with_reg,
            'share_trials_with_up_gesture': round(with_reg / n_trials, 4) if n_trials else None,
            'mean_up_gestures_per_trial': round(sum(r['n_up'] for r in per_trial) / n_trials, 3) if n_trials else None,
        },
        'up_gestures': {'total': n_up_total, 'with_landing_fixation': n_up_landed},
        'landing_by_segment': share(land_all),
        'landing_by_segment_latency_le_2000ms': share(land_fast),
        'landing_by_etype': share(etype_land),
        'origin_by_segment': share(origin_all),
        'flow_origin_to_landing': {f'{a}->{b}': v for (a, b), v in
                                   sorted(flow.items(), key=lambda kv: -kv[1])},
        'landing_latency_ms': {
            'median': lat_sorted[len(lat_sorted) // 2] if lat_sorted else None,
            'p90': lat_sorted[int(len(lat_sorted) * 0.9)] if lat_sorted else None,
        },
        'substrate_stamp': substrate_stamp(),
        'ao_parallel_note': 'AO comparator: 60.7% of regressions end in AI Overview re-fixation (Sara, CHI draft §4.1). Compare against landing_by_segment here.',
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    lines = [
        '# Scroll-regression gestures by SERP segment — AdSERP',
        '', f"Tag: `{summary['regime_tag']}` · generated {summary['generated']}", '',
        f"Trials analyzed: {n_trials} (with scroll + fixations + gapfill map; {len(excluded)} alignment-excluded).",
        f"Trials with >=1 upward gesture: {with_reg} ({summary['prevalence']['share_trials_with_up_gesture']:.1%}).",
        f"Upward gestures: {n_up_total} ({n_up_landed} with a landing fixation).", '',
        '## Landing segment of first fixation after an upward gesture', '',
        '| segment | n | share |', '|---|---|---|',
    ]
    for k, v in summary['landing_by_segment'].items():
        lines.append(f"| {k} | {v['n']} | {v['share']:.1%} |")
    lines += ['', '## Landing element type', '', '| etype | n | share |', '|---|---|---|']
    for k, v in summary['landing_by_etype'].items():
        lines.append(f"| {k} | {v['n']} | {v['share']:.1%} |")
    lines += ['', '## Origin -> landing flows (top)', '']
    for k, v in list(summary['flow_origin_to_landing'].items())[:12]:
        lines.append(f'- {k}: {v}')
    lines += ['', f"AO comparator: 60.7% of AO scroll-backs end on the AI Overview.", '']
    (OUT / 'report.md').write_text('\n'.join(lines))
    print(json.dumps({k: summary[k] for k in
                      ('population', 'prevalence', 'landing_by_segment',
                       'landing_by_etype')}, indent=1))


if __name__ == '__main__':
    main()
