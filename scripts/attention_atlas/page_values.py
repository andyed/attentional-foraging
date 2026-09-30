"""Numbers shown in the atlas pages, posters and entry-point prose, formatted once.

The renderers and page builders take displayed values from `values()`, so a
number cannot be typed into a page by hand and drift from its evidence.
verify-atlas.py checks that each value in `expected()` appears in its file,
which catches a page that was not rebuilt after the evidence changed.
"""
from functools import lru_cache

import numpy as np

import atlas_core as core
from atlas_core import ATLAS, ROOT

MINUS = '−'


def signed(x, digits=3):
    """+0.939 / −0.084, with a typographic minus."""
    s = f'{x:+.{digits}f}'
    return s.replace('-', MINUS)


def pct(x, digits=1):
    return f'{x:.{digits}f}%'


def ci(pair, digits=1):
    return f'{pair[0]:.{digits}f}–{pair[1]:.{digits}f}'


@lru_cache(maxsize=1)
def evidence():
    read = lambda rel: core.read_json(ATLAS / rel)
    return {'info': read('information-space-poster/summary.json'), 'echo': read('gaze-cursor-echo/summary.json'),
            'checks': read('gaze-cursor-echo/checks.json'), 'rest': read('evidence/resting-cursor/summary.json'),
            'prior': read('evidence/final-approach/summary.json'),
            'first_lags_ms': [d['lag_ms'] for tr in read('gaze-cursor-echo/trials.json.gz') for d in tr['first_arrivals']]}


@lru_cache(maxsize=1)
def values():
    e = evidence()
    info, echo, checks, rest = e['info'], e['echo'], e['checks'], e['rest']
    v = {'trials': f"{info['trials']:,}", 'participants': f"{info['participants']}",
         'clock_hours': f"{info['total_ms'] / 3.6e6:.3f}"}
    # Resting cursor (primary 50 px/s, 2 s hold) and its cursor-hold sensitivities.
    r = rest['results'][str(core.REST_PX_S)]
    ms, share = r['milliseconds'], r['different_aoi_share_by_denominator']
    rest_ms = ms['cursor_rest_in_aoi_ms']
    v.update({'rest_share': pct(share['cursor_rest_in_aoi_ms']['percent']),
              'rest_ci': ci(share['cursor_rest_in_aoi_ms']['ci95']),
              'rest_matched_share': pct(share['cursor_rest_in_aoi_fixation_matched_ms']['percent']),
              'rest_matched_ci': ci(share['cursor_rest_in_aoi_fixation_matched_ms']['ci95']),
              'rest_minutes': f"{ms['different_aoi_ms'] / 60000:.1f}",
              'rest_total_minutes': f"{rest_ms / 60000:.1f}",
              'rest_same': pct(100 * ms['same_aoi_ms'] / rest_ms),
              'rest_gaze_off': pct(100 * ms['gaze_off_aoi_ms'] / rest_ms),
              'rest_unmatched': pct(100 * ms['gaze_unmatched_ms'] / rest_ms)})
    for name, key in [('uncapped_hold', 'rest_uncapped'), ('uncapped_hold_scroll_shift', 'rest_uncapped_shift')]:
        s = rest['sensitivity_cursor_hold'][name]['different_aoi_share_by_denominator']['cursor_rest_in_aoi_ms']
        v[key], v[key + '_ci'] = pct(s['percent']), ci(s['ci95'])
    # First entries.
    first = echo['visit_sensitivity'][str(core.VISIT_MIN_MS)]
    lags = np.array(e['first_lags_ms']) / 1000
    v.update({'first_gaze_first': pct(first['gaze_first_share']['percent']),
              'first_ci': ci(first['gaze_first_share']['ci95']),
              'first_pairs': f"{first['totals']['both_visited']:,}",
              'first_gaze_only_aois': f"{first['totals']['gaze_only_aois']:,}",
              'first_cursor_only_aois': f"{first['totals']['cursor_only_aois']:,}",
              'first_median_s': signed(first['first_entry_lag_median_ms'] / 1000),
              'first_iqr_s': f"{signed(np.percentile(lags, 25))} to {signed(np.percentile(lags, 75))}",
              'first_same_onset': pct(100 * np.mean(lags == 0)),
              'first_cursor_first': pct(100 * np.mean(lags < 0))})
    fb = checks['first_entries_excluding_clock_boundary']
    v.update({'first_boundary_pairs': f"{fb['n']:,}", 'first_boundary_gaze_first': pct(fb['gaze_first_share']['value']),
              'first_boundary_ci': ci(fb['gaze_first_share']['ci95']),
              'first_boundary_median_s': signed(fb['median_lag_ms'] / 1000)})
    # Matched nearby visits (primary ±2 s) and the clock-origin sensitivity.
    near = echo['matching_sensitivity'][str(core.PRIMARY_MATCH_WINDOW_MS)]
    origin = checks['matched_pairs_clock_origin_sensitivity']
    allp, excl = origin['all_pairs'], origin['excluding_pairs_at_clock_origin']
    v.update({'matched_pairs': f"{near['matched_pairs']:,}", 'matched_median_s': signed(near['lag_median_ms'] / 1000),
              'matched_gaze_first': pct(near['gaze_first_share']['percent']),
              'matched_ci': ci(near['gaze_first_share']['ci95']),
              'matched_ties': pct(allp['tie']['percent']),
              'origin_pairs': f"{excl['pairs']:,}", 'origin_gaze_first': pct(excl['gaze_first']['percent']),
              'origin_trials': f"{origin['trials_with_first_cursor_visit_at_origin']:,}",
              'origin_ci': ci(excl['gaze_first']['ci95']), 'origin_median_s': signed(excl['lag_median_ms'] / 1000),
              'both_return_pairs': f"{near['both_return_pairs']:,}",
              'both_return_median_s': signed(near['both_return_lag_median_ms'] / 1000),
              'matched_share_gaze': pct(100 * near['matched_pairs'] / near['gaze_visits']),
              'matched_share_cursor': pct(100 * near['matched_pairs'] / near['cursor_visits'])})
    # Common coverage.
    ratio = checks['gaze_to_cursor_count_ratio']
    v.update({'common_hours': f"{checks['common_coverage_totals']['common_ms'] / 3.6e6:.3f}",
              'ratio_transitions': f"{ratio['transitions']['value']:.2f}",
              'ratio_transitions_ci': ci(ratio['transitions']['ci95'], 2),
              'ratio_backward': f"{ratio['backward']['value']:.2f}",
              'ratio_backward_ci': ci(ratio['backward']['ci95'], 2)})
    for m in ('100', '200'):
        t = echo['visit_sensitivity'][m]['totals']
        v[f'fullclock_ratio_{m}'] = f"{t['gaze_transitions'] / t['cursor_transitions']:.2f}"
    # The illustrated pause and how common its pattern is.
    ex, pa = echo['example'], echo['example']['pause']
    prev = checks['example_rule_prevalence']
    v.update({'pause_trial': ex['trial_id'], 'qualifying_pauses': f"{ex['qualifying_pauses']}",
              'pause_sequence': ' → '.join(str(k + 1) for k in pa['gaze_sequence']),
              'pause_aoi': f"{pa['cursor_aoi'] + 1}", 'pause_seconds': f"{(pa['end'] - pa['start']) / 1000:.1f}",
              'pause_window': f"{pa['start'] / 1000:.1f}–{pa['end'] / 1000:.1f}",
              'pause_different_s': f"{pa['different_ms'] / 1000:.2f}",
              'pauses_2_to_8': f"{prev['pauses_2_to_8_s']:,}",
              'pauses_with_return_pct': pct(prev['with_3plus_gaze_aois_and_a_return_pct']),
              'pauses_any_other_pct': pct(prev['with_any_different_aoi_gaze_pct']),
              'pauses_any_other': f"{prev['with_any_different_aoi_gaze']:,}"})
    # The prior final-approach readout the information-space poster compares against.
    legacy = e['prior']['legacy_reproduction']['shares']
    v['legacy_table'] = ' / '.join(f"{name} {100 * legacy[k]:.1f}" for name, k in
                                   [('same', 'on_same'), ('adjacent', 'adjacent'), ('other', 'other_aoi'), ('off or none', 'off_or_none')])
    res = e['prior']['results']
    v['prior_earlier'] = pct(res['xy|cap2000|full|earlier']['gaze_on_cursor_off_pct_matched'])
    v['prior_approach'] = pct(res['xy|cap2000|full|approach']['gaze_on_cursor_off_pct_matched'])
    return v


def expected():
    """Values that must appear in each generated file (and in the entry-point prose)."""
    v = values()
    echo_page = ['first_gaze_first', 'first_pairs', 'first_median_s', 'first_iqr_s', 'rest_share', 'rest_gaze_off',
                 'rest_unmatched', 'pause_sequence', 'pause_different_s', 'qualifying_pauses', 'matched_pairs',
                 'matched_gaze_first', 'matched_ci', 'matched_ties', 'origin_gaze_first', 'origin_ci',
                 'ratio_transitions', 'ratio_backward']
    echo_methods = ['clock_hours', 'common_hours', 'first_pairs', 'first_gaze_only_aois', 'first_cursor_only_aois',
                    'qualifying_pauses', 'pause_trial', 'pause_window', 'rest_uncapped', 'rest_uncapped_shift',
                    'origin_gaze_first', 'pauses_with_return_pct']
    echo_poster = ['first_gaze_first', 'first_ci', 'rest_share', 'rest_ci', 'rest_minutes', 'rest_total_minutes',
                   'rest_same', 'rest_gaze_off', 'rest_unmatched', 'rest_uncapped', 'matched_gaze_first', 'matched_ties',
                   'origin_gaze_first', 'qualifying_pauses', 'pauses_2_to_8', 'pauses_any_other']
    info_methods = ['legacy_table', 'prior_earlier', 'prior_approach', 'trials']
    return {ATLAS / 'gaze-cursor-echo/index.html': [v[k] for k in echo_page],
            ATLAS / 'gaze-cursor-echo/methods.md': [v[k] for k in echo_methods],
            ATLAS / 'gaze-cursor-echo/poster.svg': [v[k] for k in echo_poster],
            ATLAS / 'information-space-poster/methods.md': [v[k] for k in info_methods],
            ATLAS / 'information-space-poster/poster.svg': [f"{v['trials']} trials"],
            ROOT / 'README.md': [v[k] for k in ['rest_share', 'rest_matched_share', 'ratio_transitions', 'ratio_backward',
                                                'qualifying_pauses', 'pauses_with_return_pct', 'origin_gaze_first',
                                                'rest_uncapped']],
            ROOT / 'docs/not-a-cascade.md': [v[k] for k in ['rest_share', 'first_gaze_first', 'matched_pairs',
                                                           'origin_gaze_first', 'qualifying_pauses', 'rest_uncapped']],
            core.CANONICAL_ATLAS / 'README.md': [v[k] for k in ['trials', 'rest_share', 'rest_uncapped', 'origin_gaze_first',
                                                                 'matched_gaze_first', 'pauses_with_return_pct']]}
