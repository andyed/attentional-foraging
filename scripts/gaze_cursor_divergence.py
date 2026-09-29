#!/usr/bin/env python3
"""Gaze-cursor divergence on the cursor-only typed stream.

Three questions, one producer, aggregates only:

  1. Where is the cursor when it is on no main-axis AOI (parking regime), is
     that a participant trait, and does parking dilute the in-box signal?
  2. Is inter-result whitespace time a reading pointer or a place-keeper?
     (gaze coupling while the cursor sits between two results; gap-adjacent
     dwell as a per-AOI feature against the canonical M4-7 vector)
  3. What is beyond dwell? Single-feature and dwell-less LOSO AUCs on both
     targets (click; NB22 deferred vs evaluated-rejected).

Protocol mirrors m4_cursor_aoi_rerun.py: typed main-axis AOIs, screenshot
space via the per-trial ratios, native mousemove samples with
t < mousedown(final click) - 500 ms, strict x+y click containment. Gaze is
read only to (a) locate the fixation containing a cursor sample and (b) the
fifth-fixation boundary; it never enters a feature. Per-AOI M4-7 features and
click labels are taken from the canonical buf500 feature cache, hash-checked
against its sidecar; the deferred label comes from the NB22 regression cache.

Output: scripts/output/gaze_cursor_divergence/summary.json (no telemetry).
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl  # noqa: E402

M4 = ['min_dist', 'mean_dist', 'dwell_in_proximity_ms', 'mean_approach_velocity',
      'max_approach_velocity', 'direction_changes', 'frac_decreasing']
CAP_MS = 2000.0          # the dwell accumulator's interval cap
BUFFER_MS = 500.0        # canonical press-anchored buffer
APPROACH_PX = 100.0      # "approached" gate for the deferred pool
FIX_SLACK_MS = 50.0      # a cursor sample within 50 ms after a fixation ends still belongs to it
LOCS = ('in_box', 'gutter_L', 'gutter_R', 'gap', 'above', 'below')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loso(X, y, pids):
    proba = np.zeros(len(y))
    folds = {}
    for tr, te in LeaveOneGroupOut().split(X, y, pids):
        m = make_pipeline(StandardScaler(),
                          LogisticRegression(class_weight='balanced', C=1.0, max_iter=2000))
        m.fit(X[tr], y[tr])
        proba[te] = m.predict_proba(X[te])[:, 1]
        if len(set(y[te])) == 2:
            folds[pids[te][0]] = float(roc_auc_score(y[te], proba[te]))
    return float(roc_auc_score(y, proba)), folds, proba


def paired(a: dict, b: dict, seed=0):
    common = sorted(set(a) & set(b))
    d = np.array([a[p] - b[p] for p in common])
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(d, len(d)).mean() for _ in range(10000)])
    return {'n': len(d), 'mean': float(d.mean()),
            'ci95': [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            'wilcoxon_p': float(wilcoxon(d).pvalue) if np.any(d != 0) else 1.0}


def share(cnt: Counter):
    s = sum(cnt.values()) or 1.0
    return {k: cnt[k] / s for k in LOCS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--canonical-sidecar', type=Path,
                    default=ROOT / 'scripts/output/m4_cursor_aoi_mousedown/summary.json')
    ap.add_argument('--label-rows', type=Path, default=ROOT / 'AdSERP/data/cursor-approach-features-typed.json')
    ap.add_argument('--label-cache', type=Path,
                    default=ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json')
    ap.add_argument('--output', type=Path, default=ROOT / 'scripts/output/gaze_cursor_divergence/summary.json')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    # ---- provenance: substrate stamp, feature cache vs its sidecar, label cache ----
    substrate = json.loads((ROOT / 'data/aoi-typed/substrate.json').read_text())
    digest = hashlib.sha256()
    maps = sorted((ROOT / 'data/aoi-typed').glob('p*.json'))
    for p in maps:
        digest.update(p.name.encode()); digest.update(p.read_bytes())
    if digest.hexdigest()[:16] != substrate['typed_maps_content_hash']:
        raise ValueError('Typed AOI content differs from substrate stamp')
    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{int(BUFFER_MS)}']
    canonical = json.loads(args.canonical_sidecar.read_text())
    record_hash = hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    if record_hash != canonical['provenance']['feature_records_sha256'][f'buf{int(BUFFER_MS)}']:
        raise ValueError('Feature cache does not match the canonical sidecar')
    feat = {(r['trial_id'], r['position']): r for r in stored}
    lab_rows = json.loads(args.label_rows.read_text())
    reg = json.loads(args.label_cache.read_text())
    if len(lab_rows) != len(reg):
        raise ValueError('Label rows and regression cache differ in length')
    deferred = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    excl = dl.typed_alignment_exclusions()
    tids = dl.get_trial_ids()
    if args.limit:
        tids = tids[:args.limit]

    tot_unc, tot_cap = Counter(), Counter()
    per_trial_off = {}
    gap_eps, gap_x = [], Counter()
    gaze_when_gap, gaze_when_box = Counter(), Counter()
    gap_pre5 = gap_post5 = all_pre5 = all_post5 = 0.0
    cy_gy_gap, cy_gy_box = [], []
    rows = []   # (pid, tid, pos, clicked, inbox, beside, band, gapadj)
    counts = Counter()

    for tid in tids:
        if tid in excl:
            counts['alignment_excluded'] += 1; continue
        cards = [c for c in dl.load_typed_aois(tid) if c.get('position', -1) >= 0
                 and all(isinstance(c.get(k), (int, float)) and math.isfinite(c[k])
                         for k in ('x', 'y', 'width', 'height'))]
        if len(cards) < 2:
            counts['fewer_than_two_aois'] += 1; continue
        geo = dl.get_trial_geometry(tid)
        if geo is None:
            raise ValueError(f'{tid}: missing coordinate geometry')
        sx, sy = geo['ratio_x'], geo['ratio_y']
        events, _, clicks = dl.load_mouse_events(tid, space='document')
        if not clicks:
            counts['no_click'] += 1; continue
        click = max(clicks, key=lambda c: c[0])
        presses = [t for t, e, x, y in events if e == 'mousedown' and math.isfinite(t) and t <= click[0]]
        if not presses:
            counts['no_mousedown_for_final_click'] += 1; continue
        cutoff = max(presses) - BUFFER_MS
        cx, cy = click[1] * sx, click[2] * sy
        hits = [c['position'] for c in cards
                if c['x'] <= cx <= c['x'] + c['width'] and c['y'] <= cy <= c['y'] + c['height']]
        if len(hits) != 1:
            counts['ambiguous_click' if hits else 'click_outside_main_boxes'] += 1; continue
        clicked = hits[0]
        moves = [(t, x * sx, y * sy) for t, e, x, y in events
                 if e == 'mousemove' and t < cutoff and all(math.isfinite(v) for v in (t, x, y))]
        if len(moves) < 2:
            counts['insufficient_prebuffer_mousemove'] += 1; continue
        if any(b[0] < a[0] for a, b in zip(moves, moves[1:])):
            counts['nonmonotonic_mouse_time'] += 1; continue
        fix = sorted((f for f in dl.load_fixations(tid)
                      if all(math.isfinite(f[k]) for k in ('t', 'x', 'y', 'd'))), key=lambda f: f['t'])
        ft = [f['t'] for f in fix]
        fifth_end = (fix[4]['t'] + fix[4]['d']) if len(fix) >= 5 else None
        counts['included'] += 1
        cards.sort(key=lambda c: c['position'])
        y0 = min(c['y'] for c in cards); y1 = max(c['y'] + c['height'] for c in cards)
        colx0 = min(c['x'] for c in cards); colx1 = max(c['x'] + c['width'] for c in cards)

        def band_of(y):
            for c in cards:
                if c['y'] <= y <= c['y'] + c['height']:
                    return c
            return None

        def gaze_at(t):
            i = bisect.bisect_right(ft, t) - 1
            if i >= 0 and t < fix[i]['t'] + fix[i]['d'] + FIX_SLACK_MS:
                return fix[i]
            return None

        unc, cap = Counter(), Counter()
        inbox, beside, band, gapadj = (defaultdict(float) for _ in range(4))
        ep = 0.0
        for i, (t, x, y) in enumerate(moves):
            dt_ = (moves[i + 1][0] - t) if i + 1 < len(moves) else 0.0
            if dt_ <= 0:
                continue
            dtc = min(dt_, CAP_MS)
            if fifth_end is not None:
                if t < fifth_end: all_pre5 += dtc
                else: all_post5 += dtc
            g = gaze_at(t)
            gb = band_of(g['y']) if g else None
            gpos = gb['position'] if gb else None
            c = band_of(y)
            in_gap = False
            if c is not None:
                band[c['position']] += dtc
                if c['x'] <= x <= c['x'] + c['width']:
                    loc = 'in_box'; inbox[c['position']] += dtc
                    gaze_when_box['on_same' if gpos == c['position'] else 'adjacent'
                                  if gpos is not None and abs(gpos - c['position']) == 1 else
                                  'other_aoi' if gpos is not None else 'off_or_none'] += dtc
                    if g: cy_gy_box.append((y, g['y']))
                else:
                    loc = 'gutter_L' if x < c['x'] else 'gutter_R'; beside[c['position']] += dtc
            elif y < y0:
                loc = 'above'
            elif y > y1:
                loc = 'below'
            else:
                loc = 'gap'; in_gap = True
                above = max((k for k in cards if k['y'] + k['height'] < y), key=lambda k: k['y'])
                below = min((k for k in cards if k['y'] > y), key=lambda k: k['y'])
                ep += dt_
                gap_x['column' if colx0 <= x <= colx1 else 'gutter'] += dtc
                gapadj[above['position']] += dtc / 2; gapadj[below['position']] += dtc / 2
                if fifth_end is not None:
                    if t < fifth_end: gap_pre5 += dtc
                    else: gap_post5 += dtc
                gaze_when_gap['on_above' if gpos == above['position'] else 'on_below'
                              if gpos == below['position'] else 'other_aoi'
                              if gpos is not None else 'off_or_none'] += dtc
                if g: cy_gy_gap.append((y, g['y']))
            if not in_gap and ep > 0:
                gap_eps.append(ep); ep = 0.0
            unc[loc] += dt_; cap[loc] += dtc
        if ep > 0:
            gap_eps.append(ep)
        tot_unc.update(unc); tot_cap.update(cap)
        per_trial_off[tid] = 1.0 - share(unc)['in_box']
        pid = tid.split('-')[0]
        for c in cards:
            p = c['position']
            rows.append((pid, tid, p, int(p == clicked), inbox[p], beside[p], band[p], gapadj[p]))

    # ---- join to canonical features; the joined population is the paper's 34,328 rows ----
    joined = []
    for r in rows:
        f = feat.get((r[1], r[2]))
        if f is None:
            continue
        if int(f['was_clicked']) != r[3]:
            raise ValueError(f'Click label disagrees with canonical cache at {r[1]}/{r[2]}')
        joined.append(r + (f,))
    pids = np.array([r[0] for r in joined]); y_click = np.array([r[3] for r in joined])
    appr = [r for r in joined if r[3] == 0 and r[8]['min_dist'] < APPROACH_PX and (r[1], r[2]) in deferred]
    pids_d = np.array([r[0] for r in appr]); y_def = np.array([int(deferred[(r[1], r[2])]) for r in appr])

    def X_of(rs, cols, log=False):
        X = np.array([[r[8][c] if isinstance(c, str) else r[c] for c in cols] for r in rs], dtype=float)
        return np.log1p(X) if log else X

    # 1. parking regime
    by_pid = defaultdict(list)
    for t, v in per_trial_off.items():
        by_pid[t.split('-')[0]].append(v)
    allv = np.array(list(per_trial_off.values()))
    within = float(np.mean([np.var(v) for v in by_pid.values() if len(v) > 1]))
    off_rows = np.array([per_trial_off[r[1]] for r in joined])
    cuts = np.percentile(allv, [100 / 3, 200 / 3])
    _, _, proba_inbox = loso(X_of(joined, [4], log=True), y_click, pids)
    terciles = {}
    for name, mask in (('low', off_rows < cuts[0]), ('mid', (off_rows >= cuts[0]) & (off_rows < cuts[1])),
                       ('high', off_rows >= cuts[1])):
        terciles[name] = {'rows': int(mask.sum()), 'in_box_dwell_auc': float(roc_auc_score(y_click[mask], proba_inbox[mask]))}
    parking = {
        'time_share_uncapped': share(tot_unc), 'time_share_capped_2s': share(tot_cap),
        'per_trial_off_box_share_quantiles': {q: float(np.percentile(allv, p)) for q, p in
                                              (('q25', 25), ('median', 50), ('q75', 75))},
        'participant_median_off_box_quantiles': {q: float(np.percentile([np.median(v) for v in by_pid.values()], p))
                                                 for q, p in (('min', 0), ('q25', 25), ('median', 50), ('q75', 75), ('max', 100))},
        'off_box_variance': {'total': float(allv.var()), 'within_participant_mean': within,
                             'between_participant_share': float(1 - within / allv.var())},
        'tercile_cuts': [float(c) for c in cuts], 'in_box_dwell_auc_by_off_box_tercile': terciles,
        'single_feature_click_auc': {name: loso(X_of(joined, cols, log=True), y_click, pids)[0]
                                     for name, cols in (('in_box_dwell', [4]), ('beside_box_dwell', [5]),
                                                        ('vertical_band_dwell', [6]), ('in_box_plus_beside', [4, 5]))},
        'clicked_aois_zero_in_box_dwell_share': float(np.mean([r[4] == 0 for r in joined if r[3]])),
    }

    # 2. whitespace
    eps = np.array(gap_eps)
    def cc(arr):
        a = np.array(arr); d = a[:, 1] - a[:, 0]
        return {'n': len(a), 'pearson_r': float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]),
                'gaze_minus_cursor_px': {'median': float(np.median(d)), 'q25': float(np.percentile(d, 25)),
                                         'q75': float(np.percentile(d, 75))}}
    m4_c, f_m4_c, _ = loso(X_of(joined, M4), y_click, pids)
    m4g_c, f_m4g_c, _ = loso(np.hstack([X_of(joined, M4), X_of(joined, [7], log=True)]), y_click, pids)
    m4_d, f_m4_d, _ = loso(X_of(appr, M4), y_def, pids_d)
    m4g_d, f_m4g_d, _ = loso(np.hstack([X_of(appr, M4), X_of(appr, [7], log=True)]), y_def, pids_d)
    whitespace = {
        'gap_episodes': {'n': int(len(eps)), 'median_ms': float(np.median(eps)),
                         'q25_ms': float(np.percentile(eps, 25)), 'q75_ms': float(np.percentile(eps, 75)),
                         'time_share_in_episodes_over_1s': float(eps[eps > 1000].sum() / eps.sum()),
                         'time_share_in_episodes_over_3s': float(eps[eps > 3000].sum() / eps.sum())},
        'gap_time_by_x': {k: gap_x[k] / sum(gap_x.values()) for k in ('column', 'gutter')},
        'gap_share_of_cursor_time': {'pre_fifth_fixation': gap_pre5 / max(all_pre5, 1), 'post': gap_post5 / max(all_post5, 1)},
        'gaze_while_cursor_in_gap': {k: v / sum(gaze_when_gap.values()) for k, v in gaze_when_gap.items()},
        'gaze_while_cursor_in_box': {k: v / sum(gaze_when_box.values()) for k, v in gaze_when_box.items()},
        'cursor_y_vs_gaze_y': {'gap': cc(cy_gy_gap), 'box': cc(cy_gy_box)},
        'gap_adjacent_dwell': {
            'click': {'alone_auc': loso(X_of(joined, [7], log=True), y_click, pids)[0], 'm4_7_auc': m4_c,
                      'm4_7_plus_gap_auc': m4g_c, 'paired_participant_delta': paired(f_m4g_c, f_m4_c)},
            'deferred': {'alone_auc': loso(X_of(appr, [7], log=True), y_def, pids_d)[0], 'm4_7_auc': m4_d,
                         'm4_7_plus_gap_auc': m4g_d, 'paired_participant_delta': paired(f_m4g_d, f_m4_d)}},
    }

    # 3. beyond dwell
    sets = {'dwell_only': ['dwell_in_proximity_ms'], 'min_dist_only': ['min_dist'], 'mean_dist_only': ['mean_dist'],
            'mean_approach_velocity_only': ['mean_approach_velocity'], 'direction_changes_only': ['direction_changes'],
            'm4_7_minus_dwell': [f for f in M4 if f != 'dwell_in_proximity_ms'],
            'dwell_plus_mean_dist': ['dwell_in_proximity_ms', 'mean_dist'], 'm4_7': M4}
    beyond = {name: {'click': loso(X_of(joined, cols), y_click, pids)[0],
                     'deferred': loso(X_of(appr, cols), y_def, pids_d)[0]} for name, cols in sets.items()}

    payload = {
        'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'regime': '[LAB, AdSERP, typed]; cursor-only stream, press-anchored 500 ms buffer',
        'protocol': {'buffer_ms': BUFFER_MS, 'dwell_cap_ms': CAP_MS, 'approach_px': APPROACH_PX,
                     'fixation_slack_ms': FIX_SLACK_MS, 'classifier': 'LOSO 47-fold balanced LR, StandardScaler, C=1.0',
                     'dwell_features_log1p': True, 'm4_features_raw': True,
                     'gaze_used_for': ['fixation containing a cursor sample (coupling only)', 'fifth-fixation boundary (timing split)',
                                       'NB22 deferred label (target only)']},
        'counts': dict(counts), 'rows': {'scanned': len(rows), 'joined_to_canonical': len(joined),
                                          'approached_non_click': len(appr), 'deferred_rate': float(y_def.mean())},
        'parking_regime': parking, 'whitespace': whitespace, 'beyond_dwell': beyond,
        'provenance': {'producer_sha256': sha256(Path(__file__)), 'substrate': substrate,
                       'feature_cache': str(args.feature_cache.relative_to(ROOT)), 'feature_records_sha256': record_hash,
                       'canonical_sidecar_sha256': sha256(args.canonical_sidecar),
                       'label_cache_sha256': sha256(args.label_cache), 'label_rows_sha256': sha256(args.label_rows),
                       'data_loader_sha256': sha256(ROOT / 'notebooks-v2/data_loader.py')},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'counts': payload['counts'], 'rows': payload['rows'],
                      'off_box_share': round(1 - parking['time_share_uncapped']['in_box'], 4),
                      'beyond_dwell': {k: {t: round(v, 4) for t, v in d.items()} for k, d in beyond.items()},
                      'gap_adj_paired_click': whitespace['gap_adjacent_dwell']['click']['paired_participant_delta'],
                      'gap_adj_paired_deferred': whitespace['gap_adjacent_dwell']['deferred']['paired_participant_delta']},
                     indent=1))
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
