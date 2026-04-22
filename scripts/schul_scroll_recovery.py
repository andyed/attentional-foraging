"""Recover per-frame scroll offset from a Schul session WMV/MP4.

The phone-mirror setup is a physical phone on a dark stand, recorded by a
desktop webcam. Per frame, we:
  1. Auto-detect the phone-screen bounds via brightness threshold (stable
     throughout a session because the phone is stationary).
  2. Crop out the status bar + nav-button chrome.
  3. Scale the crop to the reference PNG width.
  4. Convert to grayscale + high-pass filter (subtract local mean) to remove
     the blue color cast from the phone glass.
  5. Template-match the crop against the reference SERP PNG with normalized
     cross-correlation → argmax y gives scroll offset in page coords.

Match scores are intrinsically low (0.2-0.3) because the live Google SERP
rendered on the phone differs in ads/snippets from the static reference PNG.
Robustness comes from temporal stability: we smooth per-frame estimates with
a median filter across a sliding window.

Usage:
  python3 scripts/schul_scroll_recovery.py \\
      --video  docs/schul-replay/data/trial.mp4 \\
      --refpng docs/schul-replay/data/reference.png \\
      --out    docs/schul-replay/data/scroll.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass
class ScrollSample:
    t_ms: float           # frame timestamp (video clock)
    y_offset_px: int      # best-matching page y-offset (in reference-PNG coords)
    match_score: float    # normalized cross-correlation peak value [0..1]
    scale: float          # scale factor applied (crop_w → ref_w)


def detect_screen_bounds(frame_bgr: np.ndarray, threshold: int = 60) -> tuple[int, int, int, int]:
    """Return (x0, y0, w, h) of the brightest contiguous region — the phone screen.

    Assumes a single phone on a dark background. Uses morphological closing to
    fill dark text holes before finding connected components.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)),
    )
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n < 2:
        raise RuntimeError("no bright region detected — is the video dark or the phone off?")
    # Skip label 0 (background); pick the biggest remaining.
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, _ = stats[biggest]
    return x, y, w, h


def high_pass(gray: np.ndarray, kernel: int = 21) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (kernel, kernel), 0)
    return cv2.subtract(gray, blur) + cv2.subtract(blur, gray)


def median_smooth(values: list[int], window: int = 5) -> list[int]:
    if window < 2 or len(values) < window:
        return list(values)
    out = []
    half = window // 2
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(int(np.median(values[lo:hi])))
    return out


def top_k_peaks(score_col: np.ndarray, k: int = 8, min_gap: int = 80) -> list[tuple[int, float]]:
    """Return top-k local peaks in a 1-D score column with non-max suppression.

    score_col: shape (N, 1) as returned by matchTemplate. min_gap: separation
    between peaks in pixels.
    """
    scores = score_col.flatten().copy()
    peaks: list[tuple[int, float]] = []
    for _ in range(k):
        idx = int(np.argmax(scores))
        val = float(scores[idx])
        if val <= -1.0:
            break
        peaks.append((idx, val))
        lo, hi = max(0, idx - min_gap), min(len(scores), idx + min_gap + 1)
        scores[lo:hi] = -1.0
    return peaks


def best_path(per_frame_candidates: list[list[tuple[int, float]]],
              motion_weight: float = 0.0008) -> list[int]:
    """Select a y-offset per frame minimizing: sum(-score) + motion_weight * |Δy|.

    Classic forward DP; each frame has K candidates, path must thread through.
    """
    if not per_frame_candidates:
        return []
    K = max(len(c) for c in per_frame_candidates) or 1
    N = len(per_frame_candidates)
    # cost[t][i] = best cumulative cost reaching candidate i at time t
    cost = np.full((N, K), np.inf)
    back = np.full((N, K), -1, dtype=int)
    for i, (_, score) in enumerate(per_frame_candidates[0]):
        cost[0, i] = -score
    for t in range(1, N):
        curr = per_frame_candidates[t]
        prev = per_frame_candidates[t - 1]
        for i, (y_i, s_i) in enumerate(curr):
            best_prev_cost = np.inf
            best_prev_idx = -1
            for j, (y_j, _) in enumerate(prev):
                c = cost[t - 1, j] + motion_weight * abs(y_i - y_j)
                if c < best_prev_cost:
                    best_prev_cost = c
                    best_prev_idx = j
            cost[t, i] = best_prev_cost + (-s_i)
            back[t, i] = best_prev_idx
    # Backtrace from best endpoint
    end = int(np.argmin(cost[N - 1]))
    path_idx = [end]
    for t in range(N - 1, 0, -1):
        path_idx.append(int(back[t, path_idx[-1]]))
    path_idx.reverse()
    return [per_frame_candidates[t][i][0] for t, i in enumerate(path_idx)]


def recover(video_path: str, refpng_path: str,
            chrome_top: int = 50, chrome_bottom: int = 50,
            smooth_window: int = 5) -> tuple[list[dict], dict]:
    ref = cv2.imread(refpng_path)
    if ref is None:
        raise SystemExit(f"cannot read reference PNG: {refpng_path}")
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    ref_hp = high_pass(ref_gray)
    ref_w, ref_h = ref.shape[1], ref.shape[0]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {video_path}")
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    duration_s = n_frames / fps

    # Detect phone bounds from a middle frame (more reliable than frame 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, n_frames // 2)
    ok, mid = cap.read()
    if not ok:
        raise SystemExit("cannot read mid frame")
    sx, sy, sw, sh = detect_screen_bounds(mid)
    x0, y0 = sx + 4, sy + chrome_top
    x1, y1 = sx + sw - 4, sy + sh - chrome_bottom
    crop_w, crop_h = x1 - x0, y1 - y0
    scale = ref_w / crop_w
    scaled_h = int(crop_h * scale)

    print(f"phone screen: [{sx},{sy}] {sw}×{sh}; crop [{x0},{y0}..{x1},{y1}] {crop_w}×{crop_h}; "
          f"scale ×{scale:.3f} → template {ref_w}×{scaled_h}", file=sys.stderr)

    # Walk all frames — for each, collect top-K scroll candidates rather than just argmax
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    per_frame: list[list[tuple[int, float]]] = []
    timestamps: list[float] = []
    raw_argmax: list[int] = []
    raw_score: list[float] = []
    for fi in range(n_frames):
        ok, frame = cap.read()
        if not ok:
            break
        crop = frame[y0:y1, x0:x1]
        scaled = cv2.resize(crop, (ref_w, scaled_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        hp = high_pass(gray)
        if hp.shape[0] > ref_h:
            continue
        res = cv2.matchTemplate(ref_hp, hp, cv2.TM_CCOEFF_NORMED)
        peaks = top_k_peaks(res, k=8, min_gap=80)
        per_frame.append(peaks)
        timestamps.append(fi / fps * 1000)
        raw_argmax.append(peaks[0][0])
        raw_score.append(peaks[0][1])
    cap.release()

    # DP through candidates — minimize (−score) + motion_weight * |Δy|
    dp_ys = best_path(per_frame, motion_weight=0.0008)

    # Final median smoothing on the DP path for residual jitter
    ys_smooth = median_smooth(dp_ys, window=smooth_window)

    # Match scores kept from argmax (not the DP-selected peak score — DP can pick
    # a sub-argmax with lower absolute score but better global continuity)
    samples = [
        asdict(ScrollSample(
            t_ms=round(t, 1),
            y_offset_px=int(y),
            match_score=round(s, 4),
            scale=round(scale, 4),
        ))
        for t, y, s in zip(timestamps, ys_smooth, raw_score)
    ]

    meta = {
        "video_path": os.path.basename(video_path),
        "reference_path": os.path.basename(refpng_path),
        "reference_size_px": [ref_w, ref_h],
        "video_size_px": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                          if cap.isOpened() else None, None],
        "fps": fps,
        "n_frames": len(samples),
        "duration_s": round(duration_s, 3),
        "phone_screen_bounds": [int(sx), int(sy), int(sw), int(sh)],
        "crop_bounds": [int(x0), int(y0), int(x1), int(y1)],
        "scale_crop_to_ref": scale,
        "smooth_window": smooth_window,
        "match_score_range": [
            min((s["match_score"] for s in samples), default=0),
            max((s["match_score"] for s in samples), default=0),
        ],
        "y_offset_range_px": [
            min((s["y_offset_px"] for s in samples), default=0),
            max((s["y_offset_px"] for s in samples), default=0),
        ],
        "notes": (
            "Scroll offset recovered via high-pass grayscale NCC against "
            "reference SERP PNG. Match scores are intrinsically low (0.15-0.3 "
            "typical) because the live Google SERP rendered on the phone "
            "differs in ads/snippets from the static reference; reliability "
            "comes from temporal stability + median smoothing."
        ),
    }
    return samples, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--refpng", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smooth-window", type=int, default=5)
    args = ap.parse_args()

    samples, meta = recover(args.video, args.refpng, smooth_window=args.smooth_window)
    out = {"meta": meta, "samples": samples}
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"wrote {len(samples)} scroll samples → {args.out}", file=sys.stderr)
    print(f"y_offset range: {meta['y_offset_range_px']}  "
          f"match score range: {meta['match_score_range']}", file=sys.stderr)


if __name__ == "__main__":
    main()
