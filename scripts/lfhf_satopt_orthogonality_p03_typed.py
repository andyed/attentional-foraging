"""LF/HF × satopt orthogonality (P0-P3) under typed attribution.

Forked from lfhf_satopt_orthogonality_p03.py. Identical logic; reads typed
LF/HF JSON instead of absolute. Tests whether the orthogonality finding
holds when LF/HF is computed under the typed cascade.

Output: scripts/output/lfhf_satopt_orthogonality_p03_typed/summary.json
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
# Typed LF/HF (post-2026-05-04 cascade)
LFHF_JSON = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-typed.json'
TRAITS_CSV = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
OUT_DIR = ROOT / 'scripts/output/lfhf_satopt_orthogonality_p03_typed'
OUT_DIR.mkdir(parents=True, exist_ok=True)

POS_STEEP = list(range(4))
MIN_POS_PER_PARTICIPANT = 3
RNG_SEED = 2026


def load_lfhf_per_participant():
    data = json.load(open(LFHF_JSON))
    out = {}
    for trial_id, trial in data.items():
        pid = trial_id.split('-')[0]
        out.setdefault(pid, {})
        for seg in trial['positions']:
            lfhf = seg['lfhf']
            if lfhf is None or not math.isfinite(lfhf):
                continue
            if seg['pos'] not in POS_STEEP:
                continue
            out[pid].setdefault(seg['pos'], []).append(float(lfhf))
    return out


def per_participant_features(per_pid):
    """6 LF/HF trajectory features per participant on P0-P3."""
    feats = {}
    for pid, by_pos in per_pid.items():
        positions = sorted(by_pos.keys())
        if len(positions) < MIN_POS_PER_PARTICIPANT:
            continue
        medians = [float(np.median(by_pos[p])) for p in positions]
        # Slope via Spearman ρ on (pos, median)
        try:
            slope_rho = stats.spearmanr(positions, medians).correlation
        except Exception:
            slope_rho = float('nan')
        feats[pid] = {
            'mean_p0': float(np.median(by_pos.get(0, [np.nan]))),
            'mean_p1': float(np.median(by_pos.get(1, [np.nan]))),
            'mean_p2': float(np.median(by_pos.get(2, [np.nan]))),
            'mean_p3': float(np.median(by_pos.get(3, [np.nan]))),
            'slope_rho': slope_rho,
            'mean_overall': float(np.median(np.concatenate([by_pos[p] for p in positions]))),
        }
    return feats


def load_traits():
    traits = {}
    with open(TRAITS_CSV) as f:
        for row in csv.DictReader(f):
            pid = row['participant']
            traits[pid] = row
    return traits


def main():
    print(f"[orthogonality-typed] Loading LF/HF per-participant on P0-P3...")
    per_pid = load_lfhf_per_participant()
    feats = per_participant_features(per_pid)
    print(f"  {len(feats)} participants with LF/HF features")

    traits = load_traits()
    common = sorted(set(feats) & set(traits))
    print(f"  {len(common)} participants with LF/HF + traits")

    # Build X, y
    feature_keys = ['mean_p0', 'mean_p1', 'mean_p2', 'mean_p3', 'slope_rho',
                    'mean_overall']
    X_rows = []
    y_satopt = []  # 1 if optimizer (high regression rate), 0 satisficer
    rates = []
    for pid in common:
        row = [feats[pid][k] for k in feature_keys]
        if any(not math.isfinite(v) for v in row):
            continue
        rate_str = traits[pid].get('regression_rate', '')
        try:
            rate = float(rate_str)
        except (ValueError, TypeError):
            continue
        X_rows.append(row)
        rates.append(rate)
        y_satopt.append(1 if rate > np.median([float(traits[p].get('regression_rate', 0))
                                                for p in common
                                                if traits[p].get('regression_rate', '')]) else 0)
    X = np.array(X_rows)
    y = np.array(y_satopt)
    rates = np.array(rates)
    print(f"  N for orthogonality test: {len(X)}")
    print(f"  satopt class balance: optimizer={int(y.sum())} satisficer={int((y == 0).sum())}")

    # ── LOO logistic regression: predict satopt from 6 LF/HF features
    pipe = Pipeline([('scaler', StandardScaler()),
                     ('lr', LogisticRegression(max_iter=200, random_state=RNG_SEED))])
    loo = LeaveOneOut()
    preds = np.zeros(len(X))
    for tr, te in loo.split(X):
        pipe.fit(X[tr], y[tr])
        preds[te] = pipe.predict_proba(X[te])[:, 1]
    auc_lr = roc_auc_score(y, preds)
    majority = max(y.mean(), 1 - y.mean())

    # Spearman(slope_rho, regression_rate)
    slopes = X[:, 4]
    rho_slope_rate, p_slope_rate = stats.spearmanr(slopes, rates)

    # Per-feature Cohen's d satisficer vs optimizer
    per_feature_d = {}
    for i, k in enumerate(feature_keys):
        a = X[y == 0, i]
        b = X[y == 1, i]
        if len(a) > 1 and len(b) > 1:
            pooled = np.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2)
            d = (b.mean() - a.mean()) / pooled if pooled > 0 else 0.0
            per_feature_d[k] = float(d)

    print("\n=== TYPED P0-P3 orthogonality verdict ===")
    print(f"  LOO-LR AUC               : {auc_lr:.3f}  (majority baseline {majority:.3f})")
    print(f"  Spearman(slope_rho, rate): ρ={rho_slope_rate:+.3f}  p={p_slope_rate:.3f}")
    print(f"  Per-feature |d|: {', '.join(f'{k}={abs(v):.2f}' for k, v in per_feature_d.items())}")

    # Compare to documented bbox-organic baseline
    print("\nHistorical baseline (bbox-organic, 2026-04-19):")
    print("  LOO-LR AUC               : 0.523  (majority 0.522)")
    print("  Spearman(slope_rho, rate): ρ=-0.020  p=0.90")

    if auc_lr < 0.60 and abs(rho_slope_rate) < 0.10:
        print("\n  → ORTHOGONALITY HOLDS under typed.")
    else:
        print("\n  → Re-evaluate orthogonality framing.")

    summary = {
        'date': '2026-05-04',
        'attribution': 'typed',
        'positions': POS_STEEP,
        'n_participants': int(len(X)),
        'auc_loo_lr': float(auc_lr),
        'majority_baseline': float(majority),
        'spearman_slope_vs_rate': {'rho': float(rho_slope_rate),
                                    'p': float(p_slope_rate)},
        'per_feature_cohens_d': per_feature_d,
        'historical_bbox_organic': {
            'auc_loo_lr': 0.523,
            'majority_baseline': 0.522,
            'spearman_slope_vs_rate': {'rho': -0.020, 'p': 0.90},
        },
    }
    out_path = OUT_DIR / 'summary.json'
    json.dump(summary, open(out_path, 'w'), indent=2)
    print(f"\nWrote {out_path}")


if __name__ == '__main__':
    main()
