"""Label distribution: canonical (parent-only) vs cell-aware.

Reports counts for a 3-class proxy of the paper's 4-class taxonomy
(without gaze-regression access we can't split DEFERRED vs EVAL_REJECTED
without re-deriving from fixation revisits; the 3-class collapse is
what the deployable path uses anyway):

  CLICKED:                 was_clicked == True
  NOT_APPROACHED:          dwell_in_proximity_ms == 0
  APPROACHED_NOT_CLICKED:  everything else (deferred + eval-rejected merged)

Run:
    .venv/bin/python scripts/m4_cellsplit_label_dist.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from m4_cellsplit_loso import build_records  # noqa: E402


def label_of(r: dict) -> str:
    if r.get("was_clicked"):
        return "CLICKED"
    dwell = float(r.get("dwell_in_proximity_ms") or 0)
    if dwell == 0:
        return "NOT_APPROACHED"
    return "APPROACHED_NOT_CLICKED"


def summarize(view: str):
    records = build_records(view)
    overall = Counter(label_of(r) for r in records)
    by_etype = defaultdict(Counter)
    for r in records:
        by_etype[r.get("etype", "?")][label_of(r)] += 1
    return {"n": len(records), "overall": overall, "by_etype": by_etype}


def main():
    print("Canonical view (parent-only)...", file=sys.stderr)
    canon = summarize("canonical")
    print("Cell-aware view...", file=sys.stderr)
    cell = summarize("cell_aware")

    print("\n" + "=" * 76)
    print("Label distribution: canonical vs cell-aware (3-class proxy)")
    print("=" * 76)

    print(f"\nOverall (n_records: canonical={canon['n']}, cell-aware={cell['n']}):")
    print(f"{'label':<26} {'canonical':>14} {'cell-aware':>14} {'delta':>10}")
    for lab in ["CLICKED", "APPROACHED_NOT_CLICKED", "NOT_APPROACHED"]:
        c = canon["overall"][lab]
        a = cell["overall"][lab]
        c_pct = 100 * c / canon["n"]
        a_pct = 100 * a / cell["n"]
        print(f"{lab:<26} {c:>6} ({c_pct:5.1f}%) {a:>6} ({a_pct:5.1f}%) {a-c:>+10}")

    print(f"\nBy etype:")
    etypes = sorted(set(list(canon["by_etype"].keys()) + list(cell["by_etype"].keys())))
    for et in etypes:
        c = canon["by_etype"].get(et, Counter())
        a = cell["by_etype"].get(et, Counter())
        n_c = sum(c.values())
        n_a = sum(a.values())
        if n_c == 0 and n_a == 0:
            continue
        print(f"\n  etype={et}  canonical n={n_c}  cell-aware n={n_a}")
        for lab in ["CLICKED", "APPROACHED_NOT_CLICKED", "NOT_APPROACHED"]:
            cv, av = c[lab], a[lab]
            c_pct = 100 * cv / n_c if n_c else 0
            a_pct = 100 * av / n_a if n_a else 0
            print(f"    {lab:<24} {cv:>6} ({c_pct:5.1f}%) {av:>6} ({a_pct:5.1f}%)")

    out = {
        "canonical": {"n": canon["n"], "overall": dict(canon["overall"]),
                       "by_etype": {k: dict(v) for k, v in canon["by_etype"].items()}},
        "cell_aware": {"n": cell["n"], "overall": dict(cell["overall"]),
                        "by_etype": {k: dict(v) for k, v in cell["by_etype"].items()}},
    }
    out_path = ROOT / "scripts/output/m4_cellsplit_loso/label_distribution.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
