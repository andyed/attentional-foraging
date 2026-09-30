"""Checks and saved-data sensitivities for the sequence poster.

Works from the saved per-trial sequence records; it does not reread raw
recordings. It
- recounts both channels over common coverage (time covered by both signals),
- re-derives first entries without the clock boundary,
- re-derives the matched-pair gaze-first share with ties reported separately
  and without pairs that start at the clock origin (every trial's first cursor
  visit starts there, so origin ties pull the share toward 50%),
- counts how common the illustrated pause pattern is,
- and checks every stored gate and every visit pair for AOI identity, time
  bounds, unique use and monotone order. Any failure exits non-zero.

Writes gaze-cursor-echo/checks.json and common-coverage-trials.json.gz.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import atlas_core as core
from atlas_core import ATLAS

O = ATLAS / 'gaze-cursor-echo'
TRIALS = O / 'trials.json.gz'
SUMMARY = O / 'summary.json'
NOTE = ('Common coverage intersects exact cursor coverage and recorded fixation intervals. Both channels use the same '
        '>=100ms visit threshold and <=100ms merge gap. Counting links still allows <=500ms gaps; estimates are '
        'descriptive and depend on fixation segmentation.')


def matched_pair_shares(trials, window, pids, boot, exclude_origin):
    """Gaze-first / tie / cursor-first shares among matched pairs, with participant-cluster CIs."""
    counts = defaultdict(Counter)
    lags = []
    for tr in trials:
        for gi, ci, d in tr['matches'][window]:
            if exclude_origin and (tr['gaze_visits'][gi]['start'] == 0 or tr['cursor_visits'][ci]['start'] == 0):
                continue
            lags.append(d)
            counts[tr['pid']]['pairs'] += 1
            counts[tr['pid']]['gaze_first'] += d > 0
            counts[tr['pid']]['tie'] += d == 0
            counts[tr['pid']]['cursor_first'] += d < 0
    den = {p: counts[p]['pairs'] for p in pids}
    out = {'pairs': len(lags), 'lag_median_ms': float(np.median(lags)), 'lag_iqr_ms': np.percentile(lags, [25, 75]).tolist()}
    for k in ['gaze_first', 'tie', 'cursor_first']:
        out[k] = core.ratio_ci({p: counts[p][k] for p in pids}, den, pids, boot)
    # Gaze first among pairs whose onsets differ at all.
    untied = {p: counts[p]['gaze_first'] + counts[p]['cursor_first'] for p in pids}
    out['gaze_first_among_untied'] = core.ratio_ci({p: counts[p]['gaze_first'] for p in pids}, untied, pids, boot)
    return out


def example_prevalence(trials):
    """How common the illustrated pattern is among cursor pauses of 2-8 s."""
    rule = {'min_ms': 2000, 'max_ms': 8000}
    pauses = [pa for tr in trials for pa in tr['pauses'] if rule['min_ms'] <= pa['end'] - pa['start'] <= rule['max_ms']]
    with_return = [pa for pa in pauses if pa['distinct'] >= 3 and pa['returns'] >= 1]
    covered = [pa for pa in with_return if pa['gaze_aoi_coverage'] >= .6]
    any_other = [pa for pa in pauses if pa['different_ms'] > 0]
    n = len(pauses)
    return {'pauses_2_to_8_s': n,
            'with_3plus_gaze_aois_and_a_return': len(with_return),
            'with_3plus_gaze_aois_and_a_return_pct': 100 * len(with_return) / n,
            'qualifying_for_the_illustration': len(covered),
            'qualifying_for_the_illustration_pct': 100 * len(covered) / n,
            'with_any_different_aoi_gaze': len(any_other),
            'with_any_different_aoi_gaze_pct': 100 * len(any_other) / n,
            'note': 'Pauses are cursor rests of at least 1 s inside one AOI; counts are pauses, not trials.'}


def main():
    trials = core.read_json(TRIALS)
    s = core.read_json(SUMMARY)
    result = [core.common_coverage(tr) for tr in trials]
    pids = sorted(set(r['pid'] for r in result))
    by = defaultdict(Counter)
    for r in result:
        by[r['pid']]['common_ms'] += r['common_ms']
        for ch in ['gaze', 'cursor']:
            for k, v in r[ch].items():
                by[r['pid']][ch + '_' + k] += v
        by[r['pid']]['first_count'] += len(r['first_lags_without_boundary'])
        by[r['pid']]['gaze_first'] += sum(v > 0 for v in r['first_lags_without_boundary'])
    boot = core.bootstrap_indices(len(pids), core.SEED_SEQUENCES)

    def ratio(num, den, scale=1):
        r = core.ratio_ci({p: by[p][num] for p in pids}, {p: by[p][den] for p in pids}, pids, boot, scale)
        return {'value': r['percent'], 'ci95': r['ci95']}

    agg = Counter()
    for v in by.values():
        agg.update(v)
    lag = [v for r in result for v in r['first_lags_without_boundary']]
    window = str(core.PRIMARY_MATCH_WINDOW_MS)
    checks = {
        'common_coverage_totals': dict(agg),
        'common_coverage_rates_per_minute': {ch: {k: ratio(ch + '_' + k, 'common_ms', 60000)
                                                  for k in ['transitions', 'backward', 'reversals']}
                                             for ch in ['gaze', 'cursor']},
        'gaze_to_cursor_count_ratio': {k: ratio('gaze_' + k, 'cursor_' + k) for k in ['transitions', 'backward', 'reversals']},
        'first_entries_excluding_clock_boundary': {'n': len(lag), 'median_lag_ms': float(np.median(lag)),
                                                   'gaze_first_share': ratio('gaze_first', 'first_count', 100)},
        'matched_pairs_clock_origin_sensitivity': {
            'window_ms': core.PRIMARY_MATCH_WINDOW_MS,
            'all_pairs': matched_pair_shares(trials, window, pids, boot, exclude_origin=False),
            'excluding_pairs_at_clock_origin': matched_pair_shares(trials, window, pids, boot, exclude_origin=True),
            'trials_with_first_cursor_visit_at_origin': sum(1 for tr in trials if tr['cursor_visits'] and tr['cursor_visits'][0]['start'] == 0),
            'note': 'The clock starts at the first mousemove, so in trials where the cursor is already inside an AOI '
                    'then, its first visit starts at 0 ms and can only tie or precede gaze. Pairs whose gaze or '
                    'cursor visit starts there are excluded in the second row; ties are a separate category.'},
        'example_rule_prevalence': example_prevalence(trials),
        'note': NOTE,
        'source_hashes': core.source_hashes([Path(__file__), Path(core.__file__), TRIALS, SUMMARY])}

    # Stored gates: exactly five, all exact.
    core.gate(len(s['gates']) == 5, f"expected 5 rest-to-sequence gates, found {len(s['gates'])}")
    for g in s['gates']:
        core.gate(g['status'] == 'ok' and g['delta'] == 0, f"gate {g['source_path']} is not an exact reproduction")
    # Every matched pair: one use per visit, monotone order, same AOI, within the window, correct lag.
    for tr in trials:
        for w, pairs in tr['matches'].items():
            core.gate(len(set(v[0] for v in pairs)) == len(pairs) == len(set(v[1] for v in pairs)),
                      f"{tr['trial_id']} ±{w}: a visit is matched twice")
            core.gate(pairs == sorted(pairs, key=lambda x: x[0]) and pairs == sorted(pairs, key=lambda x: x[1]),
                      f"{tr['trial_id']} ±{w}: pairs cross")
            for gi, ci, d in pairs:
                core.gate(tr['gaze_visits'][gi]['aoi'] == tr['cursor_visits'][ci]['aoi'],
                          f"{tr['trial_id']} ±{w}: pair joins different AOIs")
                core.gate(abs(d) <= int(w) and d == tr['cursor_visits'][ci]['start'] - tr['gaze_visits'][gi]['start'],
                          f"{tr['trial_id']} ±{w}: pair lag outside the window or misrecorded")
    core.write_json(O / 'checks.json', checks)
    core.write_json_gz(O / 'common-coverage-trials.json.gz', result)
    (O / 'common-coverage-trials.json').unlink(missing_ok=True)
    print(json.dumps({k: v for k, v in checks.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    main()
