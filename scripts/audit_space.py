"""Explicit coordinate-space selection for the bbox-y-coverage audit quartet.

evtrack records clicks and cursor samples in DOCUMENT space (1403 px wide);
the typed AOI maps are SCREENSHOT space (1280 px). Every containment test in
these audits compares one against the other, so the space is load-bearing and
must never be implicit: the 2026-08-31 re-run moved `approached & clicked`
contamination from 22.7 % to 3.91 % on exactly this conversion.

Default is `screenshot`, because that is the space the AOIs live in and the
space the comparison is only meaningful in. Pass `--space document` to
reproduce the pre-2026-08-31 published figures.

Thresholds matter as much as points. A document-space constant (the X 162-702
result column, a document height) is wrong once the click has been converted,
so scale it through the same per-trial ratios rather than leaving it fixed --
converting the point but not the threshold silently re-buckets clicks.

Used by: audit_cascade_contamination.py, audit_unattributed_clicks.py,
audit_dd_right.py, audit_calibration_bias.py.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import document_to_screenshot, get_trial_geometry  # noqa: E402

SPACES = ("screenshot", "document")
DEFAULT_SPACE = "screenshot"


class Space:
    """Converts document-space points and thresholds into the chosen space."""

    def __init__(self, name):
        if name not in SPACES:
            raise ValueError(f"unknown space {name!r}; expected one of {SPACES}")
        self.name = name

    @property
    def converts(self):
        return self.name == "screenshot"

    def point(self, x, y, trial_id):
        """A document-space (x, y) click/cursor sample in the chosen space."""
        if not self.converts:
            return x, y
        # Same arithmetic as data_loader.document_to_screenshot, over the cached
        # ratios -- that helper re-reads the trial geometry on every call, and
        # the Y-band audit converts every click in every trial.
        r = _ratios(trial_id)
        return x * r["x"], y * r["y"]

    def _ratio(self, trial_id, axis):
        if not self.converts:
            return 1.0
        # Cached: get_trial_geometry re-parses the metadata XML and opens the
        # screenshot, and a threshold is resolved several times per trial.
        return _ratios(trial_id)[axis]

    def x(self, value, trial_id):
        """A document-space X threshold in the chosen space."""
        return value * self._ratio(trial_id, "x")

    def y(self, value, trial_id):
        """A document-space Y threshold in the chosen space."""
        return value * self._ratio(trial_id, "y")

    def banner(self):
        if self.converts:
            return ("coordinate space: SCREENSHOT (evtrack document coords converted "
                    "per-trial to AOI space)")
        return ("coordinate space: DOCUMENT (raw evtrack coords; AOIs are screenshot "
                "space -- legacy, reproduces pre-2026-08-31 figures)")


@lru_cache(maxsize=None)
def _ratios(trial_id):
    """Per-trial (x, y) document -> screenshot scale factors.

    document_to_screenshot degrades to identity on unreadable geometry, so
    thresholds must degrade the same way or they stop matching the points.
    """
    g = get_trial_geometry(trial_id)
    if g is None:
        return {"x": 1.0, "y": 1.0}
    return {"x": g["ratio_x"], "y": g["ratio_y"]}


def add_space_argument(parser):
    parser.add_argument(
        "--space",
        choices=SPACES,
        default=DEFAULT_SPACE,
        help=("coordinate space for click/cursor samples (default: %(default)s). "
              "'document' reproduces the pre-2026-08-31 published figures."),
    )
    return parser


def resolve(name=None):
    """Space from an explicit name, else from sys.argv, else the default.

    Lets the three argparse-less audits in the quartet accept --space without
    growing a parser each.
    """
    if name is None:
        argv = sys.argv
        if "--space" in argv:
            i = argv.index("--space")
            if i + 1 >= len(argv):
                raise SystemExit("--space requires a value: " + " | ".join(SPACES))
            name = argv[i + 1]
        else:
            name = next((a.split("=", 1)[1] for a in argv
                         if a.startswith("--space=")), DEFAULT_SPACE)
    space = Space(name)
    print(space.banner())
    return space
