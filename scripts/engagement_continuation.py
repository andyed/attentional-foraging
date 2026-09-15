#!/usr/bin/env python3
"""Continuation four ways, examination cost tiers, and whether the periphery
evaluates -- the C/W/L-facing reading of the five-state census.

Consumes scripts/output/engagement_state_census/states.csv (one row per
typed result slot, state assigned under the matched-opportunity rule) plus
the cursor cache and the organic content features. Regime [LAB, AdSERP,
typed]; kernel spec_eq2 inherited from the census.

(a) Continuation C(i) = P(reached i+1 | reached i) and reach R(i), under
    four operationalisations of "viewed": viewport (residence > 0),
    periphery (peripheral intake at or above the fixated median, or deeper),
    fixation (any gaze visit), cursor (approached within 100 px). C/W/L's
    C(i) is one function; the corpus gives four, and they diverge with depth.
    Computed on the trials where opportunity is known for every slot, so the
    four curves share a denominator.
(b) Examination cost by state: median gaze dwell, cursor proximity dwell and
    visit count. The per-element cost model of Azzopardi, Thomas & Craswell
    (SIGIR 2018) measured, with the peripheral tier at zero fixation cost.
(c) Position-matched peripheral split: for never-fixated on-screen slots the
    threshold is the median unfixated-rate of FIXATED slots of the same etype
    AND position, and the skipped-vs-read distributions are compared at
    matched (etype, position) with an AUC (0.5 = indistinguishable).
(d) Does the periphery evaluate? On organic slots, query-to-result cosine
    (content-features, organic flavour; typed organic slot k joined to organic
    position k) by state, with a within-trial rank so position is removed.
    Prediction if peripheral sampling is rejection: peripheral < unsampled
    on relevance, and peripheral < rejected/deferred.

Output: scripts/output/engagement_continuation/summary.json
Run:    .venv/bin/python scripts/engagement_continuation.py
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import sys

import numpy as np
from scipy.stats import mannwhitneyu

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
CENSUS = ROOT / 'scripts/output/engagement_state_census'
OUT = ROOT / 'scripts/output/engagement_continuation'
CACHE = ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json'
CONTENT = ROOT / 'AdSERP/data/content-features-by-position-organic.json'
MAXP = 10
STATES = ('never_onscreen', 'brief_onscreen', 'unsampled', 'peripheral', 'rejected', 'deferred', 'clicked')


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def auc_pair(a, b):
    """P(a > b) + 0.5 P(a == b) via Mann-Whitney U."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return None
    u = mannwhitneyu(a, b, alternative='two-sided')
    return {'auc': float(u.statistic / (len(a) * len(b))), 'p': float(u.pvalue), 'n_a': len(a), 'n_b': len(b)}


def cluster_ci(vals, pids, stat=np.median, n=3000, seed=20260914):
    rng = np.random.default_rng(seed)
    vals, pids = np.asarray(vals, float), np.asarray(pids)
    groups = [vals[pids == p] for p in np.unique(pids)]
    out = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        out.append(stat(np.concatenate([groups[k] for k in pick])))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def main():
    global CENSUS, OUT
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--census-dir', type=Path, default=CENSUS)
    ap.add_argument('--out-dir', type=Path, default=OUT)
    args = ap.parse_args()
    CENSUS, OUT = args.census_dir, args.out_dir
    rows = list(csv.DictReader(open(CENSUS / 'states.csv')))
    census = json.loads((CENSUS / 'summary.json').read_text())
    cache = json.loads(CACHE.read_text())['conditions']['buf500']
    rec = {(r['trial_id'], r['position']): r for r in cache}
    for r in rows:
        r['position'] = int(r['position'])
        r['fixated'] = r['fixated'] == '1'
        r['approached'] = r['approached'] == '1'
        r['total_dwell_ms'] = float(r['total_dwell_ms'])
        r['n_visits'] = int(r['n_visits'])
        r['pai_rate_unfix'] = float(r['pai_rate_unfix']) if r['pai_rate_unfix'] else np.nan
        r['vp_residence_ms'] = float(r['vp_residence_ms']) if r['vp_residence_ms'] else np.nan
        c = rec[(r['trial_id'], r['position'])]
        r['cursor_dwell_ms'] = float(c['dwell_in_proximity_ms'])
    by = defaultdict(dict)
    for r in rows:
        by[r['trial_id']][r['position']] = r
    known = {tid for tid, d in by.items()
             if all(x['state'] != 'unknown_opportunity' for x in d.values())}

    # ---- (a) continuation four ways ---------------------------------------
    chan = {
        'viewport': lambda r: r['state'] != 'never_onscreen',
        'periphery': lambda r: r['state'] in ('peripheral', 'rejected', 'deferred', 'clicked'),
        'fixation': lambda r: r['fixated'],
        'cursor': lambda r: r['approached'],
    }
    cont, reach = {c: [] for c in chan}, {c: [] for c in chan}
    n_pos = []
    for i in range(MAXP):
        n_pos.append(sum(1 for t in known if i in by[t]))
        for c, f in chan.items():
            num = den = 0
            hit = tot = 0
            for t in known:
                d = by[t]
                if i in d:
                    tot += 1
                    hit += f(d[i])
                    if i + 1 in d and f(d[i]):
                        den += 1
                        num += f(d[i + 1])
            reach[c].append(hit / tot if tot else None)
            cont[c].append(num / den if den else None)
    # ---- (a2) ordered first-pass continuation: the strict C/W/L version --
    # A result is first-pass viewed if its first fixation precedes the first
    # fixation on every deeper result (or no deeper result is ever fixated).
    # C_fp(i) = P(first-pass i+1 | first-pass i). Fixations assigned by the
    # label producer's rule on the typed map, as everywhere else.
    import data_loader as dl
    fp_reach = [0] * MAXP
    fp_cont_num, fp_cont_den = [0] * MAXP, [0] * MAXP
    fp_tot = [0] * MAXP
    n_fp_trials = 0
    for t in known:
        d = by[t]
        try:
            tops = dl.typed_aoi_tops(t)
            fixs = dl.load_fixations(t)
        except Exception:
            continue
        if not fixs or not tops:
            continue
        n_fp_trials += 1
        t_first = {}
        for f in fixs:
            q = dl.assign_fixation_to_position(f['y'], tops, len(tops))
            if q is not None and q >= 0 and q not in t_first:
                t_first[q] = float(f['t'])
        deeper_min = {}
        cur = float('inf')
        for q in range(len(tops) - 1, -1, -1):
            deeper_min[q] = cur
            if q in t_first:
                cur = min(cur, t_first[q])
        fp = {q: (q in t_first and t_first[q] <= deeper_min[q]) for q in range(len(tops))}
        for i in range(min(MAXP, len(tops))):
            fp_tot[i] += 1
            fp_reach[i] += fp[i]
            if i + 1 < len(tops) and fp[i]:
                fp_cont_den[i] += 1
                fp_cont_num[i] += fp[i + 1]
    reach['fixation_first_pass'] = [fp_reach[i] / fp_tot[i] if fp_tot[i] else None for i in range(MAXP)]
    cont['fixation_first_pass'] = [fp_cont_num[i] / fp_cont_den[i] if fp_cont_den[i] else None for i in range(MAXP)]
    chan['fixation_first_pass'] = None

    # ---- (b) cost tiers by state ------------------------------------------
    cost = {}
    for s in STATES:
        sel = [r for r in rows if r['state'] == s]
        if not sel:
            continue
        pid = [r['pid'] for r in sel]
        cost[s] = {'n': len(sel),
                   'gaze_dwell_ms_median': float(np.median([r['total_dwell_ms'] for r in sel])),
                   'gaze_dwell_ci': cluster_ci([r['total_dwell_ms'] for r in sel], pid),
                   'cursor_dwell_ms_median': float(np.median([r['cursor_dwell_ms'] for r in sel])),
                   'cursor_dwell_ci': cluster_ci([r['cursor_dwell_ms'] for r in sel], pid),
                   'n_visits_median': float(np.median([r['n_visits'] for r in sel])),
                   'approached_share': float(np.mean([r['approached'] for r in sel]))}

    # ---- (c) position-matched peripheral split ----------------------------
    thr = {}
    fixated_rates = defaultdict(list)
    for r in rows:
        if r['fixated'] and np.isfinite(r['pai_rate_unfix']) and (r['vp_residence_ms'] - r['total_dwell_ms']) >= 500:
            fixated_rates[(r['etype'], min(r['position'], MAXP - 1))].append(r['pai_rate_unfix'])
    for k, v in fixated_rates.items():
        thr[k] = float(np.median(v)) if len(v) >= 20 else None
    skipped = [r for r in rows if not r['fixated'] and r['state'] in ('peripheral', 'unsampled')]
    pm = {'n': 0, 'peripheral': 0, 'no_threshold': 0}
    by_pos = defaultdict(lambda: {'skipped': [], 'read': []})
    for r in skipped:
        k = (r['etype'], min(r['position'], MAXP - 1))
        t = thr.get(k)
        if t is None:
            pm['no_threshold'] += 1
            continue
        pm['n'] += 1
        pm['peripheral'] += int(r['pai_rate_unfix'] >= t)
        by_pos[k]['skipped'].append(r['pai_rate_unfix'])
    for k, v in fixated_rates.items():
        by_pos[k]['read'] = v
    pm['peripheral_share'] = pm['peripheral'] / pm['n'] if pm['n'] else None
    # distributional comparison at matched (etype, position): pooled AUC over
    # strata weighted by skipped count, plus the organic per-position rows
    strata = []
    for k, v in by_pos.items():
        if len(v['skipped']) >= 20 and len(v['read']) >= 20:
            a = auc_pair(v['skipped'], v['read'])
            strata.append({'etype': k[0], 'position': k[1], **a})
    w = np.array([s['n_a'] for s in strata], float)
    pm['matched_auc_skipped_vs_read_weighted'] = float(np.sum(w * np.array([s['auc'] for s in strata])) / w.sum()) if len(w) else None
    pm['strata'] = strata

    # ---- (d) does the periphery evaluate? relevance by state --------------
    # Typed organic slots are joined to organic-flavour cards on page-space
    # geometry (same y and height; both flavours measure the same DOM boxes),
    # then organic position k -> content-features organic pos k. A typed
    # organic slot with no geometric twin in the organic flavour is skipped.
    import data_loader as dl
    from m4_cursor_aoi_rerun import load_flavor_cards
    typed_cards = {}
    content = json.loads(CONTENT.read_text())
    rel_rows = []
    n_mismatch = n_joined = n_unmatched = 0
    for tid, d in by.items():
        org = [d[p] for p in sorted(d) if d[p]['etype'] == 'organic']
        if not org:
            continue
        try:
            tcards = {c['position']: c for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0}
            ocards = load_flavor_cards(dl, tid, 'organic')
        except Exception:
            n_mismatch += 1
            continue
        geo = {(int(c['y']), int(c['height'])): int(c['position']) for c in ocards if c.get('position', -1) >= 0}
        feats = content.get(tid, {}).get('positions', [])
        cos_by_pos = {int(f['pos']): f.get('q_text_cosine') for f in feats}
        joined = []
        for r in org:
            tc = tcards.get(r['position'])
            if tc is None:
                n_unmatched += 1
                continue
            k = geo.get((int(tc['y']), int(tc['height'])))
            c = cos_by_pos.get(k) if k is not None else None
            if c is None or not np.isfinite(c):
                n_unmatched += 1
                continue
            joined.append((r, float(c)))
        if len(joined) < 2:
            continue
        n_joined += 1
        cos = np.asarray([c for _, c in joined])
        ranks = (np.argsort(np.argsort(-cos)) + 1) / len(cos)   # 1/n = most relevant in trial
        for (r, c), rk in zip(joined, ranks):
            rel_rows.append({'pid': r['pid'], 'state': r['state'], 'position': r['position'],
                             'cos': c, 'rel_rank': float(rk)})
    rel = {'n_trials_joined': n_joined, 'n_slots_joined': len(rel_rows),
           'n_slots_unmatched': n_unmatched, 'n_trials_load_failed': n_mismatch, 'by_state': {}}
    for s in STATES:
        sel = [x for x in rel_rows if x['state'] == s]
        if len(sel) < 30:
            continue
        rel['by_state'][s] = {'n': len(sel),
                              'cos_median': float(np.median([x['cos'] for x in sel])),
                              'cos_ci': cluster_ci([x['cos'] for x in sel], [x['pid'] for x in sel]),
                              'rel_rank_median': float(np.median([x['rel_rank'] for x in sel])),
                              'rel_rank_ci': cluster_ci([x['rel_rank'] for x in sel], [x['pid'] for x in sel])}
    def pair(a, b, key):
        A = [x[key] for x in rel_rows if x['state'] == a]
        B = [x[key] for x in rel_rows if x['state'] == b]
        return auc_pair(A, B)
    rel['tests'] = {
        'peripheral_vs_unsampled_cos': pair('peripheral', 'unsampled', 'cos'),
        'peripheral_vs_unsampled_rel_rank': pair('peripheral', 'unsampled', 'rel_rank'),
        'peripheral_vs_rejected_cos': pair('peripheral', 'rejected', 'cos'),
        'peripheral_vs_rejected_rel_rank': pair('peripheral', 'rejected', 'rel_rank'),
        'rejected_vs_deferred_rel_rank': pair('rejected', 'deferred', 'rel_rank'),
        'deferred_vs_clicked_rel_rank': pair('deferred', 'clicked', 'rel_rank'),
    }
    # position-matched version of the key contrast (positions 2..9, where skips live)
    strat = []
    for p in range(MAXP):
        A = [x['cos'] for x in rel_rows if x['state'] == 'peripheral' and x['position'] == p]
        B = [x['cos'] for x in rel_rows if x['state'] == 'unsampled' and x['position'] == p]
        if len(A) >= 20 and len(B) >= 20:
            strat.append({'position': p, **auc_pair(A, B)})
    rel['tests']['peripheral_vs_unsampled_cos_by_position'] = strat

    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]', 'kernel': census['kernel'],
           'inputs': {'states_csv_sha256': sha256(CENSUS / 'states.csv'),
                      'census_generated_utc': census['generated_utc'],
                      'cache_sha256': sha256(CACHE), 'content_sha256': sha256(CONTENT)},
           'population': {'trials_all': len(by), 'trials_opportunity_known': len(known),
                          'n_by_position_known': n_pos},
           'continuation': {'reach': reach, 'continuation': cont,
                            'note': 'viewport/periphery/fixation/cursor = flag at any time in the trial; '
                                    'fixation_first_pass = first fixation precedes the first fixation on every deeper result '
                                    f'(strict C/W/L viewing order; {n_fp_trials} trials)'},
           'cost_by_state': cost,
           'position_matched_peripheral_split': pm,
           'relevance_by_state': rel}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / 'summary.json', 'w'), indent=1)

    print(f"trials {len(by):,}; opportunity known on {len(known):,}")
    print('\nREACH R(i) by channel (known-opportunity trials)')
    print('  pos   n    viewport periphery fixation cursor   first-pass')
    for i in range(MAXP):
        print(f"  {i:3d} {n_pos[i]:5d}   " + ' '.join(f"{reach[c][i]:8.3f}" for c in chan))
    print('\nCONTINUATION C(i) = P(reached i+1 | reached i)')
    for i in range(MAXP - 1):
        print(f"  {i:3d}→{i+1:<3d}      " + ' '.join(f"{cont[c][i]:8.3f}" if cont[c][i] is not None else '     -  ' for c in chan))
    print('\nCOST by state: gaze dwell / cursor dwell (median ms), visits, approached share')
    for s, c in cost.items():
        print(f"  {s:15s} n={c['n']:6,}  gaze {c['gaze_dwell_ms_median']:6.0f}  cursor {c['cursor_dwell_ms_median']:6.0f}  "
              f"visits {c['n_visits_median']:.0f}  approached {c['approached_share']:.2f}")
    print(f"\nPOSITION-MATCHED split: n={pm['n']:,} peripheral share {pm['peripheral_share']:.3f}  "
          f"(no threshold {pm['no_threshold']})  matched AUC skipped-vs-read {pm['matched_auc_skipped_vs_read_weighted']}")
    print('\nRELEVANCE (organic, query-text cosine) by state; rel_rank 1/n = most relevant in trial')
    for s, c in rel['by_state'].items():
        print(f"  {s:12s} n={c['n']:6,}  cos {c['cos_median']:.3f} {c['cos_ci']}  rel_rank {c['rel_rank_median']:.3f} {c['rel_rank_ci']}")
    for k, v in rel['tests'].items():
        print(f"  {k}: {v}")
    print(f"  (trials joined {n_joined:,}; slots joined {len(rel_rows):,}; unmatched slots {n_unmatched:,})")
    print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
