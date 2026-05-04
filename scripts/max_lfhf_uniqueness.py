"""Test two within-trial uniqueness hypotheses on regression / refind behavior:

Hypothesis A (max-LF/HF uniqueness, Andy 2026-05-02): the position
holding the trial's max LF/HF is the peak-load moment; if it's where
cognitive resources commit, it should be disproportionately the click
or regression target.

Hypothesis B (content uniqueness, Andy 2026-05-02): "more unique
results are easier to refind." A position whose content is more
distinct from other results on the same SERP carries a more
distinctive memory trace; distinctive traces should be easier to
retrieve, so the user is more likely to regress back to a unique
position than to a typical one.

Inputs (under [organic] attribution):
  butterworth-lfhf-by-position-organic.json   (per-(trial, pos) median LF/HF)
  content-features-by-position-organic.json    (per-(trial, pos) snippet/embedding features)
  serp-embeddings.json                          (raw embeddings; for content-uniqueness)
  regression_labels_cache_organic.json          (will_regress, parallel to features)
  cursor-approach-features-organic.json         (was_clicked, parallel to labels)

Outputs:
  scripts/output/aoi-consumer-cascade/max_lfhf_uniqueness.json + stdout

Run:
  .venv/bin/python scripts/max_lfhf_uniqueness.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent

LFHF_PATH = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json'
FEAT_PATH = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
REG_PATH = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'


def main():
    print('[load]', file=sys.stderr)
    lfhf = json.load(open(LFHF_PATH))
    features = json.load(open(FEAT_PATH))
    will_regress = json.load(open(REG_PATH))
    assert len(features) == len(will_regress)

    # Index click + will_regress per (trial, position)
    click_by_tp: dict[tuple[str, int], bool] = {}
    regress_by_tp: dict[tuple[str, int], bool] = {}
    for r, wr in zip(features, will_regress):
        key = (r['trial_id'], int(r['position']))
        click_by_tp[key] = bool(r.get('was_clicked', False))
        regress_by_tp[key] = bool(wr)

    # Per trial: identify max-LFHF position
    max_lfhf_pos: dict[str, int | None] = {}
    n_trials_with_lfhf = 0
    for tid, entry in lfhf.items():
        positions = entry.get('positions', [])
        valid = [p for p in positions if p.get('lfhf') is not None and p['lfhf'] == p['lfhf']]
        if not valid:
            continue
        max_p = max(valid, key=lambda p: p['lfhf'])
        max_lfhf_pos[tid] = int(max_p['pos'])
        n_trials_with_lfhf += 1

    print(f'  trials with valid LF/HF data: {n_trials_with_lfhf:,}', file=sys.stderr)

    # ── Test 1: P(click on max-LFHF) vs P(click on other positions) ──
    # Walk records. For each record, classify whether its position is
    # the max-LFHF position for its trial. Tally clicks.
    n_max_records = 0; n_max_click = 0
    n_other_records = 0; n_other_click = 0
    n_max_regress = 0; n_other_regress = 0
    for (tid, pos), clicked in click_by_tp.items():
        if tid not in max_lfhf_pos:
            continue
        is_max = (pos == max_lfhf_pos[tid])
        wr = regress_by_tp.get((tid, pos), False)
        if is_max:
            n_max_records += 1
            if clicked: n_max_click += 1
            if wr: n_max_regress += 1
        else:
            n_other_records += 1
            if clicked: n_other_click += 1
            if wr: n_other_regress += 1

    p_click_max = n_max_click / max(n_max_records, 1)
    p_click_other = n_other_click / max(n_other_records, 1)
    p_regress_max = n_max_regress / max(n_max_records, 1)
    p_regress_other = n_other_regress / max(n_other_records, 1)

    # Two-proportion z-tests
    def two_prop_z(k1, n1, k2, n2):
        p1 = k1 / max(n1, 1); p2 = k2 / max(n2, 1)
        p_pool = (k1 + k2) / max(n1 + n2, 1)
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2)) if n1 > 0 and n2 > 0 else 0.0
        z = (p1 - p2) / se if se > 0 else 0.0
        p_two = 2 * (1 - stats.norm.cdf(abs(z)))
        return float(z), float(p_two), float(100 * (p1 - p2))

    z_click, p_click, delta_click = two_prop_z(n_max_click, n_max_records, n_other_click, n_other_records)
    z_reg, p_reg, delta_reg = two_prop_z(n_max_regress, n_max_records, n_other_regress, n_other_records)

    print('\n=== Test 1: P(click | is_max_lfhf_pos) vs P(click | other) ===')
    print(f'  max-LFHF positions:    n={n_max_records:>5,}  click rate={100*p_click_max:>5.1f}%')
    print(f'  other positions:       n={n_other_records:>5,}  click rate={100*p_click_other:>5.1f}%')
    print(f'  Δ = {delta_click:+.1f} pp;  z = {z_click:+.2f};  p = {p_click:.3e}')

    print('\n=== Test 2: P(regress | is_max_lfhf_pos) vs P(regress | other) ===')
    print(f'  max-LFHF positions:    n={n_max_records:>5,}  regress rate={100*p_regress_max:>5.1f}%')
    print(f'  other positions:       n={n_other_records:>5,}  regress rate={100*p_regress_other:>5.1f}%')
    print(f'  Δ = {delta_reg:+.1f} pp;  z = {z_reg:+.2f};  p = {p_reg:.3e}')

    # ── Test 3: variance reduction — within-trial LFHF deviation from max ──
    # Compute σ(lfhf) per trial vs σ(lfhf - max_lfhf) per trial; the second
    # should have smaller per-trial variance if max-pivot is informative.
    raw_sds = []; deviation_sds = []
    for tid, entry in lfhf.items():
        valid = [p for p in entry.get('positions', []) if p.get('lfhf') is not None and p['lfhf'] == p['lfhf']]
        if len(valid) < 3:
            continue
        vals = np.array([p['lfhf'] for p in valid], dtype=float)
        max_v = vals.max()
        raw_sds.append(float(np.std(vals, ddof=1)))
        deviation_sds.append(float(np.std(max_v - vals, ddof=1)))
    raw_sds = np.array(raw_sds); deviation_sds = np.array(deviation_sds)

    # By construction these are equal (both = std(vals)) — a substantive
    # variance-reduction test needs a different framing. Try: per-trial
    # range of LFHF (max - min) — if max position is unique, range is
    # informative; otherwise mean-deviation is.
    ranges = []
    for tid, entry in lfhf.items():
        vals = [p['lfhf'] for p in entry.get('positions', []) if p.get('lfhf') is not None and p['lfhf'] == p['lfhf']]
        if len(vals) < 3:
            continue
        ranges.append(max(vals) - min(vals))
    ranges = np.array(ranges)

    # ── Test 4: Within-trial relative-rank position ──
    # Compute for each (trial, pos): LFHF rank within the trial (1 = max,
    # n = min). Test whether click rate / regress rate decay with rank.
    rank_buckets = defaultdict(lambda: {'n': 0, 'click': 0, 'regress': 0})
    for tid, entry in lfhf.items():
        valid = [p for p in entry.get('positions', []) if p.get('lfhf') is not None and p['lfhf'] == p['lfhf']]
        if not valid:
            continue
        sorted_pos = sorted(valid, key=lambda p: -p['lfhf'])
        for rank, p in enumerate(sorted_pos, start=1):
            key = (tid, int(p['pos']))
            if key not in click_by_tp:
                continue
            rank_buckets[rank]['n'] += 1
            if click_by_tp[key]: rank_buckets[rank]['click'] += 1
            if regress_by_tp.get(key, False): rank_buckets[rank]['regress'] += 1

    print('\n=== Test 3: within-trial LF/HF rank → click & regress rates ===')
    print(f'  {"rank":>4s}  {"n":>6s}  {"click rate":>11s}  {"regress rate":>13s}')
    rank_table = []
    for rank in sorted(rank_buckets.keys())[:8]:
        b = rank_buckets[rank]
        n = b['n']
        c = 100 * b['click'] / max(n, 1)
        r = 100 * b['regress'] / max(n, 1)
        print(f'  {rank:>4d}  {n:>6,}  {c:>10.1f}%  {r:>12.1f}%')
        rank_table.append({'rank': rank, 'n': n, 'click_rate_pp': c, 'regress_rate_pp': r})

    # ──────────────────────────────────────────────────────────
    # Hypothesis B: content uniqueness → refind ease
    # ──────────────────────────────────────────────────────────
    print('\n[load] serp-embeddings + content-features-organic for content uniqueness', file=sys.stderr)
    serp_emb = json.load(open(ROOT / 'AdSERP/data/serp-embeddings.json'))
    content_org = json.load(open(ROOT / 'AdSERP/data/content-features-by-position-organic.json'))

    # Per (trial, organic_pos): compute "content uniqueness" = 1 - mean
    # cosine similarity between this result's embedding and the other
    # organic-result embeddings in the same trial. Maps absolute-rank
    # h3 source position via content-features-organic 'source_h3_pos'.

    org_pos_to_h3: dict[tuple[str, int], int] = {}
    for tid, t in content_org.items():
        for r in t.get('positions', []):
            if 'source_h3_pos' in r:
                org_pos_to_h3[(tid, int(r['pos']))] = int(r['source_h3_pos'])

    def cosine_np(a: np.ndarray, b: np.ndarray) -> float:
        na = float(np.linalg.norm(a)); nb = float(np.linalg.norm(b))
        if na < 1e-9 or nb < 1e-9: return 0.0
        return float((a / na) @ (b / nb))

    # uniqueness_by_tp[(tid, organic_pos)] = 1 - mean cosine to other organics
    uniqueness_by_tp: dict[tuple[str, int], float] = {}
    n_uniq_trials = 0
    for tid, results in serp_emb.items():
        # Restrict to organic h3s (those that appear in content-features-organic)
        organic_pairs = [(p, h3) for (t, p), h3 in org_pos_to_h3.items() if t == tid]
        if len(organic_pairs) < 2:
            continue
        # Build h3_pos → embedding map for this trial
        h3_to_emb = {}
        for r in results:
            h3 = int(r.get('position', -1))
            emb = r.get('embedding')
            if emb is None: continue
            h3_to_emb[h3] = np.asarray(emb, dtype=np.float32)
        # Compute uniqueness per organic position: 1 - mean cosine to all other organics
        organic_pairs_with_emb = [(p, h3) for p, h3 in organic_pairs if h3 in h3_to_emb]
        if len(organic_pairs_with_emb) < 2:
            continue
        for org_pos, h3 in organic_pairs_with_emb:
            this_emb = h3_to_emb[h3]
            sims = []
            for other_pos, other_h3 in organic_pairs_with_emb:
                if other_pos == org_pos: continue
                sims.append(cosine_np(this_emb, h3_to_emb[other_h3]))
            if not sims: continue
            mean_sim = float(np.mean(sims))
            uniqueness_by_tp[(tid, org_pos)] = 1.0 - mean_sim
        n_uniq_trials += 1

    print(f'  uniqueness computed for {len(uniqueness_by_tp):,} positions across {n_uniq_trials:,} trials', file=sys.stderr)

    # Stratify uniqueness by quartile and report regress / click rates
    uniq_records = []
    for (tid, pos), u in uniqueness_by_tp.items():
        if (tid, pos) not in click_by_tp: continue
        clicked = click_by_tp[(tid, pos)]
        wr = regress_by_tp.get((tid, pos), False)
        uniq_records.append((u, clicked, wr))
    if not uniq_records:
        print('  no uniqueness records; skipping')
        out_uniq = None
    else:
        u_arr = np.array([r[0] for r in uniq_records])
        c_arr = np.array([r[1] for r in uniq_records], dtype=int)
        r_arr = np.array([r[2] for r in uniq_records], dtype=int)
        # Quartile bins
        q1, q2, q3 = np.percentile(u_arr, [25, 50, 75])
        bins = []
        for label, mask in [
            ('Q1 (least unique)', u_arr <= q1),
            ('Q2',                 (u_arr > q1) & (u_arr <= q2)),
            ('Q3',                 (u_arr > q2) & (u_arr <= q3)),
            ('Q4 (most unique)',  u_arr > q3),
        ]:
            n = int(mask.sum())
            if n == 0: continue
            click_rate = 100 * c_arr[mask].mean()
            regress_rate = 100 * r_arr[mask].mean()
            bins.append({'label': label, 'n': n, 'click_rate_pp': float(click_rate),
                         'regress_rate_pp': float(regress_rate)})
        print('\n=== Hypothesis B: content uniqueness × refind / click rates ===')
        print('Uniqueness = 1 - mean(cosine to other organics in the same trial)')
        print(f'  {"bin":>22s}  {"n":>6s}  {"click rate":>11s}  {"regress rate":>13s}')
        for b in bins:
            print(f'  {b["label"]:>22s}  {b["n"]:>6,}  {b["click_rate_pp"]:>10.1f}%  {b["regress_rate_pp"]:>12.1f}%')

        # Spearman correlation
        rho_c, p_c = stats.spearmanr(u_arr, c_arr)
        rho_r, p_r = stats.spearmanr(u_arr, r_arr)
        print(f'\n  Spearman ρ(uniqueness, clicked):  {rho_c:+.3f}  p = {p_c:.3e}')
        print(f'  Spearman ρ(uniqueness, regressed): {rho_r:+.3f}  p = {p_r:.3e}')

        out_uniq = {
            'n_records': len(uniq_records),
            'n_trials': n_uniq_trials,
            'rho_uniqueness_click': float(rho_c), 'p_uniqueness_click': float(p_c),
            'rho_uniqueness_regress': float(rho_r), 'p_uniqueness_regress': float(p_r),
            'quartile_bins': bins,
        }

    # Save
    out = {
        'attribution': 'organic',
        'n_trials_with_lfhf': n_trials_with_lfhf,
        'click_uniqueness': {
            'n_max_lfhf_positions': n_max_records,
            'n_max_clicks': n_max_click,
            'p_click_max_pp': 100 * p_click_max,
            'n_other_positions': n_other_records,
            'n_other_clicks': n_other_click,
            'p_click_other_pp': 100 * p_click_other,
            'delta_pp': delta_click,
            'z': z_click,
            'p_value': p_click,
        },
        'regress_uniqueness': {
            'n_max_lfhf_positions': n_max_records,
            'n_max_regress': n_max_regress,
            'p_regress_max_pp': 100 * p_regress_max,
            'n_other_positions': n_other_records,
            'n_other_regress': n_other_regress,
            'p_regress_other_pp': 100 * p_regress_other,
            'delta_pp': delta_reg,
            'z': z_reg,
            'p_value': p_reg,
        },
        'within_trial_rank_decay': rank_table,
        'per_trial_lfhf_range': {
            'n_trials': len(ranges),
            'mean': float(ranges.mean()) if len(ranges) else None,
            'median': float(np.median(ranges)) if len(ranges) else None,
            'p25': float(np.percentile(ranges, 25)) if len(ranges) else None,
            'p75': float(np.percentile(ranges, 75)) if len(ranges) else None,
        },
        'content_uniqueness': out_uniq,
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/max_lfhf_uniqueness.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
