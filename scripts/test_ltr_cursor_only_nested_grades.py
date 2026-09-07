"""Leakage guards for nested cursor supervision in the outer LOSO ranker."""
import unittest
from unittest.mock import patch

import numpy as np
from lightgbm import LGBMRanker

import ltr_cursor_only_nested_grades as nested
import ltr_typed_four_distinct_grades as shared


def fixture():
    records, X, gaze, pid, pool = [], [], [], [], []
    for p in range(4):
        for trial in range(4):
            for position, distance in enumerate([200, 10, 90, 20, 200]):
                unique = len(records) + 1
                records.append(dict(trial_id=f'p{p:03d}-t{trial}', position=position,
                                    click_pos=3, was_clicked=position == 3,
                                    min_dist=distance))
                X.append([distance, unique, trial, position, p, distance / 3, position * 2])
                gaze.append(int(position == 1))
                pid.append(f'p{p:03d}')
                pool.append(position in (1, 2))
    return records, np.array(X, dtype=float), np.array(gaze), np.array(pid), np.array(pool)


def ranker_predictions(records, X, pid, fold, held_out):
    kept = fold['outer_training_indices'][fold['include']]
    tids = np.array([r['trial_id'] for r in records])
    model = LGBMRanker(objective='lambdarank', metric='ndcg', eval_at=[10],
                       n_estimators=12, learning_rate=0.05, num_leaves=7,
                       min_data_in_leaf=1, verbose=-1, n_jobs=1)
    model.fit(X[kept], fold['4grade'], group=shared.contiguous_group_sizes(tids[kept]))
    return model.predict(X[pid == held_out])


class NestedCursorLabelTests(unittest.TestCase):
    def test_outer_test_gaze_cannot_change_training_labels_or_ranker_predictions(self):
        records, X, gaze, pid, pool = fixture()
        p = 'p000'
        original = nested.nested_cursor_training_labels(records, X, gaze, pid, pool, p)
        changed = gaze.copy()
        changed[pid == p] = 1 - changed[pid == p]
        perturbed = nested.nested_cursor_training_labels(records, X, changed, pid, pool, p)
        for key in ('3grade', '4grade', 'probabilities', 'outer_training_indices'):
            np.testing.assert_array_equal(original[key], perturbed[key])
        np.testing.assert_array_equal(ranker_predictions(records, X, pid, original, p),
                                      ranker_predictions(records, X, pid, perturbed, p))
        self.assertEqual(original['diagnostics'], perturbed['diagnostics'])

    def test_outer_test_features_cannot_change_labeler_scaling_or_training_labels(self):
        records, X, gaze, pid, pool = fixture()
        original = nested.nested_cursor_training_labels(records, X, gaze, pid, pool, 'p000')
        changed = X.copy()
        changed[pid == 'p000'] = 1e10
        perturbed = nested.nested_cursor_training_labels(records, changed, gaze, pid, pool, 'p000')
        np.testing.assert_array_equal(original['probabilities'], perturbed['probabilities'])
        np.testing.assert_array_equal(original['4grade'], perturbed['4grade'])

    def test_each_inner_fit_excludes_outer_and_its_own_prediction_participant(self):
        records, X, gaze, pid, pool = fixture()
        calls = []
        real_pipeline = shared.Pipeline

        class AuditedPipeline:
            def __init__(self, steps):
                self.model = real_pipeline(steps)
            def fit(self, features, labels):
                self.train_ids = set(features[:, 1].astype(int))
                self.model.fit(features, labels)
                return self
            def predict_proba(self, features):
                calls.append((self.train_ids, set(features[:, 1].astype(int))))
                return self.model.predict_proba(features)

        with patch.object(shared, 'Pipeline', AuditedPipeline):
            fold = nested.nested_cursor_training_labels(records, X, gaze, pid, pool, 'p000')
        self.assertEqual(len(calls), 3)
        outer_ids = set(X[pid == 'p000', 1].astype(int))
        id_pid = {int(row[1]): p for row, p in zip(X, pid)}
        for train, test in calls:
            self.assertFalse(outer_ids & (train | test))
            train_parts, test_parts = {id_pid[i] for i in train}, {id_pid[i] for i in test}
            self.assertEqual(len(test_parts), 1)
            self.assertFalse(train_parts & test_parts)
            self.assertEqual(len(train_parts), 2)
        self.assertTrue((pid[fold['outer_training_indices']] != 'p000').all())

    def test_probability_threshold_and_grade_assignment_are_fixed(self):
        records, X, gaze, pid, pool = fixture()
        real_pipeline = shared.Pipeline

        class BoundaryPipeline:
            def __init__(self, steps):
                pass
            def fit(self, features, labels):
                return self
            def predict_proba(self, features):
                probabilities = np.where(features[:, 3] == 1, 0.5, 0.499999)
                return np.column_stack([1 - probabilities, probabilities])

        with patch.object(shared, 'Pipeline', BoundaryPipeline):
            fold = nested.nested_cursor_training_labels(records, X, gaze, pid, pool, 'p000')
        # Each trial keeps positions 0..3, drops only the unapproached row below
        # the click, and assigns a 0.5 prediction to Deferred without tuning.
        np.testing.assert_array_equal(fold['4grade'].reshape(-1, 4),
                                      np.tile([0, 2, 1, 3], (12, 1)))
        np.testing.assert_array_equal(fold['3grade'].reshape(-1, 4),
                                      np.tile([0, 1, 0, 2], (12, 1)))
        self.assertEqual(fold['diagnostics']['class_distribution_outer_training'],
                         {'NotApprAbove': 12, 'DEFERRED': 12, 'EVAL_REJECTED': 12,
                          'CLICKED': 12, 'NotApprBelow_EXCLUDED': 12})

    def test_inner_training_with_one_gaze_class_fails_explicitly(self):
        records, X, gaze, pid, pool = fixture()
        with self.assertRaisesRegex(ValueError, 'both gaze classes'):
            nested.nested_cursor_training_labels(records, X, np.zeros_like(gaze), pid, pool, 'p000')


if __name__ == '__main__':
    unittest.main()
