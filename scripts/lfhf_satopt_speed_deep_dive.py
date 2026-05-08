#!/usr/bin/env python3
"""Deep dive: satopt vs speed terciles as moderators of LF/HF × position.

Reconciles two participant-level groupings the ETTAC team has used:

  • Speed tercile     — sorted by `median_duration_s` (chattiness JSON).
                        The original ETTAC fast/medium/slow split.
  • Satopt tercile    — sorted by `regression_rate` (per_participant_with_traits.csv).
                        Boundaries inherited from ski_jump_satopt summary.

And resolves the LHIPA paradox:

  NB11:K12 reports per-participant ρ(regression_rate, mean_lhipa) = -0.568
  (optimizers carry higher overall load), yet our position-stratified analysis
  found the LF/HF × position curve invariant across satopt terciles. We test
  whether that overall-load difference survives controlling for trial duration.

Outputs (scripts/output/figures/ + scripts/output/lfhf_satopt_tercile/):
  satopt_vs_speed_crosstab.{png,pdf}
  lfhf_speed_vs_satopt_curves.{png,pdf}
  lfhf_intercept_slope_by_metric.{png,pdf}
  lhipa_paradox_partial_correlation.{png,pdf}
  deep_dive_summary.json
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

REPO = Path("/Users/andyed/Documents/dev/attentional-foraging")
LFHF_JSON = REPO / "AdSERP/data/butterworth-lfhf-by-position.json"
TRAITS_CSV = REPO / "scripts/output/survey_bimodality/per_participant_with_traits.csv"
CHATTINESS_JSON = REPO / "notebooks-v2/chattiness_per_participant.json"
SATOPT_SUMMARY = REPO / "scripts/output/ski_jump_satopt/summary.json"

FIG_DIR = REPO / "scripts/output/figures"
OUT_DIR = REPO / "scripts/output/lfhf_satopt_tercile"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INK = "#1a1a2e"
SAT_COLOR = {"satisficer": "#7fcdbb", "mixed": "#41b6c4", "optimizer": "#253494"}
SPD_COLOR = {"fast":       "#fdae61", "medium": "#d7642f", "slow":      "#7f0000"}

POSITIONS = list(range(0, 11))
EARLY_POSITIONS = [0, 1, 2, 3]
LATE_POSITIONS = [4, 5, 6, 7, 8, 9, 10]
N_BOOT = 5000


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_lfhf() -> dict[str, dict[int, list[float]]]:
    with open(LFHF_JSON) as f:
        d = json.load(f)
    by_p: dict[str, dict[int, list[float]]] = {}
    for trial_id, trial in d.items():
        pid = trial_id.split("-")[0]
        by_p.setdefault(pid, {p: [] for p in POSITIONS})
        for pos_obj in trial["positions"]:
            pos = pos_obj["pos"]
            v = pos_obj["lfhf"]
            if v is None or not math.isfinite(v) or pos not in POSITIONS:
                continue
            by_p[pid][pos].append(float(v))
    return by_p


def load_traits() -> dict[str, dict]:
    out: dict[str, dict] = {}
    def _f(v):
        try:
            return float(v) if v not in (None, "", "NaN", "nan") else None
        except (TypeError, ValueError):
            return None
    with open(TRAITS_CSV) as f:
        for row in csv.DictReader(f):
            out[row["participant"]] = {
                "regression_rate": _f(row.get("regression_rate")),
                "mean_lhipa": _f(row.get("mean_lhipa")),
                "median_tti_s": _f(row.get("median_tti_s")),
                "mean_fixations": _f(row.get("mean_fixations")),
            }
    out = {pid: rec for pid, rec in out.items()
           if rec["regression_rate"] is not None and rec["mean_lhipa"] is not None}
    return out


def load_speed() -> dict[str, float]:
    with open(CHATTINESS_JSON) as f:
        d = json.load(f)
    return {pid: rec["median_duration_s"] for pid, rec in d["participants"].items()}


def satopt_boundaries() -> tuple[float, float]:
    with open(SATOPT_SUMMARY) as f:
        s = json.load(f)
    return s["tier_boundaries_regression_rate"]["t1"], s["tier_boundaries_regression_rate"]["t2"]


# ---------------------------------------------------------------------------
# Tercile assignment
# ---------------------------------------------------------------------------

def assign_satopt(rate: float, t1: float, t2: float) -> str:
    if rate <= t1:
        return "satisficer"
    if rate <= t2:
        return "mixed"
    return "optimizer"


def assign_speed(speed: dict[str, float]) -> dict[str, str]:
    """Replicates regenerate_lfhf_plots.py:308-316 — sort by median_duration_s,
    bottom-third = fast, mid-third = medium, top-third = slow.
    """
    pids = sorted(speed.keys(), key=lambda p: speed[p])
    n = len(pids)
    t1 = n // 3
    t2 = 2 * n // 3
    out = {}
    for i, pid in enumerate(pids):
        out[pid] = "fast" if i < t1 else ("medium" if i < t2 else "slow")
    return out


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def per_p_per_pos_median(
    by_p: dict[str, dict[int, list[float]]], min_obs: int = 3
) -> dict[str, dict[int, float | None]]:
    out = {}
    for pid, posmap in by_p.items():
        out[pid] = {}
        for pos in POSITIONS:
            vals = posmap.get(pos, [])
            out[pid][pos] = float(np.median(vals)) if len(vals) >= min_obs else None
    return out


def bootstrap_ci(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return float("nan"), float("nan"), float("nan")
    arr = np.asarray(values, dtype=float)
    med = float(np.median(arr))
    boots = np.empty(N_BOOT)
    n = len(arr)
    for b in range(N_BOOT):
        boots[b] = np.median(arr[np.random.randint(0, n, size=n)])
    return med, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def per_p_intercept(pp_pos_med: dict[str, dict[int, float | None]]) -> dict[str, float | None]:
    """Median LF/HF over EARLY_POSITIONS per participant — the 'starting load' proxy."""
    out: dict[str, float | None] = {}
    for pid, posmap in pp_pos_med.items():
        vals = [posmap[p] for p in EARLY_POSITIONS if posmap.get(p) is not None]
        out[pid] = float(np.median(vals)) if len(vals) >= 2 else None
    return out


def per_p_slope(pp_pos_med: dict[str, dict[int, float | None]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for pid, posmap in pp_pos_med.items():
        xs, ys = [], []
        for pos in POSITIONS:
            v = posmap.get(pos)
            if v is not None:
                xs.append(pos)
                ys.append(v)
        if len(xs) >= 4:
            slope, _ = np.polyfit(xs, ys, 1)
            out[pid] = float(slope)
        else:
            out[pid] = None
    return out


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def partial_spearman(x: list[float], y: list[float], z: list[float]) -> tuple[float, float]:
    """Partial Spearman correlation of x and y controlling for z.
    Computed via residuals of rank-rank linear fits.
    """
    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rz = stats.rankdata(z)
    # OLS regress rx on rz, ry on rz; correlate residuals
    A = np.column_stack([np.ones_like(rz), rz])
    bx, *_ = np.linalg.lstsq(A, rx, rcond=None)
    by, *_ = np.linalg.lstsq(A, ry, rcond=None)
    res_x = rx - A @ bx
    res_y = ry - A @ by
    rho, _ = stats.spearmanr(res_x, res_y)
    # Approximate p-value: t-test on n-3 df (adjust for one controlled covariate)
    n = len(x)
    if abs(rho) >= 1.0 - 1e-9:
        p = 0.0
    else:
        t = rho * math.sqrt((n - 3) / (1 - rho * rho))
        p = 2 * (1 - stats.t.cdf(abs(t), df=n - 3))
    return float(rho), float(p)


# ---------------------------------------------------------------------------
# Figure 1 — cross-tab
# ---------------------------------------------------------------------------

def fig_crosstab(satopt: dict[str, str], speed: dict[str, str], traits: dict, dur: dict) -> dict:
    pids = sorted(set(satopt) & set(speed))
    sat_levels = ["satisficer", "mixed", "optimizer"]
    spd_levels = ["fast", "medium", "slow"]
    tab = np.zeros((3, 3), dtype=int)
    for pid in pids:
        i = sat_levels.index(satopt[pid])
        j = spd_levels.index(speed[pid])
        tab[i, j] += 1

    rates = [traits[p]["regression_rate"] for p in pids]
    durs = [dur[p] for p in pids]
    rho_rate_dur, p_rate_dur = stats.spearmanr(rates, durs)

    # Chi-square independence
    chi2, p_chi, dof, exp = stats.chi2_contingency(tab)

    # Cramér's V for effect size on 3x3
    n = tab.sum()
    cramers_v = math.sqrt(chi2 / (n * (min(tab.shape) - 1)))

    fig, (ax_tab, ax_scat) = plt.subplots(1, 2, figsize=(13, 5.5), facecolor="white")

    im = ax_tab.imshow(tab, cmap="Purples", vmin=0)
    ax_tab.set_xticks(range(3))
    ax_tab.set_yticks(range(3))
    ax_tab.set_xticklabels(spd_levels, color=INK, fontsize=11)
    ax_tab.set_yticklabels(sat_levels, color=INK, fontsize=11)
    ax_tab.set_xlabel("Speed tercile (median_duration_s)", color=INK, fontsize=11)
    ax_tab.set_ylabel("Satopt tercile (regression_rate)", color=INK, fontsize=11)
    for i in range(3):
        for j in range(3):
            cnt = tab[i, j]
            row_total = tab[i].sum()
            col_total = tab[:, j].sum()
            txt_color = "white" if cnt >= tab.max() * 0.6 else INK
            ax_tab.text(j, i - 0.10, f"n={cnt}", ha="center", va="center",
                        color=txt_color, fontsize=12, fontweight="bold")
            row_pct = 100 * cnt / row_total if row_total else 0
            ax_tab.text(j, i + 0.18, f"({row_pct:.0f}% of row)",
                        ha="center", va="center", color=txt_color, fontsize=8.5)
    ax_tab.set_title(
        f"Satopt × Speed tercile cross-tab (n={n})\n"
        f"χ²(4) = {chi2:.2f}, p = {p_chi:.4g}    Cramér's V = {cramers_v:.3f}",
        color=INK, fontsize=11, pad=8,
    )

    ax_scat.scatter(rates, durs, color=INK, alpha=0.65, s=44, edgecolor="white", linewidth=0.6)
    sat_t1, sat_t2 = satopt_boundaries()
    ax_scat.axvline(sat_t1, color="#888", linestyle=":", linewidth=0.8)
    ax_scat.axvline(sat_t2, color="#888", linestyle=":", linewidth=0.8)
    spd_sorted = sorted(durs)
    spd_t1 = spd_sorted[len(spd_sorted) // 3 - 1]
    spd_t2 = spd_sorted[2 * len(spd_sorted) // 3 - 1]
    ax_scat.axhline(spd_t1, color="#888", linestyle=":", linewidth=0.8)
    ax_scat.axhline(spd_t2, color="#888", linestyle=":", linewidth=0.8)
    ax_scat.set_xlabel("Regression rate", color=INK, fontsize=11)
    ax_scat.set_ylabel("Median trial duration (s)", color=INK, fontsize=11)
    ax_scat.set_title(
        f"Satopt vs Speed at participant level\n"
        f"Spearman ρ = {rho_rate_dur:+.3f}, p = {p_rate_dur:.4g}",
        color=INK, fontsize=11, pad=8,
    )
    ax_scat.tick_params(colors=INK)
    for sp in ("top", "right"):
        ax_scat.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax_scat.spines[sp].set_color(INK)

    fig.suptitle(
        "ETTAC moderator reconciliation — same 47 participants, two terciles",
        color=INK, fontsize=13, y=1.02,
    )
    fig.tight_layout()
    out_png = FIG_DIR / "satopt_vs_speed_crosstab.png"
    out_pdf = FIG_DIR / "satopt_vs_speed_crosstab.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")

    return {
        "table": tab.tolist(),
        "row_labels_satopt": sat_levels,
        "col_labels_speed": spd_levels,
        "chi2": float(chi2),
        "chi2_dof": int(dof),
        "chi2_p": float(p_chi),
        "cramers_v": float(cramers_v),
        "spearman_regrate_duration": {"rho": float(rho_rate_dur), "p": float(p_rate_dur)},
    }


# ---------------------------------------------------------------------------
# Figure 2 — side-by-side LF/HF × position curves
# ---------------------------------------------------------------------------

def _curves(pp_pos_med, group_of, levels):
    np.random.seed(20260417)
    out = {lvl: {} for lvl in levels}
    for lvl in levels:
        members = [p for p, g in group_of.items() if g == lvl]
        for pos in POSITIONS:
            vals = [pp_pos_med[p][pos] for p in members
                    if p in pp_pos_med and pp_pos_med[p][pos] is not None]
            med, lo, hi = bootstrap_ci(vals)
            out[lvl][pos] = {"n": len(vals), "median": med, "ci_lo": lo, "ci_hi": hi}
    return out


def _spearman_by_level(curves):
    out = {}
    for lvl, posmap in curves.items():
        xs = [p for p in POSITIONS if not math.isnan(posmap[p]["median"])]
        ys = [posmap[p]["median"] for p in xs]
        rho, p = stats.spearmanr(xs, ys) if len(xs) >= 3 else (float("nan"), float("nan"))
        out[lvl] = {"rho": float(rho), "p": float(p), "n_positions": len(xs)}
    return out


def fig_side_by_side(pp_pos_med, satopt, speed):
    sat_curves = _curves(pp_pos_med, satopt, list(SAT_COLOR))
    spd_curves = _curves(pp_pos_med, speed, list(SPD_COLOR))
    sat_rho = _spearman_by_level(sat_curves)
    spd_rho = _spearman_by_level(spd_curves)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="white", sharey=True)
    for ax, curves, colors, rho_map, title in [
        (axes[0], sat_curves, SAT_COLOR, sat_rho, "Satopt tercile (regression_rate)"),
        (axes[1], spd_curves, SPD_COLOR, spd_rho, "Speed tercile (median_duration_s)"),
    ]:
        for lvl, color in colors.items():
            xs = [pos for pos in POSITIONS if not math.isnan(curves[lvl][pos]["median"])]
            meds = [curves[lvl][pos]["median"] for pos in xs]
            los = [curves[lvl][pos]["ci_lo"] for pos in xs]
            his = [curves[lvl][pos]["ci_hi"] for pos in xs]
            n_max = max(curves[lvl][p]["n"] for p in POSITIONS)
            rho = rho_map[lvl]["rho"]
            ax.fill_between(xs, los, his, color=color, alpha=0.15, linewidth=0)
            ax.plot(xs, meds, "-o", color=color, linewidth=2.0, markersize=6,
                    markeredgecolor="white", markeredgewidth=0.6,
                    label=f"{lvl} (n={n_max}, ρ={rho:+.3f})")
        ax.set_xlabel("SERP position", color=INK, fontsize=11)
        ax.set_xticks(POSITIONS)
        ax.tick_params(colors=INK)
        ax.set_title(title, color=INK, fontsize=12, pad=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(INK)
        leg = ax.legend(loc="upper right", frameon=True, facecolor="white",
                        edgecolor=INK, fontsize=9.5, labelcolor=INK)
    axes[0].set_ylabel("Butterworth LF/HF (median across participants)",
                       color=INK, fontsize=11)
    fig.suptitle(
        "LF/HF × position by tercile — satopt vs speed (n=47)",
        color=INK, fontsize=13, y=1.005,
    )
    fig.tight_layout()
    out_png = FIG_DIR / "lfhf_speed_vs_satopt_curves.png"
    out_pdf = FIG_DIR / "lfhf_speed_vs_satopt_curves.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    return {"satopt_curves": sat_curves, "speed_curves": spd_curves,
            "satopt_spearman": sat_rho, "speed_spearman": spd_rho}


# ---------------------------------------------------------------------------
# Figure 3 — per-participant intercept and slope vs each metric
# ---------------------------------------------------------------------------

def fig_intercept_slope(pp_pos_med, traits, dur):
    interc = per_p_intercept(pp_pos_med)
    slope = per_p_slope(pp_pos_med)

    pids = sorted(set(interc) & set(slope) & set(traits) & set(dur))
    pids = [p for p in pids if interc[p] is not None and slope[p] is not None]

    rate = np.array([traits[p]["regression_rate"] for p in pids])
    duration = np.array([dur[p] for p in pids])
    inter_arr = np.array([interc[p] for p in pids])
    slope_arr = np.array([slope[p] for p in pids])

    rho_int_rate, p_int_rate = stats.spearmanr(rate, inter_arr)
    rho_slp_rate, p_slp_rate = stats.spearmanr(rate, slope_arr)
    rho_int_dur, p_int_dur = stats.spearmanr(duration, inter_arr)
    rho_slp_dur, p_slp_dur = stats.spearmanr(duration, slope_arr)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9.2), facecolor="white")

    panels = [
        (axes[0, 0], rate, inter_arr, rho_int_rate, p_int_rate,
         "Regression rate", f"Median LF/HF over positions {EARLY_POSITIONS}",
         "Intercept (early-scan load) vs satopt"),
        (axes[0, 1], duration, inter_arr, rho_int_dur, p_int_dur,
         "Median trial duration (s)", f"Median LF/HF over positions {EARLY_POSITIONS}",
         "Intercept (early-scan load) vs speed"),
        (axes[1, 0], rate, slope_arr, rho_slp_rate, p_slp_rate,
         "Regression rate", "Per-participant slope (LF/HF / position)",
         "Gradient slope vs satopt"),
        (axes[1, 1], duration, slope_arr, rho_slp_dur, p_slp_dur,
         "Median trial duration (s)", "Per-participant slope (LF/HF / position)",
         "Gradient slope vs speed"),
    ]
    for ax, x, y, rho, p, xlabel, ylabel, title in panels:
        ax.scatter(x, y, color=INK, alpha=0.65, s=42, edgecolor="white", linewidth=0.6)
        if len(x) >= 3:
            slope_, intercept_ = np.polyfit(x, y, 1)
            xs = np.array([x.min(), x.max()])
            ax.plot(xs, slope_ * xs + intercept_, "-", color="#b2182b", linewidth=1.5, alpha=0.8)
        ax.set_xlabel(xlabel, color=INK, fontsize=11)
        ax.set_ylabel(ylabel, color=INK, fontsize=10.5)
        ax.tick_params(colors=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(INK)
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
        ax.set_title(
            f"{title}\nSpearman ρ = {rho:+.3f}, p = {p:.4g}  ({sig})",
            color=INK, fontsize=11, pad=8,
        )

    fig.suptitle(
        "Per-participant intercept (positions 0–3) and slope vs each grouping metric",
        color=INK, fontsize=13, y=1.005,
    )
    fig.tight_layout()
    out_png = FIG_DIR / "lfhf_intercept_slope_by_metric.png"
    out_pdf = FIG_DIR / "lfhf_intercept_slope_by_metric.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    return {
        "n_participants": len(pids),
        "intercept_x_regression_rate": {"rho": float(rho_int_rate), "p": float(p_int_rate)},
        "intercept_x_duration": {"rho": float(rho_int_dur), "p": float(p_int_dur)},
        "slope_x_regression_rate": {"rho": float(rho_slp_rate), "p": float(p_slp_rate)},
        "slope_x_duration": {"rho": float(rho_slp_dur), "p": float(p_slp_dur)},
    }


# ---------------------------------------------------------------------------
# Figure 4 — LHIPA paradox: partial correlation
# ---------------------------------------------------------------------------

def fig_lhipa_paradox(traits, dur):
    pids = sorted(set(traits) & set(dur))
    rate = [traits[p]["regression_rate"] for p in pids]
    lhipa = [traits[p]["mean_lhipa"] for p in pids]
    duration = [dur[p] for p in pids]

    rho_rate_lhipa, p_rate_lhipa = stats.spearmanr(rate, lhipa)
    rho_dur_lhipa, p_dur_lhipa = stats.spearmanr(duration, lhipa)
    rho_rate_dur, p_rate_dur = stats.spearmanr(rate, duration)

    par_rate, par_p_rate = partial_spearman(rate, lhipa, duration)
    par_dur, par_p_dur = partial_spearman(duration, lhipa, rate)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), facecolor="white")

    for ax, x, y, rho, p, xlabel, ylabel, title in [
        (axes[0], rate, lhipa, rho_rate_lhipa, p_rate_lhipa,
         "Regression rate", "mean LHIPA",
         "Reproduces NB11:K12"),
        (axes[1], duration, lhipa, rho_dur_lhipa, p_dur_lhipa,
         "Median trial duration (s)", "mean LHIPA",
         "Speed × LHIPA (raw)"),
        (axes[2], rate, duration, rho_rate_dur, p_rate_dur,
         "Regression rate", "Median trial duration (s)",
         "Confounding-link strength"),
    ]:
        ax.scatter(x, y, color=INK, alpha=0.65, s=42, edgecolor="white", linewidth=0.6)
        if len(x) >= 3:
            slope_, intercept_ = np.polyfit(x, y, 1)
            xs = np.array([min(x), max(x)])
            ax.plot(xs, slope_ * xs + intercept_, "-", color="#b2182b", linewidth=1.5, alpha=0.8)
        ax.set_xlabel(xlabel, color=INK, fontsize=10.5)
        ax.set_ylabel(ylabel, color=INK, fontsize=10.5)
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
        ax.set_title(f"{title}\nρ = {rho:+.3f}, p = {p:.4g}  ({sig})",
                     color=INK, fontsize=11, pad=8)
        ax.tick_params(colors=INK)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(INK)

    sig_par_rate = "***" if par_p_rate < 0.001 else ("**" if par_p_rate < 0.01
                   else ("*" if par_p_rate < 0.05 else "ns"))
    sig_par_dur = "***" if par_p_dur < 0.001 else ("**" if par_p_dur < 0.01
                  else ("*" if par_p_dur < 0.05 else "ns"))
    footer = (
        "Partial Spearman correlations (controlling for the third):\n"
        f"  ρ(regression_rate, mean_lhipa | duration) = {par_rate:+.3f}, "
        f"p = {par_p_rate:.4g}  ({sig_par_rate})\n"
        f"  ρ(duration, mean_lhipa | regression_rate)  = {par_dur:+.3f}, "
        f"p = {par_p_dur:.4g}  ({sig_par_dur})"
    )
    fig.text(0.5, -0.04, footer, ha="center", va="top", color=INK,
             fontsize=10.5, family="monospace")

    fig.suptitle(
        "LHIPA paradox — does the regression-rate × LHIPA link survive controlling for trial duration?",
        color=INK, fontsize=13, y=1.04,
    )
    fig.tight_layout()
    out_png = FIG_DIR / "lhipa_paradox_partial_correlation.png"
    out_pdf = FIG_DIR / "lhipa_paradox_partial_correlation.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    return {
        "n_participants": len(pids),
        "raw": {
            "regression_rate_x_lhipa": {"rho": float(rho_rate_lhipa), "p": float(p_rate_lhipa)},
            "duration_x_lhipa": {"rho": float(rho_dur_lhipa), "p": float(p_dur_lhipa)},
            "regression_rate_x_duration": {"rho": float(rho_rate_dur), "p": float(p_rate_dur)},
        },
        "partial": {
            "regression_rate_x_lhipa_given_duration": {"rho": par_rate, "p": par_p_rate},
            "duration_x_lhipa_given_regression_rate": {"rho": par_dur, "p": par_p_dur},
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    by_p = load_lfhf()
    traits = load_traits()
    speed = load_speed()
    t1, t2 = satopt_boundaries()

    pids_all = sorted(set(by_p) & set(traits) & set(speed))
    print(f"n_participants common to LF/HF + traits + chattiness: {len(pids_all)}")

    satopt = {p: assign_satopt(traits[p]["regression_rate"], t1, t2) for p in pids_all}
    speed_t = assign_speed({p: speed[p] for p in pids_all})

    print("\n[Figure 1] Satopt vs Speed cross-tab")
    crosstab = fig_crosstab(satopt, speed_t, traits, speed)
    print(f"  Cramér's V = {crosstab['cramers_v']:.3f}, χ² p = {crosstab['chi2_p']:.4g}")
    print(f"  Spearman(regrate, duration) = {crosstab['spearman_regrate_duration']['rho']:+.3f}, "
          f"p = {crosstab['spearman_regrate_duration']['p']:.4g}")

    pp_pos_med = per_p_per_pos_median(by_p)

    print("\n[Figure 2] Side-by-side LF/HF × position curves")
    curves = fig_side_by_side(pp_pos_med, satopt, speed_t)

    print("\n[Figure 3] Per-participant intercept + slope vs each metric")
    interc_slope = fig_intercept_slope(pp_pos_med, traits, speed)

    print("\n[Figure 4] LHIPA paradox partial correlation")
    paradox = fig_lhipa_paradox(traits, speed)

    summary = {
        "n_participants": len(pids_all),
        "satopt_boundaries": {"t1": t1, "t2": t2},
        "speed_metric": "median_duration_s",
        "early_positions": EARLY_POSITIONS,
        "crosstab_satopt_speed": crosstab,
        "lfhf_curves": curves,
        "intercept_slope_correlations": interc_slope,
        "lhipa_paradox": paradox,
        "interpretation": {
            "crosstab": "If Cramér's V is high (>0.4), the two terciles redundantly carve the cohort. If low (<0.2), they're orthogonal.",
            "intercept_slope": "ns rho values for both intercept and slope vs each metric reinforce that LF/HF×position is unmoderated by deliberation style or speed.",
            "paradox": (
                "If raw regression_rate × LHIPA is significant but the partial correlation "
                "controlling for duration drops to ns, then NB11:K12's apparent satopt-LHIPA "
                "link is mediated by trial duration — longer trials accumulate more low-LHIPA "
                "samples. If the partial stays significant, optimizers really do carry higher "
                "overall load that the LF/HF position-curve aggregate does not see."
            ),
        },
    }
    out_json = OUT_DIR / "deep_dive_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {out_json}")


if __name__ == "__main__":
    main()
