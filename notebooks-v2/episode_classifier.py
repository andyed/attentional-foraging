"""
episode_classifier.py — forward/regressive classification of cursor/gaze episodes.

An *episode* is a single visit to a search result (enter-dwell-exit). Every
notebook defines episodes differently: NB17 uses scroll-based retreats, NB20
uses aggregated approach features, NB24 extracts retreat arcs from cursor
tracks. This module does not detect episodes — it answers one question: given
an episode entry time, was the user moving forward through the SERP or
regressing back to re-examine something already passed?

Rule (mirrors `classify_fixations` in data_loader.py):
    forward iff scroll_offset(entry_t) >= hwm_at_entry - tol_px

where hwm_at_entry is the running maximum of scroll offsets sampled at every
fixation up to and including entry_t. Classification is frozen at entry time —
a regressive re-examination is not relabeled "forward" if the user later
scrolls further down.

The `tol_px=50` default matches `data_loader.classify_fixations`, which is the
canonical per-fixation implementation this module wraps at episode granularity.
"""

from bisect import bisect_right

import numpy as np

# ── HWM timeline cache ────────────────────────────────────────────────────

_HWM_CACHE = {}


def build_hwm_timeline(trial):
    """Build the scroll high-water-mark timeline for a trial.

    Walks fixations in time order and records, for each fixation, the scroll
    offset sampled at that fixation and the running max over all prior
    fixations. Cached by `trial_id`.

    Args:
        trial: dict from load_trial()

    Returns:
        (fix_ts, fix_scroll, fix_hwm) — three np.ndarrays of equal length.
          fix_ts:     fixation timestamps (ms), sorted ascending
          fix_scroll: scroll offset at each fixation (last-known-value lookup
                      into trial['scroll_ts'] / trial['scroll_ys'])
          fix_hwm:    running max of fix_scroll up to and including fix i
        Returns three empty arrays if the trial has no fixations.
    """
    tid = trial['trial_id']
    cached = _HWM_CACHE.get(tid)
    if cached is not None:
        return cached

    fixations = trial['fixations']
    sts = trial['scroll_ts']
    sys_ = trial['scroll_ys']

    n = len(fixations)
    fix_ts = np.empty(n, dtype=np.float64)
    fix_scroll = np.empty(n, dtype=np.float64)
    fix_hwm = np.empty(n, dtype=np.float64)

    hwm = 0.0
    for i, fix in enumerate(fixations):
        t = fix['t']
        # Last-known-value scroll lookup — must match classify_fixations
        # exactly for parity. No linear interpolation.
        if not sts:
            so = 0.0
        elif t <= sts[0]:
            so = sys_[0]
        elif t >= sts[-1]:
            so = sys_[-1]
        else:
            so = sys_[bisect_right(sts, t) - 1]

        if so > hwm:
            hwm = so

        fix_ts[i] = t
        fix_scroll[i] = so
        fix_hwm[i] = hwm

    # Defensive: bisect_right on fix_ts assumes monotone-nondecreasing time.
    # AdSERP fixations are I-DT-filtered and already time-sorted, but a
    # stale cache or a custom trial dict could violate this. Check once.
    if n > 1 and not np.all(np.diff(fix_ts) >= 0):
        raise ValueError(
            f'trial {tid}: fixation timestamps are not monotone-nondecreasing; '
            'classify_episode bisect lookups would be ill-defined'
        )

    result = (fix_ts, fix_scroll, fix_hwm)
    _HWM_CACHE[tid] = result
    return result


def _scroll_at(t, sts, sys_):
    """Last-known-value scroll lookup at time t. Matches classify_fixations."""
    if not sts:
        return 0.0
    if t <= sts[0]:
        return sys_[0]
    if t >= sts[-1]:
        return sys_[-1]
    return sys_[bisect_right(sts, t) - 1]


def classify_episode(entry_t, trial, tol_px=50.0):
    """Classify a single episode as forward or regressive at entry time.

    Args:
        entry_t: episode entry timestamp (ms)
        trial: dict from load_trial()
        tol_px: pixels below HWM that still count as forward (default 50,
            matches data_loader.classify_fixations).

    Returns:
        dict with:
          direction:    'forward' | 'regressive'
          entry_scroll: scroll offset at entry_t
          hwm_at_entry: max scroll offset sampled at any fixation with
                        t <= entry_t, union'd with entry_scroll itself
          hwm_deficit:  max(0, hwm_at_entry - entry_scroll)
          confidence:   1.0 when |deficit - tol_px| >= tol_px (clearly one
                        side of the band); ramps linearly to 0 inside the
                        ±tol_px uncertainty band around the boundary.

    Rule: forward iff entry_scroll >= hwm_at_entry - tol_px.
    """
    fix_ts, _fix_scroll, fix_hwm = build_hwm_timeline(trial)

    sts = trial['scroll_ts']
    sys_ = trial['scroll_ys']
    entry_scroll = _scroll_at(entry_t, sts, sys_)

    # HWM from all fixations up to and including entry_t.
    if len(fix_ts) == 0:
        hwm_from_fixations = 0.0
    else:
        idx = bisect_right(fix_ts, entry_t) - 1
        hwm_from_fixations = float(fix_hwm[idx]) if idx >= 0 else 0.0

    # Union with entry_scroll itself — consistent with classify_fixations
    # which updates HWM with the current sample before the forward test.
    hwm_at_entry = max(hwm_from_fixations, entry_scroll)

    hwm_deficit = max(0.0, hwm_at_entry - entry_scroll)
    direction = 'forward' if entry_scroll >= hwm_at_entry - tol_px else 'regressive'

    # Confidence: 0 inside the band, ramps to 1 at distance tol_px from the
    # boundary. Useful for flagging borderline episodes in audit.
    distance_from_boundary = abs(hwm_deficit - tol_px)
    confidence = float(min(1.0, distance_from_boundary / tol_px)) if tol_px > 0 else 1.0

    return {
        'direction': direction,
        'entry_scroll': float(entry_scroll),
        'hwm_at_entry': float(hwm_at_entry),
        'hwm_deficit': float(hwm_deficit),
        'confidence': confidence,
    }


def classify_trial_episodes(trial, episodes, tol_px=50.0, entry_t_key='entry_t'):
    """Classify a list of episodes for a single trial.

    Args:
        trial: dict from load_trial()
        episodes: list of dicts, each carrying `entry_t` (override key via
            `entry_t_key` if the caller uses a different name)
        tol_px: forward tolerance (default 50)
        entry_t_key: name of the entry timestamp field on each episode

    Returns:
        (classified, summary)
          classified: list of the input episodes with classification fields
                      merged in (`direction`, `entry_scroll`, `hwm_at_entry`,
                      `hwm_deficit`, `confidence`). The original dicts are
                      not mutated.
          summary:    {'forward_count', 'regressive_count', 'total'}
    """
    # Warm the cache once for the trial.
    build_hwm_timeline(trial)

    classified = []
    fwd = 0
    reg = 0
    for ep in episodes:
        info = classify_episode(ep[entry_t_key], trial, tol_px=tol_px)
        merged = dict(ep)
        merged.update(info)
        classified.append(merged)
        if info['direction'] == 'forward':
            fwd += 1
        else:
            reg += 1

    total = len(episodes)
    assert fwd + reg == total, f'mass balance: {fwd}+{reg} != {total}'

    return classified, {
        'forward_count': fwd,
        'regressive_count': reg,
        'total': total,
    }


def clear_cache():
    """Clear the HWM timeline cache. Useful in long-running notebooks that
    reload trials after tweaking fixation filters."""
    _HWM_CACHE.clear()
