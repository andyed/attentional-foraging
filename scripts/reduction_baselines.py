"""Head-to-head baselines as projections of one construction.

The unification claim has two halves. This producer measures the first:
**the reductions are faithful** — each prior measurement, expressed as the
construction with its slots fixed (which pointer, which grain, which derivative
order), reproduces its source's reported behaviour under ONE protocol, on the
same rows, against the same targets.

Baselines, all computed from the SAME stream the canonical M4 features come
from (mousemove only, press-anchored, samples strictly before
mousedown(final click) − 500 ms, typed main-axis AOIs in screenshot space):

  B1  total_mouse_length          Brückner primitive. Candidate-free marginal,
                                  order 1. Constant within a trial.
  B2  dwell_in_proximity_ms       Huang 2011 hover-on-unclicked. Order 0,
                                  candidate grain, 100 px zone.
  B3  Liu 2014 per-result summary dwell-in-box + hover entries + presence.
                                  Order 0, candidate grain, strict box.
  B4  page-grain session battery  Arapakis-style global cursor statistics
                                  broadcast to every candidate: path length,
                                  n samples, duration, idle fraction, scroll
                                  count. Constant within a trial BY
                                  CONSTRUCTION — this is the structural point.
  B5  position                    Rank prior (M1).
  FULL M4-7                       Orders 0 + 1-magnitude + 1-sign, candidate
                                  grain.

Targets: `was_clicked` (all rows) and the deferred/evaluated-rejected split on
the label-complete approached non-click pool (rows PRESENT in the label cache;
see gaze_cursor_divergence.py:256 and the `.get(key, False)` defect it avoids).

Why MRR matters more than AUC here: a page-grain representation assigns the
SAME score to every candidate in a trial, so it cannot order candidates inside
one no matter how good its features are. The structural demonstration is the
within-trial AUC of exactly 0.500 (every same-trial pair is a tie). MRR@10 and
NDCG@1 are then reported under FAIR tie-breaking (expected value over uniform
random orderings of tied candidates), so they show what a page-grain model
actually achieves rather than inheriting the rank prior through row order —
see within_trial_ranking. `n_trials_with_ties` makes the tie mass visible.

Run from attentional-foraging:
  .venv/bin/python scripts/reduction_baselines.py
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
import math
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

from m4_cursor_aoi_rerun import APPROACH_7, main_cards, load_flavor_cards  # noqa: E402
from m4_cursor_only_downstream import (  # noqa: E402
    loso_proba, summarize, sha256, rel, APPROACH_PX,
)

OUT_DIR = ROOT / 'scripts' / 'output' / 'reduction_baselines'
BUFFER_MS = 500.0
PROX = 100.0
IDLE_GAP_MS = 500.0     # no mousemove for this long = idle interval

B1 = ['total_mouse_length']
B2 = ['dwell_in_proximity_ms']
B3 = ['dwell_in_box_ms', 'n_box_entries', 'ever_in_box']
B4 = ['g_path_length', 'g_n_samples', 'g_duration_ms', 'g_idle_fraction', 'g_n_scroll']
B5 = ['position']

MODELS = [
    ('B1 mouse-length (Brückner)', B1),
    ('B2 hover/proximity dwell (Huang 2011)', B2),
    ('B3 per-result summary (Liu 2014)', B3),
    ('B4 page-grain battery (broadcast)', B4),
    ('B5 rank position (M1)', B5),
    ('B3 + B4 (best non-episode)', B3 + B4),
    ('FULL M4-7 episode geometry', APPROACH_7),
    ('FULL + B3 + B4', APPROACH_7 + B3 + B4),
    # The deferred label is defined on rank order (`p in visited and p < max_seen`),
    # so a shallow result can satisfy it and the deepest cannot. Position therefore
    # carries a prior on the label BY CONSTRUCTION. On the deferred target,
    # position is the baseline to beat, not a feature to absorb — the mirror image
    # of the M3/M4 absorption result on the click target.
    ('B5 + FULL (position + episode)', B5 + APPROACH_7),
    ('B5 + FULL + B3 + B4 (everything)', B5 + APPROACH_7 + B3 + B4),
]


def trial_stream(tid, cards, dl):
    """Mirror m4_cursor_aoi_rerun.prepare_trial's stream rules exactly, but keep
    x as well as y so 2-D box containment is computable."""
    try:
        events, scrolls, clicks = dl.load_mouse_events(tid, space='screenshot')
    except Exception:
        return None
    if not clicks:
        return None
    click = max(clicks, key=lambda c: c[0])
    if not all(math.isfinite(v) for v in click):
        return None
    presses = [t for t, e, x, y in events
               if e == 'mousedown' and math.isfinite(t) and t <= click[0]]
    if not presses:
        return None
    cutoff = max(presses) - BUFFER_MS
    samples = [(t, x, y) for t, e, x, y in events
               if e == 'mousemove' and all(math.isfinite(v) for v in (t, x, y))
               and t < cutoff]
    if len(samples) < 2:
        return None
    n_scroll = sum(1 for t, e, _x, _y in events if e == 'scroll' and t < cutoff)
    return samples, n_scroll


def globals_for(samples, n_scroll):
    ts = np.asarray([s[0] for s in samples], dtype=float)
    xs = np.asarray([s[1] for s in samples], dtype=float)
    ys = np.asarray([s[2] for s in samples], dtype=float)
    path = float(np.hypot(np.diff(xs), np.diff(ys)).sum())
    dur = float(ts[-1] - ts[0])
    dts = np.diff(ts)
    idle = float(dts[dts >= IDLE_GAP_MS].sum()) / dur if dur > 0 else 0.0
    return {'g_path_length': path, 'g_n_samples': float(len(ts)),
            'g_duration_ms': dur, 'g_idle_fraction': idle,
            'g_n_scroll': float(n_scroll), 'total_mouse_length': path}


def per_candidate(samples, cards):
    """B3: strict in-box dwell, entries, presence — Liu's per-result summary."""
    ts = np.asarray([s[0] for s in samples], dtype=float)
    xs = np.asarray([s[1] for s in samples], dtype=float)
    ys = np.asarray([s[2] for s in samples], dtype=float)
    dts = np.diff(ts)
    out = {}
    for c in cards:
        p = c['position']
        inside = ((xs >= c['x']) & (xs <= c['x'] + c['width']) &
                  (ys >= c['y']) & (ys <= c['y'] + c['height']))
        ok = (dts > 0) & (dts < 2000)
        dwell = float(dts[ok & inside[1:]].sum())
        entries = int(np.sum((~inside[:-1]) & inside[1:])) + int(inside[0])
        out[p] = {'dwell_in_box_ms': dwell, 'n_box_entries': float(entries),
                  'ever_in_box': float(bool(inside.any()))}
    return out


def within_trial_auc(trial_ids, y, proba, mask):
    """Concordance over same-trial pairs with differing labels.

    Pooled AUC rewards a feature that merely predicts which TRIALS have a high
    deferred rate. A page-grain feature is constant within a trial, so it cannot
    order candidates inside one — yet it can still score well pooled, purely on
    between-trial base rate. This metric removes that channel entirely: only
    pairs drawn from the same trial count, so a within-trial-constant feature
    scores exactly 0.5 by construction.
    """
    by = defaultdict(list)
    for i, t in enumerate(trial_ids):
        if mask[i] and np.isfinite(proba[i]):
            by[t].append(i)
    conc = ties = tot = 0
    for idx in by.values():
        pos = [i for i in idx if y[i] == 1]
        neg = [i for i in idx if y[i] == 0]
        for a in pos:
            for b in neg:
                tot += 1
                if proba[a] > proba[b]:
                    conc += 1
                elif proba[a] == proba[b]:
                    ties += 1
    if tot == 0:
        return float('nan'), 0
    return (conc + 0.5 * ties) / tot, tot


def within_trial_ranking(trial_ids, y, proba, tie_atol=1e-12):
    """Tie-aware MRR@10 / NDCG@1 over single-positive trials.

    Rows arrive sorted by (trial_id, position), so a sort keyed on
    (-score, row index) breaks ties BY RANK POSITION. A model that scores every
    candidate in a trial identically (B1, B4: constant within trial by
    construction) would then be handed the rank prior for free and report the
    same MRR as B5 to full precision. That number is an artifact of the sort
    key, not a measurement.

    Instead, each trial contributes its EXPECTED value under uniform random
    tie-breaking, computed analytically: with the positive strictly beaten by
    m candidates and tied with k candidates (itself included), its rank is
    uniform over m+1..m+k, so
        E[RR@10]  = mean(1/r for r in m+1..m+k if r <= 10, else 0)
        E[top-1]  = 1/k if m == 0 else 0
    Deterministic (no RNG), and a fully tied trial of n candidates yields the
    same value as averaging over every permutation.

    Returns (mrr_at_10, ndcg_at_1, n_ranked_trials, n_trials_with_ties), where
    the last counts trials whose positive is tied with >= 1 other candidate.
    """
    by = defaultdict(list)
    for i, t in enumerate(trial_ids):
        by[t].append(i)
    rr, top1, n_tied = [], [], 0
    for idx in by.values():
        if sum(y[i] for i in idx) != 1:
            continue
        scores = np.asarray([proba[i] for i in idx], dtype=float)
        if not np.all(np.isfinite(scores)):
            # A NaN score (LOSO fold with no fit) cannot be ranked; the old
            # sort silently produced an arbitrary order here.
            continue
        s_pos = scores[[y[i] for i in idx].index(1)]
        beaten = int(np.sum(scores > s_pos + tie_atol))
        tied = int(np.sum(np.abs(scores - s_pos) <= tie_atol))  # includes itself
        ranks = np.arange(beaten + 1, beaten + tied + 1)
        rr.append(float(np.mean(np.where(ranks <= 10, 1.0 / ranks, 0.0))))
        top1.append(1.0 / tied if beaten == 0 else 0.0)
        n_tied += int(tied > 1)
    return (float(np.mean(rr)) if rr else float('nan'),
            float(np.mean(top1)) if top1 else float('nan'), len(rr), n_tied)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    args = ap.parse_args()

    import data_loader as dl

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match its aggregate sidecar')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))
    keyed = {(r['trial_id'], r['position']): r for r in records}
    print(f'canonical rows {len(records):,} over '
          f'{len({r["trial_id"] for r in records}):,} trials')

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({r['trial_id'] for r in records})
    attached, skipped = 0, defaultdict(int)
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
        except Exception:
            skipped['cards'] += 1; continue
        if len(cards) < 2:
            skipped['cards'] += 1; continue
        st = trial_stream(tid, cards, dl)
        if st is None:
            skipped['stream'] += 1; continue
        samples, n_scroll = st
        g = globals_for(samples, n_scroll)
        pc = per_candidate(samples, cards)
        for c in cards:
            r = keyed.get((tid, c['position']))
            if r is None:
                continue
            r.update(g)
            r.update(pc.get(c['position'], dict.fromkeys(B3, 0.0)))
            r['position'] = float(c['position'])
            r['_ok'] = True
            attached += 1
    print(f'  attached {attached:,} rows; skipped {dict(skipped)}')

    rows = [r for r in records if r.get('_ok')]
    pid = np.asarray([r['trial_id'].split('-')[0] for r in rows])
    tid_arr = [r['trial_id'] for r in rows]
    y_click = np.asarray([int(r['was_clicked']) for r in rows])
    labeled = np.asarray([(r['trial_id'], r['position_int'] if 'position_int' in r
                           else int(r['position'])) in label for r in rows])
    y_def = np.asarray([int(label.get((r['trial_id'], int(r['position'])), False))
                        for r in rows])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in rows])
    pool_def = approached & (y_click == 0) & labeled
    all_rows = np.ones(len(rows), dtype=bool)
    print(f'\nclick rows {len(rows):,} ({int(y_click.sum()):,} clicks) | '
          f'deferred pool {int(pool_def.sum()):,} '
          f'(rate {y_def[pool_def].mean():.3f})')

    # Structural check: is each page-grain feature actually constant in a trial?
    byt = defaultdict(list)
    for i, t in enumerate(tid_arr):
        byt[t].append(i)
    const = {}
    for f in B4:
        v = np.asarray([r[f] for r in rows], dtype=float)
        const[f] = bool(all(len(set(np.round(v[idx], 9))) == 1 for idx in byt.values()))
    print(f'  page-grain features constant within trial: {const}')

    out = {'schema_version': 2,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'buffer_ms': args.buffer, 'flavor': args.flavor,
                      'anchor_event': cache['anchor_event']},
           'population': {'rows': len(rows), 'clicks': int(y_click.sum()),
                          'deferred_pool': int(pool_def.sum()),
                          'participants': int(len(np.unique(pid)))},
           'page_grain_constant_within_trial': const,
           'click': {}, 'deferred': {}}

    print(f"\n{'='*104}\n{'model':>38s} {'CLICK auc':>10s} {'MRR@10':>8s} "
          f"{'NDCG@1':>8s} {'tied':>7s} {'DEF pooled':>13s} {'DEF in-trial':>13s}\n{'='*104}")
    for name, feats in MODELS:
        pc_, _ = loso_proba(rows, feats, y_click, all_rows)
        sc, _ = summarize(y_click, pc_, pid, all_rows)
        mrr, nd, nrank, ntied = within_trial_ranking(tid_arr, y_click, pc_)
        sc.update({'mrr_at_10': mrr, 'ndcg_at_1': nd, 'n_ranked_trials': nrank,
                   'n_trials_with_ties': ntied})
        out['click'][name] = sc
        pd_, _ = loso_proba(rows, feats, y_def, pool_def)
        sd, _ = summarize(y_def, pd_, pid, pool_def)
        wt, npair = within_trial_auc(tid_arr, y_def, pd_, pool_def)
        sd.update({'within_trial_auc': wt, 'n_within_trial_pairs': npair})
        out['deferred'][name] = sd
        print(f"{name:>38s} {sc['pooled_auc']:10.3f} {mrr:8.3f} {nd:8.3f} "
              f"{ntied:7d} {sd['pooled_auc']:13.3f} {wt:13.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
