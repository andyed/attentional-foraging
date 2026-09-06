"""Validate and render an m4_cursor_aoi_rerun.py aggregate as Key Claims rows.

Used by notebooks-v2/21_click_prediction.ipynb for both the click-anchored
reference run and the press-anchored (mousedown) buffer grid. The function
refuses smoke output, stale source or substrate hashes, a mismatched solver
environment, and inconsistent populations before it prints a single number.
It never loads telemetry or fits a model.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path

FEATURES_9 = [
    'min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
    'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
    'direction_changes', 'frac_decreasing',
]
FEATURES_7 = [f for f in FEATURES_9 if f not in ('final_dist', 'retreat_dist')]
EXPECTED_FEATURES = {'M1': ['position'], 'M3': ['position'] + FEATURES_7,
                     'M4-7': FEATURES_7, 'M4-9': FEATURES_9}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_and_validate(summary_path, expected_buffers, expected_anchor,
                      repo_root=None, source_root=None, tracker_js=None):
    root = Path(repo_root or os.environ.get('M4_REPO_ROOT', '.')).resolve()
    if root.name == 'notebooks-v2':
        root = root.parent
    source_root = Path(source_root or os.environ.get('M4_SOURCE_ROOT', str(root))).resolve()
    tracker = Path(tracker_js or os.environ.get(
        'M4_TRACKER_JS', str(root.parent / 'approach-retreat/src/approach-retreat.js')))
    summary_path = Path(summary_path)
    summary = json.loads(summary_path.read_text())

    if summary.get('schema_version') != 1 or summary.get('status') != 'full_corpus':
        raise ValueError('A full-corpus schema-v1 aggregate is required; smoke output is not evidence.')
    protocol = summary['protocol']
    if (protocol.get('rank_type') != 'typed' or protocol.get('gaze_used') is not False
            or protocol.get('feature_source') != 'approach-retreat ResultFeatureTracker'
            or sorted(protocol.get('buffers_ms', [])) != sorted(expected_buffers)
            or protocol.get('anchor_event') != expected_anchor
            or protocol.get('proximity_px') != 100):
        raise ValueError('Unexpected sensor, attribution, anchor, buffer, or feature protocol.')

    source_files = {
        'producer': source_root / 'scripts/m4_cursor_aoi_rerun.py',
        'bridge': source_root / 'scripts/m4_cursor_tracker.mjs',
        'tracker': tracker,
        'data_loader': root / 'notebooks-v2/data_loader.py',
        'substrate': root / 'data/aoi-typed/substrate.json',
        'exclusions': root / 'data/aoi-typed/alignment-exclusions.json',
    }
    for key, path in source_files.items():
        if _sha256(path) != summary['provenance']['sha256'].get(key):
            raise ValueError(f'Stale aggregate: {key} source hash differs.')
    substrate = json.loads(source_files['substrate'].read_text())
    if summary['substrate'] != substrate:
        raise ValueError('Aggregate substrate stamp differs from the current stamp.')
    maps = sorted((root / 'data/aoi-typed').glob('p*.json'))
    digest = hashlib.sha256()
    for path in maps:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    if digest.hexdigest()[:16] != substrate['typed_maps_content_hash']:
        raise ValueError('AOI files differ from the declared substrate hash.')
    exclusions = json.loads(source_files['exclusions'].read_text())['tids']
    counts = summary['counts']
    if (len(maps) != substrate['n_trial_maps'] or len(exclusions) != substrate['n_excluded']
            or counts['discovered_trials'] != len(maps)
            or counts['alignment_excluded'] != len(exclusions) or counts['included'] <= 0):
        raise ValueError('Full-corpus counts or exclusions disagree with the substrate.')
    if (metadata.version('scikit-learn') != summary['provenance']['sklearn']
            or metadata.version('numpy') != summary['provenance']['numpy']):
        raise ValueError('Reader environment differs from the recorded solver environment.')

    population = None
    for condition in (f'buf{b}' for b in expected_buffers):
        for model, features in EXPECTED_FEATURES.items():
            result = summary['conditions'][condition][model]
            this = tuple(result[k] for k in ('n_records', 'n_clicks', 'n_folds'))
            if result['features'] != features:
                raise ValueError(f'Unexpected feature order for {model}.')
            if population is not None and this != population:
                raise ValueError('Model/buffer populations differ; no matched comparison may be printed.')
            population = this
    if population[1] != counts['included'] or population[2] != 47:
        raise ValueError('Expected one target click per included trial and 47 valid LOSO folds.')
    for key, pair in summary['paired'].items():
        if pair['n_participants'] != population[2]:
            raise ValueError(f'Paired comparison {key} does not cover the reported folds.')

    diag = summary['sampling_diagnostics']
    removed, changed = diag['samples_removed_relative_to_buf0'], diag['trials_changed_relative_to_buf0']
    if removed['buf0'] != 0 or changed['buf0'] != 0:
        raise ValueError('buf0 must remove nothing relative to itself.')
    for condition in removed:
        if not 0 <= changed[condition] <= counts['included'] or removed[condition] < changed[condition]:
            raise ValueError('Inconsistent sampling diagnostics.')
        if removed[condition] == 0 and (
                summary['provenance']['feature_records_sha256'][condition]
                != summary['provenance']['feature_records_sha256']['buf0']
                or summary['conditions'][condition] != summary['conditions']['buf0']):
            raise ValueError('No removed samples reported, but buffered features or metrics differ.')
    for key in ('last_mousemove_to_click_ms_quantiles', 'last_mousemove_to_anchor_ms_quantiles',
                'anchor_to_click_ms_quantiles'):
        values = [diag[key][k] for k in ('min', 'q25', 'median', 'q75', 'max')]
        if not all(math.isfinite(v) and v >= 0 for v in values) or values != sorted(values):
            raise ValueError(f'Inconsistent {key}.')
    return summary, substrate, exclusions, population, _sha256(summary_path)


def render_claims(summary, substrate, exclusions, population, summary_sha, *,
                  headline_buffer, id_prefix, rel_path, title):
    """Markdown block with stable K-IDs; every value is read from the aggregate."""
    counts = summary['counts']
    hb = f'buf{headline_buffer}'
    anchor = summary['protocol']['anchor_event']
    diag = summary['sampling_diagnostics']
    cond = summary['conditions'][hb]
    lines = [
        f'### {title}',
        '',
        f"Generated {summary['generated_utc']}; `[LAB, AdSERP, typed, cursor-only, {anchor}-anchored, {hb}]`. "
        f"AOI map hash `{substrate['typed_maps_content_hash']}`; {len(exclusions)} alignment exclusions. "
        'Source and substrate hashes verified.',
        '',
        f'Source: [cursor-only aggregate]({rel_path}); SHA256 `{summary_sha}`.',
        '',
        '| ID | Claim | Value |',
        '|---|---|---|',
        f"| **{id_prefix}-1** | Included trials / AOI records / valid participant folds | "
        f"{counts['included']:,} / {population[0]:,} / {population[2]} |",
    ]
    n = 2
    for model in ('M1', 'M3', 'M4-7', 'M4-9'):
        r = cond[model]
        lines.append(
            f"| **{id_prefix}-{n}** | {model} pooled OOF AUC; participant mean ± SD; median [IQR]; MRR@10; NDCG@1 | "
            f"**{r['pooled_auc']:.4f}**; {r['fold_auc_mean']:.4f} ± {r['fold_auc_sd']:.4f}; "
            f"{r['fold_auc_median']:.4f} [{r['fold_auc_iqr'][0]:.4f}, {r['fold_auc_iqr'][1]:.4f}]; "
            f"{r['mrr_at_10']:.4f}; {r['ndcg_at_1']:.4f} |")
        n += 1
    for key, label in ((f'{hb}_M4-7_vs_M1', 'M4-7 minus M1'), (f'{hb}_M3_vs_M4-7', 'M3 minus M4-7')):
        p = summary['paired'][key]
        ci = p['bootstrap_ci95']
        lines.append(
            f"| **{id_prefix}-{n}** | {label}, mean paired participant AUC difference | "
            f"**{p['mean_participant_auc_delta']:+.4f}**; 95% participant-bootstrap CI "
            f"[{ci[0]:+.4f}, {ci[1]:+.4f}]; Wilcoxon p = {p['wilcoxon_two_sided_p']:.2e} |")
        n += 1
    grid = ' / '.join(
        f"{c}: {summary['conditions'][c]['M4-7']['pooled_auc']:.4f} "
        f"({diag['samples_removed_relative_to_buf0'][c]:,} samples, "
        f"{diag['trials_changed_relative_to_buf0'][c]:,} trials changed)"
        for c in summary['conditions'])
    lines.append(f"| **{id_prefix}-{n}** | M4-7 pooled AUC by buffer (native samples removed vs buf0, trials affected) | {grid} |")
    n += 1
    lofo = summary['feature_ablation'][hb]['leave_one_out']
    order = sorted(lofo, key=lambda f: lofo[f]['delta_pooled_auc_vs_M4-7'])
    lines.append(
        f"| **{id_prefix}-{n}** | Leave-one-feature-out on M4-7 (ΔAUC vs full, ordered) | "
        + '; '.join(f"`{f}` {lofo[f]['delta_pooled_auc_vs_M4-7']:+.4f}" for f in order) + ' |')
    n += 1
    alone = summary['feature_ablation'][hb]['alone']
    order = sorted(alone, key=lambda f: -alone[f]['pooled_auc'])
    lines.append(
        f"| **{id_prefix}-{n}** | Single-feature LOSO AUC (ordered) | "
        + '; '.join(f"`{f}` {alone[f]['pooled_auc']:.4f}" for f in order) + ' |')
    n += 1
    q = lambda key: ' / '.join(f"{diag[key][k]:,.0f}" for k in ('min', 'q25', 'median', 'q75', 'max'))
    lines.extend([
        '',
        f"Timing (ms, min / Q1 / median / Q3 / max): last native mousemove → logged click {q('last_mousemove_to_click_ms_quantiles')}; "
        f"last native mousemove → {anchor} anchor {q('last_mousemove_to_anchor_ms_quantiles')}; "
        f"anchor → logged click {q('anchor_to_click_ms_quantiles')}. "
        f"Samples between anchor and logged click, excluded at every buffer: {diag['post_anchor_samples_excluded_at_every_buffer']:,}.",
        '',
        'Excluded-trial counts: ' + '; '.join(
            f'{k.replace("_", " ")}: {v:,}' for k, v in counts.items()
            if k not in ('discovered_trials', 'included')) + '.',
        '',
        'The paired differences are computed within participants; they are not differences of pooled AUCs. '
        'These click-prediction results do not validate relevance labels, a psychological interpretation, '
        'or a deployed browser model. The reader verifies current source files and AOI maps; recorded '
        'mouse/metadata and geometry hashes document the extraction inputs without re-reading private traces.',
    ])
    return '\n'.join(lines)
