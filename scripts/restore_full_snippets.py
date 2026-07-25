"""One-time repair (2026-07-17): restore untruncated snippet text in
serp-embeddings.json and serp-embeddings-split.json.

Background: embed_serp_results.py stored `snippet[:200]` (and the HTML walk
capped at [:500]), so snippet_chars/snippet_tokens/snippet_ttr computed by
compute_content_features.py were range-restricted (93% of snippets at exactly
200 chars; corpus mean 198, sd 11). This silently nulled any analysis using
snippet length/diversity as a predictor (NB33 Gate B, click_prediction_ablation).

Embeddings are NOT touched: the embedding input was a separate capped field
(`text[:400]` combined; title/snippet [:400] split), which this repair leaves
as-is. Only the stored `snippet` string is replaced by the full re-parsed text.

Integrity check per result: the old truncated snippet must be an exact prefix
of the restored full snippet (old = full[:200] combined, full[:500] split).
Results failing the check are left untouched and counted.

Run:
  .venv/bin/python scripts/restore_full_snippets.py
Then regenerate features:
  .venv/bin/python scripts/compute_content_features.py --attribution organic
  .venv/bin/python scripts/compute_content_features.py --attribution absolute
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_serp_results import extract_serp_results  # noqa: E402 (uncapped as of 2026-07-17)

ROOT = Path(__file__).resolve().parent.parent
SERP_DIR = ROOT / 'AdSERP/data/serps'
TARGETS = [
    # (path, old_cap) — old stored snippet == full_snippet[:old_cap]
    (ROOT / 'AdSERP/data/serp-embeddings.json', 200),
    (ROOT / 'AdSERP/data/serp-embeddings-split.json', 500),
]


def build_full_snippets() -> dict[str, dict[int, str]]:
    """Re-parse every SERP HTML → {trial_id: {position: full_snippet}}."""
    files = sorted(SERP_DIR.glob('*.html'))
    print(f'[parse] {len(files)} SERP HTML files', file=sys.stderr)
    full: dict[str, dict[int, str]] = {}
    for i, fp in enumerate(files):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(files)}', file=sys.stderr)
        results = extract_serp_results(str(fp))
        full[fp.stem] = {r['position']: r['snippet'] for r in results}
    return full


def patch(path: Path, cap: int, full: dict[str, dict[int, str]]) -> None:
    print(f'\n[patch] {path.name} (old cap {cap})', file=sys.stderr)
    bak = path.with_suffix('.json.bak')
    if not bak.exists():
        print(f'  backup → {bak.name}', file=sys.stderr)
        shutil.copy2(path, bak)

    data = json.load(open(path))
    n_ok = n_same = n_missing = n_mismatch = 0
    for tid, results in data.items():
        trial_full = full.get(tid, {})
        for r in results:
            new = trial_full.get(r['position'])
            old = r.get('snippet', '')
            if new is None:
                n_missing += 1
                continue
            if new == old:
                n_same += 1
                continue
            if new[:cap] != old:
                # re-parse disagrees with what was originally stored — leave it
                n_mismatch += 1
                continue
            r['snippet'] = new
            n_ok += 1

    print(f'  restored {n_ok:,}  already-full {n_same:,}  '
          f'missing {n_missing:,}  prefix-mismatch {n_mismatch:,}', file=sys.stderr)
    if n_mismatch > 0.01 * max(1, n_ok + n_same + n_mismatch):
        sys.exit(f'ABORT: >1% prefix mismatches in {path.name}; not writing. '
                 'Parse is not reproducing the original extraction.')

    tmp = path.with_suffix('.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(data, f)
    tmp.replace(path)
    print(f'  wrote {path.name} ({path.stat().st_size/1e6:.0f} MB)', file=sys.stderr)


def main() -> None:
    full = build_full_snippets()
    lens = [len(s) for tr in full.values() for s in tr.values()]
    import statistics
    print(f'[full snippets] n={len(lens):,} mean={statistics.mean(lens):.0f} '
          f'sd={statistics.stdev(lens):.0f} max={max(lens)}', file=sys.stderr)
    for path, cap in TARGETS:
        patch(path, cap, full)


if __name__ == '__main__':
    main()
