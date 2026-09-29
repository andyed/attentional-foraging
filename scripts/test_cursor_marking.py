import unittest

from cursor_marking import (cluster_ci, gaze_by_aoi, illustration_candidates, lead_bin,
                            most_gazed_other, remark_test)

SEGS = [[0, 100, 2], [100, 300, -1], [300, 700, 3], [700, 900, -2], [900, 1500, 2], [1500, 2000, 1]]


class GazeTest(unittest.TestCase):
    def test_overlap_is_clipped_to_the_pause_and_skips_unobserved(self):
        ms, first = gaze_by_aoi(SEGS, 50, 1600)
        self.assertEqual(ms, {2: 650, 3: 400, 1: 100})
        self.assertEqual(first, {2: 50, 3: 300, 1: 1500})

    def test_most_gazed_other_excludes_the_cursor_aoi_and_short_looks(self):
        ms, first = gaze_by_aoi(SEGS, 50, 1600)
        self.assertEqual(most_gazed_other(ms, first, 2, 100), 3)
        self.assertEqual(most_gazed_other(ms, first, 3, 100), 2)
        self.assertIsNone(most_gazed_other(ms, first, 2, 500))

    def test_ties_go_to_the_earliest_entry(self):
        ms, first = gaze_by_aoi([[0, 200, 4], [200, 400, 5]], 0, 400)
        self.assertEqual(most_gazed_other(ms, first, 0, 100), 4)


class HelpersTest(unittest.TestCase):
    def test_lead_bins(self):
        self.assertEqual(lead_bin(0.0), '0-2s')
        self.assertEqual(lead_bin(4.99), '2-5s')
        self.assertEqual(lead_bin(12), '>=10s')
        self.assertIsNone(lead_bin(-0.1))

    def test_cluster_ci_ratio_of_sums(self):
        r = cluster_ci({'a': 1, 'b': 3}, {'a': 2, 'b': 6}, draws=100, seed=1)
        self.assertAlmostEqual(r['value'], 0.5)
        self.assertEqual(r['ci95'], [0.5, 0.5])

    def test_remark_pairs_only_consecutive_pauses_on_different_aois(self):
        recs = [dict(trial_id='t', pid='p', start=0, aoi=1, target=2, pre_approach=True),
                dict(trial_id='t', pid='p', start=10, aoi=1, target=2, pre_approach=True),
                dict(trial_id='t', pid='p', start=20, aoi=2, target=2, pre_approach=True),
                dict(trial_id='t', pid='p', start=30, aoi=3, target=2, pre_approach=False)]
        r = remark_test(recs)
        self.assertEqual(r['later_hit']['value'], 1.0)
        self.assertEqual(r['earlier_hit']['value'], 0.0)
        self.assertEqual(r['diff']['n'], 1)

    def test_illustration_rule(self):
        pa = dict(start=0, end=4000, distinct=3, returns=1, gaze_aoi_coverage=.7)
        short = dict(pa, end=1500)
        c = illustration_candidates([dict(trial_id='t', pauses=[pa, short])])
        self.assertEqual(len(c), 1)


if __name__ == '__main__':
    unittest.main()
