"""Append a '2026-05-04 typed cascade' section to each Tier-A notebook's
Key Claims markdown cell, populated from executed cell outputs.

Strategy: for each notebook, scrape numerical claims (regex over cell
stdout / execute_result text) and emit a curated section listing the
typed values for the K-IDs whose pattern signature is identifiable. The
new section is appended to the FIRST markdown cell that mentions 'Key
Claims'. Legacy K-IDs are preserved untouched.

Run:
  .venv/bin/python scripts/_append_typed_key_claims.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NB_DIR = Path('/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2')

# Per-notebook claim-scraper rules: (claim_label, regex, group_to_extract).
# `extract` is a list of regex captures from cell stdout that map to claim lines.
# When matched, the value gets included in the appended typed-cascade section
# under the label.
RULES: dict[str, list[dict]] = {
    '04_fixation_coverage': [
        # NB04 is mostly attribution-independent (fixation duration, TTI).
        # Pull whatever numbers do print so the typed re-execution timestamp
        # is recorded.
        {'label': 'TTI calibrator (first 5 → remaining)',
         'pattern': r'first[- ]5 TTI.*?r\s*=\s*([+-]?[\d.]+)'},
        {'label': 'Per-position TTI predictiveness',
         'pattern': r'positions?\s*\d+[-–]\d+'},
    ],
    '14_butterworth_cognitive_load': [
        {'label': 'Full-range Spearman ρ on position medians',
         'pattern': r'Spearman rho.*?:?\s*([+-]?[\d.]+),\s*p\s*=\s*([\d.e+-]+)'},
        {'label': 'Steep (P0–P3) cross-position Spearman',
         'pattern': r'(P0[-–]P3|steep).*?ρ?\s*=\s*([+-]?[\d.]+).*?p\s*=\s*([\d.e+-]+)'},
        {'label': 'Plateau (P4–P10) cross-position Spearman',
         'pattern': r'plateau.*?ρ?\s*=\s*([+-]?[\d.]+).*?p\s*=\s*([\d.e+-]+)'},
        {'label': 'Within-trial Spearman median ρ',
         'pattern': r'Median rho:\s*([+-]?[\d.]+)'},
        {'label': 'Clicked vs non-clicked LF/HF',
         'pattern': r'Clicked:.*?median\s+([\d.]+).*?Non-clicked:.*?median\s+([\d.]+)'},
        {'label': 'Trial-mean LF/HF × LHIPA',
         'pattern': r'LF/HF vs LHIPA.*?ρ\s*=\s*([+-]?[\d.]+),\s*p\s*=\s*([\d.e+-]+),\s*N\s*=\s*([\d,]+)'},
    ],
    '15_cursor_approach': [
        {'label': 'Click prediction LOSO AUC (M3 full)',
         'pattern': r'M3.*?AUC[^\d]+([0-9.]+)'},
        {'label': 'M4 approach-only LOSO AUC',
         'pattern': r'M4.*?AUC[^\d]+([0-9.]+)'},
    ],
    '18_ripa2_vs_lfhf': [
        {'label': 'RIPA2 cross-position Spearman ρ',
         'pattern': r'RIPA2.*?ρ\s*=\s*([+-]?[\d.]+).*?p\s*=\s*([\d.e+-]+)'},
        {'label': 'LF/HF × RIPA2 within-fixation correlation',
         'pattern': r'LF/HF.*?RIPA2.*?r\s*=\s*([+-]?[\d.]+)'},
    ],
    '22_four_class_taxonomy': [
        {'label': 'M3 LOSO AUC (typed)',
         'pattern': r'M3 LOSO.*?AUC[^\d]+([0-9.]+)'},
        {'label': 'Per-etype counts',
         'pattern': r'(organic|dd_top|native_ad|paa|image_pack|knowledge_panel|top_places).*?N\s*=\s*([\d,]+)'},
    ],
    '23_rank_effects': [
        {'label': 'CTR Spearman × organic-rank',
         'pattern': r'CTR.*?ρ\s*=\s*([+-]?[\d.]+).*?p\s*=\s*([\d.e+-]+)'},
        {'label': 'Click-share Spearman × rank',
         'pattern': r'click[- ]share.*?ρ\s*=\s*([+-]?[\d.]+)'},
    ],
    '24_retreat_arc_geometry': [
        {'label': 'Top-Ad lateral/arc ratio',
         'pattern': r'lateral.*?ratio.*?([\d.]+)'},
        {'label': 'Organic vs Top-Ad MW p-value',
         'pattern': r'Organic.*?Top.*?p\s*=\s*([\d.e+-]+)'},
    ],
    '25_serp_composition': [
        {'label': 'Trial count',
         'pattern': r'(\d+)\s*trials?'},
        {'label': 'Modal h3 slot count',
         'pattern': r'modal.*?(\d+)\s*absolute'},
    ],
    '28_viewport_bands': [
        {'label': 'Combined retreat + bands LOSO AUC',
         'pattern': r'combined.*?AUC[^\d]+([0-9.]+)'},
        {'label': 'Bands-alone LOSO AUC',
         'pattern': r'bands.alone.*?AUC[^\d]+([0-9.]+)'},
    ],
    '30_scroll_trajectory': [
        {'label': 'Forward-selection minimal AUC',
         'pattern': r'minimal.*?AUC[^\d]+([0-9.]+)'},
        {'label': 'n_reversals deferred vs eval-rejected',
         'pattern': r'n_reversals.*?Δ\s*=\s*([+-]?[\d.]+)'},
    ],
    '32_k_coefficient': [
        {'label': 'K clicked vs non-clicked',
         'pattern': r'clicked.*?\+([\d.]+).*?non-clicked.*?([+-][\d.]+)'},
        {'label': 'K × LF/HF position correlation',
         'pattern': r'K × .*?LF/HF.*?ρ\s*=\s*([+-]?[\d.]+)'},
    ],
}


def all_executed_text(nb: dict) -> str:
    parts = []
    for cell in nb.get('cells', []):
        if cell.get('cell_type') != 'code':
            continue
        for out in cell.get('outputs', []):
            text = ''
            if out.get('output_type') == 'stream':
                text = ''.join(out.get('text', []))
            elif out.get('output_type') == 'execute_result':
                data = out.get('data', {})
                text = ''.join(data.get('text/plain', []))
            if text:
                parts.append(text)
    return '\n'.join(parts)


def build_typed_section(nb_name: str, nb: dict) -> str:
    rules = RULES.get(nb_name)
    if not rules:
        return ''
    body = all_executed_text(nb)
    lines = [
        '',
        '### 2026-05-04 typed cascade — second post-cascade primary',
        '',
        '*Typed cascade (HTML+vision joint widget typing) replaced organic_hybrid as primary on 2026-05-04. Notebook re-executed under typed; values below scraped from executed cell output. Legacy K-IDs preserved above for historical comparison.*',
        '',
        '| Claim | Value (typed) |',
        '|---|---|',
    ]
    for rule in rules:
        m = re.search(rule['pattern'], body, flags=re.IGNORECASE | re.DOTALL)
        if m:
            value = m.group(0)[:120]
        else:
            value = '*(see executed cell output)*'
        lines.append(f'| {rule["label"]} | `{value}` |')
    lines.append('')
    return '\n'.join(lines)


def append_typed_section(nb_path: Path, nb_name: str) -> bool:
    nb = json.load(open(nb_path))
    section = build_typed_section(nb_name, nb)
    if not section:
        return False

    # Find the first markdown cell that mentions Key Claims and append.
    for cell in nb['cells']:
        if cell.get('cell_type') != 'markdown':
            continue
        src = cell.get('source', [])
        if isinstance(src, list):
            joined = ''.join(src)
        else:
            joined = src
        if 'Key Claims' not in joined and 'key claims' not in joined.lower():
            continue
        # Avoid duplicate appends
        if '2026-05-04 typed cascade' in joined:
            print(f'  {nb_name}: typed-cascade section already present, skipping',
                  file=sys.stderr)
            return False
        new_joined = joined.rstrip() + '\n' + section
        cell['source'] = new_joined.splitlines(keepends=True)
        json.dump(nb, open(nb_path, 'w'), indent=1)
        print(f'  {nb_name}: typed-cascade section appended',
              file=sys.stderr)
        return True
    print(f'  {nb_name}: no Key Claims cell found', file=sys.stderr)
    return False


def main():
    for nb_name in RULES:
        path = NB_DIR / f'{nb_name}.ipynb'
        if not path.exists():
            print(f'  {nb_name}: missing', file=sys.stderr)
            continue
        append_typed_section(path, nb_name)


if __name__ == '__main__':
    main()
