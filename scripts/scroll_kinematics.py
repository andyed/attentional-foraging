"""Scroll kinematics as the viewport-pointer projection: does the scroll channel
carry an evaluation signal, or is it ballistic transport?

Settles the premise of the Jaewon Kim collaboration ask
(`docs/drafts/email-jaewon-kim.md`), which asserts that on desktop "scroll dwell,
velocity deceleration, and pause duration are all identical for clicked vs
non-clicked results (all p > 0.3)" and concludes the two motor channels
specialise — scroll for transport, cursor for evaluation. That claim predates the
cursor-only rebuild and was never re-derived. `scroll_only_carve.py` already
showed that viewport *geometry* from the same timeline reaches click AUC 0.779,
which is not a null — but geometry is a different feature family from kinematics,
so the original claim was unverified rather than falsified. This producer builds
the kinematics.

The construction is the paper's own, with the **viewport as the pointer** instead
of the cursor: d(t) = |candidate_centre - viewport_centre|, aggregated over
derivative order 0 (proximity, residence, pause), 1-magnitude (approach rate,
deceleration) and 1-sign (direction changes, fraction closing). So this is not an
ad-hoc feature set; it is the mobile row of the reduction table computed properly.
The earlier scroll vector was order-0 heavy and therefore understated the channel.

Scroll events fire only on change, so an inter-event gap IS a stationary interval:
pauses are measured as gaps, not inferred.

Both targets, one protocol, plus the first-visit carve on the deferral target
(viewport residence contains the return exactly as gaze dwell does) and
within-trial concordance alongside pooled AUC. The carve is a LEAKAGE
DIAGNOSTIC, not a deployable claim: it truncates the scroll timeline at the
end of the first GAZE visit, a cutoff a scroll-only deployment cannot compute
without an eye tracker. It shows what the viewport-pointer features retain
once the label-containing time is removed; it is not a feature deployment
could ship.

Run from attentional-foraging:
  .venv/bin/python scripts/scroll_kinematics.py
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from m4_cursor_aoi_rerun import APPROACH_7, main_cards, load_flavor_cards  # noqa: E402
from m4_cursor_only_downstream import loso_proba, summarize, sha256, rel, APPROACH_PX  # noqa: E402
from deferred_dwell_carve import visit_decomposition  # noqa: E402
from transition_pathing import within_trial_auc  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'scroll_kinematics'
BUFFER_MS = 500.0
PAUSE_MS = 500.0        # an inter-scroll gap this long counts as a pause
DWELL_CAP_MS = 30000.0

ORDER0 = ['K_min_dist', 'K_mean_dist', 'K_residence_ms', 'K_max_pause_ms',
          'K_total_pause_ms', 'K_n_pauses']
ORDER1M = ['K_mean_approach_vel', 'K_max_approach_vel', 'K_vel_at_closest',
           'K_decel_into_closest']
ORDER1S = ['K_dir_changes', 'K_frac_closing']
KIN = ORDER0 + ORDER1M + ORDER1S
EMAIL3 = ['K_residence_ms', 'K_decel_into_closest', 'K_max_pause_ms']


def scroll_stream(tid, dl):
    """Scroll timeline in screenshot space, cut at the canonical observation
    boundary (mousedown of the final click minus 500 ms)."""
    try:
        events, scrolls, clicks = dl.load_mouse_events(tid, space='screenshot')
    except Exception:
        return None
    if not clicks or len(scrolls) < 3:
        return None
    click = max(clicks, key=lambda c: c[0])
    presses = [t for t, e, x, y in events
               if e == 'mousedown' and math.isfinite(t) and t <= click[0]]
    if not presses:
        return None
    cutoff = max(presses) - BUFFER_MS
    s = sorted((t, y) for t, y in scrolls
               if math.isfinite(t) and math.isfinite(y) and t < cutoff)
    if len(s) < 3:
        return None
    return np.asarray([p[0] for p in s]), np.asarray([p[1] for p in s])


def kinematics(st, sy, scr_h, centre, cut=None):
    """Viewport-pointer features for one candidate. cut truncates the timeline
    (used for the first-visit carve)."""
    if cut is not None:
        m = st <= cut
        st, sy = st[m], sy[m]
    if len(st) < 3 or not scr_h:
        return None
    vp_centre = sy + scr_h / 2.0
    d = np.abs(centre - vp_centre)
    visible = (sy <= centre) & (centre <= sy + scr_h)
    dt_ = np.diff(st)
    dd = np.diff(d)
    ok = dt_ > 0
    if not ok.any():
        return None
    # order 0
    residence = float(dt_[ok & visible[1:] & (dt_ < DWELL_CAP_MS)].sum())
    gaps = dt_[ok & visible[1:]]
    pauses = gaps[gaps >= PAUSE_MS]
    # order 1, magnitude: closing rate on the candidate (positive = approaching)
    vel = -dd[ok] / dt_[ok] * 1000.0
    i_closest = int(np.argmin(d))
    j = max(min(i_closest - 1, len(vel) - 1), 0)
    vel_at_closest = float(abs(vel[j])) if len(vel) else 0.0
    prior = vel[max(j - 3, 0):j]
    decel = float(np.mean(np.abs(prior)) - vel_at_closest) if len(prior) else 0.0
    # order 1, sign
    sgn = np.sign(vel)
    dirchg = int(np.sum(np.diff(sgn) != 0)) if len(sgn) > 1 else 0
    return {
        'K_min_dist': float(d.min()), 'K_mean_dist': float(d.mean()),
        'K_residence_ms': residence,
        'K_max_pause_ms': float(pauses.max()) if len(pauses) else 0.0,
        'K_total_pause_ms': float(pauses.sum()) if len(pauses) else 0.0,
        'K_n_pauses': float(len(pauses)),
        'K_mean_approach_vel': float(vel.mean()),
        'K_max_approach_vel': float(vel.max()),
        'K_vel_at_closest': vel_at_closest,
        'K_decel_into_closest': decel,
        'K_dir_changes': float(dirchg),
        'K_frac_closing': float(np.mean(dd[ok] < 0)),
    }


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

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({r['trial_id'] for r in records})
    skips = defaultdict(int)
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
            geom = dl.get_trial_geometry(tid)
        except Exception:
            skips['cards'] += 1; continue
        if len(cards) < 2 or geom is None:
            skips['cards'] += 1; continue
        ss = scroll_stream(tid, dl)
        if ss is None:
            skips['scroll'] += 1; continue
        st, sy = ss
        _dh, scr_h, _ = dl.get_trial_meta(tid)
        if not scr_h:
            skips['screen_h'] += 1; continue
        scr_h = scr_h * geom['ratio_y']
        per_pos, _c, _r = visit_decomposition(dl, tid, cards)
        for c in cards:
            r = keyed.get((tid, c['position']))
            if r is None:
                continue
            centre = c['y'] + c['height'] / 2.0
            full = kinematics(st, sy, scr_h, centre)
            if full is None:
                skips['no_kin'] += 1; continue
            r.update(full)
            v = per_pos.get(c['position'])
            fv = (kinematics(st, sy, scr_h, centre, cut=v['first_visit_end_ms'])
                  if v else None)
            for k in KIN:
                r[f'FV_{k}'] = (fv[k] if fv else 0.0)
            r['_kin'] = True
            r['_fv'] = fv is not None
    rows = [r for r in records if r.get('_kin')]
    print(f'\nrows with kinematics {len(rows):,} over '
          f'{len({r["trial_id"] for r in rows}):,} trials; skips {dict(skips)}')

    pid = np.asarray([r['trial_id'].split('-')[0] for r in rows])
    tarr = [r['trial_id'] for r in rows]
    y_click = np.asarray([int(r['was_clicked']) for r in rows])
    y_def = np.asarray([int(label.get((r['trial_id'], r['position']), False))
                        for r in rows])
    labeled = np.asarray([(r['trial_id'], r['position']) in label for r in rows])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in rows])
    pool_def = approached & (y_click == 0) & labeled & np.asarray([r['_fv'] for r in rows])
    allr = np.ones(len(rows), dtype=bool)
    print(f'click rows {len(rows):,} ({int(y_click.sum()):,} clicks) | '
          f'deferred pool {int(pool_def.sum()):,}')

    MODELS = [
        ("email's three (dwell, decel, pause)", EMAIL3),
        ('K order 0 only (proximity/residence/pause)', ORDER0),
        ('K order 1-magnitude only (rates, decel)', ORDER1M),
        ('K order 1-sign only', ORDER1S),
        ('K full viewport-pointer vector', KIN),
        ('K full, first-visit carve', [f'FV_{k}' for k in KIN]),
        ('cursor M4-7, same rows', APPROACH_7),
        ('cursor M4-7 + K full', APPROACH_7 + KIN),
    ]
    out = {'schema_version': 2,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'inputs': {'feature_cache': rel(args.feature_cache),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'pause_threshold_ms': PAUSE_MS, 'flavor': args.flavor,
                      # the first-visit cutoff needs gaze; say so in the output
                      'carve_cutoff': 'end of first gaze visit (diagnostic, not deployable)'},
           'population': {'rows': len(rows), 'clicks': int(y_click.sum()),
                          'deferred_pool': int(pool_def.sum()),
                          # pool_def already requires presence in the label
                          # cache (`labeled` above), so there is no shipped
                          # variant here; no --labeled-only flag needed.
                          'carve_pool': 'label_complete',
                          'participants': int(len(np.unique(pid))),
                          'skips': dict(skips)},
           'click': {}, 'deferred': {}}
    print(f"\n{'='*94}\n{'model':>44s} {'CLICK':>8s} {'in-trial':>9s} "
          f"{'DEFERRED':>9s} {'in-trial':>9s}\n{'='*94}")
    for name, feats in MODELS:
        pc, _ = loso_proba(rows, feats, y_click, allr)
        sc, _ = summarize(y_click, pc, pid, allr)
        wc, _ = within_trial_auc(tarr, y_click, pc, allr)
        sc['within_trial_auc'] = wc
        out['click'][name] = sc
        pd_, _ = loso_proba(rows, feats, y_def, pool_def)
        sd, _ = summarize(y_def, pd_, pid, pool_def)
        wd, _ = within_trial_auc(tarr, y_def, pd_, pool_def)
        sd['within_trial_auc'] = wd
        out['deferred'][name] = sd
        print(f"{name:>44s} {sc['pooled_auc']:8.3f} {wc:9.3f} "
              f"{sd['pooled_auc']:9.3f} {wd:9.3f}")

    print('\n  single kinematic features (CLICK pooled AUC):')
    out['click_single'] = {}
    for f in KIN:
        p_, _ = loso_proba(rows, [f], y_click, allr)
        s_, _ = summarize(y_click, p_, pid, allr)
        out['click_single'][f] = s_['pooled_auc']
        print(f"     {f:24s} {s_['pooled_auc']:.3f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
