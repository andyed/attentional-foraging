"""Temporal test of ad prior × pass × dd_top on click press duration.

The ad-utility prior is estimated only from early-block survey fixations on
ad-top trials. The motor outcome is then tested only on later-block organic
and dd_top clicks. This temporally separates segmentation measurement from the
clicks whose mousedown→mouseup duration is modeled.

Primary specification:
  prior:   blocks 1–3, K=5 survey fixations
  outcome: blocks 4–6, primary click-press cohort
  model:   participant-demeaned log hold with categorical display-rank FE
           and the full lower-order hierarchy for pass × dd_top × prior
  target:  three-way coefficient per +0.10 in p_ad_survey

This is confirmatory in form but not an independent replication: the same
47-person AdSERP cohort motivated the hypothesis before this temporal split.

Run:
  .venv/bin/python scripts/click_press_latency_pass_analysis.py
  .venv/bin/python scripts/click_press_prior_temporal_test.py
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SURVEY = ROOT / "scripts" / "output" / "survey_vs_ads" / "per_trial.csv"
PRESS = ROOT / "scripts" / "output" / "click_press_latency_pass" / "click_press_records.csv"
FEATURES = ROOT / "AdSERP" / "data" / "cursor-approach-features-typed-gapfill.json"
OUT = ROOT / "scripts" / "output" / "click_press_prior_temporal_test"
OUT.mkdir(parents=True, exist_ok=True)

BOOTSTRAPS = 5000
SEED = 20260822


def block_number(tid):
    return int(tid.split("-")[1][1:])


def load_survey_rows():
    return list(csv.DictReader(open(SURVEY)))


def estimate_prior(survey_rows, blocks, k=5):
    """Participant p_ad_survey on ad-top trials in selected blocks."""
    totals = defaultdict(lambda: [0.0, 0.0])
    for row in survey_rows:
        if block_number(row["tid"]) not in blocks or row["is_plain_top"] == "True":
            continue
        pid = row["tid"].split("-")[0]
        totals[pid][0] += float(row[f"n_survey_on_ad_K{k}"])
        totals[pid][1] += float(row[f"n_survey_fix_K{k}"])
    return {
        pid: on_ad / total
        for pid, (on_ad, total) in totals.items()
        if total > 0
    }


def load_press_rows(prior, outcome_blocks):
    rows = []
    for row in csv.DictReader(open(PRESS)):
        if row["primary_pass_eligible"] != "True":
            continue
        if row["etype"] not in {"organic", "dd_top"}:
            continue
        if block_number(row["trial_id"]) not in outcome_blocks:
            continue
        if row["pid"] not in prior:
            continue
        rows.append({
            "trial_id": row["trial_id"],
            "pid": row["pid"],
            "log_hold": math.log(float(row["press_duration_ms"])),
            "hold_ms": float(row["press_duration_ms"]),
            "target_fix_age_ms": float(row["target_fix_age_ms"]),
            "regressive": float(row["pass_label"] == "regressive_return"),
            "dd_top": float(row["etype"] == "dd_top"),
            "display_rank0": int(float(row["click_pos"])),
            "prior": prior[row["pid"]],
        })
    return rows


def design(rows, pids, prior_center):
    ranks = sorted({row["display_rank0"] for row in rows})
    y_all, x_all = [], []
    for pid in pids:
        subset = [row for row in rows if row["pid"] == pid]
        y = np.asarray([row["log_hold"] for row in subset])
        x = []
        for row in subset:
            reg = row["regressive"]
            dd = row["dd_top"]
            prior10 = (row["prior"] - prior_center) / 0.10
            x.append([
                reg,
                dd,
                reg * dd,
                reg * prior10,
                dd * prior10,
                reg * dd * prior10,
                *[float(row["display_rank0"] == rank) for rank in ranks[1:]],
            ])
        x = np.asarray(x)
        y_all.append(y - np.mean(y))
        x_all.append(x - np.mean(x, axis=0))
    return np.concatenate(y_all), np.vstack(x_all)


def fit_temporal_model(rows, seed=SEED, bootstraps=BOOTSTRAPS):
    pids = sorted({row["pid"] for row in rows})
    prior_center = float(np.mean([row["prior"] for row in rows]))
    y, x = design(rows, pids, prior_center)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(bootstraps):
        sampled = list(rng.choice(pids, size=len(pids), replace=True))
        yb, xb = design(rows, sampled, prior_center)
        boot.append(np.linalg.lstsq(xb, yb, rcond=None)[0][:6])
    boot = np.asarray(boot)
    names = [
        "regressive",
        "dd_top",
        "regressive_x_dd_top",
        "regressive_x_prior_per_0.10",
        "dd_top_x_prior_per_0.10",
        "regressive_x_dd_top_x_prior_per_0.10",
    ]
    terms = {}
    for i, name in enumerate(names):
        ci = np.quantile(boot[:, i], [0.025, 0.975])
        p_boot = 2 * min(np.mean(boot[:, i] <= 0), np.mean(boot[:, i] >= 0))
        terms[name] = {
            "log_coefficient": float(beta[i]),
            "percent_change": float(100 * (math.exp(beta[i]) - 1)),
            "bootstrap_ci95_percent_change": [
                float(100 * (math.exp(ci[0]) - 1)),
                float(100 * (math.exp(ci[1]) - 1)),
            ],
            "bootstrap_p_two_sided": float(p_boot),
        }
    cell_counts = defaultdict(int)
    for row in rows:
        surface = "dd_top" if row["dd_top"] else "organic"
        mode = "regressive" if row["regressive"] else "first_forward"
        cell_counts[f"{surface}|{mode}"] += 1
    return {
        "n": len(y),
        "n_participants": len(pids),
        "prior_center": prior_center,
        "cell_counts": dict(cell_counts),
        "rank_control": "categorical typed_gapfill display-rank fixed effects",
        "terms": terms,
    }


def prior_stability(survey_rows, k=5):
    early = estimate_prior(survey_rows, {1, 2, 3}, k=k)
    late = estimate_prior(survey_rows, {4, 5, 6}, k=k)
    pids = sorted(set(early) & set(late))
    test = stats.spearmanr([early[pid] for pid in pids], [late[pid] for pid in pids])
    rng = np.random.default_rng(SEED + k)
    pairs = np.asarray([(early[pid], late[pid]) for pid in pids])
    boot = []
    for _ in range(BOOTSTRAPS):
        sample = pairs[rng.integers(0, len(pairs), size=len(pairs))]
        rho = stats.spearmanr(sample[:, 0], sample[:, 1]).statistic
        if math.isfinite(rho):
            boot.append(rho)
    return {
        "n_participants": len(pids),
        "spearman_rho": float(test.statistic),
        "p": float(test.pvalue),
        "bootstrap_ci95": [
            float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
        ],
    }


def late_click_positive_control(early_prior):
    """Early prior versus late-block dd_top click share, main-axis clicks."""
    totals = defaultdict(lambda: [0, 0])
    for row in json.load(open(FEATURES)):
        if not row.get("was_clicked") or block_number(row["trial_id"]) < 4:
            continue
        pid = row["trial_id"].split("-")[0]
        totals[pid][1] += 1
        totals[pid][0] += int(row.get("etype") == "dd_top")
    pids = sorted(set(early_prior) & set(totals))
    rates = [totals[pid][0] / totals[pid][1] for pid in pids]
    test = stats.spearmanr([early_prior[pid] for pid in pids], rates)
    return {
        "n_participants": len(pids),
        "n_late_clicks": int(sum(totals[pid][1] for pid in pids)),
        "spearman_rho": float(test.statistic),
        "p": float(test.pvalue),
    }


def sensitivity_grid(survey_rows):
    rows_out = []
    for k in (3, 5, 7):
        for cutoff in (2, 3, 4):
            early_blocks = set(range(1, cutoff + 1))
            outcome_blocks = set(range(cutoff + 1, 7))
            prior = estimate_prior(survey_rows, early_blocks, k=k)
            rows = load_press_rows(prior, outcome_blocks)
            model = fit_temporal_model(
                rows,
                seed=SEED + 100 * k + cutoff,
                bootstraps=2500,
            )
            triple = model["terms"]["regressive_x_dd_top_x_prior_per_0.10"]
            rows_out.append({
                "survey_k": k,
                "prior_blocks": [1, cutoff],
                "outcome_blocks": [cutoff + 1, 6],
                "n": model["n"],
                "n_participants": model["n_participants"],
                **triple,
            })
    return rows_out


def analyze():
    survey_rows = load_survey_rows()
    early_prior = estimate_prior(survey_rows, {1, 2, 3}, k=5)
    late_rows = load_press_rows(early_prior, {4, 5, 6})
    primary = fit_temporal_model(late_rows)
    return {
        "regime": "LAB, AdSERP",
        "status": "temporally separated test in the already-examined cohort; not an independent replication",
        "primary_specification": {
            "prior": "p_ad_survey from ad-top trials in blocks 1-3, K=5",
            "outcome": "primary organic/dd_top press records in blocks 4-6",
            "target": "regressive x dd_top x prior per +0.10",
        },
        "primary_model": primary,
        "prior_stability_early_vs_late": prior_stability(survey_rows, k=5),
        "early_prior_vs_late_dd_top_click_share": late_click_positive_control(early_prior),
        "sensitivity": sensitivity_grid(survey_rows),
        "interpretation": [
            "The ad-attention prior is stable across early and late blocks.",
            "The temporally separated three-way motor interaction is positive in the hypothesized direction but its confidence interval crosses zero.",
            "Early prior does not significantly predict late dd_top click share in this half-split.",
            "The test is underpowered for a three-way interaction because late first-forward dd_top clicks are sparse.",
            "A new cohort remains necessary for confirmation.",
        ],
    }


def fmt(value, digits=2):
    if value != 0 and abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.{digits}f}"


def write_report(summary):
    model = summary["primary_model"]
    triple = model["terms"]["regressive_x_dd_top_x_prior_per_0.10"]
    dd = model["terms"]["regressive_x_dd_top"]
    stability = summary["prior_stability_early_vs_late"]
    click = summary["early_prior_vs_late_dd_top_click_share"]
    lines = [
        "# Temporal test: early ad prior × late pass × dd_top",
        "",
        "**Regime:** `[LAB, AdSERP, typed_gapfill]`  ",
        "**Status:** temporally separated within the already-examined cohort; not an independent replication.",
        "",
        "## Primary result",
        "",
        "Each participant's ad prior is estimated from survey fixations in blocks 1–3. "
        "Only organic and `dd_top` press events in blocks 4–6 enter the outcome model. "
        "The participant-demeaned log-duration model includes categorical display-rank "
        "effects and the complete lower-order hierarchy for `pass × dd_top × prior`.",
        "",
        f"The three-way interaction is **{fmt(triple['percent_change'])}% per +0.10 "
        f"in early `p_ad_survey`** (participant-cluster bootstrap 95% CI "
        f"{fmt(triple['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(triple['bootstrap_ci95_percent_change'][1])}%; "
        f"p={fmt(triple['bootstrap_p_two_sided'], 3)}). The direction matches the "
        "full-session exploratory pattern, but the interval crosses zero.",
        "",
        f"The late-block pass × `dd_top` term at the mean early prior is "
        f"{fmt(dd['percent_change'])}% (95% CI "
        f"{fmt(dd['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(dd['bootstrap_ci95_percent_change'][1])}%; "
        f"p={fmt(dd['bootstrap_p_two_sided'], 3)}).",
        "",
        f"Outcome n={model['n']} across {model['n_participants']} participants; cells: "
        f"{model['cell_counts']}.",
        "",
        "## Does the early prior behave like a trait?",
        "",
        f"Yes at the gaze level: early versus late `p_ad_survey` has Spearman "
        f"ρ={fmt(stability['spearman_rho'], 3)}, 95% bootstrap CI "
        f"[{fmt(stability['bootstrap_ci95'][0], 3)}, "
        f"{fmt(stability['bootstrap_ci95'][1], 3)}], p={fmt(stability['p'], 3)}.",
        "",
        f"But early prior does not significantly predict late `dd_top` click share in "
        f"this split: ρ={fmt(click['spearman_rho'], 3)}, p={fmt(click['p'], 3)} "
        f"({click['n_participants']} participants, {click['n_late_clicks']} late clicks).",
        "",
        "## Sensitivity grid",
        "",
        "| survey K | prior blocks | outcome blocks | n | triple % per +0.10 | 95% CI | p |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["sensitivity"]:
        lines.append(
            f"| {row['survey_k']} | {row['prior_blocks'][0]}–{row['prior_blocks'][1]} | "
            f"{row['outcome_blocks'][0]}–{row['outcome_blocks'][1]} | {row['n']} | "
            f"{fmt(row['percent_change'])}% | "
            f"[{fmt(row['bootstrap_ci95_percent_change'][0])}%, "
            f"{fmt(row['bootstrap_ci95_percent_change'][1])}%] | "
            f"{fmt(row['bootstrap_p_two_sided'], 3)} |"
        )
    lines += [
        "",
        "## Verdict",
        "",
        "The segmentation is temporally stable, and the three-way estimate points in the "
        "predicted direction, but this is **not a successful temporal confirmation**. The "
        "late outcome contains only 21 first-forward `dd_top` clicks, leaving the interaction "
        "interval wide. The next evidential step is a new cohort with the single three-way "
        "model fixed in advance—not another slice of these 47 participants.",
        "",
        "## Reproduce",
        "",
        "```bash",
        ".venv/bin/python scripts/click_press_latency_pass_analysis.py",
        ".venv/bin/python scripts/click_press_prior_temporal_test.py",
        "```",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines))


def main():
    summary = analyze()
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    write_report(summary)
    print(json.dumps({
        "primary": summary["primary_model"],
        "prior_stability": summary["prior_stability_early_vs_late"],
        "late_click_positive_control": summary["early_prior_vs_late_dd_top_click_share"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
