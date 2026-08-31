"""Verification for pai_spec.py against the ETTAC 2026 manuscript.

Three groups:
  1. Primitive correctness on known geometry (area, centroid, OGD, CGD).
  2. Equation forms vs the paper's own Listing 1.1 — agree exactly where
     the paper is consistent, and the D1/D2 options reproduce each side
     where it is not.
  3. The four documented discrepancies (D1-D4) demonstrated numerically,
     so each is a checked fact rather than a reading of the prose.

Standalone runner, repo *_test.py convention: prints each check, exits
non-zero on any failure.
"""

import sys

import numpy as np

from pai_spec import (
    cgd,
    compute_cgd,
    compute_ogd,
    ogd,
    pai,
    pai_area_weighted,
    polygon_centroid,
    rect_alpha_grid,
    shoelace_area,
    soft_alpha,
)

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


# unit square, uniform vertex spacing: shoelace and vertex-mean centroids agree
SQUARE = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
# L-shape with a densified bottom edge: non-uniform vertex spacing
LSHAPE = np.array(
    [[0.0, 0.0], [0.5, 0.0], [1.0, 0.0], [1.5, 0.0], [2.0, 0.0],
     [2.0, 1.0], [1.0, 1.0], [1.0, 2.0], [0.0, 2.0]]
)

print("1. primitives on known geometry")
check("square area = 1 (signed, CCW)", np.isclose(shoelace_area(SQUARE), 1.0))
check("square centroid = (0.5, 0.5)",
      np.allclose(polygon_centroid(SQUARE), [0.5, 0.5]))
check("L-shape area = 3", np.isclose(abs(shoelace_area(LSHAPE)), 3.0))
check("OGD at (0.5, 0.5) in square = sqrt(0.5) (nearest VERTEX, not edge)",
      np.isclose(ogd([0.5, 0.5], SQUARE), np.sqrt(0.5)))
check("OGD at a vertex = 0", ogd([1.0, 1.0], SQUARE) == 0.0)
check("CGD at centroid = 0", cgd([0.5, 0.5], SQUARE) == 0.0)

print("2. equation forms vs Listing 1.1 where the paper is consistent")
rng = np.random.default_rng(20260831)
gazes = rng.uniform(-3, 4, size=(200, 2))
# On the square (uniform spacing) with the listing's weight placement,
# pai_area_weighted must reproduce soft_alpha exactly; unweighted Eq 1
# with vertex_mean centroid must reproduce soft_alpha(area_weight=False).
agree_w = all(
    np.isclose(
        pai_area_weighted(g, SQUARE, 50000.0, centroid="vertex_mean",
                          weight_placement="listing"),
        soft_alpha(g[0], g[1], SQUARE),
    )
    for g in gazes
)
agree_u = all(
    np.isclose(pai(g, SQUARE, centroid="vertex_mean"),
               soft_alpha(g[0], g[1], SQUARE, area_weight=False))
    for g in gazes
)
check("area-weighted 'listing' form == soft_alpha on 200 random gazes", agree_w)
check("Eq 1 (vertex_mean) == soft_alpha(area_weight=False)", agree_u)
check("compute_ogd == ogd on random gazes",
      all(np.isclose(compute_ogd(g[0], g[1], LSHAPE), ogd(g, LSHAPE))
          for g in gazes))
check("compute_cgd == cgd(centroid='vertex_mean')",
      all(np.isclose(compute_cgd(g[0], g[1], LSHAPE),
                     cgd(g, LSHAPE, centroid="vertex_mean"))
          for g in gazes))
check("alpha in [0,1] everywhere (clipped forms)",
      all(0.0 <= pai(g, LSHAPE) <= 1.0 for g in gazes))

print("3. documented discrepancies, demonstrated")
# D1: shoelace vs vertex-mean centroid diverge under non-uniform spacing
c_sl = polygon_centroid(LSHAPE)
c_vm = LSHAPE.mean(axis=0)
check(f"D1: L-shape shoelace centroid {np.round(c_sl, 3)} != "
      f"vertex mean {np.round(c_vm, 3)}",
      not np.allclose(c_sl, c_vm))
check("D1 control: uniform square, the two centroids agree",
      np.allclose(polygon_centroid(SQUARE), SQUARE.mean(axis=0)))

# D2: Eq 2 (weight inside sqrt) != Listing (outside) once weight < 1
g = np.array([3.0, 3.0])
a_ref = 10.0  # square area 1 -> weight 0.1
d2_eq2 = pai_area_weighted(g, SQUARE, a_ref, weight_placement="eq2",
                           clip=False)
d2_lst = pai_area_weighted(g, SQUARE, a_ref, weight_placement="listing",
                           clip=False)
check(f"D2: eq2 form {d2_eq2:.4f} != listing form {d2_lst:.4f} at weight 0.1",
      not np.isclose(d2_eq2, d2_lst))

# D3: strictly interior gaze away from vertices has OGD > 0 (prose claims 0)
check("D3: OGD at square center > 0 despite 'inside => OGD = 0' prose",
      ogd([0.5, 0.5], SQUARE) > 0.0)

# D4: Theorem 1 counterexample — at G = centroid, CGD = 0 < OGD, and
# near the centroid raw Eq 1 goes negative (clip is load-bearing).
g_near = np.array([0.5 + 1e-6, 0.5])
check("D4: at G = C, OGD > CGD (theorem claims OGD <= CGD for all G)",
      ogd([0.5, 0.5], SQUARE) > cgd([0.5, 0.5], SQUARE))
check("D4: raw Eq 1 < 0 near centroid",
      pai(g_near, SQUARE, clip=False) < 0.0)
check("D4: clipped Eq 1 = 0 near centroid (interior transparency dip)",
      pai(g_near, SQUARE) == 0.0)

print("4. vectorized rect grid vs scalar reference")
# Two band rects sharing the producers' column x-extent; a_ref = max area.
X0, X1 = 162.0, 702.0
TOPS, BOTS = [100.0, 400.0], [250.0, 900.0]   # areas 540*150, 540*500
POLYS = [np.array([[X0, t], [X1, t], [X1, b], [X0, b]]) for t, b in
         zip(TOPS, BOTS)]
A_REF = max(abs(shoelace_area(p)) for p in POLYS)
gz = rng.uniform(-100, 1100, size=(300, 2))
for wp in ("eq2", "listing"):
    grid = rect_alpha_grid(gz[:, 0], gz[:, 1], X0, X1, TOPS, BOTS,
                           weight_placement=wp)
    ok = all(
        np.isclose(grid[i, j],
                   pai_area_weighted(gz[i], POLYS[j], A_REF,
                                     weight_placement=wp))
        for i in range(len(gz)) for j in range(len(POLYS)))
    check(f"rect_alpha_grid({wp}) == pai_area_weighted on 300x2 pairs", ok)
check("rect_alpha_grid: alpha = 1 at AOI center distance 0",
      rect_alpha_grid([ (X0+X1)/2 ], [175.0], X0, X1, TOPS, BOTS)[0, 0]
      == 1.0)

n_fail = sum(1 for _, ok in CHECKS if not ok)
print(f"\n{len(CHECKS) - n_fail}/{len(CHECKS)} checks passed")
if n_fail or not CHECKS:
    sys.exit(1)
