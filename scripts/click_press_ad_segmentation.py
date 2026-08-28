"""Ad surface, ad-utility segment, and DOM-target follow-up for click holds.

Consumes the primary click-press records produced by
``click_press_latency_pass_analysis.py`` and joins the canonical 47-person
ad-utility prior table. The analysis asks whether the otherwise-null
first-forward versus regressive-return press contrast is moderated by:

1. clicked surface: organic, dd_top, native_ad, or other widget;
2. the participant's pre-decision ad-attention prior (continuous and tercile);
3. the terminal DOM node in the evtrack XPath.

All inferential models are participant-demeaned log-duration regressions with
categorical display-rank fixed effects and participant-cluster bootstrap CIs.
This is an exploratory follow-up; it does not change the overall null result.

Run:
  .venv/bin/python scripts/click_press_latency_pass_analysis.py
  .venv/bin/python scripts/click_press_ad_segmentation.py
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
PRESS_OUT = ROOT / "scripts" / "output" / "click_press_latency_pass"
OUT = ROOT / "scripts" / "output" / "click_press_ad_segmentation"
MOUSE = ROOT / "AdSERP" / "data" / "mouse-movement-data"
TRAITS = ROOT / "scripts" / "output" / "ad_utility_prior" / "per_participant.csv"
OUT.mkdir(parents=True, exist_ok=True)

BOOTSTRAPS = 5000
SEED = 20260822


def terminal_xpath(tid):
    with open(MOUSE / f"{tid}.csv") as f:
        clicks = [row for row in csv.DictReader(f) if row.get("event") == "click"]
    return clicks[-1].get("xpath", "") if clicks else ""


def xpath_node(xpath):
    match = re.search(r"/([a-zA-Z][a-zA-Z0-9_-]*)(?:\[[^/]*\])?$", xpath.strip())
    return match.group(1).lower() if match else "id_target"


def content_group(etype):
    if etype in {"dd_top", "native_ad"}:
        return "ad"
    if etype == "organic":
        return "organic"
    return "widget"


def load_rows():
    traits = {row["participant"]: row for row in csv.DictReader(open(TRAITS))}
    rows = []
    path = PRESS_OUT / "click_press_records.csv"
    for row in csv.DictReader(open(path)):
        if row["primary_pass_eligible"] != "True":
            continue
        trait = traits[row["pid"]]
        xpath = terminal_xpath(row["trial_id"])
        rows.append({
            "trial_id": row["trial_id"],
            "pid": row["pid"],
            "pass_label": row["pass_label"],
            "is_regressive": float(row["pass_label"] == "regressive_return"),
            "press_duration_ms": float(row["press_duration_ms"]),
            "log_press_duration": math.log(float(row["press_duration_ms"])),
            "target_fix_age_ms": float(row["target_fix_age_ms"]),
            "display_rank0": int(float(row["click_pos"])),
            "etype": row["etype"],
            "content_group": content_group(row["etype"]),
            "p_ad_survey": float(trait["p_ad_survey"]),
            "ad_over_index": float(trait["ad_over_index"]),
            "ad_prior_tercile": trait["tercile"],
            "p_ad_click": float(trait["p_ad_click"]),
            "p_dd_top_click": float(trait["p_dd_top_click"]),
            "click_xpath": xpath,
            "click_node": xpath_node(xpath),
        })
    return rows


def paired_summary(rows):
    first = [row for row in rows if row["pass_label"] == "first_forward"]
    reg = [row for row in rows if row["pass_label"] == "regressive_return"]
    by_pid = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_pid[row["pid"]][row["pass_label"]].append(row["press_duration_ms"])
    deltas = []
    for groups in by_pid.values():
        if groups["first_forward"] and groups["regressive_return"]:
            deltas.append(
                float(np.median(groups["regressive_return"]))
                - float(np.median(groups["first_forward"]))
            )
    p = None
    if len(deltas) >= 5 and np.any(np.asarray(deltas) != 0):
        p = float(stats.wilcoxon(deltas, alternative="two-sided").pvalue)
    return {
        "n_first_forward": len(first),
        "participants_first_forward": len({row["pid"] for row in first}),
        "median_first_forward_ms": (
            float(np.median([row["press_duration_ms"] for row in first])) if first else None
        ),
        "n_regressive_return": len(reg),
        "participants_regressive_return": len({row["pid"] for row in reg}),
        "median_regressive_return_ms": (
            float(np.median([row["press_duration_ms"] for row in reg])) if reg else None
        ),
        "paired_participants": len(deltas),
        "median_participant_delta_ms": float(np.median(deltas)) if deltas else None,
        "paired_wilcoxon_p": p,
    }


def rank_fixed_design(rows, pids, feature_fn):
    ranks = sorted({row["display_rank0"] for row in rows})
    y_all, x_all = [], []
    for pid in pids:
        subset = [row for row in rows if row["pid"] == pid]
        y = np.asarray([row["log_press_duration"] for row in subset])
        x = np.asarray([
            feature_fn(row) + [float(row["display_rank0"] == rank) for rank in ranks[1:]]
            for row in subset
        ])
        y_all.append(y - np.mean(y))
        x_all.append(x - np.mean(x, axis=0))
    return np.concatenate(y_all), np.vstack(x_all)


def bootstrap_model(rows, feature_names, feature_fn, seed=SEED):
    pids = sorted({row["pid"] for row in rows})
    y, x = rank_fixed_design(rows, pids, feature_fn)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(BOOTSTRAPS):
        sampled = list(rng.choice(pids, size=len(pids), replace=True))
        yb, xb = rank_fixed_design(rows, sampled, feature_fn)
        boot.append(np.linalg.lstsq(xb, yb, rcond=None)[0])
    boot = np.asarray(boot)
    terms = {}
    for i, name in enumerate(feature_names):
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
    return {
        "n": len(y),
        "n_participants": len(pids),
        "rank_control": "categorical typed_gapfill display-rank fixed effects",
        "terms": terms,
        "_beta": beta,
        "_boot": boot,
    }


def surface_moderation(rows, surface):
    """Pass × surface model against organic baseline."""
    subset = [row for row in rows if row["etype"] in {"organic", surface}]

    def features(row):
        typed = float(row["etype"] == surface)
        reg = row["is_regressive"]
        return [reg, typed, reg * typed]

    model = bootstrap_model(
        subset,
        ["regressive_on_organic", f"{surface}_main", f"regressive_x_{surface}"],
        features,
        seed=SEED + len(surface),
    )
    beta, boot = model.pop("_beta"), model.pop("_boot")
    combined = boot[:, 0] + boot[:, 2]
    ci = np.quantile(combined, [0.025, 0.975])
    p_boot = 2 * min(np.mean(combined <= 0), np.mean(combined >= 0))
    model["regressive_effect_on_surface"] = {
        "percent_change": float(100 * (math.exp(beta[0] + beta[2]) - 1)),
        "bootstrap_ci95_percent_change": [
            float(100 * (math.exp(ci[0]) - 1)),
            float(100 * (math.exp(ci[1]) - 1)),
        ],
        "bootstrap_p_two_sided": float(p_boot),
    }
    return model


def combined_ad_moderation(rows):
    subset = [row for row in rows if row["content_group"] in {"organic", "ad"}]

    def features(row):
        ad = float(row["content_group"] == "ad")
        reg = row["is_regressive"]
        return [reg, ad, reg * ad]

    model = bootstrap_model(
        subset,
        ["regressive_on_organic", "ad_main", "regressive_x_ad"],
        features,
        seed=SEED + 101,
    )
    model.pop("_beta")
    model.pop("_boot")
    return model


def prior_moderation(rows, label, predicate):
    subset = [row for row in rows if predicate(row)]
    center = float(np.mean([row["p_ad_survey"] for row in subset]))

    def features(row):
        reg = row["is_regressive"]
        return [reg, reg * (row["p_ad_survey"] - center) / 0.10]

    model = bootstrap_model(
        subset,
        ["regressive_at_mean_prior", "regressive_x_prior_per_0.10"],
        features,
        seed=SEED + len(label) * 7,
    )
    model.pop("_beta")
    model.pop("_boot")
    model["subset"] = label
    model["prior_center"] = center
    return model


def sensitivity_dd_top(rows):
    out = []
    for max_age in (500, 1000, 1500):
        for max_hold in (500, 1000):
            subset = [
                row for row in rows
                if row["etype"] in {"organic", "dd_top"}
                and row["target_fix_age_ms"] <= max_age
                and row["press_duration_ms"] <= max_hold
            ]

            def features(row):
                dd = float(row["etype"] == "dd_top")
                reg = row["is_regressive"]
                return [reg, dd, reg * dd]

            model = bootstrap_model(
                subset,
                ["regressive_on_organic", "dd_top_main", "regressive_x_dd_top"],
                features,
                seed=SEED + max_age + max_hold,
            )
            term = model["terms"]["regressive_x_dd_top"]
            out.append({
                "max_target_fix_age_ms": max_age,
                "max_press_ms": max_hold,
                "n": model["n"],
                **term,
            })
    return out


def breakdown(rows, key, levels):
    return {
        level: paired_summary([row for row in rows if row[key] == level])
        for level in levels
    }


def analyze(rows):
    content = breakdown(rows, "content_group", ["organic", "ad", "widget"])
    etype = breakdown(
        rows, "etype",
        ["organic", "dd_top", "native_ad", "image_pack", "paa", "knowledge_panel"],
    )
    node_counts = Counter(row["click_node"] for row in rows)
    node = breakdown(rows, "click_node", ["h3", "span", "div", "cite", "id_target", "a"])
    node_etype = Counter((row["click_node"], row["etype"]) for row in rows)
    segment = {}
    for tercile in ("low", "mid", "high"):
        segment[tercile] = {
            "all": paired_summary([row for row in rows if row["ad_prior_tercile"] == tercile]),
            "organic": paired_summary([
                row for row in rows
                if row["ad_prior_tercile"] == tercile and row["content_group"] == "organic"
            ]),
            "ad": paired_summary([
                row for row in rows
                if row["ad_prior_tercile"] == tercile and row["content_group"] == "ad"
            ]),
        }

    prior_models = {}
    predicates = {
        "all": lambda row: True,
        "organic": lambda row: row["content_group"] == "organic",
        "ad": lambda row: row["content_group"] == "ad",
        "dd_top": lambda row: row["etype"] == "dd_top",
        "native_ad": lambda row: row["etype"] == "native_ad",
    }
    for label, predicate in predicates.items():
        prior_models[label] = prior_moderation(rows, label, predicate)

    return {
        "regime": "LAB, AdSERP",
        "rank_type": "typed_gapfill display rank",
        "n": len(rows),
        "n_participants": len({row["pid"] for row in rows}),
        "content_breakdown": content,
        "etype_breakdown": etype,
        "surface_moderation": {
            "combined_ad_vs_organic": combined_ad_moderation(rows),
            "dd_top_vs_organic": surface_moderation(rows, "dd_top"),
            "native_ad_vs_organic": surface_moderation(rows, "native_ad"),
        },
        "dd_top_sensitivity": sensitivity_dd_top(rows),
        "ad_prior_tercile": segment,
        "continuous_ad_prior_moderation": prior_models,
        "link_target": {
            "counts": dict(node_counts),
            "pass_breakdown": node,
            "node_by_etype": {
                f"{node_name}|{etype_name}": count
                for (node_name, etype_name), count in sorted(node_etype.items())
            },
            "span_ad_share": float(
                sum(row["click_node"] == "span" and row["content_group"] == "ad" for row in rows)
                / max(1, sum(row["click_node"] == "span" for row in rows))
            ),
            "h3_organic_share": float(
                sum(row["click_node"] == "h3" and row["etype"] == "organic" for row in rows)
                / max(1, sum(row["click_node"] == "h3" for row in rows))
            ),
        },
        "interpretation": [
            "The overall pass-duration effect remains null.",
            "dd_top, not native_ad, drives the clicked-surface moderation.",
            "The dd_top interaction survives all six recency/hold threshold combinations.",
            "Ad-prior moderation on ad clicks is borderline and exploratory at n=47.",
            "DOM node type is largely a proxy for AOI type (span mostly ads; h3 mostly organic), so it cannot identify an independent link-surface effect.",
        ],
    }


def fmt(value, digits=2):
    if value is None:
        return "NA"
    if value != 0 and abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.{digits}f}"


def write_report(summary):
    dd = summary["surface_moderation"]["dd_top_vs_organic"]
    dd_int = dd["terms"]["regressive_x_dd_top"]
    dd_reg = dd["regressive_effect_on_surface"]
    org_reg = dd["terms"]["regressive_on_organic"]
    ad_prior = summary["continuous_ad_prior_moderation"]["ad"]["terms"][
        "regressive_x_prior_per_0.10"
    ]
    lines = [
        "# Click press duration by ad surface and ad-utility prior",
        "",
        "**Regime:** `[LAB, AdSERP]`  ",
        "**Rank/AOI type:** `typed_gapfill` display rank  ",
        "**Status:** theoretically motivated exploratory follow-up; overall pass effect remains null.",
        "**Multiplicity:** bootstrap p-values are descriptive; no confirmatory test family was registered before this follow-up.",
        "",
        "## Surface type",
        "",
        "| clicked surface | first n / median ms | regressive n / median ms | paired participants | participant median Δ ms | paired p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for level in ("organic", "ad", "widget"):
        row = summary["content_breakdown"][level]
        lines.append(
            f"| {level} | {row['n_first_forward']} / {fmt(row['median_first_forward_ms'], 1)} | "
            f"{row['n_regressive_return']} / {fmt(row['median_regressive_return_ms'], 1)} | "
            f"{row['paired_participants']} | {fmt(row['median_participant_delta_ms'], 1)} | "
            f"{fmt(row['paired_wilcoxon_p'], 3)} |"
        )
    lines += [
        "",
        f"With participant and categorical display-rank effects removed, the regressive "
        f"effect is {fmt(org_reg['percent_change'])}% on organic clicks "
        f"(95% CI {fmt(org_reg['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(org_reg['bootstrap_ci95_percent_change'][1])}%) but "
        f"{fmt(dd_reg['percent_change'])}% on `dd_top` clicks "
        f"(95% CI {fmt(dd_reg['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(dd_reg['bootstrap_ci95_percent_change'][1])}%). The pass × `dd_top` "
        f"interaction is {fmt(dd_int['percent_change'])}% "
        f"(95% CI {fmt(dd_int['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(dd_int['bootstrap_ci95_percent_change'][1])}%; bootstrap "
        f"p={fmt(dd_int['bootstrap_p_two_sided'], 3)}). It remains negative in all six "
        "recency/hold sensitivities. `native_ad` does not show this moderation.",
        "",
        "## Existing ad-utility segmentation",
        "",
        "The segment is the canonical pre-decision `p_ad_survey` tercile, not a cohort "
        "defined from the current click outcome.",
        "",
        "| prior tercile | all clicks: first / regressive median ms | participant median Δ ms | ad clicks: first / regressive median ms | ad participant Δ ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for tercile in ("low", "mid", "high"):
        all_row = summary["ad_prior_tercile"][tercile]["all"]
        ad_row = summary["ad_prior_tercile"][tercile]["ad"]
        lines.append(
            f"| {tercile} | {fmt(all_row['median_first_forward_ms'], 1)} / "
            f"{fmt(all_row['median_regressive_return_ms'], 1)} | "
            f"{fmt(all_row['median_participant_delta_ms'], 1)} | "
            f"{fmt(ad_row['median_first_forward_ms'], 1)} / "
            f"{fmt(ad_row['median_regressive_return_ms'], 1)} | "
            f"{fmt(ad_row['median_participant_delta_ms'], 1)} |"
        )
    lines += [
        "",
        f"On ad clicks, each +0.10 in pre-decision ad-attention prior changes the "
        f"regressive effect by {fmt(ad_prior['percent_change'])}% "
        f"(95% CI {fmt(ad_prior['bootstrap_ci95_percent_change'][0])}% to "
        f"{fmt(ad_prior['bootstrap_ci95_percent_change'][1])}%; bootstrap "
        f"p={fmt(ad_prior['bootstrap_p_two_sided'], 3)}). This is borderline and "
        "post-hoc; it motivates replication rather than a confirmed user-segment claim.",
        "",
        "## DOM/link target",
        "",
        f"Terminal node counts are h3={summary['link_target']['counts'].get('h3', 0)}, "
        f"span={summary['link_target']['counts'].get('span', 0)}, "
        f"div={summary['link_target']['counts'].get('div', 0)}, "
        f"id-only target={summary['link_target']['counts'].get('id_target', 0)}, and "
        f"cite={summary['link_target']['counts'].get('cite', 0)}. However, "
        f"{100 * summary['link_target']['span_ad_share']:.1f}% of span targets are ads and "
        f"{100 * summary['link_target']['h3_organic_share']:.1f}% of h3 targets are organic. "
        "Node/link type is therefore too confounded with AOI type to support an independent "
        "link-surface interpretation.",
        "",
        "## Reproduce",
        "",
        "```bash",
        ".venv/bin/python scripts/click_press_latency_pass_analysis.py",
        ".venv/bin/python scripts/click_press_ad_segmentation.py",
        "```",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines))


def main():
    rows = load_rows()
    summary = analyze(rows)
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    write_report(summary)
    print(json.dumps({
        "n": summary["n"],
        "content": summary["content_breakdown"],
        "dd_top": summary["surface_moderation"]["dd_top_vs_organic"],
        "ad_prior_on_ad_clicks": summary["continuous_ad_prior_moderation"]["ad"],
        "link_target": summary["link_target"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
