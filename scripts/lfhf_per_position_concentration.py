"""Participant-concentration audit for NB14 per-position LF/HF (ETTAC queue item 1).

Motivated by the NB28 viewport-bands P6+ audit pattern. The NB14:K11 plateau
(P4–P10) ρ = −0.714, *p* = 0.071 is a marginal-p claim. If the estimate is
driven by a small number of participants contributing the bulk of segments
at deeper positions, the "plateau" framing is small-n rather than a
population-level shape. If participants are balanced, the marginal *p* is
just low N (7 positions) and the shape is real.

Unit: position × participant × segment medians from NB14 (K2 = 6,112
segments post-2026-04-12 coord audit).

Data source: pupil-lfhf/validation/butterworth-lfhf-by-position.json
(per-trial JSON; trial_id = pXXX-bY-tZ, participant = first 4 chars).

Outputs:
  - scripts/output/lfhf_per_position_concentration/concentration.json
  - scripts/output/lfhf_per_position_concentration/cap_sensitivity.json

Run:
    uv run python3 scripts/lfhf_per_position_concentration.py
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
OUT_DIR = ROOT / 'scripts' / 'output' / 'lfhf_per_position_concentration'
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_BOOTSTRAP = 2000
RNG_SEED = 2026
CAPS = [3, 5, 10, 20, None]  # None = no cap (baseline)
POSITIONS = list(range(11))  # 0..10
STEEP = list(range(0, 4))     # P0–P3
PLATEAU = list(range(4, 11))  # P4–P10


def load_segments() -> dict[int, list[tuple[str, float]]]:
    """Return {pos: [(participant, lfhf), ...]} over all valid segments."""
    data = json.load(open(LFHF_JSON))
    by_pos: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for trial_id, trial in data.items():
        part = trial_id.split('-')[0]  # e.g. 'p004'
        for seg in trial['positions']:
            if seg['lfhf'] is None:
                continue
            pos = seg['pos']
            by_pos[pos].append((part, float(seg['lfhf'])))
    return dict(by_pos)


def concentration_stats(pairs: list[tuple[str, float]]) -> dict:
    """Top-N share, Gini, N_participants for a position's segment list."""
    per_part: dict[str, int] = defaultdict(int)
    for part, _ in pairs:
        per_part[part] += 1
    counts = sorted(per_part.values(), reverse=True)
    total = sum(counts)
    n_parts = len(counts)
    counts_arr = np.array(counts, dtype=float)
    # Gini on participant counts
    if n_parts > 1:
        sorted_c = np.sort(counts_arr)
        idx = np.arange(1, n_parts + 1)
        gini = (2.0 * np.sum(idx * sorted_c) - (n_parts + 1) * sorted_c.sum()) / (n_parts * sorted_c.sum())
    else:
        gini = 0.0

    def top_share(k: int) -> float:
        return float(sum(counts[:k]) / total) if total else 0.0

    return {
        'n_segments': total,
        'n_participants': n_parts,
        'max_share': float(counts[0] / total) if total else 0.0,
        'top4_share': top_share(4),
        'top6_share': top_share(6),
        'top10_share': top_share(10),
        'gini': float(gini),
        'mean_per_participant': float(total / n_parts) if n_parts else 0.0,
        'median_per_participant': float(np.median(counts)) if counts else 0.0,
    }


def cap_participant_segments(
    pairs: list[tuple[str, float]],
    cap: int | None,
    rng: np.random.Generator,
) -> list[float]:
    """Return LF/HF values after capping per-participant count (random subsample)."""
    if cap is None:
        return [v for _, v in pairs]
    per_part: dict[str, list[float]] = defaultdict(list)
    for part, v in pairs:
        per_part[part].append(v)
    out: list[float] = []
    for part, values in per_part.items():
        if len(values) <= cap:
            out.extend(values)
        else:
            idx = rng.choice(len(values), size=cap, replace=False)
            out.extend([values[i] for i in idx])
    return out


def position_medians(by_pos: dict[int, list[tuple[str, float]]], cap: int | None,
                     rng: np.random.Generator, positions: list[int]) -> dict[int, float]:
    meds: dict[int, float] = {}
    for pos in positions:
        vals = cap_participant_segments(by_pos.get(pos, []), cap, rng)
        if vals:
            meds[pos] = float(np.median(vals))
    return meds


def spearman_over_positions(meds: dict[int, float], positions: list[int]) -> tuple[float, float, int]:
    xs, ys = [], []
    for p in positions:
        if p in meds:
            xs.append(p); ys.append(meds[p])
    if len(xs) < 3:
        return float('nan'), float('nan'), len(xs)
    rho, p = spearmanr(xs, ys)
    return float(rho), float(p), len(xs)


def bootstrap_spearman(by_pos: dict[int, list[tuple[str, float]]], cap: int | None,
                       positions: list[int], n_boot: int, rng: np.random.Generator) -> dict:
    """Participant-cluster bootstrap over cap-applied medians → Spearman on medians."""
    all_parts = sorted({part for pairs in by_pos.values() for part, _ in pairs})
    rhos = np.empty(n_boot)
    rhos.fill(np.nan)
    for b in range(n_boot):
        resample = set(rng.choice(all_parts, size=len(all_parts), replace=True))
        # build by_pos restricted to resampled participants
        sub: dict[int, list[tuple[str, float]]] = {}
        for pos, pairs in by_pos.items():
            sub[pos] = [(p, v) for p, v in pairs if p in resample]
        meds = position_medians(sub, cap, rng, positions)
        rho, _, _ = spearman_over_positions(meds, positions)
        rhos[b] = rho
    rhos = rhos[~np.isnan(rhos)]
    if len(rhos) == 0:
        return {'median': None, 'lo': None, 'hi': None, 'n_boot_valid': 0}
    return {
        'median': float(np.median(rhos)),
        'lo': float(np.percentile(rhos, 2.5)),
        'hi': float(np.percentile(rhos, 97.5)),
        'n_boot_valid': int(len(rhos)),
    }


def main() -> None:
    print(f'[concentration] loading {LFHF_JSON}')
    by_pos = load_segments()

    # ── Pass 1: per-position concentration stats ────────────────────────────
    conc = {}
    total_seg = 0
    for pos in POSITIONS:
        pairs = by_pos.get(pos, [])
        conc[pos] = concentration_stats(pairs)
        total_seg += conc[pos]['n_segments']
    print(f'[concentration] total valid segments across P0–P10: {total_seg} (NB14:K2 = 6,112)')
    for pos in POSITIONS:
        c = conc[pos]
        print(f'  P{pos}: n_seg={c["n_segments"]:>4d}  n_part={c["n_participants"]:>3d}  '
              f'top4={c["top4_share"]:.2%}  top6={c["top6_share"]:.2%}  top10={c["top10_share"]:.2%}  '
              f'max={c["max_share"]:.2%}  gini={c["gini"]:.3f}')

    # ── Pass 2: cap sensitivity on medians — point estimates ────────────────
    print('\n[cap-sensitivity] position medians and Spearman ρ per cap')
    rng = np.random.default_rng(RNG_SEED)
    cap_results: dict[str, dict] = {}
    for cap in CAPS:
        key = 'uncapped' if cap is None else f'cap{cap}'
        rng_cap = np.random.default_rng(RNG_SEED + (cap or 0))
        meds_all = position_medians(by_pos, cap, rng_cap, POSITIONS)
        rho_full, p_full, n_full = spearman_over_positions(meds_all, POSITIONS)
        rho_steep, p_steep, n_steep = spearman_over_positions(meds_all, STEEP)
        rho_plat, p_plat, n_plat = spearman_over_positions(meds_all, PLATEAU)
        cap_results[key] = {
            'medians': {str(p): meds_all.get(p) for p in POSITIONS},
            'full_P0_P10':   {'rho': rho_full,  'p': p_full,  'n_points': n_full},
            'steep_P0_P3':   {'rho': rho_steep, 'p': p_steep, 'n_points': n_steep},
            'plateau_P4_P10':{'rho': rho_plat,  'p': p_plat,  'n_points': n_plat},
        }
        print(f'  {key:>9s}: full ρ={rho_full:+.3f} (p={p_full:.3g})  '
              f'steep ρ={rho_steep:+.3f} (p={p_steep:.3g})  '
              f'plateau ρ={rho_plat:+.3f} (p={p_plat:.3g})')

    # ── Pass 3: participant-cluster bootstrap CIs on plateau & steep ────────
    print(f'\n[bootstrap] n={N_BOOTSTRAP} participant-cluster resamples per cap')
    boot_results: dict[str, dict] = {}
    for cap in CAPS:
        key = 'uncapped' if cap is None else f'cap{cap}'
        rng_b = np.random.default_rng(RNG_SEED + 100 + (cap or 0))
        boot_results[key] = {
            'full_P0_P10':    bootstrap_spearman(by_pos, cap, POSITIONS, N_BOOTSTRAP, rng_b),
            'steep_P0_P3':    bootstrap_spearman(by_pos, cap, STEEP,     N_BOOTSTRAP, rng_b),
            'plateau_P4_P10': bootstrap_spearman(by_pos, cap, PLATEAU,   N_BOOTSTRAP, rng_b),
        }
        b = boot_results[key]
        print(f'  {key:>9s}: full ρ median={b["full_P0_P10"]["median"]:+.3f} '
              f'[{b["full_P0_P10"]["lo"]:+.3f}, {b["full_P0_P10"]["hi"]:+.3f}]  '
              f'steep [{b["steep_P0_P3"]["lo"]:+.3f}, {b["steep_P0_P3"]["hi"]:+.3f}]  '
              f'plateau [{b["plateau_P4_P10"]["lo"]:+.3f}, {b["plateau_P4_P10"]["hi"]:+.3f}]')

    # ── Write outputs ───────────────────────────────────────────────────────
    conc_out = OUT_DIR / 'concentration.json'
    cap_out = OUT_DIR / 'cap_sensitivity.json'
    boot_out = OUT_DIR / 'bootstrap_results.json'
    conc_out.write_text(json.dumps({str(k): v for k, v in conc.items()}, indent=2))
    cap_out.write_text(json.dumps(cap_results, indent=2))
    boot_out.write_text(json.dumps(boot_results, indent=2))
    print(f'\n[out] {conc_out.relative_to(ROOT)}')
    print(f'[out] {cap_out.relative_to(ROOT)}')
    print(f'[out] {boot_out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
