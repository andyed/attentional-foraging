"""Shared definitions for the attention-atlas producers, checks and renderers.

Every measurement rule that more than one producer uses lives here once:
trial reconstruction, the cursor hold and interpolation rule, occupancy
intervals, joint AOI states, visits, visit matching and sequence counts.
The three producers previously carried copies of this code, so a defect in
one copy could pass every reproduction gate.

Importing this module has no side effects. It reads no data, creates no
directories and does not import the AdSERP loader until a trial is
reconstructed, so tests and the verifier can import it without raw data.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
# Canonical location of the atlas. AF_ATLAS_DIR redirects every read and write
# to a copy for an isolated rebuild; provenance paths still name the canonical
# location so a rebuilt copy produces the same summaries.
CANONICAL_ATLAS = ROOT / 'docs' / 'visualizations'
ATLAS = Path(os.environ.get('AF_ATLAS_DIR', CANONICAL_ATLAS)).resolve()

# ---------------------------------------------------------------------------
# Measurement constants. Changing one changes shipped numbers: rerun every
# producer, then pin the new values deliberately (verify-atlas.py --pin).
# ---------------------------------------------------------------------------
CURSOR_HOLD_MS = 2000           # a mousemove position is held at most this long
CURSOR_INTERP_MAX_GAP_MS = 250  # cursor endpoints interpolate only across short gaps
MOTION_WINDOW_MS = 100          # complete, non-overlapping displacement windows
GAZE_ENDPOINT_HALF_WINDOW_MS = 20
GAZE_MOVING_PX_S = 300
CURSOR_MOVING_PX_S = 50
MOTION_THRESHOLDS_PX_S = ((150, 25), (300, 50), (600, 100))  # halved, primary, doubled
REST_PX_S = 50                  # cursor "rest": below this endpoint speed
REST_THRESHOLDS_PX_S = (25, 50, 100)
VISIT_MIN_MS = 100              # minimum observed occupancy for a qualifying visit
VISIT_MIN_SENSITIVITY_MS = (0, 100, 200)
VISIT_MERGE_GAP_MS = 100        # same-AOI segments merge across gaps this short
SEQUENCE_CHAIN_GAP_MS = 500     # longer gaps break an AOI-change chain
MATCH_WINDOWS_MS = (500, 1000, 2000, 5000)
PRIMARY_MATCH_WINDOW_MS = 2000
PAUSE_MIN_MS = 1000             # a cursor pause is at least this long
TIMECOURSE_BINS = 20
BOOTSTRAP_RESAMPLES = 2000
SEED_INFORMATION_SPACE = 20260927  # information-space and resting-cursor CIs
SEED_SEQUENCES = 20260929          # sequence, timing and common-coverage CIs
GATE_TOLERANCE_MS = 1e-4
CONSERVATION_TOLERANCE_MS = 1e-6
WORKERS = 8
COHORT_TRIALS = 2650
COHORT_PARTICIPANTS = 47

# AOI labels in segment arrays.
OFF_AOI = -1
UNOBSERVED = -2


# ---------------------------------------------------------------------------
# Gates, provenance and JSON I/O
# ---------------------------------------------------------------------------
class GateFailure(SystemExit):
    """A failed reproduction or integrity gate. Exits non-zero with a message.

    Gates are not `assert` statements: `python -O` strips asserts, which would
    let a failed gate exit 0.
    """


def gate(condition, message):
    if not condition:
        raise GateFailure(f'GATE FAILED: {message}')


def rel(path):
    """Repository-relative provenance path, independent of AF_ATLAS_DIR."""
    p = Path(path).resolve()
    for base, prefix in ((ATLAS, 'docs/visualizations/'), (ROOT, '')):
        try:
            return prefix + p.relative_to(base).as_posix()
        except ValueError:
            continue
    return p.name


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes(paths):
    return {rel(p): sha256(p) for p in paths}


def read_json(path):
    """Read JSON, or gzip-compressed JSON when the path ends in .gz."""
    path = Path(path)
    if path.suffix == '.gz':
        return json.loads(gzip.decompress(path.read_bytes()))
    return json.loads(path.read_text())


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2))


def write_json_gz(path, obj):
    """Compact JSON, gzip with a zero timestamp so identical data gives identical bytes."""
    data = json.dumps(obj, separators=(',', ':')).encode()
    with open(path, 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz:
        gz.write(data)


def canonical_digest(obj):
    """Order-independent digest of JSON content, for pinning values rather than bytes."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_cohort():
    """The saved cohort: trial IDs, press times, target AOIs, approach onsets."""
    with (ATLAS / 'evidence/final-approach/trial-summary.csv').open() as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Trial reconstruction
# ---------------------------------------------------------------------------
_DATA_LOADER = None


def data_loader():
    global _DATA_LOADER
    if _DATA_LOADER is None:
        sys.path.insert(0, str(ROOT / 'notebooks-v2'))
        import data_loader as dl
        _DATA_LOADER = dl
    return _DATA_LOADER


class Trial:
    """One trial on the atlas clock: first native mousemove to final press.

    Coordinates are screenshot page space. `fix` rows are (t, x, y, duration);
    `moves` rows are (t, x, y). A trial with no recorded fixation gets one
    zero-length placeholder before the clock, so no interval is covered.
    """

    def __init__(self, row):
        dl = data_loader()
        self.row = row
        self.trial_id = row['trial_id']
        self.pid = self.trial_id.split('-')[0]
        self.end = float(row['press_ms'])
        self.geo = dl.get_trial_geometry(self.trial_id)
        gate(self.geo is not None and self.geo.get('derived') == 'screenshot',
             f"{self.trial_id}: screenshot geometry unavailable (derived={self.geo and self.geo.get('derived')}); "
             'mount the AdSERP full-page screenshots before rebuilding')
        self.sx, self.sy = self.geo['ratio_x'], self.geo['ratio_y']
        self.cards = sorted(
            [c for c in dl.load_typed_aois(self.trial_id)
             if c.get('position', -1) >= 0 and all(np.isfinite(c[k]) for k in ['x', 'y', 'width', 'height'])],
            key=lambda c: c['position'])
        events, scrolls, self.clicks = dl.load_mouse_events(self.trial_id, space='document')
        self.moves = np.array([(t, x * self.sx, y * self.sy) for t, e, x, y in events
                               if e == 'mousemove' and t < self.end and np.all(np.isfinite([t, x, y]))])
        fix = np.array([(f['t'], f['x'], f['y'], f['d'])
                        for f in sorted(dl.load_fixations(self.trial_id), key=lambda f: f['t'])
                        if all(np.isfinite(f[k]) for k in ['t', 'x', 'y', 'd'])])
        self.no_fixations = len(fix) == 0
        self.fix = np.array([[self.moves[0, 0] - 1, 0, 0, 0.]]) if self.no_fixations else fix
        self.st = np.array([s[0] for s in scrolls])
        self.sv = np.array([s[1] * self.sy for s in scrolls])
        self.start = self.moves[0, 0]
        self.windows = np.arange(self.start, self.end + 0.01, MOTION_WINDOW_MS)


def aoi(x, y, cards):
    """Position of the strict x/y AOI rectangle containing each point, else OFF_AOI."""
    out = np.full(len(x), OFF_AOI, dtype=int)
    for c in cards:
        sel = (x >= c['x']) & (x <= c['x'] + c['width']) & (y >= c['y']) & (y <= c['y'] + c['height']) & (out == OFF_AOI)
        out[sel] = int(c['position'])
    return out


def inside(x, y, c):
    return (x >= c['x']) & (x <= c['x'] + c['width']) & (y >= c['y']) & (y <= c['y'] + c['height'])


def durations(keys, dt):
    return {str(k): float(dt[keys == k].sum()) for k in np.unique(keys)}


def scroll_at(t, st, sv):
    """Page scroll offset in effect at each time (0 before the first scroll)."""
    if not len(st):
        return np.zeros_like(t, dtype=float)
    i = np.searchsorted(st, t, side='right')
    return np.where(i > 0, sv[np.maximum(0, i - 1)], 0)


def interval_edges(trial, *extra):
    """Every time at which an occupancy state can change, clipped to the clock."""
    edges = np.unique(np.r_[trial.start, trial.end, trial.moves[:, 0], trial.moves[:, 0] + CURSOR_HOLD_MS,
                            trial.fix[:, 0], trial.fix[:, 0] + trial.fix[:, 3], trial.st, *extra])
    return edges[(edges >= trial.start) & (edges <= trial.end)]


def occupancy(trial, edges, hold_ms=CURSOR_HOLD_MS, shift_with_scroll=False):
    """Held cursor and recorded fixation at each interval midpoint.

    The primary rule holds each mousemove's page position for at most hold_ms
    and does not follow page scroll. The sensitivities relax it: hold_ms=None
    holds until the next mousemove (the logger records the cursor only when it
    moves), and shift_with_scroll=True moves the held page position with the
    scroll offset, since a still cursor keeps its screen position while the
    page scrolls under it.
    """
    a, b = edges[:-1], edges[1:]
    mid = (a + b) / 2
    ci = np.maximum(0, np.searchsorted(trial.moves[:, 0], mid, side='right') - 1)
    cx, cy = trial.moves[ci, 1], trial.moves[ci, 2]
    if shift_with_scroll:
        cy = cy + scroll_at(mid, trial.st, trial.sv) - scroll_at(trial.moves[ci, 0], trial.st, trial.sv)
    if hold_ms is None:
        cv = np.ones(len(mid), bool)
    else:
        cv = mid < trial.moves[ci, 0] + hold_ms
    gi = np.searchsorted(trial.fix[:, 0], mid, side='right') - 1
    gc = np.maximum(0, gi)
    gv = (gi >= 0) & (mid < trial.fix[gc, 0] + trial.fix[gc, 3])
    return {'a': a, 'b': b, 'dt': b - a, 'mid': mid, 'ci': ci, 'cx': cx, 'cy': cy, 'cv': cv,
            'gc': gc, 'gx': trial.fix[gc, 1], 'gy': trial.fix[gc, 2], 'gv': gv}


def joint_states(ga, ca, gv, cv):
    """Gaze/cursor AOI relation; coverage states override spatial ones."""
    state = np.full(len(ga), 'both_off', dtype='<U24')
    go, co = ga >= 0, ca >= 0
    state[go & ~co] = 'gaze_only'
    state[co & ~go] = 'cursor_only'
    state[go & co] = 'other'
    state[go & co & (abs(ga - ca) == 1)] = 'adjacent'
    state[go & co & (ga == ca)] = 'same'
    state[~gv & cv] = 'no_fixation'
    state[gv & ~cv] = 'no_cursor'
    state[~gv & ~cv] = 'neither_recorded'
    return state


def cursor_endpoints(trial, hold_ms=CURSOR_HOLD_MS):
    """Screen-space cursor position at each motion-window endpoint.

    Interpolates only across gaps of at most CURSOR_INTERP_MAX_GAP_MS; otherwise
    holds the previous sample, for at most hold_ms (None: until the next sample).
    """
    moves, me = trial.moves, trial.windows
    ix = np.maximum(0, np.searchsorted(moves[:, 0], me, side='right') - 1)
    nx = np.minimum(len(moves) - 1, ix + 1)
    age = me - moves[ix, 0]
    gap = moves[nx, 0] - moves[ix, 0]
    weight = np.divide(age, gap, out=np.zeros_like(age), where=(gap > 0) & (gap <= CURSOR_INTERP_MAX_GAP_MS))
    weight = np.clip(weight, 0, 1)
    cpos = moves[ix, 1:3] + weight[:, None] * (moves[nx, 1:3] - moves[ix, 1:3])
    cpos[:, 1] -= scroll_at(me, trial.st, trial.sv)
    if hold_ms is not None:
        cpos[age > hold_ms] = np.nan
    return cpos


def window_speed(positions):
    """Endpoint displacement per window, as px/s."""
    return np.linalg.norm(np.diff(positions, axis=0), axis=1) * (1000 / MOTION_WINDOW_MS)


def scroll_windows(trial):
    """Windows that contain a scroll event; they are never classified."""
    me = trial.windows
    return (np.searchsorted(trial.st, me[1:], side='right') - np.searchsorted(trial.st, me[:-1], side='right')) > 0


def window_lookup(trial, mid, speed, valid):
    """Map interval midpoints to their complete motion window: (classifiable, speed)."""
    wi = np.searchsorted(trial.windows, mid, side='right') - 1
    if not len(speed):
        return np.zeros(len(mid), bool), np.full(len(mid), np.nan)
    in_range = (wi >= 0) & (wi < len(speed))
    wc = np.clip(wi, 0, max(0, len(speed) - 1))
    return in_range & valid[wc], speed[wc]


# ---------------------------------------------------------------------------
# Visits, matching and sequences
# ---------------------------------------------------------------------------
def segments(edges, labels):
    """Merge consecutive intervals with the same label into [start, end, label]."""
    out = []
    for a, b, k in zip(edges[:-1], edges[1:], labels):
        if out and out[-1][2] == int(k) and abs(out[-1][1] - a) < 1e-6:
            out[-1][1] = float(b)
        else:
            out.append([float(a), float(b), int(k)])
    return out


def visits(segs, minimum=VISIT_MIN_MS, gap=VISIT_MERGE_GAP_MS):
    """Qualifying visits from AOI segments.

    Same-AOI segments merge across off-AOI or unobserved gaps of at most `gap`
    ms, never across an intervening different AOI. Bridged gaps do not count
    toward `observed_ms`; a visit qualifies with at least `minimum` observed.
    """
    out = []
    candidate = None
    for a, b, k in segs:
        if k < 0:
            continue
        if candidate and candidate['aoi'] == k and a - candidate['end'] <= gap:
            candidate['end'] = b
            candidate['observed_ms'] += b - a
        else:
            candidate = {'start': a, 'end': b, 'aoi': k, 'observed_ms': b - a}
            out.append(candidate)
    return [v for v in out if v['observed_ms'] >= minimum]


def match(g, c, window):
    """Maximum-cardinality, monotone, one-to-one same-AOI matching of visit onsets.

    Among maximum matchings, minimizes the summed absolute onset difference.
    Returns [gaze index, cursor index, cursor onset - gaze onset].
    """
    n, m = len(g), len(c)
    count = np.zeros((n + 1, m + 1), int)
    cost = np.zeros((n + 1, m + 1))
    choice = np.zeros((n + 1, m + 1), int)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opts = [(count[i - 1, j], -cost[i - 1, j], 1), (count[i, j - 1], -cost[i, j - 1], 2)]
            d = c[j - 1]['start'] - g[i - 1]['start']
            if g[i - 1]['aoi'] == c[j - 1]['aoi'] and abs(d) <= window:
                opts.append((count[i - 1, j - 1] + 1, -cost[i - 1, j - 1] - abs(d), 3))
            v = max(opts, key=lambda z: (z[0], z[1], z[2]))
            count[i, j] = v[0]
            cost[i, j] = -v[1]
            choice[i, j] = v[2]
    pairs = []
    i, j = n, m
    while i and j:
        k = choice[i, j]
        if k == 3:
            pairs.append([i - 1, j - 1, c[j - 1]['start'] - g[i - 1]['start']])
            i -= 1
            j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def sequence_stats(v):
    """AOI changes, backward steps and direction reversals between visits.

    A gap over SEQUENCE_CHAIN_GAP_MS breaks the chain. Repeated occupancy of
    the same AOI does not erase the last direction, so coverage fragmentation
    is not counted as movement.
    """
    transitions = backward = reversals = 0
    last_direction = 0
    previous = None
    for current in v:
        if previous is not None:
            if current['start'] - previous['end'] > SEQUENCE_CHAIN_GAP_MS:
                last_direction = 0
            else:
                delta = current['aoi'] - previous['aoi']
                if delta:
                    direction = int(np.sign(delta))
                    transitions += 1
                    backward += int(delta < 0)
                    reversals += int(last_direction != 0 and direction != last_direction)
                    last_direction = direction
        previous = current
    return {'visits': len(v), 'transitions': transitions, 'backward': backward,
            'reversals': reversals, 'distinct_aois': len(set(x['aoi'] for x in v))}


def common_coverage(trial_record):
    """Recount both channels' sequences over time covered by both signals.

    Works from a saved per-trial record (segments, first arrivals); it does
    not reread raw recordings.
    """
    g = np.array(trial_record['gaze_segments'])
    c = np.array(trial_record['cursor_segments'])
    edges = np.unique(np.r_[g[:, 0], g[:, 1], c[:, 0], c[:, 1]])
    mid = (edges[:-1] + edges[1:]) / 2
    dt = np.diff(edges)
    gi = np.maximum(0, np.searchsorted(g[:, 0], mid, side='right') - 1)
    ci = np.maximum(0, np.searchsorted(c[:, 0], mid, side='right') - 1)
    gl = g[gi, 2].astype(int)
    cl = c[ci, 2].astype(int)
    covered = (gl != UNOBSERVED) & (cl != UNOBSERVED)
    gl[~covered] = UNOBSERVED
    cl[~covered] = UNOBSERVED
    v = {ch: visits(segments(edges, labels), VISIT_MIN_MS) for ch, labels in [('gaze', gl), ('cursor', cl)]}
    return {'trial_id': trial_record['trial_id'], 'pid': trial_record['pid'], 'common_ms': float(dt[covered].sum()),
            'gaze': sequence_stats(v['gaze']), 'cursor': sequence_stats(v['cursor']),
            'first_lags_without_boundary': [x['lag_ms'] for x in trial_record['first_arrivals']
                                            if x['gaze_ms'] > 0 and x['cursor_ms'] > 0]}


# ---------------------------------------------------------------------------
# Participant-cluster bootstrap
# ---------------------------------------------------------------------------
def bootstrap_indices(n_participants, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_participants, size=(BOOTSTRAP_RESAMPLES, n_participants))


def ratio_ci(numerators, denominators, pids, boot, scale=100):
    """Pooled ratio of sums with a participant-cluster percentile 95% CI."""
    nn = np.array([numerators.get(p, 0) for p in pids])
    dd = np.array([denominators.get(p, 0) for p in pids])
    r = scale * nn[boot].sum(1) / dd[boot].sum(1)
    return {'percent': scale * nn.sum() / dd.sum(), 'ci95': np.percentile(r, [2.5, 97.5]).tolist()}
