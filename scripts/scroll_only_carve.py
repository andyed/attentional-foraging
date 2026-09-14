"""Scroll+click-only floor for the deferred task, on the canonical typed pool.

Peter's condition: no cursor position stream at all. Features come from the
scroll timeline and the viewport -- the paper's own proposed mobile analog
("viewport residence replaces cursor proximity-dwell").

The same carve applies. For the gaze to make the return fixation that DEFINES
`deferred`, the result must be on screen, so viewport residence measured over
the whole trial contains the label exactly as total_dwell_ms does. Both are
reported. The first-visit column is a LEAKAGE DIAGNOSTIC, not a deployable
claim: it truncates the scroll timeline at the end of the first GAZE visit,
a cutoff a scroll-only deployment cannot compute without an eye tracker. It
shows what viewport residence retains once the label-containing time is
removed; it is not a feature that deployment could ship.

Rows, pool and label match scripts/deferred_dwell_carve.py: the canonical
cursor-only typed cache (press-anchored, buf500), approached non-click pool,
typed regression label.

Run from attentional-foraging:
  .venv/bin/python scripts/scroll_only_carve.py
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

from m4_cursor_only_downstream import loso_proba, summarize, sha256, rel, APPROACH_PX  # noqa: E402
from deferred_dwell_carve import visit_decomposition  # noqa: E402
from m4_cursor_aoi_rerun import APPROACH_7 as APPROACH_7_LOCAL  # noqa: E402
from scroll_kinematics import scroll_stream  # noqa: E402

SCROLL_FEATS = ['vp_residence_ms', 'n_vp_entries', 'min_vp_dist', 'mean_vp_dist',
                'vp_hwm_return', 'n_scroll_events', 'session_ms']


def scroll_features(scrolls, cards, scr_h, cutoff=None):
    """Viewport-residence features per position from the scroll timeline alone.

    scrolls are (t, y) in screenshot space; cards are typed boxes in the same
    space. cutoff truncates the timeline at the end of the first gaze visit.
    """
    s = [(t, y) for t, y in scrolls if cutoff is None or t <= cutoff]
    if len(s) < 2 or not scr_h:
        return {}
    # Elapsed span of THIS window. Passing the whole-trial span into the
    # truncated condition leaks post-cutoff duration into a feature the
    # carve is supposed to have removed.
    t_span = float(s[-1][0] - s[0][0])
    st = np.asarray([x[0] for x in s], dtype=float)
    sy = np.asarray([x[1] for x in s], dtype=float)
    dts = np.diff(st)
    ok = dts > 0
    vp_centre = sy + scr_h / 2.0
    out = {}
    for c in cards:
        p = c.get('position', -1)
        if p < 0:
            continue
        centre = c['y'] + c['height'] / 2.0
        bot = c['y'] + c['height']
        inside = (sy <= centre) & (centre <= sy + scr_h)
        residence = float(dts[ok & inside[1:] & (dts < 30000)].sum())
        entries = int(np.sum((~inside[:-1]) & inside[1:])) + int(inside[0])
        d = np.abs(centre - vp_centre)
        hwm, passed, hwm_return = -1e18, False, 0
        for i in range(len(sy)):
            if sy[i] + scr_h > hwm:
                hwm = sy[i] + scr_h
            if not passed and hwm > bot + scr_h * 0.25:
                passed = True
            elif passed and inside[i]:
                hwm_return = 1
                break
        out[p] = [residence, float(entries), float(d.min()), float(d.mean()),
                  float(hwm_return), float(len(s)), float(t_span)]
    return out


def perm_null(records, feats, y, pool, pid, n=100, seed=1):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        ys = y.copy()
        for p in np.unique(pid):
            m = pool & (pid == p)
            if m.sum():
                ys[m] = rng.permutation(ys[m])
        pr, _ = loso_proba(records, feats, ys, pool)
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
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--perms', type=int, default=100)
    ap.add_argument('--output', type=Path,
                    default=ROOT / 'scripts/output/deferred_dwell_carve/scroll_only.json')
    ap.add_argument('--labeled-only', action='store_true',
                    help='Carve on rows PRESENT in the label cache only (examined '
                         'non-clicks), mirroring deferred_dwell_carve.py. Default '
                         'is the shipped pool, absent rows counted as rejected.')
    args = ap.parse_args()

    import data_loader as dl
    from m4_cursor_aoi_rerun import load_flavor_cards, main_cards

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match its aggregate sidecar')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({r['trial_id'] for r in records})
    full_by_key, first_by_key = {}, {}
    from collections import Counter
    skips = Counter()
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
            # Window-match the cursor columns: every cursor number this is
            # compared with is computed on samples strictly before
            # mousedown(final click) - 500 ms, so the uncut scroll list
            # (final approach + post-press scrolls) is not the same window.
            # scroll_stream owns that cutoff; do not re-derive it here.
            stream = scroll_stream(tid, dl)
            geom = dl.get_trial_geometry(tid)
        except Exception:
            skips['load_failed'] += 1
            continue
        if len(cards) < 2:
            skips['fewer_than_two_aois'] += 1
            continue
        if stream is None:
            # kinematics' eligibility rule: >=3 scroll events before the cutoff
            skips['fewer_than_three_scrolls_pre_cutoff'] += 1
            continue
        st, sy = stream
        scrolls = list(zip(st, sy))
        if geom is None:
            skips['no_geometry'] += 1
            continue
        _doc_h, scr_h, _ = dl.get_trial_meta(tid)
        if not scr_h:
            skips['no_screen_height'] += 1
            continue
        scr_h = scr_h * geom['ratio_y']
        per_pos, _c, _r = visit_decomposition(dl, tid, cards)
        full = scroll_features(scrolls, cards, scr_h)
        for p, v in full.items():
            full_by_key[(tid, p)] = v
        # first-visit-only: truncate the scroll timeline at the end of the
        # first gaze visit to THAT position, so the window differs per AOI.
        for p, vis in per_pos.items():
            cut = vis.get('first_visit_end_ms')
            if cut is None:
                skips['no_first_visit_end'] += 1
                continue
            fv = scroll_features(scrolls, [c for c in cards if c.get('position') == p],
                                 scr_h, cutoff=cut)
            if p in fv:
                first_by_key[(tid, p)] = fv[p]

    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    y = np.asarray([int(label.get((r['trial_id'], r['position']), False)) for r in records])
    have = np.asarray([(r['trial_id'], r['position']) in full_by_key
                       and (r['trial_id'], r['position']) in first_by_key
                       for r in records])
    # A row absent from the label cache was never fixated under the label
    # producer's assignment (see deferred_dwell_carve.py); --labeled-only
    # restricts the carve to examined non-clicks, the shipped pool keeps them
    # as rejected via `.get(key, False)` above.
    labeled = np.asarray([(r['trial_id'], r['position']) in label for r in records])
    pool = approached & (clicked == 0) & have
    if args.labeled_only:
        pool = pool & labeled

    for r in records:
        k = (r['trial_id'], r['position'])
        f = full_by_key.get(k, [0.0] * len(SCROLL_FEATS))
        v = first_by_key.get(k, [0.0] * len(SCROLL_FEATS))
        for j, nm in enumerate(SCROLL_FEATS):
            r[f'full_{nm}'] = f[j]
            r[f'first_{nm}'] = v[j]

    out = {'schema_version': 3,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'buffer_ms': args.buffer, 'flavor': args.flavor,
                      'scroll_window': 'mousemove/scroll events strictly before '
                                       'mousedown(final click) - 500 ms '
                                       '(scroll_kinematics.scroll_stream)',
                      # the first-visit cutoff needs gaze; say so in the output
                      'carve_cutoff': 'end of first gaze visit (diagnostic, not deployable)'},
           'skips': dict(skips),
           'population': {'pool': int(pool.sum()),
                          'carve_pool': 'label_complete' if args.labeled_only else 'shipped',
                          'labeled_only': bool(args.labeled_only),
                          'participants': int(len(np.unique(pid[pool]))),
                          'deferred': int((pool & (y == 1)).sum())}}
    print(f"  skips: {dict(skips)}")
    print(f"\npool {int(pool.sum()):,}  participants "
          f"{len(np.unique(pid[pool]))}  deferred rate {y[pool].mean():.3f}")

    out['null'] = perm_null(records, [f'full_{n}' for n in SCROLL_FEATS],
                            y, pool, pid, n=args.perms)
    out['all_seven'] = {}
    print(f"\n{'='*62}\nSCROLL+CLICK ONLY, deferred task (canonical pool)\n{'='*62}")
    for tag, prefix in (('full trial', 'full'), ('first visit only', 'first')):
        p, _ = loso_proba(records, [f'{prefix}_{n}' for n in SCROLL_FEATS], y, pool)
        s, _ = summarize(y, p, pid, pool)
        out['all_seven'][tag] = s
        mark = '  <- inside null' if s['pooled_auc'] <= out['null']['p99'] else ''
        print(f"  {tag:20s} AUC {s['pooled_auc']:.3f}   fold "
              f"{s['fold_auc_mean']:.3f} +- {s['fold_auc_sd']:.3f}{mark}")
    # Cursor M4-7 on the SAME pool rows, so the scroll-vs-cursor comparison
    # on the deferred target is same-rows (the click block below already
    # carries its own; quoting that one against this pool mixes pools).
    m4d, _ = loso_proba(records, APPROACH_7_LOCAL, y, pool)
    sm4d, _ = summarize(y, m4d, pid, pool)
    out['all_seven']['cursor_M4_7_same_rows'] = {
        'pooled_auc': sm4d['pooled_auc'], 'fold_auc_mean': sm4d['fold_auc_mean'],
        'fold_auc_sd': sm4d['fold_auc_sd'], 'n_records': sm4d['n_records']}
    print(f"  {'cursor M4-7, same rows':20s} AUC {sm4d['pooled_auc']:.3f}   fold "
          f"{sm4d['fold_auc_mean']:.3f} +- {sm4d['fold_auc_sd']:.3f}")
    n = out['null']
    print(f"  {'perm null':20s} mean {n['mean']:.3f}  p95 {n['p95']:.3f}  p99 {n['p99']:.3f}")

    # The CLICK target as well: the premise of the Jaewon Kim collaboration
    # ask is that desktop scroll does NOT discriminate clicked from non-clicked
    # results while the cursor does. That claim predates the cursor-only rebuild
    # and needs re-deriving on this stream before it is quoted to anyone.
    have_all = np.asarray([(r['trial_id'], r['position']) in full_by_key
                           for r in records])
    clicked_y = clicked.astype(int)
    out['click_target'] = {}
    print(f"\n{'='*62}\nCLICK target on the same scroll features\n{'='*62}")
    for tag, prefix in (('scroll full trial', 'full'),):
        pc, _ = loso_proba(records, [f'{prefix}_{n}' for n in SCROLL_FEATS],
                           clicked_y, have_all)
        sc_, _ = summarize(clicked_y, pc, pid, have_all)
        out['click_target'][tag] = sc_
        print(f"  {tag:24s} AUC {sc_['pooled_auc']:.3f}  fold "
              f"{sc_['fold_auc_mean']:.3f} +- {sc_['fold_auc_sd']:.3f}  "
              f"n={sc_['n_records']:,}")
    for j, nm in enumerate(SCROLL_FEATS):
        pc, _ = loso_proba(records, [f'full_{nm}'], clicked_y, have_all)
        sc_, _ = summarize(clicked_y, pc, pid, have_all)
        out['click_target'][nm] = sc_['pooled_auc']
        print(f"     {nm:22s} {sc_['pooled_auc']:.3f}")
    m4c, _ = loso_proba(records, APPROACH_7_LOCAL, clicked_y, have_all)
    sm4, _ = summarize(clicked_y, m4c, pid, have_all)
    out['click_target']['cursor_M4_7_same_rows'] = sm4['pooled_auc']
    print(f"  {'cursor M4-7, same rows':24s} AUC {sm4['pooled_auc']:.3f}")

    out['single'] = {}
    print('\n  single features (full | first visit):')
    for nm in SCROLL_FEATS:
        a, _ = loso_proba(records, [f'full_{nm}'], y, pool)
        sa, _ = summarize(y, a, pid, pool)
        b, _ = loso_proba(records, [f'first_{nm}'], y, pool)
        sb, _ = summarize(y, b, pid, pool)
        out['single'][nm] = {'full': sa['pooled_auc'], 'first': sb['pooled_auc']}
        print(f"     {nm:22s} {sa['pooled_auc']:.3f} | {sb['pooled_auc']:.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
