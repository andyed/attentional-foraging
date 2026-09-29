"""Boundary tests for added event counts; run with unittest discovery."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import m4_return_scroll_ablation as producer
from m4_return_scroll_ablation import cursor_returns, gaze_returns, scroll_counts, holm

CARDS = [dict(position=0, x=0, y=0, width=100, height=100),
         dict(position=1, x=0, y=200, width=100, height=100)]


class CountsTest(unittest.TestCase):
    def test_cursor_merge_and_minimum_dwell(self):
        samples = [(0, 50, 50), (100, 500, 500), (200, 50, 50), (300, 500, 500),
                   (6000, 50, 50), (6100, 500, 500), (6200, 50, 50), (6250, 500, 500)]
        self.assertEqual(cursor_returns(samples, CARDS, 5000), {0: 1})
        self.assertEqual(cursor_returns(samples, CARDS, None), {0: 2})

    def test_no_invented_terminal_dwell(self):
        self.assertEqual(cursor_returns([(0, 500, 500), (100, 50, 50)], CARDS, None), {})

    def test_scroll_reversal_ignores_jitter(self):
        self.assertEqual(scroll_counts([(0, 0), (50, 100), (100, 98), (150, 80), (200, 60)])[0], 1)
        self.assertEqual(scroll_counts([(0, 100), (50, 80), (100, 60)])[0], 0)
        self.assertEqual(scroll_counts([(0, 100), (50, 80), (100, 60)])[1], 1)

    def test_scroll_clock_reversal_breaks_gesture_without_sorting(self):
        self.assertEqual(scroll_counts([(1000, 100), (1050, 90), (100, 80), (150, 70)]), (0, 0))

    def test_gaze_returns_and_strict_cutoff(self):
        fixes = [{'t': t, 'y': y} for t, y in [(0, 50), (100, 50), (200, 250), (300, 50), (400, 150), (500, 50)]]
        returns, regressive = gaze_returns(fixes, CARDS, 500)
        self.assertEqual(dict(returns), {0: 1})
        self.assertEqual(dict(regressive), {0: 1})
        self.assertEqual(dict(gaze_returns(fixes, CARDS, 501)[0]), {0: 2})

    def test_holm(self):
        self.assertEqual(holm({'a': .01, 'b': .02, 'c': .5}), {'a': .03, 'b': .04, 'c': .5})

    def test_extraction_filters_every_stream_at_cutoff(self):
        events = [(0, 'mousemove', 500, 500), (100, 'mousemove', 50, 50),
                  (200, 'mousemove', 500, 500), (300, 'mousemove', 50, 50),
                  (499, 'mousemove', 500, 500), (500, 'mousemove', 50, 50),
                  (700, 'mousemove', 500, 500)]
        scroll = [(0, 0), (100, 100), (200, 80), (500, 100), (501, 60)]
        fixes = [{'t': t, 'y': y} for t, y in [(0, 50), (100, 250), (500, 50)]]
        with TemporaryDirectory() as folder:
            (Path(folder)/'trial.csv').write_text('fixture')
            with patch.multiple(producer.dl, FIXATION_DIR=Path(folder),
                                load_mouse_events=lambda *a, **k: (events, scroll, []),
                                load_typed_aois=lambda _: CARDS,
                                get_trial_geometry=lambda _: {'ratio_x': 1, 'ratio_y': 1},
                                load_fixations=lambda _: fixes), patch.object(
                                    producer, 'prepare_trial', return_value=(
                                        {'anchor_t': 1000, 'click_position': 0}, 'included')):
                _, rows, info = producer.extract('trial')
        self.assertEqual(info['cutoff_ms'], 500)
        self.assertEqual(rows[0]['cursor_return_count_unmerged'], 1)
        self.assertEqual(rows[0]['scroll_regression_count'], 1)
        self.assertEqual(rows[0]['gaze_return_count'], 0)


if __name__ == '__main__':
    unittest.main()
