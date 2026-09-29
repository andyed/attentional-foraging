"""Tests for the attention-atlas core definitions and the shipped atlas.

The unit tests use synthetic inputs and need no AdSERP data. The last test
runs the verifier over the shipped atlas in docs/visualizations/.

Run:
  .venv/bin/python -m unittest discover -s scripts -p test_attention_atlas.py
"""
import gzip
import itertools
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'attention_atlas'))
import atlas_core as core  # noqa: E402


def v(start, end, aoi):
    return {'start': start, 'end': end, 'aoi': aoi}


def brute_force_match(g, c, window):
    """Best monotone one-to-one matching by exhaustive search: max count, then min cost."""
    candidates = [(i, j) for i in range(len(g)) for j in range(len(c))
                  if g[i]['aoi'] == c[j]['aoi'] and abs(c[j]['start'] - g[i]['start']) <= window]
    best = (0, 0.0)
    for r in range(len(candidates), 0, -1):
        for combo in itertools.combinations(candidates, r):
            gi = [p[0] for p in combo]
            ci = [p[1] for p in combo]
            if all(a < b for a, b in zip(gi, gi[1:])) and all(a < b for a, b in zip(ci, ci[1:])):
                cost = sum(abs(c[j]['start'] - g[i]['start']) for i, j in combo)
                if r > best[0] or (r == best[0] and cost < best[1]):
                    best = (r, cost)
        if best[0] == r:
            break
    return best


class SyntheticTrial:
    """Just enough of atlas_core.Trial to exercise occupancy without data."""

    def __init__(self, moves, fix, st=(), sv=(), end=None):
        self.moves = np.array(moves, float)
        self.fix = np.array(fix, float)
        self.st = np.array(st, float)
        self.sv = np.array(sv, float)
        self.start = self.moves[0, 0]
        self.end = float(end)
        self.windows = np.arange(self.start, self.end + 0.01, core.MOTION_WINDOW_MS)


class VisitTests(unittest.TestCase):
    def test_bridges_unobserved_gap_but_not_an_intervening_aoi(self):
        self.assertEqual(len(core.visits([[0, 100, 2], [100, 130, -2], [130, 200, 2]], 100)), 1)
        self.assertEqual(len(core.visits([[0, 100, 2], [100, 150, 3], [150, 250, 2]], 0)), 3)

    def test_bridged_gap_does_not_count_toward_the_minimum(self):
        # 60 + 60 observed across a 50 ms gap: 120 observed, 170 elapsed.
        visits = core.visits([[0, 60, 1], [60, 110, -1], [110, 170, 1]], 150)
        self.assertEqual(visits, [])
        visits = core.visits([[0, 60, 1], [60, 110, -1], [110, 170, 1]], 120)
        self.assertEqual(len(visits), 1)
        self.assertAlmostEqual(visits[0]['observed_ms'], 120)

    def test_segments_merge_contiguous_labels(self):
        self.assertEqual(core.segments(np.array([0, 10, 20, 30]), [1, 1, 2]), [[0.0, 20.0, 1], [20.0, 30.0, 2]])


class MatchTests(unittest.TestCase):
    def test_known_pairs(self):
        g = [{'start': 0, 'aoi': 1}, {'start': 300, 'aoi': 2}]
        c = [{'start': 100, 'aoi': 1}, {'start': 500, 'aoi': 2}]
        self.assertEqual(core.match(g, c, 1000), [[0, 0, 100], [1, 1, 200]])
        self.assertEqual(core.match(g, c, 50), [])

    def test_against_brute_force(self):
        rng = random.Random(7)
        for _ in range(300):
            g = [{'start': rng.randrange(0, 3000), 'aoi': rng.randrange(3)} for _ in range(rng.randrange(0, 5))]
            c = [{'start': rng.randrange(0, 3000), 'aoi': rng.randrange(3)} for _ in range(rng.randrange(0, 5))]
            g.sort(key=lambda x: x['start'])
            c.sort(key=lambda x: x['start'])
            window = rng.choice([200, 800, 2000])
            pairs = core.match(g, c, window)
            count, cost = brute_force_match(g, c, window)
            self.assertEqual(len(pairs), count)
            self.assertAlmostEqual(sum(abs(d) for _, _, d in pairs), cost)
            self.assertEqual(len({p[0] for p in pairs}), len(pairs))
            self.assertEqual(len({p[1] for p in pairs}), len(pairs))


class SequenceTests(unittest.TestCase):
    def test_repeated_occupancy_keeps_the_direction(self):
        stats = core.sequence_stats([v(i * 100, i * 100 + 100, k) for i, k in enumerate([4, 4, 3, 3, 4])])
        self.assertEqual((stats['transitions'], stats['backward'], stats['reversals']), (2, 1, 1))

    def test_long_gap_breaks_the_chain(self):
        stats = core.sequence_stats([v(0, 100, 1), v(700, 800, 2), v(900, 1000, 1)])
        # 1->2 is 600 ms apart (not counted); 2->1 counts with no prior direction.
        self.assertEqual((stats['transitions'], stats['backward'], stats['reversals']), (1, 1, 0))


class StateTests(unittest.TestCase):
    def test_coverage_overrides_space(self):
        ga, ca = np.array([1, 1, 2, -1, 1]), np.array([1, 2, 5, 3, 1])
        gv = np.array([True, True, True, True, False])
        cv = np.array([True, True, True, True, True])
        self.assertEqual(core.joint_states(ga, ca, gv, cv).tolist(),
                         ['same', 'adjacent', 'other', 'cursor_only', 'no_fixation'])

    def test_occupancy_conserves_the_clock_and_expires_the_hold(self):
        # Cursor moves at 0 and 500, then is still; fixations cover 100-400 and 3000-3500.
        tr = SyntheticTrial(moves=[[0, 10, 10], [500, 20, 20]], fix=[[100, 10, 10, 300], [3000, 10, 10, 500]], end=4000)
        edges = core.interval_edges(tr, tr.windows)
        o = core.occupancy(tr, edges)
        self.assertAlmostEqual(o['dt'].sum(), 4000)
        covered = o['dt'][o['cv']].sum()
        self.assertAlmostEqual(covered, 2500)  # held until 500 + 2000
        o = core.occupancy(tr, edges, hold_ms=None)
        self.assertAlmostEqual(o['dt'][o['cv']].sum(), 4000)
        self.assertAlmostEqual(o['dt'][o['gv']].sum(), 800)

    def test_scroll_shift_moves_a_held_cursor_with_the_page(self):
        tr = SyntheticTrial(moves=[[0, 10, 100]], fix=[[-1, 0, 0, 0]], st=[1000], sv=[250], end=2000)
        o = core.occupancy(tr, np.array([0, 1000, 2000.]), hold_ms=None, shift_with_scroll=True)
        self.assertEqual(o['cy'].tolist(), [100, 350])

    def test_cursor_endpoints_hold_and_interpolate(self):
        tr = SyntheticTrial(moves=[[0, 0, 0], [200, 100, 0], [2600, 200, 0]], fix=[[-1, 0, 0, 0]], end=3000)
        pos = core.cursor_endpoints(tr)
        self.assertEqual(pos[1, 0], 50)          # 100 ms into a 200 ms gap: interpolated
        self.assertEqual(pos[3, 0], 100)         # 300 ms: past the last sample, held
        self.assertTrue(np.isnan(pos[23, 0]))    # 2300 ms: 2.1 s after the sample, hold expired
        self.assertFalse(np.isnan(core.cursor_endpoints(tr, hold_ms=None)[23, 0]))


class InfrastructureTests(unittest.TestCase):
    def test_gate_raises_with_a_message(self):
        with self.assertRaises(SystemExit) as cm:
            core.gate(False, 'reason')
        self.assertIn('reason', str(cm.exception))
        core.gate(True, 'not raised')

    def test_gzip_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.json.gz', Path(tmp) / 'b.json.gz'
            core.write_json_gz(a, {'x': [1, 2.5]})
            core.write_json_gz(b, {'x': [1, 2.5]})
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(core.read_json(a), {'x': [1, 2.5]})
            self.assertEqual(gzip.decompress(a.read_bytes()), b'{"x":[1,2.5]}')

    def test_provenance_paths_are_repository_relative(self):
        self.assertEqual(core.rel(core.ROOT / 'README.md'), 'README.md')
        self.assertEqual(core.rel(core.ATLAS / 'gaze-cursor-echo/summary.json'),
                         'docs/visualizations/gaze-cursor-echo/summary.json')


class ShippedAtlasTests(unittest.TestCase):
    def test_verifier_passes_on_the_shipped_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Verify a copy, so the report the verifier writes does not touch the tree.
            import shutil
            atlas = Path(tmp) / 'visualizations'
            shutil.copytree(core.CANONICAL_ATLAS, atlas)
            env = dict(os.environ, AF_ATLAS_DIR=str(atlas), PYTHONDONTWRITEBYTECODE='1')
            proc = subprocess.run([sys.executable, str(HERE / 'attention_atlas/verify-atlas.py')],
                                  env=env, capture_output=True, text=True, cwd=str(HERE / 'attention_atlas'))
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
