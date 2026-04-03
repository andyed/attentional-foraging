"""
data_loader.py — shared data loading utilities for attentional-foraging notebooks.

Usage:
    from data_loader import load_sessions, load_fixations, load_events, DATA_DIR
"""

from pathlib import Path
import pandas as pd

# Resolve data directory relative to this file (notebooks-v2/ → ../data/)
DATA_DIR = Path(__file__).parent.parent / "data"


def load_sessions(path: Path | str | None = None) -> pd.DataFrame:
    """Load session-level metadata. Returns DataFrame indexed by session_id."""
    p = Path(path) if path else DATA_DIR / "sessions.csv"
    df = pd.read_csv(p)
    if "session_id" in df.columns:
        df = df.set_index("session_id")
    return df


def load_fixations(path: Path | str | None = None) -> pd.DataFrame:
    """Load fixation events. Returns DataFrame with columns: session_id, t, x, y, duration_ms."""
    p = Path(path) if path else DATA_DIR / "fixations.csv"
    return pd.read_csv(p)


def load_events(path: Path | str | None = None) -> pd.DataFrame:
    """Load raw event stream (gaze, mouse, scroll, click). Returns DataFrame sorted by t."""
    p = Path(path) if path else DATA_DIR / "events.csv"
    df = pd.read_csv(p)
    if "t" in df.columns:
        df = df.sort_values("t").reset_index(drop=True)
    return df


def load_serps(path: Path | str | None = None) -> pd.DataFrame:
    """Load SERP metadata (query, condition, result count, difficulty label)."""
    p = Path(path) if path else DATA_DIR / "serps.csv"
    return pd.read_csv(p)


def load_participants(path: Path | str | None = None) -> pd.DataFrame:
    """Load participant demographics / individual-differences measures."""
    p = Path(path) if path else DATA_DIR / "participants.csv"
    df = pd.read_csv(p)
    if "participant_id" in df.columns:
        df = df.set_index("participant_id")
    return df
