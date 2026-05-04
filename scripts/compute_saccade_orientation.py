"""Saccade-orientation features on AdSERP — operationalizing Bhattacharya 2020.

Bhattacharya, Rokeby, Gwizdka & Kulgut (CHIIR 2020 / arXiv:2001.05152)
showed via Grad-CAM on scan-path-images that:
  - relevant docs → fixation density along right margin (continuous reading
    → line-end fixations stack horizontally)
  - irrelevant docs → fixation density at top + bottom (vertical scanning)

Their CNN learned this from raw 2D pattern. We operationalize the same
intuition as a *per-saccade orientation* feature on AdSERP, which they
didn't have access to. SERP-side translation:
  - horizontal saccade ≈ within-snippet reading
  - vertical saccade ≈ between-rank scanning

Per-saccade angle from horizontal axis: θ = atan2(|dy|, |dx|) ∈ [0, π/2].
  horizontal:  θ < 30°
  vertical:    θ > 60°
  oblique:     30° ≤ θ ≤ 60°

Microsaccade filter: skip pairs with magnitude < 10 px.

Outputs:
  AdSERP/data/saccade-orientation-by-position.json   (per-(trial, pos) cache)
  AdSERP/data/saccade-orientation-by-trial.json      (per-trial summary)
  scripts/output/saccade_orientation/summary.json    (empirical tests)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from data_loader import load_fixations, get_trial_ids, organic_aoi_tops, typed_aoi_tops  # noqa: E402
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
# pupil-lfhf provides the canonical position assignment matching NB14/NB18
from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_meta as pl_get_trial_meta,
    result_band_tops as pl_result_band_tops,
    count_results_html as pl_count_results,
    assign_fixation_to_position as pl_assign,
)

ENC_PATH = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
OUT_DIR = ROOT / 'scripts/output/saccade_orientation'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_paths(attribution: str) -> tuple[Path, Path, Path, str]:
    """Return (ripa2_path, by_pos_path, by_trial_path, suffix) for attribution."""
    if attribution == 'organic':
        return (
            ROOT / 'AdSERP/data/ripa2-by-position-organic.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-position-organic.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-trial-organic.json',
            '_organic',
        )
    if attribution == 'organic_hybrid':
        return (
            ROOT / 'AdSERP/data/ripa2-by-position-organic.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-position-organic-hybrid.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-trial-organic-hybrid.json',
            '_organic_hybrid',
        )
    if attribution == 'typed':
        return (
            ROOT / 'AdSERP/data/ripa2-by-position-typed.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-position-typed.json',
            ROOT / 'AdSERP/data/saccade-orientation-by-trial-typed.json',
            '_typed',
        )
    return (
        ROOT / 'AdSERP/data/ripa2-by-position.json',
        ROOT / 'AdSERP/data/saccade-orientation-by-position.json',
        ROOT / 'AdSERP/data/saccade-orientation-by-trial.json',
        '',
    )

# Thresholds
HORIZ_DEG = 30.0     # saccade is horizontal if angle from horiz ≤ 30°
VERT_DEG  = 60.0     # vertical if ≥ 60°
MIN_MAGNITUDE_PX = 10.0
HORIZ_RAD = math.radians(HORIZ_DEG)
VERT_RAD  = math.radians(VERT_DEG)


def classify_saccade(dx: float, dy: float) -> str | None:
    mag = math.hypot(dx, dy)
    if mag < MIN_MAGNITUDE_PX:
        return None
    theta = math.atan2(abs(dy), abs(dx))  # angle from horizontal
    if theta <= HORIZ_RAD:
        return 'h'
    if theta >= VERT_RAD:
        return 'v'
    return 'o'


def max_run(seq: list[str], target: str) -> int:
    best = cur = 0
    for c in seq:
        if c == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def trial_position_from_y(fix_y: float, tops, n_results: int) -> int | None:
    p = pl_assign(fix_y, tops, n_results)
    if p is None or p < 0 or p >= n_results:
        return None
    return int(p)


def features_from_classes(classes: list[str]) -> dict:
    n = len(classes)
    n_h = classes.count('h')
    n_v = classes.count('v')
    n_o = classes.count('o')
    return {
        'n_saccades': n,
        'n_horizontal': n_h,
        'n_vertical': n_v,
        'n_oblique': n_o,
        'frac_horizontal': n_h / n if n else 0.0,
        'ratio_h_to_v': n_h / n_v if n_v else (float('inf') if n_h else 0.0),
        'max_horizontal_run': max_run(classes, 'h'),
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--attribution', choices=['absolute', 'organic', 'organic_hybrid', 'typed'], default='organic',
                    help='organic (default; bbox-attributed) or absolute (legacy)')
    args = ap.parse_args()
    global RIPA2_PATH, OUT_BY_POS, OUT_BY_TRIAL, _OUT_SUFFIX
    RIPA2_PATH, OUT_BY_POS, OUT_BY_TRIAL, _OUT_SUFFIX = resolve_paths(args.attribution)
    print(f'[attribution] {args.attribution}', file=sys.stderr)
    print(f'  RIPA2 input  : {RIPA2_PATH.name}', file=sys.stderr)
    print(f'  by-pos out   : {OUT_BY_POS.name}', file=sys.stderr)
    print(f'  by-trial out : {OUT_BY_TRIAL.name}', file=sys.stderr)

    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    by_pos: dict[str, dict] = {}
    by_trial: dict[str, dict] = {}
    skipped_no_fix = 0
    skipped_no_meta = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        fix = load_fixations(tid)
        if not fix or len(fix) < 2:
            skipped_no_fix += 1
            continue
        # Position assignment context
        if args.attribution == 'organic':
            tops = organic_aoi_tops(tid)
        elif args.attribution == 'organic_hybrid':
            tops = _hybrid_aoi_tops(tid)
        elif args.attribution == 'typed':
            tops = typed_aoi_tops(tid)
            n_results = len(tops) if tops else 0
            if n_results == 0:
                tops = None
        else:
            n_results = pl_count_results(tid) or 11
            doc_h, _, _ = pl_get_trial_meta(tid)
            if doc_h is None:
                skipped_no_meta += 1
                tops = None
            else:
                tops = pl_result_band_tops(n_results, doc_h)

        # Walk consecutive pairs; classify each saccade and tag origin position
        trial_classes: list[str] = []
        per_pos_classes: dict[int, list[str]] = defaultdict(list)
        for a, b in zip(fix[:-1], fix[1:]):
            cls = classify_saccade(b['x'] - a['x'], b['y'] - a['y'])
            if cls is None:
                continue
            trial_classes.append(cls)
            if tops is not None:
                p = trial_position_from_y(a['y'], tops, n_results)
                if p is not None:
                    per_pos_classes[p].append(cls)

        # Per-trial features
        by_trial[tid] = features_from_classes(trial_classes)
        by_trial[tid]['pid'] = tid.split('-')[0]

        # Per-(trial, position) features
        positions = []
        for p, cls in per_pos_classes.items():
            entry = features_from_classes(cls)
            entry['pos'] = p
            positions.append(entry)
        positions.sort(key=lambda r: r['pos'])
        by_pos[tid] = {'positions': positions}

    print(f'  trials with features: {len(by_trial):,}  '
          f'(skipped {skipped_no_fix} no-fix, {skipped_no_meta} no-meta)',
          file=sys.stderr)

    # Save caches
    OUT_BY_TRIAL.write_text(json.dumps(by_trial, indent=2))
    OUT_BY_POS.write_text(json.dumps(by_pos, indent=2))
    print(f'[out] {OUT_BY_TRIAL.relative_to(ROOT)}  '
          f'{OUT_BY_POS.relative_to(ROOT)}', file=sys.stderr)

    # ── Summary stats ─────────────────────────────────────────────────
    n_h_total = sum(t['n_horizontal'] for t in by_trial.values())
    n_v_total = sum(t['n_vertical'] for t in by_trial.values())
    n_o_total = sum(t['n_oblique'] for t in by_trial.values())
    n_sac = n_h_total + n_v_total + n_o_total

    summary = {
        'cohort': {
            'n_trials': len(by_trial),
            'n_pids': len(set(t['pid'] for t in by_trial.values())),
            'n_saccades_total': n_sac,
        },
        'global_distribution': {
            'frac_horizontal': n_h_total / n_sac if n_sac else 0.0,
            'frac_vertical':   n_v_total / n_sac if n_sac else 0.0,
            'frac_oblique':    n_o_total / n_sac if n_sac else 0.0,
        },
        'tests': {},
    }
    print('\n=== Global saccade-orientation distribution ===')
    print(f'  n trials = {len(by_trial):,};  n saccades = {n_sac:,}')
    print(f'  horizontal = {n_h_total:,}  ({100*n_h_total/n_sac:.1f}%)')
    print(f'  vertical   = {n_v_total:,}  ({100*n_v_total/n_sac:.1f}%)')
    print(f'  oblique    = {n_o_total:,}  ({100*n_o_total/n_sac:.1f}%)')

    # ── Test 1: trial-level h:v ratio for trials WITH a click vs without ─
    enc = json.load(open(ENC_PATH))
    clicked_set = set()
    for tid, trial in enc.items():
        # 'click_pos' from ripa2 cache; load that separately
        pass
    # Cleanest: load from ripa2-by-position.json which has click_pos
    rcache = json.load(open(RIPA2_PATH))
    clicked_set = {tid for tid, t in rcache.items()
                   if t.get('click_pos') is not None}
    print(f'\n=== Test 1: trial h:v ratio × click outcome ===')
    print(f'  trials with click: {len(clicked_set & set(by_trial)):,}')
    h2v_clicked, h2v_unclicked = [], []
    for tid, t in by_trial.items():
        if t['n_vertical'] == 0:
            continue
        ratio = t['n_horizontal'] / t['n_vertical']
        if tid in clicked_set:
            h2v_clicked.append(ratio)
        else:
            h2v_unclicked.append(ratio)
    if len(h2v_clicked) >= 5 and len(h2v_unclicked) >= 5:
        u, p = mannwhitneyu(h2v_clicked, h2v_unclicked, alternative='two-sided')
        print(f'  clicked   median h:v = {np.median(h2v_clicked):.3f}  N = {len(h2v_clicked):,}')
        print(f'  unclicked median h:v = {np.median(h2v_unclicked):.3f}  N = {len(h2v_unclicked):,}')
        print(f'  Mann-Whitney U = {u:.0f}  p_two = {p:.3g}')
        summary['tests']['trial_ratio_clicked_vs_not'] = {
            'median_clicked': float(np.median(h2v_clicked)),
            'median_unclicked': float(np.median(h2v_unclicked)),
            'n_clicked': len(h2v_clicked),
            'n_unclicked': len(h2v_unclicked),
            'p_two_sided': float(p),
        }

    # ── Test 2: per-position h:v ratio at clicked vs non-clicked positions ─
    print('\n=== Test 2: per-position frac_horizontal at clicked vs non-clicked positions ===')
    # For each trial, position p: did the user click at p? Then compare
    clicked_hfrac, nonclicked_hfrac = [], []
    for tid, posdata in by_pos.items():
        click_pos = rcache.get(tid, {}).get('click_pos')
        if click_pos is None:
            continue
        for entry in posdata['positions']:
            if entry['n_saccades'] < 3:
                continue  # need a few saccades to compute frac
            if entry['pos'] == click_pos:
                clicked_hfrac.append(entry['frac_horizontal'])
            else:
                nonclicked_hfrac.append(entry['frac_horizontal'])
    if len(clicked_hfrac) >= 5 and len(nonclicked_hfrac) >= 5:
        u, p = mannwhitneyu(clicked_hfrac, nonclicked_hfrac, alternative='two-sided')
        print(f'  clicked-pos     frac_horiz median = {np.median(clicked_hfrac):.3f}  N = {len(clicked_hfrac):,}')
        print(f'  non-clicked-pos frac_horiz median = {np.median(nonclicked_hfrac):.3f}  N = {len(nonclicked_hfrac):,}')
        print(f'  Mann-Whitney p_two = {p:.3g}')
        summary['tests']['per_position_clicked_vs_not'] = {
            'median_clicked': float(np.median(clicked_hfrac)),
            'median_nonclicked': float(np.median(nonclicked_hfrac)),
            'n_clicked': len(clicked_hfrac),
            'n_nonclicked': len(nonclicked_hfrac),
            'p_two_sided': float(p),
        }

    # ── Test 3: will-regress vs no-regress: max_horizontal_run at the position ─
    print('\n=== Test 3: max_horizontal_run × will-regress (per-(trial, pos) using NB22 label) ===')
    # encoding-vs-retrieval.json has per-fix will_regress; aggregate to per-(trial, pos)
    # by taking ANY first-pass fix with will_regress=True at that pos
    wr_map: dict[tuple[str, int], bool] = {}
    for tid, trial in enc.items():
        for fix in trial.get('first_pass') or []:
            key = (tid, int(fix['pos']))
            wr_map[key] = wr_map.get(key, False) or bool(fix.get('will_regress'))
    wr_runs, nr_runs = [], []
    for tid, posdata in by_pos.items():
        for entry in posdata['positions']:
            key = (tid, entry['pos'])
            if key not in wr_map:
                continue
            if entry['n_saccades'] < 3:
                continue
            if wr_map[key]:
                wr_runs.append(entry['max_horizontal_run'])
            else:
                nr_runs.append(entry['max_horizontal_run'])
    if len(wr_runs) >= 5 and len(nr_runs) >= 5:
        u, p = mannwhitneyu(wr_runs, nr_runs, alternative='two-sided')
        print(f'  will-regress median run = {np.median(wr_runs):.2f}  N = {len(wr_runs):,}')
        print(f'  no-regress   median run = {np.median(nr_runs):.2f}  N = {len(nr_runs):,}')
        print(f'  Mann-Whitney p_two = {p:.3g}')
        summary['tests']['max_horizontal_run_wr_vs_nr'] = {
            'median_wr': float(np.median(wr_runs)),
            'median_nr': float(np.median(nr_runs)),
            'n_wr': len(wr_runs),
            'n_nr': len(nr_runs),
            'p_two_sided': float(p),
        }

    summary_path = OUT_DIR / f'summary{_OUT_SUFFIX}.json'
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {summary_path.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
