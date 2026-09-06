"""Tests for the audit quartet's coordinate-space selector.

Every assertion here is written to FAIL if the space stops being load-bearing.
A `--space` flag that silently did nothing would pass a naive "does it run"
check, so each test names a difference that must exist (screenshot != document)
or an invariant that must hold (conversion matches data_loader; thresholds
travel with points).

Run: .venv/bin/python scripts/test_audit_space.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from audit_space import Space, SPACES, DEFAULT_SPACE, resolve  # noqa: E402
from data_loader import document_to_screenshot, get_trial_geometry  # noqa: E402

METADATA = ROOT / "AdSERP/data/trial-metadata"


def sample_tids(n=40):
    tids = sorted(p.stem for p in METADATA.glob("p*.xml"))
    if not tids:
        raise unittest.SkipTest("trial metadata unavailable")
    step = max(1, len(tids) // n)
    return tids[::step][:n]


class SpaceContract(unittest.TestCase):
    def test_default_is_screenshot(self):
        # The AOIs live in screenshot space; document is the legacy opt-in.
        self.assertEqual(DEFAULT_SPACE, "screenshot")
        self.assertEqual(set(SPACES), {"screenshot", "document"})

    def test_unknown_space_refuses(self):
        with self.assertRaises(ValueError):
            Space("viewport")

    def test_document_is_identity(self):
        doc = Space("document")
        for tid in sample_tids(10):
            self.assertEqual(doc.point(123.5, 456.5, tid), (123.5, 456.5))
            self.assertEqual(doc.x(162, tid), 162)
            self.assertEqual(doc.y(900, tid), 900)


class ConversionIsLoadBearing(unittest.TestCase):
    """The tests that fail if --space becomes a no-op."""

    def test_screenshot_actually_moves_points(self):
        shot, doc = Space("screenshot"), Space("document")
        moved = 0
        tids = sample_tids()
        for tid in tids:
            if get_trial_geometry(tid) is None:
                continue
            a, b = shot.point(700.0, 900.0, tid), doc.point(700.0, 900.0, tid)
            if a != b:
                moved += 1
        self.assertGreater(
            moved, 0.5 * len(tids),
            "screenshot space did not move points on a majority of trials -- "
            "the flag is a no-op and every audit that reads it is reporting "
            "document-space numbers under a screenshot-space label",
        )

    def test_thresholds_travel_with_points(self):
        # A point at the threshold must stay at the threshold after conversion.
        # If only one of the two is converted, this drifts and near-misses
        # silently re-bucket -- the failure the 162/702 column bounds invite.
        shot = Space("screenshot")
        for tid in sample_tids():
            if get_trial_geometry(tid) is None:
                continue
            for bound in (162, 702):
                px, _ = shot.point(bound, 0.0, tid)
                self.assertAlmostEqual(px, shot.x(bound, tid), places=9)
            _, py = shot.point(0.0, 1000.0, tid)
            self.assertAlmostEqual(py, shot.y(1000, tid), places=9)

    def test_matches_data_loader(self):
        # The cached fast path must equal the canonical helper exactly.
        shot = Space("screenshot")
        for tid in sample_tids():
            for x, y in ((0, 0), (162, 300), (702, 1200), (1403.0, 900.5)):
                self.assertEqual(shot.point(x, y, tid),
                                 document_to_screenshot(x, y, tid))

    def test_unreadable_geometry_degrades_consistently(self):
        # document_to_screenshot returns the point unchanged when geometry
        # cannot be read; thresholds must degrade the same way or they stop
        # matching the points they are compared against.
        shot = Space("screenshot")
        missing = "p999-b9-t9"
        self.assertIsNone(get_trial_geometry(missing))
        self.assertEqual(shot.point(500.0, 500.0, missing), (500.0, 500.0))
        self.assertEqual(shot.x(162, missing), 162)
        self.assertEqual(shot.y(900, missing), 900)


class ArgvParsing(unittest.TestCase):
    def test_space_flag_forms(self):
        for argv, expected in (
            (["prog"], "screenshot"),
            (["prog", "--space", "document"], "document"),
            (["prog", "--space=document"], "document"),
        ):
            old = sys.argv
            try:
                sys.argv = argv
                self.assertEqual(resolve().name, expected)
            finally:
                sys.argv = old

    def test_bare_flag_refuses(self):
        old = sys.argv
        try:
            sys.argv = ["prog", "--space"]
            with self.assertRaises(SystemExit):
                resolve()
        finally:
            sys.argv = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
