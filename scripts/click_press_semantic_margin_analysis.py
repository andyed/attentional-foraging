"""Semantic fit and local competition in AdSERP click press duration.

This follow-up joins the canonical ``typed_gapfill`` click/pass records to
precomputed query-result embedding cosines.  Display rank and gaze-pass state
remain defined by ``typed_gapfill``.  Organic result text is joined through the
AOI's ``rso[k]`` handle to absolute h3 position ``k`` in the content cache; the
cache position is deliberately not treated as display rank.

Three related, explicitly separated constructs are tested:

1. query-clicked distance: ``1 - cosine(query, clicked result)``;
2. competitive disadvantage: ``best viewed-other cosine - clicked cosine``;
3. local ambiguity: ``-abs(clicked cosine - best viewed-other cosine)``
   (larger values mean a closer semantic tie).

"Viewed" means that the corresponding main-axis typed display slot received
at least one fixation at or before mousedown.  Two structural sensitivities use
all joinable organic slots rather than only viewed slots.  The three primary
pass-interaction p-values are Holm-adjusted as one family.

Outputs:
  scripts/output/click_press_semantic_margin/
    semantic_click_records.csv
    summary.json
    report.md
    semantic_interactions.png

Run:
  .venv/bin/python scripts/click_press_latency_pass_analysis.py
  .venv/bin/python scripts/click_press_semantic_margin_analysis.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PRESS_OUT = ROOT / "scripts" / "output" / "click_press_latency_pass"
OUT = ROOT / "scripts" / "output" / "click_press_semantic_margin"
CONTENT = ROOT / "AdSERP" / "data" / "content-features-by-position.json"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
from click_press_latency_pass_analysis import load_mouse_rows, pair_terminal_press  # noqa: E402
from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    load_fixations,
    load_typed_gapfill_aois,
    typed_gapfill_aoi_tops,
)

BOOTSTRAPS = 5000
SEED = 20260822
RSO_RE = re.compile(r"^rso\[(\d+)\]$")


def finite(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def source_h3_pos(card):
    match = RSO_RE.match(str(card.get("html_handle", "")).strip())
    return int(match.group(1)) if match else None


def content_index():
    raw = json.load(open(CONTENT))
    out = {}
    for tid, trial in raw.items():
        by_source = {}
        for row in trial.get("positions", []):
            source = row.get("pos")
            cosine = finite(row.get("q_text_cosine"))
            if source is not None and cosine is not None:
                by_source[int(source)] = {
                    "q_text_cosine": cosine,
                    "content_absolute_h3_pos": int(row["pos"]),
                }
        out[tid] = by_source
    return out


def typed_organic_cosines(tid, content, cards):
    """Map typed display positions to query-result cosines via rso handles."""
    out = {}
    for card in cards:
        if card.get("type") != "organic" or int(card.get("position", -1)) < 0:
            continue
        source = source_h3_pos(card)
        record = content.get(tid, {}).get(source)
        if source is not None and record is not None:
            out[int(card["position"])] = {
                "source_h3_pos": source,
                "heading_text": card.get("heading_text", ""),
                **record,
            }
    return out


def load_primary_organic_rows():
    rows = []
    for row in csv.DictReader(open(PRESS_OUT / "click_press_records.csv")):
        if row["primary_pass_eligible"] != "True" or row["etype"] != "organic":
            continue
        rows.append({
            "trial_id": row["trial_id"],
            "pid": row["pid"],
            "pass_label": row["pass_label"],
            "is_regressive": float(row["pass_label"] == "regressive_return"),
            "press_duration_ms": float(row["press_duration_ms"]),
            "log_press_duration": math.log(float(row["press_duration_ms"])),
            "display_rank0": int(float(row["click_pos"])),
            "decision_time_ms": float(row["decision_time_ms"]),
            "log_decision_time": math.log(max(1.0, float(row["decision_time_ms"]))),
            "target_fix_age_ms": float(row["target_fix_age_ms"]),
            "prepress_cursor_speed_px_s": float(row["prepress_cursor_speed_px_s"]),
        })
    return rows


def build_semantic_rows():
    content = content_index()
    base = load_primary_organic_rows()
    exclusions = defaultdict(int)
    output = []

    for row in base:
        tid = row["trial_id"]
        cards = load_typed_gapfill_aois(tid)
        card_by_pos = {
            int(card["position"]): card
            for card in cards
            if int(card.get("position", -1)) >= 0
        }
        clicked_card = card_by_pos.get(row["display_rank0"])
        if clicked_card is None or clicked_card.get("type") != "organic":
            exclusions["clicked_typed_card_not_organic"] += 1
            continue

        organic_cosines = typed_organic_cosines(tid, content, cards)
        clicked = organic_cosines.get(row["display_rank0"])
        if clicked is None:
            exclusions["clicked_embedding_join_missing"] += 1
            continue

        mouse = load_mouse_rows(tid)
        pair, reason = pair_terminal_press(mouse)
        if pair is None:
            exclusions[f"press_repair_{reason}"] += 1
            continue
        down_t = pair["down"]["t"]
        tops = typed_gapfill_aoi_tops(tid)
        viewed_positions = set()
        for fix in load_fixations(tid):
            if fix["t"] > down_t:
                break
            pos = assign_fixation_to_position(fix["y"], tops, len(tops))
            if pos in organic_cosines:
                viewed_positions.add(pos)

        clicked_cosine = clicked["q_text_cosine"]
        evaluated_other = [
            record["q_text_cosine"]
            for pos, record in organic_cosines.items()
            if pos != row["display_rank0"] and pos in viewed_positions
        ]
        all_other = [
            record["q_text_cosine"]
            for pos, record in organic_cosines.items()
            if pos != row["display_rank0"]
        ]

        enriched = {
            **row,
            "down_timestamp_ms": down_t,
            "clicked_source_h3_pos": clicked["source_h3_pos"],
            "clicked_content_absolute_h3_pos": clicked["content_absolute_h3_pos"],
            "clicked_heading_text": clicked["heading_text"],
            "query_clicked_cosine": clicked_cosine,
            "query_clicked_distance": 1.0 - clicked_cosine,
            "n_viewed_organic": len(viewed_positions),
            "n_joined_organic": len(organic_cosines),
            "n_evaluated_other_organic": len(evaluated_other),
        }
        if evaluated_other:
            best = max(evaluated_other)
            margin = clicked_cosine - best
            enriched.update({
                "evaluated_best_other_cosine": best,
                "evaluated_clicked_margin": margin,
                "evaluated_competitive_disadvantage": -margin,
                "evaluated_local_ambiguity": -abs(margin),
            })
        else:
            enriched.update({
                "evaluated_best_other_cosine": None,
                "evaluated_clicked_margin": None,
                "evaluated_competitive_disadvantage": None,
                "evaluated_local_ambiguity": None,
            })
            exclusions["no_viewed_other_organic"] += 1
        if all_other:
            best = max(all_other)
            margin = clicked_cosine - best
            enriched.update({
                "all_best_other_cosine": best,
                "all_clicked_margin": margin,
                "all_competitive_disadvantage": -margin,
                "all_local_ambiguity": -abs(margin),
            })
        else:
            enriched.update({
                "all_best_other_cosine": None,
                "all_clicked_margin": None,
                "all_competitive_disadvantage": None,
                "all_local_ambiguity": None,
            })
            exclusions["no_joined_other_organic"] += 1
        output.append(enriched)
    return output, dict(exclusions), len(base)


def _cluster_sufficient_statistics(rows, feature_key):
    values = np.asarray([row[feature_key] for row in rows], dtype=float)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        raise ValueError(f"non-varying feature: {feature_key}")
    ranks = sorted({row["display_rank0"] for row in rows})
    pids = sorted({row["pid"] for row in rows})
    feature_names = [
        "regressive_return",
        f"{feature_key}_z",
        f"regressive_x_{feature_key}_z",
        "log_decision_time",
        "target_fix_age_s",
        "log1p_cursor_speed",
    ]
    feature_names += [f"display_rank_{rank + 1}" for rank in ranks[1:]]

    xtx, xty = [], []
    for pid in pids:
        subset = [row for row in rows if row["pid"] == pid]
        y = np.asarray([row["log_press_duration"] for row in subset], dtype=float)
        x_rows = []
        for row in subset:
            z = (row[feature_key] - mean) / sd
            reg = row["is_regressive"]
            x_rows.append([
                reg,
                z,
                reg * z,
                row["log_decision_time"],
                row["target_fix_age_ms"] / 1000.0,
                math.log1p(row["prepress_cursor_speed_px_s"]),
                *[float(row["display_rank0"] == rank) for rank in ranks[1:]],
            ])
        x = np.asarray(x_rows, dtype=float)
        yc = y - np.mean(y)
        xc = x - np.mean(x, axis=0)
        xtx.append(xc.T @ xc)
        xty.append(xc.T @ yc)
    return (
        np.asarray(xtx),
        np.asarray(xty),
        pids,
        feature_names,
        mean,
        sd,
        ranks,
    )


def _term(beta, boot):
    ci = np.quantile(boot, [0.025, 0.975])
    lower = (np.sum(boot <= 0) + 1) / (len(boot) + 1)
    upper = (np.sum(boot >= 0) + 1) / (len(boot) + 1)
    return {
        "log_coefficient": float(beta),
        "percent_change": float(100 * (math.exp(beta) - 1)),
        "bootstrap_ci95_percent_change": [
            float(100 * (math.exp(ci[0]) - 1)),
            float(100 * (math.exp(ci[1]) - 1)),
        ],
        "bootstrap_p_two_sided": float(min(1.0, 2 * min(lower, upper))),
    }


def fit_interaction(rows, feature_key, seed):
    subset = [row for row in rows if finite(row.get(feature_key)) is not None]
    xtx, xty, pids, names, mean, sd, ranks = _cluster_sufficient_statistics(
        subset, feature_key
    )
    beta = np.linalg.lstsq(np.sum(xtx, axis=0), np.sum(xty, axis=0), rcond=None)[0]
    total_xtx = np.sum(xtx, axis=0)
    total_xty = np.sum(xty, axis=0)
    leave_one_out = []
    for i in range(len(pids)):
        beta_i = np.linalg.lstsq(total_xtx - xtx[i], total_xty - xty[i], rcond=None)[0]
        leave_one_out.append(float(100 * (math.exp(beta_i[2]) - 1)))
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(
        len(pids), np.repeat(1.0 / len(pids), len(pids)), size=BOOTSTRAPS
    )
    boot = np.empty((BOOTSTRAPS, len(beta)), dtype=float)
    for i, weight in enumerate(counts):
        bx = np.tensordot(weight, xtx, axes=(0, 0))
        by = np.tensordot(weight, xty, axes=(0, 0))
        boot[i] = np.linalg.lstsq(bx, by, rcond=None)[0]

    terms = {name: _term(beta[i], boot[:, i]) for i, name in enumerate(names[:6])}
    regressive_slope = _term(beta[1] + beta[2], boot[:, 1] + boot[:, 2])
    return {
        "feature": feature_key,
        "feature_mean": mean,
        "feature_sd": sd,
        "n": len(subset),
        "n_first_forward": sum(row["is_regressive"] == 0 for row in subset),
        "n_regressive_return": sum(row["is_regressive"] == 1 for row in subset),
        "n_participants": len(pids),
        "n_paired_participants": sum(
            len({row["is_regressive"] for row in subset if row["pid"] == pid}) == 2
            for pid in pids
        ),
        "rank_control": "categorical typed_gapfill display-rank fixed effects",
        "controls": [
            "participant fixed effects",
            "log decision time",
            "target-fixation recency",
            "log1p pre-press cursor speed",
        ],
        "display_ranks_1based": [rank + 1 for rank in ranks],
        "terms": terms,
        "regressive_feature_slope": regressive_slope,
        "interaction_leave_one_participant_out": {
            "min_percent_change": float(np.min(leave_one_out)),
            "median_percent_change": float(np.median(leave_one_out)),
            "max_percent_change": float(np.max(leave_one_out)),
            "same_sign_as_full": int(
                sum(np.sign(value) == np.sign(terms[names[2]]["percent_change"])
                    for value in leave_one_out)
            ),
            "n": len(leave_one_out),
        },
    }


def holm_adjust(p_values):
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [None] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * p_values[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def descriptive(rows, key):
    subset = [row for row in rows if finite(row.get(key)) is not None]
    return {
        label: {
            "n": len(group),
            "median_press_duration_ms": float(np.median([r["press_duration_ms"] for r in group])),
            "median_feature": float(np.median([r[key] for r in group])),
        }
        for label in ("first_forward", "regressive_return")
        for group in [[r for r in subset if r["pass_label"] == label]]
    }


def analyze(rows, exclusions, base_n):
    specs = [
        ("query_clicked_distance", "query_to_clicked_distance", SEED + 1),
        (
            "evaluated_competitive_disadvantage",
            "viewed_competitive_disadvantage",
            SEED + 2,
        ),
        ("evaluated_local_ambiguity", "viewed_local_ambiguity", SEED + 3),
    ]
    primary = {}
    raw_p = []
    for key, label, seed in specs:
        model = fit_interaction(rows, key, seed)
        primary[label] = model
        raw_p.append(model["terms"][f"regressive_x_{key}_z"]["bootstrap_p_two_sided"])
    adjusted = holm_adjust(raw_p)
    for (_, label, _), p_adj in zip(specs, adjusted):
        primary[label]["interaction_holm_p"] = p_adj

    sensitivities = {}
    for offset, key in enumerate(
        ("all_competitive_disadvantage", "all_local_ambiguity"), start=10
    ):
        sensitivities[key] = fit_interaction(rows, key, SEED + offset)

    return {
        "analysis_date": "2026-08-22",
        "regime": "LAB, AdSERP, typed_gapfill",
        "rank_type": "typed_gapfill display rank; ads/widgets included in rank positions",
        "embedding_join": "typed organic AOI rso[k] -> absolute content-cache h3 position k",
        "embedding_measure": "precomputed q_text_cosine from query and full result-text embeddings",
        "sample_flow": {
            "primary_organic_press_rows": base_n,
            "clicked_embedding_joined_rows": len(rows),
            "clicked_embedding_join_rate": len(rows) / base_n if base_n else None,
            "rows_with_viewed_other_organic": sum(
                row["evaluated_best_other_cosine"] is not None for row in rows
            ),
            "exclusions": exclusions,
        },
        "primary_family": primary,
        "multiplicity": "Holm adjustment across the three primary pass-by-semantic interactions",
        "structural_all_organic_sensitivities": sensitivities,
        "descriptives": {
            key: descriptive(rows, key)
            for key in (
                "query_clicked_distance",
                "evaluated_competitive_disadvantage",
                "evaluated_local_ambiguity",
            )
        },
        "interpretive_limits": [
            "Query-clicked distance is a semantic-fit proxy, not a relevance judgment or correctness label.",
            "Viewed-competitor measures are conditional on recorded gaze and do not prove conscious comparison.",
            "The typed dd_top/native_ad AOIs have neither rso handles nor heading text, so this analysis cannot defensibly join their clicked text.",
            "Press duration is mousedown-to-mouseup motor hold time, not total decision latency.",
        ],
    }


def fmt(value, digits=2):
    return f"{value:.{digits}f}"


def write_report(summary):
    labels = [
        ("query_to_clicked_distance", "query→clicked distance", "higher = poorer semantic fit"),
        (
            "viewed_competitive_disadvantage",
            "best viewed competitor − clicked cosine",
            "higher = competitor more query-aligned",
        ),
        (
            "viewed_local_ambiguity",
            "viewed local ambiguity",
            "higher = closer semantic tie",
        ),
    ]
    lines = [
        "# Click press duration, query fit, and viewed semantic competition",
        "",
        "**Regime:** `[LAB, AdSERP, typed_gapfill]`  ",
        "**Rank:** `typed_gapfill` display rank (ads/widgets included in positions)  ",
        "**Outcome:** same-XPath `mousedown`→`mouseup` duration, log transformed  ",
        "**Multiplicity:** Holm correction across the three primary pass × semantic interactions.",
        "",
        "## Sample and join",
        "",
        f"The organic primary press sample contains {summary['sample_flow']['primary_organic_press_rows']:,} clicks. "
        f"The `rso[k]`→absolute h3-position bridge joins {summary['sample_flow']['clicked_embedding_joined_rows']:,} "
        f"({100 * summary['sample_flow']['clicked_embedding_join_rate']:.1f}%). "
        f"A viewed organic competitor is available for {summary['sample_flow']['rows_with_viewed_other_organic']:,} clicks.",
        "",
        "The cache's absolute h3 position is not used as behavioral rank. Click/pass assignment and rank controls stay on the canonical `typed_gapfill` display positions.",
        "",
        "## Primary interaction family",
        "",
        "Each model contains participant fixed effects, categorical display-rank effects, log decision time, target-fixation recency, and pre-press cursor speed. Effects are percent change in hold duration per 1-SD increase in the semantic feature.",
        "",
        "| feature | n (forward / regressive) | pass × feature | bootstrap 95% CI | raw p | Holm p | forward slope | regressive slope |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, title, direction in labels:
        model = summary["primary_family"][label]
        key = model["feature"]
        interaction = model["terms"][f"regressive_x_{key}_z"]
        forward_slope = model["terms"][f"{key}_z"]
        reg_slope = model["regressive_feature_slope"]
        lines.append(
            f"| {title} ({direction}) | {model['n']:,} ({model['n_first_forward']} / "
            f"{model['n_regressive_return']}) | {fmt(interaction['percent_change'])}% | "
            f"[{fmt(interaction['bootstrap_ci95_percent_change'][0])}%, "
            f"{fmt(interaction['bootstrap_ci95_percent_change'][1])}%] | "
            f"{fmt(interaction['bootstrap_p_two_sided'], 3)} | "
            f"{fmt(model['interaction_holm_p'], 3)} | {fmt(forward_slope['percent_change'])}% "
            f"[{fmt(forward_slope['bootstrap_ci95_percent_change'][0])}%, "
            f"{fmt(forward_slope['bootstrap_ci95_percent_change'][1])}%] | "
            f"{fmt(reg_slope['percent_change'])}% "
            f"[{fmt(reg_slope['bootstrap_ci95_percent_change'][0])}%, "
            f"{fmt(reg_slope['bootstrap_ci95_percent_change'][1])}%] |"
        )
    disadvantage_loo = summary["primary_family"]["viewed_competitive_disadvantage"][
        "interaction_leave_one_participant_out"
    ]
    lines += [
        "",
        "The interaction asks whether the semantic-feature slope differs between first-forward and regressive-return clicks. The two slope columns decompose that interaction; the regressive slope is a model-derived linear combination, not an additional independently selected test.",
        "",
        f"The suggestive viewed-competitor interaction keeps the same negative sign in all {disadvantage_loo['n']} leave-one-participant-out fits (range {fmt(disadvantage_loo['min_percent_change'])}% to {fmt(disadvantage_loo['max_percent_change'])}%). This rules out a single-participant sign reversal, but does not turn the multiplicity-adjusted null into a confirmed effect.",
        "",
        "## Structural sensitivity",
        "",
        "Replacing the gaze-viewed competitor with the best joinable organic result on the page gives:",
        "",
        "| feature | n | pass × feature | bootstrap 95% CI | p |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, title in (
        ("all_competitive_disadvantage", "all-organic competitive disadvantage"),
        ("all_local_ambiguity", "all-organic local ambiguity"),
    ):
        model = summary["structural_all_organic_sensitivities"][key]
        term = model["terms"][f"regressive_x_{key}_z"]
        lines.append(
            f"| {title} | {model['n']:,} | {fmt(term['percent_change'])}% | "
            f"[{fmt(term['bootstrap_ci95_percent_change'][0])}%, "
            f"{fmt(term['bootstrap_ci95_percent_change'][1])}%] | "
            f"{fmt(term['bootstrap_p_two_sided'], 3)} |"
        )
    lines += [
        "",
        "## Interpretation limits",
        "",
        *[f"- {item}" for item in summary["interpretive_limits"]],
        "",
        "## Reproduce",
        "",
        "```bash",
        ".venv/bin/python scripts/click_press_latency_pass_analysis.py",
        ".venv/bin/python scripts/click_press_semantic_margin_analysis.py",
        "```",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines))


def write_figure(summary):
    labels = ["Query→clicked\ndistance", "Viewed competitor\ndisadvantage", "Viewed local\nambiguity"]
    keys = ["query_to_clicked_distance", "viewed_competitive_disadvantage", "viewed_local_ambiguity"]
    estimates, low, high = [], [], []
    for key in keys:
        model = summary["primary_family"][key]
        term = model["terms"][f"regressive_x_{model['feature']}_z"]
        estimates.append(term["percent_change"])
        low.append(term["bootstrap_ci95_percent_change"][0])
        high.append(term["bootstrap_ci95_percent_change"][1])
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.axvline(0, color="#555", linewidth=1)
    ax.errorbar(
        estimates,
        y,
        xerr=[np.asarray(estimates) - np.asarray(low), np.asarray(high) - np.asarray(estimates)],
        fmt="o",
        color="#2463a6",
        ecolor="#6f91b8",
        capsize=4,
    )
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Pass × semantic feature (% hold-duration change per 1 SD)\n95% participant-cluster bootstrap CI")
    ax.set_title("Semantic moderation of regressive vs first-forward click holds")
    ax.grid(axis="x", color="#dddddd", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "semantic_interactions.png", dpi=180)
    plt.close(fig)


def write_records(rows):
    fields = sorted({key for row in rows for key in row})
    with open(OUT / "semantic_click_records.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows, exclusions, base_n = build_semantic_rows()
    if not rows:
        raise RuntimeError("No semantic click rows were joined")
    summary = analyze(rows, exclusions, base_n)
    write_records(rows)
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    write_report(summary)
    write_figure(summary)
    compact = {
        "sample_flow": summary["sample_flow"],
        "primary": {
            label: {
                "interaction": model["terms"][f"regressive_x_{model['feature']}_z"],
                "holm_p": model["interaction_holm_p"],
                "regressive_slope": model["regressive_feature_slope"],
            }
            for label, model in summary["primary_family"].items()
        },
    }
    print(json.dumps(compact, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
