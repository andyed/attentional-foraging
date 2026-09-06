"""Regression checks for the typed, cursor-only M4 stream.

Run: .venv/bin/python -m unittest discover -s scripts -p test_m4_cursor_aoi.py
"""
import copy
import json
import os
from pathlib import Path
import unittest

from m4_cursor_aoi_rerun import (prepare_trial, strict_click_position, track_batch,
                                 within_trial_ranking, downsample_samples,
                                 gaze_gated_samples, fifth_fixation_end, load_flavor_cards)

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

    def test_mousedown_anchor_cuts_press_and_post_press_samples(self):
        # Press at 450; two post-press moves and the click at 1000. The logged
        # click is late relative to the press, so the anchor must be the press.
        events = self.events + [(450, 'mousedown', 200, 560), (500, 'mousemove', 200, 9000),
                                (560, 'mouseup', 200, 9000), (900, 'mousemove', 200, 8000)]
        trial, reason = prepare_trial('p001-b1-t1', self.cards, events, self.clicks,
                                      self.geometry, [0, 200], anchor='mousedown')
        self.assertEqual(reason, 'included')
        self.assertEqual(trial['anchor_t'], 450)
        self.assertEqual(trial['click_t'], 1000)
        result = track_batch([trial], BRIDGE, TRACKER)[0]
        self.assertEqual(result['buf0'][0]['sample_count'], 5)
        self.assertEqual(result['buf200'][0]['sample_count'], 3)
        by_click, _ = prepare_trial('p001-b1-t1', self.cards, events, self.clicks,
                                    self.geometry, [0, 200], anchor='click')
        self.assertEqual(by_click['anchor_t'], 1000)
        self.assertEqual(track_batch([by_click], BRIDGE, TRACKER)[0]['buf0'][0]['sample_count'], 7)

    def test_mousedown_anchor_requires_a_press_before_the_click(self):
        trial, reason = prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                                      self.geometry, [0, 500], anchor='mousedown')
        self.assertIsNone(trial)
        self.assertEqual(reason, 'no_mousedown_for_final_click')
        with self.assertRaisesRegex(ValueError, 'anchor'):
            prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                          self.geometry, [0, 500], anchor='mouseup')

    def test_within_trial_ranking_scores_one_click_per_trial(self):
        trial_ids = ['a', 'a', 'a', 'b', 'b', 'c', 'c']
        y = [0, 1, 0, 1, 0, 1, 0]
        proba = [.1, .9, .5, .4, .6, .5, .5]  # a: rank 1; b: rank 2; c: tie -> rank 1
        out = within_trial_ranking(trial_ids, y, proba)
        self.assertEqual(out['n_ranked_trials'], 3)
        self.assertAlmostEqual(out['mrr_at_10'], (1 + .5 + 1) / 3)
        self.assertAlmostEqual(out['ndcg_at_1'], 2 / 3)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            within_trial_ranking(['a', 'a'], [1, 1], [.5, .5])

    def test_downsampling_is_greedy_and_keeps_first_sample(self):
        samples = [[0, 1], [100, 2], [200, 3], [300, 4], [400, 5]]
        self.assertEqual(downsample_samples(samples, 5), [[0, 1], [200, 3], [400, 5]])
        self.assertEqual(downsample_samples(samples, 0), samples)
        trial, reason = prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                                      self.geometry, [0, 500], downsample_hz=5)
        self.assertEqual(reason, 'included')
        self.assertEqual([t for t, _ in trial['samples']], [0, 200, 400])

    def test_gaze_gated_sampling_interpolates_at_fixation_onsets_only(self):
        samples = [[0, 700], [100, 580], [200, 540]]
        self.assertEqual(gaze_gated_samples(samples, [50, 150, 250, -10]),
                         [[50.0, 640.0], [150.0, 560.0]])
        self.assertEqual(gaze_gated_samples([[0, 1]], [0]), [])

    def test_window_uses_end_of_fifth_fixation(self):
        fix = [dict(t=10 * i, d=5) for i in range(1, 8)]  # ends: 15, 25, 35, 45, 55, ...
        self.assertEqual(fifth_fixation_end(fix), 55.0)
        self.assertIsNone(fifth_fixation_end(fix[:5]))
        post, reason = prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                                     self.geometry, [0], window='post5', fixations=fix)
        self.assertEqual(reason, 'included')
        self.assertEqual([t for t, _ in post['samples']], [100, 200, 300, 400])
        pre, reason = prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                                    self.geometry, [0], window='pre5', fixations=fix)
        self.assertIsNone(pre)
        self.assertEqual(reason, 'insufficient_prebuffer_mousemove')
        none, reason = prepare_trial('p001-b1-t1', self.cards, self.events, self.clicks,
                                     self.geometry, [0], window='pre5', fixations=fix[:3])
        self.assertEqual(reason, 'no_fifth_fixation_boundary')

    def test_organic_flavor_converts_bands_to_cards_and_refuses_estimates(self):
        class DL:
            def typed_alignment_exclusions(self): return {'p009-b1-t1'}
            def load_aois(self, tid):
                return {'source': 'bbox' if tid == 'p001-b1-t1' else 'band_estimate',
                        'organic': [dict(position=1, y_top=100, y_bottom=180, x_top=160, x_bottom=740)]}
        cards = load_flavor_cards(DL(), 'p001-b1-t1', 'organic')
        self.assertEqual(cards, [dict(position=0, type='organic', x=160, y=100, width=580, height=80)])
        self.assertEqual(load_flavor_cards(DL(), 'p002-b1-t1', 'organic'), [])
        self.assertEqual(load_flavor_cards(DL(), 'p009-b1-t1', 'organic'), [])

if __name__ == '__main__':
    unittest.main()
