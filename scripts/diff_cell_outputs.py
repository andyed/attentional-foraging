#!/usr/bin/env python3
"""Compare notebook cell stdout numbers against pre-fix Key Claims snapshot.

update_key_claims.py writes hand-curated values into notebook markdown — it
doesn't read cell outputs. So after re-running a notebook, the Key Claims
markdown is stale until a human updates update_key_claims.py's hardcoded
strings. To do the coord-fix diff we compare:

  old values:  docs/drafts/coord_fix_snapshot_20260412/key_claims_before.json
               (extracted from markdown tables before the re-run)
  new values:  cell stdout from the newly-executed notebooks

For each K-ID in the snapshot, extract any numbers from its old value string
and search the notebook's cell outputs for a line that looks like a match —
same keywords (labels nearby), similar magnitudes, or explicit presence of
the old number.

Output: docs/drafts/coord_fix_snapshot_20260412/cell_output_diff.md
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / 'docs' / 'drafts' / 'coord_fix_snapshot_20260412'

NBS = [
    '07c_regressions_kinematics',
    '12_regression_precision_by_load',
    '14_butterworth_cognitive_load',
    '15_cursor_approach',
    '18_learning_curve',
    '18_ripa2_vs_lfhf',
    '19_margin_fixations',
    '22_four_class_taxonomy',
]

NUM_RE = re.compile(r'[-+]?\d[\d,]*\.?\d*(?:e[-+]?\d+)?', re.IGNORECASE)


def extract_cell_stdout(nb_path: Path) -> list[tuple[int, str]]:
    """Return list of (cell_idx, stdout_text) for code cells with stdout output."""
    nb = json.load(open(nb_path))
    out = []
    for i, cell in enumerate(nb['cells']):
        if cell.get('cell_type') != 'code':
            continue
        texts = []
        for o in cell.get('outputs', []):
            if o.get('output_type') == 'stream' and o.get('name') == 'stdout':
                t = o.get('text', '')
                if isinstance(t, list):
                    t = ''.join(t)
                texts.append(t)
            elif o.get('output_type') == 'execute_result':
                d = o.get('data', {})
                t = d.get('text/plain', '')
                if isinstance(t, list):
                    t = ''.join(t)
                texts.append(t)
        if texts:
            out.append((i, '\n'.join(texts)))
    return out


def numbers_in(s: str) -> list[float]:
    vals = []
    for m in NUM_RE.findall(s):
        try:
            vals.append(float(m.replace(',', '')))
        except ValueError:
            pass
    return vals


def find_matching_line(old_val: str, stdout_blobs: list[tuple[int, str]]) -> tuple[str, str]:
    """Search for a stdout line plausibly reporting the same metric.

    Returns (best_match_line, match_class) where match_class is
    'exact_number', 'keyword_near', 'nothing'.
    """
    old_nums = numbers_in(old_val)
    # Normalize: strip markdown emphasis and whitespace for keyword match
    keywords = re.findall(r'[A-Za-z]{3,}', old_val.lower())
    meaningful_keywords = [k for k in keywords
                           if k not in {'per', 'and', 'for', 'the', 'with', 'all'}]

    best_line = ''
    best_class = 'nothing'

    for cell_idx, blob in stdout_blobs:
        for line in blob.split('\n'):
            line_nums = numbers_in(line)
            # Try exact number match first
            for o in old_nums:
                for n in line_nums:
                    if abs(o) > 0.001:
                        if abs(n - o) / abs(o) < 0.005:  # within 0.5%
                            return (line.strip(), 'exact_number')
                    elif abs(n) < 0.001:
                        return (line.strip(), 'exact_number')
            # Fall back to keyword match
            line_low = line.lower()
            hits = sum(1 for k in meaningful_keywords if k in line_low)
            if hits >= 2 and line_nums:
                if best_class != 'exact_number':
                    best_line = line.strip()
                    best_class = 'keyword_near'

    return (best_line, best_class)


def main():
    before_path = SNAP / 'key_claims_before.json'
    if not before_path.exists():
        print(f'ERROR: {before_path} not found', file=sys.stderr)
        sys.exit(1)
    before = json.load(open(before_path))

    out_lines = []
    out_lines.append('# Cell Output vs Snapshot — 2026-04-12 coord fix\n')
    out_lines.append('For each K-ID captured in the pre-fix snapshot, search the post-fix '
                     'notebook cell stdout for a line that plausibly reports the same metric. '
                     'Classification:\n')
    out_lines.append('- **`exact`** — a number within 0.5% of the snapshot value appears somewhere in stdout. '
                     'Likely unchanged; verify context.')
    out_lines.append('- **`near`** — no exact number match, but a stdout line shares ≥2 keywords with the K-ID description. '
                     'Probably the right metric with a shifted value. **These need human review.**')
    out_lines.append('- **`missing`** — no plausible match found. Either the metric was renamed, '
                     'the notebook no longer computes it, or it needs manual lookup.')
    out_lines.append('')

    totals = {'exact': 0, 'near': 0, 'missing': 0}

    for nb in NBS:
        path = ROOT / 'notebooks-v2' / f'{nb}.ipynb'
        if not path.exists():
            continue
        stdout_blobs = extract_cell_stdout(path)

        b = before.get(nb, {})
        if not b:
            continue

        out_lines.append(f'## {nb}\n')
        out_lines.append(f'Pre-fix K-IDs: {len(b)} · Cells with stdout: {len(stdout_blobs)}\n')

        rows = []
        for kid in sorted(b.keys(), key=lambda k: (len(k), k)):
            entry = b[kid]
            old_val = entry['value']
            desc = entry['desc']
            match_line, cls = find_matching_line(old_val, stdout_blobs)
            status = {
                'exact_number': 'exact',
                'keyword_near': 'near',
                'nothing': 'missing',
            }[cls]
            totals[status] += 1
            if status == 'exact':
                summary = f'found `{match_line[:80]}`'
            elif status == 'near':
                summary = f'**{match_line[:100]}** _(old: {old_val})_'
            else:
                summary = f'_not found in stdout_ (old: `{old_val}`)'
            rows.append(f'| **{status}** | **{kid}** | {desc[:50]} | {summary} |')

        out_lines.append('| status | K-ID | description | evidence |')
        out_lines.append('|---|---|---|---|')
        out_lines.extend(rows)
        out_lines.append('')

    out_lines.append('## Summary\n')
    out_lines.append(f'- **exact**: {totals["exact"]} K-IDs where the old number is still present → likely unchanged')
    out_lines.append(f'- **near**: {totals["near"]} K-IDs with keyword-matching stdout line but no exact number → probable shift')
    out_lines.append(f'- **missing**: {totals["missing"]} K-IDs with no plausible match → need manual lookup')
    out_lines.append('')
    out_lines.append('**Review priority:** `near` first (shifts we can locate), then `missing` (may have been renamed).')

    diff_path = SNAP / 'cell_output_diff.md'
    diff_path.write_text('\n'.join(out_lines))
    print(f'Wrote {diff_path}')
    print()
    print('Summary:')
    for k, v in totals.items():
        print(f'  {k:>8}: {v}')


if __name__ == '__main__':
    main()
