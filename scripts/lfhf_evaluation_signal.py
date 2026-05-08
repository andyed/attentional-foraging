"""LF/HF at per-(trial, position) evaluation moments — does it respond to
content richness and engagement at the result level?

NB14:K6 already shows LF/HF clicked > non-clicked at result level (p < 10⁻⁸).
This script extends the picture: does LF/HF at the evaluation moment also
track:
  (a) snippet content richness (TTR, query-overlap, embedding similarity)
  (b) engagement signature (frac_horizontal, n_saccades)
  (c) NB22 will-regress label
And how does it compare to RIPA2 at the same granularity?

Tests at per-(trial, position):
  - Spearman ρ for LF/HF × each content feature (pooled and partial | position)
  - Spearman ρ for LF/HF × engagement features
  - Mann-Whitney for LF/HF × {clicked, will_regress}
  - Same tests for RIPA2 to show side-by-side scope difference

Output:
  scripts/output/lfhf_evaluation_signal/summary.json
  scripts/output/lfhf_evaluation_signal/comparison_panel.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, rankdata, t as tdist, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'
SACCADE = ROOT / 'AdSERP/data/saccade-orientation-by-position.json'
CONTENT = ROOT / 'AdSERP/data/content-features-by-position.json'
ENC = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
OUT_DIR = ROOT / 'scripts/output/lfhf_evaluation_signal'
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONTENT_FEATS = [
    'snippet_tokens', 'snippet_ttr',
    'q_overlap_count', 'q_overlap_jaccard',
    'q_text_cosine',
]
ENGAGEMENT_FEATS = ['frac_horizontal', 'max_horizontal_run', 'n_saccades']

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
COLOR_LFHF = "#d4a574"
COLOR_RIPA2 = "#7c4dff"


def partial_rank_spearman(x: np.ndarray, y: np.ndarray, z: np.ndarray
                          ) -> tuple[float, float]:
    rx = rankdata(x).astype(float)
    ry = rankdata(y).astype(float)
    rz = rankdata(z).astype(float)
    Z = np.column_stack([np.ones(len(x)), rz])
    bx, *_ = np.linalg.lstsq(Z, rx, rcond=None)
    by, *_ = np.linalg.lstsq(Z, ry, rcond=None)
    rx_r = rx - Z @ bx
    ry_r = ry - Z @ by
    if rx_r.std() == 0 or ry_r.std() == 0:
        return float('nan'), float('nan')
    rho = float(np.corrcoef(rx_r, ry_r)[0, 1])
    n = len(x)
    if abs(rho) >= 1 or n < 5:
        return rho, 0.0
    t = rho * math.sqrt((n - 3) / max(1 - rho ** 2, 1e-12))
    p = float(2 * (1 - tdist.cdf(abs(t), df=n - 3)))
    return rho, p


def main() -> None:
    print('[load] LF/HF + RIPA2 + saccade + content + encoding caches', file=sys.stderr)
    lfhf = json.load(open(LFHF))
    ripa2 = json.load(open(RIPA2))
    saccade = json.load(open(SACCADE))
    content = json.load(open(CONTENT))
    enc = json.load(open(ENC))

    # Build will_regress map (per (trial, pos) — any first-pass fixation marked
    # will_regress)
    wr_map: dict[tuple[str, int], bool] = {}
    for tid, trial in enc.items():
        for fix in trial.get('first_pass') or []:
            key = (tid, int(fix['pos']))
            wr_map[key] = wr_map.get(key, False) or bool(fix.get('will_regress'))

    rows: list[dict] = []
    for tid, lblock in lfhf.items():
        rblock = ripa2.get(tid, {})
        sblock = saccade.get(tid, {})
        cblock = content.get(tid, {})
        click_pos = lblock.get('click_pos')

        ripa2_by_pos = {p['pos']: p['ripa2'] for p in rblock.get('positions', [])
                        if p.get('ripa2') is not None}
        sacc_by_pos = {p['pos']: p for p in sblock.get('positions', [])}
        cont_by_pos = {p['pos']: p for p in cblock.get('positions', [])}

        for lp in lblock.get('positions', []):
            pos = int(lp['pos'])
            lv = lp.get('lfhf')
            if lv is None or not math.isfinite(lv):
                continue
            row = {'tid': tid, 'pid': tid.split('-')[0], 'pos': pos,
                   'lfhf': float(lv),
                   'ripa2': ripa2_by_pos.get(pos, float('nan')),
                   'clicked': int(click_pos == pos) if click_pos is not None else 0,
                   'will_regress': int(wr_map.get((tid, pos), False)),
                   }
            sp = sacc_by_pos.get(pos, {})
            for k in ENGAGEMENT_FEATS:
                v = sp.get(k, float('nan'))
                if v == float('inf'):
                    v = 100.0
                row[k] = float(v) if v == v else float('nan')
            cp = cont_by_pos.get(pos, {})
            for k in CONTENT_FEATS:
                v = cp.get(k, float('nan'))
                row[k] = float(v) if v == v else float('nan')
            rows.append(row)

    print(f'  {len(rows):,} (trial, pos) rows with valid LF/HF', file=sys.stderr)
    n_clk = sum(r['clicked'] for r in rows)
    print(f'  click positions: {n_clk:,}  ({100*n_clk/len(rows):.1f}%)', file=sys.stderr)

    summary = {'n_rows': len(rows), 'n_clicked': n_clk}

    # ── (1) Outcome: clicked vs non-clicked ──────────────────────────
    print('\n=== (1) Outcome: clicked vs non-clicked at per-(trial, pos) evaluation moment ===')
    for metric_name in ('lfhf', 'ripa2'):
        clk = np.array([r[metric_name] for r in rows
                        if r['clicked'] == 1 and r[metric_name] == r[metric_name]])
        nc  = np.array([r[metric_name] for r in rows
                        if r['clicked'] == 0 and r[metric_name] == r[metric_name]])
        if len(clk) < 5 or len(nc) < 5:
            continue
        u, p = mannwhitneyu(clk, nc, alternative='two-sided')
        delta = float(np.median(clk) - np.median(nc))
        print(f'  {metric_name.upper():>5s}  med_clk = {np.median(clk):.4f}  '
              f'med_not = {np.median(nc):.4f}  Δ = {delta:+.4f}  '
              f'N = {len(clk):,}/{len(nc):,}  MW p = {p:.3g}')
        summary[f'{metric_name}_outcome'] = {
            'median_clicked': float(np.median(clk)),
            'median_notclicked': float(np.median(nc)),
            'delta': delta,
            'n_clicked': int(len(clk)), 'n_notclicked': int(len(nc)),
            'mw_p': float(p),
        }

    # ── (2) Will-regress vs no-regress ────────────────────────────────
    print('\n=== (2) Will-regress (NB22 label) vs no-regress at evaluation moment ===')
    for metric_name in ('lfhf', 'ripa2'):
        wr = np.array([r[metric_name] for r in rows
                       if r['will_regress'] == 1 and r[metric_name] == r[metric_name]])
        nr = np.array([r[metric_name] for r in rows
                       if r['will_regress'] == 0 and r[metric_name] == r[metric_name]])
        if len(wr) < 5 or len(nr) < 5:
            continue
        u, p = mannwhitneyu(wr, nr, alternative='two-sided')
        delta = float(np.median(wr) - np.median(nr))
        print(f'  {metric_name.upper():>5s}  med_wr = {np.median(wr):.4f}  '
              f'med_nr = {np.median(nr):.4f}  Δ = {delta:+.4f}  '
              f'N = {len(wr):,}/{len(nr):,}  MW p = {p:.3g}')
        summary[f'{metric_name}_wr_vs_nr'] = {
            'median_wr': float(np.median(wr)),
            'median_nr': float(np.median(nr)),
            'delta': delta,
            'n_wr': int(len(wr)), 'n_nr': int(len(nr)),
            'mw_p': float(p),
        }

    # ── (3) Content + engagement correlations (pooled & partial | position) ─
    print('\n=== (3) Content & engagement × LF/HF (and × RIPA2 for comparison) ===')
    print(f'{"feature":>22s}  {"metric":>6s}  {"pool ρ":>8s}  {"p":>9s}  '
          f'{"part|pos ρ":>11s}  {"p":>9s}')

    for feat in CONTENT_FEATS + ENGAGEMENT_FEATS:
        for metric_name, color in [('lfhf', COLOR_LFHF), ('ripa2', COLOR_RIPA2)]:
            x = np.array([r[feat] for r in rows], dtype=float)
            y = np.array([r[metric_name] for r in rows], dtype=float)
            z = np.array([r['pos'] for r in rows], dtype=float)
            valid = ~(np.isnan(x) | np.isnan(y))
            if valid.sum() < 50 or np.std(x[valid]) == 0:
                continue
            rho_p, pv_p = spearmanr(x[valid], y[valid])
            rho_part, pv_part = partial_rank_spearman(x[valid], y[valid], z[valid])
            print(f'{feat:>22s}  {metric_name:>6s}  '
                  f'{rho_p:>+8.4f}  {pv_p:>9.2g}  '
                  f'{rho_part:>+11.4f}  {pv_part:>9.2g}')
            key = f'{metric_name}_x_{feat}'
            summary.setdefault('correlations', {})[key] = {
                'n': int(valid.sum()),
                'pooled_rho': float(rho_p), 'pooled_p': float(pv_p),
                'partial_pos_rho': float(rho_part), 'partial_pos_p': float(pv_part),
            }

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Visualization: side-by-side correlation table ──────────────────
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(12, 6))

    feats = CONTENT_FEATS + ENGAGEMENT_FEATS
    y_idx = np.arange(len(feats))
    width = 0.4

    lfhf_vals = []
    ripa2_vals = []
    lfhf_ps = []
    ripa2_ps = []
    for feat in feats:
        l = summary.get('correlations', {}).get(f'lfhf_x_{feat}', {})
        r = summary.get('correlations', {}).get(f'ripa2_x_{feat}', {})
        lfhf_vals.append(l.get('partial_pos_rho', 0))
        ripa2_vals.append(r.get('partial_pos_rho', 0))
        lfhf_ps.append(l.get('partial_pos_p', 1))
        ripa2_ps.append(r.get('partial_pos_p', 1))

    ax.barh(y_idx - width/2, lfhf_vals, height=width, color=COLOR_LFHF,
            alpha=0.75, edgecolor='#222222', linewidth=0.4, label='LF/HF')
    ax.barh(y_idx + width/2, ripa2_vals, height=width, color=COLOR_RIPA2,
            alpha=0.75, edgecolor='#222222', linewidth=0.4, label='RIPA2')
    ax.set_yticks(y_idx)
    ax.set_yticklabels(feats, fontsize=10)
    ax.invert_yaxis()
    ax.axvline(0, color='#222222', lw=0.6)
    ax.set_xlabel('partial Spearman ρ | position')
    ax.set_title("Per-(trial, position) evaluation-moment signal — LF/HF vs RIPA2 across content & engagement features\n"
                 "(content top, engagement bottom; partial-residualized on position)",
                 fontsize=12)
    ax.legend(loc='lower right', frameon=True, framealpha=0.92, edgecolor='#cccccc')
    ax.grid(True, axis='x', alpha=0.5)

    # Mark significance
    for i, (lp, rp) in enumerate(zip(lfhf_ps, ripa2_ps)):
        for off, p, val in [(-width/2, lp, lfhf_vals[i]), (width/2, rp, ripa2_vals[i])]:
            mark = '*' if p < 0.05 else ''
            if mark:
                ax.text(val + (0.001 if val >= 0 else -0.001), i + off,
                        mark, fontsize=12, color='#222222',
                        ha='left' if val >= 0 else 'right', va='center')

    # Section divider
    ax.axhline(len(CONTENT_FEATS) - 0.5, color='#aaaaaa', lw=0.5, ls=':')
    ax.text(0.98, len(CONTENT_FEATS)/2 - 0.5, 'content', transform=ax.get_yaxis_transform(),
            ha='right', va='center', fontsize=9, color='#888888', fontstyle='italic')
    ax.text(0.98, (len(CONTENT_FEATS) + len(feats))/2 - 0.5,
            'engagement', transform=ax.get_yaxis_transform(),
            ha='right', va='center', fontsize=9, color='#888888', fontstyle='italic')

    plt.tight_layout()
    out_png = OUT_DIR / 'comparison_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'comparison_panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
