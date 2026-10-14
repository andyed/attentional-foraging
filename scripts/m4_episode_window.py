"""Episode-cropped M4 cursor features: does click prediction survive the crop?

Runs the canonical producer (scripts/m4_cursor_aoi_rerun.py) three times on
the press-anchored 500 ms headline protocol, changing only --window:

  whole        every retained post-buffer mousemove sample, every AOI (paper §4.1)
  episode      per AOI, only samples inside that AOI's proximity episodes:
               maximal runs of consecutive samples with |pageY - center y| < 100 px
  episode-pad  the same runs extended by 500 ms on both sides

Row inclusion, labels and LOSO folds are identical across windows (checked).
Rows with no in-episode sample get the tracker's empty state (all features 0,
min_dist = 0 included); they are counted, and two controls separate "entered
the zone at all" from what happens inside the episode:
  * in_zone alone (1 if the AOI had any in-episode sample) and M4-7 + in_zone;
  * a non-empty subset: trials whose clicked AOI has an episode, rows with an
    episode, scored with episode and whole-stream features on the same rows.

Run from attentional-foraging:
  .venv/bin/python scripts/m4_episode_window.py
Writes scripts/output/m4_episode_window/summary.json (aggregates only) plus the
three per-window producer summaries under runs/. Feature caches stay untracked.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import m4_cursor_aoi_rerun as m4  # noqa: E402

OUT = ROOT / 'scripts/output/m4_episode_window'
WINDOWS = {'whole': 'all', 'episode': 'episode', 'episode_pad': 'episode-pad'}
BUFFER = 500
# The headline run's grid. Row inclusion requires two samples before the
# LARGEST buffer cutoff, so the grid fixes the population (2,608 trials /
# 34,328 rows); only the 500 ms condition is scored here.
BUFFER_GRID = [0, 250, 500, 1000]
HEADLINE = ROOT / 'scripts/output/m4_cursor_aoi_mousedown/summary.json'
COND = f'buf{BUFFER}'
KEEP = ('pooled_auc', 'fold_auc_mean', 'fold_auc_median', 'fold_auc_iqr',
        'mrr_at_10', 'ndcg_at_1', 'n_records', 'n_clicks', 'n_folds', 'n_ranked_trials')


def slim(res):
    return {k: res[k] for k in KEEP}


def run_producer(name, window):
    out_dir = OUT / 'runs' / name
    cache = OUT / 'cache' / f'{name}.json'
    cmd = [sys.executable, str(HERE / 'm4_cursor_aoi_rerun.py'), '--anchor', 'mousedown',
           '--buffers', *map(str, BUFFER_GRID), '--window', window, '--no-ablation',
           '--output-dir', str(out_dir), '--feature-cache', str(cache)]
    print('$', ' '.join(cmd[1:]), flush=True)
    subprocess.run(cmd, check=True)
    summary = json.loads((out_dir / 'summary.json').read_text())
    records = json.loads(cache.read_text())['conditions'][COND]
    return summary, records


def main():
    summaries, records = {}, {}
    for name, window in WINDOWS.items():
        summaries[name], records[name] = run_producer(name, window)
    keys = {n: [(r['trial_id'], r['position'], r['was_clicked']) for r in rs]
            for n, rs in records.items()}
    if not (keys['whole'] == keys['episode'] == keys['episode_pad']):
        raise ValueError('Rows/labels differ across windows')
    n_rows = len(keys['whole'])

    models, folds = {}, {}
    for name, rs in records.items():
        models[name], folds[name] = {}, {}
        for label, feats in (('M1_position', ['position']), ('M4-7', m4.APPROACH_7),
                             ('M3_position_plus_M4-7', ['position'] + m4.APPROACH_7)):
            res, f = m4.evaluate(rs, feats)
            models[name][label], folds[name][label] = slim(res), f
            print(f'{name} {label}: pooled {res["pooled_auc"]:.4f} median {res["fold_auc_median"]:.4f}'
                  f' MRR {res["mrr_at_10"]:.4f} NDCG@1 {res["ndcg_at_1"]:.4f}', flush=True)

    paired = {
        'episode_vs_whole_M4-7': m4.paired_comparison(folds['episode']['M4-7'], folds['whole']['M4-7']),
        'episode_pad_vs_whole_M4-7': m4.paired_comparison(folds['episode_pad']['M4-7'], folds['whole']['M4-7']),
        'episode_M4-7_vs_M1': m4.paired_comparison(folds['episode']['M4-7'], folds['whole']['M1_position']),
        'episode_pad_M4-7_vs_M1': m4.paired_comparison(folds['episode_pad']['M4-7'], folds['whole']['M1_position']),
    }

    single = {}
    for name, rs in records.items():
        single[name] = {}
        for feat in m4.APPROACH_7:
            res, _ = m4.evaluate(rs, [feat])
            single[name][feat] = {k: res[k] for k in ('pooled_auc', 'fold_auc_median', 'mrr_at_10', 'ndcg_at_1')}
        print(f'{name} single-feature sweep done', flush=True)

    # Zone-entry control. in_zone is identical for episode and episode-pad
    # (a padded run exists iff an unpadded run exists) and equals whole-stream
    # min_dist < 100 px.
    in_zone = [int(r['kept_samples'] > 0) for r in records['episode']]
    if in_zone != [int(r['min_dist'] < m4.EPISODE_PROXIMITY_PX) for r in records['whole']]:
        raise ValueError('in_zone disagrees with whole-stream min_dist < 100 px')
    zone = {}
    aug = [dict(r, in_zone=z) for r, z in zip(records['whole'], in_zone)]
    res, zf = m4.evaluate(aug, ['in_zone'])
    zone['in_zone_alone'] = slim(res)
    res, pf = m4.evaluate(aug, ['position', 'in_zone'])
    zone['position_plus_in_zone'] = slim(res)
    zone_folds = {}
    for name in ('episode', 'episode_pad'):
        aug = [dict(r, in_zone=z) for r, z in zip(records[name], in_zone)]
        res, f = m4.evaluate(aug, m4.APPROACH_7 + ['in_zone'])
        zone[f'{name}_M4-7_plus_in_zone'] = slim(res)
        zone_folds[name] = f
    zone['paired'] = {
        'whole_M4-7_vs_in_zone_alone': m4.paired_comparison(folds['whole']['M4-7'], zf),
        'episode_M4-7_vs_in_zone_alone': m4.paired_comparison(folds['episode']['M4-7'], zf),
        'episode_M4-7_plus_in_zone_vs_in_zone_alone': m4.paired_comparison(zone_folds['episode'], zf),
        'whole_M4-7_vs_position_plus_in_zone': m4.paired_comparison(folds['whole']['M4-7'], pf),
    }
    zone['note'] = ('in_zone = 1 when the AOI has at least one post-buffer sample within 100 px of its '
                    'center (equivalently whole-stream min_dist < 100). It is what the empty-state rows '
                    'encode, so it bounds how much of the episode-window AUC is zone entry alone.')
    print('zone control done', flush=True)

    # Non-empty subset: within-episode information only. Trials whose clicked
    # AOI never entered its zone are dropped; then rows without an episode.
    trials_ok = {r['trial_id'] for r, z in zip(records['episode'], in_zone) if r['was_clicked'] and z}
    idx = [i for i, (r, z) in enumerate(zip(records['episode'], in_zone)) if z and r['trial_id'] in trials_ok]
    multi = {}
    for i in idx:
        multi.setdefault(records['episode'][i]['trial_id'], []).append(i)
    # Ranking needs at least two candidates; single-candidate trials go.
    idx = [i for i in idx if len(multi[records['episode'][i]['trial_id']]) >= 2]
    subset = {'rule': 'trials whose clicked AOI has >= 1 in-episode sample; rows with >= 1 in-episode sample; '
                      'trials left with >= 2 such rows',
              'n_trials': len({records['episode'][i]['trial_id'] for i in idx}), 'n_rows': len(idx)}
    sub_folds = {}
    for name in WINDOWS:
        rs = [records[name][i] for i in idx]
        res, f = m4.evaluate(rs, m4.APPROACH_7)
        subset[f'{name}_M4-7'] = slim(res)
        sub_folds[name] = f
        res, f1 = m4.evaluate(rs, ['position'])
        subset[f'{name}_M1_position'] = slim(res)
        if name == 'episode':
            subset['episode_single_feature'] = {}
            for feat in m4.APPROACH_7:
                r1, _ = m4.evaluate(rs, [feat])
                subset['episode_single_feature'][feat] = {k: r1[k] for k in ('pooled_auc', 'fold_auc_median', 'mrr_at_10')}
    subset['paired'] = {
        'episode_vs_whole_M4-7': m4.paired_comparison(sub_folds['episode'], sub_folds['whole']),
        'episode_pad_vs_whole_M4-7': m4.paired_comparison(sub_folds['episode_pad'], sub_folds['whole']),
    }
    print(f'non-empty subset: {subset["n_trials"]} trials, {subset["n_rows"]} rows; '
          f'episode {subset["episode_M4-7"]["pooled_auc"]:.4f} whole {subset["whole_M4-7"]["pooled_auc"]:.4f}', flush=True)

    files = {'driver': Path(__file__), 'producer': HERE / 'm4_cursor_aoi_rerun.py',
             'bridge': HERE / 'm4_cursor_tracker.mjs'}
    payload = {
        'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'question': 'Does M4-7 click prediction survive cropping each AOI to its own proximity episodes?',
        'configuration': {
            'regime': '[LAB, AdSERP, typed]; cursor-only predictors and row selection; no gaze',
            'anchor_event': 'mousedown', 'buffer_ms': BUFFER, 'sampling': 'native mousemove',
            'windows': {
                'whole': 'all retained post-buffer samples against every AOI center (paper §4.1)',
                'episode': summaries['episode']['episode_diagnostics']['definition'],
                'episode_pad': summaries['episode_pad']['episode_diagnostics']['definition'],
            },
            'order': 'press buffer first, then episode detection on the remaining samples',
            'distance': 'vertical |pageY - AOI center y| in document CSS px',
            'empty_row_policy': summaries['episode']['episode_diagnostics']['empty_row_policy'],
            'estimator': 'LOSO by participant, StandardScaler + balanced LogisticRegression(C=1)',
            'paired_test': 'per-participant fold AUC difference, 10,000 bootstrap resamples (seed 20260904), Wilcoxon',
        },
        'counts': summaries['whole']['counts'], 'n_rows': n_rows,
        'n_trials': len({k[0] for k in keys['whole']}),
        'episode_survival': {n: summaries[n]['episode_diagnostics'][COND] for n in ('episode', 'episode_pad')},
        'models': models, 'paired': paired, 'single_feature': single,
        'zone_entry_control': zone, 'nonempty_subset': subset,
        'provenance': {
            'sha256': {k: m4.sha256(p) for k, p in files.items()},
            'run_summaries_sha256': {n: m4.sha256(OUT / 'runs' / n / 'summary.json') for n in WINDOWS},
            'record_keys_and_labels_sha256': summaries['whole']['provenance']['record_keys_and_labels_sha256'],
            'feature_records_sha256': {n: summaries[n]['provenance']['feature_records_sha256'][COND] for n in WINDOWS},
            'substrate_typed_maps_content_hash': summaries['whole']['substrate']['typed_maps_content_hash'],
            'mouse_and_metadata_sha256': summaries['whole']['provenance']['mouse_and_metadata_sha256'],
            'producer_provenance': summaries['whole']['provenance'],
            'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        },
    }
    headline = json.loads(HEADLINE.read_text())
    if headline['provenance']['record_keys_and_labels_sha256'] != payload['provenance']['record_keys_and_labels_sha256']:
        raise ValueError('Rows/labels differ from the committed headline run')
    payload['provenance']['headline_summary_sha256'] = m4.sha256(HEADLINE)
    payload['provenance']['headline_M4-7_buf500_pooled_auc'] = headline['conditions'][COND]['M4-7']['pooled_auc']
    payload['configuration']['buffer_grid_for_row_inclusion'] = BUFFER_GRID
    for n in WINDOWS:
        if summaries[n]['provenance']['record_keys_and_labels_sha256'] != payload['provenance']['record_keys_and_labels_sha256']:
            raise ValueError('record key hash differs across runs')
    (OUT / 'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(f'Wrote {OUT / "summary.json"}')


if __name__ == '__main__':
    main()
