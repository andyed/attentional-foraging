"""STUB-G: Four-class taxonomy under organic_hybrid attribution.

Tests whether the deferred-vs-evaluated-rejected motor-signature
dissociation is etype-invariant (organic / dd_top / native_ad) or
organic-specific.

Inputs:
  AdSERP/data/cursor-approach-features-organic-hybrid.json (19,908 records)
  scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic_hybrid.json

Outputs:
  scripts/output/aoi-consumer-cascade/four_class_taxonomy_hybrid.json
  + stdout summary

Four-class rule (NB22 derivation):
  CLICKED:           was_clicked == True
  DEFERRED:          NOT clicked AND approached AND gaze_regression_label
  EVAL_REJECTED:     NOT clicked AND approached AND NOT gaze_regression_label
  NOT_APPROACHED:    NOT approached
  approached := min_dist < APPROACH_THRESHOLD_PX (100 px, NB22 convention)

Run:
  .venv/bin/python scripts/four_class_taxonomy_hybrid.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
APPROACH_THRESHOLD_PX = 100.0

FEAT_PATH = ROOT / 'AdSERP/data/cursor-approach-features-organic-hybrid.json'
LABELS_PATH = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic_hybrid.json'


def cohens_d(a, b):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    b = np.asarray(b, float); b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def main():
    print(f'[load] {FEAT_PATH.name} + {LABELS_PATH.name}', file=sys.stderr)
    records = json.load(open(FEAT_PATH))
    labels = json.load(open(LABELS_PATH))
    assert len(records) == len(labels), f'len mismatch: {len(records)} vs {len(labels)}'

    # Classify
    classes = []
    for r, will_regress in zip(records, labels):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        if clicked:
            cls = 'CLICKED'
        elif not approached:
            cls = 'NOT_APPROACHED'
        elif will_regress:
            cls = 'DEFERRED'
        else:
            cls = 'EVAL_REJECTED'
        classes.append(cls)

    # Per-etype × per-class counts
    print('\n=== Per-etype four-class distribution (n records / % of etype subset) ===')
    by_etype = defaultdict(lambda: defaultdict(int))
    by_etype_total = defaultdict(int)
    for r, cls in zip(records, classes):
        et = r.get('etype', 'organic')
        by_etype[et][cls] += 1
        by_etype_total[et] += 1

    print(f'\n{"etype":12s} {"N":>7s} {"CLK":>10s} {"DEF":>10s} {"REJ":>10s} {"NA":>10s}')
    out_dist = {}
    for et in ['organic', 'dd_top', 'native_ad']:
        if et not in by_etype: continue
        n = by_etype_total[et]
        row = by_etype[et]
        clk = row.get('CLICKED', 0)
        defc = row.get('DEFERRED', 0)
        rej = row.get('EVAL_REJECTED', 0)
        na = row.get('NOT_APPROACHED', 0)
        print(f'{et:12s} {n:>7,} '
              f'{clk:>5,} ({100*clk/n:>4.1f}%) '
              f'{defc:>5,} ({100*defc/n:>4.1f}%) '
              f'{rej:>5,} ({100*rej/n:>4.1f}%) '
              f'{na:>5,} ({100*na/n:>4.1f}%)')
        out_dist[et] = {
            'n': n,
            'clicked': clk, 'clicked_pct': 100 * clk / n,
            'deferred': defc, 'deferred_pct': 100 * defc / n,
            'eval_rejected': rej, 'eval_rejected_pct': 100 * rej / n,
            'not_approached': na, 'not_approached_pct': 100 * na / n,
        }

    # ── Per-etype motor-signature dissociation: DEFERRED vs EVAL_REJECTED ──
    print('\n=== Per-etype DEFERRED vs EVAL_REJECTED motor-signature dissociation ===')
    metrics = [
        ('retreat_dist', 'post-closest drift (px)'),
        ('dwell_in_proximity_ms', 'dwell in proximity (ms)'),
        ('total_dwell_ms', 'total dwell (ms)'),
        ('mean_dist', 'mean cursor-AOI distance (px)'),
        ('final_dist', 'final cursor-AOI distance (px)'),
        ('direction_changes', 'direction changes'),
        ('frac_decreasing', 'frac decreasing'),
    ]

    def mw_block(records_subset, classes_subset, et_label):
        """Return rows for a single etype subset."""
        deferred_recs = [r for r, c in zip(records_subset, classes_subset) if c == 'DEFERRED']
        eval_rej_recs = [r for r, c in zip(records_subset, classes_subset) if c == 'EVAL_REJECTED']
        n_def = len(deferred_recs)
        n_rej = len(eval_rej_recs)
        rows = []
        for m, label in metrics:
            d_vals = [float(r.get(m, np.nan) or np.nan) for r in deferred_recs]
            r_vals = [float(r.get(m, np.nan) or np.nan) for r in eval_rej_recs]
            d_arr = np.array(d_vals); d_arr = d_arr[np.isfinite(d_arr)]
            r_arr = np.array(r_vals); r_arr = r_arr[np.isfinite(r_arr)]
            if len(d_arr) < 10 or len(r_arr) < 10:
                rows.append({
                    'metric': m, 'n_def': len(d_arr), 'n_rej': len(r_arr),
                    'mw_p': None, 'd': None, 'med_def': None, 'med_rej': None,
                })
                continue
            u, p = stats.mannwhitneyu(d_arr, r_arr, alternative='two-sided')
            d_eff = cohens_d(d_arr, r_arr)
            rows.append({
                'metric': m, 'label': label,
                'n_def': len(d_arr), 'n_rej': len(r_arr),
                'med_def': float(np.median(d_arr)),
                'med_rej': float(np.median(r_arr)),
                'mean_def': float(d_arr.mean()),
                'mean_rej': float(r_arr.mean()),
                'mw_p': float(p), 'd': float(d_eff),
            })
        return rows, n_def, n_rej

    # Print + collect
    out_dissociation = {}
    for et in ['organic', 'dd_top', 'native_ad']:
        et_records = [r for r in records if r.get('etype', 'organic') == et]
        et_classes = [classes[i] for i, r in enumerate(records) if r.get('etype', 'organic') == et]
        rows, n_def, n_rej = mw_block(et_records, et_classes, et)
        print(f'\n--- {et} (DEF n={n_def:,}, REJ n={n_rej:,}) ---')
        if n_def < 10 or n_rej < 10:
            print(f'  [insufficient n]')
            continue
        print(f'  {"metric":24s} {"med DEF":>10s} {"med REJ":>10s} {"d":>7s} {"p (MW)":>10s}')
        for row in rows:
            if row['mw_p'] is None:
                continue
            sig = '***' if row['mw_p'] < 1e-3 else ('**' if row['mw_p'] < 0.01 else ('*' if row['mw_p'] < 0.05 else ''))
            print(f'  {row["metric"]:24s} {row["med_def"]:>10.2f} {row["med_rej"]:>10.2f} '
                  f'{row["d"]:>+7.3f} {row["mw_p"]:>10.3e} {sig}')
        out_dissociation[et] = {'n_def': n_def, 'n_rej': n_rej, 'rows': rows}

    # ── Cross-etype comparison: is the dissociation invariant? ──
    print('\n=== Cross-etype dissociation comparison (Cohen\'s d on retreat_dist + dwell) ===')
    print('Effect-size invariance check: do the d values agree across etypes?')
    for m_name in ['retreat_dist', 'dwell_in_proximity_ms', 'total_dwell_ms']:
        d_vals = []
        for et in ['organic', 'dd_top', 'native_ad']:
            if et in out_dissociation:
                row = next((r for r in out_dissociation[et]['rows'] if r['metric'] == m_name), None)
                if row and row['d'] is not None:
                    d_vals.append((et, row['d']))
        if len(d_vals) > 1:
            print(f'  {m_name:24s}: ' +
                  '  '.join(f'{et}: d={d:+.3f}' for et, d in d_vals))

    # Save
    out = {
        'attribution': 'organic_hybrid',
        'n_records': len(records),
        'approach_threshold_px': APPROACH_THRESHOLD_PX,
        'distribution_by_etype': out_dist,
        'dissociation_by_etype': out_dissociation,
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/four_class_taxonomy_hybrid.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
