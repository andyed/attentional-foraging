"""Cell export eligibility regressions; no corpus export is generated."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export_aois_by_trial_id as exporter
import data_loader


def right_rail_snapshot():
    return [
        {'role': 'parent', 'kind': 'dd_right', 'x': 900, 'y': 180,
         'w': 240, 'h': 400},
        {'role': 'cell', 'kind': 'dd_right_cell', 'parent_kind': 'dd_right',
         'x': 900, 'y': 180, 'w': 240, 'h': 180},
    ]


class CellExportEligibilityTests(unittest.TestCase):
    def setUp(self):
        # Exercise the canonical loader's JSON contract, without the corpus
        # or its cached exclusion state influencing these isolated cases.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        typed = Path(directory.name)
        (typed / 'alignment-exclusions.json').write_text(json.dumps({
            'tids': ['p007-b1-t9'],
        }))
        for mocked in (
            patch.object(data_loader, '_TYPED_EXCLUSIONS', None),
            patch.object(data_loader, '_typed_aoi_path',
                         side_effect=lambda tid: typed / f'{tid}.json'),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_excluded_trial_cannot_export_legacy_right_rail(self):
        with patch.object(exporter, 'rows_typed', return_value=[]) as typed, \
                patch.object(exporter, 'load_cell_aois',
                             return_value=right_rail_snapshot()) as snapshot:
            rows = exporter.rows_typed_cellsplit('p007-b1-t9', 2400, 1024, 7, 1, 9)
        self.assertEqual(rows, [])
        snapshot.assert_not_called()
        typed.assert_not_called()

    def test_eligible_right_only_trial_survives_empty_main_axis(self):
        with patch.object(exporter, 'rows_typed', return_value=[]), \
                patch.object(exporter, 'load_cell_aois',
                             return_value=right_rail_snapshot()) as snapshot:
            rows = exporter.rows_typed_cellsplit('p004-b1-t1', 2400, 1024, 4, 1, 1)
        snapshot.assert_called_once_with('p004-b1-t1', midpoint_split=True)
        self.assertEqual([r['etype'] for r in rows], ['dd_right', 'dd_right_cell'])
        self.assertEqual([r['role'] for r in rows], ['parent', 'cell'])
        self.assertTrue(all(not r['main_axis'] for r in rows))
        self.assertTrue(all(r['n_cells'] == 1 for r in rows))
        self.assertEqual((rows[0]['left_x'], rows[0]['right_x'],
                          rows[0]['top_y'], rows[0]['bottom_y']),
                         (900, 1140, 180, 580))
        self.assertEqual((rows[1]['left_x'], rows[1]['right_x'],
                          rows[1]['top_y'], rows[1]['bottom_y']),
                         (900, 1140, 180, 360))

    def test_eligible_main_axis_parent_keeps_its_original_fields(self):
        original = {
            'trial_id': 'p004-b1-t1', 'uid': 4, 'batch': 1, 'trial': 1,
            'rank': 0, 'etype': 'organic', 'organic_rank': 0,
            'top_y': 170.5, 'bottom_y': 320.25, 'center_y': 245.375,
            'left_x': 160.25, 'right_x': 701.5, 'n_total': 1, 'n_organic': 1,
            'doc_height': 2400, 'screen_height': 1024,
            'html_handle': '#result', 'html_signature': 'organic result',
        }
        with patch.object(exporter, 'rows_typed', return_value=[copy.deepcopy(original)]), \
                patch.object(exporter, 'load_cell_aois', return_value=[]):
            rows = exporter.rows_typed_cellsplit('p004-b1-t1', 2400, 1024, 4, 1, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual({key: rows[0][key] for key in original}, original)
        self.assertEqual(rows[0]['role'], 'parent')
        self.assertTrue(rows[0]['main_axis'])


if __name__ == '__main__':
    unittest.main()
