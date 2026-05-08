"""LF/HF time-locked around click and last-fixation-onset — the LF/HF analog
of ripa2_around_click_sanity.py.

Tests the temporal-scope dissociation between RIPA2 and LF/HF:
  - RIPA2 (per-fixation amplitude, derivative-based) detects peri-click TEPR
    (peak at -10 ms vs early baseline, p = 3.3×10⁻²¹).
  - Hypothesis: LF/HF (windowed frequency-domain, ≥7.5 s reliability per
    Duchowski 2026) does NOT see the peri-click amplitude excursion, since
    it integrates power over multi-second windows.

If LF/HF is flat at the click event → dissociation confirmed: RIPA2 reads
events, LF/HF reads sustained state. Different temporal scopes, same pupil.

If LF/HF shows a peri-click peak → dissociation weaker than claimed; would
need to revise the "RIPA2 unique territory = per-event" framing.

Output:
  scripts/output/lfhf_around_click/summary.json
  scripts/output/lfhf_around_click/comparison_4panel.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
from scipy.stats import wilcoxon, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_pupil_trial, load_mouse_events, load_fixations,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/lfhf_around_click'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FS = 150
PRE_MS = 3000
POST_MS = 3000
BIN_MS = 20

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_RIPA2 = "#7c4dff"
COLOR_LFHF = "#d4a574"
COLOR_CONTROL = "#888888"


def make_axis(pre_ms: int, post_ms: int) -> tuple[np.ndarray, int]:
    n = (pre_ms + post_ms) // BIN_MS
    return np.arange(-pre_ms, post_ms, BIN_MS) + BIN_MS / 2, n


def time_lock(ts_ms: np.ndarray, signal: np.ndarray, event_t_ms: float,
              pre_ms: int, post_ms: int) -> np.ndarray | None:
    rel = ts_ms - event_t_ms
    mask = (rel >= -pre_ms) & (rel < post_ms)
    n_bins = (pre_ms + post_ms) // BIN_MS
    if mask.sum() < n_bins // 4:
        return None
    binned = np.full(n_bins, np.nan)
    for i in range(n_bins):
        bin_lo = -pre_ms + i * BIN_MS
        bin_hi = bin_lo + BIN_MS
        bin_mask = mask & (rel >= bin_lo) & (rel < bin_hi)
        if bin_mask.any():
            binned[i] = float(np.mean(signal[bin_mask]))
    return binned


def lfhf_signal(pupil: np.ndarray) -> np.ndarray:
    """Per-sample LF/HF power ratio. Uses Task Force 1996 / Duchowski 2026
    bands (LF: 0.04-0.15 Hz, HF: 0.15-0.40 Hz)."""
    nyq = FS / 2
    lf_b, lf_a = butter(2, [0.04 / nyq, 0.15 / nyq], btype='band')
    hf_b, hf_a = butter(2, [0.15 / nyq, 0.40 / nyq], btype='band')
    lf = filtfilt(lf_b, lf_a, pupil)
    hf = filtfilt(hf_b, hf_a, pupil)
    return (lf ** 2) / (hf ** 2 + 1e-9)


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    axis, n_bins = make_axis(PRE_MS, POST_MS)

    traces = {
        'ripa2_click': [], 'ripa2_lastfix': [], 'ripa2_ctrl': [],
        'lfhf_click':  [], 'lfhf_lastfix':  [], 'lfhf_ctrl':  [],
    }
    delta_fix_to_click = []
    rng = np.random.default_rng(42)

    n_skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            n_skipped += 1
            continue
        ts = pupil['ts']
        signal = pupil['clean_pd']
        if len(signal) < FS * 4:
            continue

        ripa2 = compute_ripa2_signal(signal)
        lf = lfhf_signal(signal)
        # Cap LF/HF outliers for plotting stability — the per-sample power
        # ratio has very heavy tails. Use the 99th percentile within trial.
        lf_cap = float(np.nanpercentile(lf, 99))
        if np.isfinite(lf_cap) and lf_cap > 0:
            lf = np.clip(lf, 0, lf_cap)

        events, scrolls, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        click_t = float(clicks[-1][0])

        # Event 1: click
        for name, sig in [('ripa2', ripa2), ('lfhf', lf)]:
            tr = time_lock(ts, sig, click_t, PRE_MS, POST_MS)
            if tr is not None:
                traces[f'{name}_click'].append(tr)

        # Event 2: last fixation onset
        fixations = load_fixations(tid)
        if fixations:
            fix_ts = np.array([f['t'] for f in fixations], dtype=float)
            mask = fix_ts < click_t
            if mask.any():
                last_fix_t = float(fix_ts[mask][-1])
                delta_fix_to_click.append(click_t - last_fix_t)
                for name, sig in [('ripa2', ripa2), ('lfhf', lf)]:
                    tr = time_lock(ts, sig, last_fix_t, PRE_MS, POST_MS)
                    if tr is not None:
                        traces[f'{name}_lastfix'].append(tr)

        # Control: random fixation > 2s from click
        if fixations:
            fix_ts = np.array([f['t'] for f in fixations], dtype=float)
            far = np.abs(fix_ts - click_t) > 2000
            if far.any():
                ctrl_t = float(rng.choice(fix_ts[far]))
                for name, sig in [('ripa2', ripa2), ('lfhf', lf)]:
                    tr = time_lock(ts, sig, ctrl_t, PRE_MS, POST_MS)
                    if tr is not None:
                        traces[f'{name}_ctrl'].append(tr)

    arrs = {k: np.array(v) if v else None for k, v in traces.items()}
    print(f'\n  click-locked: ripa2={len(traces["ripa2_click"]):,}  '
          f'lfhf={len(traces["lfhf_click"]):,}', file=sys.stderr)
    print(f'  lastfix-locked: ripa2={len(traces["ripa2_lastfix"]):,}  '
          f'lfhf={len(traces["lfhf_lastfix"]):,}', file=sys.stderr)
    print(f'  control: ripa2={len(traces["ripa2_ctrl"]):,}  '
          f'lfhf={len(traces["lfhf_ctrl"]):,}', file=sys.stderr)
    if delta_fix_to_click:
        d = np.array(delta_fix_to_click)
        print(f'  median (last_fix → click) = {np.median(d):.0f} ms',
              file=sys.stderr)

    def trace_mean(arr):
        return None if arr is None or len(arr) == 0 else np.nanmean(arr, axis=0)

    def ci_bootstrap(arr, n_boot=400):
        if arr is None or len(arr) == 0:
            return None, None
        n = len(arr)
        rng_loc = np.random.default_rng(7)
        idx = rng_loc.integers(0, n, size=(n_boot, n))
        boots = np.nanmean(arr[idx], axis=1)
        lo = np.nanpercentile(boots, 2.5, axis=0)
        hi = np.nanpercentile(boots, 97.5, axis=0)
        return lo, hi

    # Statistical comparisons: peri-event window vs early baseline
    early_mask = (axis >= -3000) & (axis <= -2000)
    pre_window = (axis >= -1500) & (axis <= -100)
    post_window = (axis >= 0) & (axis <= 1500)

    def event_vs_baseline(arr):
        """Returns dict of pre-peri vs early-baseline test stats."""
        if arr is None or len(arr) == 0:
            return None
        eb = np.nanmean(arr[:, early_mask], axis=1)
        pre = np.nanmean(arr[:, pre_window], axis=1)
        post = np.nanmean(arr[:, post_window], axis=1)
        valid = ~(np.isnan(eb) | np.isnan(pre))
        if valid.sum() < 30:
            return None
        w_pre = wilcoxon(pre[valid], eb[valid], alternative='greater')
        w_post = wilcoxon(post[valid][~np.isnan(post[valid])],
                          eb[valid][~np.isnan(post[valid])],
                          alternative='greater')
        return {
            'n': int(valid.sum()),
            'baseline_mean': float(np.nanmean(eb)),
            'pre_window_mean': float(np.nanmean(pre)),
            'post_window_mean': float(np.nanmean(post)),
            'w_pre_gt_baseline_p': float(w_pre.pvalue),
            'w_post_gt_baseline_p': float(w_post.pvalue),
            'pre_div_baseline': float(np.nanmean(pre) / max(np.nanmean(eb), 1e-9)),
        }

    summary = {
        'n_click_locked':   {'ripa2': len(traces['ripa2_click']),
                             'lfhf':  len(traces['lfhf_click'])},
        'n_lastfix_locked': {'ripa2': len(traces['ripa2_lastfix']),
                             'lfhf':  len(traces['lfhf_lastfix'])},
        'n_control':        {'ripa2': len(traces['ripa2_ctrl']),
                             'lfhf':  len(traces['lfhf_ctrl'])},
        'last_fix_to_click_ms': float(np.median(delta_fix_to_click))
                                if delta_fix_to_click else None,
        'tests': {
            'ripa2_click':   event_vs_baseline(arrs['ripa2_click']),
            'ripa2_lastfix': event_vs_baseline(arrs['ripa2_lastfix']),
            'lfhf_click':    event_vs_baseline(arrs['lfhf_click']),
            'lfhf_lastfix':  event_vs_baseline(arrs['lfhf_lastfix']),
        },
    }

    print('\n=== Event > early-baseline tests (Wilcoxon, one-sided) ===')
    print(f'{"metric / lock":>20s} {"n":>6s} {"pre/baseline":>14s} {"p_pre":>10s} {"p_post":>10s}')
    for label in ('ripa2_click', 'ripa2_lastfix', 'lfhf_click', 'lfhf_lastfix'):
        t = summary['tests'].get(label)
        if t is None:
            print(f'{label:>20s}  insufficient n')
            continue
        print(f'{label:>20s} {t["n"]:>6,} {t["pre_div_baseline"]:>14.3f} '
              f'{t["w_pre_gt_baseline_p"]:>10.3g} {t["w_post_gt_baseline_p"]:>10.3g}')

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── 4-panel comparison figure ────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    fig.suptitle("Time-locked RIPA2 vs LF/HF — peri-click vs peri-fixation",
                 y=0.995, fontsize=15)

    panels = [
        ('ripa2_click',   'ripa2_ctrl', '(A) RIPA2 click-locked',         COLOR_RIPA2, axes[0, 0]),
        ('lfhf_click',    'lfhf_ctrl',  '(B) LF/HF click-locked',         COLOR_LFHF,  axes[0, 1]),
        ('ripa2_lastfix', 'ripa2_ctrl', '(C) RIPA2 last-fix-onset locked', COLOR_RIPA2, axes[1, 0]),
        ('lfhf_lastfix',  'lfhf_ctrl',  '(D) LF/HF last-fix-onset locked', COLOR_LFHF,  axes[1, 1]),
    ]

    for evt_key, ctrl_key, title, col, ax in panels:
        ev_arr = arrs[evt_key]
        ct_arr = arrs[ctrl_key]
        if ct_arr is not None and len(ct_arr) > 0:
            lo, hi = ci_bootstrap(ct_arr)
            ax.fill_between(axis, lo, hi, color=COLOR_CONTROL, alpha=0.15)
            ax.plot(axis, trace_mean(ct_arr), color=COLOR_CONTROL, lw=1.4,
                    label=f'control  N={len(ct_arr):,}')
        if ev_arr is not None and len(ev_arr) > 0:
            lo, hi = ci_bootstrap(ev_arr)
            ax.fill_between(axis, lo, hi, color=col, alpha=0.22)
            ax.plot(axis, trace_mean(ev_arr), color=col, lw=2.0,
                    label=f'event  N={len(ev_arr):,}')
        ax.axvline(0, color="#222222", lw=1.0, ls="--", alpha=0.6)
        ax.set_xlabel('time from event (ms)')
        ax.set_ylabel(evt_key.split('_')[0].upper())
        ax.set_title(title)
        ax.legend(loc='upper left', frameon=True, framealpha=0.92, edgecolor="#cccccc")
        ax.grid(True, alpha=0.5)

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    out_png = OUT_DIR / 'comparison_4panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'comparison_4panel.svg', bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
