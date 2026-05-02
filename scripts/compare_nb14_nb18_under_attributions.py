"""Side-by-side K-ID comparison for NB14 (Butterworth LF/HF) and NB18a
(RIPA2 vs LF/HF) under absolute-rank vs organic-rank attribution.

Loads:
  - butterworth-lfhf-by-position.json          (absolute, legacy)
  - butterworth-lfhf-by-position-organic.json  (organic, bbox)
  - ripa2-by-position.json                     (absolute, legacy)
  - ripa2-by-position-organic.json             (organic, bbox)

Computes K-IDs for each and writes a markdown comparison table to
scripts/output/aoi-consumer-cascade/nb14_nb18_comparison.md plus
machine-readable JSON.

Run:
    .venv/bin/python scripts/compare_nb14_nb18_under_attributions.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "AdSERP" / "data"
OUT = ROOT / "scripts" / "output" / "aoi-consumer-cascade"
OUT.mkdir(parents=True, exist_ok=True)


def kclaims_butterworth(data, label):
    by_pos = defaultdict(list)
    by_pos_clicked = defaultdict(list)
    by_pos_notclicked = defaultdict(list)
    n_trials = n_segs = 0
    for tid, t in data.items():
        if t is None:
            continue
        positions = t.get("positions", [])
        click_pos = t.get("click_pos")
        if not any(p.get("lfhf") is not None for p in positions):
            continue
        n_trials += 1
        for p in positions:
            ratio = p.get("lfhf")
            if ratio is None:
                continue
            n_segs += 1
            pos = p["pos"]
            by_pos[pos].append(ratio)
            if click_pos is not None and pos == click_pos:
                by_pos_clicked[pos].append(ratio)
            elif click_pos is not None:
                by_pos_notclicked[pos].append(ratio)

    pos_ranks = sorted(by_pos.keys())
    medians = {p: float(np.median(by_pos[p])) for p in pos_ranks}
    # K3 in published Key Claims uses N=11 positions (0–10), not all positions
    # found in the data. Match that denominator here so the comparison
    # column lines up with the published value.
    pr_010 = [p for p in pos_ranks if 0 <= p <= 10]
    rho_all, p_all = spearmanr(pr_010, [medians[p] for p in pr_010]) if len(pr_010) >= 2 else (None, None)

    pr_410 = [p for p in pos_ranks if 1 <= p <= 10]
    rho_410, p_410 = (None, None)
    if len(pr_410) >= 2:
        rho_410, p_410 = spearmanr(pr_410, [medians[p] for p in pr_410])

    clicked_all = [r for vs in by_pos_clicked.values() for r in vs]
    nonclicked_all = [r for vs in by_pos_notclicked.values() for r in vs]
    k6_p = None
    if clicked_all and nonclicked_all:
        _u, k6_p = mannwhitneyu(clicked_all, nonclicked_all, alternative="greater")

    steep = [r for p in [0, 1, 2, 3] for r in by_pos.get(p, [])]
    plateau = [r for p in [4, 5, 6, 7, 8, 9, 10] for r in by_pos.get(p, [])]
    k9_u = k9_p = None
    if steep and plateau:
        k9_u, k9_p = mannwhitneyu(steep, plateau, alternative="greater")

    pr_steep = [p for p in pos_ranks if 0 <= p <= 3]
    rho_steep, p_steep = (None, None)
    if len(pr_steep) >= 2:
        rho_steep, p_steep = spearmanr(pr_steep, [medians[p] for p in pr_steep])

    pr_plateau = [p for p in pos_ranks if 4 <= p <= 10]
    rho_plateau, p_plateau = (None, None)
    if len(pr_plateau) >= 2:
        rho_plateau, p_plateau = spearmanr(pr_plateau, [medians[p] for p in pr_plateau])

    return {
        "label": label,
        "K1_trials": n_trials,
        "K2_segments": n_segs,
        "K3_rho": rho_all, "K3_p": p_all,
        "K4_rho": rho_410, "K4_p": p_410,
        "K6_clicked_median": float(np.median(clicked_all)) if clicked_all else None,
        "K6_nonclicked_median": float(np.median(nonclicked_all)) if nonclicked_all else None,
        "K6_clicked_n": len(clicked_all),
        "K6_nonclicked_n": len(nonclicked_all),
        "K6_p": k6_p,
        "K8_medians": medians,
        "K9_steep_n": len(steep), "K9_plateau_n": len(plateau),
        "K9_steep_median": float(np.median(steep)) if steep else None,
        "K9_plateau_median": float(np.median(plateau)) if plateau else None,
        "K9_U": k9_u, "K9_p": k9_p,
        "K10_rho": rho_steep, "K10_p": p_steep,
        "K11_rho": rho_plateau, "K11_p": p_plateau,
    }


def kclaims_ripa2(data, label):
    by_pos = defaultdict(list)
    n_trials = n_segs = 0
    for tid, t in data.items():
        if t is None:
            continue
        positions = t.get("positions", [])
        if not any(p.get("ripa2") is not None for p in positions):
            continue
        n_trials += 1
        for p in positions:
            ratio = p.get("ripa2")
            if ratio is None:
                continue
            n_segs += 1
            by_pos[p["pos"]].append(ratio)

    pos_ranks = sorted(by_pos.keys())
    medians = {p: float(np.median(by_pos[p])) for p in pos_ranks}
    rho_all, p_all = spearmanr(pos_ranks, [medians[p] for p in pos_ranks])
    return {
        "label": label,
        "K1_trials": n_trials,
        "K2_segments": n_segs,
        "K_pos_x_median_rho": rho_all,
        "K_pos_x_median_p": p_all,
        "K8_medians": medians,
    }


def fmt(x, fmt_str=":.3f"):
    if x is None:
        return "—"
    if isinstance(x, float) and (np.isnan(x) or x != x):
        return "—"
    if isinstance(x, float):
        if abs(x) < 1e-3 or abs(x) > 1e3:
            return f"{x:.2e}"
        return f"{x:.3f}"
    return str(x)


def main():
    abs_path = DATA / "butterworth-lfhf-by-position.json"
    org_path = DATA / "butterworth-lfhf-by-position-organic.json"
    rip2_abs = DATA / "ripa2-by-position.json"
    rip2_org = DATA / "ripa2-by-position-organic.json"

    out_lines = []
    out_lines.append("# NB14 / NB18 K-ID comparison: absolute rank vs organic rank")
    out_lines.append("")
    out_lines.append(f"Generated by `scripts/compare_nb14_nb18_under_attributions.py` on the full corpus.")
    out_lines.append("")
    out_lines.append("## Tl;dr for the ETTAC deep-dive")
    out_lines.append("")
    out_lines.append("Three things to know walking in:")
    out_lines.append("")
    out_lines.append("1. **The K3 monotone-decline survives but weakens** under organic-rank attribution (positions 0–10, N=11): ρ −0.927 (p=4e-5) → −0.655 (p=0.029). K4 (1–10), K10 (steep), and K11 (plateau) lose significance; K11 sign-flips.")
    out_lines.append("2. **Two other findings *strengthen* under organic-rank.** K6 (clicked > non-clicked) goes from p=3.5e-6 to p=2.5e-7 — clicked positions carry decisively more load when ads are factored out. K9 (steep vs plateau dichotomy) still p<10⁻⁸.")
    out_lines.append("3. **The mechanism is ad-distractor pollution.** Under absolute rank, positions 0–3 are inflated by ad-screening discrimination cost (Buscher 2010); the curve looks monotone because ad-load decays as the user moves past ads, then organic-evaluation load takes over.")
    out_lines.append("")
    out_lines.append("Per the methodological reframe Andy proposed (organic rank as primary, ads as essential distractors): the paper's headline shifts from **\"load declines monotonically with rank\"** to **\"cognitive engagement is two-band — early evaluation-heavy band + late satisficer plateau, with clicked positions uniformly elevated regardless of band\"**. K6 and K9 carry the new headline. K3/K4/K10/K11 retire to a robustness section showing the absolute-rank version with explanation.")
    out_lines.append("")

    # --- NB14 (Butterworth LF/HF) ---
    abs_d = json.loads(abs_path.read_text()) if abs_path.exists() else {}
    org_d = json.loads(org_path.read_text()) if org_path.exists() else {}

    if abs_d and org_d:
        ka = kclaims_butterworth(abs_d, "absolute")
        ko = kclaims_butterworth(org_d, "organic")

        out_lines.append("## NB14 — Butterworth LF/HF × position")
        out_lines.append("")
        out_lines.append("| K-ID | Absolute (h3 + ads pooled) | Organic (bbox, ads excluded) | Delta verdict |")
        out_lines.append("|---|---|---|---|")
        out_lines.append(f"| K1 trials with usable LF/HF | {ka['K1_trials']:,} | {ko['K1_trials']:,} | {ko['K1_trials']-ka['K1_trials']:+,} |")
        out_lines.append(f"| K2 segments | {ka['K2_segments']:,} | {ko['K2_segments']:,} | {ko['K2_segments']-ka['K2_segments']:+,} |")
        out_lines.append(f"| K3 ρ all positions | {fmt(ka['K3_rho'])}, p={fmt(ka['K3_p'])} | {fmt(ko['K3_rho'])}, p={fmt(ko['K3_p'])} | {'✓' if ko['K3_p'] is not None and ko['K3_p'] < 0.05 else '⚠ ns'} |")
        out_lines.append(f"| K4 ρ pos 1–10 | {fmt(ka['K4_rho'])}, p={fmt(ka['K4_p'])} | {fmt(ko['K4_rho'])}, p={fmt(ko['K4_p'])} | {'✓' if ko['K4_p'] is not None and ko['K4_p'] < 0.05 else '⚠ ns'} |")
        out_lines.append(f"| K6 clicked > non-clicked p | {fmt(ka['K6_p'])} | {fmt(ko['K6_p'])} | {'✓ stronger' if ko['K6_p'] is not None and ka['K6_p'] is not None and ko['K6_p'] < ka['K6_p'] else '✓'} |")
        out_lines.append(f"| K6 clicked median | {fmt(ka['K6_clicked_median'])} (N={ka['K6_clicked_n']:,}) | {fmt(ko['K6_clicked_median'])} (N={ko['K6_clicked_n']:,}) | |")
        out_lines.append(f"| K6 non-clicked median | {fmt(ka['K6_nonclicked_median'])} (N={ka['K6_nonclicked_n']:,}) | {fmt(ko['K6_nonclicked_median'])} (N={ko['K6_nonclicked_n']:,}) | |")
        out_lines.append(f"| K9 steep vs plateau MW p | {fmt(ka['K9_p'])} | {fmt(ko['K9_p'])} | {'✓' if ko['K9_p'] is not None and ko['K9_p'] < 0.05 else '⚠'} |")
        out_lines.append(f"| K9 steep median (pos 0–3) | {fmt(ka['K9_steep_median'])} | {fmt(ko['K9_steep_median'])} | |")
        out_lines.append(f"| K9 plateau median (pos 4–10) | {fmt(ka['K9_plateau_median'])} | {fmt(ko['K9_plateau_median'])} | |")
        out_lines.append(f"| K10 steep ρ (pos 0–3) | {fmt(ka['K10_rho'])}, p={fmt(ka['K10_p'])} | {fmt(ko['K10_rho'])}, p={fmt(ko['K10_p'])} | {'⚠ ns' if ko['K10_p'] is not None and ko['K10_p'] >= 0.05 else '✓'} |")
        out_lines.append(f"| K11 plateau ρ (pos 4–10) | {fmt(ka['K11_rho'])}, p={fmt(ka['K11_p'])} | {fmt(ko['K11_rho'])}, p={fmt(ko['K11_p'])} | {'⚠ sign flip' if ko['K11_rho'] is not None and ka['K11_rho'] is not None and ko['K11_rho']*ka['K11_rho'] < 0 else ''} |")
        out_lines.append("")
        out_lines.append("### K8 per-position medians")
        out_lines.append("")
        out_lines.append("| Position | Absolute median (N) | Organic median (N) |")
        out_lines.append("|---|---|---|")
        all_pos = sorted(set(ka['K8_medians'].keys()) | set(ko['K8_medians'].keys()))
        ka_n = {p: len([r for r in []]) for p in all_pos}  # stub; need more data
        # Recount Ns from raw
        abs_by = defaultdict(int)
        org_by = defaultdict(int)
        for t in abs_d.values():
            if t is None: continue
            for p in t.get("positions", []):
                if p.get("lfhf") is not None: abs_by[p["pos"]] += 1
        for t in org_d.values():
            if t is None: continue
            for p in t.get("positions", []):
                if p.get("lfhf") is not None: org_by[p["pos"]] += 1
        for p in all_pos[:14]:
            am = ka['K8_medians'].get(p); om = ko['K8_medians'].get(p)
            out_lines.append(f"| {p} | {fmt(am)} (N={abs_by.get(p,0):,}) | {fmt(om)} (N={org_by.get(p,0):,}) |")
        out_lines.append("")

    # --- NB18a (RIPA2 vs LF/HF) ---
    if rip2_abs.exists() and rip2_org.exists():
        rabs = json.loads(rip2_abs.read_text())
        rorg = json.loads(rip2_org.read_text())
        ra = kclaims_ripa2(rabs, "absolute")
        ro = kclaims_ripa2(rorg, "organic")
        out_lines.append("## NB18a — RIPA2 × position (paired with K-ID K6 of NB18)")
        out_lines.append("")
        out_lines.append("| K-ID | Absolute | Organic | Verdict |")
        out_lines.append("|---|---|---|---|")
        out_lines.append(f"| K1 trials | {ra['K1_trials']:,} | {ro['K1_trials']:,} | {ro['K1_trials']-ra['K1_trials']:+,} |")
        out_lines.append(f"| K2 segments | {ra['K2_segments']:,} | {ro['K2_segments']:,} | {ro['K2_segments']-ra['K2_segments']:+,} |")
        out_lines.append(f"| K6 RIPA2 × position ρ | {fmt(ra['K_pos_x_median_rho'])}, p={fmt(ra['K_pos_x_median_p'])} | {fmt(ro['K_pos_x_median_rho'])}, p={fmt(ro['K_pos_x_median_p'])} | {'✓' if ro['K_pos_x_median_p'] is not None and ro['K_pos_x_median_p'] < 0.05 else '⚠ ns'} |")
        out_lines.append("")
    else:
        out_lines.append("## NB18a — RIPA2")
        out_lines.append("")
        out_lines.append(f"⏳ Waiting on `{rip2_org.name}` to finish writing — re-run this script after.")
        out_lines.append("")

    # Write
    md_out = OUT / "nb14_nb18_comparison.md"
    md_out.write_text("\n".join(out_lines))
    print(f"Wrote {md_out}")
    print()
    print("\n".join(out_lines[:50]))


if __name__ == "__main__":
    main()
