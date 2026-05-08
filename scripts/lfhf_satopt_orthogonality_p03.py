"""LF/HF × satisficer/optimizer orthogonality — P0–P3 robustness check (ETTAC queue item 3).

The original orthogonality finding (AUC = 0.43, χ² p = 0.77) was computed on
per-participant features summarized across full positions 0–9. Given:
  - satopt terciles are partly self-selected at depth (who scrolls deep is who),
  - NB11 documents a satopt–LHIPA duration confound at depth,
the orthogonality result might have been depth-noise-assisted.

This script recomputes the same dissociation using ONLY P0–P3 segments —
the "steep phase" where K10 says the gradient is universal (ρ = −1.000)
and where every participant contributes (see 2026-04-19 concentration audit).
If orthogonality holds in the steep phase, the dissociation is robust.
If it collapses, the original framing was depth-noise-assisted.

Outputs:
  scripts/output/lfhf_satopt_orthogonality_p03/summary.json
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
TRAITS_CSV = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
OUT_DIR = ROOT / 'scripts/output/lfhf_satopt_orthogonality_p03'
OUT_DIR.mkdir(parents=True, exist_ok=True)

POS_FULL = list(range(10))   # original orthogonality range P0–P9
POS_STEEP = list(range(4))   # robustness range P0–P3
MIN_POS_PER_PARTICIPANT = 3  # require ≥3 of the 4 (or 10) positions to compute slope

RNG_SEED = 2026


def load_lfhf_per_participant() -> dict[str, dict[int, list[float]]]:
    """Return {pid: {pos: [lfhf, ...]}} from the per-trial JSON."""
    data = json.load(open(LFHF_JSON))
    out: dict[str, dict[int, list[float]]] = {}
    for trial_id, trial in data.items():
        pid = trial_id.split('-')[0]
        out.setdefault(pid, {})
        for seg in trial['positions']:
            lfhf = seg['lfhf']
            if lfhf is None or not math.isfinite(lfhf):
                continue
            out[pid].setdefault(seg['pos'], []).append(float(lfhf))
    return out


def load_regression_rate() -> dict[str, float]:
    rates: dict[str, float] = {}
    with open(TRAITS_CSV) as f:
        for row in csv.DictReader(f):
            rates[row['participant']] = float(row['regression_rate'])
    return rates


def position_medians(per_part: dict[str, dict[int, list[float]]], positions: list[int]
                     ) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for pid, pos_map in per_part.items():
        med_by_pos: dict[int, float] = {}
        for p in positions:
            vals = pos_map.get(p, [])
            if vals:
                med_by_pos[p] = float(np.median(vals))
        out[pid] = med_by_pos
    return out


def participant_features(meds: dict[int, float], positions: list[int]) -> dict[str, float] | None:
    """Extract slope/mean/pos0/early-late-ratio features from a participant's medians.

    Returns None if insufficient positions.
    """
    xs, ys = [], []
    for p in positions:
        if p in meds:
            xs.append(p); ys.append(meds[p])
    if len(xs) < MIN_POS_PER_PARTICIPANT:
        return None

    xs_a, ys_a = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    slope, intercept = np.polyfit(xs_a, ys_a, 1)
    mean_val = float(np.mean(ys_a))
    pos0 = float(meds.get(positions[0], np.nan))
    late = float(meds.get(positions[-1], np.nan))
    # Early/late ratio (robust: guard zero)
    early_late_ratio = (pos0 / late) if (np.isfinite(pos0) and np.isfinite(late) and late > 1e-6) else np.nan
    trial_iqr = float(np.percentile(ys_a, 75) - np.percentile(ys_a, 25))

    return {
        'slope':            float(slope),
        'mean':             mean_val,
        'pos_first':        pos0,
        'pos_last':         late,
        'early_late_ratio': early_late_ratio,
        'trial_iqr':        trial_iqr,
    }


def loo_auc(X: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """LOO LR AUC + accuracy. Returns (auc, accuracy)."""
    if len(y) < 10 or y.sum() < 3 or (len(y) - y.sum()) < 3:
        return float('nan'), float('nan')
    loo = LeaveOneOut()
    proba = np.zeros(len(y))
    pred = np.zeros(len(y), dtype=int)
    for train_idx, test_idx in loo.split(X):
        pipe = Pipeline([
            ('scaler', StandardScaler()),
            ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
        ])
        pipe.fit(X[train_idx], y[train_idx])
        proba[test_idx] = pipe.predict_proba(X[test_idx])[0, 1]
        pred[test_idx] = pipe.predict(X[test_idx])[0]
    auc = roc_auc_score(y, proba)
    acc = float((pred == y).mean())
    return float(auc), acc


def trajectory_category(slope: float, rho_threshold: float = 0.15,
                        meds: dict[int, float] | None = None,
                        positions: list[int] | None = None) -> str | None:
    """Categorize as declining / flat / increasing by Spearman sign using positions + medians."""
    if meds is None or positions is None:
        # Fallback: use slope sign as a proxy when we don't have the whole trajectory
        if slope < -0.15:
            return 'declining'
        if slope > 0.15:
            return 'increasing'
        return 'flat'
    xs, ys = [], []
    for p in positions:
        if p in meds:
            xs.append(p); ys.append(meds[p])
    if len(xs) < 3:
        return None
    rho, _ = stats.spearmanr(xs, ys)
    if not math.isfinite(rho):
        return None
    if rho < -rho_threshold:
        return 'declining'
    if rho > rho_threshold:
        return 'increasing'
    return 'flat'


def run_range(name: str, positions: list[int],
              per_part: dict[str, dict[int, list[float]]],
              rates: dict[str, float]) -> dict:
    print(f'\n═══ Range {name}: positions {positions[0]}..{positions[-1]} ═══')
    meds = position_medians(per_part, positions)

    # Build participant feature table
    feats: dict[str, dict[str, float]] = {}
    for pid, m in meds.items():
        f = participant_features(m, positions)
        if f is not None:
            feats[pid] = f

    # Keep only participants with both features and regression_rate
    pids = sorted(p for p in feats if p in rates)
    print(f'  N participants with features + regression_rate: {len(pids)}')

    # Satisfice / optimize labels via median split (matches orthogonality memo convention)
    rates_arr = np.array([rates[p] for p in pids], dtype=float)
    median_rate = float(np.median(rates_arr))
    labels = (rates_arr > median_rate).astype(int)  # 1 = optimizer (more regressions)
    print(f'  median regression_rate = {median_rate:.4f}  '
          f'(satisficer N={(labels == 0).sum()}, optimizer N={(labels == 1).sum()})')

    feature_names = ['slope', 'mean', 'pos_first', 'early_late_ratio', 'trial_iqr']
    X = np.array([[feats[p][fn] for fn in feature_names] for p in pids], dtype=float)
    # Drop rows with any NaN in early_late_ratio
    keep = ~np.any(~np.isfinite(X), axis=1)
    X_ok = X[keep]
    y_ok = labels[keep]
    print(f'  N with all features finite: {len(y_ok)}')

    # LOO LR
    auc, acc = loo_auc(X_ok, y_ok)
    print(f'  LOO-LR  AUC = {auc:.3f}  accuracy = {acc:.3f}  '
          f'(majority baseline = {max(y_ok.mean(), 1 - y_ok.mean()):.3f})')

    # Per-feature t-tests
    feature_tests: dict[str, dict] = {}
    for i, fn in enumerate(feature_names):
        vals0 = X_ok[y_ok == 0, i]
        vals1 = X_ok[y_ok == 1, i]
        if len(vals0) >= 3 and len(vals1) >= 3:
            t, p = stats.ttest_ind(vals0, vals1, equal_var=False)
            pooled_sd = math.sqrt((np.var(vals0, ddof=1) + np.var(vals1, ddof=1)) / 2)
            d = (np.mean(vals1) - np.mean(vals0)) / pooled_sd if pooled_sd > 0 else float('nan')
            feature_tests[fn] = {
                't': float(t), 'p': float(p), 'cohens_d': float(d),
                'mean_sat': float(np.mean(vals0)), 'mean_opt': float(np.mean(vals1)),
            }
        else:
            feature_tests[fn] = None
    print('  per-feature t-tests (sat vs opt, Welch):')
    for fn, row in feature_tests.items():
        if row is None:
            print(f'    {fn:>18s}: insufficient n')
        else:
            print(f'    {fn:>18s}:  t={row["t"]:+.3f}  p={row["p"]:.3g}  d={row["cohens_d"]:+.3f}')

    # Trajectory categories × satopt (χ²)
    cat_by_pid: dict[str, str] = {}
    for p in pids:
        cat = trajectory_category(feats[p]['slope'], meds=meds[p], positions=positions)
        if cat is not None:
            cat_by_pid[p] = cat
    cats = ['declining', 'flat', 'increasing']
    contingency = np.zeros((3, 2), dtype=int)
    for p in pids:
        if p not in cat_by_pid:
            continue
        is_opt = int(rates[p] > median_rate)
        ci = cats.index(cat_by_pid[p])
        contingency[ci, is_opt] += 1
    chi2_result = {'contingency': contingency.tolist()}
    # χ² requires all rows to have ≥1 obs
    if (contingency.sum(axis=1) > 0).all() and (contingency.sum(axis=0) > 0).all():
        chi2, pval, dof, _ = stats.chi2_contingency(contingency)
        chi2_result.update({'chi2': float(chi2), 'p': float(pval), 'dof': int(dof)})
    print(f'  trajectory × satopt contingency (rows = {cats}, cols = sat, opt):')
    for ci, cname in enumerate(cats):
        print(f'    {cname:>11s}: sat={contingency[ci, 0]:>2d} opt={contingency[ci, 1]:>2d}')
    if 'chi2' in chi2_result:
        print(f'  χ² = {chi2_result["chi2"]:.3f}  p = {chi2_result["p"]:.3g}  dof = {chi2_result["dof"]}')

    # Spearman(slope, regression_rate)
    slopes = np.array([feats[p]['slope'] for p in pids], dtype=float)
    rates_aligned = np.array([rates[p] for p in pids], dtype=float)
    mask = np.isfinite(slopes)
    rho_sr, p_sr = stats.spearmanr(slopes[mask], rates_aligned[mask])
    print(f'  Spearman(slope, regression_rate) = {rho_sr:+.3f}  p = {p_sr:.3g}')

    return {
        'range': f'P{positions[0]}-P{positions[-1]}',
        'n_participants': int(len(y_ok)),
        'median_regression_rate': median_rate,
        'loo_auc': auc,
        'loo_accuracy': acc,
        'majority_baseline': float(max(y_ok.mean(), 1 - y_ok.mean())),
        'feature_tests': feature_tests,
        'chi_square': chi2_result,
        'spearman_slope_regression_rate': {'rho': float(rho_sr), 'p': float(p_sr)},
    }


def main() -> None:
    np.random.seed(RNG_SEED)
    per_part = load_lfhf_per_participant()
    rates = load_regression_rate()
    print(f'[load] {len(per_part)} participants from LF/HF JSON, '
          f'{len(rates)} with regression_rate traits')

    results = {
        'full_P0_P9': run_range('full', POS_FULL, per_part, rates),
        'steep_P0_P3': run_range('steep', POS_STEEP, per_part, rates),
    }

    # Summary comparison
    print('\n═══ Comparison ═══')
    print(f'  {"metric":<35s} {"full P0–P9":>12s} {"steep P0–P3":>12s}')
    for key in ('loo_auc', 'loo_accuracy'):
        f_val = results['full_P0_P9'][key]
        s_val = results['steep_P0_P3'][key]
        print(f'  {key:<35s} {f_val:>12.3f} {s_val:>12.3f}')
    for key in ('chi_square', 'spearman_slope_regression_rate'):
        f_val = results['full_P0_P9'][key].get('p') if isinstance(results['full_P0_P9'][key], dict) else None
        s_val = results['steep_P0_P3'][key].get('p') if isinstance(results['steep_P0_P3'][key], dict) else None
        label = f'{key} p'
        f_str = f'{f_val:.3g}' if f_val is not None else 'n/a'
        s_str = f'{s_val:.3g}' if s_val is not None else 'n/a'
        print(f'  {label:<35s} {f_str:>12s} {s_str:>12s}')

    out = OUT_DIR / 'summary.json'
    out.write_text(json.dumps(results, indent=2))
    print(f'\n[out] {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
