"""Patch Tier-A notebooks to load typed-attribution data.

For each notebook, do a string substitution in cell sources:
  cursor-approach-features-organic.json  -> -typed
  cursor-approach-features-organic-hybrid.json -> -typed
  cursor-approach-features.json (legacy absolute) -> -typed
  butterworth-lfhf-by-position-organic.json -> -typed
  ripa2-by-position-organic.json -> -typed
  k-coefficient-by-position-organic.json -> -typed
  retreat-arcs-organic.json -> -typed
  regression_labels_cache_organic.json -> _typed
  ...

Notebooks that already use typed (NB22) are skipped.
"""
import json
import sys
from pathlib import Path

NB_DIR = Path('/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2')

# Per-notebook list of (find, replace) substitutions
PATCHES = {
    '14_butterworth_cognitive_load.ipynb': [
        ('butterworth-lfhf-by-position-organic.json', 'butterworth-lfhf-by-position-typed.json'),
        ('butterworth-lfhf-by-position.json', 'butterworth-lfhf-by-position-typed.json'),
    ],
    '15_cursor_approach.ipynb': [
        ('cursor-approach-features-organic.json', 'cursor-approach-features-typed.json'),
        ('cursor-approach-features.json', 'cursor-approach-features-typed.json'),
        ('butterworth-lfhf-by-position.json', 'butterworth-lfhf-by-position-typed.json'),
    ],
    '18_ripa2_vs_lfhf.ipynb': [
        ('butterworth-lfhf-by-position-organic.json', 'butterworth-lfhf-by-position-typed.json'),
        ('butterworth-lfhf-by-position.json', 'butterworth-lfhf-by-position-typed.json'),
        ('ripa2-by-position-organic.json', 'ripa2-by-position-typed.json'),
        ('ripa2-by-position.json', 'ripa2-by-position-typed.json'),
    ],
    '23_rank_effects.ipynb': [
        ('butterworth-lfhf-by-position.json', 'butterworth-lfhf-by-position-typed.json'),
    ],
    '28_viewport_bands.ipynb': [
        ('cursor-approach-features-organic.json', 'cursor-approach-features-typed.json'),
        ('cursor-approach-features.json', 'cursor-approach-features-typed.json'),
        ('regression_labels_cache_organic.json', 'regression_labels_cache_typed.json'),
        ('regression_labels_cache.json', 'regression_labels_cache_typed.json'),
    ],
    '30_scroll_trajectory.ipynb': [
        ('cursor-approach-features.json', 'cursor-approach-features-typed.json'),
        ('regression_labels_cache.json', 'regression_labels_cache_typed.json'),
    ],
    '32_k_coefficient.ipynb': [
        ('k-coefficient-by-position-organic.json', 'k-coefficient-by-position-typed.json'),
        ('k-coefficient-by-position.json', 'k-coefficient-by-position-typed.json'),
    ],
    '24_retreat_arc_geometry.ipynb': [
        ('retreat-arcs-organic.json', 'retreat-arcs-typed.json'),
        ('retreat-arcs.json', 'retreat-arcs-typed.json'),
    ],
}


def patch_notebook(nb_path: Path, patches: list[tuple[str, str]]):
    nb = json.load(open(nb_path))
    n_subs = 0
    for cell in nb.get('cells', []):
        if cell.get('cell_type') != 'code':
            continue
        src = cell.get('source', [])
        if isinstance(src, list):
            joined = ''.join(src)
        else:
            joined = src
        new_joined = joined
        for find, repl in patches:
            if find in new_joined:
                new_joined = new_joined.replace(find, repl)
                n_subs += 1
        if new_joined != joined:
            cell['source'] = new_joined.splitlines(keepends=True)
    json.dump(nb, open(nb_path, 'w'), indent=1)
    return n_subs


def main():
    for nb_name, patches in PATCHES.items():
        path = NB_DIR / nb_name
        if not path.exists():
            print(f'  MISSING: {nb_name}', file=sys.stderr)
            continue
        n = patch_notebook(path, patches)
        print(f'  {nb_name}: {n} substitutions', file=sys.stderr)


if __name__ == '__main__':
    main()
