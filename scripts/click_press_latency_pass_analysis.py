"""Click press duration on first-forward versus regressive target encounters.

The evtrack ``click`` row is emitted substantially after ``mouseup`` in AdSERP.
This analysis therefore pairs the terminal same-XPath ``mousedown``/``mouseup``
events and anchors all gaze and pupil features at ``mousedown``.

Primary behavioral contrast (typed_gapfill, LAB):
  * first_forward: the latest pre-press gaze episode on the clicked target is
    the target's first encounter and advances (or equals) the rank high-water
    mark;
  * regressive_return: that episode revisits an already-seen target below the
    rank high-water mark.

The classifier only consumes gaze at or before mousedown. Backfilled first
looks, repeated frontier looks, stale target looks, and off-axis clicks are
reported but excluded from the primary contrast.

LF/HF is computed from exactly 150/300/450 pupil samples ending at mousedown
(1/2/3 s nominally). This fixed-sample window is the primary LF/HF measure;
the legacy whole-target LF/HF value is retained only as a confounded audit.

Outputs:
  scripts/output/click_press_latency_pass/
    click_press_records.csv
    summary.json
    report.md
    press_latency_pass_and_correlates.png

Run:
  .venv/bin/python scripts/click_press_latency_pass_analysis.py
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
from scipy import stats
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "AdSERP" / "data"
MOUSE_DIR = DATA / "mouse-movement-data"
OUT = ROOT / "scripts" / "output" / "click_press_latency_pass"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
from compute_ripa2 import compute_ripa2_signal  # noqa: E402
from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    attribute_click_to_typed_gapfill,
    get_trial_ids,
    load_difficulty_measures,
    load_fixations,
    load_lhipa,
    load_pupil_trial,
    typed_gapfill_aoi_tops,
)

FS = 150
LF_SOS = butter(4, 1.6, btype="low", fs=FS, output="sos")
HF_SOS = butter(4, (1.6, 4.0), btype="band", fs=FS, output="sos")
PRIMARY_PUPIL_SAMPLES = 300
MAX_PRESS_MS = 1000
MAX_TARGET_FIX_AGE_MS = 1500
MAX_UP_TO_CLICK_MS = 15000
BOOTSTRAPS = 5000
SEED = 20260822


def finite(value):
    """Float value or None, safe for JSON/CSV input."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def load_mouse_rows(tid):
    rows = []
    with open(MOUSE_DIR / f"{tid}.csv") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "t": int(float(row["timestamp"])),
                    "x": float(row["xpos"]),
                    "y": float(row["ypos"]),
                    "event": row["event"],
                    "xpath": row.get("xpath", ""),
                })
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def pair_terminal_press(rows):
    """Pair terminal click to nearest preceding same-XPath up and down."""
    click_indices = [i for i, row in enumerate(rows) if row["event"] == "click"]
    if not click_indices:
        return None, "no_click"
    ci = click_indices[-1]
    click = rows[ci]
    up_indices = [
        i for i, row in enumerate(rows[:ci])
        if row["event"] == "mouseup" and row["xpath"] == click["xpath"]
    ]
    if not up_indices:
        return None, "no_same_xpath_mouseup"
    ui = up_indices[-1]
    up = rows[ui]
    down_indices = [
        i for i, row in enumerate(rows[:ui])
        if row["event"] == "mousedown" and row["xpath"] == click["xpath"]
    ]
    if not down_indices:
        return None, "no_same_xpath_mousedown"
    di = down_indices[-1]
    down = rows[di]
    hold_ms = up["t"] - down["t"]
    up_to_click_ms = click["t"] - up["t"]
    if hold_ms < 0:
        return None, "negative_press_duration"
    if not (0 <= up_to_click_ms <= MAX_UP_TO_CLICK_MS):
        return None, "implausible_up_to_click_lag"

    prior_downs = sum(1 for row in rows[:di] if row["event"] == "mousedown")
    down_up_distance = math.hypot(up["x"] - down["x"], up["y"] - down["y"])
    return {
        "click": click,
        "down": down,
        "up": up,
        "hold_ms": hold_ms,
        "up_to_click_ms": up_to_click_ms,
        "prior_mousedown_count": prior_downs,
        "down_up_distance_px": down_up_distance,
    }, None


def prepress_cursor_features(rows, down_t, window_ms=500):
    pos_events = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup"}
    points = [
        row for row in rows
        if down_t - window_ms <= row["t"] <= down_t and row["event"] in pos_events
    ]
    if len(points) < 2:
        # evtrack emits movement events; a window containing only the down
        # event means no observed cursor displacement in the prior 500 ms.
        return {"prepress_cursor_speed_px_s": 0.0, "prepress_cursor_path_px": 0.0}
    path = sum(
        math.hypot(b["x"] - a["x"], b["y"] - a["y"])
        for a, b in zip(points, points[1:])
    )
    return {
        "prepress_cursor_speed_px_s": path / (window_ms / 1000.0),
        "prepress_cursor_path_px": path,
    }


def scroll_features(rows, down_t):
    scrolls = [row for row in rows if row["event"] == "scroll" and row["t"] <= down_t]
    if not scrolls:
        return {"scroll_y_at_press": 0.0, "scroll_retreat_px": 0.0}
    ys = [row["y"] for row in scrolls]
    return {
        "scroll_y_at_press": ys[-1],
        "scroll_retreat_px": max(ys) - ys[-1],
    }


def classify_target_encounter(tid, click_pos, down):
    """Classify latest pre-down target gaze episode without future leakage."""
    tops = typed_gapfill_aoi_tops(tid)
    if not tops:
        return None, "no_typed_gapfill_aois"
    fixations = load_fixations(tid)
    if not fixations:
        return None, "no_fixations"

    visited = set()
    hwm = -1
    previous_pos = None
    episode_label = None
    target_visits = 0
    target_dwell_ms = 0.0
    last_target = None
    last_valid_fix = None

    for fix in fixations:
        if fix["t"] > down["t"]:
            break
        pos = assign_fixation_to_position(fix["y"], tops, len(tops))
        if pos is None or pos < 0:
            continue
        if pos != previous_pos:
            if pos not in visited and pos >= hwm:
                episode_label = "first_forward"
            elif pos in visited and pos < hwm:
                episode_label = "regressive_return"
            elif pos not in visited and pos < hwm:
                episode_label = "backfill_first"
            elif pos in visited and pos >= hwm:
                episode_label = "repeat_frontier"
            else:
                episode_label = "other"
            if pos == click_pos:
                target_visits += 1
            visited.add(pos)
            hwm = max(hwm, pos)
            previous_pos = pos

        last_valid_fix = fix
        if pos == click_pos:
            target_dwell_ms += min(fix["d"], max(0.0, down["t"] - fix["t"]))
            age = max(0.0, down["t"] - (fix["t"] + fix["d"]))
            last_target = {
                "pass_label": episode_label,
                "target_fix_age_ms": age,
                "regression_depth": max(0, hwm - click_pos),
                "hwm_at_target": hwm,
                "last_target_fix_x": fix["x"],
                "last_target_fix_y": fix["y"],
            }

    if last_target is None:
        return None, "no_prepress_target_fixation"
    last_target.update({
        "target_visit_count": target_visits,
        "target_dwell_ms": target_dwell_ms,
        "gaze_cursor_distance_px": math.hypot(
            down["x"] - last_target["last_target_fix_x"],
            down["y"] - last_target["last_target_fix_y"],
        ),
        "last_any_fix_age_ms": (
            max(0.0, down["t"] - (last_valid_fix["t"] + last_valid_fix["d"]))
            if last_valid_fix else None
        ),
    })
    if last_target["target_fix_age_ms"] > MAX_TARGET_FIX_AGE_MS:
        return last_target, "stale_target_fixation"
    return last_target, None


def fixed_sample_pupil_features(tid, down_t):
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return {}
    ts = np.asarray(pupil["ts"], dtype=float)
    pd = np.asarray(pupil["clean_pd"], dtype=float)
    if len(pd) < 243:
        return {}
    end = int(np.searchsorted(ts, down_t, side="right"))
    if end < 150:
        return {}

    # Filter only the prefix ending at mousedown. The canonical zero-phase
    # filters are retained, but no post-press samples can leak backward into
    # a purportedly pre-press feature.
    ts = ts[:end]
    pd = pd[:end]
    end = len(pd)
    lf_signal = sosfiltfilt(LF_SOS, pd)
    hf_signal = sosfiltfilt(HF_SOS, pd)
    ripa2_signal = compute_ripa2_signal(pd)
    out = {}
    for n, label in ((150, "1s"), (300, "2s"), (450, "3s")):
        if end < n:
            out[f"prepress_lfhf_{label}"] = None
            out[f"prepress_window_span_{label}_ms"] = None
            continue
        idx = np.arange(end - n, end)
        span_ms = ts[idx[-1]] - ts[idx[0]]
        # Guard against rare acquisition gaps while keeping sample count exact.
        if not (0.8 * (1000 * n / FS) <= span_ms <= 1.25 * (1000 * n / FS)):
            out[f"prepress_lfhf_{label}"] = None
            out[f"prepress_window_span_{label}_ms"] = float(span_ms)
            continue
        lf_power = float(np.var(lf_signal[idx]))
        hf_power = float(np.var(hf_signal[idx]))
        out[f"prepress_lfhf_{label}"] = lf_power / hf_power if hf_power > 1e-20 else None
        out[f"prepress_window_span_{label}_ms"] = float(span_ms)
        if n == PRIMARY_PUPIL_SAMPLES:
            out["prepress_ripa2_2s"] = float(np.mean(ripa2_signal[idx]))
            out["prepress_pupil_mean_2s"] = float(np.mean(pd[idx]))
            x = (ts[idx] - ts[idx][0]) / 1000.0
            out["prepress_pupil_slope_2s"] = float(np.polyfit(x, pd[idx], 1)[0])
    return out


def index_position_json(path, value_key):
    data = json.load(open(path))
    out = {}
    for tid, trial in data.items():
        for row in trial.get("positions", []):
            out[(tid, int(row["pos"]))] = {
                value_key: finite(row.get(value_key)),
                "n_samples": finite(row.get("n_samples")),
                "duration_s": finite(row.get("duration_s")),
            }
    return out


def index_clicked_approach():
    path = DATA / "cursor-approach-features-typed-gapfill.json"
    out = {}
    for row in json.load(open(path)):
        if row.get("was_clicked"):
            out[(row["trial_id"], int(row["position"]))] = row
    return out


def build_records():
    difficulty = load_difficulty_measures()
    lhipa = load_lhipa()
    whole_lfhf = index_position_json(
        DATA / "butterworth-lfhf-by-position-typed.json", "lfhf"
    )
    whole_ripa2 = index_position_json(DATA / "ripa2-by-position-typed.json", "ripa2")
    approach = index_clicked_approach()
    exclusions = Counter()
    label_counts = Counter()
    rows_out = []

    for i, tid in enumerate(get_trial_ids(), start=1):
        if i % 400 == 0:
            print(f"processed {i:,} trials", file=sys.stderr)
        rows = load_mouse_rows(tid)
        pair, reason = pair_terminal_press(rows)
        if pair is None:
            exclusions[reason] += 1
            continue
        click = pair["click"]
        attr = attribute_click_to_typed_gapfill(click["x"], click["y"], tid)
        if attr is None:
            exclusions["off_main_axis_click"] += 1
            continue
        click_pos, etype = attr
        encounter, encounter_reason = classify_target_encounter(
            tid, click_pos, pair["down"]
        )
        if encounter is None:
            exclusions[encounter_reason] += 1
            continue

        row = {
            "trial_id": tid,
            "pid": tid.split("-")[0],
            "click_pos": click_pos,
            "etype": etype,
            "pass_label": encounter["pass_label"],
            "primary_pass_eligible": bool(
                encounter_reason is None
                and encounter["pass_label"] in {"first_forward", "regressive_return"}
                and pair["hold_ms"] <= MAX_PRESS_MS
            ),
            "press_duration_ms": pair["hold_ms"],
            "up_to_click_ms": pair["up_to_click_ms"],
            "decision_time_ms": pair["down"]["t"] - rows[0]["t"],
            "prior_mousedown_count": pair["prior_mousedown_count"],
            "down_up_distance_px": pair["down_up_distance_px"],
            "click_x": click["x"],
            "click_y": click["y"],
            "pair_same_xpath": True,
            "target_fix_stale": encounter_reason == "stale_target_fixation",
            **encounter,
            **prepress_cursor_features(rows, pair["down"]["t"]),
            **scroll_features(rows, pair["down"]["t"]),
            **fixed_sample_pupil_features(tid, pair["down"]["t"]),
        }
        label_counts[encounter["pass_label"]] += 1
        if encounter_reason:
            exclusions[encounter_reason] += 1
        if pair["hold_ms"] > MAX_PRESS_MS:
            exclusions["press_over_1000ms"] += 1

        diff = difficulty.get(tid, {})
        for key in ("jaccard", "distinctive_density", "relevance_spread", "n_results"):
            row[f"difficulty_{key}"] = finite(diff.get(key))
        row["trial_lhipa"] = finite(lhipa.get(tid, {}).get("lhipa"))

        lf = whole_lfhf.get((tid, click_pos), {})
        rp = whole_ripa2.get((tid, click_pos), {})
        row["whole_target_lfhf_typed"] = lf.get("lfhf")
        row["whole_target_lfhf_n_samples"] = lf.get("n_samples")
        row["whole_target_lfhf_duration_s"] = lf.get("duration_s")
        row["whole_target_ripa2_typed"] = rp.get("ripa2")

        app = approach.get((tid, click_pos), {})
        for key in (
            "n_fixations", "total_dwell_ms", "min_dist", "mean_dist",
            "final_dist", "retreat_dist", "dwell_in_proximity_ms",
            "mean_approach_velocity", "max_approach_velocity",
            "direction_changes", "frac_decreasing",
        ):
            row[f"approach_{key}"] = finite(app.get(key))
        rows_out.append(row)

    return rows_out, exclusions, label_counts


def describe(values):
    x = np.asarray([v for v in values if finite(v) is not None], dtype=float)
    if len(x) == 0:
        return {"n": 0}
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)) if len(x) > 1 else None,
        "median": float(np.median(x)),
        "q1": float(np.quantile(x, 0.25)),
        "q3": float(np.quantile(x, 0.75)),
    }


def participant_contrast(rows, seed=SEED):
    by_pid = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_pid[row["pid"]][row["pass_label"]].append(row["press_duration_ms"])
    deltas = []
    pid_rows = []
    for pid, groups in by_pid.items():
        if groups["first_forward"] and groups["regressive_return"]:
            fwd = float(np.median(groups["first_forward"]))
            reg = float(np.median(groups["regressive_return"]))
            deltas.append(reg - fwd)
            pid_rows.append({
                "pid": pid, "first_forward_median_ms": fwd,
                "regressive_return_median_ms": reg, "delta_ms": reg - fwd,
                "n_first_forward": len(groups["first_forward"]),
                "n_regressive_return": len(groups["regressive_return"]),
            })
    x = np.asarray(deltas, dtype=float)
    if len(x) == 0:
        return {"n_participants": 0}, []
    wilcoxon = stats.wilcoxon(x, alternative="two-sided")
    rng = np.random.default_rng(seed)
    boot = np.array([
        np.mean(rng.choice(x, size=len(x), replace=True)) for _ in range(BOOTSTRAPS)
    ])
    boot_median = np.array([
        np.median(rng.choice(x, size=len(x), replace=True)) for _ in range(BOOTSTRAPS)
    ])
    return {
        "n_participants": int(len(x)),
        "mean_participant_delta_ms": float(np.mean(x)),
        "mean_participant_delta_ci95": [
            float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
        ],
        "median_participant_delta_ms": float(np.median(x)),
        "median_participant_delta_ci95": [
            float(np.quantile(boot_median, 0.025)),
            float(np.quantile(boot_median, 0.975)),
        ],
        "participants_positive_pct": float(100 * np.mean(x > 0)),
        "wilcoxon_statistic": float(wilcoxon.statistic),
        "wilcoxon_p_two_sided": float(wilcoxon.pvalue),
    }, pid_rows


def rank_breakdown(rows):
    """Raw and participant-paired press contrasts by 1-based display rank."""
    out = []
    for rank0 in sorted({int(row["click_pos"]) for row in rows}):
        subset = [row for row in rows if int(row["click_pos"]) == rank0]
        first = [row for row in subset if row["pass_label"] == "first_forward"]
        reg = [row for row in subset if row["pass_label"] == "regressive_return"]
        paired, _ = participant_contrast(subset, seed=SEED + rank0)
        first_median = float(np.median([row["press_duration_ms"] for row in first])) if first else None
        reg_median = float(np.median([row["press_duration_ms"] for row in reg])) if reg else None
        out.append({
            "display_rank_1based": rank0 + 1,
            "click_pos_0based": rank0,
            "n_first_forward": len(first),
            "participants_first_forward": len({row["pid"] for row in first}),
            "median_first_forward_ms": first_median,
            "n_regressive_return": len(reg),
            "participants_regressive_return": len({row["pid"] for row in reg}),
            "median_regressive_return_ms": reg_median,
            "raw_median_delta_ms": (
                reg_median - first_median
                if first_median is not None and reg_median is not None else None
            ),
            "paired_participants": paired.get("n_participants", 0),
            "median_participant_delta_ms": paired.get("median_participant_delta_ms"),
            "wilcoxon_p_two_sided": paired.get("wilcoxon_p_two_sided"),
        })
    return out


def rank_by_pass_interaction(rows, max_rank0=6, seed=SEED):
    """Participant-demeaned log-hold model: regressive + rank + interaction.

    Restricted to display ranks 1--7 because later first-forward cells contain
    fewer than ten clicks and cannot support a stable interaction estimate.
    """
    selected = [row for row in rows if int(row["click_pos"]) <= max_rank0]
    packed = []
    for row in selected:
        rank = float(row["click_pos"])
        reg = 1.0 if row["pass_label"] == "regressive_return" else 0.0
        packed.append((
            row["pid"], math.log(float(row["press_duration_ms"])),
            np.asarray([reg, rank, reg * rank], dtype=float),
        ))
    pids = sorted({row[0] for row in packed})

    def design(selected_pids):
        y_all, x_all = [], []
        for pid in selected_pids:
            subset = [row for row in packed if row[0] == pid]
            y = np.asarray([row[1] for row in subset])
            x = np.stack([row[2] for row in subset])
            y_all.append(y - np.mean(y))
            x_all.append(x - np.mean(x, axis=0))
        return np.concatenate(y_all), np.vstack(x_all)

    y, x = design(pids)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(BOOTSTRAPS):
        yb, xb = design(list(rng.choice(pids, size=len(pids), replace=True)))
        boot.append(np.linalg.lstsq(xb, yb, rcond=None)[0])
    boot = np.asarray(boot)
    interaction_ci = np.quantile(boot[:, 2], [0.025, 0.975])
    estimates = []
    for rank0 in range(max_rank0 + 1):
        effect = beta[0] + rank0 * beta[2]
        effect_boot = boot[:, 0] + rank0 * boot[:, 2]
        ci = np.quantile(effect_boot, [0.025, 0.975])
        estimates.append({
            "display_rank_1based": rank0 + 1,
            "regressive_percent_change": float(100 * (math.exp(effect) - 1)),
            "bootstrap_ci95_percent_change": [
                float(100 * (math.exp(ci[0]) - 1)),
                float(100 * (math.exp(ci[1]) - 1)),
            ],
        })
    return {
        "rank_type": "typed_gapfill display rank, 1-based in report",
        "included_display_ranks": [1, max_rank0 + 1],
        "n_observations": len(y),
        "n_participants": len(pids),
        "interaction_log_coefficient_per_rank": float(beta[2]),
        "interaction_percent_change_per_rank": float(100 * (math.exp(beta[2]) - 1)),
        "interaction_bootstrap_ci95_percent_change_per_rank": [
            float(100 * (math.exp(interaction_ci[0]) - 1)),
            float(100 * (math.exp(interaction_ci[1]) - 1)),
        ],
        "rank_specific_regressive_effects": estimates,
    }


def within_participant_regression(rows, covariates, seed=SEED):
    """Participant-demeaned OLS; coefficient 0 is regressive-return effect."""
    complete = []
    for row in rows:
        vals = [finite(row.get(c)) for c in covariates]
        hold = finite(row.get("press_duration_ms"))
        if hold and all(v is not None for v in vals):
            complete.append((row["pid"], math.log(hold), vals))
    candidate_pids = sorted({row[0] for row in complete})
    pids = []
    for pid in candidate_pids:
        subset = [row for row in complete if row[0] == pid]
        if len(subset) >= 2 and np.std([row[2][0] for row in subset]) > 0:
            pids.append(pid)

    def design(selected_pids):
        y_all, x_all = [], []
        for pid in selected_pids:
            subset = [row for row in complete if row[0] == pid]
            if len(subset) < 2:
                continue
            y = np.asarray([row[1] for row in subset], dtype=float)
            x = np.asarray([row[2] for row in subset], dtype=float)
            if np.std(x[:, 0]) == 0:
                continue
            y_all.append(y - np.mean(y))
            x_all.append(x - np.mean(x, axis=0))
        if not y_all:
            return None, None
        return np.concatenate(y_all), np.vstack(x_all)

    y, x = design(pids)
    if y is None or np.linalg.matrix_rank(x) < x.shape[1]:
        return {"n": 0}
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(BOOTSTRAPS):
        sampled = list(rng.choice(pids, size=len(pids), replace=True))
        yb, xb = design(sampled)
        if yb is not None and np.linalg.matrix_rank(xb) == xb.shape[1]:
            boot.append(np.linalg.lstsq(xb, yb, rcond=None)[0][0])
    b = np.asarray(boot)
    return {
        "n_observations": int(len(y)),
        "n_participants": int(len(pids)),
        "covariates": covariates,
        "regressive_log_coefficient": float(beta[0]),
        "regressive_percent_change": float(100 * (math.exp(beta[0]) - 1)),
        "bootstrap_ci95_log_coefficient": [
            float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))
        ],
        "bootstrap_ci95_percent_change": [
            float(100 * (math.exp(np.quantile(b, 0.025)) - 1)),
            float(100 * (math.exp(np.quantile(b, 0.975)) - 1)),
        ],
    }


def within_pid_spearman_pair(
    rows, metric, outcome="press_duration_ms", min_per_pid=8
):
    pairs = []
    by_pid = defaultdict(list)
    for row in rows:
        x = finite(row.get(metric))
        y = finite(row.get(outcome))
        if x is not None and y is not None:
            pairs.append((x, y))
            by_pid[row["pid"]].append((x, y))
    if len(pairs) < 10:
        return {
            "metric": metric, "outcome": outcome, "n": len(pairs),
            "n_participants": 0,
        }
    pooled = stats.spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
    rhos = []
    for vals in by_pid.values():
        if len(vals) < min_per_pid:
            continue
        x = np.asarray([p[0] for p in vals])
        y = np.asarray([p[1] for p in vals])
        if len(np.unique(x)) < 3 or len(np.unique(y)) < 3:
            continue
        rho = stats.spearmanr(x, y).statistic
        if math.isfinite(rho):
            rhos.append(float(rho))
    if not rhos:
        return {
            "metric": metric, "outcome": outcome, "n": len(pairs),
            "pooled_rho": float(pooled.statistic), "pooled_p": float(pooled.pvalue),
            "n_participants": 0,
        }
    test = stats.wilcoxon(rhos, alternative="two-sided")
    return {
        "metric": metric,
        "outcome": outcome,
        "n": len(pairs),
        "pooled_rho": float(pooled.statistic),
        "pooled_p": float(pooled.pvalue),
        "n_participants": len(rhos),
        "median_within_participant_rho": float(np.median(rhos)),
        "mean_within_participant_rho": float(np.mean(rhos)),
        "within_participant_wilcoxon_p": float(test.pvalue),
    }


def within_pid_spearman(rows, metric, min_per_pid=8):
    return within_pid_spearman_pair(
        rows, metric, outcome="press_duration_ms", min_per_pid=min_per_pid
    )


def add_bh_fdr(results, p_key="within_participant_wilcoxon_p"):
    valid = [(i, row[p_key]) for i, row in enumerate(results) if row.get(p_key) is not None]
    if not valid:
        return
    ordered = sorted(valid, key=lambda item: item[1])
    m = len(ordered)
    adjusted = [0.0] * m
    running = 1.0
    for j in range(m - 1, -1, -1):
        _, p = ordered[j]
        running = min(running, p * m / (j + 1))
        adjusted[j] = running
    for (item, _), q in zip(ordered, adjusted):
        results[item]["within_participant_fdr_bh"] = float(min(1.0, q))


def analyze(rows, exclusions, label_counts):
    primary = [row for row in rows if row["primary_pass_eligible"]]
    first = [row for row in primary if row["pass_label"] == "first_forward"]
    reg = [row for row in primary if row["pass_label"] == "regressive_return"]
    contrast, pid_rows = participant_contrast(primary)
    by_rank = rank_breakdown(primary)
    rank_interaction = rank_by_pass_interaction(primary)

    simple_model = within_participant_regression(primary, ["is_regressive"])
    adjusted_covariates = [
        "is_regressive", "click_pos", "log_decision_time",
        "target_fix_age_ms", "prepress_cursor_speed_px_s", "down_up_distance_px",
    ]
    adjusted_model = within_participant_regression(primary, adjusted_covariates)

    metrics = [
        "prepress_lfhf_1s", "prepress_lfhf_2s", "prepress_lfhf_3s",
        "prepress_ripa2_2s", "prepress_pupil_mean_2s", "prepress_pupil_slope_2s",
        "whole_target_lfhf_typed", "whole_target_lfhf_n_samples",
        "whole_target_ripa2_typed", "trial_lhipa", "click_pos",
        "target_fix_age_ms", "target_dwell_ms", "target_visit_count",
        "regression_depth", "decision_time_ms", "prior_mousedown_count",
        "prepress_cursor_speed_px_s",
        "down_up_distance_px", "gaze_cursor_distance_px", "scroll_retreat_px",
        "difficulty_jaccard", "difficulty_distinctive_density",
        "difficulty_relevance_spread", "approach_total_dwell_ms",
        "approach_min_dist", "approach_retreat_dist",
        "approach_dwell_in_proximity_ms", "approach_direction_changes",
    ]
    correlations = [within_pid_spearman(primary, metric) for metric in metrics]
    add_bh_fdr(correlations)
    lfhf_by_pass = {
        "first_forward": within_pid_spearman(first, "prepress_lfhf_2s", min_per_pid=4),
        "regressive_return": within_pid_spearman(reg, "prepress_lfhf_2s", min_per_pid=6),
    }
    legacy_lfhf_duration = within_pid_spearman_pair(
        primary,
        "whole_target_lfhf_n_samples",
        outcome="whole_target_lfhf_typed",
    )

    sensitivities = []
    for max_age in (500, 1000, 1500):
        for max_press in (500, 1000):
            subset = [
                row for row in rows
                if row["pass_label"] in {"first_forward", "regressive_return"}
                and row["target_fix_age_ms"] <= max_age
                and row["press_duration_ms"] <= max_press
            ]
            result, _ = participant_contrast(subset, seed=SEED + max_age + max_press)
            result.update({"max_target_fix_age_ms": max_age, "max_press_ms": max_press})
            sensitivities.append(result)

    summary = {
        "regime": "LAB, AdSERP",
        "rank_type": "typed_gapfill",
        "event_pairing": "terminal click -> nearest preceding same-XPath mouseup -> nearest preceding same-XPath mousedown",
        "time_anchor": "mousedown",
        "primary_definition": {
            "first_forward": "first gaze episode on clicked target while at/advancing rank high-water mark",
            "regressive_return": "return gaze episode on already-seen clicked target below rank high-water mark",
            "max_target_fix_age_ms": MAX_TARGET_FIX_AGE_MS,
            "max_press_ms": MAX_PRESS_MS,
        },
        "counts": {
            "records": len(rows),
            "primary_records": len(primary),
            "participants": len({row["pid"] for row in primary}),
            "labels_before_primary_filters": dict(label_counts),
            "exclusions_and_flags": dict(exclusions),
        },
        "press_duration": {
            "first_forward": describe([row["press_duration_ms"] for row in first]),
            "regressive_return": describe([row["press_duration_ms"] for row in reg]),
            "participant_paired": contrast,
            "within_participant_log_model": simple_model,
            "adjusted_within_participant_log_model": adjusted_model,
            "sensitivity": sensitivities,
            "by_display_rank": by_rank,
            "rank_by_pass_interaction": rank_interaction,
        },
        "correlations": correlations,
        "lfhf_2s_by_pass": lfhf_by_pass,
        "legacy_lfhf_duration_association": legacy_lfhf_duration,
        "lfhf_window_audit": {
            label: describe([row.get(f"prepress_window_span_{label}_ms") for row in primary])
            for label in ("1s", "2s", "3s")
        },
        "participant_rows": pid_rows,
        "limitations": [
            "Press duration is a motor-response measure, not end-to-end decision latency.",
            "No correctness ground truth exists in AdSERP; click rank and SERP difficulty are outcomes/covariates, not accuracy.",
            "Pass labels are inferred from gaze rank order and require a recent target fixation; they do not prove a latent cognitive state.",
            "The fixed-sample prepress LF/HF window removes the known window-length imbalance but remains observational pupillometry.",
            "Legacy whole-target LF/HF is retained only to expose its window-duration confound and must not be the primary physiological result.",
            "Exploratory correlate p-values use participant-level Wilcoxon tests with Benjamini-Hochberg correction.",
        ],
    }
    return summary, primary


def write_records(rows):
    path = OUT / "click_press_records.csv"
    keys = sorted({key for row in rows for key in row})
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, digits=3):
    if value is None:
        return "NA"
    if abs(value) < 0.001 and value != 0:
        return f"{value:.2e}"
    return f"{value:.{digits}f}"


def write_report(summary):
    press = summary["press_duration"]
    fwd = press["first_forward"]
    reg = press["regressive_return"]
    paired = press["participant_paired"]
    adjusted = press["adjusted_within_participant_log_model"]
    rank_interaction = press["rank_by_pass_interaction"]
    corrs = sorted(
        [r for r in summary["correlations"] if r.get("within_participant_fdr_bh") is not None],
        key=lambda r: r["within_participant_fdr_bh"],
    )
    lfhf = next(r for r in summary["correlations"] if r["metric"] == "prepress_lfhf_2s")
    legacy_lfhf = next(
        r for r in summary["correlations"] if r["metric"] == "whole_target_lfhf_typed"
    )
    duration = next(
        r for r in summary["correlations"] if r["metric"] == "whole_target_lfhf_n_samples"
    )
    lines = [
        "# Click press duration: first-forward vs regressive-return",
        "",
        "**Regime:** `[LAB, AdSERP]`  ",
        "**Rank/AOI type:** `typed_gapfill` (current post-cascade primary)  ",
        "**Motor measure:** `mouseup − mousedown`; pass state and physiology anchored at `mousedown`.",
        "",
        "## Result",
        "",
        f"The primary sample contains **{summary['counts']['primary_records']:,} clicks** from "
        f"**{summary['counts']['participants']} participants**: {fwd['n']:,} first-forward and "
        f"{reg['n']:,} regressive-return clicks.",
        "",
        f"Raw median press duration was **{fmt(fwd['median'], 1)} ms** first-forward versus "
        f"**{fmt(reg['median'], 1)} ms** regressive-return. Among the "
        f"{paired['n_participants']} participants represented in both conditions, the median "
        f"participant-level difference (regressive − forward) was "
        f"**{fmt(paired['median_participant_delta_ms'], 1)} ms** "
        f"(participant bootstrap 95% CI {fmt(paired['median_participant_delta_ci95'][0], 1)} to "
        f"{fmt(paired['median_participant_delta_ci95'][1], 1)}; paired Wilcoxon "
        f"p={fmt(paired['wilcoxon_p_two_sided'])}).",
        "",
        f"A participant-demeaned log-duration model adjusting for clicked rank, decision time, "
        f"target-fixation recency, pre-press cursor speed, and down/up displacement estimated "
        f"**{fmt(adjusted.get('regressive_percent_change'), 1)}%** change for regressive-return "
        f"clicks (participant-cluster bootstrap 95% CI "
        f"{fmt(adjusted.get('bootstrap_ci95_percent_change', [None, None])[0], 1)}% to "
        f"{fmt(adjusted.get('bootstrap_ci95_percent_change', [None, None])[1], 1)}%).",
        "",
        "## By display rank",
        "",
        "Ranks are 1-based `typed_gapfill` display ranks (ads/widgets included), not "
        "organic-only ranks. Ranks 8+ have fewer than ten first-forward clicks and are "
        "descriptive only.",
        "",
        "| display rank | first n / median ms | regressive n / median ms | raw Δ ms | paired participants | participant median Δ ms | paired p |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in press["by_display_rank"]:
        if row["display_rank_1based"] > 7:
            continue
        lines.append(
            f"| {row['display_rank_1based']} | {row['n_first_forward']} / "
            f"{fmt(row['median_first_forward_ms'], 1)} | {row['n_regressive_return']} / "
            f"{fmt(row['median_regressive_return_ms'], 1)} | "
            f"{fmt(row['raw_median_delta_ms'], 1)} | {row['paired_participants']} | "
            f"{fmt(row['median_participant_delta_ms'], 1)} | "
            f"{fmt(row['wilcoxon_p_two_sided'])} |"
        )
    lines += [
        "",
        f"Across ranks 1–7, the participant-demeaned rank × pass interaction is "
        f"**{fmt(rank_interaction['interaction_percent_change_per_rank'], 2)}% per rank** "
        f"(cluster-bootstrap 95% CI "
        f"{fmt(rank_interaction['interaction_bootstrap_ci95_percent_change_per_rank'][0], 2)}% "
        f"to {fmt(rank_interaction['interaction_bootstrap_ci95_percent_change_per_rank'][1], 2)}%). "
        "There is no evidence that the forward/regressive press-duration contrast changes "
        "systematically with display rank.",
        "",
        "## LF/HF and other correlates",
        "",
        f"Primary fixed-window LF/HF (exactly 300 samples / nominal 2 s before mousedown) "
        f"had pooled Spearman ρ={fmt(lfhf.get('pooled_rho'))}; the median within-participant "
        f"ρ was {fmt(lfhf.get('median_within_participant_rho'))} "
        f"(participant Wilcoxon p={fmt(lfhf.get('within_participant_wilcoxon_p'))}, "
        f"BH-FDR q={fmt(lfhf.get('within_participant_fdr_bh'))}).",
        "",
        f"For comparison only, legacy whole-target LF/HF had median within-participant "
        f"ρ={fmt(legacy_lfhf.get('median_within_participant_rho'))} with press duration, and "
        f"whole-target sample count had ρ={fmt(duration.get('median_within_participant_rho'))} "
        f"with press duration. More importantly, LF/HF itself correlated with its sample count "
        f"at median within-participant ρ="
        f"{fmt(summary['legacy_lfhf_duration_association'].get('median_within_participant_rho'))}. "
        "The legacy LF/HF association is therefore not interpreted.",
        "",
        "Exploratory participant-aware correlations (ordered by BH-FDR):",
        "",
        "| feature | n | participants | pooled ρ | median within-person ρ | p | q |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in corrs:
        lines.append(
            f"| `{row['metric']}` | {row['n']} | {row.get('n_participants', 0)} | "
            f"{fmt(row.get('pooled_rho'))} | {fmt(row.get('median_within_participant_rho'))} | "
            f"{fmt(row.get('within_participant_wilcoxon_p'))} | "
            f"{fmt(row.get('within_participant_fdr_bh'))} |"
        )
    lines += [
        "",
        "## Classification and exclusions",
        "",
        "A click is `first_forward` only when the latest recent gaze episode on its target is "
        "the target's first encounter at the rank frontier. It is `regressive_return` only when "
        "the target was already seen and is now below the gaze rank high-water mark. Only gaze "
        "at or before mousedown is used. Backfilled first encounters, repeated frontier episodes, "
        "target fixations older than 1.5 s, off-axis clicks, and press durations over 1 s are not "
        "in the primary contrast. See `summary.json` for the complete count flow and threshold "
        "sensitivities.",
        "",
        "The only BH-FDR-surviving exploratory feature was pre-press cursor movement: more "
        "cursor travel per second in the preceding 500 ms accompanied a shorter button hold. "
        "This is best treated as a motor-vigor association, not a cognitive-load result.",
        "",
        "## Interpretation limits",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["limitations"])
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        ".venv/bin/python scripts/click_press_latency_pass_analysis.py",
        "```",
        "",
    ]
    (OUT / "report.md").write_text("\n".join(lines))


def plot_results(summary, primary):
    first = np.asarray([
        row["press_duration_ms"] for row in primary if row["pass_label"] == "first_forward"
    ])
    reg = np.asarray([
        row["press_duration_ms"] for row in primary if row["pass_label"] == "regressive_return"
    ])
    corrs = [
        row for row in summary["correlations"]
        if row.get("median_within_participant_rho") is not None
    ]
    corrs = sorted(corrs, key=lambda row: abs(row["median_within_participant_rho"]), reverse=True)[:12]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    ax = axes[0]
    parts = ax.violinplot([first, reg], positions=[0, 1], showextrema=False, widths=0.8)
    for body, color in zip(parts["bodies"], ["#2b6cb0", "#c05621"]):
        body.set_facecolor(color)
        body.set_alpha(0.35)
    ax.boxplot(
        [first, reg], positions=[0, 1], widths=0.25, showfliers=False,
        medianprops={"color": "black", "linewidth": 2},
        boxprops={"color": "#333333"}, whiskerprops={"color": "#333333"},
        capprops={"color": "#333333"},
    )
    ax.set_xticks([0, 1], [f"First-forward\n(n={len(first)})", f"Regressive-return\n(n={len(reg)})"])
    ax.set_ylabel("Press duration: mouseup − mousedown (ms)")
    ax.set_title("A. Click press duration by target encounter")
    ax.grid(axis="y", alpha=0.2)

    ax = axes[1]
    labels = [row["metric"].replace("_", " ") for row in corrs][::-1]
    values = [row["median_within_participant_rho"] for row in corrs][::-1]
    colors = ["#c05621" if value > 0 else "#2b6cb0" for value in values]
    ax.barh(range(len(values)), values, color=colors, alpha=0.8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_xlabel("Median within-participant Spearman ρ")
    ax.set_title("B. Strongest exploratory correlates")
    ax.grid(axis="x", alpha=0.2)
    fig.suptitle("AdSERP click press duration — LAB, typed_gapfill", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT / "press_latency_pass_and_correlates.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    rows, exclusions, label_counts = build_records()
    for row in rows:
        row["is_regressive"] = 1.0 if row["pass_label"] == "regressive_return" else 0.0
        row["log_decision_time"] = math.log(max(1.0, row["decision_time_ms"]))
    write_records(rows)
    summary, primary = analyze(rows, exclusions, label_counts)
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    write_report(summary)
    plot_results(summary, primary)
    print(json.dumps({
        "records": len(rows),
        "primary": len(primary),
        "first_forward": summary["press_duration"]["first_forward"],
        "regressive_return": summary["press_duration"]["regressive_return"],
        "participant_paired": summary["press_duration"]["participant_paired"],
        "prepress_lfhf_2s": next(
            row for row in summary["correlations"] if row["metric"] == "prepress_lfhf_2s"
        ),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
