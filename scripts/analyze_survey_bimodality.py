"""Per-participant bimodality analysis of Survey-phase ad over-indexing.

Follow-up to docs/survey-phase-vs-ads.md. The cohort-level 2.45x ad-over-indexing
could hide participant heterogeneity. This script tests whether
per-participant p_ad_survey (fraction of a participant's Survey fixations
landing on ads) is unimodal, bimodal, or right-skewed.

Inputs
------
- scripts/output/survey_vs_ads/per_trial.csv   (from analyze_survey_vs_ads.py)
- notebooks-v2/nb11_participant_panel.json     (LHIPA, regression rate, click pos)
- notebooks-v2/chattiness_per_participant.json (mouse chattiness)

Outputs
-------
- scripts/output/survey_bimodality/per_participant.csv
- scripts/output/survey_bimodality/gmm_fit.json
- scripts/output/survey_bimodality/tercile_comparison.csv
- scripts/output/survey_bimodality/histogram.png
- scripts/output/survey_bimodality/summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats
from sklearn.mixture import GaussianMixture

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
PER_TRIAL = ROOT / "scripts/output/survey_vs_ads/per_trial.csv"
PANEL = ROOT / "notebooks-v2/nb11_participant_panel.json"
CHATTY = ROOT / "notebooks-v2/chattiness_per_participant.json"
OUT = ROOT / "scripts/output/survey_bimodality"
OUT.mkdir(parents=True, exist_ok=True)


def aggregate_per_participant(df: pl.DataFrame) -> pl.DataFrame:
    """Restrict to ad_top trials, aggregate per participant.

    ad_top = trials with a DoubleDeck ad at the top (is_plain_top == False).
    This is the cohort where the prior analysis found the 2.45x
    Survey-phase over-indexing headline.
    """
    ad_top = df.filter(pl.col("is_plain_top") == False)  # noqa: E712

    ad_top = ad_top.with_columns(
        pl.col("tid").str.split("-").list.get(0).alias("participant")
    )

    # Sum over trials then compute ratio (robust to trials with zero survey fix)
    agg = ad_top.group_by("participant").agg(
        pl.col("n_survey_fix_K5").sum().alias("n_survey_fix"),
        pl.col("n_survey_on_ad_K5").sum().alias("n_survey_on_ad"),
        pl.col("ad_area_frac").mean().alias("mean_ad_area_frac"),
        pl.len().alias("n_ad_top_trials"),
    )

    agg = agg.with_columns(
        (pl.col("n_survey_on_ad") / pl.col("n_survey_fix"))
        .alias("p_ad_survey"),
        (pl.col("n_survey_on_ad") / pl.col("n_survey_fix") / pl.col("mean_ad_area_frac"))
        .alias("ad_over_index"),
    )
    return agg.sort("p_ad_survey")


def hartigan_dip_simple(x: np.ndarray) -> float:
    """Very simple dip-like statistic: max deviation between ECDF and its
    greatest convex minorant / least concave majorant (bounded version).

    Not a true Hartigan dip test (no reference distribution), but gives a
    magnitude that can be interpreted alongside skew/kurtosis. Returns 0 for
    perfectly unimodal.
    """
    x = np.sort(x)
    n = len(x)
    ecdf = np.arange(1, n + 1) / n
    # Fit a single linear ramp (uniform reference). Dip = max deviation.
    uniform = (x - x.min()) / (x.max() - x.min() + 1e-12)
    return float(np.max(np.abs(ecdf - uniform)))


def fit_gmm(p: np.ndarray) -> dict:
    """Fit 1- and 2-component GMM to p_ad_survey. Compare by BIC."""
    X = p.reshape(-1, 1)
    results = {}
    for k in (1, 2):
        gmm = GaussianMixture(
            n_components=k,
            covariance_type="full",
            n_init=10,
            random_state=0,
        ).fit(X)
        means = gmm.means_.flatten().tolist()
        stds = np.sqrt(gmm.covariances_.flatten()).tolist()
        weights = gmm.weights_.flatten().tolist()
        results[f"k{k}"] = {
            "bic": float(gmm.bic(X)),
            "aic": float(gmm.aic(X)),
            "log_likelihood": float(gmm.score(X) * len(X)),
            "means": means,
            "stds": stds,
            "weights": weights,
        }
    delta_bic = results["k1"]["bic"] - results["k2"]["bic"]
    results["delta_bic_k1_minus_k2"] = float(delta_bic)
    results["preferred"] = "k2" if delta_bic > 2 else "k1"  # BIC delta > 2 = positive
    return results


def load_panel() -> dict:
    with open(PANEL) as f:
        data = json.load(f)
    return data["participants"]


def load_chattiness() -> dict:
    with open(CHATTY) as f:
        data = json.load(f)
    return data["participants"]


def tercile_comparison(agg: pl.DataFrame) -> pl.DataFrame:
    """Split participants into terciles on p_ad_survey, compare other traits."""
    panel = load_panel()
    chatty = load_chattiness()

    rows = []
    for row in agg.iter_rows(named=True):
        pid = row["participant"]
        panel_row = panel.get(pid, {})
        chatty_row = chatty.get(pid, {})
        rows.append({
            "participant": pid,
            "p_ad_survey": row["p_ad_survey"],
            "ad_over_index": row["ad_over_index"],
            "n_survey_fix": row["n_survey_fix"],
            "n_ad_top_trials": row["n_ad_top_trials"],
            "mean_ad_area_frac": row["mean_ad_area_frac"],
            "mean_lhipa": panel_row.get("mean_lhipa"),
            "regression_rate": panel_row.get("regression_rate"),
            "mean_click_pos": panel_row.get("mean_click_pos"),
            "median_tti_s": panel_row.get("median_tti_s"),
            "mean_fixations": panel_row.get("mean_fixations"),
            "events_per_sec": chatty_row.get("events_per_sec"),
            "dir_changes_per_sec": chatty_row.get("dir_changes_per_sec"),
        })

    full = pl.DataFrame(rows).sort("p_ad_survey")

    # Assign tercile by rank
    n = full.height
    ranks = np.arange(n)
    # 0..n/3 -> "low", n/3..2n/3 -> "mid", 2n/3..n -> "high"
    tercile_labels = np.array(["low"] * n, dtype=object)
    tercile_labels[ranks >= n / 3] = "mid"
    tercile_labels[ranks >= 2 * n / 3] = "high"
    full = full.with_columns(pl.Series("tercile", tercile_labels))

    # Summary per tercile
    metric_cols = [
        "p_ad_survey",
        "ad_over_index",
        "mean_lhipa",
        "regression_rate",
        "mean_click_pos",
        "median_tti_s",
        "mean_fixations",
        "events_per_sec",
        "dir_changes_per_sec",
    ]
    summary = full.group_by("tercile").agg(
        [pl.col(c).mean().alias(f"{c}_mean") for c in metric_cols]
        + [pl.col(c).median().alias(f"{c}_median") for c in metric_cols]
        + [pl.len().alias("n_participants")]
    )
    # Preserve ordering low/mid/high
    summary = summary.with_columns(
        pl.col("tercile").replace_strict(
            {"low": 0, "mid": 1, "high": 2}, return_dtype=pl.Int32
        ).alias("_order")
    ).sort("_order").drop("_order")

    return full, summary, metric_cols


def between_tercile_tests(full: pl.DataFrame, metric_cols: list[str]) -> dict:
    """Compare low vs high tercile on each candidate moderator."""
    low_df = full.filter(pl.col("tercile") == "low")
    high_df = full.filter(pl.col("tercile") == "high")
    results = {}
    for col in metric_cols:
        low_vals = np.array(
            [v for v in low_df[col].to_list() if v is not None], dtype=float
        )
        high_vals = np.array(
            [v for v in high_df[col].to_list() if v is not None], dtype=float
        )
        if len(low_vals) < 3 or len(high_vals) < 3:
            results[col] = {"skipped": True}
            continue
        # Mann-Whitney U (nonparametric, robust to small n)
        u, p = stats.mannwhitneyu(low_vals, high_vals, alternative="two-sided")
        results[col] = {
            "low_median": float(np.median(low_vals)),
            "high_median": float(np.median(high_vals)),
            "diff_high_minus_low": float(np.median(high_vals) - np.median(low_vals)),
            "mannwhitney_u": float(u),
            "mannwhitney_p": float(p),
            "n_low": int(len(low_vals)),
            "n_high": int(len(high_vals)),
        }
    return results


def conditional_over_index(full: pl.DataFrame) -> dict:
    """2.45x held cohort-wide. What's the per-tercile over-index?"""
    out = {}
    for tercile in ("low", "mid", "high"):
        sub = full.filter(pl.col("tercile") == tercile)
        p_ad = sub["p_ad_survey"].mean()
        mean_area = sub["mean_ad_area_frac"].mean()
        out[tercile] = {
            "mean_p_ad_survey": float(p_ad),
            "mean_ad_area_frac": float(mean_area),
            "over_index_ratio": float(p_ad / mean_area),
            "n_participants": int(sub.height),
        }
    return out


def plot_histogram(p: np.ndarray, gmm: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))

    # High-contrast palette
    ax.hist(p, bins=15, color="#1a1a2e", edgecolor="#f5f5f5", linewidth=1.2,
            alpha=0.95, label="Participants (n=47)")

    # Overlay GMM fits
    xs = np.linspace(p.min() - 0.01, p.max() + 0.01, 400)

    k1 = gmm["k1"]
    mu = k1["means"][0]
    sd = k1["stds"][0]
    pdf1 = stats.norm.pdf(xs, mu, sd)
    # scale to hist counts for visual overlay (bin_width * n)
    bin_width = (p.max() - p.min()) / 15
    scale = bin_width * len(p)
    ax.plot(xs, pdf1 * scale, color="#e63946", lw=3,
            label=f"1-comp GMM (BIC={k1['bic']:.1f})")

    k2 = gmm["k2"]
    pdf2 = np.zeros_like(xs)
    for w, m, s in zip(k2["weights"], k2["means"], k2["stds"]):
        pdf2 += w * stats.norm.pdf(xs, m, s)
    ax.plot(xs, pdf2 * scale, color="#06d6a0", lw=3, linestyle="--",
            label=f"2-comp GMM (BIC={k2['bic']:.1f})")

    ax.axvline(float(np.mean(p)), color="#ffd166", lw=2, linestyle=":",
               label=f"mean = {np.mean(p):.3f}")
    ax.axvline(float(np.median(p)), color="#118ab2", lw=2, linestyle=":",
               label=f"median = {np.median(p):.3f}")

    ax.set_xlabel("p_ad_survey  (fraction of Survey fixations landing on ads)",
                  fontsize=13, color="#0b0b10")
    ax.set_ylabel("Participants", fontsize=13, color="#0b0b10")
    ax.set_title("Per-participant Survey-phase ad capture (K=5, ad_top trials)",
                 fontsize=14, color="#0b0b10")
    ax.tick_params(colors="#0b0b10")
    ax.legend(loc="upper right", framealpha=0.95, fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)


def main() -> None:
    print(f"[bimodality] loading {PER_TRIAL}")
    df = pl.read_csv(PER_TRIAL)

    agg = aggregate_per_participant(df)
    print(f"[bimodality] {agg.height} participants with ad_top trials")
    agg.write_csv(OUT / "per_participant.csv")

    p = agg["p_ad_survey"].to_numpy()
    p = p[np.isfinite(p)]

    # Shape stats
    shape = {
        "n": int(len(p)),
        "mean": float(np.mean(p)),
        "median": float(np.median(p)),
        "std": float(np.std(p, ddof=1)),
        "min": float(np.min(p)),
        "max": float(np.max(p)),
        "q25": float(np.quantile(p, 0.25)),
        "q75": float(np.quantile(p, 0.75)),
        "iqr": float(np.quantile(p, 0.75) - np.quantile(p, 0.25)),
        "skewness": float(stats.skew(p)),
        "kurtosis_excess": float(stats.kurtosis(p)),
        "simple_dip_stat": hartigan_dip_simple(p),
    }
    # Normality (rejecting normal isn't the same as bimodal but is diagnostic)
    sw_stat, sw_p = stats.shapiro(p)
    shape["shapiro_W"] = float(sw_stat)
    shape["shapiro_p"] = float(sw_p)

    # GMM fit
    gmm = fit_gmm(p)
    shape["gmm"] = gmm
    print(
        f"[bimodality] GMM delta BIC (k1-k2) = {gmm['delta_bic_k1_minus_k2']:.2f}, "
        f"preferred = {gmm['preferred']}"
    )

    with open(OUT / "gmm_fit.json", "w") as f:
        json.dump(shape, f, indent=2)

    # Tercile comparison
    full, summary, metric_cols = tercile_comparison(agg)
    full.write_csv(OUT / "per_participant_with_traits.csv")
    summary.write_csv(OUT / "tercile_comparison.csv")

    tests = between_tercile_tests(full, metric_cols)
    cond = conditional_over_index(full)

    summary_out = {
        "distribution_shape": shape,
        "tercile_tests_low_vs_high": tests,
        "conditional_over_index_by_tercile": cond,
        "inputs": {
            "per_trial": str(PER_TRIAL),
            "panel": str(PANEL),
            "chattiness": str(CHATTY),
        },
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary_out, f, indent=2)

    # Histogram
    plot_histogram(p, gmm, OUT / "histogram.png")

    print(f"[bimodality] wrote outputs to {OUT}")
    print(f"[bimodality] mean={shape['mean']:.3f} median={shape['median']:.3f} "
          f"skew={shape['skewness']:.2f} kurtosis={shape['kurtosis_excess']:.2f}")
    print(f"[bimodality] GMM preferred = {gmm['preferred']} "
          f"(k1 BIC={gmm['k1']['bic']:.2f}, k2 BIC={gmm['k2']['bic']:.2f})")
    print(f"[bimodality] conditional over-index: "
          f"low={cond['low']['over_index_ratio']:.2f}  "
          f"mid={cond['mid']['over_index_ratio']:.2f}  "
          f"high={cond['high']['over_index_ratio']:.2f}")


if __name__ == "__main__":
    main()
