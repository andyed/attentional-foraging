#!/usr/bin/env python3
"""Bold query-term density by engagement state -- the one crowding-robust
cue the periphery could read.

Google marks query terms in snippets with <em>. Bold weight is a
low-spatial-frequency feature that survives crowding at the eccentricities
where letter identity does not, so if the periphery evaluates anything on a
skipped result it is the density of bold in it. Two opposite predictions:

  attractor    bold draws fixation: fixated results carry MORE bold than
               on-screen unfixated ones, and among skips the peripherally
               sampled carry more than the unsampled
  rejection    the periphery reads low bold density as poor match and
               moves on: peripherally sampled skips carry LESS bold than
               unsampled skips (which were never assessed)

Phase 1  parse every SERP snapshot in AdSERP/data/serps with the SAME h3
         enumeration and container walk as embed_serp_results.py, so the
         index equals content-features' `source_h3_pos`. Per result: number
         of <em>, em characters, snippet characters, bold share, em in
         title.
Phase 2  join typed organic slots -> organic-flavour card (page geometry)
         -> content-features organic pos -> source_h3_pos -> phase-1 row,
         attach the census state, and test by state under the primary
         census (intake within 8 deg) and the soft-falloff census.

Regime [LAB, AdSERP, typed]. Outputs scripts/output/bold_term_density/
  by_trial.json   phase-1 rows per trial (h3 order)
  summary.json    tests by state
Run: .venv/bin/python scripts/bold_term_density.py [--skip-parse]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from bs4 import BeautifulSoup
from scipy.stats import mannwhitneyu, spearmanr

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
SERPS = ROOT / 'AdSERP/data/serps'
CONTENT = ROOT / 'AdSERP/data/content-features-by-position-organic.json'
OUT = ROOT / 'scripts/output/bold_term_density'
CENSUS = {'within_8deg': ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv',
          'soft_falloff_24': ROOT / 'scripts/output/engagement_state_census/kernel_boundary_cm_24/states.csv'}
STATES = ('unsampled', 'peripheral', 'rejected', 'deferred', 'clicked')


def parse_serp(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
    rso = soup.find(id='rso') or soup
    rows = []
    for i, h3 in enumerate(rso.find_all('h3')):
        title = h3.get_text(strip=True)
        container = h3.parent
        for _ in range(5):
            if container and container.parent:
                container = container.parent
                if container.get('class') and any('g' in c for c in container.get('class', [])):
                    break
        all_text = container.get_text(' ', strip=True) if container else ''
        snippet = all_text.replace(title, '', 1).strip()
        ems = container.find_all('em') if container else []
        em_chars = sum(len(e.get_text(strip=True)) for e in ems)
        rows.append({'h3_pos': i, 'title_chars': len(title), 'snippet_chars': len(snippet),
                     'n_em': len(ems), 'em_chars': em_chars,
                     'bold_share': (em_chars / len(snippet)) if snippet else 0.0,
                     'em_in_title': int(bool(h3.find_all('em')))})
    return rows


def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 20 or len(b) < 20:
        return None
    u = mannwhitneyu(a, b, alternative='two-sided')
    return {'auc': float(u.statistic / (len(a) * len(b))), 'p': float(u.pvalue), 'n_a': int(len(a)), 'n_b': int(len(b))}


def cluster_ci(vals, pids, n=3000, seed=20260914):
    rng = np.random.default_rng(seed)
    vals, pids = np.asarray(vals, float), np.asarray(pids)
    groups = [vals[pids == p] for p in np.unique(pids)]
    meds = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        meds.append(np.median(np.concatenate([groups[k] for k in pick])))
    return [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-parse', action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- phase 1 ------------------------------------------------------------
    if args.skip_parse and (OUT / 'by_trial.json').exists():
        by_trial = json.loads((OUT / 'by_trial.json').read_text())
    else:
        by_trial = {}
        files = sorted(SERPS.glob('*.html'))
        for i, f in enumerate(files, 1):
            if i % 400 == 0:
                print(f'  parsed {i}/{len(files)}', flush=True)
            try:
                by_trial[f.stem] = parse_serp(f)
            except Exception as e:  # noqa: BLE001
                by_trial[f.stem] = {'error': str(e)}
        json.dump(by_trial, open(OUT / 'by_trial.json', 'w'))
    corpus = [r for v in by_trial.values() if isinstance(v, list) for r in v]
    print(f"phase 1: {len(by_trial):,} snapshots, {len(corpus):,} results; "
          f"median bold share {np.median([r['bold_share'] for r in corpus]):.3f}, "
          f"median n_em {np.median([r['n_em'] for r in corpus]):.0f}, "
          f"em in title {np.mean([r['em_in_title'] for r in corpus]):.3f}")

    # ---- phase 2 ------------------------------------------------------------
    import csv
    import data_loader as dl
    from m4_cursor_aoi_rerun import load_flavor_cards
    content = json.loads(CONTENT.read_text())
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]', 'markup': 'query terms = <em> inside the result container (#rso h3 walk, as embed_serp_results.py)',
           'corpus': {'snapshots': len(by_trial), 'results': len(corpus),
                      'bold_share_median': float(np.median([r['bold_share'] for r in corpus])),
                      'n_em_median': float(np.median([r['n_em'] for r in corpus])),
                      'em_in_title_share': float(np.mean([r['em_in_title'] for r in corpus]))},
           'by_census': {}}
    geo_cache, feats_cache = {}, {}
    for name, path in CENSUS.items():
        rows = list(csv.DictReader(open(path)))
        by = defaultdict(dict)
        for r in rows:
            by[r['trial_id']][int(r['position'])] = r
        joined = []
        n_unmatched = 0
        for tid, d in by.items():
            org = [d[p] for p in sorted(d) if d[p]['etype'] == 'organic']
            if not org or tid not in by_trial or not isinstance(by_trial[tid], list):
                continue
            if tid not in geo_cache:
                try:
                    tcards = {c['position']: c for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0}
                    ocards = load_flavor_cards(dl, tid, 'organic')
                except Exception:
                    geo_cache[tid] = None
                    continue
                geo_cache[tid] = (tcards, {(int(c['y']), int(c['height'])): int(c['position'])
                                           for c in ocards if c.get('position', -1) >= 0})
                feats_cache[tid] = {int(f['pos']): int(f['source_h3_pos'])
                                    for f in content.get(tid, {}).get('positions', [])}
            if geo_cache[tid] is None:
                continue
            tcards, geo = geo_cache[tid]
            h3_by_org = feats_cache[tid]
            bt = by_trial[tid]
            for r in org:
                tc = tcards.get(int(r['position']))
                k = geo.get((int(tc['y']), int(tc['height']))) if tc else None
                h = h3_by_org.get(k) if k is not None else None
                if h is None or h >= len(bt):
                    n_unmatched += 1
                    continue
                b = bt[h]
                joined.append({'pid': r['pid'], 'state': r['state'], 'position': int(r['position']),
                               'fixated': r['fixated'] == '1', **b})
        res = {'n_slots': len(joined), 'n_unmatched': n_unmatched, 'by_state': {}, 'tests': {}}
        for s in STATES:
            sel = [x for x in joined if x['state'] == s]
            if len(sel) < 30:
                continue
            pid = [x['pid'] for x in sel]
            res['by_state'][s] = {'n': len(sel),
                                  'bold_share_median': float(np.median([x['bold_share'] for x in sel])),
                                  'bold_share_ci': cluster_ci([x['bold_share'] for x in sel], pid),
                                  'bold_share_mean': float(np.mean([x['bold_share'] for x in sel])),
                                  'n_em_median': float(np.median([x['n_em'] for x in sel])),
                                  'em_in_title_share': float(np.mean([x['em_in_title'] for x in sel])),
                                  'zero_bold_share': float(np.mean([x['n_em'] == 0 for x in sel]))}
        V = lambda s, k: [x[k] for x in joined if x['state'] == s]  # noqa: E731
        for k in ('bold_share', 'n_em'):
            res['tests'][f'peripheral_vs_unsampled_{k}'] = auc(V('peripheral', k), V('unsampled', k))
            res['tests'][f'peripheral_vs_rejected_{k}'] = auc(V('peripheral', k), V('rejected', k))
            res['tests'][f'fixated_vs_onscreen_unfixated_{k}'] = auc(
                [x[k] for x in joined if x['fixated']],
                [x[k] for x in joined if x['state'] in ('peripheral', 'unsampled')])
            res['tests'][f'rejected_vs_deferred_{k}'] = auc(V('rejected', k), V('deferred', k))
            res['tests'][f'deferred_vs_clicked_{k}'] = auc(V('deferred', k), V('clicked', k))
        # position-stratified peripheral vs unsampled on bold share
        strat = []
        for p in range(10):
            a = [x['bold_share'] for x in joined if x['state'] == 'peripheral' and x['position'] == p]
            b = [x['bold_share'] for x in joined if x['state'] == 'unsampled' and x['position'] == p]
            t = auc(a, b)
            if t:
                strat.append({'position': p, **t})
        res['tests']['peripheral_vs_unsampled_bold_share_by_position'] = strat
        # does bold share track position (the layout confound)?
        rho = spearmanr([x['position'] for x in joined], [x['bold_share'] for x in joined])
        res['tests']['bold_share_vs_position_spearman'] = {'rho': float(rho.statistic), 'p': float(rho.pvalue)}
        out['by_census'][name] = res

        print(f"\n[{name}] slots joined {len(joined):,} (unmatched {n_unmatched:,})")
        print(f"  {'state':11s} {'n':>6s} {'bold share med':>14s} {'mean':>6s} {'n_em':>5s} {'zero':>6s} {'em title':>8s}")
        for s, c in res['by_state'].items():
            print(f"  {s:11s} {c['n']:6,} {c['bold_share_median']:14.3f} {c['bold_share_mean']:6.3f} {c['n_em_median']:5.0f} {c['zero_bold_share']:6.2f} {c['em_in_title_share']:8.2f}")
        for k, v in res['tests'].items():
            if isinstance(v, dict) and 'auc' in v:
                print(f"  {k:44s} AUC {v['auc']:.3f}  p={v['p']:.2g}  ({v['n_a']} vs {v['n_b']})")
        print(f"  by position (peripheral vs unsampled, bold share): {[(t['position'], round(t['auc'], 2)) for t in strat]}")
        print(f"  bold share vs position: rho {res['tests']['bold_share_vs_position_spearman']['rho']:+.3f}")

    json.dump(out, open(OUT / 'summary.json', 'w'), indent=1)
    print(f'\nwrote {OUT}')


if __name__ == '__main__':
    main()
