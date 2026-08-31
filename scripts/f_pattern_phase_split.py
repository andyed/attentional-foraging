"""The F-pattern, decomposed: aggregate gaze density split by scan phase, AdSERP.

The classic F-pattern heatmap is a time-collapse of all fixations. This producer
splits the aggregate into two duration-weighted density maps:

- FORWARD-pass fixations — first-pass / frontier traffic (position not yet both
  visited and below the max-seen rank), and
- RETURN fixations — the canonical NB22 gaze_regression_label mechanism:
  fixation position previously visited AND < max_seen rank. Regression-landing
  relocation search fixations fall here by construction (they land below the
  frontier in visited territory).

Pre-registered-in-prose prediction (f-explainer thread, 2026-08-31): the F's
left stem and mid-page smear are disproportionately RETURN traffic, because
regression landing is region-level (precision ~ random baseline, ~6 relocation
fixations of search after landing). Two publishable outcomes: forward alone
still draws an F (F survives as a triage description, return traffic is the
mislocalized second process) or it doesn't (F is substantially an aggregation
artifact).

Definitions: fixations from load_fixations (FPOGX/FPOGY page/screenshot-space,
duration-weighted); position by gap-free y-band bisection against typed_gapfill
AOI tops; fixations above the first band or off-lattice (pos -1) are excluded
from both classes (counted separately). Density grids: x 0-1280 in 64 px bins,
y 0-2400 in 50 px bins, cell value = summed fixation duration (s).

Run:    .venv/bin/python scripts/f_pattern_phase_split.py
Output: scripts/output/f_pattern_phase_split/{summary.json,report.md,
        f_pattern_phase_split.png}
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    get_trial_ids,
    load_fixations,
    load_typed_gapfill_aois,
    typed_alignment_exclusions,
    typed_gapfill_aoi_tops,
)

OUT = ROOT / 'scripts' / 'output' / 'f_pattern_phase_split'
XMAX, YMAX, XBIN, YBIN = 1280, 2400, 64, 50
NX, NY = XMAX // XBIN, YMAX // YBIN


def main():
    excluded = typed_alignment_exclusions()
    grids = {'forward': np.zeros((NY, NX)), 'return': np.zeros((NY, NX))}
    counts = {'forward': 0, 'return': 0, 'off_lattice': 0}
    dur = {'forward': 0.0, 'return': 0.0}
    xs = {'forward': [], 'return': []}
    ys = {'forward': [], 'return': []}
    n_trials = 0

    for tid in get_trial_ids():
        if tid in excluded or not load_typed_gapfill_aois(tid):
            continue
        fixes = load_fixations(tid)
        if not fixes:
            continue
        tops = typed_gapfill_aoi_tops(tid)
        n = len(tops)
        n_trials += 1
        visited, max_seen = set(), -1
        for f in fixes:
            pos = assign_fixation_to_position(f['y'], tops, n)
            if pos < 0:
                counts['off_lattice'] += 1
                continue
            cls = 'return' if (pos in visited and pos < max_seen) else 'forward'
            visited.add(pos)
            max_seen = max(max_seen, pos)
            counts[cls] += 1
            dur[cls] += f['d']
            xi = min(NX - 1, max(0, int(f['x'] // XBIN)))
            yi = min(NY - 1, max(0, int(f['y'] // YBIN)))
            grids[cls][yi, xi] += f['d'] / 1000.0
            if f['x'] <= XMAX and f['y'] <= YMAX:
                xs[cls].append(f['x'])
                ys[cls].append(f['y'])

    def third_shares(cls):
        g = grids[cls]
        tot = g.sum()
        t = XMAX // 3 // XBIN  # bins per third (6 bins = 384px, close enough; use exact px via xs)
        x = np.asarray(xs[cls])
        return {
            'left_third_share': round(float((x < XMAX / 3).mean()), 4),
            'mid_third_share': round(float(((x >= XMAX / 3) & (x < 2 * XMAX / 3)).mean()), 4),
            'right_third_share': round(float((x >= 2 * XMAX / 3).mean()), 4),
            'y_median': round(float(np.median(ys[cls])), 1),
            'y_iqr': [round(float(np.percentile(ys[cls], q)), 1) for q in (25, 75)],
            'duration_weighted_total_s': round(float(tot), 1),
        }

    # return-share map (masked where total density is negligible)
    total = grids['forward'] + grids['return']
    with np.errstate(invalid='ignore', divide='ignore'):
        share = np.where(total > np.percentile(total[total > 0], 25),
                         grids['return'] / total, np.nan)

    stamp = {}
    sub = ROOT / 'data' / 'aoi-typed' / 'substrate.json'
    if sub.exists():
        stamp['substrate_json'] = json.loads(sub.read_text())
    try:
        stamp['allserp_git_sha'] = subprocess.run(
            ['git', 'rev-parse', '--short=12', 'HEAD'], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        stamp['allserp_git_sha'] = None

    summary = {
        'experiment': 'F-pattern decomposed: duration-weighted gaze density split forward-pass vs return (gaze_regression_label mechanism), AdSERP',
        'regime_tag': '[LAB, AdSERP, typed_gapfill]',
        'rank_type': 'typed_gapfill',
        'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'class_definition': 'RETURN = fixation position previously visited AND < max_seen rank (NB22 gaze_regression_label mechanism, per-fixation); FORWARD = everything else on the main-axis lattice. pos -1 (header/off-lattice) excluded from both.',
        'population': {'trials': n_trials, 'excluded_alignment': len(excluded)},
        'fixation_counts': counts,
        'duration_share_return': round(dur['return'] / (dur['forward'] + dur['return']), 4),
        'fixation_share_return': round(counts['return'] / (counts['forward'] + counts['return']), 4),
        'forward': third_shares('forward'),
        'return': third_shares('return'),
        'substrate_stamp': stamp,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    np.savez_compressed(OUT / 'grids.npz', forward=grids['forward'],
                        ret=grids['return'], share=share)

    # ---- figure -------------------------------------------------------------
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 7.2), dpi=150)
    fig.patch.set_facecolor('#faf7f0')
    vmax = max(grids['forward'].max(), grids['return'].max())
    titles = [
        f"Forward-pass gaze\n{counts['forward']:,} fixations, "
        f"{dur['forward']/1000/60:.0f} min total dwell",
        f"Return gaze (regressive + relocation)\n{counts['return']:,} fixations, "
        f"{dur['return']/1000/60:.0f} min total dwell",
        "Return share of local dwell\n(return / total, low-density cells masked)",
    ]
    for ax, (data, cmap, vmx) in zip(axes, [
            (grids['forward'], 'inferno', vmax),
            (grids['return'], 'inferno', vmax),
            (share, 'coolwarm', 1.0)]):
        im = ax.imshow(data, extent=[0, XMAX, YMAX, 0], aspect='auto',
                       cmap=cmap, vmin=0, vmax=vmx, interpolation='nearest')
        cb = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.02)
        cb.set_label('dwell (s per cell)' if cmap == 'inferno'
                     else 'return fraction', fontsize=9, color='#1a1a1a')
        cb.ax.tick_params(labelsize=8, colors='#1a1a1a')
        ax.set_xlabel('page x (px)', fontsize=10, color='#1a1a1a')
        ax.tick_params(labelsize=8, colors='#1a1a1a')
    axes[0].set_ylabel('page y (px)', fontsize=10, color='#1a1a1a')
    for ax, t in zip(axes, titles):
        ax.set_title(t, fontsize=10.5, color='#1a1a1a')
    fig.suptitle(
        'The F-pattern, decomposed — AdSERP aggregate gaze density by scan phase '
        f'({n_trials:,} trials, duration-weighted)\n'
        'RETURN = position previously visited and below the max-seen rank '
        '(gaze_regression_label); relocation search after regression landings '
        'falls in RETURN by construction',
        fontsize=11, color='#1a1a1a')
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(OUT / 'f_pattern_phase_split.png', facecolor=fig.get_facecolor())
    print(json.dumps({k: summary[k] for k in
                      ('population', 'fixation_counts', 'duration_share_return',
                       'fixation_share_return', 'forward', 'return')}, indent=1))


if __name__ == '__main__':
    main()
