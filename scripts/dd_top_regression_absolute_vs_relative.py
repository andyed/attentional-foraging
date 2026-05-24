"""Absolute (page-location) vs relative (distance) memory model for
organic regressions.

For each J→K regression event:
  - source_pos = J     (organic position the user is leaving)
  - dest_pos = K       (organic position the user lands on)
  - size = J - K       (back-distance)
  - source_y, dest_y   (page-space pixel coords from fixation data)

Tests:
  (A) linear regression of dest_pos on source_pos
        - slope ≈ 0  → absolute landmark (destination doesn't depend on source)
        - slope ≈ +1 → relative distance (destination scales with source)
        - intermediate slope → mixed model
  (B) variance ratio σ²(dest_pos) / σ²(size)
        - < 1 → destination is more anchored (absolute)
        - > 1 → distance is more anchored (relative)
  (C) destination histogram for long regressions — is there an
      absolute attractor (e.g., "back to the top")?

Stratifies by size: short (1-2) vs mid (3) vs long (>=4).

Run:    .venv/bin/python scripts/dd_top_regression_absolute_vs_relative.py
Output: scripts/output/dd_top_regression_absolute_vs_relative/summary.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import linregress

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import load_fixations  # noqa: E402

SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"
OUT_DIR = ROOT / "scripts/output/dd_top_regression_absolute_vs_relative"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_events() -> list[dict]:
    events: list[dict] = []
    with SEQ_PATH.open() as f:
        for line in f:
            d = json.loads(line)
            states = d["states"]
            fix = load_fixations(d["trial_id"])
            if len(fix) != len(states):
                continue
            for i in range(len(states) - 1):
                a, b = states[i], states[i + 1]
                if not (a.startswith("organic_") and b.startswith("organic_")):
                    continue
                try:
                    ja, jb = int(a.split("_")[1]), int(b.split("_")[1])
                except (ValueError, IndexError):
                    continue
                if jb >= ja:
                    continue
                events.append({
                    "trial": d["trial_id"],
                    "source_pos": ja,
                    "dest_pos": jb,
                    "size": ja - jb,
                    "source_y": float(fix[i]["y"]),
                    "dest_y": float(fix[i + 1]["y"]),
                })
    return events


def summarize(label: str, recs: list[dict]) -> dict:
    if len(recs) < 5:
        return {"label": label, "n": len(recs)}
    src = np.array([r["source_pos"] for r in recs])
    dst = np.array([r["dest_pos"] for r in recs])
    sz = np.array([r["size"] for r in recs])
    sy = np.array([r["source_y"] for r in recs])
    dy = np.array([r["dest_y"] for r in recs])

    # Position-space regression
    slope_p, intercept_p, r_p, p_p, se_p = linregress(src, dst)
    # Pixel-space regression
    slope_y, intercept_y, r_y, p_y, se_y = linregress(sy, dy)

    # Destination histogram
    u, c = np.unique(dst, return_counts=True)
    dest_hist = [{"dest_pos": int(p), "count": int(cnt),
                  "pct": round(cnt / len(dst) * 100, 2)}
                 for p, cnt in zip(u, c)]

    # Top-3 concentration (positions 1-3): if absolute attractor, this is high
    top3_share = float((dst <= 3).mean())

    return {
        "label": label,
        "n": int(len(recs)),
        "source_pos": {"mean": round(float(src.mean()), 2),
                       "var": round(float(src.var()), 2),
                       "range": [int(src.min()), int(src.max())]},
        "dest_pos": {"mean": round(float(dst.mean()), 2),
                     "var": round(float(dst.var()), 2),
                     "range": [int(dst.min()), int(dst.max())]},
        "size": {"mean": round(float(sz.mean()), 2),
                 "var": round(float(sz.var()), 2),
                 "range": [int(sz.min()), int(sz.max())]},
        "cov_dest_pos": round(float(dst.std() / dst.mean()), 3),
        "cov_size": round(float(sz.std() / sz.mean()), 3),
        "regress_dest_on_source_position": {
            "slope": round(float(slope_p), 4),
            "slope_se": round(float(se_p), 4),
            "intercept": round(float(intercept_p), 3),
            "r": round(float(r_p), 4),
            "p": float(p_p),
        },
        "regress_dest_y_on_source_y_pixels": {
            "slope": round(float(slope_y), 4),
            "slope_se": round(float(se_y), 4),
            "intercept_px": round(float(intercept_y), 1),
            "r": round(float(r_y), 4),
            "p": float(p_y),
        },
        "variance_ratio_dest_over_size": round(float(dst.var() / sz.var()), 3),
        "dest_top3_concentration": round(top3_share, 4),
        "destination_histogram": dest_hist,
    }


def modal_dest_by_source(recs: list[dict], min_n: int = 5) -> list[dict]:
    by_src = defaultdict(list)
    for r in recs:
        by_src[r["source_pos"]].append(r["dest_pos"])
    rows = []
    for s in sorted(by_src):
        ds = by_src[s]
        if len(ds) < min_n:
            continue
        u, c = np.unique(ds, return_counts=True)
        rows.append({
            "source_pos": int(s),
            "n": len(ds),
            "median_dest": int(np.median(ds)),
            "modal_dest": int(u[c.argmax()]),
            "modal_share": round(float(c.max() / len(ds)), 3),
            "mean_size": round(float(np.mean([s - d for d in ds])), 3),
        })
    return rows


def main() -> int:
    events = extract_events()
    print(f"n regression events: {len(events):,}")

    GROUPS = {
        "all": events,
        "short (size 1-2)": [e for e in events if e["size"] <= 2],
        "mid (size 3)": [e for e in events if e["size"] == 3],
        "long (size >= 4)": [e for e in events if e["size"] >= 4],
    }

    out = {"counts": {k: len(v) for k, v in GROUPS.items()}}
    for label, recs in GROUPS.items():
        out[label] = summarize(label, recs)

    out["modal_dest_by_source_long"] = modal_dest_by_source(
        GROUPS["long (size >= 4)"], min_n=5)

    print()
    for label in ["short (size 1-2)", "mid (size 3)", "long (size >= 4)"]:
        s = out[label]
        print(f"=== {label} (n={s['n']}) ===")
        rp = s["regress_dest_on_source_position"]
        ry = s["regress_dest_y_on_source_y_pixels"]
        print(f"  slope dest_pos ~ source_pos:  {rp['slope']:+.3f}  (r={rp['r']:+.3f})")
        print(f"  slope dest_y_px ~ source_y_px: {ry['slope']:+.3f}  intercept {ry['intercept_px']:+.1f}px")
        print(f"  σ²(dest_pos) / σ²(size) = {s['variance_ratio_dest_over_size']:.3f}")
        print(f"  dest_pos ≤ 3 share: {s['dest_top3_concentration']*100:.1f}%")
        print()

    # Headline interpretation
    short = out["short (size 1-2)"]
    long_ = out["long (size >= 4)"]
    print("=== Interpretation ===")
    print(f"  short:  slope = {short['regress_dest_on_source_position']['slope']:+.3f}  "
          f"→ pure relative (back-by-1)")
    print(f"  long:   slope = {long_['regress_dest_on_source_position']['slope']:+.3f}  "
          f"→ mixed: relative trend (≠0) but with significant absolute drift toward top "
          f"({long_['dest_top3_concentration']*100:.0f}% land at positions 1-3)")
    print()
    print(f"  Long-regression destination histogram (the absolute-attractor signal):")
    for h in long_["destination_histogram"]:
        bar = "█" * int(h["pct"] / 1.5)
        print(f"    dest_pos {h['dest_pos']:>2}: {h['count']:>3} ({h['pct']:>4.1f}%)  {bar}")

    (OUT_DIR / "summary.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_DIR}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
