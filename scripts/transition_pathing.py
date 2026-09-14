"""Examination as sequential pathing; revisit as one transition type.

Reframes the deferred construct to remove the circularity
scripts/reduction_baselines.py exposed. The binary per-result label
`p in visited and p < max_seen` is defined on rank order, so rank position
predicts it by construction (within-trial AUC 0.744 for position alone vs 0.706
for the seven cursor features). Here position becomes STATE rather than a
determinant of the target, which is legitimate by construction.

Unit of analysis: the TRANSITION between consecutive gaze visits to candidates,
not the candidate. Transition k is visit_k -> visit_{k+1}. Target: is the
destination a regression to an already-visited, shallower result — i.e. the
deferred event, expressed as a transition.

Three models, one protocol, so the question "does the cursor inform the next
move" has a non-circular answer:

  S     state only: where they are, how deep they have been, how much is left.
        This is the honest order-model baseline the binary framing could not
        express.
  S+W   state + the canonical WHOLE-TRIAL M4-7 features of the from-candidate.
        What the paper currently has.
  S+L   state + cursor features LOCALIZED to the current visit's window, ending
        at the transition. No lookahead: the window closes when visit k does.

If S+L beats S, the cursor informs the next move and whole-trial aggregation was
discarding it (§4.4's pre5/post5 gap, 0.785 vs 0.938, says the stream is
strongly non-stationary). If S+W ~ S+L ~ S, it does not, and that is worth
knowing for the price of one script.

Metrics: pooled LOSO AUC, per-fold, and WITHIN-TRIAL concordance over
transition pairs from the same trial — pooled AUC on a per-event target silently
rewards between-trial base rate, which is how a within-trial-constant feature
scored 0.599 in the baseline harness.

Cursor stream and geometry mirror the canonical producer: mousemove only,
screenshot space, samples strictly before mousedown(final click) - 500 ms.
Transitions whose window does not close before that cutoff are dropped, and the
count is reported.

Run from attentional-foraging:
  .venv/bin/python scripts/transition_pathing.py
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
from m4_cursor_only_downstream import loso_proba, summarize, sha256, rel  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'transition_pathing'
BUFFER_MS = 500.0
TAIL_MS = 200.0        # window for the "already heading somewhere" velocity term

STATE = ['from_pos', 'max_seen_before', 'n_visited_before', 'depth_remaining',
         'transition_index', 'elapsed_ms', 'n_results', 'from_is_deepest']
LOCAL = ['L_mean_dist', 'L_min_dist', 'L_net_dy', 'L_abs_dy', 'L_path',
         'L_frac_up', 'L_n_samples', 'L_window_ms', 'L_vel_tail']
WHOLE = [f'W_{f}' for f in APPROACH_7]


def cursor_stream(tid, dl):
    """Canonical stream rules, keeping y only (the tracker is 1-D)."""
    try:
        events, _scrolls, clicks = dl.load_mouse_events(tid, space='screenshot')
    except Exception:
        return None
    if not clicks:
        return None
    click = max(clicks, key=lambda c: c[0])
    presses = [t for t, e, x, y in events
               if e == 'mousedown' and math.isfinite(t) and t <= click[0]]
    if not presses:
        return None
    cutoff = max(presses) - BUFFER_MS
    s = [(t, y) for t, e, x, y in events
         if e == 'mousemove' and math.isfinite(t) and math.isfinite(y) and t < cutoff]
    if len(s) < 2:
        return None
    s.sort()
    return np.asarray([p[0] for p in s]), np.asarray([p[1] for p in s]), cutoff


def visits_of(tid, cards, dl):
    """Consecutive-fixation runs on one candidate. An unassigned fixation breaks
    the run, matching gaze_return_counts' `last = None` on a miss."""
    bands = sorted((c['y'], c['y'] + c['height'], c['position']) for c in cards)

    def pos_of(y):
        for top, bot, p in bands:
            if top <= y <= bot:
                return p
        return None

    out, cur = [], None
    for f in sorted(dl.load_fixations(tid), key=lambda f: f['t']):
        p = pos_of(f['y'])
        if p is None:
            if cur:
                out.append(cur); cur = None
            continue
        if cur is None or p != cur['pos']:
            if cur:
                out.append(cur)
            cur = {'pos': p, 't_start': float(f['t']), 't_end': float(f['t'])}
        cur['t_end'] = float(f['t'])
    if cur:
        out.append(cur)
    return out


def local_features(ts, ys, t0, t1, centre):
    m = (ts >= t0) & (ts <= t1)
    if m.sum() < 2:
        return None
    w_t, w_y = ts[m], ys[m]
    d = np.abs(w_y - centre)
    dy = np.diff(w_y)
    dt_ = np.diff(w_t)
    ok = dt_ > 0
    tail = w_t >= (t1 - TAIL_MS)
    if tail.sum() >= 2:
        tt, ty = w_t[tail], w_y[tail]
        span = tt[-1] - tt[0]
        vel = float((ty[-1] - ty[0]) / span * 1000.0) if span > 0 else 0.0
    else:
        vel = 0.0
    return {
        'L_mean_dist': float(d.mean()), 'L_min_dist': float(d.min()),
        'L_net_dy': float(w_y[-1] - w_y[0]), 'L_abs_dy': float(abs(w_y[-1] - w_y[0])),
        'L_path': float(np.abs(dy).sum()),
        'L_frac_up': float(np.mean(dy[ok] < 0)) if ok.any() else 0.5,
        'L_n_samples': float(m.sum()), 'L_window_ms': float(w_t[-1] - w_t[0]),
        'L_vel_tail': vel,
    }


def within_trial_auc(tids, y, proba, mask):
    by = defaultdict(list)
    for i, t in enumerate(tids):
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
    return ((conc + 0.5 * ties) / tot if tot else float('nan')), tot


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
    whole = {(r['trial_id'], r['position']): r for r in stored}
    tids = sorted({r['trial_id'] for r in stored})

    rows, skips = [], defaultdict(int)
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
        except Exception:
            skips['cards'] += 1; continue
        if len(cards) < 2:
            skips['cards'] += 1; continue
        cs = cursor_stream(tid, dl)
        if cs is None:
            skips['stream'] += 1; continue
        ts, ys, cutoff = cs
        centres = {c['position']: c['y'] + c['height'] / 2.0 for c in cards}
        n_res = len(cards)
        visits = visits_of(tid, cards, dl)
        if len(visits) < 2:
            skips['too_few_visits'] += 1; continue
        t_origin = visits[0]['t_start']
        visited, max_seen = set(), -1
        for k, v in enumerate(visits):
            if k + 1 < len(visits):
                nxt = visits[k + 1]['pos']
                # Target uses the state BEFORE this transition resolves.
                is_regression = int(nxt in visited and nxt < max_seen)
                if v['t_end'] < cutoff:
                    lf = local_features(ts, ys, v['t_start'], v['t_end'],
                                        centres[v['pos']])
                    w = whole.get((tid, v['pos']))
                    if lf is not None and w is not None:
                        rec = {
                            'trial_id': tid, 'participant': tid.split('-')[0],
                            'k': k, 'y': is_regression,
                            'from_pos': float(v['pos']),
                            'max_seen_before': float(max_seen),
                            'n_visited_before': float(len(visited)),
                            'depth_remaining': float(n_res - 1 - max(max_seen, 0)),
                            'transition_index': float(k),
                            'elapsed_ms': float(v['t_end'] - t_origin),
                            'n_results': float(n_res),
                            'from_is_deepest': float(v['pos'] == max_seen),
                        }
                        rec.update(lf)
                        rec.update({f'W_{f}': float(w[f]) for f in APPROACH_7})
                        rows.append(rec)
                    else:
                        # Split the causes: a missing whole-trial record is a
                        # join problem; an empty window is the parking regime
                        # (the cursor emits only when it moves, so a short visit
                        # can contain no mousemove at all) and is a finding.
                        if w is None:
                            skips['no_whole_trial_record'] += 1
                        else:
                            skips['no_cursor_samples_in_window'] += 1
                else:
                    skips['after_cursor_cutoff'] += 1
            visited.add(v['pos']); max_seen = max(max_seen, v['pos'])

    print(f'\ntransitions kept {len(rows):,} over '
          f'{len({r["trial_id"] for r in rows}):,} trials; skips {dict(skips)}')
    if not rows:
        raise SystemExit('no transitions')

    pid = np.asarray([r['participant'] for r in rows])
    tid_arr = [r['trial_id'] for r in rows]
    y = np.asarray([r['y'] for r in rows])
    all_rows = np.ones(len(rows), dtype=bool)
    print(f'regression base rate {y.mean():.3f}  participants {len(np.unique(pid))}')

    MODELS = [
        ('S   state only', STATE),
        ('W   whole-trial cursor only', WHOLE),
        ('L   localized cursor only', LOCAL),
        ('S+W state + whole-trial', STATE + WHOLE),
        ('S+L state + localized', STATE + LOCAL),
        ('S+W+L everything', STATE + WHOLE + LOCAL),
    ]
    out = {'schema_version': 1,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'buffer_ms': args.buffer, 'flavor': args.flavor},
           'population': {'transitions': len(rows),
                          'trials': len({r['trial_id'] for r in rows}),
                          'participants': int(len(np.unique(pid))),
                          'regression_base_rate': float(y.mean()),
                          'skips': dict(skips)},
           'models': {}}
    print(f"\n{'='*72}\n{'model':>30s} {'pooled':>9s} {'fold mean':>11s} "
          f"{'in-trial':>10s} {'pairs':>9s}\n{'='*72}")
    for name, feats in MODELS:
        pr, _ = loso_proba(rows, feats, y, all_rows)
        s, _ = summarize(y, pr, pid, all_rows)
        wt, npair = within_trial_auc(tid_arr, y, pr, all_rows)
        s.update({'within_trial_auc': wt, 'n_within_trial_pairs': npair,
                  'features': feats})
        out['models'][name] = s
        print(f"{name:>30s} {s['pooled_auc']:9.3f} "
              f"{s['fold_auc_mean']:6.3f}±{s['fold_auc_sd']:.3f} "
              f"{wt:10.3f} {npair:9,d}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
