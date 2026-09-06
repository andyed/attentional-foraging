"""Regression checks for the fixed-cohort candidate comparison."""
import copy
import unittest

from carousel_match_report import compare


def reference_row(tid='trial-a', count=5, exported=3):
    return {
        'tid': tid, 'cell_status': 'scored', 'dom_cells': count,
        'export_cells': exported, 'cell_count_agree': count == exported,
        'cell_parent_comparisons': [{'dom_count': count, 'export_count': exported}],
    }


def candidate_row(tid='trial-a', count=5):
    return {
        'trial_id': tid, 'status': 'scored', 'registration_status': 'accepted',
        'parents': [{
            'screenshot_registration': {'status': 'accepted', 'dy': -39},
            'cells': [{'aligned_visible_rect_screenshot': {'x': i * 120, 'y': 140, 'w': 110, 'h': 180}}
                      for i in range(count)],
        }],
    }


class FixedCohortReportTests(unittest.TestCase):
    def test_missing_candidate_stays_in_denominator(self):
        reference = [reference_row(), reference_row('trial-b')]
        report = compare(reference, {'trials': [candidate_row()]})
        self.assertEqual(report['summary']['cohort_trials'], 2)
        self.assertEqual(report['summary']['candidate_match'], 1)
        self.assertEqual(report['summary']['missing_candidates'], 1)
        self.assertEqual(report['trials'][1]['candidate_count'], 0)
        self.assertFalse(report['trials'][1]['candidate_match'])

    def test_no_candidates_keeps_whole_reference(self):
        report = compare([reference_row(), reference_row('trial-b')], {'trials': []})
        self.assertEqual(report['summary']['cohort_trials'], 2)
        self.assertEqual(report['summary']['missing_candidates'], 2)
        self.assertEqual(report['summary']['candidate_match'], 0)

    def test_rejected_registration_cannot_count_stale_aligned_cells(self):
        new = candidate_row()
        new['registration_status'] = 'rejected'
        new['parents'][0]['screenshot_registration']['status'] = 'rejected'
        report = compare([reference_row()], {'trials': [new]})
        self.assertEqual(report['summary']['cohort_trials'], 1)
        self.assertEqual(report['summary']['candidate_cards'], 0)
        self.assertEqual(report['summary']['candidate_match'], 0)
        self.assertEqual(report['summary']['registration_accepted'], 0)

    def test_failed_shift_is_not_reported_as_an_achieved_correction(self):
        new = candidate_row()
        new['registration_status'] = 'rejected'
        new['parents'][0]['screenshot_registration']['status'] = 'rejected'
        report = compare([reference_row()], {'trials': [new]})
        self.assertEqual(report['summary']['large_vertical_corrections'], 0)

    def test_changed_multi_parent_grain_is_rejected_despite_matching_total(self):
        new = candidate_row(count=3)
        second = candidate_row(count=2)['parents'][0]
        new['parents'].append(second)
        with self.assertRaisesRegex(ValueError, 'one top parent'):
            compare([reference_row(count=5)], {'trials': [new]})

    def test_multi_parent_reference_grain_is_rejected(self):
        old = reference_row()
        old['cell_parent_comparisons'].append({'dom_count': 1, 'export_count': 1})
        with self.assertRaisesRegex(ValueError, 'one top parent'):
            compare([old], {'trials': [candidate_row()]})

    def test_duplicate_candidate_ids_are_rejected(self):
        row = candidate_row()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            compare([reference_row()], {'trials': [row, copy.deepcopy(row)]})

    def test_out_of_cohort_candidate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'out-of-cohort'):
            compare([reference_row()], {'trials': [candidate_row('other')]})

    def test_duplicate_reference_ids_are_rejected(self):
        row = reference_row()
        with self.assertRaisesRegex(ValueError, '[Dd]uplicate'):
            compare([row, copy.deepcopy(row)], {'trials': [candidate_row()]})

    def test_count_disagreement_remains_a_failure_after_geometry_acceptance(self):
        report = compare([reference_row(count=5)], {'trials': [candidate_row(count=4)]})
        self.assertEqual(report['summary']['registration_accepted'], 1)
        self.assertEqual(report['summary']['candidate_match'], 0)
        self.assertEqual(report['summary']['candidate_cards'], 4)
        self.assertEqual(report['summary']['reference_cards'], 5)


if __name__ == '__main__':
    unittest.main()
