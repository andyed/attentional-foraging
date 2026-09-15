#!/usr/bin/env python3
"""How the survey treats the ads and widgets above the fold on AdSERP.

Survey = the first five fixations of the trial (NB13 convention). Bands are
the typed AOI map (native_ad, dd_top, image_pack, paa, top_places, widgets,
organic); the fold is the browser window height from trial geometry (screen
height if absent). Reports, over all trials and split by page layout (top
band is an ad vs not):
  1. composition: share of survey fixations by element class against the
     class's share of above-fold band height (selection ratio)
  2. where the first fixation and the first band fixation land
  3. on ad-topped pages: does the survey land on the ad block at all, does
     it skip over it to the first organic, and how far
  4. transitions between classes within the survey (the dance)
  5. ad examination over the trial: share of ad dwell inside the survey,
     P(ad fixated in survey | ad fixated ever), per-participant ad-landing rate
Regime [LAB, AdSERP, typed]. Output: scripts/output/survey_above_fold/summary.json
"""
import sys, csv, json, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl

N_SURVEY = 5
AD = {'native_ad', 'dd_top'}          # dd_top = top-of-page ads (typed taxonomy)
WIDGET = {'image_pack', 'paa', 'top_places', 'unknown_widget', 'other_widget'}


def cls(et):
    return 'ad' if et in AD else ('widget' if et in WIDGET else 'organic')


rows = list(csv.DictReader(open(ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv')))
tids = sorted({r['trial_id'] for r in rows})

comp = {'all': Counter(), 'ad_top': Counter(), 'other_top': Counter()}
area = {'all': Counter(), 'ad_top': Counter(), 'other_top': Counter()}
first_fix = Counter(); first_band = {'all': Counter(), 'ad_top': Counter(), 'other_top': Counter()}
trans = Counter()
adtop = dict(n=0, land_survey=0, first_band_is_ad=0, skip_to_organic=0, jump=[], ad_h=[], ad_fix_survey=[], ad_ever=0, ad_in_survey_given_ever=0,
             ad_dwell_survey=[], ad_dwell_total=[], returns_to_ad_after_survey=0, land_later_only=0)
pp = defaultdict(lambda: [0, 0])
layouts = Counter(); n_trials = 0; fold_used = []
survey_len_ms = []; survey_reach_fold = 0
for tid in tids:
    try:
        bands = dl.typed_aoi_bands(tid); fx = dl.load_fixations(tid)
    except Exception:
        continue
    if not bands or len(fx) < N_SURVEY:
        continue
    g = dl.get_trial_geometry(tid) or {}
    fold = g.get('window_height') or g.get('screen_height') or 1024
    fold_used.append(fold)
    n_trials += 1
    tops = [b[0] for b in bands]; n = len(bands)
    top_cls = cls(bands[0][2]); layouts[bands[0][2]] += 1
    lay = 'ad_top' if top_cls == 'ad' else 'other_top'
    # above-fold band height by class
    for t, b, et in bands:
        h = max(0, min(b, fold) - t)
        if h > 0:
            area['all'][cls(et)] += h; area[lay][cls(et)] += h
    pos = [dl.assign_fixation_to_position(f['y'], tops, n) for f in fx]

    def c_of(i):
        p = pos[i]
        if p is not None and p >= 0:
            return cls(bands[p][2])
        y = fx[i]['y']
        return 'page top' if y < bands[0][0] else ('below fold' if y > fold else 'between/other')

    sv = [c_of(i) for i in range(N_SURVEY)]
    survey_len_ms.append(fx[N_SURVEY - 1]['t'] + (fx[N_SURVEY - 1].get('d') or 0) - fx[0]['t'] if 't' in fx[0] else np.nan)
    if any(fx[i]['y'] > fold for i in range(N_SURVEY)):
        survey_reach_fold += 1
    for c in sv:
        comp['all'][c] += 1; comp[lay][c] += 1
    first_fix[sv[0]] += 1
    fb = next((c for c in sv if c in ('ad', 'widget', 'organic')), 'none')
    first_band['all'][fb] += 1; first_band[lay][fb] += 1
    for a, b in zip(sv, sv[1:]):
        trans[(a, b)] += 1
    if lay == 'ad_top':
        adtop['n'] += 1
        ad_idx = [k for k, b in enumerate(bands) if cls(b[2]) == 'ad' and k < next((j for j, bb in enumerate(bands) if cls(bb[2]) == 'organic'), n)]
        ad_bottom = max(bands[k][1] for k in ad_idx); adtop['ad_h'].append(ad_bottom - bands[0][0])
        in_ad = [i for i in range(len(fx)) if pos[i] is not None and pos[i] in ad_idx]
        sv_ad = [i for i in in_ad if i < N_SURVEY]
        adtop['land_survey'] += bool(sv_ad); adtop['ad_fix_survey'].append(len(sv_ad))
        pid = tid.split('-')[0]; pp[pid][0] += 1; pp[pid][1] += bool(sv_ad)
        fbi = next((i for i in range(N_SURVEY) if pos[i] is not None and pos[i] >= 0), None)
        if fbi is not None:
            if pos[fbi] in ad_idx:
                adtop['first_band_is_ad'] += 1
            elif cls(bands[pos[fbi]][2]) == 'organic':
                adtop['skip_to_organic'] += 1; adtop['jump'].append(fx[fbi]['y'] - ad_bottom)
        if in_ad:
            adtop['ad_ever'] += 1; adtop['ad_in_survey_given_ever'] += bool(sv_ad)
            dsv = sum((fx[i].get('d') or 0) for i in sv_ad); dtot = sum((fx[i].get('d') or 0) for i in in_ad)
            adtop['ad_dwell_survey'].append(dsv); adtop['ad_dwell_total'].append(dtot)
            if sv_ad and any(i >= N_SURVEY for i in in_ad):
                # a return after the survey: gaze left the ad block and came back
                left = any(pos[i] not in ad_idx for i in range(max(sv_ad), len(fx)) if pos[i] is not None)
                adtop['returns_to_ad_after_survey'] += left and any(i >= N_SURVEY for i in in_ad)
            if not sv_ad:
                adtop['land_later_only'] += 1

out = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'regime': '[LAB, AdSERP, typed]', 'n_survey_fixations': N_SURVEY,
       'trials': n_trials, 'fold_px_median': float(np.median(fold_used)), 'layouts_top_band': dict(layouts)}
print(f'trials {n_trials}; fold {np.median(fold_used):.0f} px; top band: {dict(layouts)}')
print(f'survey ({N_SURVEY} fixations) reaches below the fold in {survey_reach_fold / n_trials:.3f} of trials')
CL = ['page top', 'ad', 'widget', 'organic', 'between/other', 'below fold']
for lay in ('all', 'ad_top', 'other_top'):
    N = sum(comp[lay].values()); A = sum(area[lay].values())
    print(f'\n1. survey composition [{lay}] (share of survey fixations / share of above-fold band height / ratio)')
    d = {}
    for c in CL:
        fs = comp[lay][c] / N; as_ = area[lay][c] / A if A else np.nan
        d[c] = {'fix_share': fs, 'area_share': as_, 'ratio': (fs / as_ if as_ else None)}
        print(f'   {c:14s} {fs:6.3f} {as_:6.3f} {(fs / as_ if as_ else float("nan")):6.2f}')
    out[f'composition_{lay}'] = d
    N = sum(first_band[lay].values())
    out[f'first_band_{lay}'] = {k: v / N for k, v in first_band[lay].items()}
    print(f'   first band fixated: ' + ', '.join(f'{k} {v / N:.3f}' for k, v in first_band[lay].most_common()))
N = sum(first_fix.values()); out['first_fixation'] = {k: v / N for k, v in first_fix.items()}
print('\n2. first fixation of the trial lands on: ' + ', '.join(f'{k} {v / N:.3f}' for k, v in first_fix.most_common()))
a = adtop; n = a['n']
print(f"\n3. ad-topped pages (n = {n}; ad block height median {np.median(a['ad_h']):.0f} px)")
print(f"   survey lands on the ad block: {a['land_survey'] / n:.3f}; first band fixation is the ad: {a['first_band_is_ad'] / n:.3f}; skips over it to an organic: {a['skip_to_organic'] / n:.3f} (landing {np.median(a['jump']):.0f} px below the ad block, median)")
print(f"   survey fixations on the ad: median {np.median(a['ad_fix_survey']):.0f}, mean {np.mean(a['ad_fix_survey']):.2f}")
print(f"   ad fixated ever: {a['ad_ever'] / n:.3f}; of those, fixated in the survey: {a['ad_in_survey_given_ever'] / a['ad_ever']:.3f}; later only: {a['land_later_only'] / a['ad_ever']:.3f}")
print(f"   share of the trial's ad dwell inside the survey (median over trials with ad dwell): {np.median(np.array(a['ad_dwell_survey']) / np.maximum(np.array(a['ad_dwell_total']), 1)):.3f}; returns to the ad after the survey: {a['returns_to_ad_after_survey'] / a['ad_ever']:.3f}")
rates = np.array([v[1] / v[0] for v in pp.values() if v[0] >= 10])
print(f"   per participant P(survey lands on ad | ad-topped page): median {np.median(rates):.2f}, IQR {np.percentile(rates, 25):.2f}–{np.percentile(rates, 75):.2f}, min {rates.min():.2f}, max {rates.max():.2f} (n = {len(rates)})")
out['ad_topped'] = {'n': n, 'ad_block_h_median': float(np.median(a['ad_h'])), 'P_survey_lands_on_ad': a['land_survey'] / n, 'P_first_band_is_ad': a['first_band_is_ad'] / n,
                    'P_skip_to_organic': a['skip_to_organic'] / n, 'skip_landing_below_ad_px_median': float(np.median(a['jump'])), 'ad_fix_in_survey_mean': float(np.mean(a['ad_fix_survey'])),
                    'P_ad_ever': a['ad_ever'] / n, 'P_in_survey_given_ever': a['ad_in_survey_given_ever'] / a['ad_ever'], 'P_later_only_given_ever': a['land_later_only'] / a['ad_ever'],
                    'ad_dwell_share_in_survey_median': float(np.median(np.array(a['ad_dwell_survey']) / np.maximum(np.array(a['ad_dwell_total']), 1))),
                    'P_return_to_ad_after_survey_given_ever': a['returns_to_ad_after_survey'] / a['ad_ever'],
                    'per_participant_rate': {'median': float(np.median(rates)), 'q25': float(np.percentile(rates, 25)), 'q75': float(np.percentile(rates, 75)), 'min': float(rates.min()), 'max': float(rates.max()), 'n': int(len(rates))}}
print('\n4. transitions within the survey (row-normalised, from → to)')
T = defaultdict(Counter)
for (x, y), v in trans.items():
    T[x][y] += v
print(f"   {'from':14s}" + ''.join(f'{c:>14s}' for c in CL) + f"{'n':>7s}")
out['transitions'] = {}
for x in CL:
    N = sum(T[x].values())
    if N:
        print(f'   {x:14s}' + ''.join(f'{T[x][c] / N:14.3f}' for c in CL) + f'{N:7d}')
        out['transitions'][x] = {'n': N, **{c: T[x][c] / N for c in CL}}
json.dump(out, open(ROOT / 'scripts/output/survey_above_fold/summary.json', 'w'), indent=1)
