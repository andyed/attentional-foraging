"""Peripheral membership kernels shared by the engagement producers.

`spec`        the published PAI (Duchowski, Gehrer & Svaldi 2026), Eq. 2 via
              pai_spec.rect_alpha_grid: vertex OGD / centroid distance with the
              area weight min(1, A/A_max). On SERP result bands (~540 x 80 px)
              this alpha is nearly flat in eccentricity (corpus Spearman with
              boundary distance -0.08; mean 0.46 within 50 px, 0.40 beyond
              1,600 px) and 6.8 % of adjacent pairs get alpha 0 because the
              vertex distance exceeds the centroid distance below the middle of
              a wide band. Measured 2026-09-14 on 639k pairs / 600 trials.
`boundary_cm` PROPOSAL, not the published method: rect-boundary distance in
              degrees with a cortical-magnification falloff,
              alpha = 1 / (1 + E / E2), E2 = 2 deg by default, 0 inside the
              rect. Pixels per degree is a setup assumption (24 is the repo's
              convention from findings.md 3d-ii; 40 is the upper bound in the
              lit note).
"""
from __future__ import annotations

import numpy as np

from pai_spec import rect_alpha_grid


def boundary_ogd(fx, fy, x0, x1, tops, bottoms):
    """Rect-boundary distance (0 inside) from each fixation to each band."""
    dx = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
    dy = np.maximum.reduce([tops[None, :] - fy[:, None], np.zeros((len(fy), len(tops))),
                            fy[:, None] - bottoms[None, :]])
    return np.hypot(dx[:, None], dy)


def alpha_grid(fx, fy, x0, x1, tops, bottoms, kernel='spec', weight_placement='eq2',
               e2_deg=2.0, px_per_deg=24.0):
    tops = np.asarray(tops, float)
    bottoms = np.asarray(bottoms, float)
    if kernel == 'spec':
        return rect_alpha_grid(fx, fy, x0, x1, tops, bottoms, weight_placement=weight_placement)
    if kernel == 'boundary_cm':
        ogd = boundary_ogd(fx, fy, x0, x1, tops, bottoms)
        return 1.0 / (1.0 + (ogd / px_per_deg) / e2_deg)
    raise ValueError(kernel)


def add_kernel_args(ap):
    ap.add_argument('--kernel', default='spec', choices=['spec', 'boundary_cm'])
    ap.add_argument('--weight-placement', default='eq2', choices=['eq2', 'listing'])
    ap.add_argument('--e2-deg', type=float, default=2.0)
    ap.add_argument('--px-per-deg', type=float, default=24.0)


def kernel_label(args):
    if args.kernel == 'spec':
        return f'spec_{args.weight_placement} (published PAI)'
    return f'boundary_cm PROPOSAL: alpha = 1/(1 + E/{args.e2_deg:g}deg), {args.px_per_deg:g} px/deg'
