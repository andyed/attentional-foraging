#!/usr/bin/env python3
"""Diff Key Claims markdown tables before/after the 2026-04-12 coord fix.

Reads:
  docs/drafts/coord_fix_snapshot_20260412/key_claims_before.json  (pre-fix)
  freshly extracted claims from the current notebook state       (post-fix)

Writes:
  docs/drafts/coord_fix_snapshot_20260412/key_claims_diff.md

Flags:
  - New K-IDs (added post-fix)
  - Removed K-IDs (dropped post-fix)
  - Numeric shifts > 5% (or >10px for absolute distances)
  - Sign flips (correlation direction changes)
  - p-value threshold crossings (p<0.05 ↔ p>=0.05)
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

KCLAIM_RE = re.compile(r'\*\*(K\d+\w*)\*\*\s*\|([^|]+?)\|([^|\n]+)')
NUM_RE = re.compile(r'[-+]?\d+\.?\d*(?:e[-+]?\d+)?', re.IGNORECASE)


def extract_key_claims(nb_path: Path) -> dict:
    nb = json.load(open(nb_path))
    claims = {}
    for cell in nb['cells']:
        if cell.get('cell_type') != 'markdown':
            continue
        src = ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']
        if 'Key Claims' not in src and 'K1' not in src:
            continue
        for line in src.split('\n'):
            m = KCLAIM_RE.search(line)
            if m:
                kid, desc, val = m.groups()
                claims[kid.strip()] = {
                    'desc': desc.strip(),
                    'value': val.strip(),
                }
    return claims


def first_number(s: str):
    m = NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def all_numbers(s: str):
    return [float(m) for m in NUM_RE.findall(s) if m]


def pct_change(old: float, new: float) -> float:
    if old == 0:
        return float('inf') if new != 0 else 0.0
    return (new - old) / abs(old) * 100.0


def classify(old_val: str, new_val: str) -> tuple:
    """Return (status, detail) for a value pair.

    status in: 'identical', 'new', 'removed', 'minor', 'shifted',
               'sign_flip', 'p_cross', 'unparseable'
    """
    if old_val is None:
        return ('new', f'(new) {new_val}')
    if new_val is None:
        return ('removed', f'{old_val} (removed)')
    if old_val.strip() == new_val.strip():
        return ('identical', old_val)

    old_nums = all_numbers(old_val)
    new_nums = all_numbers(new_val)
    if not old_nums or not new_nums:
        return ('unparseable', f'{old_val}  →  {new_val}')

    # Compare first number as primary; detect any sign flip or p-cross
    details = []
    worst_shift = 0.0
    sign_flipped = False
    p_crossed = False

    for i, (o, n) in enumerate(zip(old_nums, new_nums)):
        if (o > 0) != (n > 0) and abs(o) > 1e-6 and abs(n) > 1e-6:
            sign_flipped = True
        if 0 < o < 0.10 and 0 < n < 0.10:
            # Looks like a p-value pair
            if (o < 0.05) != (n < 0.05):
                p_crossed = True
        shift = abs(pct_change(o, n))
        worst_shift = max(worst_shift, shift)

    if sign_flipped:
        return ('sign_flip', f'{old_val}  →  {new_val}  (SIGN FLIP)')
    if p_crossed:
        return ('p_cross', f'{old_val}  →  {new_val}  (p-value threshold crossed)')
    if worst_shift < 1.0:
        return ('minor', f'{old_val}  →  {new_val}  ({worst_shift:.1f}%)')
    if worst_shift < 5.0:
        return ('minor', f'{old_val}  →  {new_val}  ({worst_shift:.1f}%)')
    return ('shifted', f'{old_val}  →  {new_val}  ({worst_shift:.1f}%)')


def main():
    before_path = SNAP / 'key_claims_before.json'
    if not before_path.exists():
        print(f'ERROR: {before_path} not found', file=sys.stderr)
        sys.exit(1)

    before = json.load(open(before_path))

    after = {}
    for nb in NBS:
        path = ROOT / 'notebooks-v2' / f'{nb}.ipynb'
        if not path.exists():
            continue
        after[nb] = extract_key_claims(path)

    # Save post-fix snapshot alongside pre-fix
    (SNAP / 'key_claims_after.json').write_text(json.dumps(after, indent=2))

    out = []
    out.append('# Key Claims diff — 2026-04-12 coord fix\n')
    out.append(f'Snapshot location: `{SNAP.relative_to(ROOT)}`\n')
    out.append('')
    out.append('Compares K-ID tables extracted from affected notebooks before vs after '
               'the fixation-Y page-space fix. Flags shifts >5%, sign flips, '
               'and p-value threshold crossings.\n')

    totals = {'identical': 0, 'minor': 0, 'shifted': 0, 'sign_flip': 0,
              'p_cross': 0, 'new': 0, 'removed': 0, 'unparseable': 0}

    for nb in NBS:
        b = before.get(nb, {})
        a = after.get(nb, {})
        all_ids = sorted(set(b) | set(a), key=lambda k: (len(k), k))
        if not all_ids:
            continue

        out.append(f'## {nb}\n')
        out.append(f'Pre-fix: {len(b)} K-IDs · Post-fix: {len(a)} K-IDs\n')

        rows = []
        for kid in all_ids:
            ob = b.get(kid)
            oa = a.get(kid)
            old_val = ob['value'] if ob else None
            new_val = oa['value'] if oa else None
            desc = (oa or ob)['desc'] if (oa or ob) else ''
            status, detail = classify(old_val, new_val)
            totals[status] += 1

            if status == 'identical':
                continue  # omit identical rows for readability

            icon = {
                'minor': 'OK',
                'shifted': 'SHIFT',
                'sign_flip': 'FLIP',
                'p_cross': 'P-CROSS',
                'new': 'NEW',
                'removed': 'GONE',
                'unparseable': 'CHECK',
            }.get(status, '?')
            rows.append(f'| {icon} | **{kid}** | {desc} | {detail} |')

        if rows:
            out.append('| status | K-ID | description | change |')
            out.append('|---|---|---|---|')
            out.extend(rows)
            out.append('')
        else:
            out.append('_All K-IDs identical to pre-fix values._\n')

    out.append('## Summary\n')
    out.append('| class | count |')
    out.append('|---|---|')
    for k in ['identical', 'minor', 'shifted', 'sign_flip', 'p_cross', 'new', 'removed', 'unparseable']:
        out.append(f'| {k} | {totals[k]} |')
    out.append('')
    out.append('**Review priority:** `sign_flip` → `p_cross` → `shifted` → `new/removed`.')
    out.append(f'`minor` (< 5%) usually doesn\'t need prose edits. `identical` omitted.\n')

    diff_path = SNAP / 'key_claims_diff.md'
    diff_path.write_text('\n'.join(out))
    print(f'Wrote {diff_path}')
    print()
    print('Summary:')
    for k, v in totals.items():
        print(f'  {k:>12}: {v}')


if __name__ == '__main__':
    main()
