"""
add_etype_to_features.py — adds `etype` column to cursor-approach-features.json
and writes cursor-approach-features-typed.json.

Typing rule mirrors NB24 cell 3 (classify_position): a result position's
etype is determined by which ad-boundary rect (if any) overlaps the result
column at that position's vertical band. Positions with no ad overlap are
labeled `organic`. `dd_right` (right-rail ads) is excluded because it is
not a result position.

NOTE ON DRIFT: The prior `cursor-approach-features-typed.json` was built
by an untracked script using a different heuristic (likely classifying by
first-fixation (x, y) against ANY ad rect, as in NB16's `classify_fixation`).
This regenerator uses NB24's position-based rule instead, which is canonical
with the retreat-arc analysis. As a result, ~11.3% of records receive a
different etype label than the prior file — primarily `native_ad` ↔ `organic`
swaps. This is a correction, not a regression: NB20 and NB24 now share a
single typing definition.

Run after NB15 regenerates the base feature JSON.
"""

import json
import sys
from bisect import bisect_right
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (
    DATA_DIR,
    get_trial_meta,
    extract_serp_results,
    result_band_tops,
)

AD_DIR = DATA_DIR / 'ad-boundary-data'
RESULT_COL_X_MIN = 162
RESULT_COL_X_MAX = 702
BASE_PATH = DATA_DIR / 'cursor-approach-features.json'
TYPED_PATH = DATA_DIR / 'cursor-approach-features-typed.json'


def load_ad_regions(trial_id):
    path = AD_DIR / f'{trial_id}.json'
    if not path.exists():
        return {}
    d = json.load(open(path))
    out = {}
    for etype, elements in d.items():
        rects = []
        for el in elements:
            loc = el.get('location', {})
            size = el.get('size', {})
            rects.append((loc.get('x', 0), loc.get('y', 0),
                          size.get('width', 0), size.get('height', 0)))
        if rects:
            out[etype] = rects
    return out


def rect_in_result_column(rx, rw):
    return rx < RESULT_COL_X_MAX and (rx + rw) > RESULT_COL_X_MIN


def classify_position(pos_top, pos_bottom, ad_regions):
    pos_cy = (pos_top + pos_bottom) / 2
    for etype, rects in ad_regions.items():
        if etype == 'dd_right':
            continue
        for rx, ry, rw, rh in rects:
            if not rect_in_result_column(rx, rw):
                continue
            if ry <= pos_cy <= ry + rh:
                return etype
    return 'organic'


def main():
    with open(BASE_PATH) as f:
        records = json.load(f)
    print(f'Loaded {len(records):,} base records from {BASE_PATH.name}')

    # Cache per-trial etype lookups: trial_id -> {pos: etype}
    trial_etypes = {}
    n_unknown = 0

    for r in records:
        tid = r['trial_id']
        pos = r['position']
        if tid not in trial_etypes:
            meta = get_trial_meta(tid)
            if meta is None or meta[0] is None:
                trial_etypes[tid] = None
            else:
                doc_h, _scr_h, _ts = meta
                serp = extract_serp_results(tid)
                n_results = len(serp) if serp else 10
                if n_results == 0:
                    trial_etypes[tid] = None
                else:
                    tops = result_band_tops(n_results, doc_h)
                    bottoms = tops[1:] + [doc_h - 200]
                    ad_regions = load_ad_regions(tid)
                    trial_etypes[tid] = {
                        p: classify_position(tops[p], bottoms[p], ad_regions)
                        for p in range(n_results)
                    }
        pos_map = trial_etypes[tid]
        if pos_map is None or pos not in pos_map:
            r['etype'] = 'unknown'
            n_unknown += 1
        else:
            r['etype'] = pos_map[pos]

    with open(TYPED_PATH, 'w') as f:
        json.dump(records, f)
    print(f'Wrote {len(records):,} typed records to {TYPED_PATH.name}')

    from collections import Counter
    counts = Counter(r['etype'] for r in records)
    print(f'Etype distribution: {dict(counts)}')
    if n_unknown:
        print(f'Unknown: {n_unknown}')


if __name__ == '__main__':
    main()
