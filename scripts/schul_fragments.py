"""Parse iMotions Data.xml for per-(respondent × stimulus) segment boundaries.

Each Schultheiß & Lewandowski 2019 session zip (M1/M2/D1/D2) contains one
Data.xml with:
  - <Stimuli> blocks mapping Stimulus.Id → display name (e.g. 1019 → 'Q04_M')
  - <SceneFragment> blocks: per (respondent × stimulus) time window as
    (FragmentStart_ms, FragmentEnd_ms) in session clock.

This module extracts both, so the replay pipeline can slice a session recording
into per-stimulus clips.
"""
from __future__ import annotations

import re
import zipfile
from typing import NamedTuple


class Stimulus(NamedTuple):
    stim_id: int
    name: str           # e.g. 'Q04_M', 'M1' for the whole-block container
    stim_type: str      # 'Scene' or 'SceneRecording'


class Fragment(NamedTuple):
    frag_id: int
    stim_id: int        # == SceneId; maps to Stimulus.stim_id
    respondent_id: int
    t_start_ms: int
    t_end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.t_end_ms - self.t_start_ms


_STIMULI_RE = re.compile(
    r"<Stimuli>\s*"
    r"<Id>(\d+)</Id>"
    r".*?<StimuliDisplayName>([^<]*)</StimuliDisplayName>"
    r".*?<StimuliType>([^<]*)</StimuliType>"
    r".*?</Stimuli>",
    re.DOTALL,
)

_FRAGMENT_RE = re.compile(
    r"<SceneFragment>\s*"
    r"<Id>(\d+)</Id>\s*"
    r"<SceneId>(\d+)</SceneId>\s*"
    r"<RespondentId>(\d+)</RespondentId>\s*"
    r"<FragmentStart>(\d+)</FragmentStart>\s*"
    r"<FragmentEnd>(\d+)</FragmentEnd>\s*"
    r"</SceneFragment>",
    re.DOTALL,
)


def read_data_xml(zip_path: str) -> str:
    """Return the body of Data.xml inside the given session zip (records only,
    with the XSD schema prefix stripped)."""
    z = zipfile.ZipFile(zip_path)
    entry = next(n for n in z.namelist() if n.split("\\")[-1] == "Data.xml")
    raw = z.read(entry).decode("utf-8", errors="replace")
    cut = raw.find("</xs:schema>")
    return raw[cut + len("</xs:schema>"):] if cut != -1 else raw


def parse_stimuli(xml_body: str) -> dict[int, Stimulus]:
    out: dict[int, Stimulus] = {}
    for m in _STIMULI_RE.finditer(xml_body):
        sid, name, typ = m.groups()
        out[int(sid)] = Stimulus(int(sid), name, typ)
    return out


def parse_fragments(xml_body: str) -> list[Fragment]:
    return [
        Fragment(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]))
        for m in (fm.groups() for fm in _FRAGMENT_RE.finditer(xml_body))
    ]


def fragments_by_respondent(frags: list[Fragment]) -> dict[int, list[Fragment]]:
    out: dict[int, list[Fragment]] = {}
    for f in frags:
        out.setdefault(f.respondent_id, []).append(f)
    for v in out.values():
        v.sort(key=lambda f: f.t_start_ms)
    return out


def find_fragment(zip_path: str, respondent_id: int, q_label: str) -> tuple[Fragment, Stimulus]:
    """Look up the single (respondent × stimulus) fragment.

    Raises LookupError if the respondent didn't view that stimulus (missing
    data for that pair, which does happen in this dataset).
    """
    xml = read_data_xml(zip_path)
    stimuli = parse_stimuli(xml)
    # Find stimulus by display name
    stim = next((s for s in stimuli.values() if s.name == q_label), None)
    if stim is None:
        names = sorted(s.name for s in stimuli.values())
        raise LookupError(f"no stimulus {q_label!r} in {zip_path}. Known: {names}")

    frags = parse_fragments(xml)
    target = [f for f in frags
              if f.respondent_id == respondent_id and f.stim_id == stim.stim_id]
    if not target:
        # Give a helpful error showing which stimuli this respondent *did* view
        available = [stimuli[f.stim_id].name for f in frags
                     if f.respondent_id == respondent_id and f.stim_id in stimuli]
        raise LookupError(
            f"respondent {respondent_id} did not view {q_label} in {zip_path}. "
            f"Available: {sorted(available)}"
        )
    return target[0], stim


def build_session_timeline(zip_path: str, respondent_id: int) -> list[dict]:
    """Convenience: return a respondent's stimulus timeline as a list of dicts
    suitable for JSON (meta.json, UI timeline, etc.)."""
    xml = read_data_xml(zip_path)
    stimuli = parse_stimuli(xml)
    frags = parse_fragments(xml)
    mine = sorted(
        (f for f in frags if f.respondent_id == respondent_id),
        key=lambda f: f.t_start_ms,
    )
    out = []
    for f in mine:
        stim = stimuli.get(f.stim_id)
        out.append({
            "q_label": stim.name if stim else f"stim_{f.stim_id}",
            "stim_id": f.stim_id,
            "t_start_ms": f.t_start_ms,
            "t_end_ms": f.t_end_ms,
            "duration_ms": f.duration_ms,
        })
    return out


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Inspect iMotions stimulus timings for a participant.")
    ap.add_argument("zip", help="path to M1_Students.zip / D1_Students.zip / etc")
    ap.add_argument("respondent", type=int, help="respondent ID, e.g. 1042")
    args = ap.parse_args()

    timeline = build_session_timeline(args.zip, args.respondent)
    if not timeline:
        raise SystemExit(f"no fragments found for respondent {args.respondent}")
    print(f"Session timeline for respondent {args.respondent}:")
    total = max(f["t_end_ms"] for f in timeline)
    for f in timeline:
        print(f"  {f['q_label']:>8}  [{f['t_start_ms']:>6} .. {f['t_end_ms']:>6}] "
              f"dur {f['duration_ms']:>5}ms   ({100*f['t_start_ms']/total:5.1f}% .. {100*f['t_end_ms']/total:5.1f}%)")
    print(f"\n{len(timeline)} stimuli viewed out of 10. Total session ~{total/1000:.1f}s.")
    print("\nAs JSON:")
    print(json.dumps(timeline, indent=2))
