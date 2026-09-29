"""Focused tests for the matched learned-baseline producer.

Run:
  .venv/bin/python -m unittest discover -s scripts -p test_m4_same_target_learned_baselines.py
"""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import torch  # noqa: F401 -- the producer imports torch before LightGBM on macOS
except ImportError:  # optional extra: uv sync --extra learned-baselines
    raise unittest.SkipTest('torch is not installed; install the learned-baselines extra')

from m4_same_target_learned_baselines import (  # noqa: E402
    CircularTemporalEncoder,
    GlobalGRU,
    GlobalTCN,
    RelativeGRU,
    RelativeTCN,
    flattened_trajectory_features,
    metric_bundle,
    ranking_metrics,
    resample_cursor,
    stable_seed,
    trial_aux,
)


class RepresentationTests(unittest.TestCase):
    def test_global_and_relative_resampling(self):
        samples = [[0, 100], [1000, 300], [2000, 100]]
        global_seq = resample_cursor(samples, None, 1000, 3)
        relative_seq = resample_cursor(samples, 100, 1000, 3)
        np.testing.assert_allclose(global_seq[:, 0], [.1, .3, .1])
        np.testing.assert_allclose(relative_seq[:, 0], [0, .2, 0])
        # The relative stream approaches the AOI over the final interval.
        self.assertGreater(relative_seq[-1, 1], 0)
        self.assertTrue(np.isfinite(global_seq).all())

    def test_aux_is_bounded_and_deterministic(self):
        aux = trial_aux([[0, 0], [40000, 10]])
        np.testing.assert_allclose(aux[0], .5)
        self.assertGreater(aux[1], 0)
        self.assertEqual(stable_seed("p001", "fold"), stable_seed("p001", "fold"))
        self.assertNotEqual(stable_seed("p001", "fold"), stable_seed("p002", "fold"))

    def test_invalid_sequence_inputs_fail(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            resample_cursor([[0, 1]], None, 1000, 4)
        with self.assertRaisesRegex(ValueError, "monotone"):
            resample_cursor([[1, 1], [0, 2]], None, 1000, 4)

    def test_flattened_trajectory_features_preserve_candidate_contract(self):
        data = {
            "global_seq": np.arange(16, dtype=np.float32).reshape(2, 4, 2),
            "relative_seq": np.arange(48, dtype=np.float32).reshape(2, 3, 4, 2),
            "centers": np.asarray([[.1, .5, 0], [.2, .6, .9]], dtype=np.float32),
            "aux": np.asarray([[.3, .4], [.7, .8]], dtype=np.float32),
            "mask": np.asarray([[1, 1, 0], [1, 1, 1]], dtype=bool),
        }
        relative = flattened_trajectory_features(data, "relative_flat_lgbm")
        global_rows = flattened_trajectory_features(data, "global_flat_lgbm")
        self.assertEqual(relative.shape, (5, 10))
        self.assertEqual(global_rows.shape, (5, 11))
        # Global rows within a trial share the trajectory and differ only in
        # the candidate center before the shared trial auxiliaries.
        np.testing.assert_array_equal(global_rows[0, :8], global_rows[1, :8])
        self.assertNotEqual(global_rows[0, 8], global_rows[1, 8])
        np.testing.assert_array_equal(global_rows[0, 9:], global_rows[1, 9:])


class ModelTests(unittest.TestCase):
    def test_model_shapes_and_candidate_conditioning(self):
        torch.manual_seed(1)
        relative = torch.randn(2, 3, 8, 2)
        global_seq = torch.randn(2, 8, 2)
        centers = torch.tensor([[.1, .4, .8], [.2, .5, .9]])
        aux = torch.randn(2, 2)
        relative_model = RelativeGRU(4)
        global_model = GlobalGRU(4)
        self.assertEqual(tuple(relative_model(relative, global_seq, centers, aux).shape), (2, 3))
        global_logits = global_model(relative, global_seq, centers, aux)
        self.assertEqual(tuple(global_logits.shape), (2, 3))
        # A global encoder gets one trajectory representation; AOI centers are
        # the sole candidate-varying input to its decoder.
        self.assertFalse(torch.equal(global_logits[:, 0], global_logits[:, 1]))

    def test_circular_encoder_is_shift_invariant(self):
        torch.manual_seed(4)
        sequence = torch.randn(3, 16, 2)
        encoder = CircularTemporalEncoder(5).eval()
        expected = encoder(sequence)
        shifted = encoder(torch.roll(sequence, shifts=7, dims=1))
        torch.testing.assert_close(expected, shifted, rtol=1e-5, atol=1e-6)

    def test_tcn_model_shapes(self):
        relative = torch.randn(2, 3, 8, 2)
        global_seq = torch.randn(2, 8, 2)
        centers = torch.tensor([[.1, .4, .8], [.2, .5, .9]])
        aux = torch.randn(2, 2)
        self.assertEqual(tuple(RelativeTCN(4)(relative, global_seq, centers, aux).shape), (2, 3))
        self.assertEqual(tuple(GlobalTCN(4)(relative, global_seq, centers, aux).shape), (2, 3))

    def test_gru_backward_after_all_producer_imports(self):
        relative = torch.randn(2, 3, 8, 2)
        global_seq = torch.randn(2, 8, 2)
        centers = torch.tensor([[.1, .4, .8], [.2, .5, .9]])
        aux = torch.randn(2, 2)
        labels = torch.tensor([[1., 0., 0.], [0., 1., 0.]])
        mask = torch.tensor([[1, 1, 0], [1, 1, 1]], dtype=torch.bool)
        model = RelativeGRU(4)
        logits = model(relative, global_seq, centers, aux, mask)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits[mask], labels[mask])
        loss.backward()
        self.assertTrue(all(p.grad is not None for p in model.parameters()))


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "trial_ids": np.asarray(["p1-t1", "p1-t2", "p2-t1"]),
            "participants": np.asarray(["p1", "p1", "p2"]),
            "positions": np.asarray([[0, 1, -1], [0, 1, -1], [0, 1, -1]]),
            "mask": np.asarray([[1, 1, 0], [1, 1, 0], [1, 1, 0]], dtype=bool),
            "labels": np.asarray([[1, 0, 0], [0, 1, 0], [1, 0, 0]], dtype=np.float32),
        }

    def test_ranking_tie_breaks_by_position(self):
        scores = np.asarray([[.5, .5, np.nan], [.1, .9, np.nan], [.4, .3, np.nan]])
        metrics = ranking_metrics(self.data, scores)
        self.assertAlmostEqual(metrics["mrr_at_10"], 1.0)
        self.assertAlmostEqual(metrics["ndcg_at_1"], 1.0)

    def test_metric_bundle_reports_candidate_and_trial_metrics(self):
        scores = np.asarray([[.9, .1, np.nan], [.2, .8, np.nan], [.7, .3, np.nan]])
        metrics, folds = metric_bundle(self.data, scores)
        self.assertEqual(metrics["n_records"], 6)
        self.assertEqual(metrics["n_clicks"], 3)
        self.assertEqual(set(folds), {"p1", "p2"})
        self.assertAlmostEqual(metrics["pooled_auc"], 1.0)


if __name__ == "__main__":
    unittest.main()
