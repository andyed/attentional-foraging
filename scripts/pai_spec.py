"""Peripheral Attention Index (PAI) — spec-exact implementation.

Source: Duchowski, Gehrer & Svaldi, "Peripheral Attention Index:
Area-Weighted Distal Polygonal Areas Of Interest", ETTAC 2026 (ICPR 2026
Workshops, Lyon). Implemented from the author-shared manuscript
(Downloads/main.pdf, received 2026-08-31), NOT from the abstract — this
module supersedes the abstract-derived guesses in NB35 and
collab/allawati-ai-overviews/pai-proto-2026-08-18/.

Definitions (paper §4):
    OGD  = min_i ||G - v_i||_2          gaze to nearest polygon VERTEX
    CGD  = ||G - C||_2                  gaze to polygon centroid
    Eq 1:  alpha   = 1 - sqrt(OGD / CGD)
    Eq 2:  alpha_A = 1 - sqrt((OGD / CGD) * min(1, A / A_ref))

The paper is internally inconsistent in four places. Each is encoded
here as an explicit option or documented property so nothing is silently
resolved; pai_spec_test.py demonstrates all four numerically.

  D1 centroid: §4 defines C by the shoelace-weighted centroid formula,
     but Listing 1.1 (compute_cgd) and the Theorem 1 proof both use the
     vertex mean. These differ whenever vertex spacing is non-uniform.
     -> `centroid=` option: "shoelace" (equations) | "vertex_mean" (listing).
  D2 area-weight placement: Eq 2 puts min(1, A/A_ref) INSIDE the sqrt;
     Listing 1.1 multiplies it outside (sqrt applied to OGD/CGD only).
     -> `weight_placement=` option: "eq2" | "listing".
  D3 interior opacity: prose asserts G inside the AOI gives OGD = 0 and
     alpha = 1. True for Wang et al.'s pixel-based OGD; false for the
     vertex-based OGD defined here, which is > 0 strictly inside a
     polygon away from its vertices.
  D4 Theorem 1 ("OGD <= CGD for all G") is false: at G = C, CGD = 0 <
     OGD. The proof's first step applies the triangle inequality in the
     wrong direction (||G - mean(v)|| <= mean ||G - v_i||, not >=), so
     the corollary OGD/CGD in [0,1] also fails and Eq 1 can go negative
     near the centroid; clipping (present in Listing 1.1, absent from
     Eq 1) is therefore load-bearing, not cosmetic.

Coordinates are pixels in stimulus space; polygons are (n, 2) vertex
arrays, closed implicitly (v_{n+1} = v_1).
"""

import numpy as np

# --- §4 primitives -----------------------------------------------------


def shoelace_area(verts):
    """Signed polygon area, paper's Gauss/Shoelace formula.

    A = 1/2 * sum_i (x_i * y_{i+1} - x_{i+1} * y_i), vertices closed
    implicitly. Sign carries winding order; callers wanting geometric
    area take abs() (as Listing 1.1 does).
    """
    v = np.asarray(verts, dtype=float)
    x, y = v[:, 0], v[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    return 0.5 * np.sum(x * yn - xn * y)


def polygon_centroid(verts):
    """Shoelace-weighted centroid, the §4 equations' definition (D1).

    x_bar = 1/(6A) * sum (x_i + x_{i+1})(x_i y_{i+1} - x_{i+1} y_i),
    same for y_bar; A signed. Degenerate (A == 0) polygons fall back to
    the vertex mean, the only finite answer available.
    """
    v = np.asarray(verts, dtype=float)
    a = shoelace_area(v)
    if a == 0.0:
        return v.mean(axis=0)
    x, y = v[:, 0], v[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    return np.array(
        [np.sum((x + xn) * cross), np.sum((y + yn) * cross)]
    ) / (6.0 * a)


def ogd(gaze, verts):
    """Object-Gaze Distance: min L2 distance from gaze to a VERTEX.

    The paper's §4 redefinition of Wang et al.'s pixel-based OGD.
    Vertex-based on purpose — do not "fix" to boundary/edge distance;
    that is a different metric (see D3, and the boundary-OGD variant in
    pai-proto-2026-08-18 which this module supersedes).
    """
    v = np.asarray(verts, dtype=float)
    g = np.asarray(gaze, dtype=float)
    return float(np.min(np.hypot(v[:, 0] - g[0], v[:, 1] - g[1])))


def cgd(gaze, verts, centroid="shoelace"):
    """Centroid-Gaze Distance ||G - C||_2. `centroid` picks the D1 side."""
    if centroid == "shoelace":
        c = polygon_centroid(verts)
    elif centroid == "vertex_mean":
        c = np.asarray(verts, dtype=float).mean(axis=0)
    else:
        raise ValueError(f"unknown centroid mode: {centroid!r}")
    g = np.asarray(gaze, dtype=float)
    return float(np.hypot(g[0] - c[0], g[1] - c[1]))


# --- PAI, equation forms ----------------------------------------------


def pai(gaze, verts, centroid="shoelace", clip=True):
    """Eq 1: alpha = 1 - sqrt(OGD / CGD).

    CGD == 0 returns 1.0, following Listing 1.1's guard (Eq 1 is
    undefined there). `clip=True` bounds to [0, 1] as the listing does;
    required in practice because of D4. clip=False exposes the raw Eq 1
    value, which goes negative near the centroid.
    """
    d_o = ogd(gaze, verts)
    d_c = cgd(gaze, verts, centroid=centroid)
    if d_c == 0.0:
        return 1.0
    alpha = 1.0 - np.sqrt(d_o / d_c)
    return float(np.clip(alpha, 0.0, 1.0)) if clip else float(alpha)


def pai_area_weighted(
    gaze, verts, a_ref, centroid="shoelace", weight_placement="eq2", clip=True
):
    """Eq 2: alpha_A = 1 - sqrt((OGD/CGD) * min(1, A/A_ref)).

    A is the unsigned shoelace area of `verts`; `a_ref` is the reference
    area (paper: max AOI area in the stimulus; "maximum or median is
    optional", pre-computable over a finite AOI set).
    `weight_placement` picks the D2 side: "eq2" applies the weight
    inside the sqrt; "listing" multiplies sqrt(OGD/CGD) by the weight,
    matching soft_alpha in Listing 1.1.
    """
    d_o = ogd(gaze, verts)
    d_c = cgd(gaze, verts, centroid=centroid)
    if d_c == 0.0:
        return 1.0
    w = min(1.0, abs(shoelace_area(verts)) / a_ref)
    if weight_placement == "eq2":
        ratio = np.sqrt((d_o / d_c) * w)
    elif weight_placement == "listing":
        ratio = np.sqrt(d_o / d_c) * w
    else:
        raise ValueError(f"unknown weight_placement: {weight_placement!r}")
    alpha = 1.0 - ratio
    return float(np.clip(alpha, 0.0, 1.0)) if clip else float(alpha)


# --- Vectorized Eq-2 over column-band rect AOIs -----------------------


def rect_alpha_grid(fx, fy, x0, x1, tops, bottoms, weight_placement="eq2"):
    """Spec Eq-2 alpha for every (fixation, AOI) pair, vectorized.

    AOIs are the AdSERP producers' column-band rects: shared x-extent
    [x0, x1], per-AOI [tops[i], bottoms[i]]. For an axis-aligned rect the
    shoelace centroid equals the vertex mean equals the center (D1 moot),
    and the vertex OGD is the nearest-corner distance, which separates
    per axis: hypot(min|fx - {x0,x1}|, min|fy - {top,bottom}|).

    A_ref is the maximum AOI area on the page (the paper's default);
    weight = min(1, A/A_ref). `weight_placement` picks the D2 side, as in
    pai_area_weighted. No max(cgd, 1) guard (that is the demo/H01 lineage,
    not the paper): cgd == 0 returns alpha 1.0 per Listing 1.1's guard.
    Note D3/D4 apply — fixations inside a rect get vertex-OGD alpha < 1,
    dipping to 0 near the center; callers wanting peripheral-only mass
    must gate on rect containment themselves.

    Returns an (n_fix, n_aoi) float array in [0, 1].
    """
    fx = np.asarray(fx, dtype=float)
    fy = np.asarray(fy, dtype=float)
    a_top = np.asarray(tops, dtype=float)
    a_bot = np.asarray(bottoms, dtype=float)
    areas = (float(x1) - float(x0)) * np.maximum(a_bot - a_top, 0.0)
    w = np.minimum(1.0, areas / areas.max())

    vx = np.minimum(np.abs(fx - float(x0)), np.abs(fx - float(x1)))
    vy = np.minimum(np.abs(fy[:, None] - a_top[None, :]),
                    np.abs(fy[:, None] - a_bot[None, :]))
    ogd_v = np.hypot(vx[:, None], vy)
    cx = (float(x0) + float(x1)) / 2.0
    cy = (a_top + a_bot) / 2.0
    cgd_v = np.hypot(fx[:, None] - cx, fy[:, None] - cy[None, :])

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = ogd_v / cgd_v
        if weight_placement == "eq2":
            root = np.sqrt(ratio * w[None, :])
        elif weight_placement == "listing":
            root = np.sqrt(ratio) * w[None, :]
        else:
            raise ValueError(f"unknown weight_placement: {weight_placement!r}")
    alpha = np.clip(1.0 - root, 0.0, 1.0)
    return np.where(cgd_v == 0.0, 1.0, alpha)


# --- Listing 1.1, verbatim --------------------------------------------
# Transcribed from the manuscript's Listing 1.1 unchanged except for
# indentation (flattened by PDF text extraction) and the '-' between the
# two np.dot terms in soft_alpha, which the PDF's line break swallowed;
# it is the standard shoelace cross-difference. Note the listing's own
# quirks are preserved: vertex-mean centroid (D1), area weight outside
# the sqrt (D2), ndarray-indexing of `aoi` in soft_alpha (so `aoi` must
# already be an (n,2) array there), and the A_ref=50000 default.


def compute_ogd(x_g, y_g, aoi):
    verts = np.array(aoi)
    dists = np.sqrt((verts[:, 0] - x_g) ** 2 + (verts[:, 1] - y_g) ** 2)
    return dists.min()


def compute_cgd(x_g, y_g, aoi):
    verts = np.array(aoi)
    centroid = verts.mean(axis=0)
    return np.hypot(x_g - centroid[0], y_g - centroid[1])


def soft_alpha(x_g, y_g, aoi, area_weight=True, A_ref=50000):
    ogd = compute_ogd(x_g, y_g, aoi)
    cgd = compute_cgd(x_g, y_g, aoi)
    if cgd == 0:
        return 1.0
    ratio = np.sqrt(ogd / cgd)
    if area_weight:
        A = 0.5 * np.abs(
            np.dot(aoi[:, 0], np.roll(aoi[:, 1], 1))
            - np.dot(aoi[:, 1], np.roll(aoi[:, 0], 1))
        )
        ratio *= min(1.0, A / A_ref)
    return np.clip(1.0 - ratio, 0.0, 1.0)
