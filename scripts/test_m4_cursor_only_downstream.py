"""Fixture checks for the downstream re-derivation helpers.

Run: .venv/bin/python -m unittest discover -s scripts -p test_m4_cursor_only_downstream.py
"""
import unittest

import numpy as np

from m4_cursor_only_downstream import loso_proba, youden, paired, summarize


def synthetic_records(n_participants=4, per=12, seed=0):
    rng = np.random.default_rng(seed)
    recs, y = [], []
    for p in range(n_participants):
        for i in range(per):
            label = int(rng.random() < 0.5)
            recs.append({'trial_id': f'p{p:03d}-b1-t{i}', 'position': 0,
                         'min_dist': 20.0 + 60 * (1 - label) + rng.normal(0, 5),
                         'mean_dist': 100.0 + rng.normal(0, 5)})
            y.append(label)
    return recs, np.asarray(y)


class DownstreamHelperTests(unittest.TestCase):
    def test_loso_proba_only_scores_masked_rows_and_is_out_of_fold(self):
        recs, y = synthetic_records()
        mask = np.array([i % 3 != 0 for i in range(len(recs))])
        proba, pid = loso_proba(recs, ['min_dist', 'mean_dist'], y, mask)
        self.assertTrue(np.isnan(proba[~mask]).all())
        self.assertTrue(np.isfinite(proba[mask]).all())
        s, folds = summarize(y, proba, pid, mask)
        self.assertEqual(s['n_records'], int(mask.sum()))
        self.assertGreater(s['pooled_auc'], 0.9)  # min_dist separates the classes by construction
        self.assertEqual(s['n_folds'], 4)

    def test_youden_operating_point_is_consistent(self):
        y = np.array([0, 0, 1, 1, 0, 1])
        proba = np.array([.1, .4, .6, .9, .2, .8])
        out = youden(y, proba, np.ones(6, dtype=bool))
        self.assertEqual(out['tpr'], 1.0)
        self.assertEqual(out['fpr'], 0.0)
        self.assertEqual(out['f1'], 1.0)
        self.assertTrue(0.4 < out['threshold'] <= 0.6)

    def test_paired_bootstrap_reports_the_shared_participants_only(self):
        a = {'p1': 0.9, 'p2': 0.8, 'p3': 0.7}
        b = {'p1': 0.8, 'p2': 0.7, 'p4': 0.5}
        out = paired(a, b)
        self.assertEqual(out['n_participants'], 2)
        self.assertAlmostEqual(out['mean_delta'], 0.1)
        for v in out['bootstrap_ci95']:
            self.assertAlmostEqual(v, 0.1)


if __name__ == '__main__':
    unittest.main()
