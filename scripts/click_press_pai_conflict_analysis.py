#!/usr/bin/env python3
"""PAI-weighted competition before mousedown in AdSERP click holds.

This follow-up keeps PAI strictly peripheral and keeps conventional in-AOI
dwell as a separate covariate.  It uses fixation/AOI overlap inside fixed
pre-mousedown windows, avoiding the unequal accumulation-duration problem in
variable pre-entry windows.

Primary tests (1,000 ms exact PAI):

1. Organic semantic conflict: sum over nonclicked organic candidates of
   peripheral-PAI share * max(0, query cosine candidate - query cosine click).
   The pass interaction is adjusted for the unweighted best-candidate semantic
   disadvantage, clicked PAI share, and clicked binary-dwell share.
2. Geometry-only competition: max nonclicked peripheral-PAI share minus clicked
   peripheral-PAI share, across every typed_gapfill surface.  Surface and
   pass-by-surface terms distinguish organic, dd_top, native_ad, and widgets.

Sensitivities use a 2,000 ms exact-PAI window and the NB35 linear PAI form in a
1,000 ms window. Participant fixed effects and participant-cluster bootstrap
inference mirror the click-press semantic analysis.

Prerequisites:
  .venv/bin/python scripts/click_press_latency_pass_analysis.py
  .venv/bin/python scripts/click_press_semantic_margin_analysis.py

Outputs:
  scripts/output/click_press_pai_conflict/
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PRESS_CSV = ROOT / "scripts/output/click_press_latency_pass/click_press_records.csv"
SEMANTIC_CSV = ROOT / "scripts/output/click_press_semantic_margin/semantic_click_records.csv"
OUT = ROOT / "scripts/output/click_press_pai_conflict"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
from click_press_latency_pass_analysis import load_mouse_rows, pair_terminal_press  # noqa: E402
from click_press_semantic_margin_analysis import (  # noqa: E402
    content_index,
    typed_organic_cosines,
)
from data_loader import load_fixations, load_typed_gapfill_aois  # noqa: E402

BOOTSTRAPS = 5000
SEED = 20260822
PHI = (1 + np.sqrt(5)) / 2 - 1
P_LAMBDA = PHI ** 3
PRIMARY_WINDOW_MS = 1000


def finite(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def main_cards(tid):
    cards = [
        card for card in load_typed_gapfill_aois(tid)
        if int(card.get("position", -1)) >= 0
        and all(finite(card.get(key)) is not None for key in ("x", "y", "width", "height"))
    ]
    return sorted(cards, key=lambda card: int(card["position"]))


def pai_window(tid, cards, down_t, window_ms, form):
    """Return strictly peripheral PAI and strict in-rectangle dwell per AOI."""
    fixations = load_fixations(tid)
    if not fixations or not cards:
        return None

    x0 = np.asarray([float(card["x"]) for card in cards])
    y0 = np.asarray([float(card["y"]) for card in cards])
    x1 = x0 + np.asarray([float(card["width"]) for card in cards])
    y1 = y0 + np.asarray([float(card["height"]) for card in cards])
    area = np.maximum((x1 - x0) * (y1 - y0), 1.0)
    area_weight = (area.max() / area) ** P_LAMBDA
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    fx, fy, overlap = [], [], []
    start = float(down_t - window_ms)
    stop = float(down_t)
    for fix in fixations:
        t0 = float(fix["t"])
        duration = float(fix.get("d", 200) or 200)
        d = max(0.0, min(t0 + duration, stop) - max(t0, start))
        if d > 0:
            fx.append(float(fix["x"]))
            fy.append(float(fix["y"]))
            overlap.append(d)
    if not overlap:
        return None

    fx = np.asarray(fx)[:, None]
    fy = np.asarray(fy)[:, None]
    duration = np.asarray(overlap)[:, None]
    dx = np.maximum.reduce([x0[None, :] - fx, np.zeros((len(fx), len(cards))), fx - x1[None, :]])
    dy = np.maximum.reduce([y0[None, :] - fy, np.zeros((len(fy), len(cards))), fy - y1[None, :]])
    ogd = np.hypot(dx, dy)
    cgd = np.hypot(fx - cx[None, :], fy - cy[None, :])
    if form == "exact":
        alpha = np.clip(
            1.0 - np.sqrt(ogd / np.maximum(cgd, 1.0)) * area_weight[None, :],
            0.0,
            1.0,
        )
    elif form == "nb35":
        alpha = np.clip(1.0 - ogd / np.maximum(cgd, 1.0), 0.0, 1.0)
    else:
        raise ValueError(form)
    outside = ogd > 0.0
    peripheral = (duration * np.where(outside, alpha, 0.0)).sum(axis=0)
    binary = (duration * (~outside)).sum(axis=0)
    return {
        "peripheral_ms": peripheral,
        "binary_dwell_ms": binary,
        "covered_fixation_ms": float(np.asarray(overlap).sum()),
    }


def load_base_rows():
    rows = []
    for raw in csv.DictReader(open(PRESS_CSV)):
        if raw["primary_pass_eligible"] != "True":
            continue
        mouse = load_mouse_rows(raw["trial_id"])
        pair, reason = pair_terminal_press(mouse)
        if pair is None:
            continue
        etype = raw["etype"]
        surface = etype if etype in {"organic", "dd_top", "native_ad"} else "widget"
        rows.append({
            "trial_id": raw["trial_id"],
            "pid": raw["pid"],
            "pass_label": raw["pass_label"],
            "is_regressive": float(raw["pass_label"] == "regressive_return"),
            "press_duration_ms": float(raw["press_duration_ms"]),
            "log_press_duration": math.log(float(raw["press_duration_ms"])),
            "display_rank0": int(float(raw["click_pos"])),
            "etype": etype,
            "surface_group": surface,
            "log_decision_time": math.log(max(1.0, float(raw["decision_time_ms"]))),
            "target_fix_age_ms": float(raw["target_fix_age_ms"]),
            "prepress_cursor_speed_px_s": float(raw["prepress_cursor_speed_px_s"]),
            "down_timestamp_ms": float(pair["down"]["t"]),
        })
    return rows


def add_pai_features(rows, window_ms, form, content):
    out = []
    exclusions = Counter()
    for row in rows:
        tid = row["trial_id"]
        cards = main_cards(tid)
        by_pos = {int(card["position"]): i for i, card in enumerate(cards)}
        clicked_i = by_pos.get(row["display_rank0"])
        if clicked_i is None:
            exclusions["clicked_position_not_in_geometry"] += 1
            continue
        exposure = pai_window(tid, cards, row["down_timestamp_ms"], window_ms, form)
        if exposure is None:
            exclusions["no_overlapping_fixation_in_window"] += 1
            continue
        peripheral = exposure["peripheral_ms"]
        total_peripheral = float(peripheral.sum())
        if total_peripheral <= 0:
            exclusions["zero_total_peripheral_pai"] += 1
            continue
        pai_share = peripheral / total_peripheral
        binary = exposure["binary_dwell_ms"]
        total_binary = float(binary.sum())
        binary_share = binary / total_binary if total_binary > 0 else np.zeros_like(binary)
        other = np.delete(pai_share, clicked_i)
        enriched = {
            **row,
            "pai_window_ms": window_ms,
            "pai_form": form,
            "n_main_aois": len(cards),
            "covered_fixation_ms": exposure["covered_fixation_ms"],
            "total_peripheral_pai_ms": total_peripheral,
            "clicked_peripheral_pai_share": float(pai_share[clicked_i]),
            "clicked_binary_dwell_share": float(binary_share[clicked_i]),
            "no_binary_dwell_in_window": float(total_binary <= 0),
            "pai_geometry_competition": float(np.max(other) - pai_share[clicked_i]) if len(other) else None,
        }

        if row["etype"] == "organic":
            organic = typed_organic_cosines(tid, content, cards)
            clicked_sem = organic.get(row["display_rank0"])
            joined = [(pos, rec) for pos, rec in organic.items() if pos in by_pos]
            if clicked_sem is not None and len(joined) > 1:
                indices = np.asarray([by_pos[pos] for pos, _ in joined])
                organic_mass = peripheral[indices]
                organic_total = float(organic_mass.sum())
                if organic_total > 0:
                    organic_share = organic_mass / organic_total
                    clicked_cos = clicked_sem["q_text_cosine"]
                    conflict = 0.0
                    all_other_cos = []
                    for share, (pos, rec) in zip(organic_share, joined):
                        if pos == row["display_rank0"]:
                            continue
                        advantage = rec["q_text_cosine"] - clicked_cos
                        conflict += float(share) * max(0.0, advantage)
                        all_other_cos.append(rec["q_text_cosine"])
                    enriched["pai_semantic_conflict"] = conflict
                    enriched["all_competitive_disadvantage"] = max(all_other_cos) - clicked_cos
                    enriched["organic_peripheral_pai_total_ms"] = organic_total
                    enriched["n_joined_organic"] = len(joined)
        out.append(enriched)
    return out, dict(exclusions)


def z_params(rows, keys):
    out = {}
    for key in keys:
        values = np.asarray([row[key] for row in rows], dtype=float)
        sd = float(np.std(values, ddof=1))
        if not math.isfinite(sd) or sd <= 0:
            raise ValueError(f"non-varying feature: {key}")
        out[key] = (float(np.mean(values)), sd)
    return out


def z(row, key, params):
    mean, sd = params[key]
    return (row[key] - mean) / sd


def design_semantic(rows):
    zkeys = [
        "pai_semantic_conflict",
        "all_competitive_disadvantage",
        "clicked_peripheral_pai_share",
        "clicked_binary_dwell_share",
    ]
    params = z_params(rows, zkeys)
    ranks = sorted({row["display_rank0"] for row in rows})
    names = [
        "regressive_return",
        "pai_semantic_conflict_z",
        "regressive_x_pai_semantic_conflict_z",
        "unweighted_semantic_disadvantage_z",
        "regressive_x_unweighted_semantic_disadvantage_z",
        "clicked_peripheral_pai_share_z",
        "clicked_binary_dwell_share_z",
        "no_binary_dwell_in_window",
        "log_decision_time",
        "target_fix_age_s",
        "log1p_cursor_speed",
    ] + [f"display_rank_{rank + 1}" for rank in ranks[1:]]

    def vector(row):
        reg = row["is_regressive"]
        conflict = z(row, "pai_semantic_conflict", params)
        raw = z(row, "all_competitive_disadvantage", params)
        return [
            reg, conflict, reg * conflict, raw, reg * raw,
            z(row, "clicked_peripheral_pai_share", params),
            z(row, "clicked_binary_dwell_share", params),
            row["no_binary_dwell_in_window"],
            row["log_decision_time"], row["target_fix_age_ms"] / 1000.0,
            math.log1p(row["prepress_cursor_speed_px_s"]),
            *[float(row["display_rank0"] == rank) for rank in ranks[1:]],
        ]
    return names, vector, params


def design_geometry(rows, include_pai=True):
    zkeys = ["pai_geometry_competition", "clicked_peripheral_pai_share", "clicked_binary_dwell_share"]
    params = z_params(rows, zkeys)
    ranks = sorted({row["display_rank0"] for row in rows})
    surfaces = [surface for surface in ("dd_top", "native_ad", "widget") if any(r["surface_group"] == surface for r in rows)]
    names = ["regressive_return"]
    if include_pai:
        names += [
            "pai_geometry_competition_z",
            "regressive_x_pai_geometry_competition_z",
            "clicked_peripheral_pai_share_z",
            "clicked_binary_dwell_share_z",
            "no_binary_dwell_in_window",
        ]
    names += [f"surface_{surface}" for surface in surfaces]
    names += [f"regressive_x_surface_{surface}" for surface in surfaces]
    names += ["log_decision_time", "target_fix_age_s", "log1p_cursor_speed"]
    names += [f"display_rank_{rank + 1}" for rank in ranks[1:]]

    def vector(row):
        reg = row["is_regressive"]
        values = [reg]
        if include_pai:
            competition = z(row, "pai_geometry_competition", params)
            values += [
                competition, reg * competition,
                z(row, "clicked_peripheral_pai_share", params),
                z(row, "clicked_binary_dwell_share", params),
                row["no_binary_dwell_in_window"],
            ]
        values += [float(row["surface_group"] == surface) for surface in surfaces]
        values += [reg * float(row["surface_group"] == surface) for surface in surfaces]
        values += [
            row["log_decision_time"], row["target_fix_age_ms"] / 1000.0,
            math.log1p(row["prepress_cursor_speed_px_s"]),
            *[float(row["display_rank0"] == rank) for rank in ranks[1:]],
        ]
        return values
    return names, vector, params


def sufficient_statistics(rows, design):
    names, vector, params = design
    pids = sorted({row["pid"] for row in rows})
    xtx, xty = [], []
    for pid in pids:
        subset = [row for row in rows if row["pid"] == pid]
        y = np.asarray([row["log_press_duration"] for row in subset])
        x = np.asarray([vector(row) for row in subset])
        yc = y - y.mean()
        xc = x - x.mean(axis=0)
        xtx.append(xc.T @ xc)
        xty.append(xc.T @ yc)
    return np.asarray(xtx), np.asarray(xty), pids, names, params


def term(beta, boot):
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


def fit(rows, design, report_names, slope_pair=None, seed=SEED):
    xtx, xty, pids, names, params = sufficient_statistics(rows, design)
    total_x = xtx.sum(axis=0)
    total_y = xty.sum(axis=0)
    beta = np.linalg.lstsq(total_x, total_y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(len(pids), np.repeat(1 / len(pids), len(pids)), size=BOOTSTRAPS)
    boot = np.empty((BOOTSTRAPS, len(beta)))
    for i, weights in enumerate(counts):
        boot[i] = np.linalg.lstsq(
            np.tensordot(weights, xtx, axes=(0, 0)),
            np.tensordot(weights, xty, axes=(0, 0)),
            rcond=None,
        )[0]
    result = {
        "n": len(rows),
        "n_first_forward": sum(row["is_regressive"] == 0 for row in rows),
        "n_regressive_return": sum(row["is_regressive"] == 1 for row in rows),
        "n_participants": len(pids),
        "feature_standardization": {key: {"mean": value[0], "sd": value[1]} for key, value in params.items()},
        "terms": {name: term(beta[names.index(name)], boot[:, names.index(name)]) for name in report_names if name in names},
    }
    if slope_pair:
        main_i = names.index(slope_pair[0])
        int_i = names.index(slope_pair[1])
        result["first_forward_feature_slope"] = term(beta[main_i], boot[:, main_i])
        result["regressive_feature_slope"] = term(beta[main_i] + beta[int_i], boot[:, main_i] + boot[:, int_i])
        loo = []
        for i in range(len(pids)):
            b = np.linalg.lstsq(total_x - xtx[i], total_y - xty[i], rcond=None)[0]
            loo.append(100 * (math.exp(b[int_i]) - 1))
        full = result["terms"][slope_pair[1]]["percent_change"]
        result["interaction_leave_one_participant_out"] = {
            "min_percent_change": float(np.min(loo)),
            "median_percent_change": float(np.median(loo)),
            "max_percent_change": float(np.max(loo)),
            "same_sign_as_full": int(sum(np.sign(value) == np.sign(full) for value in loo)),
            "n": len(loo),
        }
    return result


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    out = [None] * len(p_values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[index])
        out[index] = min(1.0, running)
    return out


def write_csv(rows):
    keys = sorted({key for row in rows for key in row})
    with open(OUT / "pai_click_records.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def fmt(term_result):
    lo, hi = term_result["bootstrap_ci95_percent_change"]
    return f'{term_result["percent_change"]:+.2f}% [{lo:+.2f}, {hi:+.2f}], p={term_result["bootstrap_p_two_sided"]:.3f}'


def make_plot(summary):
    panels = [
        ("Semantic conflict × regressive", summary["primary"]["semantic"], "regressive_x_pai_semantic_conflict_z"),
        ("Geometry competition × regressive", summary["primary"]["geometry"], "regressive_x_pai_geometry_competition_z"),
    ]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for y, (label, result, key) in enumerate(panels):
        item = result["terms"][key]
        lo, hi = item["bootstrap_ci95_percent_change"]
        point = item["percent_change"]
        ax.errorbar(point, y, xerr=[[point - lo], [hi - point]], fmt="o", capsize=4, color="#315a7d")
    ax.axvline(0, color="#555", linewidth=1)
    ax.set_yticks(range(len(panels)), [panel[0] for panel in panels])
    ax.set_xlabel("Pass-interaction change in press duration per +1 SD (%)")
    ax.set_title("PAI-weighted click-press interactions\n[LAB, AdSERP, typed_gapfill]", fontsize=13)
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "pai_conflict_interactions.png", dpi=180)
    plt.close(fig)


def write_report(summary):
    sem = summary["primary"]["semantic"]
    geo = summary["primary"]["geometry"]
    sem_int = sem["terms"]["regressive_x_pai_semantic_conflict_z"]
    geo_int = geo["terms"]["regressive_x_pai_geometry_competition_z"]
    baseline = summary["primary"]["geometry_surface_baseline"]
    dd0 = baseline["terms"].get("regressive_x_surface_dd_top")
    dd1 = geo["terms"].get("regressive_x_surface_dd_top")
    lines = [
        "# PAI-weighted click-press conflict",
        "",
        "**Regime:** `[LAB, AdSERP, typed_gapfill]`  ",
        "**Primary window:** fixed 1,000 ms ending at `mousedown`  ",
        "**PAI:** exact demo formula, strictly peripheral mass (`OGD > 0`)  ",
        "**Inference:** participant fixed effects; 5,000 participant-cluster bootstrap resamples",
        "",
        "## Results",
        "",
        f"- Organic PAI-weighted semantic-conflict × pass: **{fmt(sem_int)}** (n={sem['n']}).",
        f"- Geometry-only PAI-competition × pass: **{fmt(geo_int)}** (n={geo['n']}).",
        f"- Holm-adjusted p-values across the two primary PAI interactions: semantic **{summary['primary']['holm_p']['semantic']:.3f}**, geometry **{summary['primary']['holm_p']['geometry']:.3f}**.",
        f"- Semantic slope within first-forward clicks: {fmt(sem['first_forward_feature_slope'])}; within regressive clicks: {fmt(sem['regressive_feature_slope'])}.",
        f"- Geometry slope within first-forward clicks: {fmt(geo['first_forward_feature_slope'])}; within regressive clicks: {fmt(geo['regressive_feature_slope'])}.",
    ]
    if dd0 and dd1:
        lines += [
            f"- `dd_top` × pass before PAI terms: {fmt(dd0)}; after PAI competition/dwell terms: {fmt(dd1)}.",
        ]
    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "The semantic feature is not generic ambiguity. It increases only when a semantically better organic alternative also receives peripheral PAI mass in the fixed pre-press window. The model separately controls the unweighted best-alternative disadvantage, clicked-target peripheral PAI share, and clicked-target strict in-AOI dwell share.",
        "",
        "The geometry feature contains no text: it is the strongest other AOI's peripheral PAI share minus the clicked AOI's share. Its model includes surface and pass-by-surface terms, so a PAI interaction is not merely an ad-versus-organic contrast. Widgets are pooled because individual widget classes are sparse; `dd_top` and `native_ad` remain distinct.",
        "",
        "PAI shares are normalized within a fixed window. This avoids treating a longer evidence-accumulation interval as stronger PAI evidence. PAI remains complementary to binary dwell rather than replacing it.",
        "",
        "## Sensitivities",
        "",
    ]
    for label, block in summary["sensitivities"].items():
        s = block["semantic"]["terms"]["regressive_x_pai_semantic_conflict_z"]
        g = block["geometry"]["terms"]["regressive_x_pai_geometry_competition_z"]
        lines.append(f"- **{label}:** semantic {fmt(s)}; geometry {fmt(g)}.")
    lines += [
        "",
        "## Provenance",
        "",
        "- Press pairing: terminal same-XPath `mousedown` → `mouseup`; gaze/PAI anchored at `mousedown`.",
        "- Rank and AOI geometry: `typed_gapfill` display positions; ads/widgets count as rank positions.",
        "- Semantic joins: organic AOI `rso[k]` → absolute h3 cache position `k`; cache positions are never used as behavioral rank.",
        "- Fixed effects: participant and categorical typed display rank. Shared controls: log decision time, target-fixation recency, and log1p pre-press cursor speed.",
    ]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")


def analyze_spec(rows, window_ms, form, content, seed):
    featured, exclusions = add_pai_features(rows, window_ms, form, content)
    semantic_rows = [
        row for row in featured
        if finite(row.get("pai_semantic_conflict")) is not None
        and finite(row.get("all_competitive_disadvantage")) is not None
    ]
    geometry_rows = [row for row in featured if finite(row.get("pai_geometry_competition")) is not None]
    semantic_names = [
        "regressive_return", "pai_semantic_conflict_z",
        "regressive_x_pai_semantic_conflict_z",
        "unweighted_semantic_disadvantage_z",
        "regressive_x_unweighted_semantic_disadvantage_z",
        "clicked_peripheral_pai_share_z", "clicked_binary_dwell_share_z",
        "no_binary_dwell_in_window",
    ]
    semantic = fit(
        semantic_rows, design_semantic(semantic_rows), semantic_names,
        ("pai_semantic_conflict_z", "regressive_x_pai_semantic_conflict_z"), seed,
    )
    geometry_design = design_geometry(geometry_rows, include_pai=True)
    geometry_names = [
        "regressive_return", "pai_geometry_competition_z",
        "regressive_x_pai_geometry_competition_z",
        "clicked_peripheral_pai_share_z", "clicked_binary_dwell_share_z",
        "no_binary_dwell_in_window",
        "regressive_x_surface_dd_top", "regressive_x_surface_native_ad",
        "regressive_x_surface_widget",
    ]
    geometry = fit(
        geometry_rows, geometry_design, geometry_names,
        ("pai_geometry_competition_z", "regressive_x_pai_geometry_competition_z"), seed + 1,
    )
    baseline_names = [
        "regressive_return", "regressive_x_surface_dd_top",
        "regressive_x_surface_native_ad", "regressive_x_surface_widget",
    ]
    baseline = fit(
        geometry_rows, design_geometry(geometry_rows, include_pai=False),
        baseline_names, None, seed + 2,
    )
    return featured, {
        "window_ms": window_ms,
        "pai_form": form,
        "exclusions": exclusions,
        "surface_counts": dict(Counter(row["surface_group"] for row in geometry_rows)),
        "semantic": semantic,
        "geometry": geometry,
        "geometry_surface_baseline": baseline,
    }


def main():
    if not PRESS_CSV.exists() or not SEMANTIC_CSV.exists():
        raise SystemExit("Run the click-press and semantic-margin prerequisite scripts first.")
    base = load_base_rows()
    content = content_index()
    primary_rows, primary = analyze_spec(base, PRIMARY_WINDOW_MS, "exact", content, SEED)
    sensitivity = {}
    for label, window, form, seed in (
        ("2,000 ms exact PAI", 2000, "exact", SEED + 100),
        ("1,000 ms NB35 linear PAI", 1000, "nb35", SEED + 200),
    ):
        _, result = analyze_spec(base, window, form, content, seed)
        sensitivity[label] = result

    p = [
        primary["semantic"]["terms"]["regressive_x_pai_semantic_conflict_z"]["bootstrap_p_two_sided"],
        primary["geometry"]["terms"]["regressive_x_pai_geometry_competition_z"]["bootstrap_p_two_sided"],
    ]
    adjusted = holm_adjust(p)
    primary["holm_p"] = {"semantic": adjusted[0], "geometry": adjusted[1]}
    summary = {
        "regime": "LAB, AdSERP, typed_gapfill",
        "rank_type": "typed_gapfill display rank; ads/widgets included",
        "anchor": "mousedown",
        "pai_definition": {
            "primary": "clip(1 - sqrt(OGD/max(CGD,1))*w_A, 0, 1), strictly OGD>0",
            "area_weight": "w_A=(Amax/A)^(phi^3)",
            "sensitivity": "clip(1 - OGD/max(CGD,1), 0, 1), strictly OGD>0",
        },
        "base_primary_clicks": len(base),
        "primary": primary,
        "sensitivities": sensitivity,
    }
    write_csv(primary_rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(summary)
    make_plot(summary)
    print((OUT / "report.md").read_text())


if __name__ == "__main__":
    main()
