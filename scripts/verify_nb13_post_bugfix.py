"""Recompute NB13 K1-K8 with current bugfix-corrected data_loader.

Verifies whether the saccade-amplitude phase-signature numbers the task-model
paper draft cites (Survey 107.8 px / Evaluate 69.4 px / 1.55× / per-trial
slope ρ = -0.135, p = 9.33 × 10⁻¹⁶⁸ / Mann–Whitney p ≈ 0) survive the
y-offset and gaze-cursor coupling fixes that landed in CIKM but may not have
propagated to NB13's last execution.

Output: scripts/output/verify_nb13_post_bugfix/summary.json + console diff
against the K-values currently in the NB13 Key Claims block.
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import get_trial_ids, load_fixations  # noqa: E402

OUT_DIR = ROOT / "scripts/output/verify_nb13_post_bugfix"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SURVEY_END = 5  # NB13's operationalization: fixations 1-5 are survey

# Values currently cited in NB13 Key Claims block + task-model paper draft.
NB13_CITED = {
    "K1_slope_rho_mean": -0.135,
    "K1_slope_t": -29.63,
    "K1_slope_p": 9.33e-168,
    "K1_n_trials_with_ge_10_saccades": 2754,
    "K2_pct_trials_negative_slope": 0.718,
    "K5_survey_median_amplitude_px": 107.8,
    "K5_n_survey_saccades": 13840,
    "K6_evaluate_median_amplitude_px": 69.4,
    "K6_n_evaluate_saccades": 65764,
    "K7_amplitude_ratio": 1.55,
    "K8_mannwhitney_p": 0.0,  # underflow per NB13 watch-out
    "K8_mannwhitney_p_subset": 1.59e-219,
}


def saccade_amplitudes(fixations):
    """Return list of saccade amplitudes (Euclidean) between consecutive
    fixations within a trial. Uses fixation x and y from data_loader, which
    are post-bugfix page-space coordinates."""
    amps = []
    for i in range(1, len(fixations)):
        dx = fixations[i]["x"] - fixations[i - 1]["x"]
        dy = fixations[i]["y"] - fixations[i - 1]["y"]
        amps.append(float(np.sqrt(dx * dx + dy * dy)))
    return amps


def per_trial_slope(amps, max_n=20):
    """Spearman correlation between saccade index (1..N) and saccade
    amplitude over the first max_n saccades. Negative slope = wide-then-narrow
    (the survey → evaluate compression signature)."""
    if len(amps) < 10:
        return None
    head = amps[:max_n]
    idx = np.arange(1, len(head) + 1, dtype=float)
    rho, _ = stats.spearmanr(idx, head)
    return rho


def main():
    print("=" * 70)
    print("NB13 K1-K8 verification — post-bugfix recomputation")
    print("=" * 70)

    trial_ids = get_trial_ids()
    print(f"\nloading fixations for {len(trial_ids):,} trials...")

    survey_amps = []   # all saccades within survey window (fix 1..5)
    evaluate_amps = []  # all saccades after survey (fix 6+)
    per_trial_slopes = []
    skipped = 0

    for n_done, tid in enumerate(trial_ids):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(trial_ids)}  (skipped {skipped})")
        try:
            fixations = load_fixations(tid)
        except Exception:
            skipped += 1
            continue
        if fixations is None or len(fixations) < 6:
            skipped += 1
            continue

        amps = saccade_amplitudes(fixations)
        # Saccade i goes from fixation i to fixation i+1.
        # Saccades originating from fixations 1..SURVEY_END-1 (i.e. between
        # consecutive Survey fixations) count as Survey-phase saccades.
        # Match NB13: survey window = fixations 1..5, so saccades 1..4.
        for i, a in enumerate(amps, start=1):
            if i <= SURVEY_END - 1:
                survey_amps.append(a)
            else:
                evaluate_amps.append(a)

        slope = per_trial_slope(amps)
        if slope is not None:
            per_trial_slopes.append(slope)

    print(f"\n  total trials processed: {len(trial_ids) - skipped:,}")
    print(f"  survey-window saccades:  {len(survey_amps):,}")
    print(f"  evaluate-phase saccades: {len(evaluate_amps):,}")
    print(f"  trials with ≥10 saccades (for slope): {len(per_trial_slopes):,}")

    survey_arr = np.array(survey_amps, dtype=float)
    eval_arr = np.array(evaluate_amps, dtype=float)
    slope_arr = np.array(per_trial_slopes, dtype=float)

    # K5 / K6 / K7
    k5 = float(np.median(survey_arr))
    k6 = float(np.median(eval_arr))
    k7 = k5 / k6 if k6 > 0 else float("nan")

    # K8 — Mann–Whitney with full N may underflow; report what scipy returns.
    try:
        u_stat, k8 = stats.mannwhitneyu(
            survey_arr, eval_arr, alternative="greater")
    except Exception as e:
        u_stat, k8 = (float("nan"), float("nan"))
        print(f"  (Mann–Whitney error: {e})")

    # K1 / K2 — per-trial slope
    k1_mean = float(slope_arr.mean())
    k1_t, k1_p = stats.ttest_1samp(slope_arr, 0.0)
    k2 = float((slope_arr < 0).mean())

    print("\n── Recomputed values ──")
    print(f"  K1 mean per-trial slope ρ:      {k1_mean:+.4f}")
    print(f"        t (vs 0):                {k1_t:.2f}")
    print(f"        p (vs 0):                {k1_p:.3e}")
    print(f"  K2 fraction trials with ρ < 0:  {k2:.3f}")
    print(f"  K5 survey median amplitude:     {k5:.2f} px (n = {len(survey_arr):,})")
    print(f"  K6 evaluate median amplitude:   {k6:.2f} px (n = {len(eval_arr):,})")
    print(f"  K7 ratio (survey / evaluate):   {k7:.3f}×")
    print(f"  K8 Mann–Whitney U:              {u_stat:.3e}")
    print(f"  K8 Mann–Whitney p:              {k8:.3e}")

    print("\n── Diff against NB13 cited values ──")

    def diff(label, recomputed, cited, tolerance=0.02):
        if cited is None:
            return
        if recomputed is None or np.isnan(recomputed):
            print(f"  {label:<40s} cited {cited!r}, recomputed N/A — INVESTIGATE")
            return
        try:
            cited_f = float(cited)
        except (TypeError, ValueError):
            print(f"  {label:<40s} cited {cited!r}, recomputed {recomputed!r}")
            return
        rel = abs(recomputed - cited_f) / max(abs(cited_f), 1e-12)
        flag = "OK" if rel <= tolerance else "DIFFERS"
        if rel > tolerance:
            flag += f"  ({rel * 100:.1f} % off)"
        print(f"  {label:<40s} cited {cited_f:.4g}, recomputed {recomputed:.4g}  → {flag}")

    diff("K1 slope ρ mean", k1_mean, NB13_CITED["K1_slope_rho_mean"])
    diff("K1 slope t-statistic", k1_t, NB13_CITED["K1_slope_t"], tolerance=0.05)
    diff("K2 % trials negative slope", k2, NB13_CITED["K2_pct_trials_negative_slope"])
    diff("K5 survey median (px)", k5, NB13_CITED["K5_survey_median_amplitude_px"])
    diff("K5 N survey saccades",
         len(survey_arr), NB13_CITED["K5_n_survey_saccades"], tolerance=0.05)
    diff("K6 evaluate median (px)", k6, NB13_CITED["K6_evaluate_median_amplitude_px"])
    diff("K6 N evaluate saccades",
         len(eval_arr), NB13_CITED["K6_n_evaluate_saccades"], tolerance=0.05)
    diff("K7 amplitude ratio", k7, NB13_CITED["K7_amplitude_ratio"], tolerance=0.05)

    summary = {
        "experiment": "NB13 K1-K8 verification post-bugfix",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_trials_processed": len(trial_ids) - skipped,
        "n_trials_skipped": skipped,
        "recomputed": {
            "K1_slope_rho_mean": k1_mean,
            "K1_slope_t": float(k1_t),
            "K1_slope_p": float(k1_p),
            "K1_n_trials_with_ge_10_saccades": len(slope_arr),
            "K2_pct_trials_negative_slope": k2,
            "K5_survey_median_amplitude_px": k5,
            "K5_n_survey_saccades": len(survey_arr),
            "K6_evaluate_median_amplitude_px": k6,
            "K6_n_evaluate_saccades": len(eval_arr),
            "K7_amplitude_ratio": k7,
            "K8_mannwhitney_p": float(k8),
            "K8_mannwhitney_U": float(u_stat),
        },
        "nb13_cited": NB13_CITED,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
