"""R1 will-regress dissociation under typed attribution.

Re-runs the R1 dissociation test (will-regress vs no-regress, per-(trial, pos))
on per-position LF/HF and RIPA2 under the typed cascade. Companion to
r1_intersection_sensitivity.py which compared absolute vs organic.

Output: prints to stderr; writes JSON summary to scripts/output/r1_under_typed/.

Run:
  .venv/bin/python scripts/r1_under_typed.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]

LFHF_TYPED = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-typed.json'
RIPA2_TYPED = ROOT / 'AdSERP/data/ripa2-by-position-typed.json'
EVR_PATH = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'

OUT_DIR = ROOT / 'scripts/output/r1_under_typed'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def cohens_d(a, b):
    a, b = np.asarray(a), np.asarray(b)
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def assemble_records(lfhf_data, ripa2_data, evr_data):
    records = []
    for tid, et in evr_data.items():
        if tid not in lfhf_data or tid not in ripa2_data:
            continue
        lfhf_t = {p['pos']: p['lfhf'] for p in lfhf_data[tid]['positions']
                  if p['lfhf'] is not None}
        ripa2_t = {p['pos']: p['ripa2'] for p in ripa2_data[tid]['positions']
                   if p.get('ripa2') is not None}
        wr_by_pos = {fp['pos']: fp.get('will_regress', False)
                     for fp in et.get('first_pass', [])}
        for pos in set(lfhf_t) & set(ripa2_t) & set(wr_by_pos):
            records.append((lfhf_t[pos], ripa2_t[pos], wr_by_pos[pos]))
    return (np.array([r[0] for r in records]),
            np.array([r[1] for r in records]),
            np.array([r[2] for r in records], dtype=bool))


def run_test(lfhf, ripa2, wr, label):
    n_wr = int(wr.sum())
    n_nr = int((~wr).sum())
    lf_d = cohens_d(lfhf[wr], lfhf[~wr])
    rp_d = cohens_d(ripa2[wr], ripa2[~wr])
    _, lf_p = stats.mannwhitneyu(lfhf[wr], lfhf[~wr], alternative='two-sided')
    _, rp_p = stats.mannwhitneyu(ripa2[wr], ripa2[~wr], alternative='two-sided')
    print(f"=== {label} ===", file=sys.stderr)
    print(f"  records: n={len(wr):,}  (wr={n_wr:,}, nr={n_nr:,})", file=sys.stderr)
    print(f"  LF/HF : d={lf_d:+.3f}  p={lf_p:.3e}", file=sys.stderr)
    print(f"  RIPA2 : d={rp_d:+.3f}  p={rp_p:.3e}", file=sys.stderr)
    return {
        'label': label,
        'n_records': int(len(wr)), 'n_wr': n_wr, 'n_nr': n_nr,
        'lfhf': {'d': float(lf_d), 'p': float(lf_p),
                 'median_wr': float(np.median(lfhf[wr])),
                 'median_nr': float(np.median(lfhf[~wr]))},
        'ripa2': {'d': float(rp_d), 'p': float(rp_p),
                  'median_wr': float(np.median(ripa2[wr])),
                  'median_nr': float(np.median(ripa2[~wr]))},
    }


def main():
    print("Loading typed JSONs...", file=sys.stderr)
    lfhf = json.load(open(LFHF_TYPED))
    ripa2 = json.load(open(RIPA2_TYPED))
    evr = json.load(open(EVR_PATH))

    print(f"  LF/HF trials   : {len(lfhf):,}", file=sys.stderr)
    print(f"  RIPA2 trials   : {len(ripa2):,}", file=sys.stderr)
    print(f"  EVR trials     : {len(evr):,}", file=sys.stderr)
    print(f"  intersection   : {len(set(lfhf) & set(ripa2) & set(evr)):,}",
          file=sys.stderr)
    print("", file=sys.stderr)

    result = run_test(*assemble_records(lfhf, ripa2, evr), label='TYPED (full)')

    # Compare to the absolute and organic baselines documented in
    # r1-ripa2-bbox-collapse.md
    historical = {
        'absolute_legacy': {
            'lfhf': {'d': +0.041, 'p': 0.011},
            'ripa2': {'d': +0.006, 'p': 0.0058},
            'note': 'Pre-cascade (legacy absolute attribution).',
        },
        'organic_bbox': {
            'lfhf': {'d': '+0.069 (computed)', 'p': 1.1e-3},
            'ripa2': {'d': '~0', 'p': 0.80},
            'note': 'bbox-organic post-cascade (2026-05-02).',
        },
    }
    summary = {
        'date': '2026-05-04',
        'attribution': 'typed',
        'historical_baselines': historical,
        'typed_result': result,
    }
    out_path = OUT_DIR / 'r1_under_typed.json'
    json.dump(summary, open(out_path, 'w'), indent=2)
    print(f"\nWrote {out_path}", file=sys.stderr)

    # Verdict
    print("\n" + "=" * 60, file=sys.stderr)
    print("VERDICT vs prior attributions", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  LF/HF leg : absolute p=0.011 → bbox p=1.1e-3 → typed p={result['lfhf']['p']:.3e}",
          file=sys.stderr)
    print(f"  RIPA2 leg : absolute p=0.0058 → bbox p=0.80 → typed p={result['ripa2']['p']:.3e}",
          file=sys.stderr)
    if result['ripa2']['p'] > 0.05 and result['lfhf']['p'] < 0.01:
        print("\n  → Typed REPLICATES bbox-organic split: LF/HF survives,",
              file=sys.stderr)
        print("    RIPA2 still null. The 'rank-pooling artifact' reading holds.",
              file=sys.stderr)
    elif result['ripa2']['p'] < 0.05 and result['lfhf']['p'] < 0.01:
        print("\n  → BOTH legs significant under typed. Re-evaluate the",
              file=sys.stderr)
        print("    rank-pooling-artifact framing.", file=sys.stderr)
    else:
        print(f"\n  → MIXED. Inspect numbers above.", file=sys.stderr)


if __name__ == '__main__':
    main()
