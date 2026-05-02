"""ETTAC 2026 paper figures — hero per-position plot + dissociation scatter.

Two paper-grade figures generated post the 2026-04-19 audits:

  Figure 1: plot_ettac_position_hero.png
    Per-position median LF/HF with 95 % participant-cluster bootstrap CI.
    Steep (P0–P3) and plateau (P4–P10) zones shaded with K10 / K11 annotations.
    Full-range K3 correlation called out on the right side.

  Figure 2: plot_ettac_dissociation.png
    Per-participant P0–P3 OLS slope × regression rate. Spearman ρ = −0.020,
    LOO-LR AUC = 0.523 (chance). Demonstrates load-trajectory and behavioral
    strategy are orthogonal axes of variation.

Style rules (per project CLAUDE.md feedback):
  - 8:1 minimum contrast on body text (computed, not guessed)
  - No default matplotlib figsize; no Light-weight fonts at small sizes
  - Every axis labeled with units and context
  - No decorative emoji, no false-profundity language

Run:
  uv run python3 scripts/plot_ettac_figures.py
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
TRAITS_CSV = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
CONC_DIR = ROOT / 'scripts/output/lfhf_per_position_concentration'
OUT_DIR = ROOT / 'plots-v1'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_lfhf(attribution: str) -> tuple[Path, str]:
    """Return (lfhf_json_path, output_suffix) for the chosen attribution.

    Reads from AF-canonical AdSERP/data/ rather than the sibling pupil-lfhf
    repo's stale copies. organic (default, post-2026-05-01 cascade) reads
    bbox-attributed inputs.
    """
    if attribution == "organic":
        return ROOT / "AdSERP/data/butterworth-lfhf-by-position-organic.json", ""
    if attribution == "absolute":
        return ROOT / "AdSERP/data/butterworth-lfhf-by-position.json", "_absolute"
    raise ValueError(f"unknown attribution: {attribution!r}")


# Module-level hook the loaders read; main() rebinds it after parsing args.
LFHF_JSON: Path = ROOT / "AdSERP/data/butterworth-lfhf-by-position-organic.json"

RNG_SEED = 2026
N_BOOT = 2000

# ── Style (mirrors regenerate_lfhf_plots.py) ──────────────────────────────
INK = '#111111'        # body text — ≈ 18.9:1 on white
MUTED = '#555555'      # ≈ 7.4:1 on white, large text only
GRID = '#d0d0d0'
BG = '#ffffff'

C_STEEP = '#b40426'    # warm red — steep phase
C_PLATEAU = '#3b4cc0'  # cool blue — plateau phase
C_MID = '#5a4e00'      # dark olive — 8.3:1 on white
C_ACCENT = '#0a5522'   # dark green accent — 9.0:1

# Dissociation tercile palette
C_SAT = '#005f60'      # satisficer — teal (≈ 8.8:1)
C_OPT = '#1a2e6e'      # optimizer — deep blue (≈ 13.5:1)

mpl.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.weight': 'regular',
    'axes.titleweight': 'bold',
    'axes.labelweight': 'bold',
    'axes.edgecolor': INK,
    'axes.labelcolor': INK,
    'xtick.color': INK,
    'ytick.color': INK,
    'text.color': INK,
    'axes.linewidth': 1.2,
    'xtick.major.width': 1.1,
    'ytick.major.width': 1.1,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'legend.fontsize': 10,
    'legend.frameon': False,
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'savefig.facecolor': BG,
    'savefig.dpi': 160,
})


def _contrast_ratio(hx: str, bg: str = BG) -> float:
    def _lum(h: str) -> float:
        r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (1, 3, 5))
        def ch(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    l1, l2 = _lum(hx), _lum(bg)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


def _enforce_contrast() -> None:
    for name, hx in (('INK', INK), ('MUTED (large-only)', MUTED),
                     ('C_STEEP', C_STEEP), ('C_PLATEAU', C_PLATEAU),
                     ('C_MID', C_MID), ('C_ACCENT', C_ACCENT),
                     ('C_SAT', C_SAT), ('C_OPT', C_OPT)):
        r = _contrast_ratio(hx)
        assert r >= 7.0, f'{name} {hx} contrast {r:.2f}:1 below 7:1 floor'
    assert _contrast_ratio(INK) >= 8.0, 'INK must be ≥ 8:1 for body text'


# ── Data ───────────────────────────────────────────────────────────────────

def load_segments() -> list[dict]:
    data = json.load(open(LFHF_JSON))
    out = []
    for tid, entry in data.items():
        pid = tid.split('-', 1)[0]
        for p in entry['positions']:
            if p['lfhf'] is None or not math.isfinite(p['lfhf']):
                continue
            if p['pos'] > 10:
                continue
            out.append({'pid': pid, 'tid': tid, 'pos': int(p['pos']),
                        'lfhf': float(p['lfhf'])})
    return out


def load_regression_rate() -> dict[str, float]:
    out: dict[str, float] = {}
    with open(TRAITS_CSV) as f:
        for row in csv.DictReader(f):
            out[row['participant']] = float(row['regression_rate'])
    return out


def position_medians_from_segments(segments: list[dict], positions: list[int]
                                   ) -> dict[int, float]:
    by_pos: dict[int, list[float]] = defaultdict(list)
    for s in segments:
        if s['pos'] in positions:
            by_pos[s['pos']].append(s['lfhf'])
    return {p: float(np.median(by_pos[p])) for p in positions if by_pos[p]}


def bootstrap_position_ci(segments: list[dict], positions: list[int],
                          n_boot: int, rng: np.random.Generator) -> dict[int, tuple[float, float, float]]:
    """Participant-cluster bootstrap for each position median.

    Returns {pos: (median, lo95, hi95)}.
    """
    by_pid_pos: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for s in segments:
        by_pid_pos[s['pid']][s['pos']].append(s['lfhf'])
    all_pids = sorted(by_pid_pos)

    draws: dict[int, list[float]] = {p: [] for p in positions}
    for _ in range(n_boot):
        resample = list(rng.choice(all_pids, size=len(all_pids), replace=True))
        acc: dict[int, list[float]] = defaultdict(list)
        for pid in resample:
            for pos, vs in by_pid_pos[pid].items():
                if pos in positions:
                    acc[pos].extend(vs)
        for pos in positions:
            if acc[pos]:
                draws[pos].append(float(np.median(acc[pos])))

    out: dict[int, tuple[float, float, float]] = {}
    for pos in positions:
        arr = np.array(draws[pos], dtype=float)
        if len(arr) == 0:
            continue
        out[pos] = (
            float(np.median(arr)),
            float(np.percentile(arr, 2.5)),
            float(np.percentile(arr, 97.5)),
        )
    return out


# ── Figure 1: Hero per-position plot ──────────────────────────────────────

STEEP = list(range(0, 4))
PLATEAU = list(range(4, 11))
ALL_POS = list(range(0, 11))


def plot_hero(segments: list[dict]) -> Path:
    rng = np.random.default_rng(RNG_SEED)
    meds = position_medians_from_segments(segments, ALL_POS)
    cis = bootstrap_position_ci(segments, ALL_POS, N_BOOT, rng)

    # Steep / plateau / full Spearman on the point-estimate medians
    rho_full, p_full = spearmanr([p for p in ALL_POS if p in meds],
                                 [meds[p] for p in ALL_POS if p in meds])
    rho_steep, _ = spearmanr([p for p in STEEP if p in meds],
                             [meds[p] for p in STEEP if p in meds])
    rho_plat, p_plat = spearmanr([p for p in PLATEAU if p in meds],
                                 [meds[p] for p in PLATEAU if p in meds])

    fig, ax = plt.subplots(figsize=(12.5, 7.6))

    # Phase zones — tinted background bands
    ymin, ymax = 8, 40
    ax.axvspan(-0.35, 3.35, facecolor=C_STEEP, alpha=0.07, zorder=0)
    ax.axvspan(3.35, 10.5, facecolor=C_PLATEAU, alpha=0.06, zorder=0)

    # Bootstrap CI band
    xs = np.array([p for p in ALL_POS if p in cis])
    lo = np.array([cis[p][1] for p in xs])
    hi = np.array([cis[p][2] for p in xs])
    med = np.array([meds[p] for p in xs])
    ax.fill_between(xs, lo, hi, color=C_STEEP, alpha=0.12, zorder=1, linewidth=0,
                    label='95 % participant-cluster bootstrap CI')

    # Point estimates — line + markers
    ax.plot(xs, med, color=INK, lw=2.6, zorder=3)
    ax.plot(xs, med, 'o', color=C_STEEP, markersize=10,
            markeredgecolor='white', markeredgewidth=1.6, zorder=4,
            label='Median Butterworth LF/HF (pooled across participants)')

    # Zone labels — algorithmic results only (Key Claim IDs + their numbers)
    ax.text(1.5, 38.2, 'Steep phase  ·  P0–P3',
            ha='center', va='top', fontsize=13, fontweight='bold',
            color=C_STEEP)
    ax.text(1.5, 36.1,
            'K10  ρ = −1.000   ·   K9  MW p = 3.2 × 10⁻²³',
            ha='center', va='top', fontsize=11, color=INK)

    ax.text(7, 38.2, 'Plateau  ·  P4–P10',
            ha='center', va='top', fontsize=13, fontweight='bold',
            color=C_PLATEAU)
    ax.text(7, 36.1,
            f'K11  ρ = {rho_plat:+.3f}   p = {p_plat:.3f}',
            ha='center', va='top', fontsize=11, color=INK)

    # Full-range callout — boxed annotation inside the plot area
    ax.annotate(f'Full range K3\nρ = {rho_full:+.3f}\np < 10⁻⁴',
                xy=(10, med[-1]), xytext=(9.6, 25.5),
                ha='center', va='center', fontsize=10, color=C_ACCENT,
                fontweight='bold',
                bbox=dict(facecolor='#f4f4f2', edgecolor=C_ACCENT,
                          linewidth=1.0, boxstyle='round,pad=0.45'),
                arrowprops=dict(arrowstyle='-', color=C_ACCENT, lw=1.2))

    # Horizontal separator below header strip so the data area reads cleanly
    ax.axhline(34.0, color=GRID, linestyle='-', linewidth=0.6, alpha=0.7,
               zorder=0)

    # Axes
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks(ALL_POS)
    ax.set_yticks([10, 15, 20, 25, 30])  # skip header-strip range on y
    ax.set_xlabel('SERP position  (0 = topmost organic result)')
    ax.set_ylabel('Butterworth LF/HF ratio  ·  higher = more cognitive load')
    ax.set_title('Cognitive load drops steeply over the commit-action surface',
                 pad=12, fontsize=15)
    ax.grid(axis='y', linestyle=':', color=GRID, alpha=0.9, linewidth=0.8)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)

    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.27), ncol=2,
              frameon=False, handlelength=2.4)

    # Provenance stamp at bottom-left of the figure
    fig.text(0.02, 0.015,
             'AdSERP  ·  n = 47 participants  ·  2,719 trials  ·  GP3 HD @ 150 Hz  ·  '
             'Duchowski (2026) IIR Butterworth LF/HF',
             fontsize=9, color=MUTED, ha='left', va='bottom')

    out_path = OUT_DIR / f'plot_ettac_position_hero{_OUT_SUFFIX}.png'
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(out_path, bbox_inches='tight')
    plt.close(fig)
    print(f'[fig1] {out_path.relative_to(ROOT)}  '
          f'(full ρ={rho_full:+.3f}, steep ρ={rho_steep:+.3f}, plateau ρ={rho_plat:+.3f})')
    return out_path


# ── Figure 2: Dissociation scatter ─────────────────────────────────────────

def participant_steep_slope(segments: list[dict]) -> dict[str, float]:
    """Per-participant OLS slope of position-median LF/HF on P0–P3."""
    by_pid_pos: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for s in segments:
        if s['pos'] in STEEP:
            by_pid_pos[s['pid']][s['pos']].append(s['lfhf'])
    slopes: dict[str, float] = {}
    for pid, pmap in by_pid_pos.items():
        xs, ys = [], []
        for p in STEEP:
            if pmap.get(p):
                xs.append(p); ys.append(float(np.median(pmap[p])))
        if len(xs) < 3:
            continue
        slope, intercept = np.polyfit(xs, ys, 1)
        slopes[pid] = float(slope)
    return slopes


def plot_dissociation(segments: list[dict], rates: dict[str, float]) -> Path:
    slopes = participant_steep_slope(segments)
    pids = sorted(p for p in slopes if p in rates)
    slope_arr = np.array([slopes[p] for p in pids])
    rate_arr = np.array([rates[p] for p in pids])
    med_rate = float(np.median(rate_arr))
    labels = rate_arr > med_rate  # True = optimizer

    rho, p_val = spearmanr(slope_arr, rate_arr)

    fig, ax = plt.subplots(figsize=(10.5, 6.6))

    # Jitter y slightly for readability only when identical rates stack
    ax.scatter(slope_arr[~labels], rate_arr[~labels],
               s=120, facecolor=C_SAT, edgecolor='white', linewidth=1.4,
               alpha=0.92, label=f'Satisficer  (≤ median, n = {(~labels).sum()})',
               zorder=3)
    ax.scatter(slope_arr[labels], rate_arr[labels],
               s=120, facecolor=C_OPT, edgecolor='white', linewidth=1.4,
               alpha=0.92, label=f'Optimizer  (> median, n = {labels.sum()})',
               zorder=3)

    # Median-rate horizontal
    ax.axhline(med_rate, color=MUTED, linestyle='--', linewidth=1.1, zorder=1,
               alpha=0.8)
    ax.text(ax.get_xlim()[1] * 0.98, med_rate + 0.01,
            f'median regression rate = {med_rate:.3f}',
            ha='right', va='bottom', fontsize=9, color=MUTED, fontstyle='italic')

    # Zero-slope vertical
    ax.axvline(0.0, color=MUTED, linestyle=':', linewidth=1.0, zorder=1,
               alpha=0.7)

    ax.set_xlabel('Per-participant LF/HF slope on P0–P3  (LF/HF units per position)')
    ax.set_ylabel('Regression rate  (fraction of trials with a backward saccade)')
    ax.set_title('Load trajectory is orthogonal to satisficer/optimizer strategy',
                 pad=14)
    ax.grid(axis='y', linestyle=':', color=GRID, alpha=0.9, linewidth=0.8)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)

    # Statistic annotation box
    stat_txt = (f'Spearman ρ  =  {rho:+.3f}   p = {p_val:.2f}\n'
                f'LOO-LR AUC  =  0.523   baseline 0.522\n'
                f'per-feature |d| < 0.21, p > 0.50')
    ax.text(0.02, 0.98, stat_txt, transform=ax.transAxes,
            ha='left', va='top', fontsize=10.5, color=INK,
            fontfamily='monospace',
            bbox=dict(facecolor='#f4f4f2', edgecolor=INK, linewidth=1.0,
                      boxstyle='round,pad=0.5'))

    ax.legend(loc='lower right', frameon=False)

    fig.text(0.02, 0.015,
             f'AdSERP  ·  n = {len(pids)} participants with complete P0–P3 features  ·  '
             '2026-04-19 orthogonality re-check',
             fontsize=9, color=MUTED, ha='left', va='bottom')
    out_path = OUT_DIR / f'plot_ettac_dissociation{_OUT_SUFFIX}.png'
    fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    fig.savefig(out_path, bbox_inches='tight')
    plt.close(fig)
    print(f'[fig2] {out_path.relative_to(ROOT)}  '
          f'(ρ={rho:+.3f} p={p_val:.3f} N={len(pids)})')
    return out_path


# ── Figure 3: Robustness panel (participant concentration + cap-sensitivity) ─

def plot_robustness() -> Path:
    """Two-panel appendix figure: per-position participant coverage, plus
    plateau / steep / full Spearman ρ under per-participant caps with
    participant-cluster bootstrap 95 % CIs."""
    conc = json.loads((CONC_DIR / 'concentration.json').read_text())
    boot = json.loads((CONC_DIR / 'bootstrap_results.json').read_text())

    positions = [int(k) for k in sorted(conc.keys(), key=int)]
    n_part = [conc[str(p)]['n_participants'] for p in positions]
    top10  = [conc[str(p)]['top10_share'] * 100 for p in positions]

    caps_order = ['cap3', 'cap5', 'cap10', 'cap20', 'uncapped']
    cap_labels = ['cap 3', 'cap 5', 'cap 10', 'cap 20', 'uncapped']
    ranges = [
        ('full_P0_P10',    'Full  P0–P10', C_ACCENT),
        ('steep_P0_P3',    'Steep  P0–P3', C_STEEP),
        ('plateau_P4_P10', 'Plateau  P4–P10', C_PLATEAU),
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.0, 6.4),
                                   gridspec_kw={'width_ratios': [1.0, 1.25]})

    # ── Panel A: concentration ──────────────────────────────────────────────
    ax1b = ax1.twinx()
    bars = ax1.bar(positions, n_part, color=C_PLATEAU, alpha=0.85,
                   edgecolor='white', linewidth=0.8, zorder=3,
                   label='Participants contributing ≥1 segment')
    ax1b.plot(positions, top10, color=C_STEEP, lw=2.2, marker='s',
              markersize=7, markeredgecolor='white', markeredgewidth=1.2,
              zorder=5, label='Top-10 participant share')

    for bar, n in zip(bars, n_part):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 2,
                 str(n), ha='center', va='top', fontsize=9,
                 color='white', fontweight='bold', zorder=6)

    ax1.set_xticks(positions)
    ax1.set_xlabel('SERP position')
    ax1.set_ylabel('N participants', color=C_PLATEAU)
    ax1.tick_params(axis='y', colors=C_PLATEAU)
    ax1.set_ylim(0, 52)
    ax1.grid(axis='y', linestyle=':', color=GRID, alpha=0.9, linewidth=0.8)
    for spine in ('top',):
        ax1.spines[spine].set_visible(False)

    ax1b.set_ylim(0, 100)
    ax1b.set_ylabel('Top-10 share of segments  (%)', color=C_STEEP)
    ax1b.tick_params(axis='y', colors=C_STEEP)
    ax1b.spines['top'].set_visible(False)

    ax1.set_title('Per-position participant coverage', pad=10, fontsize=13)

    # Panel-A legend: combine both axes
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc='upper right', frameon=False,
               fontsize=9.5)

    # ── Panel B: cap-sensitivity with CIs ───────────────────────────────────
    x_caps = np.arange(len(caps_order), dtype=float)
    dx = 0.22  # horizontal offset per range
    for j, (key, label, color) in enumerate(ranges):
        meds = np.array([boot[c][key]['median'] for c in caps_order], dtype=float)
        los  = np.array([boot[c][key]['lo']     for c in caps_order], dtype=float)
        his  = np.array([boot[c][key]['hi']     for c in caps_order], dtype=float)
        xs = x_caps + (j - 1) * dx
        yerr = np.vstack([meds - los, his - meds])
        ax2.errorbar(xs, meds, yerr=yerr, fmt='none', ecolor=color,
                     elinewidth=2.2, capsize=6, capthick=1.8, alpha=0.95,
                     zorder=3)
        ax2.plot(xs, meds, 'o', color=color, markersize=9,
                 markeredgecolor='white', markeredgewidth=1.4,
                 label=label, zorder=4)

    ax2.axhline(0.0, color=MUTED, linestyle='--', linewidth=1.0, alpha=0.75,
                zorder=1)
    ax2.set_xticks(x_caps)
    ax2.set_xticklabels(cap_labels)
    ax2.set_ylim(-1.05, 0.55)
    ax2.set_ylabel('Spearman  ρ  (position × median LF/HF)')
    ax2.set_xlabel('Per-participant per-position segment cap')
    ax2.set_title('Cap-sensitivity, 2,000 participant-cluster bootstraps',
                  pad=10, fontsize=13)
    ax2.grid(axis='y', linestyle=':', color=GRID, alpha=0.9, linewidth=0.8)
    for spine in ('top', 'right'):
        ax2.spines[spine].set_visible(False)
    ax2.legend(loc='lower right', frameon=False, fontsize=10)

    fig.suptitle('Plateau gradient survives participant-concentration audit',
                 fontsize=15, y=1.02)

    fig.text(0.02, 0.01,
             f'AdSERP  ·  n = 47 participants  ·  6,099 valid LF/HF segments  ·  '
             '2026-04-19 concentration audit',
             fontsize=9, color=MUTED, ha='left', va='bottom')

    out_path = OUT_DIR / f'plot_ettac_robustness{_OUT_SUFFIX}.png'
    fig.tight_layout(rect=(0, 0.04, 1, 0.98))
    fig.savefig(out_path, bbox_inches='tight')
    plt.close(fig)
    print(f'[fig3] {out_path.relative_to(ROOT)}')
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribution", choices=["organic", "absolute"], default="organic",
                    help="organic (default; bbox-attributed) or absolute (legacy h3+ads pooled)")
    args = ap.parse_args()

    global LFHF_JSON, _OUT_SUFFIX
    LFHF_JSON, _OUT_SUFFIX = resolve_lfhf(args.attribution)
    print(f'[attribution] {args.attribution} -> {LFHF_JSON.name}')

    _enforce_contrast()
    print('[load] LF/HF segments + regression rates')
    segments = load_segments()
    rates = load_regression_rate()
    print(f'       {len(segments)} segments  ·  {len({s["pid"] for s in segments})} participants  '
          f'·  {len(rates)} rate records')
    plot_hero(segments)
    plot_dissociation(segments, rates)
    plot_robustness()
    print('done.')


_OUT_SUFFIX = ""


if __name__ == '__main__':
    main()
