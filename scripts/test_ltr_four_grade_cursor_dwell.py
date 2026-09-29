import unittest
import numpy as np
from ltr_four_grade_cursor_dwell import dwell_four_grades


class DwellGradeTests(unittest.TestCase):
    def test_click_priority_and_median_ties(self):
        grades, info = dwell_four_grades([0, 10, 20, 30, 0, 1000], [0, 0, 0, 0, 1, 1], np.ones(6, dtype=bool))
        np.testing.assert_array_equal(grades, [0, 1, 1, 2, 3, 3])
        self.assertEqual(info['positive_nonclick_median_ms'], 20)

    def test_held_out_and_excluded_values_cannot_affect_threshold_or_labels(self):
        mask = np.array([True, True, True, False, False])
        a, da = dwell_four_grades([0, 10, 30, 5, 10000], [0, 0, 0, 0, 0], mask)
        b, db = dwell_four_grades([0, 10, 30, float('nan'), -50], [0, 0, 0, 1, 1], mask)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(da, db)
        self.assertEqual(da['positive_nonclick_median_ms'], 20)

    def test_no_positive_nonclick_dwell(self):
        labels, info = dwell_four_grades([0, 0, 100], [0, 1, 1], np.ones(3, dtype=bool))
        np.testing.assert_array_equal(labels, [0, 3, 3])
        self.assertIsNone(info['positive_nonclick_median_ms'])


if __name__ == '__main__':
    unittest.main()
