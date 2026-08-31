"""Pre-first-fixation PAI probe — the simplest PAI-advantage illustration.

Question: does the to-be-clicked result accrue more peripheral PAI mass
than its non-clicked neighbors BEFORE anyone has ever foveated it?

Why this is the clean demonstration: for each (trial, AOI) record, the
window [trial start, entry_t) precedes the first fixation binary-assigned
to that AOI. In that window the traditional gaze-point-in-AOI metric is
IDENTICALLY ZERO for every record by construction (any fixation assigned
to the AOI would have defined an earlier entry_t), so its discriminative
power is exactly AUC = 0.5. Any signal found here is information the
traditional metric cannot represent, full stop. No model, no LOSO — a
paired within-trial comparison and a single-feature AUC.

Geometry note: bands partition page-y and binary assignment ignores x,
so every pre-entry fixation lies strictly outside the AOI band in y —
pre-entry PAI mass is purely peripheral automatically. The peripheral
accumulator is still used for belt-and-braces.

Known bias, direction favorable: clicked results are foveated EARLY, so
their accumulation window is typically SHORTER than their non-clicked
neighbors'. Peripheral mass grows with window length (cf.
docs/null-findings/lfhf-window-duration-confound.md), so raw-mass
comparisons are biased AGAINST the hypothesis; a positive raw result is
conservative. A rate-normalized variant (mass / window) and a
position-adjacent pairing (|pos - pos_clicked| == 1) are reported as
controls anyway, plus the window-length asymmetry itself.

Population: the published buf500 grid record set (fixated AOI slots
only; never-fixated slots have no entry_t and are excluded — also
conservative, since those are slots where only PAI could score at all).
Trials without a click are excluded (no pair to form).

Four alpha forms: exact delivered-demo (sqrt + inverse-area weight,
boundary OGD), NB35 abstract-only (1 - OGD/CGD, boundary OGD), and the
two spec-exact options from the authors' manuscript (received
2026-08-31; `pai_spec.rect_alpha_grid`): vertex/corner OGD with
min(1, A/A_ref) placed inside the sqrt (spec_eq2, the Eq. 2 form) or
outside (spec_listing, the Listing 1.1 form). Peripheral gating stays
rect-containment (boundary OGD > 0) for all four — the gate belongs to
this probe's estimator, not to the alpha formula.

Outputs:
  scripts/output/ablations/pai_preentry_probe.json
Results section appended by hand to docs/ablations/pai_exposure_validation.md.

Rank-type: [LAB, AdSERP, organic_hybrid].

Run:
    .venv/bin/python scripts/pai_preentry_probe.py
"""
from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_fixations  # noqa: E402
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402
from pai_spec import rect_alpha_grid  # noqa: E402

OUT_DIR = ROOT / "scripts/output/ablations"
BUF500_FEATURES = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-buf500.json"

PHI = (1 + np.sqrt(5)) / 2 - 1
P_LAMBDA = PHI ** 3

N_BOOT = 5000
RNG = np.random.default_rng(20260818)

# (record key, form label) for the four alpha variants, in mass-tuple order.
FORMS = (("pre_mass_ms", "exact"),
         ("pre_mass35_ms", "nb35"),
         ("pre_mass_spec_ms", "spec_eq2"),
         ("pre_mass_specl_ms", "spec_listing"))


def preentry_mass_for_trial(trial_id, entry_by_pos):
    """Per-position pre-entry peripheral PAI mass, all four alpha forms.

    entry_by_pos: {position: entry_t}. Returns {position: (mass_exact,
    mass_35, mass_spec_eq2, mass_spec_listing, window_ms)} or None if
    fixations/AOIs unavailable.
    """
    try:
        fixations = load_fixations(trial_id)
    except Exception:
        return None
    if not fixations:
        return None
    tops, bottoms, _etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None

    n_aoi = len(tops)
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
    a_top = np.asarray(tops, dtype=float)
    a_bot = np.asarray(bottoms, dtype=float)
    heights = np.maximum(a_bot - a_top, 1.0)
    areas = (x1 - x0) * heights
    w_a = (areas.max() / np.maximum(areas, 1.0)) ** P_LAMBDA
    cx = (x0 + x1) / 2.0
    cy = (a_top + a_bot) / 2.0

    ft = np.array([f["t"] for f in fixations], dtype=float)
    fx = np.array([f["x"] for f in fixations], dtype=float)
    fy = np.array([f["y"] for f in fixations], dtype=float)
    fd = np.array([f.get("d", 200) or 200 for f in fixations], dtype=float)
    t_start = float(ft.min())

    dx = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
    dxg = np.repeat(dx[:, None], n_aoi, axis=1)
    dyg = np.maximum.reduce([
        a_top[None, :] - fy[:, None],
        np.zeros((len(fy), n_aoi)),
        fy[:, None] - a_bot[None, :],
    ])
    ogd = np.hypot(dxg, dyg)
    cgd = np.hypot(fx[:, None] - cx, fy[:, None] - cy[None, :])
    alpha = np.clip(1.0 - np.sqrt(ogd / np.maximum(cgd, 1.0)) * w_a[None, :],
                    0.0, 1.0)
    alpha35 = np.clip(1.0 - ogd / np.maximum(cgd, 1.0), 0.0, 1.0)
    alpha_spec = rect_alpha_grid(fx, fy, x0, x1, a_top, a_bot,
                                 weight_placement="eq2")
    alpha_specl = rect_alpha_grid(fx, fy, x0, x1, a_top, a_bot,
                                  weight_placement="listing")
    outside = ogd > 0.0

    out = {}
    for pos, entry_t in entry_by_pos.items():
        if pos >= n_aoi:
            continue
        mask = ft < float(entry_t)
        d = fd[mask]
        gate = outside[mask, pos]

        def acc(a):
            return float((d * np.where(gate, a[mask, pos], 0.0)).sum())

        out[pos] = (acc(alpha), acc(alpha35), acc(alpha_spec),
                    acc(alpha_specl), float(entry_t) - t_start)
    return out


def shared_cutoff_masses(trial_id, t_star):
    """Peripheral PAI mass for EVERY AOI slot in the shared window
    [trial start, t_star). Returns (mass_exact[], mass_35[],
    mass_spec_eq2[], mass_spec_listing[], n_aoi, n_fix_in_window) or
    None."""
    try:
        fixations = load_fixations(trial_id)
    except Exception:
        return None
    if not fixations:
        return None
    tops, bottoms, _etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None
    n_aoi = len(tops)
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
    a_top = np.asarray(tops, dtype=float)
    a_bot = np.asarray(bottoms, dtype=float)
    heights = np.maximum(a_bot - a_top, 1.0)
    areas = (x1 - x0) * heights
    w_a = (areas.max() / np.maximum(areas, 1.0)) ** P_LAMBDA
    cx = (x0 + x1) / 2.0
    cy = (a_top + a_bot) / 2.0

    ft = np.array([f["t"] for f in fixations], dtype=float)
    mask = ft < float(t_star)
    if not mask.any():
        z = [0.0] * n_aoi
        return (z, list(z), list(z), list(z), n_aoi, 0)
    fx = np.array([f["x"] for f in fixations], dtype=float)[mask]
    fy = np.array([f["y"] for f in fixations], dtype=float)[mask]
    fd = np.array([f.get("d", 200) or 200 for f in fixations],
                  dtype=float)[mask]

    dx = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
    dxg = np.repeat(dx[:, None], n_aoi, axis=1)
    dyg = np.maximum.reduce([
        a_top[None, :] - fy[:, None],
        np.zeros((len(fy), n_aoi)),
        fy[:, None] - a_bot[None, :],
    ])
    ogd = np.hypot(dxg, dyg)
    cgd = np.hypot(fx[:, None] - cx, fy[:, None] - cy[None, :])
    alpha = np.clip(1.0 - np.sqrt(ogd / np.maximum(cgd, 1.0)) * w_a[None, :],
                    0.0, 1.0)
    alpha35 = np.clip(1.0 - ogd / np.maximum(cgd, 1.0), 0.0, 1.0)
    alpha_spec = rect_alpha_grid(fx, fy, x0, x1, a_top, a_bot,
                                 weight_placement="eq2")
    alpha_specl = rect_alpha_grid(fx, fy, x0, x1, a_top, a_bot,
                                  weight_placement="listing")
    outside = ogd > 0.0
    d = fd[:, None]

    def acc(a):
        return (d * np.where(outside, a, 0.0)).sum(axis=0).tolist()

    return (acc(alpha), acc(alpha35), acc(alpha_spec), acc(alpha_specl),
            n_aoi, int(mask.sum()))


def paired_stats(diffs, label):
    diffs = np.asarray(diffs, dtype=float)
    n = len(diffs)
    try:
        _, w_p = stats.wilcoxon(diffs, zero_method="wilcox",
                                alternative="two-sided")
        w_p = float(w_p)
    except ValueError:
        w_p = 1.0
    sd = float(np.std(diffs, ddof=1)) if n >= 2 else float("nan")
    d_z = float(np.mean(diffs)) / sd if sd and sd > 0 else float("nan")
    boot = np.array([np.mean(diffs[RNG.integers(0, n, size=n)])
                     for _ in range(N_BOOT)])
    return {
        "label": label,
        "n_trials": int(n),
        "mean_diff": float(np.mean(diffs)),
        "median_diff": float(np.median(diffs)),
        "frac_positive": float((diffs > 0).mean()),
        "ci_95": [float(np.percentile(boot, 2.5)),
                  float(np.percentile(boot, 97.5))],
        "wilcoxon_p": w_p,
        "cohens_d_z": d_z,
    }


def main():
    print("=" * 72)
    print("Pre-first-fixation PAI probe — clicked vs non-clicked neighbors")
    print("=" * 72)

    recs = json.load(open(BUF500_FEATURES))
    by_trial = defaultdict(list)
    for r in recs:
        by_trial[r["trial_id"]].append(r)
    clicked_trials = {t: rows for t, rows in by_trial.items()
                      if any(r["was_clicked"] for r in rows)
                      and sum(1 for r in rows if not r["was_clicked"]) >= 1}
    print(f"  {len(by_trial):,} trials in grid; "
          f"{len(clicked_trials):,} with a click + >=1 non-clicked neighbor")

    rows_out = []   # per-record: trial, pos, clicked, mass, mass35, window
    n_fail = 0
    for i, (tid, rows) in enumerate(sorted(clicked_trials.items())):
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(clicked_trials)}", file=sys.stderr)
        entry_by_pos = {r["position"]: r["entry_t"] for r in rows}
        res = preentry_mass_for_trial(tid, entry_by_pos)
        if res is None:
            n_fail += 1
            continue
        for r in rows:
            p = r["position"]
            if p not in res:
                continue
            m, m35, msp, mspl, win = res[p]
            rows_out.append({
                "trial_id": tid, "position": p,
                "was_clicked": int(r["was_clicked"]),
                "pre_mass_ms": m, "pre_mass35_ms": m35,
                "pre_mass_spec_ms": msp, "pre_mass_specl_ms": mspl,
                "window_ms": win,
            })
    print(f"  {len(rows_out):,} records ({n_fail} trials failed loading)")

    # ── Paired within-trial comparisons ──
    per_trial = defaultdict(list)
    for r in rows_out:
        per_trial[r["trial_id"]].append(r)

    def collect(pair_fn, mass_key):
        diffs = []
        for _tid, rows in per_trial.items():
            clk = [r for r in rows if r["was_clicked"]]
            non = [r for r in rows if not r["was_clicked"]]
            if not clk or not non:
                continue
            d = pair_fn(clk[0], non, mass_key)
            if d is not None:
                diffs.append(d)
        return diffs

    def raw_pair(c, non, k):
        return c[k] - float(np.mean([r[k] for r in non]))

    def rate_pair(c, non, k):
        if c["window_ms"] <= 0:
            return None
        non_ok = [r for r in non if r["window_ms"] > 0]
        if not non_ok:
            return None
        return (c[k] / c["window_ms"]
                - float(np.mean([r[k] / r["window_ms"] for r in non_ok])))

    def adjacent_pair(c, non, k):
        adj = [r for r in non if abs(r["position"] - c["position"]) == 1]
        if not adj:
            return None
        return c[k] - float(np.mean([r[k] for r in adj]))

    tests = []
    for mass_key, form in FORMS:
        tests.append(paired_stats(collect(raw_pair, mass_key),
                                  f"raw clicked - mean(non-clicked) [{form}]"))
        tests.append(paired_stats(collect(rate_pair, mass_key),
                                  f"rate (mass/window) [{form}]"))
        tests.append(paired_stats(collect(adjacent_pair, mass_key),
                                  f"position-adjacent (|dpos|=1) [{form}]"))

    for t in tests:
        print(f"  {t['label']:44s} n={t['n_trials']:,} "
              f"median diff {t['median_diff']:+.1f}  "
              f"frac>0 {t['frac_positive']:.3f}  "
              f"d_z={t['cohens_d_z']:+.2f}  p={t['wilcoxon_p']:.1e}")

    # ── Window-length asymmetry (the conservative-bias check) ──
    win_diffs = collect(raw_pair, "window_ms")
    win_stat = paired_stats(win_diffs, "window length clicked - non-clicked")
    print(f"  window asymmetry: median {win_stat['median_diff']:+.0f} ms "
          f"(clicked window {'SHORTER' if win_stat['median_diff'] < 0 else 'longer'}"
          f"; bias against hypothesis if shorter)  p={win_stat['wilcoxon_p']:.1e}")

    # ── Single-feature AUC (binary floor is exactly 0.5) ──
    y = np.array([r["was_clicked"] for r in rows_out])
    aucs = {}
    for mass_key, form in FORMS:
        x = np.array([r[mass_key] for r in rows_out], dtype=float)
        aucs[form] = float(roc_auc_score(y, x))
        # per-participant AUC distribution
        pids = np.array([r["trial_id"].split("-")[0] for r in rows_out])
        pp = []
        for pid in sorted(set(pids)):
            m = pids == pid
            if m.sum() >= 10 and len(set(y[m])) == 2:
                pp.append(float(roc_auc_score(y[m], x[m])))
        aucs[f"{form}_per_participant_median"] = float(np.median(pp))
        aucs[f"{form}_per_participant_frac_above_half"] = float(
            np.mean([a > 0.5 for a in pp]))
        aucs[f"{form}_n_participants"] = len(pp)
        print(f"  AUC [{form}]: {aucs[form]:.4f} pooled "
              f"(per-participant median "
              f"{aucs[f'{form}_per_participant_median']:.4f}, "
              f"{aucs[f'{form}_per_participant_frac_above_half'] * 100:.0f}% "
              "of participants > 0.5; binary-dwell floor = 0.5000 exactly)")

    # Descriptives
    clk_mass = np.array([r["pre_mass_ms"] for r in rows_out if r["was_clicked"]])
    non_mass = np.array([r["pre_mass_ms"] for r in rows_out if not r["was_clicked"]])
    desc = {
        "clicked_median_ms": float(np.median(clk_mass)),
        "nonclicked_median_ms": float(np.median(non_mass)),
        "clicked_frac_nonzero": float((clk_mass > 0).mean()),
        "nonclicked_frac_nonzero": float((non_mass > 0).mean()),
    }
    print(f"  medians: clicked {desc['clicked_median_ms']:.0f} ms vs "
          f"non-clicked {desc['nonclicked_median_ms']:.0f} ms pre-entry "
          "peripheral mass")

    # ── Probe B: shared cutoff at t* = first foveation of the clicked
    #    result; candidates = all slots still unfixated at t*. Identical
    #    window per trial (no length confound), binary dwell = 0 for every
    #    candidate (floor = 0.5 exactly). Per-trial score: fraction of
    #    unfixated peers the clicked result beats on peripheral mass
    #    (ties = 0.5); one-sample vs 0.5. ──
    print("\n  Probe B: shared-cutoff (t* = clicked entry), unfixated slots only")
    b_scores = {form: [] for _, form in FORMS}
    n_no_prior_fix = 0
    n_no_peers = 0
    peer_counts = []
    for i, (tid, rows) in enumerate(sorted(clicked_trials.items())):
        if (i + 1) % 400 == 0:
            print(f"  B {i + 1}/{len(clicked_trials)}", file=sys.stderr)
        clk = next(r for r in rows if r["was_clicked"])
        t_star = float(clk["entry_t"])
        entry_by_pos = {r["position"]: float(r["entry_t"]) for r in rows}
        res = shared_cutoff_masses(tid, t_star)
        if res is None:
            continue
        *masses, n_aoi, n_fix = res
        if n_fix == 0:
            n_no_prior_fix += 1
            continue
        cpos = clk["position"]
        if cpos >= n_aoi:
            continue
        peers = [p for p in range(n_aoi)
                 if p != cpos and entry_by_pos.get(p, float("inf")) > t_star]
        if not peers:
            n_no_peers += 1
            continue
        peer_counts.append(len(peers))

        def score(vals):
            c = vals[cpos]
            less = sum(1 for p in peers if vals[p] < c)
            ties = sum(1 for p in peers if vals[p] == c)
            return (less + 0.5 * ties) / len(peers)

        for (_, form), vals in zip(FORMS, masses):
            b_scores[form].append(score(vals))

    probe_b = {}
    for label, ss in ((form, b_scores[form]) for _, form in FORMS):
        ss = np.asarray(ss, dtype=float)
        boot = np.array([np.mean(ss[RNG.integers(0, len(ss), size=len(ss))])
                         for _ in range(N_BOOT)])
        try:
            _, w_p = stats.wilcoxon(ss - 0.5, zero_method="wilcox",
                                    alternative="two-sided")
            w_p = float(w_p)
        except ValueError:
            w_p = 1.0
        sd = float(np.std(ss - 0.5, ddof=1))
        probe_b[label] = {
            "n_trials": int(len(ss)),
            "mean_score": float(np.mean(ss)),
            "median_score": float(np.median(ss)),
            "ci_95": [float(np.percentile(boot, 2.5)),
                      float(np.percentile(boot, 97.5))],
            "wilcoxon_p_vs_half": w_p,
            "cohens_d_z_vs_half": float(np.mean(ss - 0.5)) / sd if sd > 0 else float("nan"),
        }
        print(f"    [{label}] clicked beats {probe_b[label]['mean_score'] * 100:.1f}% "
              f"of unfixated peers (chance 50.0%; "
              f"CI [{probe_b[label]['ci_95'][0] * 100:.1f}, "
              f"{probe_b[label]['ci_95'][1] * 100:.1f}]%; "
              f"n={probe_b[label]['n_trials']:,}; "
              f"d_z={probe_b[label]['cohens_d_z_vs_half']:+.2f}; "
              f"p={probe_b[label]['wilcoxon_p_vs_half']:.1e})")
    probe_b["n_trials_no_prior_fixations"] = n_no_prior_fix
    probe_b["n_trials_no_unfixated_peers"] = n_no_peers
    probe_b["median_peers"] = float(np.median(peer_counts)) if peer_counts else 0
    print(f"    excluded: {n_no_prior_fix} trials with zero fixations before t*, "
          f"{n_no_peers} with no unfixated peers; median peers "
          f"{probe_b['median_peers']:.0f}")

    # ── Probe C (specificity control): same score for a non-clicked
    #    FIXATED result at ITS first-foveation moment. If any about-to-be-
    #    foveated result beats its unfixated peers equally well, probe B
    #    is foveation anticipation (scanpath frontier), not click
    #    prediction; the paired B-minus-C delta is the click-specific
    #    part. Control pick: the non-clicked fixated result whose entry_t
    #    is nearest the trial's median entry (deterministic, seeded RNG
    #    unused), excluding the clicked result. ──
    print("\n  Probe C: same score for a non-clicked fixated result at its own t*")
    c_scores = {form: [] for _, form in FORMS}
    b_paired = {form: [] for _, form in FORMS}
    for i, (tid, rows) in enumerate(sorted(clicked_trials.items())):
        if (i + 1) % 400 == 0:
            print(f"  C {i + 1}/{len(clicked_trials)}", file=sys.stderr)
        clk = next(r for r in rows if r["was_clicked"])
        non_fixated = [r for r in rows if not r["was_clicked"]]
        if not non_fixated:
            continue
        entries = sorted(float(r["entry_t"]) for r in rows)
        med = entries[len(entries) // 2]
        ctrl = min(non_fixated, key=lambda r: abs(float(r["entry_t"]) - med))
        entry_by_pos = {r["position"]: float(r["entry_t"]) for r in rows}

        def score_at(target_pos, t_star):
            res = shared_cutoff_masses(tid, t_star)
            if res is None:
                return None
            *masses, n_aoi, n_fix = res
            if n_fix == 0 or target_pos >= n_aoi:
                return None
            peers = [p for p in range(n_aoi)
                     if p != target_pos
                     and entry_by_pos.get(p, float("inf")) > t_star]
            if not peers:
                return None

            def s(vals):
                c = vals[target_pos]
                less = sum(1 for p in peers if vals[p] < c)
                ties = sum(1 for p in peers if vals[p] == c)
                return (less + 0.5 * ties) / len(peers)
            return tuple(s(vals) for vals in masses)

        sc = score_at(ctrl["position"], float(ctrl["entry_t"]))
        sb = score_at(clk["position"], float(clk["entry_t"]))
        if sc is None or sb is None:
            continue
        for j, (_, form) in enumerate(FORMS):
            c_scores[form].append(sc[j])
            b_paired[form].append(sb[j])

    probe_c = {}
    for label, cs, bs in ((form, c_scores[form], b_paired[form])
                          for _, form in FORMS):
        cs = np.asarray(cs, dtype=float)
        bs = np.asarray(bs, dtype=float)
        diffs = bs - cs
        try:
            _, w_p = stats.wilcoxon(diffs, zero_method="wilcox",
                                    alternative="two-sided")
            w_p = float(w_p)
        except ValueError:
            w_p = 1.0
        sd = float(np.std(diffs, ddof=1))
        boot = np.array([np.mean(diffs[RNG.integers(0, len(diffs),
                                                    size=len(diffs))])
                         for _ in range(N_BOOT)])
        probe_c[label] = {
            "n_trials": int(len(cs)),
            "control_mean_score": float(np.mean(cs)),
            "clicked_mean_score_paired": float(np.mean(bs)),
            "mean_b_minus_c": float(np.mean(diffs)),
            "ci_95": [float(np.percentile(boot, 2.5)),
                      float(np.percentile(boot, 97.5))],
            "wilcoxon_p": w_p,
            "cohens_d_z": float(np.mean(diffs)) / sd if sd > 0 else float("nan"),
        }
        print(f"    [{label}] control (next-foveated, non-clicked) beats "
              f"{probe_c[label]['control_mean_score'] * 100:.1f}% of its peers; "
              f"clicked {probe_c[label]['clicked_mean_score_paired'] * 100:.1f}%; "
              f"click-specific delta "
              f"{probe_c[label]['mean_b_minus_c'] * 100:+.1f} pts "
              f"(CI [{probe_c[label]['ci_95'][0] * 100:+.1f}, "
              f"{probe_c[label]['ci_95'][1] * 100:+.1f}]; "
              f"d_z={probe_c[label]['cohens_d_z']:+.2f}; p={probe_c[label]['wilcoxon_p']:.1e})")

    out = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "tags": "[LAB, AdSERP, organic_hybrid]",
        "producer": "scripts/pai_preentry_probe.py",
        "question": ("Does the to-be-clicked result accrue more peripheral "
                     "PAI mass than non-clicked neighbors before its first "
                     "fixation? Binary point-in-AOI dwell is identically 0 "
                     "in this window (AUC floor = 0.5 by construction)."),
        "alpha_forms": {
            "exact": "delivered-demo: clip(1 - sqrt(OGD_boundary/max(CGD,1)) "
                     "* (A_max/A)^lambda), lambda = phi^3",
            "nb35": "abstract-only: clip(1 - OGD_boundary/max(CGD,1))",
            "spec_eq2": "manuscript Eq 2 via pai_spec.rect_alpha_grid: "
                        "clip(1 - sqrt((OGD_vertex/CGD) * min(1, A/A_max)))",
            "spec_listing": "manuscript Listing 1.1 weight placement: "
                            "clip(1 - sqrt(OGD_vertex/CGD) * min(1, A/A_max))",
        },
        "n_trials": len(per_trial),
        "n_records": len(rows_out),
        "paired_tests": tests,
        "probe_b_shared_cutoff": probe_b,
        "probe_c_specificity_control": probe_c,
        "window_asymmetry": win_stat,
        "auc": aucs,
        "descriptives": desc,
    }
    path = OUT_DIR / "pai_preentry_probe.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"  wrote {path}")


if __name__ == "__main__":
    main()
