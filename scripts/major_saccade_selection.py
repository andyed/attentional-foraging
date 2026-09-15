#!/usr/bin/env python3
"""Before a major saccade: landing precision, ambient timing, and target
selection, by saccade amplitude. Producer for docs/ablations/major_saccade_selection.md
(inline analyses of 2026-09-14, promoted 2026-09-15).

First-entry moves: consecutive fixations (i-1, i) where fixation i is the
first fixation on typed position p and fixation i-1 is on some other position
(by default; --allow-prev-off-column keeps moves from off the column). Amplitude = Euclidean distance between the two
fixations (page px). Bins: minor < 100, 100-300, major 300-600, > 600.
  1. landing offset |y - band centre| by bin; Spearman of prior 1 s intake on
     the target with the offset, within major bins; per-participant sign
  2. duration of the fixation before the move, by bin; per-participant
     median(major) - median(minor), sign count (the ambient-mode signature)
  3. target selection: among candidates (on-screen per the census, i.e. any
     viewport residence, not yet fixated), was the landed result the nearest
     to the preceding fixation, the top by near-peripheral intake over the
     prior window, or the closest to any fixation in the window
Intake = boundary-distance kernel 1/(1 + E/E2), E2 = 2 deg at 24 px/deg (the
2026-09-14 runs; 43 px/deg is the derived scale, see the note), fixations
outside the band only. Regime [LAB, AdSERP, typed].
Output: scripts/output/major_saccade_selection/summary.json
"""
import sys, csv, json, argparse, datetime as dt
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2')); sys.path.insert(0, str(ROOT / 'scripts'))
import data_loader as dl
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX
from peripheral_kernel import boundary_ogd

ap = argparse.ArgumentParser()
ap.add_argument('--px-per-deg', type=float, default=24.0); ap.add_argument('--e2-deg', type=float, default=2.0)
ap.add_argument('--census-dir', default='scripts/output/engagement_state_census/gate_200px')
ap.add_argument('--allow-prev-off-column', action='store_true', help='keep moves whose preceding fixation was on no result (default: moves between results only, as in the note)')
args = ap.parse_args()
BINS = [('minor <100', 0, 100), ('100-300', 100, 300), ('major 300-600', 300, 600), ('major >600', 600, 1e9)]
WINS = [500, 1000, 2000, 4000]

rows = list(csv.DictReader(open(ROOT / args.census_dir / 'states.csv')))
onscreen = defaultdict(set)
for r in rows:
    if r['state'] not in ('never_onscreen', 'brief_onscreen'):
        onscreen[r['trial_id']].add(int(r['position']))
tids = sorted(onscreen)
x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)
ev = []
for tid in tids:
    try:
        bands = dl.typed_aoi_bands(tid); fx = dl.load_fixations(tid)
    except Exception:
        continue
    if not bands or len(fx) < 2:
        continue
    tops = np.array([b[0] for b in bands], float); bots = np.array([b[1] for b in bands], float); n = len(bands)
    pos = [dl.assign_fixation_to_position(f['y'], tops.tolist(), n) for f in fx]
    pos = [p if (p is not None and p >= 0) else None for p in pos]
    ft = np.array([f['t'] for f in fx], float); fxx = np.array([f['x'] for f in fx], float)
    fyy = np.array([f['y'] for f in fx], float); fd = np.array([(f.get('d') or 0) for f in fx], float)
    ogd = boundary_ogd(fxx, fyy, x0, x1, tops, bots)                  # (fix, band)
    alpha = 1.0 / (1.0 + (ogd / args.px_per_deg) / args.e2_deg)
    ins = np.array([[pos[i] == k for k in range(n)] for i in range(len(fx))])
    pid = tid.split('-')[0]; seen = set()
    for i in range(1, len(fx)):
        p, q = pos[i], pos[i - 1]
        if p is None:
            continue
        if p in seen or q == p or (q is None and not args.allow_prev_off_column):
            seen.add(p); continue
        seen.add(p)
        amp = float(np.hypot(fxx[i] - fxx[i - 1], fyy[i] - fyy[i - 1]))
        cy = (tops[p] + bots[p]) / 2; h = max(bots[p] - tops[p], 1.0)
        e = {'pid': pid, 'amp': amp, 'prev_dur': float(fd[i - 1]), 'off': float(abs(fyy[i] - cy)), 'offn': float(abs(fyy[i] - cy) / h)}
        cands = [k for k in onscreen[tid] if k < n and k not in seen and k != q]
        if p not in cands:
            cands.append(p)
        e['n_c'] = len(cands); j = cands.index(p)
        for W in WINS:
            if ft[i] - W < ft[0]:
                continue
            s = (ft >= ft[i] - W) & (ft < ft[i])
            if not s.any():
                continue
            it = np.array([(fd[s] * np.where(~ins[s, k], alpha[s, k], 0)).sum() for k in cands])
            md = np.array([ogd[s, k].min() for k in cands])
            e[f'top_intake_{W}'] = int((it > it[j]).sum() == 0); e[f'top_prox_{W}'] = int((md < md[j]).sum() == 0)
            if W == 1000:
                e['intake_target_1s'] = float(it[j]); e['nearest_prev'] = int((ogd[i - 1, cands] < ogd[i - 1, p]).sum() == 0)
        ev.append(e)

amp = np.array([e['amp'] for e in ev]); pid = np.array([e['pid'] for e in ev]); off = np.array([e['off'] for e in ev])
offn = np.array([e['offn'] for e in ev]); pdur = np.array([e['prev_dur'] for e in ev])
it1 = np.array([e.get('intake_target_1s', np.nan) for e in ev], float)
out = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'regime': '[LAB, AdSERP, typed]', 'kernel': f'boundary_cm E2={args.e2_deg} deg at {args.px_per_deg} px/deg',
       'first_entry_moves': len(ev), 'participants': int(len(set(pid))), 'bins': {}}
print(f'first-entry moves with a preceding fixation: {len(ev):,}; participants {len(set(pid))}')
print(f"{'bin':16s} {'n':>6s} {'prev fix ms':>11s} {'off px':>7s} {'off/h':>6s} {'rho(intake,off)':>16s} {'p':>7s} {'P(nearest)':>10s} {'P(top intake 1s)':>16s} {'P(top prox 1s)':>14s} {'chance':>7s} {'n sel':>6s}")
for name, lo, hi in BINS:
    m = (amp >= lo) & (amp < hi); ok = m & np.isfinite(it1)
    rho = spearmanr(it1[ok], off[ok]) if ok.sum() > 30 else None
    sel = [e for e, mm in zip(ev, m) if mm and 'top_intake_1000' in e and e['n_c'] >= 3]
    g = lambda k: float(np.mean([e[k] for e in sel])) if sel else None
    chance = float(np.median([1 / e['n_c'] for e in sel])) if sel else None
    # per-participant sign of rho(intake, offset) within this bin
    signs = []
    for p_ in np.unique(pid):
        mm = ok & (pid == p_)
        if mm.sum() >= 20:
            signs.append(spearmanr(it1[mm], off[mm]).statistic)
    row = {'n': int(m.sum()), 'prev_fix_ms_median': float(np.median(pdur[m])), 'offset_px_median': float(np.median(off[m])), 'offset_norm_median': float(np.median(offn[m])),
           'rho_intake_offset': (float(rho.statistic) if rho else None), 'rho_p': (float(rho.pvalue) if rho else None),
           'rho_participants_negative': int(np.sum(np.array(signs) < 0)), 'rho_participants': len(signs),
           'P_nearest_prev': g('nearest_prev'), 'P_top_intake_1s': g('top_intake_1000'), 'P_top_prox_1s': g('top_prox_1000'), 'chance': chance, 'n_selection': len(sel)}
    out['bins'][name] = row
    print(f"{name:16s} {row['n']:6d} {row['prev_fix_ms_median']:11.0f} {row['offset_px_median']:7.1f} {row['offset_norm_median']:6.2f} "
          f"{(f'{row['rho_intake_offset']:+.3f}' if rho else '-'):>16s} {(f'{row['rho_p']:.3f}' if rho else '-'):>7s} "
          f"{(row['P_nearest_prev'] if row['P_nearest_prev'] is not None else float('nan')):10.3f} {(row['P_top_intake_1s'] if sel else float('nan')):16.3f} {(row['P_top_prox_1s'] if sel else float('nan')):14.3f} {(chance or float('nan')):7.3f} {len(sel):6d}")
# per-participant ambient signature
d = []
for p_ in np.unique(pid):
    a_ = pdur[(pid == p_) & (amp >= 300)]; b_ = pdur[(pid == p_) & (amp < 100)]
    if len(a_) >= 8 and len(b_) >= 8:
        d.append(np.median(a_) - np.median(b_))
d = np.array(d)
out['prev_fix_major_minus_minor'] = {'n_participants': int(len(d)), 'median_ms': float(np.median(d)), 'negative': int((d < 0).sum())}
print(f"\nper-participant median(prev fix | major >= 300 px) - median(prev fix | minor < 100 px): {np.median(d):+.0f} ms, negative in {(d < 0).sum()}/{len(d)}")
# windows, major saccades
maj = amp >= 300; wins = {}
print('\nmajor (>= 300 px), P(target = top intake) / P(target = closest to any fixation in the window), by window (>= 3 candidates)')
for W in WINS:
    sel = [e for e, mm in zip(ev, maj) if mm and f'top_intake_{W}' in e and e['n_c'] >= 3]
    if sel:
        wins[W] = {'n': len(sel), 'top_intake': float(np.mean([e[f'top_intake_{W}'] for e in sel])), 'top_prox': float(np.mean([e[f'top_prox_{W}'] for e in sel]))}
        print(f"  {W:5d} ms  n={len(sel):6d}  intake {wins[W]['top_intake']:.3f}  proximity {wins[W]['top_prox']:.3f}")
out['major_windows'] = wins
sel = [e for e, mm in zip(ev, amp >= 600) if mm and 'top_intake_1000' in e and e['n_c'] >= 3]
out['top_intake_not_nearest'] = {name: float(np.mean([e['top_intake_1000'] and not e['nearest_prev'] for e, mm in zip(ev, (amp >= lo) & (amp < hi)) if mm and 'top_intake_1000' in e and e['n_c'] >= 3])) for name, lo, hi in BINS}
print('\nP(top intake and not nearest): ' + ', '.join(f'{k} {v:.3f}' for k, v in out['top_intake_not_nearest'].items()))
json.dump(out, open(ROOT / 'scripts/output/major_saccade_selection/summary.json', 'w'), indent=1)
print('\nwrote scripts/output/major_saccade_selection/summary.json')
