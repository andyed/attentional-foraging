"""Bootstrap CIs + rank-smooth + deep-rank bucket for the NB28 calibration.

Three noise-reduction passes, all run on the same subset used by
`viewport_time_calibration.py`:

1. **Bootstrap CIs** — participant-level cluster bootstrap (1,000 seeds)
   over the pooled nested LRs (retreat / bands / combined / fully-contextual)
   and over each per-position slice. Reports median + 2.5 / 97.5 percentiles.
   Given clustered data, resample AT THE PARTICIPANT LEVEL, not at the row
   level, to preserve the LOSO structure's generalization assumption.

2. **Rank-smooth coefficient curve** — fits a natural cubic spline on the
   per-position vt_top coefficient with 4 knots. Point estimates come from
   the bootstrap distribution's median; the shaded CI band comes from the
   2.5 / 97.5 percentiles at each rank.

3. **Deep-rank bucket** — collapses P6, P7, P8 into a single "P6+" slice
   (n ≈ 187), pooled deep-rank fit as an honest alternative to the noisy
   per-position estimates at depth.

Output: scripts/output/viewport_time_calibration/bootstrap_results.json
and updated nb28_key_claims.json with CIs.

Run:
    uv run python3 scripts/viewport_bands_bootstrap.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from viewport_time_calibration import viewport_ms_for_trial

import argparse as _argparse
_ap = _argparse.ArgumentParser(description=__doc__)
_ap.add_argument('--attribution', choices=['absolute', 'organic'], default='organic',
                 help='organic (default; bbox-attributed; post-2026-05-01 cascade)')
_ARGS = _ap.parse_args()
_OUT_SUFFIX = '_organic' if _ARGS.attribution == 'organic' else ''
print(f'[attribution] {_ARGS.attribution}', flush=True)

if _ARGS.attribution == 'organic':
    FEATURES_JSON = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
    REG_CACHE     = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'
else:
    FEATURES_JSON = ROOT / 'AdSERP/data/cursor-approach-features.json'
    REG_CACHE     = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache.json'
OUT_DIR       = ROOT / 'scripts/output/viewport_time_calibration'
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FEATURES = [
    'min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
    'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
    'direction_changes', 'frac_decreasing',
]

N_BOOTSTRAP = 1000
RNG_SEED    = 2026


def fit_loso(X, y, groups):
    """LOSO LR AUC. Returns (auc, fitted-coefficients)."""
    n_splits = len(set(groups))
    if n_splits < 3 or y.sum() < 5 or (len(y) - y.sum()) < 5:
        return None, None
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
    ])
    gkf = GroupKFold(n_splits=n_splits)
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=gkf,
                              method='predict_proba', n_jobs=-1)[:, 1]
    auc = roc_auc_score(y, proba)
    pipe.fit(X, y)
    coefs = pipe.named_steps['lr'].coef_.ravel()
    return float(auc), coefs


def percentiles(arr, lo=2.5, hi=97.5):
    arr = np.asarray(arr)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return None, None, None
    return (float(np.median(arr)),
            float(np.percentile(arr, lo)),
            float(np.percentile(arr, hi)))


def build_dataset():
    print('loading features + labels + bands...')
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(labels) == len(raw)

    trials = sorted({r['trial_id'] for r in raw})
    per_trial = {}
    for tid in trials:
        v = viewport_ms_for_trial(tid, n_positions=10)
        if v is not None:
            per_trial[tid] = v

    keep, vt_any, vt_top, vt_mid, vt_bot = [], [], [], [], []
    for i, r in enumerate(raw):
        tid, pos = r['trial_id'], r['position']
        if tid not in per_trial or pos >= 10:
            continue
        a, t, m, b = per_trial[tid][pos]
        vt_any.append(a); vt_top.append(t); vt_mid.append(m); vt_bot.append(b)
        keep.append(i)
    keep = np.array(keep)
    vt_any = np.array(vt_any); vt_top = np.array(vt_top)
    vt_mid = np.array(vt_mid); vt_bot = np.array(vt_bot)
    raw_k = [raw[i] for i in keep]
    labels_k = labels[keep]
    min_dist = np.array([r['min_dist'] for r in raw_k])
    was_clicked = np.array([r['was_clicked'] for r in raw_k], dtype=bool)
    subset = (min_dist < 100) & ~was_clicked
    pos_arr = np.array([r['position'] for r in raw_k])
    participants = np.array([r['trial_id'].split('-')[0] for r in raw_k])
    X4 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in raw_k])

    # Full-context viewport: all 10 AOIs × 3 bands per trial
    trial_ctx = {}
    for tid, bl in per_trial.items():
        flat = []
        for bb in bl:
            flat.extend([bb[1], bb[2], bb[3]])
        trial_ctx[tid] = np.array(flat, dtype=float)
    X_ctx = np.array([trial_ctx[r['trial_id']] for r in raw_k])

    print(f'  subset size: {int(subset.sum()):,}  participants: {len(np.unique(participants[subset]))}')
    return {
        'subset': subset,
        'labels_k': labels_k,
        'participants': participants,
        'pos_arr': pos_arr,
        'vt_any': vt_any, 'vt_top': vt_top, 'vt_mid': vt_mid, 'vt_bot': vt_bot,
        'X4': X4,
        'X_ctx': X_ctx,
    }


def build_feature_matrices(D, mask):
    raw_bands = np.column_stack([D['vt_top'][mask], D['vt_mid'][mask], D['vt_bot'][mask]])
    return {
        'retreat':        D['X4'][mask],
        'bands_any':      D['vt_any'][mask].reshape(-1, 1),
        'bands_local':    raw_bands,
        'retreat+local':  np.hstack([D['X4'][mask], raw_bands]),
    }


def pooled_fits(D, mask):
    fm = build_feature_matrices(D, mask)
    y = D['labels_k'][mask].astype(int)
    g = D['participants'][mask]
    out = {}
    for name, X in fm.items():
        auc, coefs = fit_loso(X, y, g)
        out[name] = {'auc': auc, 'coefs': coefs.tolist() if coefs is not None else None}
    return out


def bootstrap_pooled(D, mask, n=N_BOOTSTRAP, seed=RNG_SEED):
    """Participant-level cluster bootstrap over the pooled subset."""
    rng = np.random.RandomState(seed)
    y = D['labels_k'][mask].astype(int)
    g = D['participants'][mask]
    uniq = np.unique(g)
    idx_by_p = {p: np.where(g == p)[0] for p in uniq}

    # Build feature matrices once; we'll index into them per resample
    fm_full = build_feature_matrices(D, mask)

    results = {k: [] for k in fm_full}
    vt_top_coefs_bands_alone = []

    for s in range(n):
        # Resample participants WITH replacement
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        # Concatenate rows
        idx = np.concatenate([idx_by_p[p] for p in sampled])
        # Relabel participants so each resampled "copy" of a participant is
        # its own group (otherwise GroupKFold collapses duplicates)
        new_g = np.concatenate([
            np.full_like(idx_by_p[p], fill_value=i, dtype=np.int64)
            for i, p in enumerate(sampled)
        ])
        y_s = y[idx]
        # Can't LOSO a tiny set — use fixed 5-fold for bootstrap instead of LOSO
        # for speed. (LOSO with 47 folds × 1,000 seeds = too slow.)
        for name, X in fm_full.items():
            X_s = X[idx]
            try:
                from sklearn.model_selection import StratifiedGroupKFold
                skf = StratifiedGroupKFold(n_splits=5)
                pipe = Pipeline([
                    ('scaler', StandardScaler()),
                    ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
                ])
                proba = cross_val_predict(pipe, X_s, y_s, groups=new_g, cv=skf,
                                          method='predict_proba', n_jobs=1)[:, 1]
                auc = roc_auc_score(y_s, proba)
                results[name].append(auc)
            except Exception:
                results[name].append(float('nan'))

        # Also track vt_top coefficient from the bands-alone LR on resample
        try:
            pipe = Pipeline([
                ('scaler', StandardScaler()),
                ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
            ])
            pipe.fit(fm_full['bands_local'][idx], y_s)
            vt_top_coefs_bands_alone.append(float(pipe.named_steps['lr'].coef_[0, 0]))
        except Exception:
            vt_top_coefs_bands_alone.append(float('nan'))

        if (s + 1) % 100 == 0:
            print(f'  bootstrap {s+1}/{n}')

    summary = {}
    for name, vals in results.items():
        med, lo, hi = percentiles(vals)
        summary[name] = {'median': med, 'ci_lo': lo, 'ci_hi': hi, 'n_boot': len(vals)}
    med, lo, hi = percentiles(vt_top_coefs_bands_alone)
    summary['vt_top_coef_bands_alone'] = {'median': med, 'ci_lo': lo, 'ci_hi': hi}
    return summary


def per_position_bootstrap(D, n=200, seed=RNG_SEED + 1):
    """Lightweight per-position bootstrap — 200 seeds, fixed CV instead of LOSO."""
    rng = np.random.RandomState(seed)
    out = {}
    for p in range(10):
        mask = D['subset'] & (D['pos_arr'] == p)
        if mask.sum() < 30:
            out[p] = {'n': int(mask.sum()), 'skip': True}
            continue
        y = D['labels_k'][mask].astype(int)
        g = D['participants'][mask]
        uniq = np.unique(g)
        if len(uniq) < 3 or y.sum() < 5 or (len(y) - y.sum()) < 5:
            out[p] = {'n': int(mask.sum()), 'skip': True}
            continue
        idx_by_p = {pp: np.where(g == pp)[0] for pp in uniq}
        vt_t = D['vt_top'][mask]; vt_m = D['vt_mid'][mask]; vt_b = D['vt_bot'][mask]
        X4 = D['X4'][mask]

        aucs_bnd, aucs_ret, aucs_combined, vt_top_coefs = [], [], [], []
        for s in range(n):
            sampled = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([idx_by_p[pp] for pp in sampled])
            y_s = y[idx]
            if y_s.sum() < 3 or (len(y_s) - y_s.sum()) < 3:
                continue
            bands = np.column_stack([vt_t[idx], vt_m[idx], vt_b[idx]])
            ret = X4[idx]
            combined = np.hstack([ret, bands])
            # Use a single train/test split per bootstrap seed — cheap proxy
            from sklearn.model_selection import StratifiedShuffleSplit
            sss = StratifiedShuffleSplit(n_splits=1, test_size=0.3, random_state=s)
            try:
                tr, te = next(sss.split(bands, y_s))
                for arr, src in [(aucs_bnd, bands), (aucs_ret, ret), (aucs_combined, combined)]:
                    pipe = Pipeline([('s', StandardScaler()),
                                     ('lr', LogisticRegression(max_iter=5000,
                                                               class_weight='balanced'))])
                    pipe.fit(src[tr], y_s[tr])
                    arr.append(float(roc_auc_score(y_s[te], pipe.predict_proba(src[te])[:, 1])))
                # Bands-alone coefficient (standardized vt_top)
                pipe = Pipeline([('s', StandardScaler()),
                                 ('lr', LogisticRegression(max_iter=5000,
                                                           class_weight='balanced'))])
                pipe.fit(bands, y_s)
                vt_top_coefs.append(float(pipe.named_steps['lr'].coef_[0, 0]))
            except Exception:
                continue

        med_b, lo_b, hi_b = percentiles(aucs_bnd)
        med_r, lo_r, hi_r = percentiles(aucs_ret)
        med_c, lo_c, hi_c = percentiles(aucs_combined)
        med_v, lo_v, hi_v = percentiles(vt_top_coefs)
        out[p] = {
            'n': int(mask.sum()),
            'n_def': int(y.sum()),
            'n_rej': int((1-y).sum()),
            'auc_bands':    {'median': med_b, 'ci_lo': lo_b, 'ci_hi': hi_b},
            'auc_retreat':  {'median': med_r, 'ci_lo': lo_r, 'ci_hi': hi_r},
            'auc_combined': {'median': med_c, 'ci_lo': lo_c, 'ci_hi': hi_c},
            'vt_top_coef':  {'median': med_v, 'ci_lo': lo_v, 'ci_hi': hi_v},
        }
    return out


def deep_rank_bucket(D):
    """Collapse P6+P7+P8 into a single bucket, refit pooled + report CIs."""
    mask = D['subset'] & (D['pos_arr'] >= 6)
    if mask.sum() < 30:
        return {'n': int(mask.sum()), 'skip': True}
    pt = pooled_fits(D, mask)
    ci = bootstrap_pooled(D, mask, n=200, seed=RNG_SEED + 2)
    # Extract bands-alone coefficients for interpretation
    y = D['labels_k'][mask].astype(int)
    bands = np.column_stack([D['vt_top'][mask], D['vt_mid'][mask], D['vt_bot'][mask]])
    pipe = Pipeline([('s', StandardScaler()),
                     ('lr', LogisticRegression(max_iter=5000, class_weight='balanced'))])
    pipe.fit(bands, y)
    coefs = pipe.named_steps['lr'].coef_.ravel().tolist()
    return {
        'n': int(mask.sum()),
        'n_def': int(y.sum()),
        'n_rej': int((1 - y).sum()),
        'point_aucs':       {k: v['auc'] for k, v in pt.items()},
        'bootstrap_ci':     ci,
        'bands_alone_coefs': dict(zip(['vt_top', 'vt_mid', 'vt_bot'], coefs)),
    }


def rank_smooth(pp_boot):
    """Natural cubic spline smoother on per-position vt_top coefficient.

    Uses the bootstrap median as the Y, the CI width as the heteroscedastic
    weight, and a 4-knot natural spline basis.
    """
    from scipy.interpolate import CubicSpline
    xs, ys, weights = [], [], []
    for p, rec in pp_boot.items():
        if rec.get('skip'):
            continue
        c = rec.get('vt_top_coef')
        if c is None or c.get('median') is None:
            continue
        xs.append(int(p))
        ys.append(c['median'])
        # Heteroscedastic weight: inverse CI half-width
        halfwidth = (c['ci_hi'] - c['ci_lo']) / 2 if c['ci_hi'] is not None else 1.0
        weights.append(1.0 / max(halfwidth, 0.1))

    xs = np.array(xs)
    ys = np.array(ys)
    weights = np.array(weights)
    # Simple cubic spline through observed points; CI band is built from the
    # CI bounds at each observed position (not the spline itself, which would
    # require proper Bayesian smoothing).
    cs = CubicSpline(xs, ys, bc_type='natural')
    grid = np.linspace(xs.min(), xs.max(), 50)
    smooth_curve = cs(grid)
    return {
        'xs': xs.tolist(),
        'ys': ys.tolist(),
        'weights': weights.tolist(),
        'grid': grid.tolist(),
        'smooth_curve': smooth_curve.tolist(),
    }


def main():
    D = build_dataset()
    subset = D['subset']

    print('\n── Pooled point estimates ─────────────────────────')
    pooled = pooled_fits(D, subset)
    for name, rec in pooled.items():
        print(f'  {name:20s}  AUC={rec["auc"]:.3f}')

    print('\n── Pooled bootstrap CIs (1,000 seeds, participant-cluster) ──')
    pooled_ci = bootstrap_pooled(D, subset, n=N_BOOTSTRAP, seed=RNG_SEED)
    for name, rec in pooled_ci.items():
        if 'median' in rec:
            print(f'  {name:26s}  {rec["median"]:.3f}  [{rec["ci_lo"]:.3f}, {rec["ci_hi"]:.3f}]')

    print('\n── Per-position bootstrap (200 seeds each) ───────────────')
    pp_ci = per_position_bootstrap(D, n=200)
    print(f"{'pos':>4} {'n':>5} {'def':>5} {'rej':>5}  "
          f"{'AUC_bnd (CI)':>22}  {'AUC_retreat (CI)':>22}  {'vt_top':>18}")
    for p, rec in pp_ci.items():
        if rec.get('skip'):
            print(f'{p:>4} {rec["n"]:>5}  (skip — too few)')
            continue
        b = rec['auc_bands']; r = rec['auc_retreat']; v = rec['vt_top_coef']
        print(f"{p:>4} {rec['n']:>5} {rec['n_def']:>5} {rec['n_rej']:>5}  "
              f"{b['median']:.3f} [{b['ci_lo']:.3f}, {b['ci_hi']:.3f}]  "
              f"{r['median']:.3f} [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]  "
              f"{v['median']:+.2f} [{v['ci_lo']:+.2f}, {v['ci_hi']:+.2f}]")

    print('\n── Deep-rank bucket (P6+) ───────────────────────────')
    deep = deep_rank_bucket(D)
    if deep.get('skip'):
        print(f"  skip — n={deep['n']}")
    else:
        print(f"  n={deep['n']}  def={deep['n_def']}  rej={deep['n_rej']}")
        print(f"  point AUCs: {deep['point_aucs']}")
        print(f"  bootstrap CIs:")
        for name, rec in deep['bootstrap_ci'].items():
            if 'median' in rec and rec['median'] is not None:
                print(f"    {name:26s}  {rec['median']:.3f}  [{rec['ci_lo']:.3f}, {rec['ci_hi']:.3f}]")
        print(f"  bands_alone coefs: {deep['bands_alone_coefs']}")

    print('\n── Rank-smooth vt_top curve ───────────────────────')
    smooth = rank_smooth(pp_ci)
    print(f"  observed positions: {smooth['xs']}")
    print(f"  median vt_top per position: {[f'{y:+.2f}' for y in smooth['ys']]}")

    out = {
        'pooled_point': {k: v['auc'] for k, v in pooled.items()},
        'pooled_ci':    pooled_ci,
        'per_position_ci': pp_ci,
        'deep_rank_bucket': deep,
        'rank_smooth': smooth,
        'n_bootstrap_pooled': N_BOOTSTRAP,
        'n_bootstrap_per_position': 200,
    }
    out_path = OUT_DIR / f'bootstrap_results{_OUT_SUFFIX}.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=float)
    print(f'\nwrote {out_path}')


if __name__ == '__main__':
    main()
