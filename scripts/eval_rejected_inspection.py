"""Compile EVAL_REJECTED records under the typed cascade for human inspection.

The four-class taxonomy classifies each (trial, position) record as:
  CLICKED, DEFERRED, EVAL_REJECTED, NOT_APPROACHED.

EVAL_REJECTED = approached AND no gaze regression AND not clicked.
The behavioral interpretation: the user moved cursor close, looked at the
result, and decided not to click — explicitly rejected after evaluation.

This script:
  1. Computes the four-class distribution under typed cascade (n=19,774).
  2. Compares per-etype counts to four_class_taxonomy_hybrid baseline.
  3. Builds a CSV of (trial_id, query, position, etype, title, snippet,
     min_dist, dwell_ms) for every EVAL_REJECTED record — for relevance
     labeling.
  4. Writes a markdown sample (300 records, stratified by etype × position)
     for quick visual inspection.

Outputs:
  scripts/output/eval_rejected_inspection/
      summary.json                       — distribution stats
      eval_rejected_typed.csv             — full set, all etypes
      eval_rejected_organic_typed.csv     — organic-only subset
      eval_rejected_sample.md             — 300-record stratified sample

Run:
  .venv/bin/python scripts/eval_rejected_inspection.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import extract_serp_results  # noqa: E402

FEAT = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
REG_CACHE = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
META_DIR = ROOT / 'AdSERP/data/trial-metadata'
OUT = ROOT / 'scripts/output/eval_rejected_inspection'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0


def get_query(trial_id):
    p = META_DIR / f'{trial_id}.xml'
    if not p.exists():
        return None
    text = p.read_text(encoding='utf-8', errors='ignore')
    m = re.search(r'<url>([^<]+)</url>', text)
    if not m:
        return None
    try:
        parsed = urlparse(m.group(1))
        q = parse_qs(parsed.query).get('q', [''])[0]
    except Exception:
        return None
    return unquote(q).replace('-', ' ')


def main():
    print('[load] cursor-approach-features-typed + regression-labels-typed', file=sys.stderr)
    records = json.load(open(FEAT))
    regr_labels = json.load(open(REG_CACHE))
    assert len(records) == len(regr_labels)

    # Classify
    classes = []
    for r, will_regress in zip(records, regr_labels):
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

    # Distribution by etype × class
    by_etype = defaultdict(lambda: Counter())
    by_etype_total = Counter()
    for r, cls in zip(records, classes):
        et = r.get('etype', 'unknown')
        by_etype[et][cls] += 1
        by_etype_total[et] += 1

    # Print four-class distribution under typed
    print('\n=== Four-class distribution (typed cascade, n=19,774) ===', file=sys.stderr)
    print(f'{"etype":16s} {"N":>7s} {"CLK":>14s} {"DEF":>14s} {"REJ":>14s} {"NA":>14s}', file=sys.stderr)
    out_dist = {}
    for et in sorted(by_etype, key=lambda e: -by_etype_total[e]):
        n = by_etype_total[et]
        row = by_etype[et]
        clk = row['CLICKED']
        defc = row['DEFERRED']
        rej = row['EVAL_REJECTED']
        na = row['NOT_APPROACHED']
        print(f'{et:16s} {n:>7,} '
              f'{clk:>5,} ({100*clk/n:>4.1f}%) '
              f'{defc:>5,} ({100*defc/n:>4.1f}%) '
              f'{rej:>5,} ({100*rej/n:>4.1f}%) '
              f'{na:>5,} ({100*na/n:>4.1f}%)', file=sys.stderr)
        out_dist[et] = {
            'n': n,
            'CLICKED': clk, 'DEFERRED': defc,
            'EVAL_REJECTED': rej, 'NOT_APPROACHED': na,
            'pct': {'CLICKED': 100*clk/n, 'DEFERRED': 100*defc/n,
                    'EVAL_REJECTED': 100*rej/n, 'NOT_APPROACHED': 100*na/n},
        }

    # Total EVAL_REJECTED
    n_rej = sum(by_etype[e]['EVAL_REJECTED'] for e in by_etype)
    n_total = sum(by_etype_total.values())
    print(f'\nTotal EVAL_REJECTED: {n_rej:,} of {n_total:,} ({100*n_rej/n_total:.1f}%)', file=sys.stderr)

    # ── EVAL_REJECTED records: join with query + title + snippet ──
    print('\n[build] joining query + SERP HTML for every EVAL_REJECTED record...',
          file=sys.stderr)

    # Cache trial-level data once per trial
    trial_query = {}
    trial_serp = {}

    rows_full = []
    skipped_no_query = 0
    skipped_no_serp = 0
    skipped_no_match = 0

    for r, cls in zip(records, classes):
        if cls != 'EVAL_REJECTED':
            continue
        tid = r['trial_id']
        pos = int(r['position'])
        # Query
        if tid not in trial_query:
            trial_query[tid] = get_query(tid) or ''
        q = trial_query[tid]
        if not q:
            skipped_no_query += 1
            continue
        # SERP
        if tid not in trial_serp:
            try:
                trial_serp[tid] = extract_serp_results(tid)
            except Exception:
                trial_serp[tid] = None
        serp = trial_serp[tid]
        if not serp:
            skipped_no_serp += 1
            continue
        if pos >= len(serp):
            skipped_no_match += 1
            continue
        sr = serp[pos]
        title = sr.get('title', '')
        snippet = sr.get('snippet', '')
        rows_full.append({
            'trial_id':   tid,
            'participant': tid.split('-')[0],
            'position':   pos,
            'etype':      r.get('etype', 'unknown'),
            'click_pos':  r.get('click_pos'),
            'min_dist':   round(float(r.get('min_dist', 0) or 0), 1),
            'mean_dist':  round(float(r.get('mean_dist', 0) or 0), 1),
            'final_dist': round(float(r.get('final_dist', 0) or 0), 1),
            'total_dwell_ms': int(r.get('total_dwell_ms', 0) or 0),
            'dwell_in_proximity_ms': int(r.get('dwell_in_proximity_ms', 0) or 0),
            'n_fixations': int(r.get('n_fixations', 0) or 0),
            'query':      q,
            'title':      title,
            'snippet':    snippet[:500],  # truncate runaway snippets
        })

    print(f'  joined {len(rows_full):,} EVAL_REJECTED records', file=sys.stderr)
    print(f'  skipped: no_query={skipped_no_query}  no_serp={skipped_no_serp}  '
          f'no_serp_match_at_position={skipped_no_match}', file=sys.stderr)

    # ── Write full CSV ──
    fieldnames = list(rows_full[0].keys())
    with open(OUT / 'eval_rejected_typed.csv', 'w', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_full)
    print(f'wrote {OUT / "eval_rejected_typed.csv"}  ({len(rows_full):,} rows)',
          file=sys.stderr)

    # ── Organic-only CSV ──
    rows_organic = [r for r in rows_full if r['etype'] == 'organic']
    with open(OUT / 'eval_rejected_organic_typed.csv', 'w', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_organic)
    print(f'wrote {OUT / "eval_rejected_organic_typed.csv"}  ({len(rows_organic):,} rows)',
          file=sys.stderr)

    # ── Stratified sample for quick markdown inspection ──
    # Stratify by etype × position; cap each cell at ceil(target / n_cells) records.
    rng = np.random.default_rng(0xCAFE)
    target_n = 300
    cells = defaultdict(list)
    for row in rows_full:
        cells[(row['etype'], row['position'])].append(row)
    n_cells = len(cells)
    per_cell = max(1, target_n // n_cells)
    sample = []
    for k, vals in sorted(cells.items()):
        rng.shuffle(vals)
        sample.extend(vals[:per_cell])
    sample = sample[:target_n]
    print(f'  stratified sample: {len(sample)} records across {n_cells} cells '
          f'(~{per_cell}/cell)', file=sys.stderr)

    # Write markdown sample
    md = ['# EVAL_REJECTED inspection sample',
          '',
          f'Stratified across etype × position. {len(sample)} of {len(rows_full):,} total '
          f'EVAL_REJECTED records under the typed cascade.',
          '',
          '**Behavioral definition:** user moved cursor within 100 px of AOI '
          '(approached), no gaze regression to revisit, no click. Interpretable as '
          '"evaluated and rejected."',
          '',
          '## How to read each row',
          '- `query` — the search query',
          '- `position` — 0-indexed rank within trial',
          '- `etype` — AOI type (organic / dd_top / native_ad / image_pack / ...)',
          '- `min_dist` — px between cursor and AOI at closest approach',
          '- `dwell_ms` — total time within 100 px proximity',
          '- `title` / `snippet` — what the user saw',
          '',
          '---',
          '']
    cur_etype = None
    cur_pos = None
    for r in sample:
        if (r['etype'], r['position']) != (cur_etype, cur_pos):
            cur_etype, cur_pos = r['etype'], r['position']
            md.append(f'\n## etype = `{cur_etype}`, position = {cur_pos}\n')
        md.append(f"### `{r['trial_id']}` — query: *{r['query']}*")
        md.append(f"**{r['title']}**")
        md.append(f"> {r['snippet']}")
        md.append(f"<sub>min_dist = {r['min_dist']:.1f} px, "
                  f"dwell_in_proximity = {r['dwell_in_proximity_ms']} ms, "
                  f"n_fixations = {r['n_fixations']}, click_pos = {r['click_pos']}</sub>")
        md.append('')
    (OUT / 'eval_rejected_sample.md').write_text('\n'.join(md))
    print(f'wrote {OUT / "eval_rejected_sample.md"}', file=sys.stderr)

    # ── Summary JSON ──
    summary = {
        'attribution': 'typed',
        'n_records': n_total,
        'approach_threshold_px': APPROACH_THRESHOLD_PX,
        'distribution_by_etype': out_dist,
        'eval_rejected_total': n_rej,
        'eval_rejected_pct': 100 * n_rej / n_total,
        'eval_rejected_joined': len(rows_full),
        'eval_rejected_organic_joined': len(rows_organic),
        'sample_size': len(sample),
        'skipped': {
            'no_query': skipped_no_query,
            'no_serp': skipped_no_serp,
            'no_serp_match_at_position': skipped_no_match,
        },
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'wrote {OUT / "summary.json"}', file=sys.stderr)


if __name__ == '__main__':
    main()
