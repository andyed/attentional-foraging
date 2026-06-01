"""One-shot in-place editor for notebooks-v2/25_serp_composition.ipynb.

Adds K-cellsplit-comp Key Claims section + a cellsplit composition
analysis cell. Idempotent — sentinel-guarded re-runs are no-ops.

Sources numerics from scripts/output/nb25_cellsplit_composition/summary.json
(written by compute_nb25_cellsplit_composition.py).

Run:
    .venv/bin/python scripts/_apply_nb25_cellsplit_edits.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_PATH = ROOT / "notebooks-v2/25_serp_composition.ipynb"
SUMMARY_PATH = ROOT / "scripts/output/nb25_cellsplit_composition/summary.json"

SENTINEL_KC = "### Cellsplit-aware composition (K-cellsplit-comp-*)"
SENTINEL_CODE = "# ── Cellsplit-aware click distribution (NB25 §3 extension) ──"


def main() -> None:
    nb = json.loads(NB_PATH.read_text())
    summary = json.loads(SUMMARY_PATH.read_text())

    n_with_carousel = summary["n_trials_with_dd_top_carousel"]
    n_total = summary["n_trials"]
    modal = summary["modal_n_cells"]
    cells_dist = summary["cells_per_carousel"]
    n_carousel_clicks = summary["n_dd_top_clicks_cellsplit"]
    pk_std = summary["abs_standard_peak"]
    pk_cs = summary["abs_cellsplit_peak"]
    top_std = summary["abs_standard_top10"]
    top_cs = summary["abs_cellsplit_top10"]

    # Build cells-per-carousel string for Key Claims
    cells_str = " · ".join(
        f"{n}-cell **{c}** ({c/n_with_carousel*100:.1f}%)"
        for n, c in sorted(cells_dist.items())
    )

    # Build comparison rows for the rank-by-rank table
    rank_rows = []
    std_lookup = {r: (n, p) for r, n, p in top_std}
    cs_lookup = {r: (n, p) for r, n, p in top_cs}
    max_rank = max(max(std_lookup) if std_lookup else 0,
                   max(cs_lookup) if cs_lookup else 0)
    for r in range(min(11, max_rank + 1)):
        n_std, p_std = std_lookup.get(r, (0, 0.0))
        n_cs, p_cs = cs_lookup.get(r, (0, 0.0))
        rank_rows.append(
            f"| {r} | {n_std:,} ({p_std:.2f}%) | {n_cs:,} ({p_cs:.2f}%) |"
        )

    kc_lines = [
        "",
        SENTINEL_KC,
        "",
        f"*Population: full corpus N = {n_total:,}, of which "
        f"{n_with_carousel:,} ({n_with_carousel/n_total*100:.1f}%) carry a "
        f"dd_top carousel. Modal carousel size: {modal} cells. Source: "
        f"`scripts/output/nb25_cellsplit_composition/summary.json` "
        f"(`compute_nb25_cellsplit_composition.py`).*",
        "",
        "Cellsplit decomposes the dd_top carousel — collapsed to a single "
        "abs-rank-0 unit under K1–K24 — into its K constituent cells. The "
        "§3 \"rank 2 displacement peak\" story refines under cellsplit: the "
        "click distribution shows **two peaks** instead of one (carousel "
        "cell 1 at rank 0, first organic at rank ≈ K).",
        "",
        "| ID | Measure | Value |",
        "|---|---|---|",
        f"| **K-cellsplit-comp-1** | Modal carousel size | "
        f"**{modal} cells** ({cells_dist.get(modal, 0):,} / "
        f"{n_with_carousel:,} = {cells_dist.get(modal, 0)/n_with_carousel*100:.1f}% "
        f"of dd_top trials) |",
        f"| **K-cellsplit-comp-2** | Trials with dd_top carousel | "
        f"**{n_with_carousel:,}** ({n_with_carousel/n_total*100:.1f}% of corpus) |",
        f"| **K-cellsplit-comp-3** | Carousel size distribution | "
        f"{cells_str} |",
        f"| **K-cellsplit-comp-4** | First clicks landing in any carousel cell | "
        f"**{n_carousel_clicks:,}** "
        f"({n_carousel_clicks/n_with_carousel*100:.1f}% of dd_top trials) |",
        f"| **K-cellsplit-comp-5** | abs-standard click peak | "
        f"rank **{pk_std['rank']}** = **{pk_std['pct']:.2f}%** "
        f"({pk_std['count']:,} clicks) |",
        f"| **K-cellsplit-comp-6** | abs-cellsplit click peak | "
        f"rank **{pk_cs['rank']}** = **{pk_cs['pct']:.2f}%** "
        f"({pk_cs['count']:,} clicks) |",
        "",
        "**Click distribution by rank — bbox-attributed, two coordinate schemes:**",
        "",
        "| rank | abs-standard | abs-cellsplit |",
        "|---|---|---|",
    ]
    kc_lines.extend(rank_rows)
    kc_lines.extend([
        "",
        "> **The displacement story decomposes under cellsplit.** Under "
        "abs-standard attribution (dd_top = 1 slot), the click distribution "
        "concentrates at rank 0–1 with no clean per-cell resolution. Under "
        "abs-cellsplit, the *same clicks* spread across carousel cells "
        "(ranks 0–K−1) and then peak again at rank K (first organic). The "
        "cell-1-vs-rank-K bimodality is the substrate behind §3's "
        "\"displacement\" language — clicks below the carousel concentrate "
        "at the first organic regardless of how many carousel cells precede "
        "it.",
        ">",
        "> **Methodology note.** These click counts use bbox y-band "
        "attribution (cell bboxes from cascade-baseline snapshots), not the "
        "equal-band approximation used by K1–K24. The two methods differ "
        "by a few percentage points per rank; abs-standard here is *not* "
        "directly comparable to the older absolute-rank numbers in §3's "
        "`clicks_by_abs_rank.csv`. Numbers within this section are "
        "internally consistent.",
        "",
        "---",
        "",
    ])
    cs_block = "\n".join(kc_lines)

    # ── Insert into Key Claims (cell 1) ─────────────────────────────────
    kc_src = nb["cells"][1]["source"]
    if isinstance(kc_src, list):
        kc_src = "".join(kc_src)

    if SENTINEL_KC in kc_src:
        # Idempotent replace: locate block bounds
        start_idx = kc_src.index(SENTINEL_KC) - 1
        end_marker = "\n---\n\n"
        end_idx = kc_src.find(end_marker, start_idx)
        if end_idx == -1:
            end = len(kc_src)
        else:
            end = end_idx + len(end_marker)
        kc_src = kc_src[:start_idx] + cs_block + kc_src[end:]
        action_kc = "replaced existing K-cellsplit-comp section"
    else:
        # First-time insertion: place at the end of the Key Claims block.
        # Anchor: end of the K1-K24 ad type section's last line, before any
        # downstream "Click distribution" section that may not be in a
        # separator.
        anchor = "K24"
        if anchor in kc_src:
            # Find the line break after the K24 row's table block
            pos = kc_src.index(anchor)
            # Find next blank line or "###" after the anchor
            after = kc_src[pos:]
            for sep in ("\n### ", "\n\n---\n", "\n\n## "):
                hit = after.find(sep)
                if hit != -1:
                    insert_at = pos + hit
                    break
            else:
                insert_at = len(kc_src)
            kc_src = kc_src[:insert_at] + "\n\n" + cs_block + kc_src[insert_at:]
            action_kc = "inserted K-cellsplit-comp section after K24 table"
        else:
            raise RuntimeError("K24 anchor not found; manual insertion required")

    # Update the "Primary attribution" preamble to acknowledge cellsplit.
    primary_old = ("Primary attribution: **organic-rank** "
                   "(bbox AOIs from `extract_organic_bboxes.py`)")
    primary_new = (
        "Primary attribution: **organic-rank** "
        "(bbox AOIs from `extract_organic_bboxes.py`). "
        "Cellsplit composition stats added 2026-05-31 (K-cellsplit-comp-* below)"
    )
    if primary_old in kc_src and primary_new not in kc_src:
        kc_src = kc_src.replace(primary_old, primary_new)

    nb["cells"][1]["source"] = kc_src

    # ── Code cell: cellsplit click distribution comparison ──────────────
    code_src = f"""{SENTINEL_CODE}
# Reads scripts/output/nb25_cellsplit_composition/summary.json and renders
# two side-by-side bar charts:
#   - abs-standard click distribution (dd_top = 1 slot)
#   - abs-cellsplit click distribution (dd_top = K cells)
# The cellsplit panel shows the two-peak structure (carousel cell 1 +
# first organic ≈ rank K). Keep K-cellsplit-comp-* section above for the
# numeric values.

import json
from pathlib import Path
import matplotlib.pyplot as plt

CS_SUMMARY = Path('../scripts/output/nb25_cellsplit_composition/summary.json')
cs = json.load(open(CS_SUMMARY))

ranks_std = [r for r, _, _ in cs['abs_standard_top10']]
pct_std = [p for _, _, p in cs['abs_standard_top10']]
ranks_cs = [r for r, _, _ in cs['abs_cellsplit_top10']]
pct_cs = [p for _, _, p in cs['abs_cellsplit_top10']]

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
for ax, (ranks, pct, color, title) in zip(axes, [
    (ranks_std, pct_std, '#0072B2',
     f'abs-standard  (dd_top = 1 slot)  ·  peak: rank {{cs["abs_standard_peak"]["rank"]}} '
     f'= {{cs["abs_standard_peak"]["pct"]:.1f}}%'),
    (ranks_cs, pct_cs, '#D55E00',
     f'abs-cellsplit  (dd_top = K cells)  ·  peak: rank {{cs["abs_cellsplit_peak"]["rank"]}} '
     f'= {{cs["abs_cellsplit_peak"]["pct"]:.1f}}%'),
]):
    ax.bar(ranks, pct, color=color, edgecolor='#222222', linewidth=0.9, width=0.78)
    ax.set_title(title, fontsize=11.5, weight='bold', color='#222222')
    ax.set_xlabel('absolute rank (0 = topmost slot)', fontsize=11)
    ax.set_xticks(ranks)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', color='#cccccc', linewidth=0.4, alpha=0.6)
    ax.set_axisbelow(True)
axes[0].set_ylabel('% of first-clicks', fontsize=11)

n_carousel = cs['n_trials_with_dd_top_carousel']
modal = cs['modal_n_cells']
fig.suptitle(
    f'NB25 §3 extension  ·  cellsplit decomposes the dd_top displacement peak  ·  '
    f'{{n_carousel:,}} carousel trials, modal {{modal}}-cell',
    fontsize=13, weight='bold', y=1.04, color='#222222',
)
plt.tight_layout()
plt.show()
"""

    new_md = (
        "## §3b. Cellsplit-aware click distribution\n\n"
        "§3's \"clicks peak at rank 2 — dd_top displacement\" claim uses "
        "equal-band absolute-rank attribution. Recomputing with bbox y-band "
        "attribution and expanding dd_top into its K cells yields a richer "
        "picture: the displacement story is the **superposition of two "
        "peaks** — clicks on carousel cell 1 and clicks on the first organic "
        "result (which appears at absolute rank ≈ K under cellsplit, vs "
        "rank 1 under standard).\n\n"
        "Source: `compute_nb25_cellsplit_composition.py` → "
        "`scripts/output/nb25_cellsplit_composition/summary.json`. Numeric "
        "values in the K-cellsplit-comp-* table at the top of this notebook."
    )

    # Insert/replace code cell
    found_existing = False
    for i, c in enumerate(nb["cells"]):
        src = c.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        if c.get("cell_type") == "code" and SENTINEL_CODE in src:
            c["source"] = code_src
            found_existing = True
            action_code = f"replaced existing cellsplit cell at index {i}"
            break

    if not found_existing:
        # Insert before §4 (Validation cohorts) if present; else before §6
        insert_idx = len(nb["cells"])
        for i, c in enumerate(nb["cells"]):
            src = c.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            if c.get("cell_type") == "markdown" and src.lstrip().startswith(
                "## 4."
            ):
                insert_idx = i
                break

        new_md_cell = {
            "cell_type": "markdown",
            "metadata": {},
            "source": new_md,
        }
        new_code_cell = {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": code_src,
        }
        nb["cells"][insert_idx:insert_idx] = [new_md_cell, new_code_cell]
        action_code = (
            f"inserted cellsplit md + code cells at index "
            f"{insert_idx}-{insert_idx+1}"
        )

    NB_PATH.write_text(json.dumps(nb, indent=1) + "\n")
    print(f"[ok] {action_kc}")
    print(f"[ok] {action_code}")
    print(f"[ok] notebook written: {NB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
