"""is_main_axis_click must honour its coordinate space, and the default must not move.

Each assertion names a difference that has to exist, so a `space` argument that is
silently ignored fails here rather than passing a "does it run" check.
Trials come from scripts/audit_trial_filter_space.py (2026-09-26 full-corpus run):
p004-b1-t1 is one of the 118 trials whose final click misses every main-axis box in
document space and hits one in screenshot space; p004-b1-t10 hits in both.

Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest scripts.test_main_axis_click_space -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'notebooks-v2'))
from data_loader import is_main_axis_click  # noqa: E402

RECOVERED = 'p004-b1-t1'
STABLE = 'p004-b1-t10'


class MainAxisClickSpaceTest(unittest.TestCase):
    def test_default_is_still_document_space(self):
        # Released producers call it with no argument; their populations must not move.
        self.assertFalse(is_main_axis_click(RECOVERED))
        self.assertEqual(is_main_axis_click(RECOVERED), is_main_axis_click(RECOVERED, space='document'))

    def test_screenshot_space_recovers_the_trial(self):
        self.assertTrue(is_main_axis_click(RECOVERED, space='screenshot'))

    def test_trial_that_hits_in_both_spaces(self):
        self.assertTrue(is_main_axis_click(STABLE, space='document'))
        self.assertTrue(is_main_axis_click(STABLE, space='screenshot'))

    def test_unknown_space_is_refused(self):
        with self.assertRaises(ValueError):
            is_main_axis_click(STABLE, space='window')


if __name__ == '__main__':
    unittest.main()
