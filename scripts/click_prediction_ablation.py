"""LTR-style click-prediction ablation: baseline cursor/viewport vs +saccade vs
+content vs all three.

Quantifies the predictive lift of each new feature family on per-(trial,
position) click outcome. Frames as the LAB-only headroom over a WILD-portable
cursor-only baseline.

Models:
  (a) baseline      — viewport-trajectory (14 features, cursor + viewport)
  (b) +saccade      — baseline + saccade-orientation (frac_h, ratio, runs)
  (c) +content      — baseline + content (TTR, q-overlap, q-cosine, etc.)
  (d) +both         — baseline + saccade + content

Method: 5-fold cross-validated logistic regression with z-scored features,
participant-level grouping (no leakage of same participant across folds).
Reports per-fold AUC, mean ± SD, and feature importance (z-scored coefs).

Output:
  scripts/output/click_prediction_ablation/summary.json
  scripts/output/click_prediction_ablation/ablation_panel.png
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import GroupKFold

warnings.filterwarnings('ignore', category=UserWarning)

ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = ROOT / 'AdSERP/data/viewport-trajectory-features.json'
SACCADE = ROOT / 'AdSERP/data/saccade-orientation-by-position.json'
CONTENT = ROOT / 'AdSERP/data/content-features-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'  # has click_pos
OUT_DIR = ROOT / 'scripts/output/click_prediction_ablation'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Feature groups
VIEWPORT_FEATS = [
    'vt_any', 'vt_top', 'vt_mid', 'vt_bot', 'vt_center_ms',
    'avg_viewport_y', 'max_overlap_frac',
    'max_abs_velocity', 'min_abs_velocity', 'pause_ms',
    'n_reversals', 'max_decel_near_center',
    'entry_velocity', 'exit_velocity',
]
SACCADE_FEATS = [
    'frac_horizontal', 'ratio_h_to_v',
    'max_horizontal_run', 'n_saccades',
]
CONTENT_FEATS = [
    'snippet_tokens', 'snippet_ttr', 'snippet_chars',
    'snippet_numerals', 'snippet_has_price',
    'title_tokens', 'title_chars', 'title_ttr',
    'q_overlap_count', 'q_overlap_jaccard', 'q_overlap_in_title',
    'q_text_cosine',
]
POSITION_FEAT = ['position']  # Always include — strong baseline

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 9, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}


def build_table() -> list[dict]:
    print('[load] feature caches', file=sys.stderr)
    viewport = json.load(open(VIEWPORT))  # list
    saccade = json.load(open(SACCADE))    # dict
    content = json.load(open(CONTENT))    # dict
    rcache = json.load(open(RIPA2))       # dict

    # Index viewport by (tid, pos)
    vp_by_tp: dict[tuple[str, int], dict] = {}
    for r in viewport:
        vp_by_tp[(r['trial_id'], int(r['position']))] = r

    rows: list[dict] = []
    for tid, sblock in saccade.items():
        c = content.get(tid)
        if c is None:
            continue
        c_by_pos = {p['pos']: p for p in c.get('positions', [])}
        click_pos = rcache.get(tid, {}).get('click_pos')
        for s in sblock.get('positions', []):
            pos = int(s['pos'])
            vp = vp_by_tp.get((tid, pos))
            cp = c_by_pos.get(pos)
            if vp is None or cp is None:
                continue
            row: dict = {
                'tid': tid,
                'pid': tid.split('-')[0],
                'pos': pos,
                'position': pos,
                'clicked': int(click_pos == pos) if click_pos is not None else 0,
            }
            for k in VIEWPORT_FEATS:
                row[k] = float(vp.get(k, 0.0) or 0.0)
            for k in SACCADE_FEATS:
                v = s.get(k, 0.0)
                if v == float('inf'):
                    v = 100.0  # cap ratio_h_to_v when n_v==0
                row[k] = float(v)
            for k in CONTENT_FEATS:
                v = cp.get(k, 0.0)
                if not isinstance(v, (int, float)) or v != v:  # NaN
                    v = 0.0
                row[k] = float(v)
            rows.append(row)
    print(f'  joined: {len(rows):,} (trial, pos) rows', file=sys.stderr)
    return rows


def evaluate(rows: list[dict], feature_set: list[str], label: str
             ) -> dict:
    X = np.array([[r[f] for f in feature_set] for r in rows], dtype=float)
    y = np.array([r['clicked'] for r in rows], dtype=int)
    groups = np.array([r['pid'] for r in rows])

    # z-score features (fit on training only inside CV; here we report
    # whole-set coefs after train-time z-scoring per fold)
    aucs, aps = [], []
    coefs_acc = np.zeros(X.shape[1])
    n_folds = 0
    gkf = GroupKFold(n_splits=5)
    for tr_idx, te_idx in gkf.split(X, y, groups):
        X_tr, X_te = X[tr_idx], X[te_idx]
        y_tr, y_te = y[tr_idx], y[te_idx]
        mu = X_tr.mean(axis=0)
        sd = X_tr.std(axis=0)
        sd[sd < 1e-9] = 1.0
        X_tr_z = (X_tr - mu) / sd
        X_te_z = (X_te - mu) / sd
        clf = LogisticRegression(max_iter=2000, C=1.0, solver='lbfgs')
        clf.fit(X_tr_z, y_tr)
        prob = clf.predict_proba(X_te_z)[:, 1]
        aucs.append(roc_auc_score(y_te, prob))
        aps.append(average_precision_score(y_te, prob))
        coefs_acc += clf.coef_[0]
        n_folds += 1
    return {
        'label': label,
        'features': feature_set,
        'n_features': len(feature_set),
        'auc_mean': float(np.mean(aucs)),
        'auc_sd': float(np.std(aucs, ddof=1)),
        'auc_per_fold': [float(a) for a in aucs],
        'ap_mean': float(np.mean(aps)),
        'ap_sd': float(np.std(aps, ddof=1)),
        'coef_z_mean': {f: float(coefs_acc[i] / n_folds)
                        for i, f in enumerate(feature_set)},
    }


def main() -> None:
    rows = build_table()
    pids = sorted(set(r['pid'] for r in rows))
    n_clk = sum(r['clicked'] for r in rows)
    print(f'  {len(pids)} participants, {n_clk:,} clicks ({100*n_clk/len(rows):.1f}%)',
          file=sys.stderr)

    # Define feature sets — always include POSITION as a strong control
    BASE = POSITION_FEAT + VIEWPORT_FEATS
    SETS = {
        'pos_only':       POSITION_FEAT,
        'baseline':       BASE,
        'base+saccade':   BASE + SACCADE_FEATS,
        'base+content':   BASE + CONTENT_FEATS,
        'base+both':      BASE + SACCADE_FEATS + CONTENT_FEATS,
    }

    print('\n[evaluate] 5-fold CV by participant')
    results: dict = {}
    for label, feats in SETS.items():
        res = evaluate(rows, feats, label)
        results[label] = res
        print(f'  {label:>15s}  features={res["n_features"]:>2}  '
              f'AUC = {res["auc_mean"]:.4f} ± {res["auc_sd"]:.4f}  '
              f'AP = {res["ap_mean"]:.4f}')

    # ΔAUC vs baseline
    base_auc = results['baseline']['auc_mean']
    print('\n[lift over baseline]')
    for label in ('base+saccade', 'base+content', 'base+both'):
        delta = results[label]['auc_mean'] - base_auc
        print(f'  {label:>15s}  ΔAUC = {delta:+.4f}')

    summary = {
        'cohort': {
            'n_rows': len(rows),
            'n_pids': len(pids),
            'n_clicks': n_clk,
            'click_rate': n_clk / len(rows),
        },
        'results': results,
        'lift_vs_baseline': {
            label: {
                'delta_auc': results[label]['auc_mean'] - base_auc,
                'delta_ap':  results[label]['ap_mean']  - results['baseline']['ap_mean'],
            }
            for label in ('base+saccade', 'base+content', 'base+both')
        },
    }
    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Plot: AUC bar + feature importance ─────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5),
                             gridspec_kw=dict(width_ratios=[1, 1.3]))

    # Left: AUC by feature set with error bars
    labels = ['pos_only', 'baseline', 'base+saccade', 'base+content', 'base+both']
    aucs = [results[l]['auc_mean'] for l in labels]
    sds = [results[l]['auc_sd'] for l in labels]
    colors = ['#bbbbbb', '#888888', '#7c4dff', '#cc6677', '#117733']
    axes[0].bar(labels, aucs, yerr=sds, color=colors, alpha=0.75,
                edgecolor='#222222', linewidth=0.7, capsize=4)
    axes[0].set_ylabel('5-fold CV AUC (group: participant)')
    axes[0].set_ylim(min(aucs) - 0.04, max(aucs) + 0.04)
    axes[0].set_title("(A) Click-prediction AUC by feature set\n"
                      f"baseline = position + 14 viewport-trajectory features")
    axes[0].axhline(0.5, color='#222222', lw=0.5, ls='--', alpha=0.6)
    for tick in axes[0].get_xticklabels():
        tick.set_rotation(20)
        tick.set_ha('right')
    for i, (a, s) in enumerate(zip(aucs, sds)):
        axes[0].text(i, a + s + 0.003, f'{a:.4f}', ha='center', fontsize=9)
    axes[0].grid(True, axis='y', alpha=0.5)

    # Right: feature coefficients in the +both model
    full = results['base+both']
    coefs = full['coef_z_mean']
    sorted_feats = sorted(coefs.items(), key=lambda kv: abs(kv[1]),
                          reverse=True)
    feats_to_show = sorted_feats[:18]
    names = [f for f, _ in feats_to_show]
    vals = [v for _, v in feats_to_show]
    feat_colors = []
    for f in names:
        if f in SACCADE_FEATS:
            feat_colors.append('#7c4dff')
        elif f in CONTENT_FEATS:
            feat_colors.append('#cc6677')
        elif f in VIEWPORT_FEATS:
            feat_colors.append('#888888')
        else:
            feat_colors.append('#117733')
    y_idx = np.arange(len(names))[::-1]
    axes[1].barh(y_idx, vals, color=feat_colors, alpha=0.7,
                 edgecolor='#222222', linewidth=0.4)
    axes[1].set_yticks(y_idx)
    axes[1].set_yticklabels(names, fontsize=9)
    axes[1].set_xlabel('logistic coef (z-scored features)')
    axes[1].axvline(0, color='#222222', lw=0.6)
    axes[1].set_title("(B) Top 18 features by |coef| in the +both model")
    axes[1].grid(True, axis='x', alpha=0.5)

    # Legend for colors
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor='#888888', alpha=0.7, label='viewport-trajectory'),
        Patch(facecolor='#7c4dff', alpha=0.7, label='saccade-orientation'),
        Patch(facecolor='#cc6677', alpha=0.7, label='content'),
        Patch(facecolor='#117733', alpha=0.7, label='position'),
    ]
    axes[1].legend(handles=legend_elems, loc='lower right',
                   frameon=True, framealpha=0.92, edgecolor='#cccccc')

    fig.suptitle("Click-prediction ablation — viewport baseline vs +saccade-orientation +content",
                 y=0.995, fontsize=14)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / 'ablation_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'ablation_panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
