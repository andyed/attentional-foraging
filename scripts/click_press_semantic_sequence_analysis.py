#!/usr/bin/env python3
"""Temporal semantic-conflict sequences before AdSERP click presses.

The primary sequence window is the fixed 2,000 ms ending at mousedown. Gaze
fixations are assigned by strict X+Y containment in typed_gapfill rectangles,
then consecutive visits to the same display position are collapsed into AOI
runs. Unassigned gaze gaps are ignored, but any intervening assigned AOI breaks
adjacency.

Two primary tests form one Holm-corrected family:

1. Across organic clicks, whether a final better-organic -> clicked-organic
   transition has a different hold-duration association on first-forward versus
   regressive-return clicks. Nested any-AOI and any-organic return indicators
   (and their pass interactions) isolate semantic direction from generic
   switching/returning.
2. Within regressive clicks, whether a strict clicked -> better-organic ->
   clicked chain predicts hold duration beyond generic and organic three-run
   return chains. The strict chain cannot support a pass interaction because it
   does not occur among first-forward clicks under the fixed definition.

A continuous previous-result semantic-advantage interaction on the smaller
organic-return subset is exploratory. Window sensitivities use 1, 3, and 5 s.

Outputs:
  scripts/output/click_press_semantic_sequence/
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SEMANTIC_CSV = ROOT / "scripts/output/click_press_semantic_margin/semantic_click_records.csv"
OUT = ROOT / "scripts/output/click_press_semantic_sequence"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
from click_press_pai_conflict_analysis import fit, holm_adjust, term, z, z_params  # noqa: E402
from click_press_semantic_margin_analysis import content_index, typed_organic_cosines  # noqa: E402
from data_loader import load_fixations, load_typed_gapfill_aois  # noqa: E402

PRIMARY_WINDOW_MS = 2000
SEED = 20260822


def finite(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def load_rows():
    rows = []
    for raw in csv.DictReader(open(SEMANTIC_CSV)):
        rows.append({
            "trial_id": raw["trial_id"],
            "pid": raw["pid"],
            "pass_label": raw["pass_label"],
            "is_regressive": float(raw["pass_label"] == "regressive_return"),
            "press_duration_ms": float(raw["press_duration_ms"]),
            "log_press_duration": float(raw["log_press_duration"]),
            "display_rank0": int(raw["display_rank0"]),
            "log_decision_time": float(raw["log_decision_time"]),
            "target_fix_age_ms": float(raw["target_fix_age_ms"]),
            "prepress_cursor_speed_px_s": float(raw["prepress_cursor_speed_px_s"]),
            "down_timestamp_ms": float(raw["down_timestamp_ms"]),
            "all_competitive_disadvantage": finite(raw.get("all_competitive_disadvantage")),
        })
    return rows


def main_cards(tid):
    cards = [
        card for card in load_typed_gapfill_aois(tid)
        if int(card.get("position", -1)) >= 0
        and all(card.get(key) is not None for key in ("x", "y", "width", "height"))
    ]
    return sorted(cards, key=lambda card: int(card["position"]))


def strict_position(fixation, cards):
    hits = [
        card for card in cards
        if float(card["x"]) <= float(fixation["x"]) <= float(card["x"]) + float(card["width"])
        and float(card["y"]) <= float(fixation["y"]) <= float(card["y"]) + float(card["height"])
    ]
    if not hits:
        return None
    card = min(hits, key=lambda item: float(item["width"]) * float(item["height"]))
    return int(card["position"])


def fixation_runs(tid, cards, down_t, window_ms):
    start = down_t - window_ms
    runs = []
    for fixation in load_fixations(tid):
        t0 = float(fixation["t"])
        if t0 >= down_t:
            break
        duration = float(fixation.get("d", 200) or 200)
        if t0 + duration <= start:
            continue
        pos = strict_position(fixation, cards)
        if pos is None:
            continue
        overlap_start = max(start, t0)
        overlap_end = min(down_t, t0 + duration)
        if runs and runs[-1]["position"] == pos:
            runs[-1]["end_ms"] = max(runs[-1]["end_ms"], overlap_end)
            runs[-1]["fixation_ms"] += max(0.0, overlap_end - overlap_start)
        else:
            runs.append({
                "position": pos,
                "start_ms": overlap_start,
                "end_ms": overlap_end,
                "fixation_ms": max(0.0, overlap_end - overlap_start),
            })
    return runs


def add_sequence_features(rows, window_ms, content):
    output = []
    for row in rows:
        tid = row["trial_id"]
        cards = main_cards(tid)
        card_by_pos = {int(card["position"]): card for card in cards}
        organic = typed_organic_cosines(tid, content, cards)
        clicked = organic.get(row["display_rank0"])
        if clicked is None:
            continue
        runs = fixation_runs(tid, cards, row["down_timestamp_ms"], window_ms)
        final_is_clicked = bool(runs and runs[-1]["position"] == row["display_rank0"])
        any_return = bool(final_is_clicked and len(runs) >= 2)
        previous_pos = runs[-2]["position"] if any_return else None
        previous_card = card_by_pos.get(previous_pos) if previous_pos is not None else None
        previous_semantic = organic.get(previous_pos) if previous_pos is not None else None
        organic_return = bool(any_return and previous_semantic is not None)
        previous_advantage = None
        if organic_return:
            previous_advantage = previous_semantic["q_text_cosine"] - clicked["q_text_cosine"]
        better_return = bool(organic_return and previous_advantage > 0)

        strict_any = bool(
            len(runs) >= 3
            and runs[-1]["position"] == row["display_rank0"]
            and runs[-3]["position"] == row["display_rank0"]
        )
        strict_organic = bool(strict_any and previous_semantic is not None)
        strict_better = bool(strict_organic and previous_advantage > 0)
        enriched = {
            **row,
            "sequence_window_ms": window_ms,
            "n_assigned_aoi_runs": len(runs),
            "final_run_is_clicked": float(final_is_clicked),
            "final_any_return": float(any_return),
            "final_organic_return": float(organic_return),
            "final_better_return": float(better_return),
            "strict_target_other_target": float(strict_any),
            "strict_target_organic_target": float(strict_organic),
            "strict_target_better_target": float(strict_better),
            "previous_display_rank0": previous_pos,
            "previous_etype": previous_card.get("type") if previous_card else None,
            "previous_query_cosine_advantage": previous_advantage,
            "final_target_run_age_ms": (
                row["down_timestamp_ms"] - runs[-1]["start_ms"] if final_is_clicked else None
            ),
        }
        output.append(enriched)
    return output


def base_tail(row, ranks):
    return [
        row["log_decision_time"],
        row["target_fix_age_ms"] / 1000.0,
        math.log1p(row["prepress_cursor_speed_px_s"]),
        *[float(row["display_rank0"] == rank) for rank in ranks[1:]],
    ]


def design_final_return(rows):
    params = z_params(rows, ["all_competitive_disadvantage"])
    ranks = sorted({row["display_rank0"] for row in rows})
    names = [
        "regressive_return",
        "final_any_return", "regressive_x_final_any_return",
        "final_organic_return", "regressive_x_final_organic_return",
        "final_better_return", "regressive_x_final_better_return",
        "all_competitive_disadvantage_z",
        "regressive_x_all_competitive_disadvantage_z",
        "log_decision_time", "target_fix_age_s", "log1p_cursor_speed",
    ] + [f"display_rank_{rank + 1}" for rank in ranks[1:]]

    def vector(row):
        reg = row["is_regressive"]
        semantic = z(row, "all_competitive_disadvantage", params)
        any_return = row["final_any_return"]
        organic_return = row["final_organic_return"]
        better = row["final_better_return"]
        return [
            reg,
            any_return, reg * any_return,
            organic_return, reg * organic_return,
            better, reg * better,
            semantic, reg * semantic,
            *base_tail(row, ranks),
        ]
    return names, vector, params


def design_strict_regressive(rows):
    params = z_params(rows, ["all_competitive_disadvantage"])
    ranks = sorted({row["display_rank0"] for row in rows})
    names = [
        "strict_target_other_target",
        "strict_target_organic_target",
        "strict_target_better_target",
        "all_competitive_disadvantage_z",
        "log_decision_time", "target_fix_age_s", "log1p_cursor_speed",
    ] + [f"display_rank_{rank + 1}" for rank in ranks[1:]]

    def vector(row):
        return [
            row["strict_target_other_target"],
            row["strict_target_organic_target"],
            row["strict_target_better_target"],
            z(row, "all_competitive_disadvantage", params),
            *base_tail(row, ranks),
        ]
    return names, vector, params


def design_continuous_return(rows):
    params = z_params(rows, ["previous_query_cosine_advantage"])
    clicked_ranks = sorted({row["display_rank0"] for row in rows})
    previous_ranks = sorted({row["previous_display_rank0"] for row in rows})
    names = [
        "regressive_return",
        "previous_query_cosine_advantage_z",
        "regressive_x_previous_query_cosine_advantage_z",
        "log_decision_time", "target_fix_age_s", "log1p_cursor_speed",
    ]
    names += [f"display_rank_{rank + 1}" for rank in clicked_ranks[1:]]
    names += [f"previous_display_rank_{rank + 1}" for rank in previous_ranks[1:]]

    def vector(row):
        reg = row["is_regressive"]
        advantage = z(row, "previous_query_cosine_advantage", params)
        return [
            reg, advantage, reg * advantage,
            *base_tail(row, clicked_ranks),
            *[float(row["previous_display_rank0"] == rank) for rank in previous_ranks[1:]],
        ]
    return names, vector, params


def paired_participants(rows, key):
    out = 0
    for pid in {row["pid"] for row in rows}:
        values = {row[key] for row in rows if row["pid"] == pid}
        out += values == {0.0, 1.0}
    return out


def paired_descriptive(rows, key, pass_label):
    deltas = []
    for pid in {row["pid"] for row in rows}:
        groups = {
            value: [
                row["press_duration_ms"] for row in rows
                if row["pid"] == pid and row["pass_label"] == pass_label and row[key] == value
            ]
            for value in (0.0, 1.0)
        }
        if groups[0.0] and groups[1.0]:
            deltas.append(float(np.median(groups[1.0]) - np.median(groups[0.0])))
    return {
        "n_paired_participants": len(deltas),
        "median_within_participant_delta_ms": float(np.median(deltas)) if deltas else None,
        "wilcoxon_p_two_sided": float(stats.wilcoxon(deltas).pvalue) if deltas else None,
        "n_negative": sum(delta < 0 for delta in deltas),
        "n_positive": sum(delta > 0 for delta in deltas),
        "n_zero": sum(delta == 0 for delta in deltas),
    }


def descriptive(rows, key, pass_label=None):
    subset = [row for row in rows if pass_label is None or row["pass_label"] == pass_label]
    return {
        str(int(value)): {
            "n": len(group),
            "median_press_duration_ms": float(np.median([row["press_duration_ms"] for row in group])) if group else None,
            "n_participants": len({row["pid"] for row in group}),
        }
        for value in (0.0, 1.0)
        for group in [[row for row in subset if row[key] == value]]
    }


def analyze_window(base, window_ms, content, seed):
    rows = add_sequence_features(base, window_ms, content)
    complete = [row for row in rows if row["all_competitive_disadvantage"] is not None]
    regressive = [row for row in complete if row["is_regressive"] == 1]
    organic_return = [
        row for row in complete
        if row["final_organic_return"] == 1
        and row["previous_query_cosine_advantage"] is not None
    ]

    final_names = [
        "regressive_return",
        "final_any_return", "regressive_x_final_any_return",
        "final_organic_return", "regressive_x_final_organic_return",
        "final_better_return", "regressive_x_final_better_return",
        "all_competitive_disadvantage_z",
        "regressive_x_all_competitive_disadvantage_z",
    ]
    final_model = fit(
        complete, design_final_return(complete), final_names,
        ("final_better_return", "regressive_x_final_better_return"), seed,
    )
    strict_names = [
        "strict_target_other_target",
        "strict_target_organic_target",
        "strict_target_better_target",
        "all_competitive_disadvantage_z",
    ]
    strict_model = fit(
        regressive, design_strict_regressive(regressive), strict_names,
        None, seed + 1,
    )
    continuous_names = [
        "regressive_return", "previous_query_cosine_advantage_z",
        "regressive_x_previous_query_cosine_advantage_z",
    ]
    continuous_model = fit(
        organic_return, design_continuous_return(organic_return), continuous_names,
        ("previous_query_cosine_advantage_z", "regressive_x_previous_query_cosine_advantage_z"),
        seed + 2,
    )
    return rows, {
        "window_ms": window_ms,
        "n_complete": len(complete),
        "sequence_counts_by_pass": {
            label: {
                key: int(sum(row[key] for row in complete if row["pass_label"] == label))
                for key in (
                    "final_any_return", "final_organic_return", "final_better_return",
                    "strict_target_other_target", "strict_target_organic_target",
                    "strict_target_better_target",
                )
            }
            for label in ("first_forward", "regressive_return")
        },
        "paired_participants": {
            "final_better_return": paired_participants(complete, "final_better_return"),
            "strict_target_better_target_regressive": paired_participants(regressive, "strict_target_better_target"),
        },
        "descriptive_final_better_by_pass": {
            label: descriptive(complete, "final_better_return", label)
            for label in ("first_forward", "regressive_return")
        },
        "descriptive_strict_regressive": descriptive(
            regressive, "strict_target_better_target", "regressive_return"
        ),
        "participant_paired_descriptives": {
            "final_better_first_forward": paired_descriptive(
                complete, "final_better_return", "first_forward"
            ),
            "final_better_regressive": paired_descriptive(
                complete, "final_better_return", "regressive_return"
            ),
            "strict_better_regressive": paired_descriptive(
                complete, "strict_target_better_target", "regressive_return"
            ),
        },
        "final_return_model": final_model,
        "strict_regressive_model": strict_model,
        "continuous_organic_return_model": continuous_model,
    }


def fmt(item):
    lo, hi = item["bootstrap_ci95_percent_change"]
    return f'{item["percent_change"]:+.2f}% [{lo:+.2f}, {hi:+.2f}], p={item["bootstrap_p_two_sided"]:.3f}'


def write_csv(rows):
    keys = sorted({key for row in rows for key in row})
    with open(OUT / "semantic_sequence_click_records.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_report(summary):
    primary = summary["primary"]
    final = primary["final_return_model"]
    strict = primary["strict_regressive_model"]
    continuous = primary["continuous_organic_return_model"]
    final_term = final["terms"]["regressive_x_final_better_return"]
    strict_term = strict["terms"]["strict_target_better_target"]
    counts = primary["sequence_counts_by_pass"]
    paired = primary["participant_paired_descriptives"]
    lines = [
        "# Pre-press semantic return sequences",
        "",
        "**Regime:** `[LAB, AdSERP, typed_gapfill]`  ",
        "**Primary window:** fixed 2,000 ms ending at `mousedown`  ",
        "**Gaze assignment:** strict X+Y `typed_gapfill` rectangles; consecutive same-AOI fixations collapsed  ",
        "**Inference:** participant fixed effects; 5,000 participant-cluster bootstrap resamples",
        "",
        "## Results",
        "",
        f"- Final better-organic → clicked-organic transition × pass: **{fmt(final_term)}** (n={final['n']}).",
        f"- Strict clicked → better-organic → clicked chain within regressive clicks: **{fmt(strict_term)}** (n={strict['n']}).",
        f"- Holm-adjusted primary p-values: transition interaction **{summary['primary_holm_p']['final_return_interaction']:.3f}**, strict regressive chain **{summary['primary_holm_p']['strict_regressive_chain']:.3f}**.",
        f"- Better-return counts: first-forward {counts['first_forward']['final_better_return']}, regressive {counts['regressive_return']['final_better_return']}. Strict-chain counts: first-forward {counts['first_forward']['strict_target_better_target']}, regressive {counts['regressive_return']['strict_target_better_target']}.",
        f"- Participant-paired median deltas for better-return present minus absent: first-forward {paired['final_better_first_forward']['median_within_participant_delta_ms']:+.2f} ms (n={paired['final_better_first_forward']['n_paired_participants']}, Wilcoxon p={paired['final_better_first_forward']['wilcoxon_p_two_sided']:.3f}); regressive {paired['final_better_regressive']['median_within_participant_delta_ms']:+.2f} ms (n={paired['final_better_regressive']['n_paired_participants']}, p={paired['final_better_regressive']['wilcoxon_p_two_sided']:.3f}).",
        f"- Strict-chain participant-paired regressive delta: {paired['strict_better_regressive']['median_within_participant_delta_ms']:+.2f} ms (n={paired['strict_better_regressive']['n_paired_participants']}, Wilcoxon p={paired['strict_better_regressive']['wilcoxon_p_two_sided']:.3f}).",
        f"- Exploratory continuous previous-result advantage × pass, conditional on an organic return: {fmt(continuous['terms']['regressive_x_previous_query_cosine_advantage_z'])} (n={continuous['n']}).",
        "",
        "## Guardrails",
        "",
        "The final-return interaction includes nested any-AOI-return and any-organic-return terms and their pass interactions. Its focal coefficient therefore asks whether semantic-better direction adds anything beyond generic gaze switching and returning. The unweighted all-candidate semantic-disadvantage interaction remains in the model as a control.",
        "",
        "The strict clicked → better → clicked chain occurs only on regressive passes under this definition, so it is tested only within regressive clicks. It is not presented as a pass interaction. Nested generic and organic three-run chain indicators separate semantic direction from the act of leaving and returning.",
        "",
        "Unassigned gaze gaps do not create a run, but every intervening assigned AOI breaks adjacency. Semantic joins use organic `rso[k]` content handles; display positions remain the behavioral ranks.",
        "",
        "## Window sensitivities",
        "",
    ]
    for label, block in summary["sensitivities"].items():
        a = block["final_return_model"]["terms"]["regressive_x_final_better_return"]
        b = block["strict_regressive_model"]["terms"]["strict_target_better_target"]
        lines.append(f"- **{label}:** final-transition interaction {fmt(a)}; strict regressive chain {fmt(b)}.")
    lines += [
        "",
        "## Provenance",
        "",
        "- Input: primary organic same-XPath press pairs and semantic joins from `click_press_semantic_margin_analysis.py`.",
        "- Shared controls: participant fixed effects, categorical clicked display rank, log decision time, target-fixation recency, and log1p pre-press cursor speed.",
        "- Continuous-return sensitivity also controls categorical previous-result display rank.",
    ]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")


def make_plot(summary):
    primary = summary["primary"]
    items = [
        (
            "Better-return × regressive",
            primary["final_return_model"]["terms"]["regressive_x_final_better_return"],
        ),
        (
            "Strict better-return chain\n(regressive only)",
            primary["strict_regressive_model"]["terms"]["strict_target_better_target"],
        ),
        (
            "Previous semantic advantage × regressive\n(exploratory organic returns)",
            primary["continuous_organic_return_model"]["terms"]["regressive_x_previous_query_cosine_advantage_z"],
        ),
    ]
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    for y, (label, item) in enumerate(items):
        point = item["percent_change"]
        lo, hi = item["bootstrap_ci95_percent_change"]
        ax.errorbar(point, y, xerr=[[point - lo], [hi - point]], fmt="o", capsize=4, color="#315a7d")
    ax.axvline(0, color="#555", linewidth=1)
    ax.set_yticks(range(len(items)), [label for label, _ in items])
    ax.set_xlabel("Change in press duration (%)")
    ax.set_title("Pre-press semantic return sequences\n[LAB, AdSERP, typed_gapfill]", fontsize=13)
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "semantic_sequence_effects.png", dpi=180)
    plt.close(fig)


def main():
    if not SEMANTIC_CSV.exists():
        raise SystemExit("Run scripts/click_press_semantic_margin_analysis.py first")
    base = load_rows()
    content = content_index()
    primary_rows, primary = analyze_window(base, PRIMARY_WINDOW_MS, content, SEED)
    sensitivities = {}
    for label, window, seed in (
        ("1,000 ms", 1000, SEED + 100),
        ("3,000 ms", 3000, SEED + 200),
        ("5,000 ms", 5000, SEED + 300),
    ):
        _, result = analyze_window(base, window, content, seed)
        sensitivities[label] = result
    raw_p = [
        primary["final_return_model"]["terms"]["regressive_x_final_better_return"]["bootstrap_p_two_sided"],
        primary["strict_regressive_model"]["terms"]["strict_target_better_target"]["bootstrap_p_two_sided"],
    ]
    adjusted = holm_adjust(raw_p)
    summary = {
        "regime": "LAB, AdSERP, typed_gapfill",
        "rank_type": "typed_gapfill display rank; strict X+Y fixation containment",
        "anchor": "mousedown",
        "base_organic_clicks": len(base),
        "primary": primary,
        "primary_holm_p": {
            "final_return_interaction": adjusted[0],
            "strict_regressive_chain": adjusted[1],
        },
        "sensitivities": sensitivities,
    }
    write_csv(primary_rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(summary)
    make_plot(summary)
    print((OUT / "report.md").read_text())


if __name__ == "__main__":
    main()
