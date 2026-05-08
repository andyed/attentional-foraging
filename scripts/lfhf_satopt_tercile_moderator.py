#!/usr/bin/env python3
"""LF/HF × position × satisfice-optimize tercile — moderator analysis.

Tests whether the per-position cognitive-load gradient (Butterworth LF/HF) is:
  Prediction A — universal in shape, intercept differs by deliberation tercile
  Prediction B — gradient differs by tercile (e.g. satisficers steeper)

Inputs (read-only):
  AdSERP/data/butterworth-lfhf-by-position.json
  scripts/output/survey_bimodality/per_participant_with_traits.csv
  scripts/output/ski_jump_satopt/summary.json   (tercile boundaries)

Outputs (scripts/output/figures/ + scripts/output/lfhf_satopt_tercile/):
  lfhf_satopt_tercile.png + .pdf
  lfhf_satopt_tercile_summary.json
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO = Path("/Users/andyed/Documents/dev/attentional-foraging")
LFHF_JSON = REPO / "AdSERP/data/butterworth-lfhf-by-position.json"
TRAITS_CSV = REPO / "scripts/output/survey_bimodality/per_participant_with_traits.csv"
SATOPT_SUMMARY = REPO / "scripts/output/ski_jump_satopt/summary.json"
FIG_DIR = REPO / "scripts/output/figures"
OUT_DIR = REPO / "scripts/output/lfhf_satopt_tercile"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INK = "#1a1a2e"
CREAM = "#e6e4d2"

# Sequential palette: light → dark by deliberation depth
TERCILE_COLOR = {
    "satisficer": "#7fcdbb",  # light teal
    "mixed":      "#41b6c4",  # mid teal
    "optimizer":  "#253494",  # deep blue
}

POSITIONS = list(range(0, 11))  # NB14 convention: 0..10
N_BOOT = 5000
RNG = random.Random(20260416)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_lfhf() -> dict:
    """Build {participant_id: {position: [trial_lfhf, ...]}}."""
    with open(LFHF_JSON) as f:
        d = json.load(f)
    by_participant: dict[str, dict[int, list[float]]] = {}
    n_trials = 0
    n_obs = 0
    for trial_id, trial in d.items():
        pid = trial_id.split("-")[0]
        by_participant.setdefault(pid, {p: [] for p in POSITIONS})
        n_trials += 1
        for pos_obj in trial["positions"]:
            pos = pos_obj["pos"]
            lfhf = pos_obj["lfhf"]
            if lfhf is None or not math.isfinite(lfhf):
                continue
            if pos not in POSITIONS:
                continue
            by_participant[pid][pos].append(float(lfhf))
            n_obs += 1
    print(f"loaded {n_trials} trials, {n_obs} non-null position×LF/HF observations, "
          f"{len(by_participant)} participants")
    return by_participant


def load_regression_rate() -> dict[str, float]:
    rates: dict[str, float] = {}
    with open(TRAITS_CSV) as f:
        for row in csv.DictReader(f):
            rates[row["participant"]] = float(row["regression_rate"])
    print(f"loaded regression_rate for {len(rates)} participants")
    return rates


def tercile_boundaries() -> tuple[float, float]:
    with open(SATOPT_SUMMARY) as f:
        s = json.load(f)
    t1 = s["tier_boundaries_regression_rate"]["t1"]
    t2 = s["tier_boundaries_regression_rate"]["t2"]
    print(f"using satopt tercile boundaries: t1={t1:.4f} t2={t2:.4f}")
    return t1, t2


def assign_tercile(rate: float, t1: float, t2: float) -> str:
    if rate <= t1:
        return "satisficer"
    if rate <= t2:
        return "mixed"
    return "optimizer"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def per_participant_per_position_median(
    by_participant: dict[str, dict[int, list[float]]],
    min_obs: int = 3,
) -> dict[str, dict[int, float | None]]:
    """For each (participant, position), median across trials. None if < min_obs."""
    out: dict[str, dict[int, float | None]] = {}
    for pid, pos_map in by_participant.items():
        out[pid] = {}
        for pos in POSITIONS:
            vals = pos_map.get(pos, [])
            if len(vals) < min_obs:
                out[pid][pos] = None
            else:
                out[pid][pos] = float(np.median(vals))
    return out


def bootstrap_median_ci(values: list[float], n_boot: int = N_BOOT) -> tuple[float, float, float]:
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    arr = np.asarray(values, dtype=float)
    med = float(np.median(arr))
    boots = np.empty(n_boot)
    n = len(arr)
    for b in range(n_boot):
        idx = np.random.randint(0, n, size=n)
        boots[b] = np.median(arr[idx])
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    return med, lo, hi


def tercile_position_curve(
    pp_pos_med: dict[str, dict[int, float | None]],
    tercile_of: dict[str, str],
) -> dict[str, dict[int, dict]]:
    """For each (tercile, position): median across participants + bootstrap CI."""
    np.random.seed(20260416)  # reproducible bootstrap
    out: dict[str, dict[int, dict]] = {t: {} for t in TERCILE_COLOR}
    for tercile in TERCILE_COLOR:
        members = [pid for pid, t in tercile_of.items() if t == tercile]
        for pos in POSITIONS:
            vals = [pp_pos_med[pid][pos] for pid in members
                    if pid in pp_pos_med and pp_pos_med[pid][pos] is not None]
            med, lo, hi = bootstrap_median_ci(vals)
            out[tercile][pos] = {
                "n_participants": len(vals),
                "median": med,
                "ci_lo": lo,
                "ci_hi": hi,
            }
    return out


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def per_tercile_spearman(curves: dict[str, dict[int, dict]]) -> dict[str, dict]:
    """Spearman ρ(position, median LF/HF) per tercile."""
    out: dict[str, dict] = {}
    for tercile, pos_map in curves.items():
        positions = []
        medians = []
        for pos in POSITIONS:
            m = pos_map[pos]["median"]
            if not math.isnan(m):
                positions.append(pos)
                medians.append(m)
        if len(positions) >= 3:
            rho, p = stats.spearmanr(positions, medians)
        else:
            rho, p = float("nan"), float("nan")
        out[tercile] = {"rho": float(rho), "p": float(p), "n_positions": len(positions)}
    return out


def per_position_kruskal(
    pp_pos_med: dict[str, dict[int, float | None]],
    tercile_of: dict[str, str],
) -> dict[int, dict]:
    """Per-position Kruskal-Wallis across the 3 terciles (participant medians)."""
    out: dict[int, dict] = {}
    for pos in POSITIONS:
        groups = []
        for tercile in TERCILE_COLOR:
            members = [pid for pid, t in tercile_of.items() if t == tercile]
            vals = [pp_pos_med[pid][pos] for pid in members
                    if pid in pp_pos_med and pp_pos_med[pid][pos] is not None]
            if len(vals) >= 2:
                groups.append(vals)
        if len(groups) == 3 and all(len(g) >= 2 for g in groups):
            try:
                h, p = stats.kruskal(*groups)
            except ValueError:
                h, p = float("nan"), float("nan")
            ns = [len(g) for g in groups]
        else:
            h, p, ns = float("nan"), float("nan"), [len(g) for g in groups]
        out[pos] = {"H": float(h), "p": float(p), "n_per_group": ns}
    return out


def slope_difference_test(
    pp_pos_med: dict[str, dict[int, float | None]],
    tercile_of: dict[str, str],
    n_boot: int = N_BOOT,
) -> dict:
    """Per-participant OLS slope of LF/HF on position; compare slopes across terciles.

    Returns: per-tercile slope median + bootstrap CI of (optimizer - satisficer) slope diff.
    """
    np.random.seed(20260417)
    per_part_slope: dict[str, float] = {}
    for pid, pos_map in pp_pos_med.items():
        xs = []
        ys = []
        for pos in POSITIONS:
            v = pos_map.get(pos)
            if v is not None:
                xs.append(pos)
                ys.append(v)
        if len(xs) >= 4:
            slope, intercept = np.polyfit(xs, ys, 1)
            per_part_slope[pid] = float(slope)

    by_tercile: dict[str, list[float]] = {t: [] for t in TERCILE_COLOR}
    for pid, slope in per_part_slope.items():
        if pid in tercile_of:
            by_tercile[tercile_of[pid]].append(slope)

    summary: dict = {}
    for tercile in TERCILE_COLOR:
        vals = by_tercile[tercile]
        if vals:
            med, lo, hi = bootstrap_median_ci(vals)
            summary[tercile] = {
                "n_participants_with_slope": len(vals),
                "median_slope": med,
                "ci_lo": lo,
                "ci_hi": hi,
            }
        else:
            summary[tercile] = {"n_participants_with_slope": 0}

    # Bootstrap difference of medians: optimizer - satisficer
    sat = np.asarray(by_tercile["satisficer"])
    opt = np.asarray(by_tercile["optimizer"])
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        s_idx = np.random.randint(0, len(sat), size=len(sat))
        o_idx = np.random.randint(0, len(opt), size=len(opt))
        diffs[b] = np.median(opt[o_idx]) - np.median(sat[s_idx])
    summary["diff_optimizer_minus_satisficer"] = {
        "median": float(np.median(diffs)),
        "ci_lo": float(np.percentile(diffs, 2.5)),
        "ci_hi": float(np.percentile(diffs, 97.5)),
        "p_two_sided_bootstrap": float(2 * min((diffs > 0).mean(), (diffs < 0).mean())),
    }
    return summary


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_curves(
    curves: dict[str, dict[int, dict]],
    spearman: dict[str, dict],
    slope_summary: dict,
    counts: dict[str, int],
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6.5), facecolor="white")

    for tercile in ["satisficer", "mixed", "optimizer"]:
        color = TERCILE_COLOR[tercile]
        rate_label = {
            "satisficer": "≤ 0.47",
            "mixed":      "0.47–0.70",
            "optimizer":  "> 0.70",
        }[tercile]
        slope_med = slope_summary[tercile].get("median_slope", float("nan"))
        rho = spearman[tercile]["rho"]
        n = counts[tercile]
        label = (
            f"{tercile}  (regr. rate {rate_label}, n={n})\n"
            f"  ρ(pos, LF/HF) = {rho:+.3f}    "
            f"slope = {slope_med:+.3f} per position"
        )

        xs = [pos for pos in POSITIONS if not math.isnan(curves[tercile][pos]["median"])]
        meds = [curves[tercile][pos]["median"] for pos in xs]
        los = [curves[tercile][pos]["ci_lo"] for pos in xs]
        his = [curves[tercile][pos]["ci_hi"] for pos in xs]

        ax.fill_between(xs, los, his, color=color, alpha=0.18, linewidth=0)
        ax.plot(xs, meds, "-o", color=color, linewidth=2.2, markersize=7,
                markeredgecolor="white", markeredgewidth=0.8, label=label)

    ax.set_xlabel("SERP position (0 = top of results)", color=INK, fontsize=12)
    ax.set_ylabel("Butterworth LF/HF (median across participants)", color=INK, fontsize=12)
    ax.set_xticks(POSITIONS)
    ax.tick_params(colors=INK)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(INK)

    ax.set_title(
        "Per-position cognitive load (LF/HF) by satisfice–optimize tercile  ·  AdSERP, n=47",
        color=INK, fontsize=13, pad=12,
    )

    leg = ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="white",
        edgecolor=INK,
        fontsize=9.5,
        labelcolor=INK,
        title="Deliberation tercile",
        title_fontsize=10,
    )
    leg.get_title().set_color(INK)

    diff = slope_summary["diff_optimizer_minus_satisficer"]
    p_text = "p≈0" if diff["p_two_sided_bootstrap"] < 1e-3 else f"p={diff['p_two_sided_bootstrap']:.3f}"
    footer = (
        f"Slope (optimizer − satisficer) = {diff['median']:+.3f}  "
        f"[95% CI {diff['ci_lo']:+.3f} … {diff['ci_hi']:+.3f}]  ({p_text}, bootstrap)"
    )
    fig.text(
        0.5, 0.005, footer,
        ha="center", va="bottom", color=INK, fontsize=10, style="italic",
    )

    fig.tight_layout(rect=[0, 0.025, 1, 1])

    out_png = FIG_DIR / "lfhf_satopt_tercile.png"
    out_pdf = FIG_DIR / "lfhf_satopt_tercile.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    by_participant = load_lfhf()
    rates = load_regression_rate()
    t1, t2 = tercile_boundaries()

    common_pids = sorted(set(by_participant) & set(rates))
    missing = sorted(set(by_participant) - set(rates))
    print(f"participants in both LF/HF and regression-rate panels: {len(common_pids)}  "
          f"missing-rate: {len(missing)} ({missing[:5]}{'...' if len(missing)>5 else ''})")

    tercile_of = {pid: assign_tercile(rates[pid], t1, t2) for pid in common_pids}
    counts = {t: sum(1 for v in tercile_of.values() if v == t) for t in TERCILE_COLOR}
    print(f"tercile counts: {counts}")

    pp_pos_med = per_participant_per_position_median(by_participant)
    curves = tercile_position_curve(pp_pos_med, tercile_of)
    spearman = per_tercile_spearman(curves)
    kruskal = per_position_kruskal(pp_pos_med, tercile_of)
    slope_summary = slope_difference_test(pp_pos_med, tercile_of)

    print("\n--- Per-tercile Spearman ρ(position, LF/HF) ---")
    for tercile, s in spearman.items():
        print(f"  {tercile:11s}: ρ = {s['rho']:+.3f}  p = {s['p']:.4g}  ({s['n_positions']} positions)")

    print("\n--- Per-position Kruskal-Wallis across terciles ---")
    print(f"  {'pos':>3s} {'H':>8s} {'p':>10s}   n(sat,mix,opt)")
    for pos in POSITIONS:
        k = kruskal[pos]
        ns = ",".join(str(x) for x in k["n_per_group"])
        H = k["H"]; p = k["p"]
        H_s = f"{H:.3f}" if not math.isnan(H) else "nan"
        p_s = f"{p:.4g}" if not math.isnan(p) else "nan"
        print(f"  {pos:>3d} {H_s:>8s} {p_s:>10s}   ({ns})")

    print("\n--- Per-tercile per-participant slope (LF/HF on position) ---")
    for tercile in TERCILE_COLOR:
        s = slope_summary[tercile]
        if "median_slope" in s:
            print(f"  {tercile:11s}: median = {s['median_slope']:+.3f}  "
                  f"95% CI [{s['ci_lo']:+.3f}, {s['ci_hi']:+.3f}]  (n={s['n_participants_with_slope']})")
    diff = slope_summary["diff_optimizer_minus_satisficer"]
    print(f"  optimizer − satisficer slope diff: {diff['median']:+.3f}  "
          f"95% CI [{diff['ci_lo']:+.3f}, {diff['ci_hi']:+.3f}]  "
          f"bootstrap p = {diff['p_two_sided_bootstrap']:.4g}")

    plot_curves(curves, spearman, slope_summary, counts)

    summary = {
        "n_participants_total": len(common_pids),
        "tercile_boundaries_regression_rate": {"t1": t1, "t2": t2},
        "tercile_counts": counts,
        "positions": POSITIONS,
        "curves": curves,
        "spearman_position_lfhf_per_tercile": spearman,
        "kruskal_per_position": {str(p): k for p, k in kruskal.items()},
        "slope_summary": slope_summary,
        "interpretation_note": (
            "Prediction A (universal gradient, intercept differs) is supported if "
            "all three terciles have negative ρ of similar magnitude AND the slope-difference "
            "CI for (optimizer - satisficer) brackets 0. Prediction B (gradient differs) is "
            "supported if the slope-difference CI excludes 0 and/or one tercile shows a flatter "
            "or reversed gradient."
        ),
    }
    out_json = OUT_DIR / "lfhf_satopt_tercile_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
