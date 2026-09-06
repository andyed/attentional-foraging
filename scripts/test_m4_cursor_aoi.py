"""Regression checks for the typed, cursor-only M4 stream.

Run: .venv/bin/python -m unittest discover -s scripts -p test_m4_cursor_aoi.py
"""
import copy
import json
import os
from pathlib import Path
import unittest

from m4_cursor_aoi_rerun import prepare_trial, strict_click_position, track_batch

ROOT = Path(os.environ.get('M4_TEST_REPO_ROOT', Path(__file__).resolve().parent.parent))
TRACKER = ROOT.parent / 'approach-retreat/src/approach-retreat.js'
BRIDGE = Path(__file__).with_name('m4_cursor_tracker.mjs')


class CursorStreamTests(unittest.TestCase):
    def setUp(self):
        # Boxes in screenshot space, mouse in document space. The clicked
        # card's center must become document y=500, not screenshot y=450.
        self.cards = [
            dict(position=0, type='organic', x=90, y=360, width=180, height=180),
            dict(position=1, type='organic', x=90, y=720, width=180, height=180),
        ]
        self.geometry = dict(ratio_x=.9, ratio_y=.9)
        self.events = [(t, 'mousemove', 200, y) for t, y in
                       [(0, 700), (100, 580), (200, 540), (300, 620), (400, 560)]]
        self.clicks = [(1000, 200, 500)]

    def prepare(self, events=None, clicks=None):
        return prepare_trial('p001-b1-t1', self.cards,
                             self.events if events is None else events,
                             self.clicks if clicks is None else clicks,
                             self.geometry, [0, 500])

    def test_coordinate_conversion_and_actual_js_features(self):
        trial, reason = self.prepare()
        self.assertEqual(reason, 'included')
        self.assertEqual(trial['aois'][0]['center_document_y'], 500)
        result = track_batch([trial], BRIDGE, TRACKER)[0]['buf500'][0]
        expected = dict(min_dist=40, mean_dist=100, final_dist=60,
                        retreat_dist=20, dwell_in_proximity_ms=300,
                        mean_approach_velocity=350, max_approach_velocity=1200,
                        direction_changes=2, frac_decreasing=.75, sample_count=5)
        for key, value in expected.items():
            self.assertAlmostEqual(result[key], value, msg=key)
        self.assertTrue(result['was_clicked'])

    def test_cutoff_is_strict_and_click_mouseover_are_not_samples(self):
        baseline, _ = self.prepare()
        altered = self.events + [(450, 'click', 200, 10000),
                                 (450, 'mouseover', 200, 10000),
                                 (500, 'mousemove', 200, 9000),
                                 (900, 'mousemove', 200, 8000),
                                 (1000, 'mousemove', 200, 500)]
        changed, _ = self.prepare(events=altered)
        first, second = track_batch([baseline, changed], BRIDGE, TRACKER)
        self.assertEqual(first['buf500'], second['buf500'])
        self.assertNotEqual(first['buf0'][0]['mean_dist'], second['buf0'][0]['mean_dist'])
        self.assertEqual(second['buf0'][0]['sample_count'], 7)

    def test_no_gaze_conditioning_of_candidate_population(self):
        trial, _ = self.prepare()
        # The second card is never entered; it still receives a negative row.
        result = track_batch([trial], BRIDGE, TRACKER)[0]
        for records in result.values():
            self.assertEqual([r['position'] for r in records], [0, 1])
            self.assertEqual([r['was_clicked'] for r in records], [True, False])

    def test_off_axis_and_ambiguous_labels_do_not_snap(self):
        trial, reason = self.prepare(clicks=[(1000, 900, 500)])
        self.assertIsNone(trial)
        self.assertEqual(reason, 'click_outside_main_boxes')
        overlap = copy.deepcopy(self.cards)
        overlap[1].update(x=90, y=360)
        self.assertEqual(strict_click_position(overlap, 180, 450),
                         (None, 'ambiguous_click'))

    def test_corrupt_geometry_and_time_are_detected(self):
        self.cards[1]['position'] = 0
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.prepare()
        self.cards[1]['position'] = 1
        trial, reason = self.prepare(events=self.events + [(1, 'mousemove', 200, 500)])
        self.assertIsNone(trial)
        self.assertEqual(reason, 'nonmonotonic_mouse_time')

    def test_common_population_requires_two_prebuffer_timestamps(self):
        trial, reason = self.prepare(events=[(0, 'mousemove', 200, 500),
                                           (0, 'mousemove', 200, 510),
                                           (700, 'mousemove', 200, 500)])
        self.assertIsNone(trial)
        self.assertEqual(reason, 'insufficient_prebuffer_mousemove')


if __name__ == '__main__':
    unittest.main()
