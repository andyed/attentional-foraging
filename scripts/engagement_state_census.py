#!/usr/bin/env python3
"""Five-state engagement census on the typed map -- the four-class taxonomy
plus a peripheral tier.

    never_onscreen       AOI centre never inside the viewport (no opportunity)
    brief_onscreen       on screen for less than 500 ms in total (no real opportunity)
    unsampled            on screen, never fixated, peripheral intake below the
                         fixated median for its etype
    peripheral           on screen, never fixated, peripheral intake at or
                         above the fixated median for its etype
    rejected             fixated, not clicked, no gaze return (NB22 label False)
    deferred             fixated, not clicked, gaze returned (NB22 label True)
    clicked

Each transition has a channel that witnesses it: the periphery (PAI) for the
first split, gaze for the middle, the cursor for the last two. Regime
[LAB, AdSERP, typed]. Kernel spec_eq2 (bare "PAI" per the 2026-08-31 policy),
peripheral = strictly outside the typed band rect.

Substrate (post-fix, 2026-09-14): the cursor-only typed buf500 mousedown
cache (all-AOI rows, hash-checked against its sidecar) supplies the position
set, `was_clicked`, `etype` and `min_dist`; the NB22 label cache supplies
deferred/rejected; fixations are assigned by the label producer's own rule
(deferred_dwell_carve.visit_decomposition); viewport residence comes from
scroll_only_carve.scroll_features on the canonical scroll stream.

Opportunity baseline. Raw peripheral mass is geometry-confounded (page
position, time on screen), so the primary threshold is a RATE: mass per
second of viewport residence, compared with the median rate of FIXATED AOIs
of the same etype. The raw-mass threshold (the Q3 census convention) is
reported beside it. Trials without a usable scroll stream get residence
`unknown` and are censused on raw mass only.

Outputs
  scripts/output/engagement_state_census/summary.json
  scripts/output/engagement_state_census/states.csv   (one row per (trial, position))
Run: .venv/bin/python scripts/engagement_state_census.py
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))

from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from m4_cursor_aoi_rerun import load_flavor_cards, main_cards  # noqa: E402
from deferred_dwell_carve import visit_decomposition  # noqa: E402
from scroll_only_carve import scroll_features  # noqa: E402
from scroll_kinematics import scroll_stream  # noqa: E402
from pai_spec import rect_alpha_grid  # noqa: E402

OUT_DIR = ROOT / 'scripts/output/engagement_state_census'
APPROACH_PX = 100.0
STATES = ('never_onscreen', 'brief_onscreen', 'unsampled', 'peripheral', 'rejected', 'deferred', 'clicked')
MIN_RESIDENCE_MS = 500.0   # below this a never-fixated AOI had no real opportunity


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--weight-placement', default='eq2', choices=['eq2', 'listing'],
                    help='pai_spec D2 option; kernel sensitivity run uses listing')
    ap.add_argument('--out-dir', type=Path, default=OUT_DIR)
    ap.add_argument('--kernel', default='spec', choices=['spec', 'boundary_cm'],
                    help="spec = the published PAI (vertex OGD, area weight; --weight-placement picks D2). "
                         "boundary_cm = PROPOSAL, not the published method: rect-boundary distance in "
                         "degrees with a cortical-magnification falloff alpha = 1 / (1 + E / E2), 0 inside.")
    ap.add_argument('--e2-deg', type=float, default=2.0, help='boundary_cm half-sensitivity eccentricity (deg)')
    ap.add_argument('--px-per-deg', type=float, default=40.0, help='screen geometry assumption for boundary_cm')
    ap.add_argument('--max-ogd-px', type=float, default=0.0,
                    help='eccentricity gate: fixations further than this from the band rect '
                         'contribute no peripheral mass (0 = published kernel, ungated)')
    args = ap.parse_args()
    out_dir = args.out_dir

    import data_loader as dl

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    want = sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}']
    got = hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    if want != got:
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    rec = {(r['trial_id'], r['position']): r for r in stored}

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    assert len(lab_rows) == len(reg)
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({k[0] for k in rec})
    if args.limit:
        tids = tids[:args.limit]
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)

    rows = []
    skips = Counter()
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  trials {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, 'typed'))
        except Exception:
            skips['cards_failed'] += 1
            continue
        if len(cards) < 2:
            skips['fewer_than_two_aois'] += 1
            continue
        bands = dl.typed_aoi_bands(tid)
        tops = np.asarray([b[0] for b in bands], dtype=float)
        bottoms = np.asarray([b[1] for b in bands], dtype=float)
        etypes = [b[2] for b in bands]
        fixations = dl.load_fixations(tid)
        if not fixations:
            skips['no_fixations'] += 1
            continue
        per_pos, _, _ = visit_decomposition(dl, tid, cards)
        fx = np.array([f['x'] for f in fixations], dtype=float)
        fy = np.array([f['y'] for f in fixations], dtype=float)
        fd = np.array([f.get('d', 200) or 200 for f in fixations], dtype=float)
        inside = ((fx[:, None] >= x0) & (fx[:, None] <= x1)
                  & (fy[:, None] >= tops[None, :]) & (fy[:, None] <= bottoms[None, :]))
        # rect-boundary distance from the fixation to each band (0 inside)
        dxg = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
        dyg = np.maximum.reduce([tops[None, :] - fy[:, None], np.zeros((len(fy), len(tops))),
                                 fy[:, None] - bottoms[None, :]])
        ogd = np.hypot(dxg[:, None], dyg)
        if args.kernel == 'spec':
            alpha = rect_alpha_grid(fx, fy, x0, x1, tops, bottoms, weight_placement=args.weight_placement)
        else:
            alpha = 1.0 / (1.0 + (ogd / args.px_per_deg) / args.e2_deg)
        contrib = ~inside
        if args.max_ogd_px > 0:
            contrib = contrib & (ogd <= args.max_ogd_px)
        mass = (fd[:, None] * np.where(contrib, alpha, 0.0)).sum(axis=0)
        # where does the mass come from: mass-weighted OGD per slot, for the census' own report
        mcontrib = fd[:, None] * np.where(contrib, alpha, 0.0)
        ogd_w = (mcontrib * ogd).sum(axis=0) / np.maximum(mass, 1e-9)
        span_s = max((fixations[-1]['t'] - fixations[0]['t']) / 1000.0, 0.25)

        residence = None
        try:
            stream = scroll_stream(tid, dl)
            geom = dl.get_trial_geometry(tid)
            _dh, scr_h, _ = dl.get_trial_meta(tid)
            if stream is not None and geom is not None and scr_h:
                st, sy = stream
                vf = scroll_features(list(zip(st, sy)), cards, scr_h * geom['ratio_y'])
                residence = {p: v[0] for p, v in vf.items()}
        except Exception:
            residence = None
        if residence is None:
            skips['no_scroll_stream'] += 1

        for p in range(len(bands)):
            r = rec.get((tid, p))
            if r is None:
                skips['position_missing_from_cache'] += 1
                continue
            fixated = p in per_pos
            dwell_ms = float(per_pos[p]['total_dwell_ms']) if fixated else 0.0
            res_ms = residence.get(p) if residence is not None else None
            rows.append({
                'trial_id': tid, 'pid': tid.split('-')[0], 'position': p,
                'etype': etypes[p], 'was_clicked': int(r['was_clicked']),
                'fixated': int(fixated),
                'label': (int(label[(tid, p)]) if (tid, p) in label else -1),
                'approached': int(r['min_dist'] < APPROACH_PX),
                'min_dist': float(r['min_dist']),
                'pai_mass': float(mass[p]),
                'pai_ogd_mean_px': (float(ogd_w[p]) if mass[p] > 0 else None),
                'pai_rate_trial': float(mass[p] / span_s),
                'vp_residence_ms': (float(res_ms) if res_ms is not None else None),
                'pai_rate_vp': (float(mass[p] / (res_ms / 1000.0)) if res_ms else None),
                # matched opportunity: seconds on screen while NOT being fixated
                'pai_rate_unfix': (float(mass[p] / (max(res_ms - dwell_ms, 250.0) / 1000.0)) if res_ms else None),
                'n_visits': (int(per_pos[p]['n_visits']) if fixated else 0),
                'total_dwell_ms': dwell_ms,
            })

    # --- thresholds from FIXATED AOIs, per etype ----------------------------
    thr_rate, thr_mass, thr_unfix = {}, {}, {}
    for et in sorted({r['etype'] for r in rows}):
        fx_rows = [r for r in rows if r['etype'] == et and r['fixated']]
        rates = [r['pai_rate_vp'] for r in fx_rows
                 if r['pai_rate_vp'] is not None and r['vp_residence_ms'] >= MIN_RESIDENCE_MS]
        thr_rate[et] = float(np.median(rates)) if rates else None
        thr_mass[et] = float(np.median([r['pai_mass'] for r in fx_rows])) if fx_rows else None
        # matched: fixated AOIs with at least MIN_RESIDENCE_MS of on-screen-unfixated time
        unf = [r['pai_rate_unfix'] for r in fx_rows
               if r['pai_rate_unfix'] is not None
               and (r['vp_residence_ms'] - r['total_dwell_ms']) >= MIN_RESIDENCE_MS]
        thr_unfix[et] = float(np.median(unf)) if unf else None

    def assign(r, mode):
        if r['was_clicked']:
            return 'clicked'
        if r['fixated']:
            if r['label'] == 1:
                return 'deferred'
            if r['label'] == 0:
                return 'rejected'
            return 'fixated_unlabeled'
        if mode in ('rate', 'unfix'):
            if r['vp_residence_ms'] is None:
                return 'unknown_opportunity'
            if r['vp_residence_ms'] <= 0:
                return 'never_onscreen'
            if r['vp_residence_ms'] < MIN_RESIDENCE_MS:
                return 'brief_onscreen'
            if mode == 'unfix':
                t = thr_unfix[r['etype']]
                return 'peripheral' if (t is not None and r['pai_rate_unfix'] >= t) else 'unsampled'
            t = thr_rate[r['etype']]
            return 'peripheral' if (t is not None and r['pai_rate_vp'] >= t) else 'unsampled'
        t = thr_mass[r['etype']]
        return 'peripheral' if (t is not None and r['pai_mass'] >= t) else 'unsampled'

    for r in rows:
        r['state'] = assign(r, 'unfix')       # primary: matched-opportunity rate
        r['state_rate'] = assign(r, 'rate')   # lenient: raw residence rate
        r['state_mass'] = assign(r, 'mass')   # conservative: raw full-trial mass

    # --- census ---------------------------------------------------------------
    def census(key):
        out = {}
        for et in sorted({r['etype'] for r in rows}):
            c = Counter(r[key] for r in rows if r['etype'] == et)
            n = sum(c.values())
            out[et] = {'n': n, **{s: c.get(s, 0) for s in STATES + ('fixated_unlabeled', 'unknown_opportunity')},
                       'share': {s: round(c.get(s, 0) / n, 4) for s in STATES}}
        c = Counter(r[key] for r in rows)
        n = len(rows)
        out['ALL'] = {'n': n, **{s: c.get(s, 0) for s in STATES + ('fixated_unlabeled', 'unknown_opportunity')},
                      'share': {s: round(c.get(s, 0) / n, 4) for s in STATES}}
        return out

    # never-fixated split conditional on opportunity (the honest denominator)
    def nf_split(key):
        out = {}
        for et in sorted({r['etype'] for r in rows}) + ['ALL']:
            sel = [r for r in rows if (et == 'ALL' or r['etype'] == et) and not r['fixated']
                   and r[key] in ('peripheral', 'unsampled')]
            n = len(sel)
            k = sum(r[key] == 'peripheral' for r in sel)
            out[et] = {'never_fixated_onscreen': n, 'peripheral': k,
                       'peripheral_share': (round(k / n, 4) if n else None)}
        return out

    # the CHIIR carve's 663 "approached but never fixated" rows
    chiir = [r for r in rows if r['approached'] and not r['was_clicked'] and not r['fixated']]
    chiir_split = {'n': len(chiir), 'unfix': dict(Counter(r['state'] for r in chiir)),
                   'rate': dict(Counter(r['state_rate'] for r in chiir)),
                   'mass': dict(Counter(r['state_mass'] for r in chiir))}

    # per-participant peripheral share among never-fixated on-screen AOIs
    pp = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r['fixated'] and r['state'] in ('peripheral', 'unsampled'):
            pp[r['pid']][1] += 1
            pp[r['pid']][0] += (r['state'] == 'peripheral')
    pp_share = {p: v[0] / v[1] for p, v in pp.items() if v[1] >= 20}
    shares = np.array(list(pp_share.values()))

    # adjacent-position transitions in display order (what follows what)
    trans = Counter()
    by_trial = defaultdict(dict)
    for r in rows:
        by_trial[r['trial_id']][r['position']] = r['state']
    for tid, d in by_trial.items():
        for p in sorted(d):
            if p + 1 in d:
                trans[(d[p], d[p + 1])] += 1
    trans_out = {}
    for a in STATES:
        row_n = sum(v for (x, _y), v in trans.items() if x == a)
        trans_out[a] = {b: (round(trans.get((a, b), 0) / row_n, 4) if row_n else None) for b in STATES}
        trans_out[a]['n'] = row_n

    out = {
        'schema_version': 1,
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'regime': '[LAB, AdSERP, typed]',
        'kernel': (f'spec_{args.weight_placement} (published PAI)' if args.kernel == 'spec'
                   else f'boundary_cm PROPOSAL: alpha = 1/(1 + E/{args.e2_deg:g}deg), {args.px_per_deg:g} px/deg')
                  + ', peripheral = outside typed band rect'
                  + (f', eccentricity gate OGD <= {args.max_ogd_px:.0f} px' if args.max_ogd_px > 0 else ', ungated'),
        'intake_eccentricity_px': {
            s_: {'median_of_slot_mass_weighted_ogd': float(np.median([r['pai_ogd_mean_px'] for r in rows if r['state'] == s_ and r['pai_ogd_mean_px'] is not None]))
                 if any(r['state'] == s_ and r['pai_ogd_mean_px'] is not None for r in rows) else None}
            for s_ in ('peripheral', 'unsampled', 'rejected', 'deferred', 'clicked')},
        'inputs': {'feature_cache': 'AdSERP/data/cursor-only-typed-features-mousedown.json',
                   'feature_cache_sha256': sha256(args.feature_cache),
                   'label_cache_sha256': sha256(ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'),
                   'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event']},
        'population': {'trials': len(by_trial), 'rows': len(rows),
                       'participants': len({r['pid'] for r in rows}), 'skips': dict(skips)},
        'thresholds': {'unfixated_rate_per_s_by_etype': thr_unfix, 'rate_per_s_by_etype': thr_rate, 'mass_by_etype': thr_mass,
                       'min_residence_ms': MIN_RESIDENCE_MS, 'rule': 'never-fixated AOI is peripheral iff its intake >= the median of FIXATED AOIs of the same etype; '
                               'PRIMARY (state) = mass per second of on-screen-UNFIXATED time (residence minus own dwell); '
                               'lenient (state_rate) = mass per second of residence; conservative (state_mass) = raw full-trial mass'},
        'census_unfix': census('state'),
        'census_rate': census('state_rate'),
        'census_mass': census('state_mass'),
        'never_fixated_onscreen_split_unfix': nf_split('state'),
        'never_fixated_onscreen_split_rate': nf_split('state_rate'),
        'never_fixated_split_mass': nf_split('state_mass'),
        'chiir_never_fixated_rows': chiir_split,
        'participant_peripheral_share': {'n_participants': len(pp_share),
                                         'median': float(np.median(shares)) if len(shares) else None,
                                         'iqr': [float(np.percentile(shares, 25)), float(np.percentile(shares, 75))] if len(shares) else None,
                                         'min': float(shares.min()) if len(shares) else None,
                                         'max': float(shares.max()) if len(shares) else None},
        'transitions_display_order_rate': trans_out,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_dir / 'summary.json', 'w'), indent=1)
    with open(out_dir / 'states.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nrows {len(rows):,}  trials {len(by_trial):,}  skips {dict(skips)}")
    print('\nCENSUS (matched unfixated-rate rule)  n   never_on  brief  unsamp  periph  reject  defer  click')
    for et, c in out['census_unfix'].items():
        print(f"  {et:16s} {c['n']:7,} {c['never_onscreen']:9,} {c['brief_onscreen']:6,} {c['unsampled']:7,} {c['peripheral']:7,} "
              f"{c['rejected']:7,} {c['deferred']:6,} {c['clicked']:6,}")
    print('\nnever-fixated ON-SCREEN split: peripheral share by etype  (matched / lenient / mass)')
    for et in out['never_fixated_onscreen_split_unfix']:
        a = out['never_fixated_onscreen_split_unfix'][et]; b = out['never_fixated_onscreen_split_rate'][et]; c = out['never_fixated_split_mass'][et]
        print(f"  {et:16s} n={a['never_fixated_onscreen']:6,}  {a['peripheral_share']} / {b['peripheral_share']} / {c['peripheral_share']}")
    print(f"\nCHIIR approached-never-fixated rows: {out['chiir_never_fixated_rows']}")
    print(f"participant peripheral share: {out['participant_peripheral_share']}")
    print(f"intake eccentricity (median per-slot mass-weighted OGD px): "
          + ', '.join(f"{k} {v['median_of_slot_mass_weighted_ogd']:.0f}" for k, v in out['intake_eccentricity_px'].items() if v['median_of_slot_mass_weighted_ogd'] is not None))
    print('\ntransitions (display order, row-normalised):')
    for a, d in trans_out.items():
        print(f"  {a:14s} n={d['n']:6,} " + ' '.join(f"{b[:6]} {d[b]}" for b in STATES))
    print(f'\nwrote {out_dir}')


if __name__ == '__main__':
    main()
