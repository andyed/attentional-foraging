"""Guard against silently changing the prediction task while matching cohorts."""
import copy
import unittest

from m4_cursor_matched_sensitivity import digest, match_trials, validate_cache


def rows(tid, clicked=1):
    return [dict(trial_id=tid, position=p, was_clicked=int(p == clicked),
                 etype='organic', min_dist=10 + p) for p in range(3)]


class MatchedSensitivityTests(unittest.TestCase):
    def test_intersection_keeps_all_negatives_and_condition_specific_features(self):
        native = rows('p001-a') + rows('p002-b')
        sparse = list(reversed(rows('p002-b') + rows('p003-c')))
        for r in sparse:
            r['min_dist'] += 100
        matched, population = match_trials({'native': native, 'sparse': sparse})
        self.assertEqual(population['n_trials'], 1)
        self.assertEqual(population['n_records'], 3)
        self.assertEqual(population['excluded_trials_by_intersection'], {'native': 1, 'sparse': 1})
        self.assertEqual([r['position'] for r in matched['sparse']], [0, 1, 2])
        self.assertEqual(sum(r['was_clicked'] for r in matched['sparse']), 1)
        self.assertEqual(matched['sparse'][0]['min_dist'] - matched['native'][0]['min_dist'], 100)

    def test_shared_trial_with_missing_negative_must_not_be_silently_row_intersected(self):
        with self.assertRaisesRegex(ValueError, 'lattice mismatch'):
            match_trials({'native': rows('p001-a'), 'sparse': rows('p001-a')[:2]})

    def test_changed_click_target_fails(self):
        with self.assertRaisesRegex(ValueError, 'lattice mismatch'):
            match_trials({'native': rows('p001-a'), 'sparse': rows('p001-a', clicked=0)})

    def test_duplicate_aoi_fails_instead_of_overwriting(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            match_trials({'native': rows('p001-a') + rows('p001-a')[:1]})

    def test_nonclick_trial_and_empty_intersection_fail(self):
        with self.assertRaisesRegex(ValueError, 'one click'):
            match_trials({'native': rows('p001-a', clicked=4)})
        with self.assertRaisesRegex(ValueError, 'No shared'):
            match_trials({'native': rows('p001-a'), 'sparse': rows('p002-b')})

    def test_cache_cannot_change_features_or_observation_protocol(self):
        protocol = dict(anchor_event='mousedown', sampling='native', window='all', downsample_hz=0)
        record = rows('p001-a')
        cache = dict(**protocol, conditions={'buf500': record})
        summary = dict(protocol=protocol, provenance={'feature_records_sha256': {'buf500': digest(record)}})
        self.assertEqual(validate_cache(cache, summary), record)
        altered = copy.deepcopy(cache)
        altered['conditions']['buf500'][0]['min_dist'] += 1
        with self.assertRaisesRegex(ValueError, 'feature hash'):
            validate_cache(altered, summary)
        altered = copy.deepcopy(cache)
        altered['anchor_event'] = 'click'
        with self.assertRaisesRegex(ValueError, 'protocol mismatch'):
            validate_cache(altered, summary)


if __name__ == '__main__':
    unittest.main()
