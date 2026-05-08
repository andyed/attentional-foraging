"""Visualize what RIPA2 and LF/HF are uniquely sensitive to.

Composite figure with two rows:
  Row 1 (schematic): fixation sequence + per-fixation RIPA2 amplitude track
                     + windowed LF/HF rolling track.
                     Shows the temporal-resolution dissociation.
  Row 2 (empirical): 2×2 grid using NB14 / NB18 canonical numbers.
                     (a) LF/HF × position    (b) RIPA2 × position
                     (c) LF/HF wr vs nr      (d) RIPA2 wr vs nr (the unique
                                                  encoding signal)

All numbers come from canonical sources:
  - AdSERP/data/butterworth-lfhf-by-position.json
  - AdSERP/data/ripa2-by-position.json
  - AdSERP/data/encoding-vs-retrieval.json

Output:
  scripts/output/viz_ripa2_lfhf/ripa2_lfhf_unique_sensitivity.{png,svg}
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

# ── muriel light editorial rcparams (inlined for self-containment) ──
RC = {
    "figure.dpi":         120,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "font.family":        "serif",
    "font.serif":         ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size":          12,
    "axes.titlesize":     14,
    "axes.titleweight":   "regular",
    "axes.labelsize":     12,
    "xtick.labelsize":    10,
    "ytick.labelsize":    10,
    "legend.fontsize":    10,
    "figure.facecolor":   "#fafaf8",
    "axes.facecolor":     "#fafaf8",
    "savefig.facecolor":  "#fafaf8",
    "axes.edgecolor":     "#222222",
    "axes.labelcolor":    "#222222",
    "xtick.color":        "#222222",
    "ytick.color":        "#222222",
    "text.color":         "#222222",
    "grid.color":         "#dddddd",
    "grid.linewidth":     0.6,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.linewidth":     0.8,
}

# RIPA2 = purple (matches gazeplot-explorer convention from cartographer)
# LF/HF = amber (matches existing AdSERP UI convention)
COLOR_RIPA2 = "#7c4dff"
COLOR_LFHF  = "#d4a574"
COLOR_NEUTRAL = "#888888"
COLOR_FAINT = "#bbbbbb"

ROOT = Path(__file__).resolve().parent.parent
LFHF_PATH = ROOT / "AdSERP/data/butterworth-lfhf-by-position.json"
RIPA2_PATH = ROOT / "AdSERP/data/ripa2-by-position.json"
ENC_PATH = ROOT / "AdSERP/data/encoding-vs-retrieval.json"
OUT_DIR = ROOT / "scripts/output/viz_ripa2_lfhf"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_position_medians(path: Path, key: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (positions array, per-position median)."""
    data = json.load(open(path))
    by_pos: dict[int, list[float]] = {}
    for trial in data.values():
        for seg in trial.get("positions", []):
            v = seg.get(key)
            if v is None or not math.isfinite(v):
                continue
            p = int(seg["pos"])
            if p < 0 or p > 10:
                continue
            by_pos.setdefault(p, []).append(float(v))
    positions = np.array(sorted(by_pos.keys()))
    medians = np.array([np.median(by_pos[p]) for p in positions])
    return positions, medians


def load_will_regress_pairs(metric: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (will_regress_values, no_regress_values) for first-pass fixations."""
    enc = json.load(open(ENC_PATH))
    wr, nr = [], []
    for trial in enc.values():
        for fix in trial.get("first_pass") or []:
            v = fix.get(metric)
            if v is None or not math.isfinite(v):
                continue
            (wr if fix.get("will_regress") else nr).append(float(v))
    return np.array(wr), np.array(nr)


# ── Synthetic schematic data (Row 1) ─────────────────────────────────────
def make_schematic(rng: np.random.Generator, dur_s: float = 8.0,
                   fix_rate_hz: float = 3.0):
    """Return (fix_t, fix_amp_ripa2, lfhf_t, lfhf_y) — synthetic illustrative
    timeseries. Not real data — caption labels it as schematic."""
    n_fix = int(dur_s * fix_rate_hz)
    fix_t = np.sort(rng.uniform(0.2, dur_s - 0.2, n_fix))
    # Per-fixation arousal: noisy with one transient peak
    base = 0.08 + 0.015 * rng.standard_normal(n_fix)
    peak_idx = n_fix // 2
    base[peak_idx] += 0.06  # encoding-completion-style spike
    base[peak_idx + 2] += 0.04
    fix_amp = np.clip(base, 0.04, 0.20)

    # LF/HF: smooth windowed estimate (~7.5s window slid across)
    lfhf_t = np.linspace(0, dur_s, 200)
    # Slow declining trend with mild noise
    trend = 22 - 1.4 * lfhf_t + 1.2 * np.sin(0.4 * lfhf_t)
    trend += 0.6 * rng.standard_normal(len(lfhf_t))
    return fix_t, fix_amp, lfhf_t, trend


def main():
    plt.rcParams.update(RC)

    # ── Build figure: 2 rows, row-1 schematic full-width, row-2 4 panels ──
    fig = plt.figure(figsize=(11, 8.4), constrained_layout=False)
    gs = fig.add_gridspec(
        nrows=2, ncols=4,
        height_ratios=[1.05, 1.55],
        hspace=0.55, wspace=0.45,
        left=0.07, right=0.97, top=0.93, bottom=0.07,
    )

    # ===== Row 1: schematic timeline =====================================
    ax_sch = fig.add_subplot(gs[0, :])
    rng = np.random.default_rng(42)
    fix_t, fix_amp, lfhf_t, lfhf_y = make_schematic(rng)

    # RIPA2: stem-and-marker per fixation
    for t, a in zip(fix_t, fix_amp):
        ax_sch.plot([t, t], [0, a], color=COLOR_RIPA2, alpha=0.55, lw=1.2, zorder=2)
    ax_sch.scatter(fix_t, fix_amp, s=24, color=COLOR_RIPA2, zorder=3,
                   label="RIPA2 (per-fixation amplitude, ~200 ms)")

    # LF/HF: smooth curve on twin axis (rescaled)
    ax2 = ax_sch.twinx()
    ax2.plot(lfhf_t, lfhf_y, color=COLOR_LFHF, lw=2.0, zorder=4,
             label="LF/HF (windowed frequency, slow autonomic)")
    # Shaded band illustrating the rolling window
    win_center = 4.0
    win_half = 3.75
    ax2.axvspan(win_center - win_half, win_center + win_half,
                color=COLOR_LFHF, alpha=0.08, zorder=1)
    ax2.text(win_center, 26.5, "LF/HF integration window (multi-second)",
             ha="center", va="bottom", color=COLOR_LFHF,
             fontsize=10, fontstyle="italic")

    # Fixation tick marks at the bottom
    for t in fix_t:
        ax_sch.plot([t, t], [-0.012, -0.005], color="#444444", lw=0.8, zorder=2)
    ax_sch.text(0.12, -0.020, "fixations", color="#444444", fontsize=9,
                fontstyle="italic", va="top")

    ax_sch.set_xlim(0, 8.0)
    ax_sch.set_ylim(-0.025, 0.22)
    ax2.set_ylim(8, 30)
    ax_sch.set_xlabel("time within trial (s)")
    ax_sch.set_ylabel("RIPA2 amplitude", color=COLOR_RIPA2)
    ax2.set_ylabel("LF/HF ratio", color=COLOR_LFHF)
    ax_sch.tick_params(axis="y", colors=COLOR_RIPA2)
    ax2.tick_params(axis="y", colors=COLOR_LFHF)
    ax_sch.set_title(
        "Two pupil signals at two temporal scales — schematic",
        loc="left", pad=10, fontsize=14,
    )
    # Combined legend
    h1, l1 = ax_sch.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax_sch.legend(h1 + h2, l1 + l2, loc="upper right",
                  frameon=True, framealpha=0.92, edgecolor="#cccccc",
                  fontsize=10)
    ax_sch.grid(True, axis="x", alpha=0.4)
    ax2.spines["top"].set_visible(False)

    # ===== Row 2: empirical 2×2 grid =====================================
    # (a) LF/HF × position; (b) RIPA2 × position
    # (c) LF/HF wr vs nr     (d) RIPA2 wr vs nr (the unique signal)

    print("[load] LF/HF + RIPA2 per-position medians", file=sys.stderr)
    pos_l, med_l = load_position_medians(LFHF_PATH, "lfhf")
    pos_r, med_r = load_position_medians(RIPA2_PATH, "ripa2")
    print(f"  LF/HF: {len(pos_l)} positions  (range {med_l.min():.2f}–{med_l.max():.2f})",
          file=sys.stderr)
    print(f"  RIPA2: {len(pos_r)} positions  (range {med_r.min():.4f}–{med_r.max():.4f})",
          file=sys.stderr)

    # Panel (a) LF/HF × position
    axA = fig.add_subplot(gs[1, 0])
    axA.plot(pos_l, med_l, marker="o", color=COLOR_LFHF, lw=1.8, ms=6,
             markeredgecolor="#222222", markeredgewidth=0.4)
    axA.set_xlabel("SERP position")
    axA.set_ylabel("median LF/HF")
    axA.set_title(r"(a) LF/HF × position" "\n" r"$\rho = -0.927$,  $p < 0.0001$",
                  fontsize=12)
    axA.grid(True, alpha=0.5)
    axA.set_xticks(range(0, 11, 2))

    # Panel (b) RIPA2 × position
    axB = fig.add_subplot(gs[1, 1])
    axB.plot(pos_r, med_r, marker="o", color=COLOR_RIPA2, lw=1.8, ms=6,
             markeredgecolor="#222222", markeredgewidth=0.4)
    axB.set_xlabel("SERP position")
    axB.set_ylabel("median RIPA2")
    axB.set_title(r"(b) RIPA2 × position" "\n" r"$\rho = -0.909$,  $p = 1.06 \times 10^{-4}$",
                  fontsize=12)
    axB.grid(True, alpha=0.5)
    axB.set_xticks(range(0, 11, 2))

    # Panel (c) LF/HF will-regress vs no-regress (UNDERPOWERED)
    axC = fig.add_subplot(gs[1, 2])
    wr_l, nr_l = load_will_regress_pairs("lfhf")
    print(f"  LF/HF first-pass: wr N={len(wr_l)}, nr N={len(nr_l)}", file=sys.stderr)
    bp_l = axC.boxplot([wr_l, nr_l], positions=[0, 1], widths=0.55,
                       patch_artist=True, showfliers=False,
                       medianprops=dict(color="#222222", lw=1.4),
                       whiskerprops=dict(color="#666666"),
                       capprops=dict(color="#666666"),
                       boxprops=dict(facecolor=COLOR_LFHF, edgecolor="#666666",
                                     alpha=0.45))
    axC.set_xticks([0, 1])
    axC.set_xticklabels(["will-regress", "no-regress"])
    axC.set_ylabel("LF/HF")
    axC.set_title(f"(c) LF/HF × encoding outcome\nN = {len(wr_l)} vs {len(nr_l)}  —  underpowered",
                  fontsize=12)
    axC.grid(True, alpha=0.5, axis="y")
    # Annotate "underpowered"
    axC.text(0.5, 0.05, "K17: too few first-pass fixations\nwith finite LF/HF (window too short)",
             transform=axC.transAxes, ha="center", va="bottom",
             fontsize=9, fontstyle="italic", color="#666666",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf8f2",
                       edgecolor="#cccccc", lw=0.6))

    # Panel (d) RIPA2 will-regress vs no-regress (THE UNIQUE SIGNAL)
    axD = fig.add_subplot(gs[1, 3])
    wr_r, nr_r = load_will_regress_pairs("ripa2")
    print(f"  RIPA2 first-pass: wr N={len(wr_r)}, nr N={len(nr_r)}", file=sys.stderr)
    bp_r = axD.boxplot([wr_r, nr_r], positions=[0, 1], widths=0.55,
                       patch_artist=True, showfliers=False,
                       medianprops=dict(color="#222222", lw=1.4),
                       whiskerprops=dict(color="#666666"),
                       capprops=dict(color="#666666"),
                       boxprops=dict(facecolor=COLOR_RIPA2, edgecolor="#666666",
                                     alpha=0.45))
    axD.set_xticks([0, 1])
    axD.set_xticklabels(["will-regress", "no-regress"])
    axD.set_ylabel("RIPA2")
    axD.set_title(f"(d) RIPA2 × encoding outcome\nN = {len(wr_r):,} vs {len(nr_r):,}  —  p = 0.011",
                  fontsize=12)
    axD.grid(True, alpha=0.5, axis="y")
    # Highlight the unique-signal cell with a soft border
    for spine in axD.spines.values():
        spine.set_edgecolor(COLOR_RIPA2)
        spine.set_linewidth(1.4)
    # Annotate the median values
    med_wr = float(np.median(wr_r))
    med_nr = float(np.median(nr_r))
    axD.annotate(f"median {med_wr:.4f}", xy=(0, med_wr), xytext=(-0.45, med_wr),
                 fontsize=9, color="#444444", va="center")
    axD.annotate(f"median {med_nr:.4f}", xy=(1, med_nr), xytext=(1.1, med_nr),
                 fontsize=9, color="#444444", va="center")

    # ── Figure title + caption ─────────────────────────────────────────
    fig.suptitle(
        "What RIPA2 and LF/HF are uniquely sensitive to",
        fontsize=17, y=0.985,
    )

    caption = (
        "Top — schematic. RIPA2 reads pupil amplitude per fixation (~200 ms grain); "
        "LF/HF reads frequency content over a windowed estimate (multi-second integration; "
        "Duchowski 2026 recommends ≥7.5 s for stable per-window CL indices, "
        "separation, Duchowski 2026). Bottom — both metrics agree on the position "
        "gradient at the aggregate level (a, b: ρ ≈ −0.91 across 11 SERP positions, "
        "AdSERP n = 47 participants, 2,719 trials), but only RIPA2 resolves the "
        "wr/nr dissociation signal at the per-(trial, position) scale (d: will-regress < "
        "no-regress, p = 0.0106, N = 10,466 vs 5,850; NB18 K14). LF/HF is "
        "underpowered for the same comparison (c: N = 20 vs 17, K17) because the "
        "minimum window for stable frequency separation exceeds the typical "
        "first-pass fixation duration. The dissociation is the point: same pupil "
        "signal, different temporal/spectral scope, complementary informational role."
    )
    fig.text(0.07, 0.005, caption, fontsize=9.5, color="#444444",
             wrap=True, ha="left", style="italic",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf8f2",
                       edgecolor="#dddddd", lw=0.6))

    out_png = OUT_DIR / "ripa2_lfhf_unique_sensitivity.png"
    out_svg = OUT_DIR / "ripa2_lfhf_unique_sensitivity.svg"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_svg, bbox_inches="tight")
    print(f"\n[out] {out_png.relative_to(ROOT)}", file=sys.stderr)
    print(f"[out] {out_svg.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
