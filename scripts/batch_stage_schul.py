"""Batch-stage every (participant × stimulus) pair in a Schul session zip.

Iterates `build_schul_replay.py` over all SceneFragments. Writes a CSV summary
log with duration / warnings / reported-choice visibility / low-conf fraction
per trial, so failures (and DP-stuck cases) are easy to triage afterwards.

Usage:
  python3 scripts/batch_stage_schul.py \\
      --zip /Volumes/andyed/Downloads/schultheiss-lewandowski-2019/M1_Students.zip \\
      --imagemaps ".../Mobile_Block1/ImageMaps_Mobile_Block1.txt" \\
      --refpng-dir ".../Mobile_Block1" \\
      --xlsx  ".../AOI metrics.xlsx" \\
      --clicks-dir ".../Clicks"
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schul_fragments  # noqa: E402


def q_to_refpng(q_label: str, refpng_dir: str) -> str:
    # Q05_M -> Q05_Mobile.png, Q07_D -> Q07_Desktop.png
    qn, dev = q_label.split("_")
    suffix = "Mobile" if dev == "M" else "Desktop"
    return os.path.join(refpng_dir, f"{qn}_{suffix}.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--imagemaps", required=True)
    ap.add_argument("--refpng-dir", required=True)
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--clicks-dir", default=None)
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N trials (for smoke-tests)")
    ap.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True,
                    help="skip trials whose output dir already has meta.json (default: skip)")
    ap.add_argument("--log", default=None,
                    help="CSV log path (default: docs/schul-replay/trials/batch_log.csv)")
    args = ap.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    trials_root = os.path.join(repo_root, "docs", "schul-replay", "trials")
    log_path = args.log or os.path.join(trials_root, "batch_log.csv")

    xml = schul_fragments.read_data_xml(args.zip)
    stimuli = schul_fragments.parse_stimuli(xml)
    frags = schul_fragments.parse_fragments(xml)

    # Filter to stimuli with Q-labels (drop block container)
    q_ids = {sid: s.name for sid, s in stimuli.items() if s.name.startswith("Q")}
    pairs = [
        (f.respondent_id, q_ids[f.stim_id])
        for f in frags
        if f.stim_id in q_ids
    ]
    pairs.sort()

    print(f"found {len(pairs)} (participant × stimulus) fragments across "
          f"{len(set(p for p, _ in pairs))} participants", file=sys.stderr)

    log_rows: list[dict] = []
    start = time.time()
    for i, (pid, q) in enumerate(pairs):
        if args.limit and i >= args.limit:
            break

        name = f"{pid}_{q.split('_')[0]}"
        out_dir = os.path.join(trials_root, name)
        meta_path = os.path.join(out_dir, "meta.json")

        if args.skip_existing and os.path.exists(meta_path):
            print(f"[{i+1}/{len(pairs)}] {name}: skip (exists)", file=sys.stderr)
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                log_rows.append(_row_from_meta(name, pid, q, "skipped", meta))
            except Exception:
                pass
            continue

        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_schul_replay.py"),
            "--zip", args.zip,
            "--participant", str(pid),
            "--q", q,
            "--imagemaps", args.imagemaps,
            "--refpng", q_to_refpng(q, args.refpng_dir),
            "--name", name,
        ]
        if args.xlsx:
            cmd += ["--xlsx", args.xlsx]
        if args.clicks_dir:
            cmd += ["--clicks-dir", args.clicks_dir]

        t0 = time.time()
        print(f"[{i+1}/{len(pairs)}] {name}: staging ...", file=sys.stderr)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
            dt = time.time() - t0
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                log_rows.append(_row_from_meta(name, pid, q, f"ok ({dt:.0f}s)", meta))
                print(f"  → ok in {dt:.0f}s", file=sys.stderr)
            else:
                log_rows.append({"name": name, "pid": pid, "q": q,
                                 "status": "no-meta", "duration_s": dt})
                print(f"  → ran but no meta.json", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            dt = time.time() - t0
            log_rows.append({"name": name, "pid": pid, "q": q,
                             "status": f"error: {e.stderr.strip().splitlines()[-1][:80]}" if e.stderr else "error",
                             "duration_s": dt})
            print(f"  → error: {e.stderr.strip().splitlines()[-1][:120] if e.stderr else e}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            log_rows.append({"name": name, "pid": pid, "q": q, "status": "timeout", "duration_s": 300})
            print(f"  → timeout (>300s)", file=sys.stderr)

        # Flush log after each trial for resumability / monitoring
        _write_log(log_path, log_rows)

    elapsed = time.time() - start
    print(f"\ndone in {elapsed/60:.1f}min. log: {log_path}", file=sys.stderr)


def _row_from_meta(name: str, pid: int, q: str, status: str, meta: dict) -> dict:
    scroll = meta.get("scroll_confidence_summary", {}) or {}
    return {
        "name": name,
        "pid": pid,
        "q": q,
        "status": status,
        "duration_ms": meta.get("duration_ms") or meta.get("fragment_duration_ms"),
        "gaze_valid": meta.get("gaze_valid"),
        "gaze_total": meta.get("gaze_total"),
        "total_in_aoi_ms": meta.get("total_in_aoi_ms"),
        "n_visits": meta.get("n_visits"),
        "top_aoi": meta.get("top_aoi"),
        "reported_aoi": meta.get("reported_aoi"),
        "reported_aoi_visible_at_end": meta.get("reported_aoi_visible_at_end"),
        "external_code": meta.get("external_code"),
        "scroll_low_conf_frac": meta.get("scroll_low_conf_frac") or scroll.get("low_frac"),
        "n_warnings": meta.get("n_warnings"),
    }


def _write_log(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Union of all keys, preserving the canonical order from the first row
    keys: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    main()
