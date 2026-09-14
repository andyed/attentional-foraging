"""Sampling-rate curve for the DEFERRED task on the canonical cursor-only stream.

§6 states "sampling rate is not a deployment constraint" and supports it with a
curve measured on the CLICK task, then applies it to deferred-class inference.
This runs the deferred task down the same curve, with click beside it on the
same rows, using caches produced by m4_cursor_aoi_rerun.py -- the real
ResultFeatureTracker, mousemove-only samples, press-anchored buf500.

Note on an earlier critique of mine that does NOT apply here: the retired
compute_cursor_approach_features path fed six positional event types into the
features while downsample_mouse_events thinned only `mousemove`, so its thinned
conditions were not true rates. The canonical producer takes `mousemove` alone
(m4_cursor_aoi_rerun.prepare_trial), so `--downsample-hz` is an honest rate.

Rows are intersected across every rate so the curve is a within-row comparison.

Run from attentional-foraging:
  .venv/bin/python scripts/rate_curve_canonical.py
"""
from __future__ import annotations

import argparse
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
from m4_cursor_only_downstream import loso_proba, summarize, sha256, rel, APPROACH_PX  # noqa: E402

DATA = ROOT / 'AdSERP/data'
CONDS = [
    ('native', DATA / 'cursor-only-typed-features-mousedown.json', 'm4_cursor_aoi_mousedown'),
    ('30', DATA / 'cursor-only-typed-features-mousedown-30hz.json', 'm4_cursor_aoi_md_rate_30hz'),
    ('15', DATA / 'cursor-only-typed-features-mousedown-15hz.json', 'm4_cursor_aoi_md_rate_15hz'),
    ('5',  DATA / 'cursor-only-typed-features-mousedown-5hz.json',  'm4_cursor_aoi_md_rate_5hz'),
    ('2',  DATA / 'cursor-only-typed-features-mousedown-2hz.json',  'm4_cursor_aoi_md_rate_2hz'),
    ('1',  DATA / 'cursor-only-typed-features-mousedown-1hz.json',  'm4_cursor_aoi_md_rate_1hz'),
]


def load_cache(path, summary_dir, buffer=500):
    cache = json.loads(Path(path).read_text())
    stored = cache['conditions'][f'buf{buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / summary_dir / 'summary.json').read_text())
    want = sidecar['provenance']['feature_records_sha256'][f'buf{buffer}']
    got = hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    if want != got:
        raise ValueError(f'{path.name}: cache does not match its sidecar')
    return {(r['trial_id'], r['position']): r for r in stored}, cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--perms', type=int, default=100)
    ap.add_argument('--output', type=Path,
                    default=ROOT / 'scripts/output/deferred_dwell_carve/rate_curve.json')
    args = ap.parse_args()

    by_cond, meta = {}, {}
    for name, path, sdir in CONDS:
        if not path.exists():
            print(f'  missing cache for {name}, skipped')
            continue
        by_cond[name], c = load_cache(path, sdir)
        # The producer stamps `sampling: 'native'` on every thinned cache too
        # (thinning is a separate `downsample_hz` field), so copying only
        # `sampling` labels every condition "native". Carry the rate through,
        # and refuse a cache whose stamp disagrees with the CONDS name so a
        # mislabeled file cannot be plotted under the wrong rate.
        hz = float(c.get('downsample_hz') or 0)
        want_hz = 0.0 if name == 'native' else float(name)
        if hz != want_hz:
            raise ValueError(f'{path.name}: stamped downsample_hz={hz} but the '
                             f'{name!r} condition expects {want_hz}')
        meta[name] = {'cache': rel(path), 'sha256': sha256(path),
                      'anchor': c['anchor_event'], 'sampling': c['sampling'],
                      'downsample_hz': hz, 'window': c.get('window')}
        print(f'  {name:>6s}  {len(by_cond[name]):,} rows')

    keys = set.intersection(*(set(v) for v in by_cond.values()))
    keys = sorted(keys)
    print(f'\nrows present in every condition: {len(keys):,}')

    # A thinned cache that is not actually thinner is the silent-drift
    # failure (e.g. a stale rebuild), so the curve must be monotone in
    # samples/trial before any model runs: native >= 30 >= 15 >= 5 >= 2 >= 1.
    order = [c[0] for c in CONDS if c[0] in by_cond]
    ns_by_cond = {n: float(np.median([by_cond[n][k].get('sample_count', np.nan)
                                      for k in keys])) for n in order}
    for prev, cur in zip(order, order[1:]):
        if not ns_by_cond[cur] <= ns_by_cond[prev]:
            raise ValueError(f'median sample_count is not non-increasing: '
                             f'{prev}={ns_by_cond[prev]:.1f} < {cur}={ns_by_cond[cur]:.1f}')

    lab_rows = json.loads((DATA / 'cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    base = by_cond['native']
    records = [dict(base[k]) for k in keys]
    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    y_def = np.asarray([int(label.get(k, False)) for k in keys])
    y_clk = np.asarray([int(base[k]['was_clicked']) for k in keys])
    # The approach gate is evaluated on the NATIVE stream so a thinned
    # condition cannot redefine which results count as approached.
    pool = np.asarray([base[k]['min_dist'] < APPROACH_PX for k in keys]) & (y_clk == 0)
    print(f'approached non-click pool (native gate): {int(pool.sum()):,}  '
          f'deferred rate {y_def[pool].mean():.3f}')

    out = {'schema_version': 2,  # v2: inputs carry downsample_hz/window
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': meta, 'n_rows_common': len(keys),
           'pool': int(pool.sum()), 'conditions': {}}

    rng = np.random.default_rng(1)
    vals = []
    for _ in range(args.perms):
        ys = y_def.copy()
        for p in np.unique(pid):
            m = pool & (pid == p)
            if m.sum():
                ys[m] = rng.permutation(ys[m])
        pr, _ = loso_proba(records, APPROACH_7, ys, pool)
        sel = pool & np.isfinite(pr)
        if len(set(ys[sel])) == 2:
            vals.append(roc_auc_score(ys[sel], pr[sel]))
    v = np.array(vals)
    out['null_deferred'] = {'mean': float(v.mean()), 'p95': float(np.percentile(v, 95)),
                            'p99': float(np.percentile(v, 99))}

    print(f"\n{'='*58}\n{'rate':>8s} {'samples/trial':>14s} {'DEFERRED':>10s} {'CLICK':>10s}\n{'='*58}")
    for name in order:
        src = by_cond[name]
        recs = [dict(src[k]) for k in keys]
        ns = ns_by_cond[name]
        pd_, _ = loso_proba(recs, APPROACH_7, y_def, pool)
        sd, _ = summarize(y_def, pd_, pid, pool)
        allrows = np.ones(len(recs), dtype=bool)
        pc, _ = loso_proba(recs, APPROACH_7, y_clk, allrows)
        sc, _ = summarize(y_clk, pc, pid, allrows)
        out['conditions'][name] = {'deferred': sd, 'click': sc,
                                   'median_sample_count': ns}
        mark = ' *' if sd['pooled_auc'] <= out['null_deferred']['p99'] else ''
        print(f"{name:>8s} {ns:14.0f} {sd['pooled_auc']:10.3f} {sc['pooled_auc']:10.3f}{mark}")
    n = out['null_deferred']
    print(f"\n  permutation null (deferred): mean {n['mean']:.3f}  "
          f"p95 {n['p95']:.3f}  p99 {n['p99']:.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
