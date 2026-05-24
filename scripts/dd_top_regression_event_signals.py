"""Per-regression-event signal extraction: what's different between
short and long organic regressions?

For each organic→organic backward fixation transition in the
dd_top-topped substrate (1,581 trials, ~5,700 regression events),
extracts four event-level signals:

  saccade_dx_abs    px      |x_dest - x_source| of the regressive saccade
  saccade_dy_abs    px      |y_dest - y_source|
  saccade_mag       px      sqrt(dx² + dy²)
  saccade_horiz_frac        |dx| / (|dx| + |dy|)  (1 = pure horizontal, 0 = pure vertical)
  cursor_eye_offset px      distance from cursor position to destination gaze
                            at the destination fixation's start time
  lfhf_src                  per-position butterworth LF/HF at source organic pos
                            (from AdSERP/data/butterworth-lfhf-by-position.json;
                             null when source position had <80 valid pupil samples)
  lfhf_dst                  same at destination organic pos
  lfhf_delta                lfhf_dst - lfhf_src (positive = load increase on regression)

Then groups: short (|delta| ∈ {1, 2}), long (|delta| ≥ 4), mid (|delta| = 3).
Reports per-group median, IQR, n, and bootstrapped 95% CI on the
short-vs-long median difference; plus a permutation p-value for the
difference of medians.

Run:    .venv/bin/python scripts/dd_top_regression_event_signals.py
Output: scripts/output/dd_top_regression_event_signals/{events.jsonl, summary.json}
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_fixations, load_mouse_events  # noqa: E402

SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"
LFHF_PATH = ROOT / "AdSERP/data/butterworth-lfhf-by-position.json"
OUT_DIR = ROOT / "scripts/output/dd_top_regression_event_signals"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def lookup_lfhf(lfhf_data: dict, trial_id: str, pos: int) -> float | None:
    """Return per-position LF/HF for (trial, organic_position 1-indexed)."""
    rec = lfhf_data.get(trial_id)
    if rec is None:
        return None
    # The lfhf json stores positions with 'pos' integer; the index there
    # corresponds to the typed organic position 1-indexed in our states
    # (organic_K → pos K). The lfhf data uses pos starting at 0 for the
    # first below-fold-or-above region; we just match on 'pos' field.
    for p in rec.get("positions", []):
        if p.get("pos") == pos:
            return p.get("lfhf")
    return None


def nearest_cursor_xy(mouse_events: list[tuple], t: int) -> tuple[float, float] | None:
    """Return (x, y) of the mousemove event closest in time to t.
    Returns None if no mousemove events."""
    moves = [(et, x, y) for et, evt, x, y in mouse_events if evt == "mousemove"]
    if not moves:
        return None
    # binary search by time
    times = [m[0] for m in moves]
    idx = np.searchsorted(times, t)
    # consider idx-1 and idx
    candidates = []
    if 0 <= idx - 1 < len(moves):
        candidates.append(moves[idx - 1])
    if 0 <= idx < len(moves):
        candidates.append(moves[idx])
    if not candidates:
        return None
    best = min(candidates, key=lambda m: abs(m[0] - t))
    return float(best[1]), float(best[2])


def extract_events(trial_record: dict, lfhf_data: dict) -> list[dict]:
    """For one trial's state-sequence record, locate organic→organic
    regression transitions and emit per-event signal records."""
    trial_id = trial_record["trial_id"]
    states = trial_record["states"]
    timestamps = trial_record["timestamps_ms"]
    fixations = load_fixations(trial_id)
    if len(fixations) != len(states):
        # defensive: state assignment was 1:1 with load_fixations in the
        # extractor — this shouldn't happen, but skip the trial if it does
        return []
    mouse_data = load_mouse_events(trial_id)
    mouse_events = mouse_data[0] if mouse_data else []

    out: list[dict] = []
    for i in range(len(states) - 1):
        a, b = states[i], states[i + 1]
        if not (a.startswith("organic_") and b.startswith("organic_")):
            continue
        try:
            ja = int(a.split("_")[1])
            jb = int(b.split("_")[1])
        except (ValueError, IndexError):
            continue
        delta = jb - ja
        if delta >= 0:
            continue  # not a regression
        size = -delta

        fa, fb = fixations[i], fixations[i + 1]
        dx = fb["x"] - fa["x"]
        dy = fb["y"] - fa["y"]
        mag = float(np.hypot(dx, dy))
        denom = abs(dx) + abs(dy)
        horiz_frac = (abs(dx) / denom) if denom > 0 else 0.5

        cursor_xy = nearest_cursor_xy(mouse_events, int(fb["t"]))
        if cursor_xy is None:
            cursor_eye_offset = None
        else:
            cursor_eye_offset = float(np.hypot(cursor_xy[0] - fb["x"],
                                               cursor_xy[1] - fb["y"]))

        lfhf_src = lookup_lfhf(lfhf_data, trial_id, ja)
        lfhf_dst = lookup_lfhf(lfhf_data, trial_id, jb)
        lfhf_delta = (lfhf_dst - lfhf_src) if (lfhf_src is not None
                                               and lfhf_dst is not None) else None

        out.append({
            "trial_id": trial_id,
            "participant": trial_record["participant"],
            "source_pos": ja,
            "dest_pos": jb,
            "size": size,
            "saccade_dx_abs": abs(float(dx)),
            "saccade_dy_abs": abs(float(dy)),
            "saccade_mag": mag,
            "saccade_horiz_frac": horiz_frac,
            "cursor_eye_offset": cursor_eye_offset,
            "lfhf_src": lfhf_src,
            "lfhf_dst": lfhf_dst,
            "lfhf_delta": lfhf_delta,
            "dest_fix_duration_ms": int(fb["d"]),
        })
    return out


def summarize_by_size_group(events: list[dict], metric: str,
                             groups: dict[str, list[int]]) -> dict:
    out = {}
    for label, sizes in groups.items():
        vals = [e[metric] for e in events
                if e["size"] in sizes and e[metric] is not None]
        if not vals:
            out[label] = {"n": 0}
            continue
        a = np.array(vals, dtype=float)
        out[label] = {
            "n": len(vals),
            "median": round(float(np.median(a)), 3),
            "iqr": [round(float(np.percentile(a, 25)), 3),
                    round(float(np.percentile(a, 75)), 3)],
            "mean": round(float(a.mean()), 3),
            "sd": round(float(a.std(ddof=1)), 3) if len(a) > 1 else None,
        }
    return out


def permutation_median_diff(events: list[dict], metric: str,
                             grp_a_sizes: list[int], grp_b_sizes: list[int],
                             n_iter: int = 10000, seed: int = 0) -> dict:
    """Permutation test: difference of medians between two size groups."""
    rng = np.random.default_rng(seed)
    a = np.array([e[metric] for e in events
                  if e["size"] in grp_a_sizes and e[metric] is not None])
    b = np.array([e[metric] for e in events
                  if e["size"] in grp_b_sizes and e[metric] is not None])
    if len(a) < 5 or len(b) < 5:
        return {"n_a": len(a), "n_b": len(b), "observed_diff": None}
    obs = float(np.median(b) - np.median(a))
    pool = np.concatenate([a, b])
    n_a = len(a)
    null = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        rng.shuffle(pool)
        null[k] = np.median(pool[n_a:]) - np.median(pool[:n_a])
    p_two = float((np.abs(null) >= abs(obs)).mean())
    # 95% CI on the diff via bootstrap (paired sampling within group)
    boot = np.empty(2000, dtype=float)
    for k in range(2000):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        boot[k] = np.median(sb) - np.median(sa)
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
    return {
        "n_a": int(len(a)),
        "n_b": int(len(b)),
        "median_a": round(float(np.median(a)), 4),
        "median_b": round(float(np.median(b)), 4),
        "observed_diff_b_minus_a": round(obs, 4),
        "bootstrap_95ci": [round(float(ci_lo), 4), round(float(ci_hi), 4)],
        "permutation_p_two_sided": round(p_two, 4),
        "n_permutations": n_iter,
    }


def main() -> int:
    print(f"loading butterworth LF/HF per-position table...")
    lfhf_data = json.load(open(LFHF_PATH))
    print(f"  {len(lfhf_data)} trials")

    print(f"iterating sequence records...")
    all_events: list[dict] = []
    n_trials = 0
    with SEQ_PATH.open() as f:
        for line in f:
            d = json.loads(line)
            evs = extract_events(d, lfhf_data)
            all_events.extend(evs)
            n_trials += 1
            if n_trials % 200 == 0:
                print(f"  {n_trials} trials, {len(all_events)} regression events")
    print(f"  total: {n_trials} trials, {len(all_events)} regression events\n")

    # Write per-event JSONL
    ev_path = OUT_DIR / "events.jsonl"
    with ev_path.open("w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")

    GROUPS = {"short(1-2)": [1, 2], "mid(3)": [3], "long(>=4)": [4, 5, 6, 7, 8, 9]}

    metrics = ["saccade_mag", "saccade_dx_abs", "saccade_dy_abs",
               "saccade_horiz_frac", "cursor_eye_offset",
               "lfhf_src", "lfhf_dst", "lfhf_delta", "dest_fix_duration_ms"]

    print(f"=== Per-metric summary by size group ===\n")
    by_metric_summary = {}
    for m in metrics:
        by_metric_summary[m] = summarize_by_size_group(all_events, m, GROUPS)
        print(f"{m}:")
        for label, s in by_metric_summary[m].items():
            if s.get("n", 0) == 0:
                print(f"  {label:>14s} : n=0")
            else:
                print(f"  {label:>14s} : n={s['n']:>4}  med={s['median']:>8.3f}  "
                      f"IQR=[{s['iqr'][0]:>7.3f}, {s['iqr'][1]:>7.3f}]  "
                      f"mean={s['mean']:>8.3f}")
        print()

    print(f"=== Short(1-2) vs Long(>=4) — permutation tests + 95% bootstrap CI ===\n")
    tests = {}
    for m in metrics:
        tests[m] = permutation_median_diff(all_events, m, [1, 2], [4, 5, 6, 7, 8, 9])
        t = tests[m]
        if t.get("observed_diff_b_minus_a") is None:
            print(f"  {m}: insufficient n")
            continue
        sig = " *" if t["permutation_p_two_sided"] < 0.05 else ""
        print(f"  {m:25s} long − short = {t['observed_diff_b_minus_a']:+8.4f}  "
              f"95% CI [{t['bootstrap_95ci'][0]:+7.4f}, {t['bootstrap_95ci'][1]:+7.4f}]  "
              f"p={t['permutation_p_two_sided']:.4f}{sig}")

    summary = {
        "n_trials_processed": n_trials,
        "n_regression_events": len(all_events),
        "size_groups": GROUPS,
        "per_metric_summary": by_metric_summary,
        "short_vs_long_tests": tests,
        "notes": {
            "lfhf_coverage": "per-position LF/HF is null when the source "
                             "or destination organic position had < 80 "
                             "pupil samples (Welch window threshold). "
                             "Events with null lfhf_src or lfhf_dst are "
                             "excluded from lfhf_delta but counted for "
                             "single-end metrics.",
            "saccade_geometry": "page-space pixels. organic_K is at "
                                "increasing y as K increases, so regressive "
                                "saccades have negative dy (we abs-value here).",
            "cursor_eye_offset": "Euclidean distance at the destination "
                                 "fixation's start timestamp, cursor side "
                                 "from nearest mousemove event in time.",
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {OUT_DIR}/events.jsonl and summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
