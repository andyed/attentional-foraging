#!/usr/bin/env python3
"""Does the periphery navigate? Two tests of a peripheral role that is not
content evaluation.

The engagement census found a sampling tier but every content cue is null
by state (semantic proxies, coarse cues, bold density). Reading and scene
research give the periphery a different job: selecting where the eyes go
next from coarse layout, and holding a gist map. Two tests on AdSERP:

(A) Skip is a layout decision. Among on-screen, non-clicked result slots,
    predict "fixated at all" from features the periphery can resolve at
    SERP eccentricities (element type, block height, position, time on
    screen) versus features that need the fovea (query-to-text cosine,
    snippet length, bold share). LOSO logistic regression by participant.
    Prediction if the periphery steers on format: layout >> content, and
    content adds nothing over layout.

(B) The survey leaves a map. Peripheral intake during the first five
    fixations (the survey phase, NB13) on slots NOT fixated during those
    five, versus whether the slot is fixated later in the trial. Intake
    kernel: boundary-distance cortical-magnification falloff, 24 px/deg,
    gated at 200 px (~8 deg) -- `scripts/peripheral_kernel.py`. Control:
    mean gaze distance to the slot during the survey. Position is removed
    by a within-trial rank. Prediction if the survey builds a map the
    evaluate phase follows: survey intake predicts later fixation beyond
    position, and does so beyond plain distance only if the kernel adds
    something distance does not.

Regime [LAB, AdSERP, typed]. Inputs: the primary census states
(engagement_state_census/gate_200px/states.csv), the organic content
features, the bold-density rows, fixations by the label producer's rule.
Output: scripts/output/periphery_navigates/summary.json
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from m4_cursor_aoi_rerun import load_flavor_cards  # noqa: E402
from peripheral_kernel import alpha_grid, boundary_ogd  # noqa: E402

STATES = ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv'
CONTENT = ROOT / 'AdSERP/data/content-features-by-position-organic.json'
BOLD = ROOT / 'scripts/output/bold_term_density/by_trial.json'
OUT = ROOT / 'scripts/output/periphery_navigates'
SURVEY_FIX = 5
GATE_PX = 200.0
import argparse as _ap
_a = _ap.ArgumentParser(); _a.add_argument('--px-per-deg', type=float, default=24.0); _a.add_argument('--suffix', default='')
_ARGS = _a.parse_args()
PX_PER_DEG = _ARGS.px_per_deg   # 24 = the 2026-09-14 runs; 43 = the derived AdSERP scale
ETYPES = ('organic', 'native_ad', 'dd_top', 'image_pack', 'paa', 'top_places', 'unknown_widget', 'other_widget')


def loso_auc(X, y, pid):
    X = np.asarray(X, float)
    proba = np.full(len(y), np.nan)
    for p in np.unique(pid):
        tr, te = pid != p, pid == p
        if len(set(y[tr])) < 2 or not te.any():
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
        m.fit(X[tr], y[tr])
        proba[te] = m.predict_proba(X[te])[:, 1]
    ok = np.isfinite(proba)
    folds = {}
    for p in np.unique(pid):
        s = ok & (pid == p)
        if len(set(y[s])) == 2:
            folds[p] = roc_auc_score(y[s], proba[s])
    return float(roc_auc_score(y[ok], proba[ok])), folds


def paired(a, b):
    ps = sorted(set(a) & set(b))
    d = np.array([a[p] - b[p] for p in ps])
    rng = np.random.default_rng(20260914)
    m = rng.choice(d, size=(10000, len(d)), replace=True).mean(axis=1)
    return {'n': len(ps), 'mean_delta': float(d.mean()), 'ci95': np.quantile(m, [.025, .975]).tolist()}


def main():
    import data_loader as dl
    rows = list(csv.DictReader(open(STATES)))
    for r in rows:
        r['position'] = int(r['position'])
        r['fixated'] = r['fixated'] == '1'
        r['vp'] = float(r['vp_residence_ms']) if r['vp_residence_ms'] else np.nan
    by = defaultdict(dict)
    for r in rows:
        by[r['trial_id']][r['position']] = r
    content = json.loads(CONTENT.read_text())
    bold = json.loads(BOLD.read_text())

    # ---------------- (A) skip is a layout decision ----------------------
    heights, cos_by, bold_by = {}, {}, {}
    for tid, d in by.items():
        try:
            bands = dl.typed_aoi_bands(tid)
            tcards = {c['position']: c for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0}
            ocards = load_flavor_cards(dl, tid, 'organic')
        except Exception:
            continue
        for p, b in enumerate(bands):
            heights[(tid, p)] = float(b[1] - b[0])
        geo = {(int(c['y']), int(c['height'])): int(c['position']) for c in ocards if c.get('position', -1) >= 0}
        feats = {int(f['pos']): f for f in content.get(tid, {}).get('positions', [])}
        bt = bold.get(tid) if isinstance(bold.get(tid), list) else None
        for p, r in d.items():
            if r['etype'] != 'organic':
                continue
            tc = tcards.get(p)
            k = geo.get((int(tc['y']), int(tc['height']))) if tc else None
            f = feats.get(k) if k is not None else None
            if f is None:
                continue
            cos_by[(tid, p)] = (f.get('q_text_cosine'), f.get('snippet_chars'))
            h = int(f['source_h3_pos'])
            if bt is not None and h < len(bt):
                bold_by[(tid, p)] = bt[h]['bold_share']

    pool = [r for r in rows if r['state'] in ('unsampled', 'peripheral', 'rejected', 'deferred')
            and np.isfinite(r['vp']) and r['vp'] >= 500 and (r['trial_id'], r['position']) in heights]
    y = np.array([int(r['fixated']) for r in pool])
    pid = np.array([r['pid'] for r in pool])

    def layout(r):
        k = (r['trial_id'], r['position'])
        return [r['position'], heights[k], np.log1p(r['vp'])] + [int(r['etype'] == e) for e in ETYPES[:-1]]
    XL = [layout(r) for r in pool]
    aucL, fL = loso_auc(XL, y, pid)
    aucP, fP = loso_auc([[r['position']] for r in pool], y, pid)
    aucV, fV = loso_auc([[np.log1p(r['vp'])] for r in pool], y, pid)
    aucH, fH = loso_auc([[heights[(r['trial_id'], r['position'])]] for r in pool], y, pid)
    aucE, fE = loso_auc([[int(r['etype'] == e) for e in ETYPES[:-1]] for r in pool], y, pid)
    # layout WITHOUT time on screen: what the periphery can read, with opportunity held out
    XLnr = [[r['position'], heights[(r['trial_id'], r['position'])]] + [int(r['etype'] == e) for e in ETYPES[:-1]] for r in pool]
    aucLnr, fLnr = loso_auc(XLnr, y, pid)
    aucPH, _ = loso_auc([[r['position'], heights[(r['trial_id'], r['position'])]] for r in pool], y, pid)
    aucPE, _ = loso_auc([[r['position']] + [int(r['etype'] == e) for e in ETYPES[:-1]] for r in pool], y, pid)
    resA = {'pool': {'n': len(pool), 'fixated': int(y.sum()), 'participants': len(set(pid)),
                     'definition': 'on-screen >= 500 ms, opportunity known, not clicked'},
            'all_slots': {'layout (position+height+residence+etype)': aucL,
                          'layout without residence (position+height+etype)': aucLnr,
                          'position + height': aucPH, 'position + etype': aucPE,
                          'position only': aucP, 'residence only': aucV, 'height only': aucH, 'etype only': aucE,
                          'paired layout-without-residence vs position': paired(fLnr, fP)}}
    # organic subset with content features
    org = [i for i, r in enumerate(pool) if (r['trial_id'], r['position']) in cos_by
           and cos_by[(r['trial_id'], r['position'])][0] is not None
           and (r['trial_id'], r['position']) in bold_by]
    yo, po = y[org], pid[org]
    XLo = [XL[i][:2] for i in org]   # position + height; residence held out, etype constant on organics
    XC = [[cos_by[(pool[i]['trial_id'], pool[i]['position'])][0],
           np.log1p(cos_by[(pool[i]['trial_id'], pool[i]['position'])][1] or 0),
           bold_by[(pool[i]['trial_id'], pool[i]['position'])]] for i in org]
    aLo, fLo = loso_auc(XLo, yo, po)
    aCo, fCo = loso_auc(XC, yo, po)
    aBo, fBo = loso_auc([a + b for a, b in zip(XLo, XC)], yo, po)
    resA['organic_slots'] = {'n': len(org), 'fixated': int(yo.sum()),
                             'layout without residence (position+height)': aLo,
                             'content (query cosine + snippet length + bold share)': aCo,
                             'layout + content': aBo,
                             'paired layout+content vs layout': paired(fBo, fLo),
                             'paired layout vs content': paired(fLo, fCo)}

    # ---------------- (B) the survey leaves a map ------------------------
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
    ev = []
    n_tr = 0
    for tid, d in by.items():
        fx_ = dl.load_fixations(tid)
        try:
            bands = dl.typed_aoi_bands(tid)
        except Exception:
            continue
        if not fx_ or len(fx_) <= SURVEY_FIX or not bands:
            continue
        tops = np.asarray([b[0] for b in bands], float)
        bots = np.asarray([b[1] for b in bands], float)
        fx = np.array([f['x'] for f in fx_], float)[:SURVEY_FIX]
        fy = np.array([f['y'] for f in fx_], float)[:SURVEY_FIX]
        fd = np.array([f.get('d', 200) or 200 for f in fx_], float)[:SURVEY_FIX]
        alpha = alpha_grid(fx, fy, x0, x1, tops, bots, kernel='boundary_cm', px_per_deg=PX_PER_DEG)
        ogd = boundary_ogd(fx, fy, x0, x1, tops, bots)
        inside = ogd == 0
        contrib = (~inside) & (ogd <= GATE_PX)
        intake = (fd[:, None] * np.where(contrib, alpha, 0.0)).sum(axis=0)
        gdist = ogd.mean(axis=0)
        survey_fixated = inside.any(axis=0)
        n_tr += 1
        cand = []
        for p, r in d.items():
            if p >= len(bands) or survey_fixated[p] or r['state'] in ('never_onscreen', 'unknown_opportunity'):
                continue
            if r['was_clicked'] == '1':
                continue
            cand.append((p, r))
        if len(cand) < 2:
            continue
        ints = np.array([intake[p] for p, _ in cand])
        dists = np.array([gdist[p] for p, _ in cand])
        rank_i = (np.argsort(np.argsort(-ints)) + 1) / len(cand)
        rank_d = (np.argsort(np.argsort(dists)) + 1) / len(cand)
        for (p, r), it, dd, ri, rd in zip(cand, ints, dists, rank_i, rank_d):
            ev.append({'pid': r['pid'], 'tid': tid, 'position': p, 'later_fixated': int(r['fixated']),
                       'intake': float(it), 'gdist': float(dd), 'rank_intake': float(ri), 'rank_gdist': float(rd)})
    yb = np.array([e['later_fixated'] for e in ev])
    pb = np.array([e['pid'] for e in ev])
    a_int, f_int = loso_auc([[e['intake']] for e in ev], yb, pb)
    a_rint, f_rint = loso_auc([[e['rank_intake']] for e in ev], yb, pb)
    a_dist, f_dist = loso_auc([[-e['gdist']] for e in ev], yb, pb)
    a_rdist, f_rdist = loso_auc([[e['rank_gdist']] for e in ev], yb, pb)
    a_pos, f_pos = loso_auc([[e['position']] for e in ev], yb, pb)
    a_pos_int, f_pos_int = loso_auc([[e['position'], e['rank_intake']] for e in ev], yb, pb)
    a_pos_dist, f_pos_dist = loso_auc([[e['position'], e['rank_gdist']] for e in ev], yb, pb)
    a_all, f_all = loso_auc([[e['position'], e['rank_intake'], e['rank_gdist']] for e in ev], yb, pb)
    # within-trial: does the top-intake unfixated candidate get fixated later more than the bottom?
    top = bot = topn = botn = 0
    for tid in {e['tid'] for e in ev}:
        c = [e for e in ev if e['tid'] == tid]
        if len(c) < 3:
            continue
        c.sort(key=lambda e: -e['intake'])
        top += c[0]['later_fixated']; topn += 1
        bot += c[-1]['later_fixated']; botn += 1
    resB = {'trials': n_tr, 'candidates': len(ev), 'later_fixated': int(yb.sum()),
            'definition': f'slots not fixated in the first {SURVEY_FIX} fixations, on screen, not clicked; intake = boundary_cm 24 px/deg gated {GATE_PX:.0f} px',
            'auc': {'survey intake': a_int, 'survey intake (within-trial rank)': a_rint,
                    'survey gaze distance': a_dist, 'survey gaze distance (rank)': a_rdist,
                    'position only': a_pos, 'position + intake rank': a_pos_int,
                    'position + distance rank': a_pos_dist, 'position + both ranks': a_all},
            'paired': {'position+intake vs position': paired(f_pos_int, f_pos),
                       'position+distance vs position': paired(f_pos_dist, f_pos),
                       'position+both vs position+distance': paired(f_all, f_pos_dist)},
            'within_trial_top_vs_bottom_intake_later_fixated': {'top': top / topn if topn else None,
                                                                'bottom': bot / botn if botn else None, 'n_trials': topn}}

    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]', 'A_skip_is_layout': resA, 'B_survey_map': resB}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / f'summary{_ARGS.suffix}.json', 'w'), indent=1)

    print(f"(A) pool n={len(pool):,} fixated {int(y.sum()):,}")
    for k, v in resA['all_slots'].items():
        if isinstance(v, float):
            print(f"    {k:48s} LOSO AUC {v:.3f}")
    print(f"    paired layout-without-residence vs position: {resA['all_slots']['paired layout-without-residence vs position']}")
    print(f"    organic subset n={len(org):,}")
    for k, v in resA['organic_slots'].items():
        if isinstance(v, float):
            print(f"    {k:48s} LOSO AUC {v:.3f}")
    print(f"    paired layout+content vs layout: {resA['organic_slots']['paired layout+content vs layout']}")
    print(f"    paired layout vs content:        {resA['organic_slots']['paired layout vs content']}")
    print(f"\n(B) trials {n_tr:,}, candidates {len(ev):,}, later fixated {int(yb.sum()):,}")
    for k, v in resB['auc'].items():
        print(f"    {k:40s} LOSO AUC {v:.3f}")
    for k, v in resB['paired'].items():
        print(f"    paired {k}: {v}")
    print(f"    within-trial: top-intake candidate later fixated {resB['within_trial_top_vs_bottom_intake_later_fixated']}")
    print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
