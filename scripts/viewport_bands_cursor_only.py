"""Viewport bands (AR-V3) re-derived on the cursor-only deferred pool.

approach-retreat/docs/key-claims.md section V3 and
docs/validation/viewport-bands-calibration.md quote, on a fixation-selected
organic pool with the nine-feature LAB cursor vector: retreat alone 0.775,
bands alone 0.743, combined 0.811, vt_top > vt_mid > vt_bot, and a vt_top
coefficient that is positive at P0-P3 and reaches zero by P5. Those rows came
from scripts/viewport_bands_bootstrap.py. This producer asks the same
questions on the rows the paper now reports: the canonical cursor-only typed
cache (press-anchored, buf500), approached (min_dist < 100 px) non-click rows,
NB22 gaze-regression label, cursor vector = APPROACH_7.

Band definition (edmonds-2026-vpbands-v1, viewport_time_calibration.
viewport_ms_for_trial): the scroll timeline is piecewise constant, scrollY = 0
from the first mouse event and stepped at each scroll event; an AOI accrues
vp_any while any part of it intersects [scrollY, scrollY + vp_h], and accrues
vt_top / vt_mid / vt_bot according to which third of the viewport its centre
lies in. Two things differ from the old producer and are stated here rather
than hidden: (1) the timeline is cut at mousedown(final click) - 500 ms, the
window every cursor number on this pool is computed on (scroll_kinematics.
scroll_stream owns that cutoff; the old producer ran to the last mouse event,
after the click); (2) geometry is in screenshot space -- typed cards, scroll y
scaled by ratio_y, viewport height = screen_height * ratio_y -- as
scroll_only_carve.py does on this pool. The old producer mixed document-space
scroll y with band tops and raw screen_height. A raw-screen_height sensitivity
row is reported so the height convention is a visible choice.

Gate: LOSO balanced LR on APPROACH_7 over the shipped pool must reproduce
m4_cursor_only_downstream/summary.json section_4_3.deployable_M4_7.pooled_auc
to 1e-6 before any band number is computed.

Run from attentional-foraging:
  .venv/bin/python scripts/viewport_bands_cursor_only.py
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from m4_cursor_aoi_rerun import APPROACH_7, load_flavor_cards, main_cards  # noqa: E402
from m4_cursor_only_downstream import (  # noqa: E402
    APPROACH_PX, loso_proba, paired, rel, sha256, summarize,
)
from deferred_dwell_carve import visit_decomposition  # noqa: E402
from reduction_baselines import within_trial_auc  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'viewport_bands_cursor_only'
BUFFER_MS = 500.0
BANDS = ['vt_top', 'vt_mid', 'vt_bot']
BAND_ALL = ['vp_any'] + BANDS
GATE_TOL = 1e-6
N_BOOT_RANK = 1000
MIN_ROWS_PER_POSITION = 100
RANK_POSITIONS = range(6)


def observation_cutoff(events, clicks):
    """mousedown(final click) - BUFFER_MS, the boundary scroll_kinematics.
    scroll_stream cuts at. Returns None when there is no click or no press."""
    if not clicks:
        return None
    click_t = max(c[0] for c in clicks)
    presses = [t for t, e, _x, _y in events
               if e == 'mousedown' and math.isfinite(t) and t <= click_t]
    if not presses:
        return None
    return max(presses) - BUFFER_MS


def band_ms(cards, scrolls, t_start, t_end, vp_h):
    """Per-position [vp_any, vt_top, vt_mid, vt_bot] in ms over [t_start, t_end].

    Same arithmetic as viewport_time_calibration.viewport_ms_for_trial: scrollY
    starts at 0, steps at each scroll event inside the window, and the last
    value holds to t_end. An interval of zero duration is skipped. A tall AOI
    whose centre is off-viewport while part of it is visible counts in vp_any
    only. cards and scrolls must share one coordinate space with vp_h.
    """
    out = {}
    if t_end <= t_start or not vp_h:
        return out
    third = vp_h / 3.0
    timeline = [(t_start, 0.0)]
    for t, y in sorted(scrolls):
        if t_start <= t < t_end:
            timeline.append((float(t), float(y)))
    timeline.append((t_end, timeline[-1][1]))
    acc = {c['position']: [0.0, 0.0, 0.0, 0.0] for c in cards}
    geom = [(c['position'], c['y'], c['y'] + c['height']) for c in cards]
    for (t0, y0), (t1, _) in zip(timeline, timeline[1:]):
        d = t1 - t0
        if d <= 0:
            continue
        vp_top, vp_bot = y0, y0 + vp_h
        for p, a_top, a_bot in geom:
            if min(a_bot, vp_bot) <= max(a_top, vp_top):
                continue
            a = acc[p]
            a[0] += d
            c_vp = (a_top + a_bot) / 2.0 - y0
            if 0 <= c_vp < third:
                a[1] += d
            elif third <= c_vp < 2 * third:
                a[2] += d
            elif 2 * third <= c_vp <= vp_h:
                a[3] += d
    return acc


def standardized_coefs(X, y):
    m = make_pipeline(StandardScaler(),
                      LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
    m.fit(X, y)
    return m[-1].coef_.ravel()


def rank_dependence(records, y, pool, pid, n_boot, seed):
    """vt_top coefficient of the bands-alone LR fitted per position, with a
    participant-cluster bootstrap (participants resampled with replacement
    inside the position slice, model refit, coefficient recorded)."""
    rng = np.random.default_rng(seed)
    pos = np.asarray([r['position'] for r in records])
    X = np.asarray([[r[f] for f in BANDS] for r in records], dtype=float)
    out = {}
    for p in RANK_POSITIONS:
        m = pool & (pos == p)
        n = int(m.sum())
        if n < MIN_ROWS_PER_POSITION or len(set(y[m])) < 2:
            out[str(p)] = {'n': n, 'skipped': True, 'reason': f'fewer than {MIN_ROWS_PER_POSITION} rows or one class'}
            continue
        idx = np.where(m)[0]
        point = standardized_coefs(X[idx], y[idx])
        uniq = np.unique(pid[idx])
        by_p = {q: idx[pid[idx] == q] for q in uniq}
        draws = []
        for _ in range(n_boot):
            sampled = rng.choice(uniq, size=len(uniq), replace=True)
            ii = np.concatenate([by_p[q] for q in sampled])
            if len(set(y[ii])) < 2:
                continue
            draws.append(standardized_coefs(X[ii], y[ii]))
        draws = np.asarray(draws)
        out[str(p)] = {
            'n': n, 'n_deferred': int(y[m].sum()), 'participants': int(len(uniq)),
            'vt_top_coef': float(point[0]),
            'vt_top_bootstrap': {'median': float(np.median(draws[:, 0])),
                                 'ci95': np.quantile(draws[:, 0], [.025, .975]).tolist(),
                                 'n_draws': int(len(draws))},
            'vt_mid_coef': float(point[1]), 'vt_bot_coef': float(point[2]),
            'ci_includes_zero': bool(np.quantile(draws[:, 0], .025) <= 0 <= np.quantile(draws[:, 0], .975)),
        }
    return out


def model_block(records, feats, y, mask, pid, tids):
    proba, _ = loso_proba(records, feats, y, mask)
    s, folds = summarize(y, proba, pid, mask)
    wt, n_pairs = within_trial_auc(tids, y, proba, mask)
    s['within_trial_auc'] = float(wt)
    s['within_trial_pairs'] = int(n_pairs)
    s['features'] = list(feats)
    return s, folds


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--gate-sidecar', type=Path,
                    default=ROOT / 'scripts/output/m4_cursor_only_downstream/summary.json')
    ap.add_argument('--n-boot-rank', type=int, default=N_BOOT_RANK)
    ap.add_argument('--seed', type=int, default=20260918)
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    args = ap.parse_args()
    assert args.buffer == BUFFER_MS, 'the scroll cutoff is fixed at the canonical 500 ms'

    import data_loader as dl

    # ---- rows, labels, pool: exactly m4_cursor_only_downstream ---------------------------
    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar_path = ROOT / 'scripts/output' / args.summary_dir / 'summary.json'
    sidecar = json.loads(sidecar_path.read_text())
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match its aggregate sidecar')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))

    lab_rows_path = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
    label_path = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
    lab_rows = json.loads(lab_rows_path.read_text())
    reg = json.loads(label_path.read_text())
    assert len(lab_rows) == len(reg)
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    tids_arr = [r['trial_id'] for r in records]
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    y = np.asarray([int(label.get((r['trial_id'], r['position']), False)) for r in records])
    shipped_pool = approached & (clicked == 0)

    # ---- gate ------------------------------------------------------------------------------
    gate_ref = json.loads(args.gate_sidecar.read_text())['section_4_3']['deployable_M4_7']['pooled_auc']
    p7, _ = loso_proba(records, APPROACH_7, y, shipped_pool)
    g, _ = summarize(y, p7, pid, shipped_pool)
    gate = {'reference': gate_ref, 'reproduced': g['pooled_auc'],
            'abs_diff': abs(g['pooled_auc'] - gate_ref), 'tolerance': GATE_TOL,
            'n_records': g['n_records'], 'passed': abs(g['pooled_auc'] - gate_ref) <= GATE_TOL}
    print(f"gate: reproduced {g['pooled_auc']:.6f} vs shipped {gate_ref:.6f} "
          f"(diff {gate['abs_diff']:.2e}) on {g['n_records']:,} rows")
    if not gate['passed']:
        raise SystemExit('GATE FAILED: shipped M4-7 pooled AUC not reproduced; refusing to compute bands')

    # ---- viewport bands per (trial, position) ----------------------------------------------
    tids = sorted({r['trial_id'] for r in records})
    full, raw_h, carve = {}, {}, {}
    trial_skips, carve_skips = Counter(), Counter()
    vp_heights = []
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  bands {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, args.flavor))
        except Exception:
            trial_skips['cards_unusable'] += 1
            continue
        if not cards:
            trial_skips['no_typed_cards'] += 1
            continue
        geom = dl.get_trial_geometry(tid)
        if geom is None:
            trial_skips['no_geometry'] += 1
            continue
        scr_h = geom['screen_height']
        if not scr_h:
            trial_skips['no_screen_height'] += 1
            continue
        try:
            # Document space once; scroll y scaled by the same ratio_y that
            # load_mouse_events(space='screenshot') applies, so the cards, the
            # scroll timeline and the viewport height share screenshot space
            # without a second screenshot open per trial.
            events, scrolls, clicks = dl.load_mouse_events(tid, space='document')
        except Exception:
            trial_skips['no_mouse_events'] += 1
            continue
        if not events:
            trial_skips['no_mouse_events'] += 1
            continue
        cutoff = observation_cutoff(events, clicks)
        if cutoff is None:
            trial_skips['no_final_click_or_press'] += 1
            continue
        t_start = min(e[0] for e in events)
        if cutoff <= t_start:
            trial_skips['cutoff_before_first_event'] += 1
            continue
        ry = geom['ratio_y']
        scrolls_ss = [(t, yy * ry) for t, yy in scrolls if math.isfinite(t) and math.isfinite(yy)]
        vp_h = scr_h * ry
        vp_heights.append(vp_h)
        for p, v in band_ms(cards, scrolls_ss, t_start, cutoff, vp_h).items():
            full[(tid, p)] = v
        for p, v in band_ms(cards, scrolls_ss, t_start, cutoff, float(scr_h)).items():
            raw_h[(tid, p)] = v
        # First-visit carve: the same bands cut at min(cutoff, end of the first
        # gaze visit to that position). Diagnostic only; the cutoff needs gaze.
        try:
            per_pos, _c, _r = visit_decomposition(dl, tid, cards)
        except Exception:
            carve_skips['visit_decomposition_failed'] += 1
            continue
        for p, vis in per_pos.items():
            cut = vis.get('first_visit_end_ms')
            if cut is None:
                carve_skips['no_first_visit_end'] += 1
                continue
            t_c = min(cutoff, float(cut))
            if t_c <= t_start:
                carve_skips['first_visit_ends_before_first_event'] += 1
                continue
            v = band_ms([c for c in cards if c['position'] == p], scrolls_ss, t_start, t_c, vp_h)
            if p in v:
                carve[(tid, p)] = v[p]

    have = np.asarray([(r['trial_id'], r['position']) in full for r in records])
    have_carve = np.asarray([(r['trial_id'], r['position']) in carve for r in records])
    for r in records:
        k = (r['trial_id'], r['position'])
        for j, nm in enumerate(BAND_ALL):
            r[nm] = full.get(k, [0.0] * 4)[j]
            r[f'rawh_{nm}'] = raw_h.get(k, [0.0] * 4)[j]
            r[f'first_{nm}'] = carve.get(k, [0.0] * 4)[j]

    pool = shipped_pool & have
    carve_pool = pool & have_carve
    vt = np.asarray([[r[f] for f in BAND_ALL] for r in records])[pool]
    print(f"\nbands computed for {len({k[0] for k in full}):,}/{len(tids):,} trials; "
          f"trial skips {dict(trial_skips)}")
    print(f"pool {int(pool.sum()):,} of shipped {int(shipped_pool.sum()):,} "
          f"(dropped {int((shipped_pool & ~have).sum()):,} rows on skipped trials); "
          f"carve pool {int(carve_pool.sum()):,}")

    out = {
        'schema_version': 1,
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'regime': '[LAB, AdSERP, typed, cursor-only]',
        'inputs': {
            'feature_cache': rel(args.feature_cache), 'feature_cache_sha256': sha256(args.feature_cache),
            'aggregate_sidecar': rel(sidecar_path), 'aggregate_sidecar_sha256': sha256(sidecar_path),
            'lab_rows_for_label_alignment': rel(lab_rows_path), 'lab_rows_sha256': sha256(lab_rows_path),
            'regression_label_cache': rel(label_path), 'regression_label_cache_sha256': sha256(label_path),
            'gate_sidecar': rel(args.gate_sidecar), 'gate_sidecar_sha256': sha256(args.gate_sidecar),
            'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event'], 'sampling': cache['sampling'],
            'flavor': args.flavor,
        },
        'definitions': {
            'cursor_features': list(APPROACH_7),
            'band_features': BAND_ALL,
            'band_rule': 'edmonds-2026-vpbands-v1: scrollY = 0 from the first mouse event, stepped at scroll '
                         'events; vp_any accrues while any part of the AOI intersects [scrollY, scrollY + vp_h]; '
                         'vt_top/vt_mid/vt_bot accrue by which third of the viewport the AOI centre lies in',
            'window': 'first mouse event to mousedown(final click) - 500 ms (scroll_kinematics.scroll_stream boundary)',
            'space': 'screenshot: typed cards; scroll y * ratio_y; vp_h = screen_height * ratio_y (scroll_only_carve.py convention)',
            'sensitivity_space': 'rawh_*: vp_h = screen_height unscaled, everything else identical',
            'carve': 'first_*: same bands cut at min(window end, end of first gaze visit to that position); '
                     'diagnostic, the cutoff needs an eye tracker',
            'differences_from_viewport_bands_bootstrap_py': [
                'rows: cursor-only typed cache (native mousemove, press-anchored buf500) instead of the '
                'fixation-selected organic LAB rows; cursor vector APPROACH_7 instead of the nine-feature set',
                'window: cut at mousedown - 500 ms instead of running to the last mouse event after the click',
                'space: screenshot space throughout instead of document-space scroll y with raw screen_height',
                'trials with zero scroll events are kept (viewport at scrollY = 0 for the whole window), as the old producer did',
            ],
        },
        'gate': gate,
        'population': {
            'records': len(records), 'trials': len(tids), 'participants': int(len(np.unique(pid))),
            'shipped_pool': int(shipped_pool.sum()),
            'pool': int(pool.sum()), 'pool_deferred': int(y[pool].sum()),
            'pool_participants': int(len(np.unique(pid[pool]))),
            'pool_trials': int(len({t for t, m in zip(tids_arr, pool) if m})),
            'rows_dropped_from_shipped_pool': int((shipped_pool & ~have).sum()),
            'trials_with_bands': len({k[0] for k in full}),
            'trial_skips': dict(trial_skips),
            'carve_pool': int(carve_pool.sum()), 'carve_pool_deferred': int(y[carve_pool].sum()),
            'carve_skips': dict(carve_skips),
            'vp_h_screenshot_px': {'min': float(min(vp_heights)), 'max': float(max(vp_heights)),
                                   'median': float(np.median(vp_heights))},
            'band_ms_pool_quantiles': {nm: {'p10': float(np.percentile(vt[:, j], 10)),
                                            'median': float(np.median(vt[:, j])),
                                            'p90': float(np.percentile(vt[:, j], 90))}
                                       for j, nm in enumerate(BAND_ALL)},
        },
    }

    # ---- models, one pool per table ----------------------------------------------------------
    models = {}
    folds = {}
    print(f"\n{'model':32s} {'pooled':>7s} {'fold mean±sd':>15s} {'within-trial':>13s} {'n':>6s}")
    for name, feats in (('cursor_M4_7', APPROACH_7), ('bands_3', BANDS), ('vp_any', ['vp_any']),
                        ('cursor_M4_7_plus_bands_3', APPROACH_7 + BANDS),
                        ('bands_4_any_plus_thirds', BAND_ALL),
                        ('cursor_M4_7_plus_bands_4', APPROACH_7 + BAND_ALL),
                        ('bands_3_raw_screen_height', [f'rawh_{b}' for b in BANDS])):
        s, f = model_block(records, feats, y, pool, pid, tids_arr)
        models[name] = s
        folds[name] = f
        print(f"{name:32s} {s['pooled_auc']:7.3f} {s['fold_auc_mean']:7.3f} ± {s['fold_auc_sd']:.3f} "
              f"{s['within_trial_auc']:13.3f} {s['n_records']:6,d}")
    out['models'] = models
    out['paired_by_participant'] = {
        'method': 'per-participant LOSO fold AUC differences; 10,000-draw bootstrap of the participant mean '
                  '(participant-cluster) plus two-sided Wilcoxon (m4_cursor_only_downstream.paired)',
        'bands_3_minus_cursor': paired(folds['bands_3'], folds['cursor_M4_7']),
        'combined_minus_cursor': paired(folds['cursor_M4_7_plus_bands_3'], folds['cursor_M4_7']),
        'combined_minus_bands_3': paired(folds['cursor_M4_7_plus_bands_3'], folds['bands_3']),
        'vp_any_minus_bands_3': paired(folds['vp_any'], folds['bands_3']),
        'raw_screen_height_minus_scaled_bands_3': paired(folds['bands_3_raw_screen_height'], folds['bands_3']),
    }
    for k, v in out['paired_by_participant'].items():
        if isinstance(v, dict) and 'mean_delta' in v:
            print(f"  {k:40s} Δ {v['mean_delta']:+.3f} CI [{v['bootstrap_ci95'][0]:+.3f}, {v['bootstrap_ci95'][1]:+.3f}] "
                  f"p={v['wilcoxon_two_sided_p']:.2e}")

    # ---- coefficient signs, pooled standardized -------------------------------------------
    Xb = np.asarray([[r[f] for f in BANDS] for r in records], dtype=float)
    Xc = np.asarray([[r[f] for f in APPROACH_7 + BANDS] for r in records], dtype=float)
    cb = standardized_coefs(Xb[pool], y[pool])
    cc = standardized_coefs(Xc[pool], y[pool])
    out['coefficients'] = {
        'note': 'StandardScaler + balanced LR fitted once on the whole pool; + predicts deferred',
        'bands_3': dict(zip(BANDS, map(float, cb))),
        'cursor_M4_7_plus_bands_3': dict(zip(APPROACH_7 + BANDS, map(float, cc))),
        'bands_3_ordering': ' > '.join(b for b, _ in sorted(zip(BANDS, cb), key=lambda t: -t[1])),
    }
    print(f"\nbands-alone coefficients: " + ', '.join(f'{b} {c:+.3f}' for b, c in zip(BANDS, cb)))

    # ---- rank dependence of vt_top ---------------------------------------------------------
    print(f"\nrank dependence of vt_top (bands-alone LR per position, {args.n_boot_rank} participant-cluster draws)")
    rd = rank_dependence(records, y, pool, pid, args.n_boot_rank, args.seed)
    for p, rec in rd.items():
        if rec.get('skipped'):
            print(f"  P{p}: n={rec['n']} skipped")
            continue
        b = rec['vt_top_bootstrap']
        print(f"  P{p}: n={rec['n']:4d} vt_top {rec['vt_top_coef']:+.2f} "
              f"boot median {b['median']:+.2f} CI [{b['ci95'][0]:+.2f}, {b['ci95'][1]:+.2f}]"
              f"{'  CI includes 0' if rec['ci_includes_zero'] else ''}")
    out['rank_dependence_vt_top'] = {'positions': list(RANK_POSITIONS), 'min_rows': MIN_ROWS_PER_POSITION,
                                     'n_boot': args.n_boot_rank, 'seed': args.seed, 'per_position': rd}

    # ---- first-visit carve (diagnostic) ------------------------------------------------------
    carve_models = {}
    cfolds = {}
    print(f"\nfirst-visit carve, one pool ({int(carve_pool.sum()):,} rows)")
    for name, feats in (('cursor_M4_7', APPROACH_7),
                        ('bands_3_full_window', BANDS),
                        ('bands_3_first_visit', [f'first_{b}' for b in BANDS]),
                        ('vp_any_full_window', ['vp_any']),
                        ('vp_any_first_visit', ['first_vp_any']),
                        ('cursor_M4_7_plus_bands_3_first_visit', APPROACH_7 + [f'first_{b}' for b in BANDS])):
        s, f = model_block(records, feats, y, carve_pool, pid, tids_arr)
        carve_models[name] = s
        cfolds[name] = f
        print(f"  {name:38s} {s['pooled_auc']:7.3f} within-trial {s['within_trial_auc']:.3f}")
    Xf = np.asarray([[r[f'first_{f}'] for f in BANDS] for r in records], dtype=float)
    cf = standardized_coefs(Xf[carve_pool], y[carve_pool])
    out['first_visit_carve'] = {
        'status': 'run', 'note': 'cutoff = end of the first gaze visit (deferred_dwell_carve.visit_decomposition); '
                                 'a scroll-only deployment cannot compute it',
        'models': carve_models,
        'coefficients_bands_3_first_visit': dict(zip(BANDS, map(float, cf))),
        'paired_first_visit_minus_full_bands_3': paired(cfolds['bands_3_first_visit'], cfolds['bands_3_full_window']),
        'paired_first_visit_bands_minus_cursor': paired(cfolds['bands_3_first_visit'], cfolds['cursor_M4_7']),
    }

    out['provenance'] = {'producer': rel(Path(__file__)), 'producer_sha256': sha256(__file__),
                         'python': sys.version.split()[0]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=1, allow_nan=False) + '\n')
    print(f'\nwrote {args.output}')


if __name__ == '__main__':
    main()
