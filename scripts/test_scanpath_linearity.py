import unittest
from collections import Counter

from scanpath_linearity import (assign_rect, classify, compress, first_visit_end,
                                is_complete, jumps, minimal, cluster_ci)

CARDS = [dict(position=0, x=0, y=0, width=100, height=100),
         dict(position=1, x=0, y=150, width=100, height=100)]


class ClassifyTest(unittest.TestCase):
    def test_lorigo_worked_example(self):
        # Lorigo et al. 2006 section 3: scanpath 2 2 3 2 1 1 1
        comp = compress([2, 2, 3, 2, 1, 1, 1], [200] * 7)
        self.assertEqual(comp, [2, 3, 2, 1])
        self.assertEqual(minimal(comp), [2, 3, 1])
        self.assertEqual(classify(comp), 'nonlinear_backfill')

    def test_strictly_linear_steps_of_one_from_any_start(self):
        self.assertEqual(classify([1, 2, 3]), 'strictly_linear')
        self.assertEqual(classify([2, 3]), 'strictly_linear')
        # one-abstract paths are strictly linear by default (Lorigo et al.)
        self.assertEqual(classify([1]), 'strictly_linear')
        self.assertEqual(classify([4]), 'strictly_linear')

    def test_linear_when_first_entries_step_by_one(self):
        # the stutter step: read 2, back to 1, return to 2, continue
        self.assertEqual(classify([1, 2, 1, 2, 3]), 'linear_regression')
        self.assertEqual(classify([1, 2, 3, 1]), 'linear_regression')

    def test_backfill_when_a_first_entry_goes_up_the_page(self):
        self.assertEqual(classify([1, 3, 2]), 'nonlinear_backfill')
        self.assertEqual(classify([2, 1]), 'nonlinear_backfill')
        self.assertEqual(classify([1, 4, 3]), 'nonlinear_backfill')

    def test_skip_only_when_first_entries_only_move_down(self):
        self.assertEqual(classify([1, 3, 4]), 'nonlinear_skip_only')
        self.assertEqual(classify([1, 3, 1, 3, 5]), 'nonlinear_skip_only')

    def test_empty_path(self):
        self.assertIsNone(classify([]))


class CompressTest(unittest.TestCase):
    def test_off_result_fixations_do_not_split_a_visit(self):
        self.assertEqual(compress([1, None, 1, 2], [100, 50, 100, 100]), [1, 2])

    def test_short_visit_dropped_and_neighbours_merged(self):
        labels = [1, 2, 1, 3]
        durs = [200, 60, 200, 200]
        self.assertEqual(compress(labels, durs, 0), [1, 2, 1, 3])
        self.assertEqual(compress(labels, durs, 100), [1, 3])

    def test_visit_duration_is_summed_across_fixations(self):
        self.assertEqual(compress([2, 2, 1], [60, 60, 200], 100), [2, 1])


class HelpersTest(unittest.TestCase):
    def test_rectangle_edges_inclusive_and_gaps_unassigned(self):
        self.assertEqual(assign_rect(100, 100, CARDS), 0)
        self.assertIsNone(assign_rect(50, 125, CARDS))
        self.assertIsNone(assign_rect(101, 50, CARDS))

    def test_jumps_split_forward_skips_from_regressions(self):
        self.assertEqual(jumps([1, 3, 2, 5]), ([2, 3], [1]))
        self.assertEqual(jumps([1, 2, 3]), ([], []))
        self.assertEqual(jumps([3, 1]), ([], [2]))

    def test_complete_before_click(self):
        self.assertTrue(is_complete([1, 2, 3], 3))
        self.assertFalse(is_complete([1, 3], 3))
        self.assertIsNone(is_complete([1], None))

    def test_first_visit_end_port(self):
        # positions are 0-based here, as in next_action_by_position.py
        out = first_visit_end([0, 0, 1, 0, 1, 2, None, 2])
        self.assertEqual(out[0], Counter({'forward 1': 1}))
        self.assertEqual(out[1], Counter({'back': 1}))
        self.assertEqual(out[2], Counter({'off results': 1}))

    def test_cluster_ci_is_ratio_of_sums(self):
        r = cluster_ci({'a': 1, 'b': 3}, {'a': 2, 'b': 6}, draws=200, seed=1)
        self.assertAlmostEqual(r['value'], 0.5)
        self.assertEqual(r['n'], 8)
        self.assertEqual(r['ci95'], [0.5, 0.5])


if __name__ == '__main__':
    unittest.main()
