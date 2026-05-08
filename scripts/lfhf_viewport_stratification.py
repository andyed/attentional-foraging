"""LF/HF × viewport-y stratification — ETTAC-critical check.

The 2026-04-19 ETTAC brief leads with "framework compilation by rank":
  NB14:K10  ρ(LF/HF, position) = −1.000 on P0–P3 position medians
  NB14:K9   steep (P0–P3) vs plateau (P4–P10) MW p = 3.2 × 10⁻²³
  NB14:K3   full-range P0–P10 ρ = −0.927

If LF/HF actually stratifies by **viewport position** (visible vs scrolled-past)
rather than rank, the brief's interpretation is wrong. This script disambiguates:

  Test 1: Partial Spearman(LF/HF, rank | avg_viewport_y)
          If the partial ρ collapses toward 0, rank effect is viewport-mediated.
          If the partial ρ stays strong, rank effect is independent of viewport.

  Test 2: Partial Spearman(LF/HF, avg_viewport_y | rank)
          If partial ρ stays strong after controlling for rank, viewport
          position adds independent signal. If it collapses, viewport effect
          is rank-in-disguise.

  Test 3: Joint run on P0–P3 (the ETTAC steep phase where the brief is
          load-bearing).

Output: scripts/output/lfhf_viewport_stratification/summary.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, rankdata, t as tdist

ROOT = Path(__file__).resolve().parent.parent
LFHF_JSON = ROOT.parent / "pupil-lfhf" / "validation" / "butterworth-lfhf-by-position.json"
VP_JSON = ROOT / "AdSERP/data/viewport-trajectory-features.json"
OUT_DIR = ROOT / "scripts/output/lfhf_viewport_stratification"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_lfhf() -> dict[tuple[str, int], float]:
    data = json.load(open(LFHF_JSON))
    out: dict[tuple[str, int], float] = {}
    for tid, trial in data.items():
        for seg in trial["positions"]:
            v = seg["lfhf"]
            if v is None or not math.isfinite(v):
                continue
            out[(tid, int(seg["pos"]))] = float(v)
    return out


def load_vp() -> dict[tuple[str, int], dict[str, float]]:
    rows = json.load(open(VP_JSON))
    return {(r["trial_id"], int(r["position"])): r for r in rows}


def partial_rank_spearman(x, y, z_list):
    """Spearman partial correlation controlling for rank-transformed covariates."""
    rx = rankdata(x).astype(float)
    ry = rankdata(y).astype(float)
    Z = np.column_stack([rankdata(z).astype(float) for z in z_list])
    Z = np.column_stack([np.ones(len(x)), Z])
    bx, *_ = np.linalg.lstsq(Z, rx, rcond=None)
    by, *_ = np.linalg.lstsq(Z, ry, rcond=None)
    rx_r = rx - Z @ bx
    ry_r = ry - Z @ by
    if rx_r.std() == 0 or ry_r.std() == 0:
        return float("nan"), float("nan")
    rho = float(np.corrcoef(rx_r, ry_r)[0, 1])
    n = len(x)
    if abs(rho) >= 1 or n < 5:
        return rho, 0.0
    df = n - 2 - Z.shape[1] + 1  # approx df for partial
    t = rho * math.sqrt(max(df, 1) / max(1 - rho ** 2, 1e-12))
    p = float(2 * (1 - tdist.cdf(abs(t), df=max(df, 1))))
    return rho, p


def run_tests(rows, tag, out):
    lfhf = np.array([r["lfhf"] for r in rows])
    pos = np.array([r["position"] for r in rows])
    avy = np.array([r["avg_viewport_y"] for r in rows])
    vt_any = np.array([r["vt_any"] for r in rows])
    vt_center = np.array([r["vt_center_ms"] for r in rows])
    print(f"\n== {tag}  (N = {len(rows):,}) ==")

    rho_pos_pool, p_pos_pool = spearmanr(pos, lfhf)
    rho_avy_pool, p_avy_pool = spearmanr(avy, lfhf)
    rho_vta_pool, p_vta_pool = spearmanr(vt_any, lfhf)
    rho_vtc_pool, p_vtc_pool = spearmanr(vt_center, lfhf)
    print(f"  pooled Spearman(LF/HF, position):        ρ = {rho_pos_pool:+.4f}  p = {p_pos_pool:.3g}")
    print(f"  pooled Spearman(LF/HF, avg_viewport_y):  ρ = {rho_avy_pool:+.4f}  p = {p_avy_pool:.3g}")
    print(f"  pooled Spearman(LF/HF, vt_any):          ρ = {rho_vta_pool:+.4f}  p = {p_vta_pool:.3g}")
    print(f"  pooled Spearman(LF/HF, vt_center_ms):    ρ = {rho_vtc_pool:+.4f}  p = {p_vtc_pool:.3g}")

    # Test 1: position | avg_viewport_y
    rho_p_given_avy, p_p_given_avy = partial_rank_spearman(pos, lfhf, [avy])
    # Test 2: avg_viewport_y | position
    rho_avy_given_p, p_avy_given_p = partial_rank_spearman(avy, lfhf, [pos])
    # Test 3: position | {avg_viewport_y, vt_any, vt_center_ms}
    rho_p_given_all, p_p_given_all = partial_rank_spearman(
        pos, lfhf, [avy, vt_any, vt_center]
    )
    # Test 4: each viewport measure | position
    rho_vta_given_p, p_vta_given_p = partial_rank_spearman(vt_any, lfhf, [pos])
    rho_vtc_given_p, p_vtc_given_p = partial_rank_spearman(vt_center, lfhf, [pos])

    print("  -- partial Spearman (rank-residualized) --")
    print(f"    position | avg_viewport_y:              ρ = {rho_p_given_avy:+.4f}  p = {p_p_given_avy:.3g}")
    print(f"    avg_viewport_y | position:              ρ = {rho_avy_given_p:+.4f}  p = {p_avy_given_p:.3g}")
    print(f"    vt_any | position:                      ρ = {rho_vta_given_p:+.4f}  p = {p_vta_given_p:.3g}")
    print(f"    vt_center_ms | position:                ρ = {rho_vtc_given_p:+.4f}  p = {p_vtc_given_p:.3g}")
    print(f"    position | {{avy, vt_any, vt_center}}:    ρ = {rho_p_given_all:+.4f}  p = {p_p_given_all:.3g}")

    out[tag] = {
        "n": len(rows),
        "pooled": {
            "position":       {"rho": float(rho_pos_pool), "p": float(p_pos_pool)},
            "avg_viewport_y": {"rho": float(rho_avy_pool), "p": float(p_avy_pool)},
            "vt_any":         {"rho": float(rho_vta_pool), "p": float(p_vta_pool)},
            "vt_center_ms":   {"rho": float(rho_vtc_pool), "p": float(p_vtc_pool)},
        },
        "partial": {
            "position_given_avg_viewport_y":       {"rho": float(rho_p_given_avy),  "p": float(p_p_given_avy)},
            "avg_viewport_y_given_position":       {"rho": float(rho_avy_given_p),  "p": float(p_avy_given_p)},
            "vt_any_given_position":               {"rho": float(rho_vta_given_p),  "p": float(p_vta_given_p)},
            "vt_center_ms_given_position":         {"rho": float(rho_vtc_given_p),  "p": float(p_vtc_given_p)},
            "position_given_all_viewport":         {"rho": float(rho_p_given_all),  "p": float(p_p_given_all)},
        },
    }


def viewport_tercile_medians(rows, tag, out):
    """Split by avg_viewport_y tercile, report per-position LF/HF medians in each.
    If position gradient persists inside each viewport-y tercile, position is
    not viewport-mediated."""
    avy = np.array([r["avg_viewport_y"] for r in rows])
    q33, q66 = np.percentile(avy, [33.333, 66.667])
    print(f"\n-- avg_viewport_y terciles for '{tag}': <{q33:.0f}  |  {q33:.0f}–{q66:.0f}  |  >{q66:.0f} --")
    by_tercile = defaultdict(lambda: defaultdict(list))
    for r in rows:
        ay = r["avg_viewport_y"]
        if ay < q33:
            tt = "low"
        elif ay < q66:
            tt = "mid"
        else:
            tt = "high"
        by_tercile[tt][r["position"]].append(r["lfhf"])

    out_t = {}
    for tt in ("low", "mid", "high"):
        per_pos = {p: float(np.median(vs)) for p, vs in by_tercile[tt].items() if len(vs) >= 10}
        ps = sorted(per_pos.keys())
        if len(ps) >= 3:
            xs = np.array(ps, dtype=float)
            ys = np.array([per_pos[p] for p in ps])
            rho, p = spearmanr(xs, ys)
        else:
            rho, p = float("nan"), float("nan")
        print(f"    {tt:4s} (N = {sum(len(v) for v in by_tercile[tt].values()):>5,})  "
              f"ρ(pos, LF/HF median) = {rho:+.3f} over {len(ps)} positions")
        out_t[tt] = {
            "n": int(sum(len(v) for v in by_tercile[tt].values())),
            "per_position_median": per_pos,
            "positions_in_sweep": ps,
            "rho_pos_lfhf": float(rho) if rho == rho else None,
            "p": float(p) if p == p else None,
        }
    out[f"{tag}__terciles"] = out_t


def main() -> None:
    print("[load] LF/HF per (trial, pos)")
    lfhf = load_lfhf()
    print(f"       {len(lfhf):,} records")
    print("[load] viewport + trajectory features")
    vp = load_vp()
    print(f"       {len(vp):,} records")

    rows = []
    for key, v in lfhf.items():
        vpf = vp.get(key)
        if vpf is None:
            continue
        row = {"trial_id": key[0], "position": int(key[1]), "lfhf": float(v)}
        for k in ("avg_viewport_y", "vt_any", "vt_center_ms", "vt_top", "vt_bot"):
            row[k] = float(vpf.get(k, 0.0))
        rows.append(row)
    print(f"[join] LF/HF × viewport: {len(rows):,} records")

    out: dict = {"n_joined": len(rows)}

    # Pooled P0–P10
    run_tests(rows, "pooled_P0_P10", out)
    # Steep phase P0–P3 (ETTAC-critical)
    steep = [r for r in rows if r["position"] <= 3]
    run_tests(steep, "steep_P0_P3", out)
    # Plateau P4–P10
    plateau = [r for r in rows if r["position"] >= 4]
    run_tests(plateau, "plateau_P4_P10", out)

    # Tercile splits to see if the rank gradient survives inside viewport-y bins
    viewport_tercile_medians(rows, "pooled_P0_P10", out)
    viewport_tercile_medians(steep, "steep_P0_P3", out)

    # Verdict block
    ss = out["steep_P0_P3"]["partial"]
    print("\n" + "=" * 72)
    print("ETTAC BRIEF VERDICT  (steep phase P0–P3)")
    print("=" * 72)
    print(f"  partial ρ(LF/HF, position | avg_viewport_y): {ss['position_given_avg_viewport_y']['rho']:+.4f}  p = {ss['position_given_avg_viewport_y']['p']:.3g}")
    print(f"  partial ρ(LF/HF, avg_viewport_y | position): {ss['avg_viewport_y_given_position']['rho']:+.4f}  p = {ss['avg_viewport_y_given_position']['p']:.3g}")
    pos_survives = abs(ss["position_given_avg_viewport_y"]["rho"]) > 0.05 and ss["position_given_avg_viewport_y"]["p"] < 0.01
    vp_survives = abs(ss["avg_viewport_y_given_position"]["rho"]) > 0.05 and ss["avg_viewport_y_given_position"]["p"] < 0.01
    if pos_survives and not vp_survives:
        verdict = "POSITION WINS — brief stands, viewport is confounded rank"
    elif vp_survives and not pos_survives:
        verdict = "VIEWPORT WINS — brief needs rewrite, rank is confounded viewport"
    elif pos_survives and vp_survives:
        verdict = "BOTH SURVIVE — position and viewport contribute independently (nuanced dissociation)"
    else:
        verdict = "NEITHER SURVIVES — pooled effect was joint confound; needs deeper analysis"
    print(f"\n  >>> {verdict}")
    out["verdict_steep_P0_P3"] = verdict

    (OUT_DIR / "summary.json").write_text(json.dumps(out, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
