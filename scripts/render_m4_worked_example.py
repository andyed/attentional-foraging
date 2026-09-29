#!/usr/bin/env python3
"""Render one empirical M4 cursor-to-AOI trace for the manuscript.

The figure uses the same typed AOI, press-anchored 500 ms cutoff, native
``mousemove`` stream, and JavaScript ``ResultFeatureTracker`` as the §4.1
producer. It verifies the seven displayed values against the pinned per-record
feature cache before writing any output.

This is deliberately an AOI-observer trace, not a synthetic enter/exit
episode: the reported M4 classifier updates every AOI from every retained
cursor sample in the click-buffered trial.

Run from the attentional-foraging repository:

    .venv/bin/python scripts/render_m4_worked_example.py

Outputs:

    scripts/output/m4_worked_example/m4_worked_example.{pdf,svg,png}
    scripts/output/m4_worked_example/m4_worked_example.meta.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT.parent / "approach-retreat" / "src" / "approach-retreat.js"
BRIDGE = ROOT / "scripts" / "m4_cursor_tracker.mjs"
CACHE = ROOT / "AdSERP" / "data" / "cursor-only-typed-features-mousedown.json"
OUT_DIR = ROOT / "scripts" / "output" / "m4_worked_example"

DEFAULT_TRIAL = "p047-b6-t5"
DEFAULT_BUFFER_MS = 500

# Caption-first contract: this text is copied into the manuscript verbatim.
CAPTION = (
    "Worked M4 example from one empirical AdSERP trial (p047-b6-t5, clicked "
    "organic rank 2). Each point is a native mousemove retained before the "
    "press-anchored 500 ms cutoff; d(t) is vertical cursor distance to that "
    "AOI's center. The top panel shows the 100 px proximity zone, the sample "
    "mean and minimum, and the three signed-velocity direction changes. The "
    "bottom panel shows the guarded signed velocity used by the accumulator "
    "(positive means approach). The table reports the exact seven-feature "
    "vector emitted by ResultFeatureTracker. The observer spans the retained "
    "trial stream; it is not cropped to a DOM enter/exit interval."
)

# White-paper palette. Text colors exceed 8:1 contrast against white.
INK = "#0A0A0F"
COMMIT = "#2E5180"
DECIDE = "#7A3618"
VACIL = "#5C2E66"
GRID = "#D2D2D8"
BUFFER = "#ECECF0"

FEATURES = [
    "min_dist",
    "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity",
    "max_approach_velocity",
    "direction_changes",
    "frac_decreasing",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit(path: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()


def contrast_ratio(foreground: str, background: str = "#FFFFFF") -> float:
    def channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def luminance(color: str) -> float:
        rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
        r, g, b = (channel(v) for v in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    a, b = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def load_m4_module():
    spec = importlib.util.spec_from_file_location(
        "m4_cursor_aoi_rerun", ROOT / "scripts" / "m4_cursor_aoi_rerun.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load m4_cursor_aoi_rerun.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tracked_trial(trial_id: str, buffer_ms: int):
    sys.path.insert(0, str(ROOT / "notebooks-v2"))
    import data_loader as dl

    m4 = load_m4_module()
    cards = m4.load_flavor_cards(dl, trial_id, "typed")
    geometry = dl.get_trial_geometry(trial_id)
    events, _scrolls, clicks = dl.load_mouse_events(trial_id, space="document")
    trial, reason = m4.prepare_trial(
        trial_id,
        cards,
        events,
        clicks,
        geometry,
        [buffer_ms],
        anchor="mousedown",
    )
    if trial is None:
        raise RuntimeError(f"{trial_id} is not eligible: {reason}")

    condition = f"buf{buffer_ms}"
    rows = m4.track_batch([trial], BRIDGE, TRACKER)[0][condition]
    clicked = [row for row in rows if row["was_clicked"]]
    if len(clicked) != 1:
        raise RuntimeError("Expected exactly one clicked AOI row")
    row = clicked[0]
    aoi = next(a for a in trial["aois"] if a["position"] == row["position"])
    retained = [
        (float(t), float(y))
        for t, y in trial["samples"]
        if t < trial["anchor_t"] - buffer_ms
    ]
    return dl, m4, trial, aoi, row, retained


def exact_series(samples: list[tuple[float, float]], center_y: float):
    """Reproduce ResultFeatureTracker's transition series for visual proof."""
    times: list[float] = []
    distances: list[float] = []
    velocities: list[float] = []
    velocity_times: list[float] = []
    change_indices: list[int] = []

    last_t = None
    final_dist = 0.0
    last_sign = None
    for t, y in samples:
        dist = abs(y - center_y)
        if last_t is None:
            times.append(t)
            distances.append(dist)
            last_t = t
            final_dist = dist
            continue
        delta_t = t - last_t
        if delta_t <= 0:
            final_dist = dist
            continue
        dt_vel = max(delta_t, 8.0)
        raw_velocity = (-(dist - final_dist) / dt_vel) * 1000.0
        velocity = max(-5000.0, min(5000.0, raw_velocity))
        sign = 1 if velocity > 0 else -1 if velocity < 0 else 0
        if last_sign is not None and sign != last_sign:
            change_indices.append(len(times))
        last_sign = sign
        velocity_times.append(t)
        velocities.append(velocity)
        times.append(t)
        distances.append(dist)
        last_t = t
        final_dist = dist

    return {
        "times": np.asarray(times, dtype=float),
        "distances": np.asarray(distances, dtype=float),
        "velocity_times": np.asarray(velocity_times, dtype=float),
        "velocities": np.asarray(velocities, dtype=float),
        "change_indices": change_indices,
    }


def pinned_cache_row(trial_id: str, position: int, buffer_ms: int) -> dict:
    payload = json.loads(CACHE.read_text())
    if payload["anchor_event"] != "mousedown" or payload["sampling"] != "native":
        raise RuntimeError("Pinned feature cache uses an unexpected protocol")
    rows = payload["conditions"][f"buf{buffer_ms}"]
    matches = [
        row
        for row in rows
        if row["trial_id"] == trial_id and int(row["position"]) == position
    ]
    if len(matches) != 1:
        raise RuntimeError("Pinned feature cache does not contain one matching row")
    return matches[0]


def assert_feature_match(actual: dict, expected: dict) -> None:
    for feature in FEATURES:
        if not np.isclose(float(actual[feature]), float(expected[feature]), rtol=0, atol=1e-9):
            raise AssertionError(
                f"{feature} drifted: tracker={actual[feature]!r}, cache={expected[feature]!r}"
            )


def format_feature(feature: str, value: float) -> str:
    if feature in {"min_dist", "mean_dist"}:
        return f"{value:.1f} px"
    if feature == "dwell_in_proximity_ms":
        return f"{value:.0f} ms"
    if feature in {"mean_approach_velocity", "max_approach_velocity"}:
        return f"{value:.1f} px/s"
    if feature == "direction_changes":
        return f"{int(value)}"
    return f"{value:.3f}"


def render_figure(
    trial: dict,
    aoi: dict,
    row: dict,
    series: dict,
    buffer_ms: int,
    output_dir: Path,
) -> dict[str, Path]:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "font.weight": "regular",
            "axes.titlesize": 9.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 8.5,
            "axes.labelweight": "regular",
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "grid.alpha": 1.0,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    fig = plt.figure(figsize=(7.15, 3.35), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, width_ratios=(1.80, 1.45), height_ratios=(1.45, 1.0))
    ax_dist = fig.add_subplot(grid[0, 0])
    ax_vel = fig.add_subplot(grid[1, 0], sharex=ax_dist)
    ax_table = fig.add_subplot(grid[:, 1])

    x = (series["times"] - trial["anchor_t"]) / 1000.0
    x_velocity = (series["velocity_times"] - trial["anchor_t"]) / 1000.0
    distances = series["distances"]
    velocities = series["velocities"]
    cutoff_s = -buffer_ms / 1000.0

    x_left = min(float(x.min()) - 0.05, -1.05)
    x_right = 0.04
    for axis in (ax_dist, ax_vel):
        axis.axvspan(cutoff_s, 0, color=BUFFER, zorder=0)
        axis.axvline(cutoff_s, color=INK, linestyle=(0, (4, 3)), linewidth=0.9)
        axis.set_xlim(x_left, x_right)
        axis.grid(axis="y")

    ax_dist.axhspan(0, 100, color=COMMIT, alpha=0.10, zorder=0)
    ax_dist.plot(x, distances, color=INK, linewidth=1.4, marker="o", markersize=2.5)
    in_proximity = distances < 100
    ax_dist.scatter(
        x[in_proximity], distances[in_proximity], s=12, color=COMMIT, zorder=4,
        label="sample inside 100 px",
    )
    ax_dist.axhline(
        row["mean_dist"], color=COMMIT, linestyle=(0, (2, 2)), linewidth=1.0,
        label=f"mean = {row['mean_dist']:.1f} px",
    )
    min_index = int(np.argmin(distances))
    ax_dist.scatter(
        [x[min_index]], [distances[min_index]], marker="D", s=26,
        color=COMMIT, edgecolor="white", linewidth=0.7, zorder=5,
    )
    ax_dist.annotate(
        f"min = {row['min_dist']:.1f} px",
        xy=(x[min_index], distances[min_index]),
        xytext=(8, 18),
        textcoords="offset points",
        color=COMMIT,
        arrowprops={"arrowstyle": "-", "color": COMMIT, "linewidth": 0.8},
    )
    for index in series["change_indices"]:
        ax_dist.scatter(
            [x[index]], [distances[index]], marker="s", s=22,
            facecolor="white", edgecolor=VACIL, linewidth=1.1, zorder=5,
        )
    ax_dist.text(
        cutoff_s / 2, 0.82, "500 ms input buffer",
        transform=ax_dist.get_xaxis_transform(), ha="center", va="top",
        color=INK, fontsize=8,
    )
    ax_dist.set_ylabel("Distance to AOI center d(t) (px)")
    ax_dist.set_title(
        f"A. Empirical observer trace (rank {int(row['position']) + 1} clicked; "
        f"n={int(row['sample_count'])})",
        loc="left",
    )
    ax_dist.tick_params(axis="x", labelbottom=False)
    ax_dist.legend(
        handles=[
            Line2D([], [], color=COMMIT, marker="o", linewidth=0, markersize=4,
                   label="within 100 px"),
            Line2D([], [], color=COMMIT, linestyle=(0, (2, 2)), linewidth=1,
                   label=f"mean {row['mean_dist']:.1f} px"),
            Line2D([], [], color=VACIL, marker="s", markerfacecolor="white",
                   linewidth=0, markersize=4, label="direction change"),
        ],
        loc="upper left", frameon=False, ncol=2, handlelength=1.4,
        columnspacing=0.8, borderaxespad=0.2, fontsize=7.5,
    )

    positive = velocities >= 0
    ax_vel.axhline(0, color=INK, linewidth=0.8)
    ax_vel.plot(x_velocity, velocities, color=INK, linewidth=0.7, zorder=1)
    ax_vel.scatter(x_velocity[positive], velocities[positive], s=10, color=DECIDE, zorder=2)
    ax_vel.scatter(x_velocity[~positive], velocities[~positive], s=10, color=VACIL, zorder=2)
    ax_vel.set_ylabel("Signed velocity (px/s)")
    ax_vel.set_xlabel("Time relative to mousedown (s)")
    ax_vel.set_title("B. Signed velocity (+ approach, - retreat)", loc="left")

    ax_table.set_axis_off()
    ax_table.set_xlim(0, 1)
    ax_table.set_ylim(0, 1)
    ax_table.text(0, 0.99, "C. Exact emitted feature vector", va="top", fontweight="bold", fontsize=9.5)
    ax_table.text(
        0, 0.91,
        f"{row['etype']} · native mousemove · no gaze",
        va="top",
    )
    grouped = [
        ("PROXIMITY", COMMIT, FEATURES[:3]),
        ("APPROACH RATE", DECIDE, FEATURES[3:5]),
        ("MONOTONICITY", VACIL, FEATURES[5:]),
    ]
    y = 0.80
    for heading, color, features in grouped:
        ax_table.text(0, y, heading, color=color, fontweight="bold", fontsize=8.5, va="top")
        y -= 0.052
        for feature in features:
            ax_table.text(0.02, y, feature, color=INK, family="monospace", fontsize=8, va="top")
            ax_table.text(
                0.98, y, format_feature(feature, float(row[feature])),
                color=color, fontweight="bold", fontsize=8, va="top", ha="right",
            )
            y -= 0.064
        y -= 0.024
    ax_table.text(
        0, 0.025,
        f"vertical page-space distance · 500 ms press buffer",
        va="bottom", color=INK, fontsize=8,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "pdf": output_dir / "m4_worked_example.pdf",
        "svg": output_dir / "m4_worked_example.svg",
        "png": output_dir / "m4_worked_example.png",
    }
    fig.savefig(outputs["pdf"], bbox_inches="tight", pad_inches=0.04)
    fig.savefig(outputs["svg"], bbox_inches="tight", pad_inches=0.04)
    fig.savefig(outputs["png"], dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return outputs


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-id", default=DEFAULT_TRIAL)
    parser.add_argument("--buffer-ms", type=int, default=DEFAULT_BUFFER_MS)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.buffer_ms < 0:
        raise ValueError("buffer-ms must be nonnegative")
    dl, _m4, trial, aoi, row, samples = tracked_trial(args.trial_id, args.buffer_ms)
    expected = pinned_cache_row(args.trial_id, int(row["position"]), args.buffer_ms)
    assert_feature_match(row, expected)
    series = exact_series(samples, float(aoi["center_document_y"]))

    contrasts = {name: contrast_ratio(color) for name, color in {
        "ink": INK, "proximity": COMMIT, "approach": DECIDE, "monotonicity": VACIL,
    }.items()}
    if min(contrasts.values()) < 8.0:
        raise AssertionError(f"Text palette failed 8:1 contrast: {contrasts}")
    print("effective figure size: 7.15 x 3.35 in")
    print("text contrast ratios on white:", json.dumps(contrasts, sort_keys=True))
    print("feature-cache check: exact to atol=1e-9")

    outputs = render_figure(trial, aoi, row, series, args.buffer_ms, args.output_dir)
    mouse_path = dl.MOUSE_DIR / f"{args.trial_id}.csv"
    metadata_path = dl.METADATA_DIR / f"{args.trial_id}.xml"
    aoi_path = ROOT / "data" / "aoi-typed" / f"{args.trial_id}.json"
    trace_digest = hashlib.sha256(
        json.dumps(
            [[float(t), float(y), float(abs(y - aoi["center_document_y"]))] for t, y in samples],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    metadata = {
        "schema_version": 1,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "empirical_worked_example",
        "caption": CAPTION,
        "source": {
            "dataset": "AdSERP",
            "trial_id": args.trial_id,
            "position_zero_based": int(row["position"]),
            "display_rank_one_based": int(row["position"]) + 1,
            "etype": row["etype"],
            "was_clicked": bool(row["was_clicked"]),
        },
        "protocol": {
            "aoi_flavor": "typed",
            "anchor_event": "mousedown",
            "buffer_ms": args.buffer_ms,
            "sampling": "native mousemove",
            "distance_axis": "vertical absolute page-space distance to AOI center",
            "proximity_px": 100,
            "gaze_used": False,
            "observer_window": "all retained trial samples before the press cutoff; not DOM enter/exit cropped",
        },
        "feature_vector": {feature: row[feature] for feature in FEATURES},
        "sample_count": int(row["sample_count"]),
        "first_sample_relative_to_press_ms": float(samples[0][0] - trial["anchor_t"]),
        "last_sample_relative_to_press_ms": float(samples[-1][0] - trial["anchor_t"]),
        "verification": {
            "cache_path": str(CACHE.relative_to(ROOT)),
            "cache_match": "all seven features exact to absolute tolerance 1e-9",
            "trace_sha256": trace_digest,
        },
        "provenance": {
            "attentional_foraging_commit": git_commit(ROOT),
            "approach_retreat_commit": git_commit(TRACKER.parent.parent),
            "sha256": {
                "producer": sha256(Path(__file__)),
                "m4_protocol": sha256(ROOT / "scripts" / "m4_cursor_aoi_rerun.py"),
                "bridge": sha256(BRIDGE),
                "tracker": sha256(TRACKER),
                "feature_cache": sha256(CACHE),
                "mouse_input": sha256(mouse_path),
                "metadata_input": sha256(metadata_path),
                "typed_aoi_input": sha256(aoi_path),
                **{f"output_{kind}": sha256(path) for kind, path in outputs.items()},
            },
        },
    }
    meta_path = args.output_dir / "m4_worked_example.meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    for kind, path in outputs.items():
        print(f"wrote {kind}: {path}")
    print(f"wrote metadata: {meta_path}")


if __name__ == "__main__":
    main()
