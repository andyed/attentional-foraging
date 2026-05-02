"""R1 RIPA2/LF/HF will-regress dissociation: intersection-of-trials sensitivity.

Decides whether the bbox-cascade R1 RIPA2 collapse (legacy absolute p=0.0058 →
bbox p=0.80) is dilution (cleaner attribution destroying signal that lived in
rank-pooling) or selection (the trials we drop under bbox were where the signal
lived).

Method:
  1. Find trial set present in BOTH absolute and bbox attributions
  2. Run the R1 dissociation test under each method, restricted to that
     intersection trial set
  3. Compare effect sizes and p-values

Reading:
  - If absolute on intersection still p≈0.005 → bbox attribution is destroying
    real signal → the legacy positive result was rank-pooling artifact
  - If absolute on intersection ≈ bbox → trials we drop carried the signal
    (selection)
  - Mixed → both effects contribute

Run:
  .venv/bin/python scripts/r1_intersection_sensitivity.py
"""
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]

# Absolute (legacy)
LFHF_ABS = ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json'
RIPA2_ABS = ROOT / 'AdSERP/data/ripa2-by-position.json'

# Bbox-organic (cascade)
LFHF_ORG = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json'
RIPA2_ORG = ROOT / 'AdSERP/data/ripa2-by-position-organic.json'

# Encoding-vs-retrieval is the canonical will-regress source under absolute
# (NB22 gaze-regression-detector output, per-(trial, pos))
EVR_PATH = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'


def cohens_d(a, b):
    a, b = np.asarray(a), np.asarray(b)
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def assemble_records(lfhf_data, ripa2_data, evr_data, trial_filter=None):
    """Return parallel (lfhf, ripa2, wr) arrays for trials in trial_filter
    (or all trials if filter is None) where all three sources have data."""
    records = []
    for tid, et in evr_data.items():
        if trial_filter is not None and tid not in trial_filter:
            continue
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
    if not records:
        return np.array([]), np.array([]), np.array([], dtype=bool)
    return (np.array([r[0] for r in records]),
            np.array([r[1] for r in records]),
            np.array([r[2] for r in records], dtype=bool))


def run_test(lfhf, ripa2, wr, label):
    n_wr = int(wr.sum())
    n_nr = int((~wr).sum())
    if n_wr < 10 or n_nr < 10:
        print(f"{label}: insufficient class balance (wr={n_wr}, nr={n_nr})")
        return None

    lf_d = cohens_d(lfhf[wr], lfhf[~wr])
    rp_d = cohens_d(ripa2[wr], ripa2[~wr])
    lf_u, lf_p = stats.mannwhitneyu(lfhf[wr], lfhf[~wr], alternative='two-sided')
    rp_u, rp_p = stats.mannwhitneyu(ripa2[wr], ripa2[~wr], alternative='two-sided')

    lf_med_wr = float(np.median(lfhf[wr]))
    lf_med_nr = float(np.median(lfhf[~wr]))
    rp_med_wr = float(np.median(ripa2[wr]))
    rp_med_nr = float(np.median(ripa2[~wr]))

    print(f"\n=== {label} ===")
    print(f"  records: n={len(wr):,}  (wr={n_wr:,}, nr={n_nr:,})")
    print(f"  LF/HF : d={lf_d:+.3f}  p={lf_p:.3e}  "
          f"medians wr={lf_med_wr:.2f} vs nr={lf_med_nr:.2f}")
    print(f"  RIPA2 : d={rp_d:+.3f}  p={rp_p:.3e}  "
          f"medians wr={rp_med_wr:.6f} vs nr={rp_med_nr:.6f}")
    return {
        'label': label,
        'n_records': int(len(wr)),
        'n_wr': n_wr, 'n_nr': n_nr,
        'lfhf': {'d': float(lf_d), 'p': float(lf_p),
                 'median_wr': lf_med_wr, 'median_nr': lf_med_nr},
        'ripa2': {'d': float(rp_d), 'p': float(rp_p),
                  'median_wr': rp_med_wr, 'median_nr': rp_med_nr},
    }


def main():
    print(f"Loading…", flush=True)
    lfhf_abs = json.load(open(LFHF_ABS))
    ripa2_abs = json.load(open(RIPA2_ABS))
    lfhf_org = json.load(open(LFHF_ORG))
    ripa2_org = json.load(open(RIPA2_ORG))
    evr = json.load(open(EVR_PATH))

    trials_abs = set(lfhf_abs.keys()) & set(ripa2_abs.keys())
    trials_org = set(lfhf_org.keys()) & set(ripa2_org.keys())
    intersection = trials_abs & trials_org

    print(f"  absolute trial set      : {len(trials_abs):,}")
    print(f"  organic trial set       : {len(trials_org):,}")
    print(f"  intersection (both attrib): {len(intersection):,}")
    print(f"  absolute-only           : {len(trials_abs - trials_org):,}")
    print(f"  organic-only            : {len(trials_org - trials_abs):,}")

    # ── Headline tests on each attribution's full universe ──
    print("\n[FULL UNIVERSE — both methods on their full trial sets]")
    full_abs = run_test(*assemble_records(lfhf_abs, ripa2_abs, evr),
                        label='ABSOLUTE (full)')
    full_org = run_test(*assemble_records(lfhf_org, ripa2_org, evr),
                        label='ORGANIC  (full)')

    # ── Sensitivity tests on intersection trials only ──
    print("\n[INTERSECTION-OF-TRIALS — same trial subset under each method]")
    int_abs = run_test(*assemble_records(lfhf_abs, ripa2_abs, evr, trial_filter=intersection),
                       label='ABSOLUTE (intersection)')
    int_org = run_test(*assemble_records(lfhf_org, ripa2_org, evr, trial_filter=intersection),
                       label='ORGANIC  (intersection)')

    # ── Drop-only set: trials present under absolute but NOT under organic ──
    abs_only = trials_abs - trials_org
    if abs_only:
        print("\n[ABSOLUTE-ONLY — trials dropped by bbox attribution; "
              "tests dilution-vs-selection directly]")
        drop_abs = run_test(*assemble_records(lfhf_abs, ripa2_abs, evr,
                                              trial_filter=abs_only),
                            label='ABSOLUTE (dropped trials only)')
    else:
        drop_abs = None

    # ── Interpretation ──
    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)
    if int_abs and int_org:
        rp_abs_int = int_abs['ripa2']['p']
        rp_org_int = int_org['ripa2']['p']
        if rp_abs_int < 0.01 and rp_org_int > 0.05:
            print("✓ DILUTION: absolute on intersection still significant "
                  f"(p={rp_abs_int:.3e}); organic on same trials n.s. "
                  f"(p={rp_org_int:.3e}). Bbox attribution is destroying "
                  "real per-fixation signal that lived in rank-pooling.\n"
                  "  → The legacy R1 RIPA2 result was a rank-pooling "
                  "artifact, not selection. Confirms the synthesis-doc "
                  "interpretation.")
        elif rp_abs_int > 0.05 and rp_org_int > 0.05:
            print("✓ SELECTION: absolute on intersection now n.s. "
                  f"(p={rp_abs_int:.3e}). The trials we drop under bbox "
                  "carried the per-fixation RIPA2 signal.\n"
                  "  → The legacy R1 RIPA2 result was real but in a subset "
                  "of trials. The synthesis-doc 'rank-pooling artifact' "
                  "framing needs revision.")
        else:
            print(f"MIXED or borderline: abs intersection p={rp_abs_int:.3e}, "
                  f"org intersection p={rp_org_int:.3e}.")
        if drop_abs:
            print(f"\nABSOLUTE on dropped-trials-only: "
                  f"RIPA2 p={drop_abs['ripa2']['p']:.3e}, "
                  f"d={drop_abs['ripa2']['d']:+.3f} "
                  f"(n={drop_abs['n_records']:,}). If this is much smaller "
                  "than absolute-full, the dropped trials were where the "
                  "signal was concentrated.")

    # Save
    out_dir = ROOT / 'scripts/output/aoi-consumer-cascade'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'r1_intersection_sensitivity.json'
    with open(out_path, 'w') as f:
        json.dump({
            'n_trials_absolute': len(trials_abs),
            'n_trials_organic': len(trials_org),
            'n_intersection': len(intersection),
            'n_abs_only': len(abs_only),
            'full_abs': full_abs,
            'full_org': full_org,
            'int_abs': int_abs,
            'int_org': int_org,
            'drop_abs': drop_abs,
        }, f, indent=2)
    print(f"\n[wrote] {out_path.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
