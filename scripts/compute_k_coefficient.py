"""Compute Krejtz et al. 2016 ambient/focal K coefficient on AdSERP.

K[t_i] = z(FD_i) − z(SA_i)

where FD = fixation duration, SA = next saccade amplitude.
  K < 0 → ambient attention (short FD + long SA, broad scanning)
  K > 0 → focal attention (long FD + short SA, deep examination)

Per Jayawardena et al. (ETRA 2025): T1→T5 time segments show ambient→focal
shift on map-viewing tasks. We test the same dynamic on SERP-side AdSERP
trials at the position level (does K shift ambient → focal across SERP
positions?) and test cross-validation with LF/HF position gradient.

Methodology:
  - Forward-pass fixations only (matches NB14:K3 / NB18 framework)
  - z-scores computed per participant (typical convention for individual-
    differences analysis; pools all forward-pass fixations within participant)
  - SA computed as Euclidean distance to next fixation (page-space, since
    AdSERP FPOG is page-space)
  - Aggregate per (trial, position) as mean K across forward-pass fixations
    at that position

Outputs:
  AdSERP/data/k-coefficient-by-position.json
  scripts/output/k_coefficient/summary.json
  scripts/output/k_coefficient/position_gradient.png
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_fixations,
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)
# organic_aoi_tops lives in notebooks-v2/data_loader (post-2026-05-01 cascade);
# pupil-lfhf's loader is the legacy absolute-attribution path.
from data_loader import organic_aoi_tops, typed_aoi_tops  # noqa: E402
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402


def resolve_paths(attribution: str) -> tuple[Path, Path, Path, str]:
    """Return (lfhf_path, ripa2_path, out_by_pos_path, suffix) for attribution."""
    if attribution == 'organic':
        return (
            ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json',
            ROOT / 'AdSERP/data/ripa2-by-position-organic.json',
            ROOT / 'AdSERP/data/k-coefficient-by-position-organic.json',
            '_organic',
        )
    if attribution == 'organic_hybrid':
        return (
            ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json',
            ROOT / 'AdSERP/data/ripa2-by-position-organic.json',
            ROOT / 'AdSERP/data/k-coefficient-by-position-organic-hybrid.json',
            '_organic_hybrid',
        )
    if attribution == 'typed':
        return (
            ROOT / 'AdSERP/data/butterworth-lfhf-by-position-typed.json',
            ROOT / 'AdSERP/data/ripa2-by-position-typed.json',
            ROOT / 'AdSERP/data/k-coefficient-by-position-typed.json',
            '_typed',
        )
    return (
        ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json',
        ROOT / 'AdSERP/data/ripa2-by-position.json',
        ROOT / 'AdSERP/data/k-coefficient-by-position.json',
        '',
    )


OUT_DIR = ROOT / 'scripts/output/k_coefficient'
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
COLOR_K = "#5a7d8c"          # cool blue for K
COLOR_LFHF = "#d4a574"       # amber
COLOR_AMBIENT = "#2980b9"
COLOR_FOCAL = "#c0392b"


def forward_pass_indices(fixations: list[dict], tops, n_results: int
                         ) -> dict[int, list[int]]:
    """Return per-position list of fixation indices in the forward-pass run.

    A fixation belongs to forward-pass at position p if pos == high_water at
    that moment, matching pupil-lfhf identify_forward_pass logic."""
    by_pos: dict[int, list[int]] = defaultdict(list)
    high_water = -1
    for idx, f in enumerate(fixations):
        p = assign_fixation_to_position(f['y'], tops, n_results)
        if p is None or p < 0 or p >= n_results:
            continue
        if p >= high_water:
            high_water = p
            by_pos[int(p)].append(idx)
    return by_pos


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--attribution', choices=['absolute', 'organic', 'organic_hybrid', 'typed'], default='organic',
                    help='organic (default; bbox-attributed) or absolute (legacy h3+ads pooled)')
    args = ap.parse_args()
    global LFHF, RIPA2, OUT_BY_POS, _OUT_SUFFIX
    LFHF, RIPA2, OUT_BY_POS, _OUT_SUFFIX = resolve_paths(args.attribution)
    print(f'[attribution] {args.attribution}', file=sys.stderr)
    print(f'  LF/HF input : {LFHF.name}', file=sys.stderr)
    print(f'  RIPA2 input : {RIPA2.name}', file=sys.stderr)
    print(f'  K output    : {OUT_BY_POS.name}', file=sys.stderr)

    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    # Pass 1: collect FD and SA per participant for z-score normalization
    pid_fd: dict[str, list[float]] = defaultdict(list)
    pid_sa: dict[str, list[float]] = defaultdict(list)
    # Per-trial collection — keep so we can compute K per (trial, fix) in pass 2
    trial_records: list[tuple[str, list[dict], dict]] = []  # (tid, fixs, fwd_idx)

    n_skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  pass-1: {i+1}/{len(trial_ids)}', file=sys.stderr)
        fixations = load_fixations(tid)
        if not fixations or len(fixations) < 2:
            n_skipped += 1
            continue
        if args.attribution == 'organic':
            tops = organic_aoi_tops(tid)
        elif args.attribution == 'organic_hybrid':
            tops = _hybrid_aoi_tops(tid)
        elif args.attribution == 'typed':
            tops = typed_aoi_tops(tid)
            n_results = len(tops)
            if n_results == 0:
                n_skipped += 1
                continue
        else:
            n_results = count_results_html(tid) or 11
            doc_h, _, _ = get_trial_meta(tid)
            if doc_h is None:
                n_skipped += 1
                continue
            tops = result_band_tops(n_results, doc_h)
        fwd_idx = forward_pass_indices(fixations, tops, n_results)
        if not fwd_idx:
            continue

        pid = tid.split('-')[0]
        for pos_idxs in fwd_idx.values():
            for idx in pos_idxs:
                fd = float(fixations[idx]['d'])  # ms
                if idx + 1 < len(fixations):
                    nxt = fixations[idx + 1]
                    sa = math.hypot(nxt['x'] - fixations[idx]['x'],
                                    nxt['y'] - fixations[idx]['y'])
                    pid_sa[pid].append(sa)
                pid_fd[pid].append(fd)

        trial_records.append((tid, fixations, fwd_idx))

    print(f'  pass-1 done: {len(trial_records):,} trials kept  '
          f'({n_skipped} skipped)', file=sys.stderr)

    # Per-participant z-score parameters
    pid_params: dict[str, dict] = {}
    for pid in pid_fd:
        if len(pid_fd[pid]) < 30 or len(pid_sa[pid]) < 30:
            continue
        pid_params[pid] = {
            'mu_fd': float(np.mean(pid_fd[pid])),
            'sd_fd': float(np.std(pid_fd[pid], ddof=1)),
            'mu_sa': float(np.mean(pid_sa[pid])),
            'sd_sa': float(np.std(pid_sa[pid], ddof=1)),
            'n_fd': len(pid_fd[pid]),
            'n_sa': len(pid_sa[pid]),
        }
    print(f'  participants with z-score params: {len(pid_params)}', file=sys.stderr)

    # Pass 2: compute K per (trial, position) as mean K over forward-pass fixations
    by_trial: dict[str, dict] = {}
    for tid, fixations, fwd_idx in trial_records:
        pid = tid.split('-')[0]
        params = pid_params.get(pid)
        if params is None:
            continue
        positions = []
        for pos in sorted(fwd_idx.keys()):
            ks: list[float] = []
            for idx in fwd_idx[pos]:
                fd = float(fixations[idx]['d'])
                if idx + 1 >= len(fixations):
                    continue
                nxt = fixations[idx + 1]
                sa = math.hypot(nxt['x'] - fixations[idx]['x'],
                                nxt['y'] - fixations[idx]['y'])
                z_fd = (fd - params['mu_fd']) / max(params['sd_fd'], 1e-9)
                z_sa = (sa - params['mu_sa']) / max(params['sd_sa'], 1e-9)
                ks.append(z_fd - z_sa)
            if not ks:
                continue
            positions.append({
                'pos': int(pos),
                'k_mean': float(np.mean(ks)),
                'k_median': float(np.median(ks)),
                'n_fixations': len(ks),
            })
        if positions:
            by_trial[tid] = {'pid': pid, 'positions': positions}

    print(f'  pass-2 done: {len(by_trial):,} trials with K values', file=sys.stderr)
    OUT_BY_POS.write_text(json.dumps(by_trial, indent=2))
    print(f'[out] {OUT_BY_POS.relative_to(ROOT)}', file=sys.stderr)

    # ── Position gradient ──────────────────────────────────────────────
    by_pos: dict[int, list[float]] = defaultdict(list)
    for trial in by_trial.values():
        for entry in trial['positions']:
            by_pos[entry['pos']].append(entry['k_mean'])

    sorted_positions = sorted(by_pos.keys())
    medians = [float(np.median(by_pos[p])) for p in sorted_positions]
    means = [float(np.mean(by_pos[p])) for p in sorted_positions]
    ns = [len(by_pos[p]) for p in sorted_positions]

    rho_med, p_med = spearmanr(sorted_positions, medians)
    rho_mean, p_mean = spearmanr(sorted_positions, means)

    print('\n=== K position gradient ===')
    print(f'{"pos":>4s}  {"median K":>10s}  {"mean K":>10s}  {"n":>6s}  {"interpretation":<20s}')
    for p, m, mn, n in zip(sorted_positions, medians, means, ns):
        interp = 'ambient' if m < 0 else 'focal'
        print(f'{p:>4d}  {m:>+10.3f}  {mn:>+10.3f}  {n:>6,}  {interp:<20s}')
    print(f'\n  Spearman ρ (position × median K) = {rho_med:+.3f}, p = {p_med:.3g}')
    print(f'  Spearman ρ (position × mean K)   = {rho_mean:+.3f}, p = {p_mean:.3g}')

    # ── Cross-validate with LF/HF position gradient ────────────────────
    lfhf = json.load(open(LFHF))
    lfhf_by_pos: dict[int, list[float]] = defaultdict(list)
    for trial in lfhf.values():
        for seg in trial.get('positions', []):
            v = seg.get('lfhf')
            if v is not None and math.isfinite(v):
                lfhf_by_pos[int(seg['pos'])].append(float(v))
    common = sorted(set(by_pos.keys()) & set(lfhf_by_pos.keys()))
    k_means = [float(np.median(by_pos[p])) for p in common]
    lfhf_means = [float(np.median(lfhf_by_pos[p])) for p in common]
    rho_kl, p_kl = spearmanr(k_means, lfhf_means)
    print(f'\n  K × LF/HF (per-position median × median, N = {len(common)} positions): '
          f'Spearman ρ = {rho_kl:+.3f}, p = {p_kl:.3g}')

    # ── Clicked vs non-clicked K ───────────────────────────────────────
    rcache = json.load(open(RIPA2))
    clk, nc = [], []
    for tid, trial in by_trial.items():
        click_pos = rcache.get(tid, {}).get('click_pos')
        if click_pos is None:
            continue
        for entry in trial['positions']:
            (clk if entry['pos'] == click_pos else nc).append(entry['k_mean'])
    if clk and nc:
        u, p = mannwhitneyu(clk, nc, alternative='two-sided')
        rrb = 2 * u / (len(clk) * len(nc)) - 1
        print(f'\n=== K at clicked vs non-clicked positions ===')
        print(f'  med_clk = {np.median(clk):+.3f}  med_not = {np.median(nc):+.3f}  '
              f'Δ = {np.median(clk) - np.median(nc):+.3f}  '
              f'N = {len(clk):,} / {len(nc):,}  '
              f'MW p = {p:.3g}  rank-biserial r = {rrb:+.3f}')

    summary = {
        'cohort': {'n_trials': len(by_trial),
                   'n_pids': len(pid_params),
                   'n_total_positions': sum(ns)},
        'per_position': {
            str(p): {'median': m, 'mean': mn, 'n': n}
            for p, m, mn, n in zip(sorted_positions, medians, means, ns)
        },
        'position_gradient': {
            'rho_median_K': float(rho_med), 'p_median_K': float(p_med),
            'rho_mean_K':   float(rho_mean), 'p_mean_K':   float(p_mean),
        },
        'k_x_lfhf_position_correlation': {
            'rho': float(rho_kl), 'p': float(p_kl), 'n_positions': len(common),
        },
    }
    if clk and nc:
        summary['clicked_vs_not'] = {
            'median_clicked': float(np.median(clk)),
            'median_notclicked': float(np.median(nc)),
            'delta': float(np.median(clk) - np.median(nc)),
            'n_clicked': len(clk),
            'n_notclicked': len(nc),
            'mw_p': float(p),
            'rank_biserial_r': float(rrb),
        }
    summary_path = OUT_DIR / f'summary{_OUT_SUFFIX}.json'
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {summary_path.relative_to(ROOT)}', file=sys.stderr)

    # ── Plot ───────────────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5))

    # Left: K position gradient
    color_by_dir = [COLOR_AMBIENT if m < 0 else COLOR_FOCAL for m in medians]
    axes[0].plot(sorted_positions, medians, marker='o', color=COLOR_K,
                 lw=2.0, ms=8, markeredgecolor='#222222', markeredgewidth=0.5)
    axes[0].axhline(0, color='#222222', lw=0.6, ls='--', alpha=0.6)
    axes[0].fill_between(sorted_positions, medians, 0, where=[m < 0 for m in medians],
                         color=COLOR_AMBIENT, alpha=0.10, label='ambient (K < 0)')
    axes[0].fill_between(sorted_positions, medians, 0, where=[m >= 0 for m in medians],
                         color=COLOR_FOCAL, alpha=0.10, label='focal (K ≥ 0)')
    for p, m, n in zip(sorted_positions, medians, ns):
        axes[0].text(p, m + (0.02 if m >= 0 else -0.04), f'n={n:,}',
                     ha='center', va='bottom' if m >= 0 else 'top',
                     fontsize=8, color='#666666')
    axes[0].set_xlabel('SERP position')
    axes[0].set_ylabel('median K (per-(trial, pos))')
    axes[0].set_title("(A) K position gradient on AdSERP\n"
                      r"$\rho = " + f"{rho_med:+.3f}" + r"$, "
                      r"$p = " + f"{p_med:.2g}" + r"$  —  "
                      f"forward-pass fixations, per-pid z-scores",
                      fontsize=11)
    axes[0].set_xticks(sorted_positions)
    axes[0].grid(True, alpha=0.5)
    axes[0].legend(loc='upper right', frameon=True, framealpha=0.92,
                   edgecolor='#cccccc')

    # Right: K vs LF/HF correlation across positions
    axes[1].scatter(k_means, lfhf_means, s=80, color=COLOR_K, edgecolor='#222222',
                    linewidth=0.6, zorder=3)
    for p, k_m, l_m in zip(common, k_means, lfhf_means):
        axes[1].annotate(f'P{p}', xy=(k_m, l_m), xytext=(5, 5),
                         textcoords='offset points', fontsize=9, color='#444444')
    axes[1].set_xlabel('per-position median K')
    axes[1].set_ylabel('per-position median LF/HF')
    axes[1].set_title("(B) K × LF/HF position gradient cross-validation\n"
                      r"$\rho = " + f"{rho_kl:+.3f}" + r"$, "
                      r"$p = " + f"{p_kl:.2g}" + r"$,  "
                      f"N = {len(common)} positions",
                      fontsize=11)
    axes[1].grid(True, alpha=0.5)
    axes[1].axvline(0, color='#222222', lw=0.4, ls='--', alpha=0.4)

    fig.suptitle("Krejtz K (ambient/focal coefficient) on AdSERP  —  bridging Jayawardena ETRA 2025 "
                 "to our LF/HF gradient",
                 y=0.995, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / f'position_gradient{_OUT_SUFFIX}.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / f'position_gradient{_OUT_SUFFIX}.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
