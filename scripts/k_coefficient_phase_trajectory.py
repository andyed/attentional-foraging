"""K (ambient/focal) phase trajectory — does K shift ambient → focal across
trial phase, replicating Jayawardena et al. ETRA 2025's T1→T5 finding on
AdSERP and aligning Krejtz K with OSEC Survey-then-Evaluate?

For each trial, split fixations by trial-time into 3 equal-duration phases
(begin / mid / end). Compute mean K per phase using same per-pid z-score
parameters as compute_k_coefficient.py. Test phase main effect (Friedman).

Predictions:
  - Begin K < 0 (ambient — Survey scanning), End K > 0 (focal — Evaluate
    commit) → K aligns with OSEC Survey-then-Evaluate temporal phase split.
  - Phase main effect null → K is position/content-driven, not phase-driven.

Output:
  scripts/output/k_phase_trajectory/summary.json
  scripts/output/k_phase_trajectory/phase_panel.png
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
from scipy.stats import friedmanchisquare, wilcoxon

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_fixations,
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)

OUT_DIR = ROOT / 'scripts/output/k_phase_trajectory'
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
COLOR_K = "#5a7d8c"
COLOR_AMBIENT = "#2980b9"
COLOR_FOCAL = "#c0392b"


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    # Pass 1: collect per-pid FD and SA (for z-score normalization)
    pid_fd: dict[str, list[float]] = defaultdict(list)
    pid_sa: dict[str, list[float]] = defaultdict(list)
    trial_records: list[tuple[str, list[dict]]] = []

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  pass-1: {i+1}/{len(trial_ids)}', file=sys.stderr)
        fixations = load_fixations(tid)
        if not fixations or len(fixations) < 3:
            continue

        pid = tid.split('-')[0]
        for j, f in enumerate(fixations):
            pid_fd[pid].append(float(f['d']))
            if j + 1 < len(fixations):
                nxt = fixations[j + 1]
                sa = math.hypot(nxt['x'] - f['x'], nxt['y'] - f['y'])
                pid_sa[pid].append(sa)

        trial_records.append((tid, fixations))

    pid_params: dict[str, dict] = {}
    for pid in pid_fd:
        if len(pid_fd[pid]) < 30 or len(pid_sa[pid]) < 30:
            continue
        pid_params[pid] = {
            'mu_fd': float(np.mean(pid_fd[pid])),
            'sd_fd': float(np.std(pid_fd[pid], ddof=1)),
            'mu_sa': float(np.mean(pid_sa[pid])),
            'sd_sa': float(np.std(pid_sa[pid], ddof=1)),
        }
    print(f'  participants with z-score params: {len(pid_params)}', file=sys.stderr)

    # Pass 2: per-trial K by phase (begin/mid/end of trial duration)
    rows = []  # one per qualifying trial
    n_skipped = 0
    for tid, fixations in trial_records:
        pid = tid.split('-')[0]
        params = pid_params.get(pid)
        if params is None:
            n_skipped += 1
            continue
        # All fixations in trial — split by time into 3 equal phases
        t_lo = float(fixations[0]['t'])
        t_hi = float(fixations[-1]['t'])
        if t_hi - t_lo < 1000:  # need ≥ 1s of fixation activity
            continue
        third = (t_hi - t_lo) / 3.0
        boundaries = (t_lo, t_lo + third, t_lo + 2 * third, t_hi)
        phase_ks: dict[str, list[float]] = {'begin': [], 'mid': [], 'end': []}
        for j, f in enumerate(fixations):
            if j + 1 >= len(fixations):
                continue
            t = float(f['t'])
            if t < boundaries[1]:
                ph = 'begin'
            elif t < boundaries[2]:
                ph = 'mid'
            else:
                ph = 'end'
            fd = float(f['d'])
            nxt = fixations[j + 1]
            sa = math.hypot(nxt['x'] - f['x'], nxt['y'] - f['y'])
            z_fd = (fd - params['mu_fd']) / max(params['sd_fd'], 1e-9)
            z_sa = (sa - params['mu_sa']) / max(params['sd_sa'], 1e-9)
            phase_ks[ph].append(z_fd - z_sa)

        if not all(len(v) >= 2 for v in phase_ks.values()):
            continue

        rows.append({
            'tid': tid, 'pid': pid,
            'begin': float(np.mean(phase_ks['begin'])),
            'mid':   float(np.mean(phase_ks['mid'])),
            'end':   float(np.mean(phase_ks['end'])),
        })

    print(f'\n  trials with all 3 phases populated: {len(rows):,}',
          file=sys.stderr)

    if not rows:
        print('  no trials qualified — exiting', file=sys.stderr)
        return

    begin = np.array([r['begin'] for r in rows])
    mid = np.array([r['mid'] for r in rows])
    end = np.array([r['end'] for r in rows])

    fr_stat, fr_p = friedmanchisquare(begin, mid, end)
    w_be = wilcoxon(begin, end, alternative='less')   # tests begin < end (ambient → focal)
    w_bm = wilcoxon(begin, mid, alternative='less')
    w_me = wilcoxon(mid, end, alternative='less')

    n_monotone_increase = sum(1 for r in rows if r['begin'] <= r['mid'] <= r['end'])
    n_any_increase = sum(1 for r in rows if r['begin'] < r['end'])

    print('\n=== K phase trajectory (begin / mid / end) ===')
    print(f'  begin: med = {np.median(begin):+.4f}  mean = {np.mean(begin):+.4f}')
    print(f'  mid:   med = {np.median(mid):+.4f}    mean = {np.mean(mid):+.4f}')
    print(f'  end:   med = {np.median(end):+.4f}    mean = {np.mean(end):+.4f}')
    print(f'  Friedman χ²(2, N={len(rows)}) = {fr_stat:.1f}, p = {fr_p:.3g}')
    print(f'  Wilcoxon begin < end (ambient → focal):  p = {w_be.pvalue:.3g}')
    print(f'  Wilcoxon begin < mid:                    p = {w_bm.pvalue:.3g}')
    print(f'  Wilcoxon mid < end:                      p = {w_me.pvalue:.3g}')
    print(f'  Monotone (b ≤ m ≤ e):  {100*n_monotone_increase/len(rows):.1f}% of trials')
    print(f'  Any increase (b < e):  {100*n_any_increase/len(rows):.1f}% of trials')

    # Per-phase signs
    n_begin_ambient = (begin < 0).sum()
    n_end_focal = (end > 0).sum()
    print(f'  N begin K < 0 (ambient): {n_begin_ambient:,} ({100*n_begin_ambient/len(rows):.1f}%)')
    print(f'  N end K > 0 (focal):     {n_end_focal:,} ({100*n_end_focal/len(rows):.1f}%)')

    summary = {
        'n_trials': len(rows),
        'n_pids': len(set(r['pid'] for r in rows)),
        'phase_means': {
            'begin': {'median': float(np.median(begin)), 'mean': float(np.mean(begin)),
                      'sd': float(np.std(begin, ddof=1))},
            'mid':   {'median': float(np.median(mid)), 'mean': float(np.mean(mid)),
                      'sd': float(np.std(mid, ddof=1))},
            'end':   {'median': float(np.median(end)), 'mean': float(np.mean(end)),
                      'sd': float(np.std(end, ddof=1))},
        },
        'friedman': {'chi2': float(fr_stat), 'p': float(fr_p)},
        'wilcoxon_one_sided_increase': {
            'begin_lt_end':  {'stat': float(w_be.statistic), 'p': float(w_be.pvalue)},
            'begin_lt_mid':  {'stat': float(w_bm.statistic), 'p': float(w_bm.pvalue)},
            'mid_lt_end':    {'stat': float(w_me.statistic), 'p': float(w_me.pvalue)},
        },
        'monotone_pct': 100 * n_monotone_increase / len(rows),
        'pct_begin_ambient': 100 * n_begin_ambient / len(rows),
        'pct_end_focal': 100 * n_end_focal / len(rows),
    }
    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Plot ──────────────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))

    # (A) Phase median trajectory
    phases = ['begin', 'mid', 'end']
    medians = [np.median(begin), np.median(mid), np.median(end)]
    means = [np.mean(begin), np.mean(mid), np.mean(end)]
    x = np.arange(3)

    axes[0].plot(x, medians, marker='o', color=COLOR_K, lw=2.4, ms=12,
                 markeredgecolor='#222222', markeredgewidth=0.6, label='median')
    axes[0].plot(x, means, marker='s', color='#888888', lw=1.4, ms=8, ls='--',
                 markeredgecolor='#222222', markeredgewidth=0.5, label='mean')
    axes[0].axhline(0, color='#222222', lw=0.6, ls='--', alpha=0.6)
    # Shade ambient/focal regions
    yl = axes[0].get_ylim()
    axes[0].set_ylim(min(yl[0], -0.4), max(yl[1], 0.4))
    axes[0].fill_betweenx([axes[0].get_ylim()[0], 0], -0.5, 2.5,
                          color=COLOR_AMBIENT, alpha=0.07)
    axes[0].fill_betweenx([0, axes[0].get_ylim()[1]], -0.5, 2.5,
                          color=COLOR_FOCAL, alpha=0.07)
    axes[0].text(2.45, axes[0].get_ylim()[0] * 0.5, 'ambient', ha='right', va='center',
                 color=COLOR_AMBIENT, fontstyle='italic', fontsize=10)
    axes[0].text(2.45, axes[0].get_ylim()[1] * 0.5, 'focal', ha='right', va='center',
                 color=COLOR_FOCAL, fontstyle='italic', fontsize=10)

    axes[0].set_xticks(x)
    axes[0].set_xticklabels(phases)
    axes[0].set_xlim(-0.5, 2.5)
    axes[0].set_xlabel('within-trial phase')
    axes[0].set_ylabel('mean K (per-trial)')
    axes[0].set_title("(A) K phase trajectory on AdSERP\n"
                      r"Friedman $\chi^2(2, N=" + f"{len(rows):,}" + r")"
                      f"= {fr_stat:.1f}$,  "
                      r"$p = " + f"{fr_p:.2g}" + r"$;  "
                      f"Wilcoxon begin<end p = {w_be.pvalue:.2g}",
                      fontsize=11)
    axes[0].legend(loc='upper left', frameon=True, framealpha=0.92,
                   edgecolor='#cccccc')
    axes[0].grid(True, alpha=0.5)

    # (B) Distribution comparison: histogram of (end - begin) per trial
    diff = end - begin
    axes[1].hist(diff, bins=40, color=COLOR_K, alpha=0.65, edgecolor='#222222',
                 linewidth=0.4)
    axes[1].axvline(0, color='#222222', lw=1.0, ls='--')
    axes[1].axvline(np.median(diff), color=COLOR_FOCAL, lw=1.6,
                    label=f'median Δ = {np.median(diff):+.3f}')
    axes[1].set_xlabel('per-trial K_end − K_begin')
    axes[1].set_ylabel('# trials')
    n_pos = (diff > 0).sum()
    pct_pos = 100 * n_pos / len(diff)
    axes[1].set_title(f"(B) per-trial Δ K (end − begin)\n"
                      f"{n_pos:,} / {len(diff):,} trials ({pct_pos:.1f}%) show end > begin "
                      f"(ambient → focal)",
                      fontsize=11)
    axes[1].legend(loc='upper right', frameon=True, framealpha=0.92,
                   edgecolor='#cccccc')
    axes[1].grid(True, alpha=0.5)

    fig.suptitle("Does K shift ambient → focal across trial phase?  "
                 "Replicating Jayawardena et al. ETRA 2025 T1→T5 on AdSERP",
                 y=0.995, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / 'phase_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'phase_panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
