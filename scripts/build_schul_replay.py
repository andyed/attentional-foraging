#!/usr/bin/env python3
"""Stage one Schultheiß & Lewandowski 2019 trial for the HTML replay app.

By default, slices the session down to just the (participant × stimulus) window
using Data.xml <SceneFragment> boundaries — a typical slice is 10-20 s out of a
~170 s session.

Pass --no-slice to stage the whole block instead.

For the chosen (participant, stimulus), extracts:
  - RawGaze samples within the fragment → gaze.json (list of [t_ms, x, y])
  - matching WMV sliced on the fragment window → trial.mp4 (H.264)
  - the reference SERP PNG → reference.png
  - AOI polygons for that stimulus from ImageMaps_*.txt → aois.json
  - meta.json with widths, heights, durations, AND the full session timeline

Output goes into docs/schul-replay/data/ — git-ignored (big binaries).

Usage:
  python3 scripts/build_schul_replay.py \\
      --zip /path/to/M1_Students.zip \\
      --participant 1042 \\
      --q Q05_M \\
      --imagemaps /path/to/unzipped/Mobile_Block1/ImageMaps_Mobile_Block1.txt \\
      --refpng    /path/to/unzipped/Mobile_Block1/Q05_Mobile.png
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

# same directory as this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schul_fragments  # noqa: E402


def block_suffix_from_q(q: str) -> str:
    """Q05_M → 'm1' (mobile block 1). Blocks: M1 has Q01-Q10 in M_Block1, M2 has Q11-Q20 in M_Block2."""
    m = re.match(r"Q(\d+)_([MD])", q)
    if not m:
        raise ValueError(f"cannot derive block suffix from {q}")
    qn = int(m.group(1)); dev = m.group(2).lower()
    block = 1 if qn <= 10 else 2
    return f"{dev}{block}"


def _last_aoi(hits: dict) -> str | None:
    """Return the last AOI the participant dwelled on (for sanity checks)."""
    visits = hits.get("summary", {}).get("visit_log", [])
    return visits[-1]["aoi_id"] if visits else None


def lookup_click(clicks_dir: str, external_code: str, q_label: str) -> str | None:
    """Find the click AOI for (external_code × q_label) in the Clicks CSVs.

    Filename pattern: '{code}_{block_suffix}_tasks.csv'. Aufgabe N maps to Q0N_M
    (tested by duration fingerprint — the iMotions ID ↔ external code mapping
    cross-validates this assumption).
    """
    m = re.match(r"Q(\d+)_[MD]", q_label)
    if not m:
        return None
    aufgabe = int(m.group(1)) % 100  # Q11 → 11, Q15 → 15 on M_Block2
    suffix = block_suffix_from_q(q_label)
    # Try both case variants since filenames mix 'P07' and 'p07'
    for variant in (external_code, external_code.lower(), external_code.upper()):
        candidate = os.path.join(clicks_dir, f"{variant}_{suffix}_tasks.csv")
        if os.path.exists(candidate):
            with open(candidate) as f:
                for row in f.read().splitlines()[1:]:
                    parts = row.strip().split("\t")
                    if len(parts) >= 2 and parts[0].strip().isdigit() and int(parts[0]) == aufgabe:
                        return parts[1].strip()
    return None


def find_gaze_path(z: zipfile.ZipFile, q: str, participant: str) -> str:
    """Q05_M + participant 1042 → the exact internal zip entry for RawGaze."""
    needle = f"{q}\\Gaze\\RawGaze.{participant}.csv"
    for n in z.namelist():
        if n.endswith(needle):
            return n
    raise SystemExit(f"no RawGaze entry for {q} / participant {participant}")


def parse_rawgaze(blob: bytes):
    text = blob.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # first line is a path header (e.g. C:\...\Stimuli\D1_Scene[1].jpg)
    samples = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            t = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])
        except ValueError:
            continue
        samples.append([t, x, y])
    return samples


def find_wmv_by_duration(z: zipfile.ZipFile, participant: str, target_ms: int, tolerance_ms: int = 500):
    """Find the WMV for participant whose duration best matches target_ms.

    We don't have a direct stimulus-ID map without Data.xml, so we extract each
    participant-specific WMV to a temp file, ffprobe for duration, and pick
    the one within tolerance.
    """
    wmvs = [n for n in z.namelist()
            if n.endswith(".wmv") and f"sc_r{int(participant):06d}__" in n]
    if not wmvs:
        raise SystemExit(f"no WMVs for participant {participant}")
    best = None
    for n in wmvs:
        size = z.getinfo(n).file_size
        with tempfile.NamedTemporaryFile(suffix=".wmv", delete=False) as tf:
            tf_path = tf.name
        try:
            with z.open(n) as src, open(tf_path, "wb") as dst:
                dst.write(src.read())
            dur_ms = ffprobe_duration_ms(tf_path)
        finally:
            os.unlink(tf_path)
        if dur_ms is None:
            continue
        diff = abs(dur_ms - target_ms)
        print(f"  candidate {os.path.basename(n)} dur={dur_ms}ms diff={diff}ms size={size:,}")
        if best is None or diff < best[1]:
            best = (n, diff, dur_ms)
    if best is None or best[1] > tolerance_ms:
        raise SystemExit(f"no WMV within {tolerance_ms}ms of {target_ms}ms (best diff={best[1] if best else None})")
    print(f"  matched WMV: {best[0]} (diff {best[1]}ms)")
    return best[0]


def ffprobe_duration_ms(path: str):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return int(float(out) * 1000)
    except Exception as e:
        print(f"  ffprobe failed on {path}: {e}", file=sys.stderr)
        return None


def ffprobe_wh(path: str):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration,r_frame_rate,nb_read_frames",
         "-count_frames",
         "-of", "json", path],
    ).decode()
    data = json.loads(out)["streams"][0]
    return data


def transcode_to_mp4(wmv_path: str, mp4_path: str,
                     t_start_ms: int | None = None, t_end_ms: int | None = None):
    """Transcode WMV → MP4. Optionally slice to [t_start_ms, t_end_ms].

    Output-side -ss/-t gives frame-accurate slicing (input-side is keyframe-
    only). We put -ss/-t after -i so slicing is accurate.
    """
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", wmv_path]
    if t_start_ms is not None:
        cmd += ["-ss", f"{t_start_ms/1000:.3f}"]
    if t_start_ms is not None and t_end_ms is not None:
        cmd += ["-t", f"{(t_end_ms - t_start_ms)/1000:.3f}"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-an",
        "-movflags", "+faststart",
        mp4_path,
    ]
    print(f"  transcoding: ffmpeg ... (slice {t_start_ms}..{t_end_ms} ms)" if t_start_ms is not None
          else "  transcoding: ffmpeg ... (full)")
    subprocess.check_call(cmd)


def parse_imagemap(txt_path: str, q_label: str):
    """Pull the <map> block for the given stimulus and return list of AOI rects.

    q_label examples: 'Q05_Mobile', 'Q01_Desktop', etc.
    Returns [{id, x1, y1, x2, y2}, ...]
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Find the section header like "Q05_Mobile:"
    pattern = rf"{re.escape(q_label)}:\s*\n(.+?)(?=\n[A-Z][A-Za-z0-9_]+:|$)"
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        raise SystemExit(f"no section {q_label!r} in {txt_path}")
    block = m.group(1)
    aois = []
    for am in re.finditer(r'<area[^>]+id="([^"]+)"[^>]+coords="([^"]+)"', block):
        aoi_id = am.group(1)
        coords = [int(c.strip()) for c in am.group(2).split(",")]
        if len(coords) != 4:
            continue
        x1, y1, x2, y2 = coords
        aois.append({"id": aoi_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    return aois


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="path to M1_Students.zip / D1_Students.zip / etc")
    ap.add_argument("--participant", required=True, help="e.g. 1042")
    ap.add_argument("--q", required=True, help="e.g. Q05_M or Q01_D (matches folder name in zip)")
    ap.add_argument("--imagemaps", required=True, help="path to ImageMaps_*.txt (unzipped)")
    ap.add_argument("--refpng", required=True, help="path to Qxx_{Mobile,Desktop}.png (unzipped)")
    ap.add_argument("--out", default=None, help="output directory (default: docs/schul-replay/data or trials/<name> if --name given)")
    ap.add_argument("--name", default=None, help="short label for this trial — stages into docs/schul-replay/trials/<name>/ and registers in trials.json")
    ap.add_argument("--no-slice", action="store_true",
                    help="stage the whole block instead of slicing to the stimulus fragment")
    ap.add_argument("--xlsx", default=None,
                    help="path to 'AOI metrics.xlsx' for iMotions ID ↔ external code mapping (enables click overlay)")
    ap.add_argument("--clicks-dir", default=None,
                    help="path to Clicks/ dir (unzipped) for per-trial click lookup")
    args = ap.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if args.out:
        out_dir = args.out
    elif args.name:
        out_dir = os.path.join(repo_root, "docs", "schul-replay", "trials", args.name)
    else:
        out_dir = os.path.join(repo_root, "docs", "schul-replay", "data")
    os.makedirs(out_dir, exist_ok=True)

    print(f"zip:         {args.zip}")
    print(f"participant: {args.participant}")
    print(f"stimulus:    {args.q}")
    print(f"output dir:  {out_dir}")

    z = zipfile.ZipFile(args.zip)

    # 0) Resolve the slice window from Data.xml fragments
    timeline = schul_fragments.build_session_timeline(args.zip, int(args.participant))
    if not timeline:
        raise SystemExit(f"no fragments found for respondent {args.participant} in Data.xml")
    print(f"\nsession timeline ({len(timeline)} stimuli):")
    for f in timeline:
        marker = "  *" if f["q_label"] == args.q else "   "
        print(f"{marker} {f['q_label']:>8}  [{f['t_start_ms']:>6} .. {f['t_end_ms']:>6}]  dur {f['duration_ms']:>5}ms")

    slice_window = None
    if not args.no_slice:
        try:
            frag, stim = schul_fragments.find_fragment(
                args.zip, int(args.participant), args.q)
        except LookupError as e:
            print(f"\nERROR: {e}")
            print("Pass --no-slice to stage the whole session anyway.")
            sys.exit(1)
        slice_window = (frag.t_start_ms, frag.t_end_ms)
        print(f"\nslicing to {args.q}: [{frag.t_start_ms}..{frag.t_end_ms}] "
              f"= {frag.duration_ms}ms")

    # 1) Gaze (whole session first, then filter if slicing)
    gaze_entry = find_gaze_path(z, args.q, args.participant)
    print(f"\ngaze entry: {gaze_entry}")
    full_samples = parse_rawgaze(z.read(gaze_entry))
    session_duration_ms = max(s[0] for s in full_samples) if full_samples else 0

    if slice_window is not None:
        t0, t1 = slice_window
        samples = [[s[0] - t0, s[1], s[2]] for s in full_samples if t0 <= s[0] <= t1]
    else:
        samples = full_samples

    valid = [s for s in samples if s[1] != -1 and s[2] != -1]
    duration_ms = max(s[0] for s in samples) if samples else 0
    print(f"  total session: {len(full_samples)} samples, {session_duration_ms}ms")
    print(f"  in slice:      {len(samples)} samples, {len(valid)} valid, {duration_ms}ms")
    with open(os.path.join(out_dir, "gaze.json"), "w") as f:
        json.dump(samples, f)

    # 2) WMV → MP4  (resolve WMV by session-level duration match, then slice)
    wmv_entry = find_wmv_by_duration(z, args.participant, session_duration_ms)
    with tempfile.NamedTemporaryFile(suffix=".wmv", delete=False) as tf:
        tf_path = tf.name
    try:
        with z.open(wmv_entry) as src, open(tf_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        mp4_path = os.path.join(out_dir, "trial.mp4")
        if slice_window is not None:
            transcode_to_mp4(tf_path, mp4_path, slice_window[0], slice_window[1])
        else:
            transcode_to_mp4(tf_path, mp4_path)
        stream = ffprobe_wh(mp4_path)
    finally:
        os.unlink(tf_path)
    print(f"  mp4: {mp4_path}  {stream['width']}x{stream['height']}  "
          f"{float(stream.get('duration', 0)):.1f}s")

    # 3) Reference PNG
    shutil.copy2(args.refpng, os.path.join(out_dir, "reference.png"))

    # 4) AOIs
    q_label = args.q.replace("_M", "_Mobile").replace("_D", "_Desktop")
    aois = parse_imagemap(args.imagemaps, q_label)
    with open(os.path.join(out_dir, "aois.json"), "w") as f:
        json.dump(aois, f, indent=2)
    print(f"  AOIs: {len(aois)}")

    # 5) Reported-choice resolution (optional, needs xlsx + clicks-dir)
    #
    # NB: Clicks.zip is most likely POST-SESSION reported preference rather than
    # an in-session tap — verified against 5 pilot trials where the "clicked"
    # AOI was not in the final viewport for 3 of them. Treat this as the
    # participant's recorded choice for the task, not as an eye/finger landing.
    click_info = None
    if args.xlsx and args.clicks_dir:
        import schul_code_mapping
        mapping_results = schul_code_mapping.build_mapping(args.zip, args.xlsx)
        mr = mapping_results.get(int(args.participant))
        if mr and mr.external_code:
            margin_s = (mr.second_best_gap_ms - mr.total_abs_gap_ms) / 1000
            reported_aoi = lookup_click(args.clicks_dir, mr.external_code, args.q)
            click_info = {
                "external_code": mr.external_code,
                "reported_aoi": reported_aoi,
                # kept for back-compat; same value as reported_aoi
                "clicked_aoi": reported_aoi,
                "semantics": "post_session_reported_choice",
                "mapping_total_abs_gap_ms": mr.total_abs_gap_ms,
                "mapping_margin_ms": mr.second_best_gap_ms - mr.total_abs_gap_ms,
                "mapping_confidence": "high" if margin_s >= 2 else ("medium" if margin_s >= 0.5 else "low"),
                "mapping_shared_qs": mr.shared_q_count,
            }
            print(f"\nchoice mapping: iMotions {args.participant} → external {mr.external_code} "
                  f"(margin {margin_s:.1f}s, conf={click_info['mapping_confidence']}) · "
                  f"reported AOI on {args.q} = {reported_aoi!r}")
        else:
            print("\nchoice mapping: no valid external-code match found for this participant")

    # 6a) Scroll recovery (on the sliced/full trial MP4)
    print("\nrunning scroll recovery …")
    import schul_scroll_recovery
    scroll_samples, scroll_meta = schul_scroll_recovery.recover(
        mp4_path, args.refpng, smooth_window=5)
    scroll_path = os.path.join(out_dir, "scroll.json")
    with open(scroll_path, "w") as f:
        json.dump({"meta": scroll_meta, "samples": scroll_samples}, f)
    print(f"  wrote {len(scroll_samples)} scroll samples, y range {scroll_meta['y_offset_range_px']}, "
          f"score range {scroll_meta['match_score_range']}")

    # 7) Meta (first draft — we need it before AOI hits so they can read scroll geometry)
    meta = {
        "participant": args.participant,
        "stimulus": args.q,
        "q_label": q_label,
        "sliced": slice_window is not None,
        "slice_window_ms": list(slice_window) if slice_window else None,
        "session_duration_ms": session_duration_ms,
        "session_timeline": timeline,
        "click": click_info,
        "scroll_recovery": {
            "phone_crop_bounds": scroll_meta["crop_bounds"],
            "scale_crop_to_ref": scroll_meta["scale_crop_to_ref"],
            "reference_size_px": scroll_meta["reference_size_px"],
            "n_samples": scroll_meta["n_frames"],
            "match_score_range": scroll_meta["match_score_range"],
        },
        "gaze_samples_total": len(samples),
        "gaze_samples_valid": len(valid),
        "gaze_duration_ms": duration_ms,
        "video": {
            "width": stream["width"],
            "height": stream["height"],
            "duration_s": float(stream.get("duration", 0)),
            "frame_rate": stream.get("r_frame_rate"),
            "nb_read_frames": stream.get("nb_read_frames"),
        },
        "gaze_coord_space": "screen (WMV-native)",
        "aoi_coord_space": "page (reference PNG)",
        "notes": (
            "Stimulus segment resolved from Data.xml <SceneFragment>. "
            "Gaze and video are sliced to the fragment window by default "
            "(pass --no-slice to build_schul_replay.py for the whole session). "
            "Gaze is in WMV screen coords. AOI polygons are in page coords of "
            "reference.png; scroll-offset recovery still required to project "
            "gaze onto the reference image."
        ),
        "source_zip": os.path.basename(args.zip),
        "source_wmv_entry": wmv_entry,
        "source_gaze_entry": gaze_entry,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # 8) AOI-hit computation — projects 60 Hz gaze → page coords, point-in-polygon
    print("\ncomputing AOI hits …")
    import schul_aoi_hits
    hits = schul_aoi_hits.compute(meta, samples, scroll_samples, aois, min_visit_ms=100)
    with open(os.path.join(out_dir, "aoi_hits.json"), "w") as f:
        json.dump(hits, f)
    hm = hits["meta"]
    print(f"  {hm['n_samples']} samples, {hm['total_in_aoi_ms']}ms in AOIs across {hm['n_visits']} visits")
    top = sorted(((aid, e) for aid, e in hits["summary"]["per_aoi"].items() if e["visits"] > 0),
                 key=lambda x: -x[1]["dwell_ms"])[:5]
    for aid, e in top:
        print(f"    {aid:>6}  dwell {e['dwell_ms']:>4}ms  visits {e['visits']}")

    # Diagnostics: reported-choice vs final scroll sanity
    warnings = []
    if click_info and click_info.get("reported_aoi"):
        reported_id = click_info["reported_aoi"]
        aoi = next((a for a in aois if a["id"] == reported_id), None)
        if aoi and scroll_samples:
            final = scroll_samples[-1]
            vp_y0 = final["y_offset_px"]
            vp_h = int((scroll_meta["crop_bounds"][3] - scroll_meta["crop_bounds"][1])
                       * scroll_meta["scale_crop_to_ref"])
            vp_y1 = vp_y0 + vp_h
            reported_visible = aoi["y1"] < vp_y1 and aoi["y2"] > vp_y0
            click_info["reported_aoi_visible_at_end"] = reported_visible
            if not reported_visible:
                warnings.append(
                    f"reported AOI {reported_id} (page y=[{aoi['y1']},{aoi['y2']}]) "
                    f"is NOT in the final viewport (y=[{vp_y0},{vp_y1}]). "
                    "Consistent with post-session reported-choice semantics; not a pipeline bug."
                )
        click_info["session_ended_on_same_aoi"] = (
            aoi_hits_last_aoi == click_info["reported_aoi"]
            if (aoi_hits_last_aoi := _last_aoi(hits)) else False
        )

    # Diagnostics: scroll confidence summary
    lc = sum(1 for s in scroll_samples if s["confidence"] == "low")
    mc = sum(1 for s in scroll_samples if s["confidence"] == "medium")
    hc = sum(1 for s in scroll_samples if s["confidence"] == "high")
    total = len(scroll_samples) or 1
    scroll_conf_summary = {
        "high_frac": round(hc / total, 3),
        "medium_frac": round(mc / total, 3),
        "low_frac": round(lc / total, 3),
    }
    if scroll_conf_summary["low_frac"] > 0.4:
        warnings.append(
            f"{scroll_conf_summary['low_frac']*100:.0f}% of frames are low-confidence scroll "
            f"(match score < 0.15). DP path likely unreliable in those regions."
        )
    if warnings:
        print("\n⚠ warnings:")
        for w in warnings:
            print(f"  - {w}")

    meta["warnings"] = warnings
    meta["scroll_confidence_summary"] = scroll_conf_summary
    # Re-write meta with diagnostics
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # Register in trials.json if --name given
    if args.name:
        trials_root = os.path.join(repo_root, "docs", "schul-replay", "trials")
        manifest = os.path.join(trials_root, "trials.json")
        entries = []
        if os.path.exists(manifest):
            entries = json.load(open(manifest))
            entries = [e for e in entries if e.get("name") != args.name]
        entries.append({
            "name": args.name,
            "participant": args.participant,
            "q_label": q_label,
            "duration_ms": duration_ms,
            "gaze_valid": len(valid),
            "gaze_total": len(samples),
            "reported_aoi": click_info["reported_aoi"] if click_info else None,
            "reported_aoi_visible_at_end": click_info.get("reported_aoi_visible_at_end") if click_info else None,
            "external_code": click_info["external_code"] if click_info else None,
            "total_in_aoi_ms": hm["total_in_aoi_ms"],
            "n_visits": hm["n_visits"],
            "top_aoi": top[0][0] if top else None,
            "scroll_low_conf_frac": scroll_conf_summary["low_frac"],
            "n_warnings": len(warnings),
        })
        entries.sort(key=lambda e: (e["participant"], e["q_label"]))
        with open(manifest, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"\nregistered in {manifest}")

    print(f"\nopen docs/schul-replay/index.html to view.")


if __name__ == "__main__":
    main()
