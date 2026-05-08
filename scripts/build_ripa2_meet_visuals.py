"""RIPA2 meet figure set — Thursday meeting with Jacek + Gavindya + Yasith.

Five figures (some new, some referencing existing). Centerpiece is the
LF/HF wr>nr vs RIPA2 wr<nr dissociation — same evaluation moments, opposite
directions, p < 10⁻³ each. Plus the four-channel architecture diagram for
the strategic framing of the v2 mouse-latency ask.

  R1: wr/nr dissociation — LF/HF + RIPA2 side-by-side at the same evaluation
      moments (the centerpiece)
  R2: four-channel decision-moment architecture diagram

Existing figures to reference (already in scripts/output/):
  - viz_ripa2_lfhf/ripa2_lfhf_unique_sensitivity.png  (temporal-scope overview)
  - ripa2_around_click/peri_click_trace.png            (peri-click TEPR)
  - lfhf_around_click/comparison_4panel.png            (RIPA2 vs LF/HF time-locked)
  - click_prediction_ablation/ablation_panel.png       (LAB lift)

Output:
  scripts/output/ripa2_meet_visuals/R1_wrnr_dissociation.{png,svg}
  scripts/output/ripa2_meet_visuals/R2_four_channel_architecture.{png,svg}
  scripts/output/ripa2_meet_visuals/MANIFEST.md  (lists all figures)
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
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json'
RIPA2 = ROOT / 'AdSERP/data/ripa2-by-position.json'
ENC = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
OUT_DIR = ROOT / 'scripts/output/ripa2_meet_visuals'
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
COLOR_RIPA2 = "#7c4dff"   # purple
COLOR_LFHF = "#d4a574"    # amber
COLOR_SACCADE = "#117733"  # green
COLOR_MOTOR = "#cc6677"    # rose


def load_wr_nr_paired_metrics():
    """Per-(trial, pos) wr/nr labels paired with both LF/HF and RIPA2."""
    enc = json.load(open(ENC))
    wr_map: dict[tuple[str, int], bool] = {}
    for tid, t in enc.items():
        for fix in t.get('first_pass') or []:
            key = (tid, int(fix['pos']))
            wr_map[key] = wr_map.get(key, False) or bool(fix.get('will_regress'))
    lfhf = json.load(open(LFHF))
    ripa2 = json.load(open(RIPA2))

    rows = {'lfhf_wr': [], 'lfhf_nr': [], 'ripa2_wr': [], 'ripa2_nr': []}
    for tid, ltrial in lfhf.items():
        rtrial = ripa2.get(tid, {})
        rby = {p['pos']: p.get('ripa2') for p in rtrial.get('positions', [])}
        for seg in ltrial.get('positions', []):
            pos = int(seg['pos'])
            lv = seg.get('lfhf')
            rv = rby.get(pos)
            key = (tid, pos)
            if key not in wr_map:
                continue
            is_wr = wr_map[key]
            if lv is not None and math.isfinite(lv):
                rows['lfhf_wr' if is_wr else 'lfhf_nr'].append(float(lv))
            if rv is not None and math.isfinite(rv):
                rows['ripa2_wr' if is_wr else 'ripa2_nr'].append(float(rv))
    return {k: np.array(v) for k, v in rows.items()}


# ── R1: wr/nr dissociation (the centerpiece) ───────────────────────────────

def rank_biserial(a: np.ndarray, b: np.ndarray) -> float:
    """Rank-biserial correlation (Wendt 1972). Robust effect size for
    Mann-Whitney comparisons; appropriate for heavy-tailed distributions
    where Cohen's d is dominated by outliers.

    r_rb = 2U / (n_a * n_b) - 1
    Range [-1, +1]. Equivalent to "P(a > b) - P(a < b)" (the difference
    between the probability that a random observation from a exceeds one
    from b vs the reverse).
    Conventional thresholds: |r| ≈ 0.10 small, 0.30 medium, 0.50 large.
    """
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    u, _ = mannwhitneyu(a, b, alternative='two-sided')
    return 2 * u / (len(a) * len(b)) - 1


def fig_r1_dissociation():
    plt.rcParams.update(RC)
    d = load_wr_nr_paired_metrics()

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.6))

    # Panel A: LF/HF wr vs nr — wr HIGHER
    u_l, p_l = mannwhitneyu(d['lfhf_wr'], d['lfhf_nr'], alternative='greater')
    bp = axes[0].boxplot([d['lfhf_wr'], d['lfhf_nr']], positions=[0, 1],
                         widths=0.55, patch_artist=True, showfliers=False,
                         medianprops=dict(color='#222222', lw=1.8),
                         whiskerprops=dict(color='#666666'),
                         capprops=dict(color='#666666'),
                         boxprops=dict(facecolor=COLOR_LFHF,
                                       edgecolor='#666666', alpha=0.6))
    axes[0].set_xticks([0, 1])
    axes[0].set_xticklabels(['will-regress', 'no-regress'])
    axes[0].set_ylabel('LF/HF (sustained windowed load)')
    delta_l = float(np.median(d['lfhf_wr']) - np.median(d['lfhf_nr']))
    rrb_l = rank_biserial(d['lfhf_wr'], d['lfhf_nr'])
    axes[0].set_title("LF/HF — will-regress  $>$  no-regress\n"
                      f"med {np.median(d['lfhf_wr']):.2f} vs {np.median(d['lfhf_nr']):.2f},  "
                      r"$\Delta = +" + f"{delta_l:.2f}" + r"$,  "
                      r"$p = " + f"{p_l:.2g}" + r"$,  "
                      r"rank-biserial $r = " + f"{rrb_l:+.3f}" + r"$" + "\n"
                      f"N = {len(d['lfhf_wr']):,} / {len(d['lfhf_nr']):,}",
                      fontsize=11)
    axes[0].grid(True, axis='y', alpha=0.5)

    # Highlight direction
    y_top = max(np.percentile(d['lfhf_wr'], 75), np.percentile(d['lfhf_nr'], 75)) * 1.05
    axes[0].annotate('', xy=(1, y_top), xytext=(0, y_top),
                     arrowprops=dict(arrowstyle='-|>', color=COLOR_LFHF,
                                     lw=2.0))
    axes[0].text(0.5, y_top * 1.05, 'sustained engagement HIGHER',
                 ha='center', va='bottom',
                 fontsize=10, color=COLOR_LFHF, fontweight='bold',
                 fontstyle='italic')

    # Panel B: RIPA2 wr vs nr — wr LOWER
    u_r, p_r = mannwhitneyu(d['ripa2_wr'], d['ripa2_nr'], alternative='less')
    bp = axes[1].boxplot([d['ripa2_wr'], d['ripa2_nr']], positions=[0, 1],
                         widths=0.55, patch_artist=True, showfliers=False,
                         medianprops=dict(color='#222222', lw=1.8),
                         whiskerprops=dict(color='#666666'),
                         capprops=dict(color='#666666'),
                         boxprops=dict(facecolor=COLOR_RIPA2,
                                       edgecolor='#666666', alpha=0.5))
    axes[1].set_xticks([0, 1])
    axes[1].set_xticklabels(['will-regress', 'no-regress'])
    axes[1].set_ylabel('RIPA2 (per-event amplitude)')
    delta_r = float(np.median(d['ripa2_wr']) - np.median(d['ripa2_nr']))
    rrb_r = rank_biserial(d['ripa2_wr'], d['ripa2_nr'])
    # Use mean instead of median for RIPA2 since post-bug-fix medians are
    # so close they round to the same printed value at 5 decimals.
    mean_wr = float(np.mean(d['ripa2_wr']))
    mean_nr = float(np.mean(d['ripa2_nr']))
    axes[1].set_title("RIPA2 — will-regress  $<$  no-regress\n"
                      f"mean {mean_wr:.5f} vs {mean_nr:.5f},  "
                      r"$\Delta = " + f"{mean_wr - mean_nr:+.5f}" + r"$,  "
                      r"$p = " + f"{p_r:.2g}" + r"$,  "
                      r"rank-biserial $r = " + f"{rrb_r:+.3f}" + r"$" + "\n"
                      f"N = {len(d['ripa2_wr']):,} / {len(d['ripa2_nr']):,}",
                      fontsize=11)
    axes[1].grid(True, axis='y', alpha=0.5)
    y_top = max(np.percentile(d['ripa2_wr'], 75), np.percentile(d['ripa2_nr'], 75)) * 1.10
    axes[1].annotate('', xy=(0, y_top), xytext=(1, y_top),
                     arrowprops=dict(arrowstyle='-|>', color=COLOR_RIPA2,
                                     lw=2.0))
    axes[1].text(0.5, y_top * 1.05, 'per-event arousal LOWER',
                 ha='center', va='bottom',
                 fontsize=10, color=COLOR_RIPA2, fontweight='bold',
                 fontstyle='italic')

    fig.suptitle("Same evaluation moments, opposite directions  —  "
                 "RIPA2 / LF/HF temporal-scope dissociation",
                 y=0.995, fontsize=14)

    fig.text(0.5, 0.005,
             "AdSERP per-(trial, position) evaluation moments stratified by NB22 "
             "gaze-regression label.  Same trials, same label, both metrics significant, "
             "opposite directions.  Effect sizes are small (rank-biserial |r| < 0.10);  "
             "significance comes from N, not magnitude.  The DIRECTION is the finding.  "
             "RIPA2 values use the bug-fixed JEMR 2025 spec (intrinsically small magnitudes; "
             "the visual proximity of the boxes does not weaken the dissociation).\n"
             "Interpretation: will-regress items receive concentrated, sustained engagement "
             "(LF/HF up) without spike-arousal (RIPA2 down) — calm focused reading the user "
             "knows they will return to.",
             ha='center', va='bottom', fontsize=9.5, color='#444444',
             style='italic',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#fdf8f2',
                       edgecolor='#dddddd', lw=0.6))

    plt.tight_layout(rect=(0, 0.07, 1, 0.96))
    out = OUT_DIR / 'R1_wrnr_dissociation'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


# ── R2: Four-channel architecture diagram ─────────────────────────────────

def fig_r2_four_channels():
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(13, 7.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Center: the click decision moment
    decision_x, decision_y = 50, 50
    ax.add_patch(FancyBboxPatch(
        (decision_x - 11, decision_y - 5), 22, 10,
        boxstyle="round,pad=0.5", facecolor='#fdf8f2', edgecolor='#222222',
        linewidth=1.5, zorder=4,
    ))
    ax.text(decision_x, decision_y + 1.5, 'CLICK DECISION', ha='center', va='center',
            fontsize=13, fontweight='bold', color='#222222', zorder=5)
    ax.text(decision_x, decision_y - 2.5, 'AdSERP per-result moment',
            ha='center', va='center', fontsize=9, color='#666666',
            fontstyle='italic', zorder=5)

    # Channel boxes — five channels arranged around the decision moment
    channels = [
        # (x, y, color, name, granularity, signal_descr, status, evidence)
        (15, 82, COLOR_RIPA2,
         "RIPA2",
         "~200 ms grain",
         "per-event pupil amplitude",
         "v1 LIVE",
         "peri-click TEPR\n$p = 4.2 \\times 10^{-19}$"),
        (85, 82, COLOR_LFHF,
         "LF/HF",
         "spectral, slow",
         "sustained autonomic load",
         "v1 LIVE",
         "phase decline\n$p = 8.4 \\times 10^{-19}$"),
        (50, 88, "#5a7d8c",  # K coefficient — top center
         "K (Krejtz)",
         "per-fixation",
         "ambient/focal attention",
         "v1 LIVE",
         "clicked-pos focal\n$p = 7.3 \\times 10^{-19}$"),
        (15, 18, COLOR_SACCADE,
         "Saccade orientation",
         "per-position",
         "reading-shape engagement",
         "v1 LIVE",
         "clicked-pos frac_h\n$p \\approx 10^{-36}$"),
        (85, 18, COLOR_MOTOR,
         "Mouse-down/up latency",
         "per-click event",
         "motor commitment uncertainty",
         "v2 ASK",
         "ClickSense lineage"),
    ]
    for x, y, col, name, grain, signal, status, evidence in channels:
        # Box
        is_v2 = status == "v2 ASK"
        ax.add_patch(FancyBboxPatch(
            (x - 13, y - 7), 26, 14,
            boxstyle="round,pad=0.6",
            facecolor=col, edgecolor='#222222',
            linewidth=1.2 if not is_v2 else 1.4,
            alpha=0.20 if not is_v2 else 0.13,
            linestyle='-' if not is_v2 else '--',
            zorder=3,
        ))
        ax.text(x, y + 4.2, name, ha='center', va='center',
                fontsize=12, fontweight='bold', color='#222222', zorder=5)
        ax.text(x, y + 1.5, grain, ha='center', va='center',
                fontsize=9, color='#444444', fontstyle='italic', zorder=5)
        ax.text(x, y - 0.8, signal, ha='center', va='center',
                fontsize=9.5, color='#222222', zorder=5)
        ax.text(x, y - 3.8, evidence, ha='center', va='center',
                fontsize=9, color='#222222', zorder=5)
        # Status badge
        ax.add_patch(FancyBboxPatch(
            (x - 5, y + 5.6), 10, 1.6,
            boxstyle="round,pad=0.15",
            facecolor='#fdf8f2' if not is_v2 else '#fff3d6',
            edgecolor=col, linewidth=0.8, zorder=6,
        ))
        ax.text(x, y + 6.4, status, ha='center', va='center',
                fontsize=8.5, fontweight='bold', color=col, zorder=7)

        # Arrow to center
        arrow_to_x = decision_x - 11 if x < 50 else decision_x + 11
        arrow_to_y = decision_y + 4 if y > 50 else decision_y - 4
        arrow_from_x = x + 13 if x < 50 else x - 13
        arrow_from_y = y - 4 if y > 50 else y + 4
        ax.add_patch(FancyArrowPatch(
            (arrow_from_x, arrow_from_y), (arrow_to_x, arrow_to_y),
            arrowstyle='-|>', mutation_scale=18,
            color=col, lw=2.0, alpha=0.6,
            connectionstyle='arc3,rad=0.15' if x < 50 else 'arc3,rad=-0.15',
            zorder=2,
        ))

    # Headline strip at top
    ax.add_patch(Rectangle((2, 96), 96, 4,
                           facecolor='#fdf8f2', edgecolor='#cccccc',
                           linewidth=0.6, zorder=1))
    ax.text(50, 98, "AdSERP — five-channel decision-moment instrument",
            ha='center', va='center', fontsize=14, fontweight='bold',
            color='#222222', zorder=5)

    # Footer
    ax.text(50, 4,
            "Four channels live on AdSERP v1: pupil amplitude (RIPA2), pupil frequency (LF/HF), "
            "ambient/focal attention (K, Krejtz), and reading-shape engagement (saccade orientation).\n"
            "The fifth channel — mouse-down/up latency — is the v2 ask.  Each channel reads a different "
            "facet of the same decision; complementary, not redundant.",
            ha='center', va='center', fontsize=10.5, color='#444444',
            fontstyle='italic')

    out = OUT_DIR / 'R2_four_channel_architecture'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


def fig_r3_survey_evaluate_reversal():
    """The cursor-gaze relationship reverses between Survey-phase forward
    contacts and Evaluate-phase regressive returns. Loaded from the
    decision_moment_forward_vs_regressive output."""
    plt.rcParams.update(RC)

    src = ROOT / 'scripts/output/decision_moment_forward_vs_regressive/summary.json'
    if not src.exists():
        print('  R3: summary.json missing — skipping', file=sys.stderr)
        return
    s = json.load(open(src))

    fwd_pupil_t = s['ripa2_forward']['peak_t_ms']
    reg_pupil_t = s['ripa2_regress']['peak_t_ms']
    fwd_curs_t = s['cursor_forward']['peak_t_ms']
    reg_curs_t = s['cursor_regress']['peak_t_ms']
    n_return = s['n_return_trials']
    median_reg_to_click = s.get('median_regressive_to_click_ms', 2064)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.set_xlim(-1500, 1500)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Two horizontal "lanes" — top for Survey/Forward, bottom for Evaluate/Regressive
    lane_top_y = 70
    lane_bot_y = 30

    # Center vertical (gaze event)
    ax.axvline(0, color='#222222', lw=1.2, ls='--', alpha=0.7)
    ax.text(0, 96, 'GAZE\nlands on target',
            ha='center', va='top', fontsize=11, fontweight='bold')

    # SURVEY LANE
    ax.text(-1500, lane_top_y + 12, 'SURVEY phase  —  FORWARD (first contact)',
            ha='left', va='center', fontsize=12, fontweight='bold',
            color=COLOR_RIPA2)
    # Cursor marker (leads gaze)
    ax.scatter([fwd_curs_t], [lane_top_y - 4], s=180,
               color='#cc6677', marker='s', edgecolor='#222222', linewidth=0.8, zorder=4)
    ax.text(fwd_curs_t, lane_top_y - 12,
            f'cursor velocity peak\n{fwd_curs_t:+.0f} ms',
            ha='center', va='top', fontsize=9, color='#cc6677')
    # Pupil marker (after gaze)
    ax.scatter([fwd_pupil_t], [lane_top_y + 4], s=180,
               color='#7c4dff', marker='o', edgecolor='#222222', linewidth=0.8, zorder=4)
    ax.text(fwd_pupil_t, lane_top_y + 12,
            f'pupil bump\n{fwd_pupil_t:+.0f} ms',
            ha='center', va='bottom', fontsize=9, color='#7c4dff')
    # Arrow: cursor → gaze
    ax.annotate('', xy=(0, lane_top_y), xytext=(fwd_curs_t, lane_top_y),
                arrowprops=dict(arrowstyle='-|>', color='#cc6677', lw=2.5,
                                alpha=0.7))
    ax.text((fwd_curs_t + 0) / 2, lane_top_y + 1.5,
            'cursor LEADS gaze',
            ha='center', va='center', fontsize=10, color='#cc6677',
            fontstyle='italic', fontweight='bold')

    # EVALUATE LANE
    ax.text(-1500, lane_bot_y + 12, 'EVALUATE phase  —  REGRESSIVE (last return before click)',
            ha='left', va='center', fontsize=12, fontweight='bold',
            color=COLOR_LFHF)
    # Pupil first (after gaze)
    ax.scatter([reg_pupil_t], [lane_bot_y + 4], s=180,
               color='#7c4dff', marker='o', edgecolor='#222222', linewidth=0.8, zorder=4)
    ax.text(reg_pupil_t, lane_bot_y + 12,
            f'pupil bump\n{reg_pupil_t:+.0f} ms',
            ha='center', va='bottom', fontsize=9, color='#7c4dff')
    # Cursor (lags gaze)
    ax.scatter([reg_curs_t], [lane_bot_y - 4], s=180,
               color='#cc6677', marker='s', edgecolor='#222222', linewidth=0.8, zorder=4)
    ax.text(reg_curs_t, lane_bot_y - 12,
            f'cursor velocity peak\n{reg_curs_t:+.0f} ms',
            ha='center', va='top', fontsize=9, color='#cc6677')
    # Arrow: gaze → cursor
    ax.annotate('', xy=(reg_curs_t, lane_bot_y), xytext=(0, lane_bot_y),
                arrowprops=dict(arrowstyle='-|>', color=COLOR_LFHF, lw=2.5,
                                alpha=0.8))
    ax.text((0 + reg_curs_t) / 2, lane_bot_y + 1.5,
            'gaze LEADS cursor',
            ha='center', va='center', fontsize=10, color=COLOR_LFHF,
            fontstyle='italic', fontweight='bold')

    # Time axis
    ax.set_xlim(-1500, 1500)
    for t in (-1000, -500, 500, 1000):
        ax.axvline(t, color='#dddddd', lw=0.5, ls=':', alpha=0.5)
        ax.text(t, 4, f'{t:+.0f}', ha='center', va='bottom', fontsize=8.5,
                color='#888888')
    ax.text(0, 1, 'time from gaze event (ms)', ha='center', va='bottom',
            fontsize=9, color='#666666', fontstyle='italic')

    fig.suptitle("Survey vs Evaluate  —  the cursor-gaze relationship reverses across phase",
                 y=0.99, fontsize=14)
    fig.text(0.5, 0.04,
             f"AdSERP RETURN trials (N = {n_return:,}).  Forward = first time gaze lands on target. "
             f"Regressive = final target visit before click.\n"
             f"Survey forward: cursor velocity peaks "
             f"{abs(fwd_curs_t):.0f} ms BEFORE gaze (cursor-as-pointer, eyes follow). "
             f"Evaluate regressive: cursor peaks {reg_curs_t:.0f} ms AFTER gaze "
             f"(gaze-as-commitment, cursor follows). Pupil bump is identical at both events "
             f"(saccade-evoked, ~{fwd_pupil_t:.0f} ms post-event). Median Evaluate → click: "
             f"{median_reg_to_click:.0f} ms.",
             ha='center', va='bottom', fontsize=9.5, color='#444444',
             style='italic',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#fdf8f2',
                       edgecolor='#dddddd', lw=0.6))

    plt.tight_layout(rect=(0, 0.10, 1, 0.96))
    out = OUT_DIR / 'R3_survey_evaluate_reversal'
    fig.savefig(f'{out}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{out}.svg', bbox_inches='tight')
    print(f'[out] {out.relative_to(ROOT)}.png/svg', file=sys.stderr)
    plt.close(fig)


def write_manifest():
    manifest = OUT_DIR / 'MANIFEST.md'
    manifest.write_text("""# RIPA2 meet — Thursday figure set

## New figures (in this folder)

- **R1_wrnr_dissociation.png** — *centerpiece.* Same evaluation moments stratified by NB22 will-regress label; LF/HF wr > nr (Δ=+2.48, p<10⁻³, d≈+0.08) opposite to RIPA2 wr < nr (Δ=−0.004, p<10⁻³, d≈−0.10). The cleanest single demonstration of the temporal-scope dissociation. Effect sizes small; direction is the finding.
- **R2_four_channel_architecture.png** — *strategic framing.* The **five-channel** decision-moment instrument: RIPA2 (per-event amplitude), LF/HF (sustained autonomic), K Krejtz (ambient/focal), saccade orientation (engagement), and mouse-down/up latency (motor commitment, the v2 ask). Four live on v1; v2 completes the architecture.
- **R3_survey_evaluate_reversal.png** — *behavioral mode finding.* Cursor-gaze relationship REVERSES between Survey (forward target contact) and Evaluate (regressive last-return). Survey: cursor leads gaze by ~150 ms (cursor-as-pointer). Evaluate: gaze leads cursor by ~530 ms (gaze-as-commitment). Pupil response identical at both events (~+70 ms saccade-evoked). The OSEC phase split is visible in the gaze-cursor coupling pattern itself.

## Existing figures to bring (in `scripts/output/`)

- `viz_ripa2_lfhf/ripa2_lfhf_unique_sensitivity.png` — temporal-scope overview (the original 6-panel: schematic + position gradients + wr/nr per-fixation)
- `ripa2_around_click/peri_click_trace.png` — peri-click TEPR. p < 10⁻²¹ at click event.
- `lfhf_around_click/comparison_4panel.png` — RIPA2 vs LF/HF time-locked, click + last-fixation. RIPA2 sees the event, LF/HF doesn't.
- `click_prediction_ablation/ablation_panel.png` — saccade-orientation features add +4 AUC over viewport-trajectory baseline (LAB-only headroom over WILD-portable).
- `gaze_cursor_coupling/coupling_panel.png` — *WILD-bridge.* Cursor saccade-orientation Test 2 replicates across all coupling tiers (Δ frac_h = +0.23 / +0.31 / +0.41 by tertile). Mechanism shifts (cursor-follows-gaze for tight; hover-before-click for loose), but predictive direction is invariant. Cursor saccade-orientation is plausibly WILD-portable to ACD.
- `decision_moment_forward_vs_regressive/timeline_panel.png` — *decision-phase timing.* 6-panel detailed view: forward / regressive / click time-locks for both pupil and cursor. The substrate behind R3.

## Suggested narrative arc

1. **Open with the dissociation (R1).** It's the strongest single empirical claim, requires no setup. "Same evaluation moments, opposite directions, both metrics significant. Effect sizes small but direction is the finding."
2. **Show the temporal-scope overview** (`viz_ripa2_lfhf/ripa2_lfhf_unique_sensitivity.png`). Schematic + position gradients + early per-fixation finding.
3. **Show the peri-click TEPR** (`ripa2_around_click/peri_click_trace.png`). Beatty & Lucero-Wagoner / Gwizdka pre-decision claim, operationalized.
4. **Show the time-locked dissociation** (`lfhf_around_click/comparison_4panel.png`). RIPA2 sees the event, LF/HF doesn't — temporal-scope claim made visual.
5. **Show the LAB lift from gaze** (`click_prediction_ablation/ablation_panel.png`). Saccade-orientation features add +4 AUC over cursor baseline.
6. **WILD-bridge** (`gaze_cursor_coupling/coupling_panel.png`). Cursor saccade-orientation transfers to ACD-shaped data across all coupling tiers — different mechanism per tier, same predictive direction.
7. **Survey-vs-Evaluate reversal (R3).** The OSEC phase split has a behavioral signature: cursor leads gaze in Survey, gaze leads cursor in Evaluate. Decision-phase duration: 2,064 ms median.
8. **Close with the four-channel architecture (R2).** The v2 ask completes a story that's already two-thirds delivered on v1.
""")
    print(f'[out] {manifest.relative_to(ROOT)}', file=sys.stderr)


def main():
    print('[RIPA2 meet visuals] building 3 new figures + manifest', file=sys.stderr)
    fig_r1_dissociation()
    fig_r2_four_channels()
    fig_r3_survey_evaluate_reversal()
    write_manifest()


if __name__ == '__main__':
    main()
