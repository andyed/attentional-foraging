"""First-visit dwell carve on the CANONICAL cursor-only typed stream.

Supersedes scripts/visit_decomposition.py + visit_dwell_vs_cursor.py, which were
built on the retired lineage (compute_cursor_approach_features.py caches, whose
identically-named fields are gaze-cursor distances over fixation-selected rows).
Per the 2026-09-06 decision, the paper's LAB numbers come from
m4_cursor_aoi_rerun.py: the real approach-retreat ResultFeatureTracker driven
through Node, mousemove-only samples, press-anchored buffers, document CSS px.
This script reads that producer's feature cache and changes nothing about it.

THE QUESTION
------------
total_dwell_ms -- the paper's M2 dwell baseline -- sums every fixation on a
result AOI, INCLUDING the return fixations that define the `deferred` label it
is compared against. Split it:

    total_dwell_ms = first_visit_dwell_ms + subsequent_dwell_ms

and ask what the baseline retains once the term containing the label is removed.
first_visit_dwell_ms is what a system actually holds at the moment it must
predict whether the reader will come back.

GATES
-----
1. Reproduce the shipped §4.3 deployable M4-7 pooled AUC from
   scripts/output/m4_cursor_only_downstream/summary.json on the same cache,
   the SHIPPED pool (approached & non-click, never-fixated rows counted as
   rejected) and label -- always, whatever pool the carve then uses. If it
   cannot, it stops: no carve number is trustworthy on a stream whose
   published result cannot be reproduced.
2. Label agreement: the fixation->AOI assignment used to draw the visit
   structure must reproduce the shipped label cache on every labeled pool
   row. Zero disagreement is the only acceptable result; otherwise the carve
   is drawn on a different map than the label it carves (the 2026-09-13
   audit found 1,486 disagreements when the script used strict card
   containment while the cache uses compute_regression_labels' bisect rule).

LABELS -- both variants, because both exist in this lineage
-----------------------------------------------------------
  cache      regression_labels_cache_typed.json, the per-fixation rule from
             compute_regression_labels.py. This is what the shipped §4.3
             number uses, so it is the comparison label.
  reentry    m4_cursor_only_downstream.gaze_return_counts' rule, which adds
             `p != last` so consecutive re-fixations inside one visit do not
             count as a return. The refinement already present in the lineage.

POOLS -- every model in a block is scored on that block's rows
-------------------------------------------------------------
  carve[label]['pool']        cursor-only models on the carve pool.
  carve[label]['dwell_rows']  EVERY model, cursor-only ones included, on the
                              rows that have a gaze visit. Dwell features are
                              undefined elsewhere, and quoting a dwell AUC
                              from this block against a cursor AUC from the
                              other one mixes pools (schema_version 1 did).
  Each block carries its own permutation null, computed on its own rows.

Run from attentional-foraging:
  .venv/bin/python scripts/deferred_dwell_carve.py
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from m4_cursor_aoi_rerun import APPROACH_7  # noqa: E402
from m4_cursor_only_downstream import (  # noqa: E402
    loso_proba, summarize, sha256, rel, APPROACH_PX,
)
from compute_regression_labels import regressed_positions  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'deferred_dwell_carve'

# Visit-derived fields attached to every record. A model that reads any of
# them is only defined on rows with a gaze visit and is scored in the
# `dwell_rows` block; rows without a visit carry 0.0 here purely so the
# descriptives can index them, never as a feature value.
VISIT_FIELDS = ('total_dwell_ms', 'first_visit_dwell_ms', 'subsequent_dwell_ms',
                'n_fix_total', 'n_fix_first_visit', 'n_visits')


def label_tops(dl, tid, cards):
    """Band tops in the exact form compute_regression_labels feeds to
    assign_fixation_to_position. Reuses data_loader.typed_aoi_tops rather than
    deriving tops from `cards`, so the label producer's path is the source;
    the cards the caller passes are only checked against it. A mismatch means
    the caller loaded a different flavor than the label cache was built on,
    which is exactly the map divergence this check exists to refuse."""
    tops = dl.typed_aoi_tops(tid)
    from_cards = [int(c['y']) for c in sorted(cards, key=lambda c: c['position'])
                  if c.get('position', -1) >= 0]
    if tops != from_cards:
        raise ValueError(f'{tid}: cards do not match typed_aoi_tops '
                         f'({len(from_cards)} vs {len(tops)} bands); the visit '
                         'decomposition is only defined on the typed map')
    return tops


def visit_decomposition(dl, tid, cards):
    """Per-position gaze visit structure on the typed map.

    Fixations are assigned to positions by the SAME path that produced the
    shipped label cache -- data_loader.typed_aoi_tops + assign_fixation_to_position
    (bisect against band tops: no gaps between cards, everything below the
    last top is the last card, everything above the first top is unassigned).
    Fixations are walked in file order, as compute_regression_labels does;
    every AdSERP fixation file is already time-sorted so this is also
    chronological.

    A VISIT is a maximal run of consecutive assigned fixations on one position;
    an unassigned fixation breaks the run (it is a look above the first card),
    matching gaze_return_counts' `last = None` on a miss.

    Returns {position: {...}} and the two label sets. `cache_lbl` comes from
    compute_regression_labels.regressed_positions itself, so the label the
    carve is scored against is the producer's, not a re-implementation.
    """
    tops = label_tops(dl, tid, cards)
    n_res = len(tops)
    regressed, _ = regressed_positions(tid, 'typed')
    cache_lbl = set(regressed) if regressed is not None else set()

    visits = defaultdict(list)
    reentry_lbl = set()
    visited, max_seen, last = set(), -1, None
    cur_pos, cur = None, None
    for f in dl.load_fixations(tid):
        p = dl.assign_fixation_to_position(f['y'], tops, n_res)
        if p is None or p < 0:
            last = None
            if cur is not None:
                visits[cur_pos].append(cur)
                cur_pos, cur = None, None
            continue
        # Re-entry rule: a long dwell is one return, not many.
        if p != last and p in visited and p < max_seen:
            reentry_lbl.add(p)
        d = float(f.get('d', 200) or 200)
        if p != cur_pos:
            if cur is not None:
                visits[cur_pos].append(cur)
            cur_pos = p
            cur = {'dwell_ms': 0.0, 'n_fix': 0, 't_start': float(f['t']),
                   't_end': float(f['t'])}
        cur['dwell_ms'] += d
        cur['n_fix'] += 1
        cur['t_end'] = float(f['t'])
        visited.add(p); max_seen = max(max_seen, p); last = p
    if cur is not None:
        visits[cur_pos].append(cur)

    out = {}
    for p, vs in visits.items():
        dwells = [v['dwell_ms'] for v in vs]
        out[p] = {
            'n_visits': len(vs),
            'total_dwell_ms': float(sum(dwells)),
            'first_visit_dwell_ms': float(dwells[0]),
            'subsequent_dwell_ms': float(sum(dwells) - dwells[0]),
            'n_fix_total': int(sum(v['n_fix'] for v in vs)),
            'n_fix_first_visit': int(vs[0]['n_fix']),
            'return_gap_ms': (float(vs[1]['t_start'] - vs[0]['t_end'])
                              if len(vs) > 1 else None),
            # Cutoff for carving any time-windowed feature (e.g. the scroll
            # condition's viewport residence) at the moment before the return.
            'first_visit_end_ms': float(vs[0]['t_end']),
        }
    return out, cache_lbl, reentry_lbl


def perm_null(records, features, y, pool, pid, n=100, seed=1):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        ys = y.copy()
        for p in np.unique(pid):
            m = pool & (pid == p)
            if m.sum():
                ys[m] = rng.permutation(ys[m])
        pr, _ = loso_proba(records, features, ys, pool)
        sel = pool & np.isfinite(pr)
        if len(set(ys[sel])) == 2:
            vals.append(roc_auc_score(ys[sel], pr[sel]))
    v = np.array(vals)
    return {'mean': float(v.mean()), 'p95': float(np.percentile(v, 95)),
            'p99': float(np.percentile(v, 99)), 'n_perm': len(v)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--shipped', type=Path,
                    default=ROOT / 'scripts/output/m4_cursor_only_downstream/summary.json')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--perms', type=int, default=100)
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    ap.add_argument('--labeled-only', action='store_true',
                    help='Carve on rows PRESENT in the label cache only, i.e. '
                         'examined non-clicks (gaze_cursor_divergence.py:256 '
                         'pool). The gate still runs on the shipped pool, '
                         'never-fixated rows counted as rejected.')
    ap.add_argument('--skip-gate', action='store_true',
                    help='Rate-thinned caches have no shipped number to reproduce; '
                         'the gate is validated once on the native cache.')
    args = ap.parse_args()

    import data_loader as dl
    from m4_cursor_aoi_rerun import load_flavor_cards, main_cards

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    want = sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}']
    got = hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    if want != got:
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))
    print(f'cache ok: {len(records):,} records, '
          f'{len({r["trial_id"] for r in records}):,} trials, '
          f'anchor={cache["anchor_event"]} sampling={cache["sampling"]}')

    # --- labels -----------------------------------------------------------
    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    assert len(lab_rows) == len(reg)
    cache_label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}
    # A row absent from the label cache was never fixated: the cache's row set
    # (compute_cursor_approach_features.py) emits one row per position that
    # received a fixation, so absence is zero gaze visits, not a missing
    # label. The shipped §4.3 number counts such rows as not-deferred via
    # `.get(key, False)` (m4_cursor_only_downstream.py); the gate below keeps
    # that pool. gaze_cursor_divergence.py:256 requires presence, which is why
    # its pool is 9,269 and the shipped one is 9,932: --labeled-only carves on
    # that examined-non-click pool. The assertion below checks the reading.

    # --- gaze visit decomposition, per trial on the same typed map ---------
    tids = sorted({r['trial_id'] for r in records})
    visits_by_key, reentry_by_key, script_cache_by_key = {}, {}, {}
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  visits {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
        except Exception:
            continue
        if len(cards) < 2:
            continue
        per_pos, cache_lbl, reentry_lbl = visit_decomposition(dl, tid, cards)
        for p, v in per_pos.items():
            visits_by_key[(tid, p)] = v
        for p in reentry_lbl:
            reentry_by_key[(tid, p)] = True
        for p in cache_lbl:
            script_cache_by_key[(tid, p)] = True

    # --- attach, build masks ---------------------------------------------
    for r in records:
        k = (r['trial_id'], r['position'])
        v = visits_by_key.get(k)
        r['_has_visit'] = v is not None
        for f in VISIT_FIELDS:
            r[f] = float(v[f]) if v else 0.0

    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    y_cache = np.asarray([int(cache_label.get((r['trial_id'], r['position']), False))
                          for r in records])
    y_reentry = np.asarray([int(reentry_by_key.get((r['trial_id'], r['position']), False))
                            for r in records])
    y_script = np.asarray([int(script_cache_by_key.get((r['trial_id'], r['position']), False))
                           for r in records])
    labeled = np.asarray([(r['trial_id'], r['position']) in cache_label
                          for r in records])
    has_visit = np.asarray([r['_has_visit'] for r in records])
    # The shipped pool is fixed: approached & non-click, with rows absent from
    # the label cache counted as rejected. The gate ALWAYS runs on it; the flag
    # only selects which pool the carve is drawn on.
    shipped_pool = approached & (clicked == 0)
    pool = shipped_pool & labeled if args.labeled_only else shipped_pool

    # A row absent from the label cache is one whose position received no
    # fixation under the label producer's assignment (that producer emits a
    # row per fixated position). Excluding it is therefore a construct
    # boundary -- the carve is over examined non-clicks -- not a data gap.
    # That reading only holds if the script's own map agrees, so assert it.
    never_fixated = shipped_pool & ~labeled
    n_never_fixated_with_visit = int((never_fixated & has_visit).sum())
    if n_never_fixated_with_visit:
        bad = [(r['trial_id'], r['position'])
               for r, m in zip(records, never_fixated & has_visit) if m][:10]
        raise SystemExit(f'{n_never_fixated_with_visit} pool rows absent from the '
                         f'label cache HAVE a gaze visit on the script map; they '
                         f'are not never-fixated. Examples: {bad}')

    out = {'schema_version': 2,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'aggregate_sidecar': f'scripts/output/{args.summary_dir}/summary.json',
                      'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event'],
                      'sampling': cache['sampling'], 'flavor': args.flavor},
           'population': {'records': len(records),
                          'trials': len(tids), 'participants': int(len(np.unique(pid))),
                          'shipped_pool': int(shipped_pool.sum()),
                          'approached_nonclick_pool': int(pool.sum()),
                          'carve_pool': 'label_complete' if args.labeled_only else 'shipped',
                          'labeled_only': bool(args.labeled_only),
                          'pool_rows_never_fixated': int(never_fixated.sum()),
                          'never_fixated_with_gaze_visit': n_never_fixated_with_visit,
                          'pool_with_gaze_visit': int((pool & has_visit).sum()),
                          'deferred_cache_rule': int((pool & (y_cache == 1)).sum()),
                          'deferred_reentry_rule': int((pool & (y_reentry == 1)).sum())}}

    # --- GATE 1: reproduce the shipped §4.3 deployable number -------------
    if args.skip_gate:
        out['gate'] = {'status': 'skipped (validated on the native cache)'}
        print('\nGATE  skipped')
        target = None
    else:
        shipped = json.loads(args.shipped.read_text())
        target = shipped['section_4_3']['deployable_M4_7']['pooled_auc']
    if target is not None:
        pr, _ = loso_proba(records, APPROACH_7, y_cache, shipped_pool)
        rep, _ = summarize(y_cache, pr, pid, shipped_pool)
        delta = rep['pooled_auc'] - target
        out['gate'] = {'shipped_section_4_3_deployable_M4_7': target,
                       'reproduced': rep['pooled_auc'], 'delta': delta,
                       'n_records': rep['n_records'], 'pool': 'shipped'}
        print(f"\nGATE  shipped §4.3 deployable M4-7 = {target:.4f}   "
              f"reproduced = {rep['pooled_auc']:.4f}   delta = {delta:+.4f}   "
              f"n={rep['n_records']:,}")
        if abs(delta) > 5e-4:
            out['gate']['status'] = 'FAILED'
            json.dump(out, open(args.output.parent / 'summary.FAILED.json', 'w'), indent=1)
            raise SystemExit('Gate failed: cannot reproduce the shipped number; '
                             'no carve result reported.')
        out['gate']['status'] = 'ok'

    # --- GATE 2: the script's per-fixation rule must reproduce the cache --
    # Checked on the shipped pool, the superset of both carve pools. Any
    # disagreement means the visit structure is drawn on a different map than
    # the label it is scored against, and no carve number is reportable.
    lab = shipped_pool & labeled
    disagree = lab & (y_script != y_cache)
    out['label_agreement'] = {
        'n_labeled': int(lab.sum()),
        'n_agree': int((lab & (y_script == y_cache)).sum()),
        'n_disagree': int(disagree.sum()),
        'n_labeled_without_visit': int((lab & ~has_visit).sum()),
        'n_labeled_deferred_without_visit': int((lab & (y_cache == 1) & ~has_visit).sum()),
    }
    la = out['label_agreement']
    print(f"AGREE labeled {la['n_labeled']:,}  agree {la['n_agree']:,}  "
          f"disagree {la['n_disagree']:,}  labeled-without-visit "
          f"{la['n_labeled_without_visit']:,} (deferred {la['n_labeled_deferred_without_visit']:,})")
    if la['n_disagree']:
        ex = [(r['trial_id'], r['position'], 'cache', bool(y_cache[i]), 'script', bool(y_script[i]))
              for i, (r, m) in enumerate(zip(records, disagree)) if m][:10]
        out['label_agreement']['status'] = 'FAILED'
        out['label_agreement']['examples'] = ex
        json.dump(out, open(args.output.parent / 'summary.FAILED.json', 'w'), indent=1)
        raise SystemExit(f"Label agreement failed: {la['n_disagree']} labeled pool rows "
                         f"disagree with the shipped cache; examples {ex}")
    out['label_agreement']['status'] = 'ok'

    # --- the carve --------------------------------------------------------
    models = {
        'dwell_total':            ['total_dwell_ms'],
        'dwell_first_visit':      ['first_visit_dwell_ms'],
        'n_fix_first_visit':      ['n_fix_first_visit'],
        'mean_dist':              ['mean_dist'],
        'M4_7_cursor':            APPROACH_7,
        'M4_7_plus_first_visit':  APPROACH_7 + ['first_visit_dwell_ms'],
        'M4_7_plus_total_dwell':  APPROACH_7 + ['total_dwell_ms'],
    }
    # A model is cursor-only iff none of its features is visit-derived.
    cursor_only = {n for n, feats in models.items()
                   if not set(feats) & set(VISIT_FIELDS)}
    dwell_pool = pool & has_visit

    def score_block(y, mask, names):
        block = {}
        for name in names:
            p, _ = loso_proba(records, models[name], y, mask)
            s, _ = summarize(y, p, pid, mask)
            block[name] = s
        # Null on the block's own rows, so it is comparable to every AUC beside it.
        block['_null_M4_7'] = perm_null(records, APPROACH_7, y, mask, pid, n=args.perms)
        return block

    out['carve'] = {}
    for label_name, y in (('cache', y_cache), ('reentry', y_reentry)):
        out['carve'][label_name] = {
            'pool': score_block(y, pool, [n for n in models if n in cursor_only]),
            'dwell_rows': score_block(y, dwell_pool, list(models)),
        }

    # --- descriptives -----------------------------------------------------
    desc = {}
    for label_name, y in (('cache', y_cache), ('reentry', y_reentry)):
        d = dwell_pool & (y == 1); e = dwell_pool & (y == 0)
        desc[label_name] = {
            'n_deferred': int(d.sum()), 'n_rejected': int(e.sum()),
            'medians': {},
        }
        for f in ('total_dwell_ms', 'first_visit_dwell_ms', 'subsequent_dwell_ms',
                  'n_visits', 'n_fix_total', 'n_fix_first_visit'):
            v = np.asarray([r[f] for r in records], dtype=float)
            desc[label_name]['medians'][f] = {
                'deferred': float(np.median(v[d])), 'rejected': float(np.median(v[e]))}
        sub = np.asarray([r['subsequent_dwell_ms'] / max(r['total_dwell_ms'], 1.0)
                          for r in records])
        desc[label_name]['subsequent_share_deferred_median'] = float(np.median(sub[d]))
    # Distributions for the review page: proportion-normalised histograms so
    # the two classes are comparable despite different n, plus quantiles.
    def hist(v, lo, hi, nbins=32):
        edges = np.linspace(lo, hi, nbins + 1)
        c, _ = np.histogram(v[(v >= lo) & (v <= hi)], bins=edges)
        return {'edges': [round(float(e), 1) for e in edges],
                'counts': [int(x) for x in c], 'n': int(((v >= lo) & (v <= hi)).sum())}

    dists = {}
    for label_name, y in (('cache', y_cache), ('reentry', y_reentry)):
        d = dwell_pool & (y == 1); e = dwell_pool & (y == 0)
        blk = {}
        for f, lo, hi in (('first_visit_dwell_ms', 0, 3000),
                          ('total_dwell_ms', 0, 8000)):
            v = np.asarray([r[f] for r in records], dtype=float)
            blk[f] = {'deferred': hist(v[d], lo, hi), 'rejected': hist(v[e], lo, hi),
                      'q_deferred': {f'p{q}': round(float(np.percentile(v[d], q)), 1)
                                     for q in (10, 25, 50, 75, 90)},
                      'q_rejected': {f'p{q}': round(float(np.percentile(v[e], q)), 1)
                                     for q in (10, 25, 50, 75, 90)}}
        nv = np.asarray([r['n_visits'] for r in records], dtype=float)
        blk['n_visits'] = {'deferred': {str(k): int((nv[d] == k).sum()) for k in range(1, 9)},
                           'rejected': {str(k): int((nv[e] == k).sum()) for k in range(1, 9)}}
        gaps = [visits_by_key[(r['trial_id'], r['position'])]['return_gap_ms']
                for r in records
                if (r['trial_id'], r['position']) in visits_by_key
                and visits_by_key[(r['trial_id'], r['position'])]['return_gap_ms'] is not None]
        g = np.asarray(gaps, dtype=float)
        blk['return_gap_q'] = {f'p{q}': round(float(np.percentile(g, q)), 1)
                               for q in (10, 25, 50, 75, 90)}
        dists[label_name] = blk
    out['distributions'] = dists
    out['descriptives'] = desc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)

    print(f"\ncarve pool = {out['population']['carve_pool']}: "
          f"{out['population']['approached_nonclick_pool']:,} rows "
          f"(with gaze visit {out['population']['pool_with_gaze_visit']:,}; "
          f"shipped pool {out['population']['shipped_pool']:,}, "
          f"never-fixated {out['population']['pool_rows_never_fixated']:,})")
    for label_name in ('cache', 'reentry'):
        dd = desc[label_name]
        print(f"\n=== label rule: {label_name}  "
              f"(dwell rows: deferred {dd['n_deferred']:,} / rejected {dd['n_rejected']:,}) ===")
        print(f"  median first-visit dwell  deferred "
              f"{dd['medians']['first_visit_dwell_ms']['deferred']:.0f} ms  vs  rejected "
              f"{dd['medians']['first_visit_dwell_ms']['rejected']:.0f} ms")
        print(f"  median total dwell        deferred "
              f"{dd['medians']['total_dwell_ms']['deferred']:.0f} ms  vs  rejected "
              f"{dd['medians']['total_dwell_ms']['rejected']:.0f} ms")
        print(f"  subsequent share of deferred dwell: "
              f"{dd['subsequent_share_deferred_median']:.2f}")
        for block_name in ('pool', 'dwell_rows'):
            b = out['carve'][label_name][block_name]
            print(f"  -- block {block_name} --")
            for name in models:
                if name not in b:
                    continue
                print(f"    {name:24s} AUC {b[name]['pooled_auc']:.3f}  "
                      f"fold {b[name]['fold_auc_mean']:.3f} +- {b[name]['fold_auc_sd']:.3f}  "
                      f"n={b[name]['n_records']:,}")
            n = b['_null_M4_7']
            print(f"    {'perm null (M4-7)':24s} mean {n['mean']:.3f}  "
                  f"p95 {n['p95']:.3f}  p99 {n['p99']:.3f}")
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
