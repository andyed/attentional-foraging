"""Page-grain reductions scored at their SOURCE's grain and target.

reduction_baselines.py scores every prior measurement at CANDIDATE grain (one
row per result). Two of its baselines are page-grain BY CONSTRUCTION —
B1 `total_mouse_length` (Brückner 2021) and B4 the session battery
(Arapakis-style) — so broadcast to candidates they are constant within a trial
and score 0.500 within-trial. That number demonstrates the structural point;
it says nothing about whether the projection is FAITHFUL to its source. The
sources predicted per-session (per-page) outcomes. This producer scores the
same two projections — the SAME numbers, computed by the same
`trial_stream` / `globals_for` the candidate-grain harness uses, just not
broadcast — with one row per TRIAL against trial-level targets chosen to
match the sources' own targets.

Source -> target mapping (from approach-retreat/docs/references lit-notes;
quoted lines are stamped into the output under `source_target_mapping`):

  Brückner, Arapakis & Leiva 2021 (B1). Unit: session (one SERP encounter on
    the Attentive Cursor Dataset). Targets: ad noticeability (self-report
    Likert), result-page abandonment (any click), frustration; the headline
    number is "AUC ~0.69 on the ad-clicked target on the native-ad subset".
    On AdSERP: `ad_clicked` (final click on a native_ad card; pool = trials
    that show >= 1 native_ad) is the direct analog. Abandonment is NOT
    computable (every AdSERP trial ends in a click). No self-report exists.
  Arapakis & Leiva 2016 (B4). Unit: session. Targets: attention ("Did you
    notice the Knowledge Module?", binary self-report), usefulness,
    perceived speed (Likert). On AdSERP: `ad_noticed` — any fixation inside a
    native_ad card — is a GAZE-DEFINED PROXY for the self-report; the
    direct-display analog is the native ad, not a KM. Usefulness / perceived
    speed have no analog.
  Leiva & Arapakis 2020 (dataset). Ground truth = click behaviour (binary) +
    self-reported attention (1-5). Same two analogs as above.
  Huang, White & Buscher 2012. Target is gaze POSITION (RMSE) at sample
    grain; there is no page-grain target and the projection is not scored.

Targets with no source analog, reported because the brief named them:
  `clicked_rank` (position of the final click) and `total_gaze_dwell_ms`
  (sum of fixation durations) — descriptive Spearman only, no model.

Protocol: LOSO-by-participant logistic regression (m4_cursor_only_downstream
.loso_proba / summarize), pooled AUC + fold mean±sd, 100-permutation
within-participant label null per (target, model). One pool per target; every
model in a table is fit on the same trials. Features are cursor-only; gaze
defines `ad_noticed` and `total_gaze_dwell_ms` only (targets, never features).

Run from attentional-foraging:
  .venv/bin/python scripts/page_grain_faithfulness.py
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
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from m4_cursor_aoi_rerun import main_cards, load_flavor_cards  # noqa: E402
from m4_cursor_only_downstream import loso_proba, summarize, sha256, rel  # noqa: E402
from reduction_baselines import (  # noqa: E402
    trial_stream, globals_for, B1, B4, BUFFER_MS, IDLE_GAP_MS,
)
from deferred_dwell_carve import perm_null  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'page_grain_faithfulness'
LIT_DIR = Path('/Users/andyed/Documents/dev/approach-retreat/docs/references')
AD_TYPE = 'native_ad'

# Layout priors: what the page showed, independent of any cursor sample. On
# an ad target, whether and where ads were shown is the analog of the rank
# prior (B5) on the click target — the thing a cursor model must beat.
PRIOR_AD = ['n_results', 'n_ads', 'first_ad_position']
PRIOR_RANK = ['n_results']

# Verbatim lines from the lit-notes, so the mapping is auditable against the
# note rather than against memory.
SOURCE_TARGET_MAPPING = [
    {'source': 'Brückner, Arapakis & Leiva 2021 (SIGIR)',
     'lit_note': 'bruckner-2021-systematic.md',
     'baseline': 'B1 total_mouse_length',
     'unit_of_analysis': 'session (one SERP encounter, Attentive Cursor Dataset)',
     'source_targets': ['ad noticeability (self-report Likert)',
                        'result-page abandonment (any click)',
                        'frustration (composite self-report)',
                        'ad-clicked (native-ad subset; the quoted AUC)'],
     'source_features': 'total mouse movement length (scalar); BiLSTM over (x,y,t)',
     'source_effect': 'AUC ~0.69 (reproduced 0.696 ± 0.031; 0.653 ± 0.031 under 500 ms click-buffer)',
     'quotes': [
         'The headline cursor primitive is **total mouse movement length** (a scalar that sums the per-step Euclidean displacement across the session).',
         "The Brückner paper's primitive is *per-session*: total mouse path summed across the whole encounter.",
         '**Mouse-length scalar baseline reaches AUC ~0.69** on the ad-clicked target on the native-ad subset.',
         '2. **Result-page abandonment** — did the user click any result on the SERP?'],
     'adserp_target': 'ad_clicked',
     'adserp_target_status': 'direct analog: final click lands on a native_ad card; pool = trials showing >= 1 native_ad',
     'not_computable': ['abandonment (every AdSERP trial ends in a click)',
                        'noticeability / frustration self-report (AdSERP has no questionnaire)']},
    {'source': 'Arapakis & Leiva 2016 (SIGIR)',
     'lit_note': 'arapakis-leiva-2016.md',
     'baseline': 'B4 page-grain session battery',
     'unit_of_analysis': 'session (300 sessions, 638 features per session)',
     'source_targets': ['attention: "Did you notice the Knowledge Module?" (binary)',
                        'usefulness (1-5 Likert)', 'perceived speed (1-5 Likert)'],
     'source_features': '638 per-session cursor features (RF); top = distance to KM reference points, hover ratio, entropy, SD of speed',
     'source_effect': 'AUC 0.86 attention, 0.71 usefulness, 0.77 perceived speed (RF, 10-fold CV)',
     'quotes': [
         '1. **Attention** — "Did you notice the Knowledge Module?" (binary)',
         '| Attention | **0.86** | 0.76 | 0.68 (all baselines) |',
         '| Features extracted | 638 per session |'],
     'adserp_target': 'ad_noticed',
     'adserp_target_status': 'PROXY (gaze-defined): any fixation strictly inside a native_ad card; stands in for the self-report attention question; direct display = native ad, not KM',
     'not_computable': ['usefulness', 'perceived speed (no questionnaire)']},
    {'source': 'Leiva & Arapakis 2020 (Frontiers; Attentive Cursor Dataset)',
     'lit_note': 'leiva-arapakis-2020.md',
     'baseline': 'substrate for B1 and B4',
     'unit_of_analysis': 'session (one log per participant)',
     'source_targets': ['click behaviour (binary)', 'self-reported attention (1-5 Likert)'],
     'source_features': 'raw cursor log (dataset paper; no model of its own)',
     'source_effect': 'none reported in the note',
     'quotes': [
         '- **`groundtruth.tsv`** — User ID, click behavior (binary), self-reported attention (1-5 Likert), log ID.'],
     'adserp_target': 'ad_clicked (click behaviour); ad_noticed (attention proxy)',
     'adserp_target_status': 'same two analogs as the papers built on it',
     'not_computable': []},
    {'source': 'Huang, White & Buscher 2012 (CHI)',
     'lit_note': 'huang-white-buscher-2012.md',
     'baseline': 'none of the page-grain baselines (B2 is Huang 2011 hover; candidate grain)',
     'unit_of_analysis': 'cursor/gaze sample pairs within query sessions',
     'source_targets': ['gaze position (RMSE, px)'],
     'source_features': 'cursor position, behaviour class, log(dwell), future cursor',
     'source_effect': 'RMSE 236.6 px cursor-only -> 186.3 px with behaviour + dwell',
     'quotes': [
         '| Cursor alone (baseline) | 236.6 px |',
         'Their top predictive feature is `log(dwell_time)`'],
     'adserp_target': None,
     'adserp_target_status': 'no page-grain target exists; not scored here',
     'not_computable': ['gaze RMSE is sample-grain, not a trial outcome']},
]


def fixations_in_ads(fixations, ad_cards):
    """Strict 2-D box containment of fixations in native_ad cards.

    Fixations are screenshot space per the AdSERP README ("relative to the
    top-left corner of the screenshot"); the typed cards are screenshot space
    too, so no ratio is applied — the same rule adsight_noticed_features.py
    uses. Y-band assignment (typed_aoi_tops) would credit a fixation in the
    right rail to an ad row; the box rule does not.
    """
    n, dwell = 0, 0.0
    for f in fixations:
        x, y, d = f['x'], f['y'], f['d']
        if not all(math.isfinite(v) for v in (x, y, d)):
            continue
        for c in ad_cards:
            if c['x'] <= x <= c['x'] + c['width'] and c['y'] <= y <= c['y'] + c['height']:
                n += 1
                dwell += d
                break
    return n, dwell


def trial_record(tid, click_row, dl, flavor):
    """One trial-grain row, or (None, reason). Cursor features come from the
    exact stream/battery functions the candidate-grain harness uses."""
    try:
        cards = main_cards(load_flavor_cards(dl, tid, flavor))
    except Exception:
        return None, 'cards'
    if len(cards) < 2:
        return None, 'cards'          # same gate as reduction_baselines
    st = trial_stream(tid, cards, dl)
    if st is None:
        return None, 'stream'
    samples, n_scroll = st
    g = globals_for(samples, n_scroll)
    ads = [c for c in cards if c['type'] == AD_TYPE]
    rec = dict(g)
    rec.update({
        'trial_id': tid,
        'n_results': float(len(cards)),
        'n_ads': float(len(ads)),
        # No ad shown -> sentinel one past the last slot, so "later than any
        # result" rather than a NaN the scaler cannot take.
        'first_ad_position': float(min(c['position'] for c in ads)) if ads else float(len(cards)),
        'clicked_position': int(click_row['position']),
        'clicked_etype': click_row['etype'],
        'ad_clicked': int(click_row['etype'] == AD_TYPE),
    })
    try:
        fx = dl.load_fixations(tid)
    except Exception:
        fx = None
    if fx:
        n_ad_fix, ad_dwell = fixations_in_ads(fx, ads)
        rec.update({'has_gaze': True, 'n_fixations': len(fx),
                    'total_gaze_dwell_ms': float(sum(f['d'] for f in fx if math.isfinite(f['d']))),
                    'n_ad_fixations': int(n_ad_fix), 'ad_gaze_dwell_ms': float(ad_dwell),
                    'ad_noticed': int(n_ad_fix > 0)})
    else:
        rec.update({'has_gaze': False, 'n_fixations': 0, 'total_gaze_dwell_ms': float('nan'),
                    'n_ad_fixations': 0, 'ad_gaze_dwell_ms': float('nan'), 'ad_noticed': -1})
    return rec, 'included'


def univariate_auc(x, y, pid, pool):
    """Fit-free AUC of one raw scalar — Brückner's baseline is a threshold on
    total mouse length, so the projection's direction must be readable
    without a classifier standing between the feature and the target.
    AUC > 0.5 means the positive class moves the cursor MORE."""
    from sklearn.metrics import roc_auc_score
    sel = pool & np.isfinite(x)
    if len(set(y[sel])) < 2:
        return {'skipped': 'pool has one class'}
    per = []
    for q in np.unique(pid[sel]):
        s = sel & (pid == q)
        if len(set(y[s])) == 2:
            per.append(float(roc_auc_score(y[s], x[s])))
    per = np.asarray(per)
    return {'pooled_auc': float(roc_auc_score(y[sel], x[sel])), 'n_records': int(sel.sum()),
            'per_participant_auc_mean': float(per.mean()) if len(per) else float('nan'),
            'per_participant_auc_sd': float(per.std(ddof=1)) if len(per) > 1 else float('nan'),
            'n_participants_with_both_classes': int(len(per))}


def score_table(rows, y, pool, pid, models, n_perm):
    """Every model on the same pool; null per model on the same pool."""
    out = {}
    for name, feats in models:
        if pool.sum() == 0 or len(set(y[pool])) < 2:
            out[name] = {'skipped': 'pool has one class'}
            continue
        pr, _ = loso_proba(rows, feats, y, pool)
        sc, _ = summarize(y, pr, pid, pool)
        sc['features'] = feats
        if n_perm > 0:
            sc['label_null'] = perm_null(rows, feats, y, pool, pid, n=n_perm)
        out[name] = sc
    return out


def spearman_block(x, t, pid, mask):
    """Pooled Spearman plus the per-participant distribution, so a pooled rho
    driven by between-participant offsets is visible as such."""
    sel = mask & np.isfinite(x) & np.isfinite(t)
    if sel.sum() < 3:
        return {'n': int(sel.sum()), 'rho': float('nan'), 'p': float('nan')}
    rho, p = spearmanr(x[sel], t[sel])
    per = []
    for q in np.unique(pid[sel]):
        s = sel & (pid == q)
        if s.sum() >= 5 and len(np.unique(t[s])) > 1 and len(np.unique(x[s])) > 1:
            r, _ = spearmanr(x[s], t[s])
            if np.isfinite(r):
                per.append(float(r))
    per = np.asarray(per)
    return {'n': int(sel.sum()), 'rho': float(rho), 'p': float(p),
            'per_participant_rho_mean': float(per.mean()) if len(per) else float('nan'),
            'per_participant_rho_sd': float(per.std(ddof=1)) if len(per) > 1 else float('nan'),
            'n_participants': int(len(per))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--candidate-grain', type=Path,
                    default=ROOT / 'scripts/output/reduction_baselines/summary.json')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--flavor', default='typed')
    ap.add_argument('--below-k', type=int, default=3,
                    help='clicked_below_k = clicked_position >= k (0-based)')
    ap.add_argument('--perms', type=int, default=100)
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    args = ap.parse_args()
    if args.buffer != int(BUFFER_MS):
        # trial_stream hard-codes reduction_baselines.BUFFER_MS; a different
        # cache buffer would pair features and rows from different protocols.
        raise ValueError(f'trial_stream uses BUFFER_MS={BUFFER_MS}; --buffer must match')

    import data_loader as dl

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar_path = ROOT / 'scripts/output' / args.summary_dir / 'summary.json'
    sidecar = json.loads(sidecar_path.read_text())
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match its aggregate sidecar')
    click_rows = {}
    for r in stored:
        if r['was_clicked']:
            if r['trial_id'] in click_rows:
                raise ValueError(f"{r['trial_id']}: more than one clicked row")
            click_rows[r['trial_id']] = r
    tids = sorted({r['trial_id'] for r in stored})
    missing = [t for t in tids if t not in click_rows]
    if missing:
        raise ValueError(f'{len(missing)} trials have no clicked row')
    print(f'cache: {len(stored):,} candidate rows over {len(tids):,} trials')

    rows, skipped = [], Counter()
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  {i}/{len(tids)}', flush=True)
        rec, why = trial_record(tid, click_rows[tid], dl, args.flavor)
        if rec is None:
            skipped[why] += 1
            continue
        rows.append(rec)
    print(f'  trial rows {len(rows):,}; skipped {dict(skipped)}')

    # The trial-grain B1 must be the number the candidate harness broadcasts:
    # same function, so identity is expected — assert rather than assume.
    if any(r['total_mouse_length'] != r['g_path_length'] for r in rows):
        raise AssertionError('total_mouse_length diverged from g_path_length')

    pid = np.asarray([r['trial_id'].split('-')[0] for r in rows])
    n_ads = np.asarray([r['n_ads'] for r in rows])
    has_gaze = np.asarray([r['has_gaze'] for r in rows])
    y_adclick = np.asarray([r['ad_clicked'] for r in rows], dtype=int)
    y_noticed = np.asarray([max(r['ad_noticed'], 0) for r in rows], dtype=int)
    rank = np.asarray([r['clicked_position'] for r in rows], dtype=float)
    y_below = (rank >= args.below_k).astype(int)
    tml = np.asarray([r['total_mouse_length'] for r in rows], dtype=float)
    gaze_dwell = np.asarray([r['total_gaze_dwell_ms'] for r in rows], dtype=float)

    pool_ad = n_ads > 0                 # Brückner's native-ad subset
    pool_noticed = pool_ad & has_gaze   # target needs a gaze record
    pool_all = np.ones(len(rows), dtype=bool)

    cursor_models = [('B1 mouse-length (Brückner)', B1),
                     ('B4 page-grain battery (Arapakis-style)', B4),
                     ('B1 + B4', B1 + B4)]
    ad_models = cursor_models + [('layout prior (n_results, n_ads, first_ad_position)', PRIOR_AD),
                                 ('prior + B1 + B4', PRIOR_AD + B1 + B4)]
    rank_models = cursor_models + [('rank prior (n_results)', PRIOR_RANK),
                                   ('prior + B1 + B4', PRIOR_RANK + B1 + B4)]

    tables = {}
    for key, y, pool, models, note in [
        ('ad_clicked', y_adclick, pool_ad, ad_models,
         'final click on a native_ad card; pool = trials showing >= 1 native_ad. Brückner analog. Cursor-defined target.'),
        ('ad_noticed', y_noticed, pool_noticed, ad_models,
         'any fixation strictly inside a native_ad card (screenshot space); pool = ad trials with a gaze record. GAZE-DEFINED PROXY for Arapakis & Leiva 2016 self-report attention.'),
        (f'clicked_below_{args.below_k}', y_below, pool_all, rank_models,
         f'clicked_position >= {args.below_k} (0-based); all trials. No source analog; named in the brief as a depth target.'),
    ]:
        print(f'\n[{key}] pool {int(pool.sum()):,} trials, positives {int(y[pool].sum()):,} '
              f'(rate {y[pool].mean():.3f})')
        tab = score_table(rows, y, pool, pid, models, args.perms)
        tab['B1 raw scalar, no fit (univariate AUC)'] = univariate_auc(tml, y, pid, pool)
        u = tab['B1 raw scalar, no fit (univariate AUC)']
        if 'pooled_auc' in u:
            print(f"  {'B1 raw scalar, no fit':>52s} AUC {u['pooled_auc']:.3f} "
                  f"per-pid {u['per_participant_auc_mean']:.3f}±{u['per_participant_auc_sd']:.3f}")
        for name, sc in tab.items():
            if 'fold_auc_mean' in sc:
                nl = sc.get('label_null', {})
                print(f"  {name:>52s} AUC {sc['pooled_auc']:.3f} folds {sc['fold_auc_mean']:.3f}±{sc['fold_auc_sd']:.3f} "
                      f"null p95 {nl.get('p95', float('nan')):.3f}")
        tables[key] = {'definition': note, 'n_trials': int(pool.sum()),
                       'n_positive': int(y[pool].sum()), 'positive_rate': float(y[pool].mean()),
                       'models': tab}

    spearman = {
        'clicked_rank': spearman_block(tml, rank, pid, pool_all),
        'total_gaze_dwell_ms': spearman_block(tml, gaze_dwell, pid, has_gaze),
        'ad_gaze_dwell_ms_on_ad_trials': spearman_block(
            tml, np.asarray([r['ad_gaze_dwell_ms'] for r in rows], dtype=float), pid, pool_noticed),
    }
    print('\nSpearman(total_mouse_length, target):')
    for k, v in spearman.items():
        print(f"  {k:>32s} rho {v['rho']:+.3f} p {v['p']:.2e} n {v['n']} "
              f"per-pid {v.get('per_participant_rho_mean', float('nan')):+.3f}")

    cg = json.loads(args.candidate_grain.read_text()) if args.candidate_grain.exists() else None
    candidate_grain_ref = None
    if cg:
        candidate_grain_ref = {
            'file': rel(args.candidate_grain), 'sha256': sha256(args.candidate_grain),
            'click': {k: {m: cg['click'][k][m] for m in ('pooled_auc', 'fold_auc_mean', 'fold_auc_sd', 'mrr_at_10')}
                      for k in cg['click'] if k.startswith(('B1', 'B4'))},
            'deferred': {k: {m: cg['deferred'][k][m] for m in ('pooled_auc', 'within_trial_auc')}
                         for k in cg['deferred'] if k.startswith(('B1', 'B4'))}}

    exclusions = ROOT / 'data/aoi-typed/alignment-exclusions.json'
    out = {
        'schema_version': 1,
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'inputs': {
            'feature_cache': rel(args.feature_cache), 'feature_cache_sha256': sha256(args.feature_cache),
            'aggregate_sidecar': rel(sidecar_path), 'aggregate_sidecar_sha256': sha256(sidecar_path),
            'typed_alignment_exclusions': rel(exclusions),
            'typed_alignment_exclusions_sha256': sha256(exclusions) if exclusions.exists() else None,
            'lit_notes': {p.name: sha256(p) for p in sorted(LIT_DIR.glob('*.md'))
                          if p.name in {m['lit_note'] for m in SOURCE_TARGET_MAPPING}},
            'candidate_grain_reference': candidate_grain_ref,
        },
        'protocol': {
            'grain': 'trial (one row per AdSERP trial)',
            'stream': 'reduction_baselines.trial_stream: mousemove only, screenshot space, '
                      f'samples strictly before mousedown(final click) - {BUFFER_MS:.0f} ms',
            'anchor_event': cache['anchor_event'], 'buffer_ms': args.buffer, 'flavor': args.flavor,
            'battery': f'reduction_baselines.globals_for (idle gap {IDLE_GAP_MS:.0f} ms); '
                       'B1 total_mouse_length == B4 g_path_length by construction, so B1+B4 carries a duplicated column',
            'ad_type': AD_TYPE,
            'fixation_rule': 'strict 2-D box containment in native_ad main-axis cards, fixations and cards both '
                             'screenshot space (no ratio applied); all fixations in the trial file, no time bound',
            'classifier': 'LOSO-by-participant StandardScaler + LogisticRegression(class_weight=balanced, C=1); '
                          'pooled AUC over out-of-fold probabilities + per-fold AUC mean/sd',
            'label_null': f'{args.perms} permutations of labels within participant on the pool, same LOSO model',
            'gaze_in_features': False,
            'gaze_defines_targets': ['ad_noticed', 'total_gaze_dwell_ms', 'ad_gaze_dwell_ms_on_ad_trials'],
        },
        'source_target_mapping': SOURCE_TARGET_MAPPING,
        'population': {
            'cache_trials': len(tids), 'trial_rows': len(rows), 'skipped': dict(skipped),
            'participants': int(len(np.unique(pid))),
            'trials_with_ads': int(pool_ad.sum()), 'trials_with_ads_and_gaze': int(pool_noticed.sum()),
            'trials_with_gaze': int(has_gaze.sum()),
            'clicked_etype': dict(Counter(r['clicked_etype'] for r in rows)),
            'clicked_position_hist': {str(int(k)): int(v) for k, v in sorted(Counter(rank.tolist()).items())},
            'n_ads_hist': {str(int(k)): int(v) for k, v in sorted(Counter(n_ads.tolist()).items())},
        },
        'targets': tables,
        'spearman_total_mouse_length': spearman,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f'\nwrote {args.output}')


if __name__ == '__main__':
    main()
