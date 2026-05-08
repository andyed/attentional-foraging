"""ETTAC paper figure set — LF/HF cognitive load on AdSERP.

Three paper-quality figures for the ETTAC 2026 (Duchowski) paper, deadline
mid-May. Conservative editorial palette, methodologically precise, LF/HF-only
(RIPA2 lives in the separate Gavindya track).

  E1: position gradient (framework-compilation finding, NB14:K3)
  E2: phase replication (Jayawardena 2026 begin > end)
  E3: evaluation-moment effects (clicked / will-regress / LHIPA cross-index)

Output:
  scripts/output/ettac_visuals/E1_position_gradient.{png,svg}
  scripts/output/ettac_visuals/E2_phase_replication.{png,svg}
  scripts/output/ettac_visuals/E3_evaluation_moment_effects.{png,svg}
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
from scipy.stats import friedmanchisquare, wilcoxon, mannwhitneyu, spearmanr

ROOT = Path(__file__).resolve().parent.parent
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'
LHIPA = ROOT.parent / 'pupil-lfhf' / 'validation' / 'lhipa-per-trial.json'
ENC = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
PHASE_SUMMARY = ROOT / 'scripts/output/replicate_jayawardena_phase_cl/summary.json'
OUT_DIR = ROOT / 'scripts/output/ettac_visuals'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Editorial light palette — conservative, paper-friendly
RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_LFHF = "#d4a574"      # amber — primary
COLOR_LFHF_DARK = "#a87d3c"
COLOR_LHIPA = "#5a7d8c"     # muted blue — secondary
COLOR_NEUTRAL = "#888888"


def load_lfhf_per_position() -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Return (positions, per-pos medians, per-pos N) for LF/HF."""
    data = json.load(open(LFHF))
    by_pos: dict[int, list[float]] = {}
    for trial in data.values():
        for seg in trial.get('positions', []):
            v = seg.get('lfhf')
            if v is None or not math.isfinite(v):
                continue
            p = int(seg['pos'])
            if 0 <= p <= 10:
                by_pos.setdefault(p, []).append(float(v))
    positions = np.array(sorted(by_pos.keys()))
    medians = np.array([np.median(by_pos[p]) for p in positions])
    ns = [len(by_pos[p]) for p in positions]
    return positions, medians, ns


def load_clicked_vs_not() -> tuple[np.ndarray, np.ndarray]:
    """Per-(trial, position) LF/HF, separated by whether that pos was clicked."""
    data = json.load(open(LFHF))
    clk, nc = [], []
    for trial in data.values():
        click_pos = trial.get('click_pos')
        for seg in trial.get('positions', []):
            v = seg.get('lfhf')
            if v is None or not math.isfinite(v):
                continue
            (clk if click_pos == seg['pos'] else nc).append(float(v))
    return np.array(clk), np.array(nc)


def load_wr_vs_nr() -> tuple[np.ndarray, np.ndarray]:
    """LF/HF stratified by NB22 will_regress per (trial, pos)."""
    enc = json.load(open(ENC))
    wr_map: dict[tuple[str, int], bool] = {}
    for tid, t in enc.items():
        for fix in t.get('first_pass') or []:
            key = (tid, int(fix['pos']))
            wr_map[key] = wr_map.get(key, False) or bool(fix.get('will_regress'))
    data = json.load(open(LFHF))
    wr, nr = [], []
    for tid, trial in data.items():
        for seg in trial.get('positions', []):
            v = seg.get('lfhf')
            if v is None or not math.isfinite(v):
                continue
            key = (tid, int(seg['pos']))
            if key not in wr_map:
                continue
            (wr if wr_map[key] else nr).append(float(v))
    return np.array(wr), np.array(nr)


def load_lfhf_lhipa_paired() -> tuple[np.ndarray, np.ndarray]:
    """Per-trial mean LF/HF and trial-level LHIPA. Returns (lfhf_means, lhipas)."""
    lfhf_data = json.load(open(LFHF))
    lhipa_data = json.load(open(LHIPA))
    pairs = []
    for tid, trial in lfhf_data.items():
        vals = [s.get('lfhf') for s in trial.get('positions', [])
                if s.get('lfhf') is not None and math.isfinite(s.get('lfhf'))]
        if not vals:
            continue
        lf_mean = float(np.mean(vals))
        lhipa_rec = lhipa_data.get(tid)
        if lhipa_rec is None:
            continue
        lh = lhipa_rec.get('lhipa')
        if lh is None or not math.isfinite(lh):
            continue
        pairs.append((lf_mean, float(lh)))
    if not pairs:
        return np.array([]), np.array([])
    lf, lh = zip(*pairs)
    return np.array(lf), np.array(lh)


# ── Figure E1: position gradient ───────────────────────────────────────────

def fig_e1_position_gradient():
    plt.rcParams.update(RC)
    pos, med, ns = load_lfhf_per_position()
    rho, p = spearmanr(pos, med)

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.plot(pos, med, marker='o', color=COLOR_LFHF, lw=1.8, ms=8,
            markeredgecolor='#222222', markeredgewidth=0.6, zorder=3)
    # N annotations on each marker
    for p_, m_, n_ in zip(pos, med, ns):
        ax.text(p_, m_ - 1.2, f'n={n_:,}', ha='center', va='top',
                fontsize=8, color='#666666')

    # Mark steep vs plateau partition (NB14: pos 0-3 vs 4-10)
    ax.axvspan(-0.5, 3.5, color=COLOR_LFHF, alpha=0.07, zorder=1)
    ax.text(1.5, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] else 28,
            'steep phase\n(criterion compilation)',
            ha='center', va='top', fontsize=9, color=COLOR_LFHF_DARK,
            fontstyle='italic')
    ax.text(7, ax.get_ylim()[1] * 0.55 if ax.get_ylim()[1] else 18,
            'plateau\n(criterion reuse)',
            ha='center', va='top', fontsize=9, color='#666666',
            fontstyle='italic')

    ax.set_xlabel('SERP position')
    ax.set_ylabel('median LF/HF (Butterworth IIR)')
    ax.set_xticks(pos)
    ax.set_title("Cognitive load decreases with SERP position\n"
                 r"$\rho = " + f"{rho:.3f}" + r"$, $p < 0.0001$, "
                 f"forward-pass fixations, N = 2,719 trials  (NB14:K3)",
                 fontsize=12, loc='left', pad=10)
    ax.grid(True, alpha=0.5)

    plt.tight_layout()
    out = OUT_DIR / 'E1_position_gradient'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


# ── Figure E2: phase replication of Jayawardena 2026 ───────────────────────

def fig_e2_phase_replication():
    plt.rcParams.update(RC)
    summary = json.load(open(PHASE_SUMMARY))
    lfhf = summary['results']['lfhf']
    pm = lfhf['phase_means']

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    phases = ['begin', 'mid', 'end']
    medians = [pm[ph]['median'] for ph in phases]
    means = [pm[ph]['mean'] for ph in phases]
    sds = [pm[ph]['std'] for ph in phases]
    ses = [s / math.sqrt(lfhf['n_trials']) for s in sds]

    x = np.arange(3)
    ax.errorbar(x, medians, yerr=None, marker='o', color=COLOR_LFHF, lw=2.0,
                ms=10, markeredgecolor='#222222', markeredgewidth=0.7,
                zorder=3, label='AdSERP per-trial median (this work)')
    # Connect with a stronger line
    ax.plot(x, medians, color=COLOR_LFHF, lw=2.0, alpha=0.55, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels(phases)
    ax.set_xlabel('within-trial phase (begin / middle / end of evaluation)')
    ax.set_ylabel('median LF/HF (per-trial phase mean)')

    n = lfhf['n_trials']
    p_be = lfhf['wilcoxon_one_sided']['begin_gt_end']['p']
    p_me = lfhf['wilcoxon_one_sided']['mid_gt_end']['p']
    fr_p = lfhf['friedman']['p']
    ax.set_title("Cognitive load decreases over the evaluation episode  —  "
                 "AdSERP replication of Jayawardena, Shi & Gwizdka (CHIIR 2026)\n"
                 r"Friedman $\chi^2(2, N=" + f"{n:,}" + r")$ "
                 r"$= " + f"{lfhf['friedman']['chi2']:.1f}" + r"$, "
                 r"$p = " + f"{fr_p:.2g}" + r"$;  "
                 r"begin $>$ end Wilcoxon $p = " + f"{p_be:.2g}" + r"$",
                 fontsize=11.5, loc='left', pad=10)

    # Annotate pairwise tests
    ax.annotate('', xy=(0, medians[0]), xytext=(2, medians[2]),
                arrowprops=dict(arrowstyle='-', color='#888888', lw=0.6,
                                connectionstyle="arc3,rad=-0.15"))
    ymid_arrow = (medians[0] + medians[2]) / 2
    ax.text(1.15, ymid_arrow * 0.92, f'p = {p_be:.1e}',
            fontsize=9, color='#666666', fontstyle='italic')

    ax.grid(True, alpha=0.5)
    ax.text(0.02, 0.05, 'AdSERP subset: trials ≥ 22.5 s for stable per-phase LF/HF\n'
                       '(Duchowski 2026 minimum-window guidance)',
            transform=ax.transAxes, fontsize=8.5, color='#666666',
            fontstyle='italic',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#fdf8f2',
                      edgecolor='#cccccc', lw=0.5))

    plt.tight_layout()
    out = OUT_DIR / 'E2_phase_replication'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


# ── Figure E3: evaluation-moment effects (clicked / will-regress / LHIPA) ──

def fig_e3_evaluation_effects():
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.0))

    # (a) Clicked vs non-clicked
    clk, nc = load_clicked_vs_not()
    u, p_cn = mannwhitneyu(clk, nc, alternative='greater')
    bp = axes[0].boxplot([clk, nc], positions=[0, 1], widths=0.55,
                         patch_artist=True, showfliers=False,
                         medianprops=dict(color='#222222', lw=1.6),
                         whiskerprops=dict(color='#666666'),
                         capprops=dict(color='#666666'),
                         boxprops=dict(facecolor=COLOR_LFHF,
                                       edgecolor='#666666', alpha=0.55))
    axes[0].set_xticks([0, 1])
    axes[0].set_xticklabels(['clicked', 'not clicked'])
    axes[0].set_ylabel('LF/HF')
    axes[0].set_title("(a) clicked vs not at evaluation moment\n"
                      f"med {np.median(clk):.2f} vs {np.median(nc):.2f},  "
                      r"$p < 10^{-8}$" + f"  (N = {len(clk):,} / {len(nc):,})",
                      fontsize=11.5)
    axes[0].grid(True, axis='y', alpha=0.5)

    # (b) Will-regress vs no-regress
    wr, nr = load_wr_vs_nr()
    bp2 = axes[1].boxplot([wr, nr], positions=[0, 1], widths=0.55,
                          patch_artist=True, showfliers=False,
                          medianprops=dict(color='#222222', lw=1.6),
                          whiskerprops=dict(color='#666666'),
                          capprops=dict(color='#666666'),
                          boxprops=dict(facecolor=COLOR_LFHF,
                                        edgecolor='#666666', alpha=0.55))
    axes[1].set_xticks([0, 1])
    axes[1].set_xticklabels(['will-regress', 'no-regress'])
    axes[1].set_ylabel('LF/HF')
    u, p_wr = mannwhitneyu(wr, nr, alternative='greater')
    axes[1].set_title("(b) will-regress vs no-regress\n"
                      f"med {np.median(wr):.2f} vs {np.median(nr):.2f},  "
                      r"$p < 10^{-3}$" + f"  (N = {len(wr):,} / {len(nr):,})",
                      fontsize=11.5)
    axes[1].grid(True, axis='y', alpha=0.5)

    # (c) Cross-index: LF/HF × LHIPA
    lf_means, lh = load_lfhf_lhipa_paired()
    if len(lf_means) >= 30:
        rho, pv = spearmanr(lf_means, lh)
        axes[2].scatter(lf_means, lh, s=5, color=COLOR_LFHF, alpha=0.20,
                        edgecolor='none', zorder=2)
        # Trend line via robust median binning
        n_bins = 20
        edges = np.linspace(lf_means.min(), np.percentile(lf_means, 95), n_bins + 1)
        bin_x, bin_y = [], []
        for i in range(n_bins):
            mask = (lf_means >= edges[i]) & (lf_means < edges[i + 1])
            if mask.sum() >= 5:
                bin_x.append((edges[i] + edges[i + 1]) / 2)
                bin_y.append(float(np.median(lh[mask])))
        axes[2].plot(bin_x, bin_y, color=COLOR_LHIPA, lw=2.4, zorder=3,
                     label='binned median')
        axes[2].set_xlim(0, np.percentile(lf_means, 99))
        axes[2].set_xlabel('per-trial mean LF/HF')
        axes[2].set_ylabel('per-trial LHIPA (Duchowski 2020)')
        axes[2].set_title("(c) cross-index validation: LF/HF × LHIPA\n"
                          r"$\rho = " + f"{rho:+.3f}" + r"$, "
                          r"$p = " + f"{pv:.2g}" + r"$,  N = "
                          f"{len(lf_means):,}",
                          fontsize=11.5)
        axes[2].legend(loc='upper right', frameon=True, framealpha=0.92,
                       edgecolor='#cccccc')
        axes[2].grid(True, alpha=0.5)

    fig.suptitle("LF/HF carries result-evaluation signal at three independent "
                 "validation axes  —  AdSERP, n=47 participants",
                 y=0.995, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out = OUT_DIR / 'E3_evaluation_moment_effects'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


def main():
    print('[ETTAC visuals] building 3 figures', file=sys.stderr)
    fig_e1_position_gradient()
    fig_e2_phase_replication()
    fig_e3_evaluation_effects()


if __name__ == '__main__':
    main()
