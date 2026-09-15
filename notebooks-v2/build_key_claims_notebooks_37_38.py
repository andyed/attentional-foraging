"""Build (and execute) NB37 and NB38, the reader notebooks whose Key Claims
blocks cover the 2026-09-14 / 09-15 producers.

Each notebook: title cell; Key Claims markdown rendered from
``key_claims_3738`` at build time; a code cell that asserts every input's
SHA256 against the values recorded at build; a final cell that prints the
same table from the same files. Re-run this script whenever a producer's
summary changes, then ``python notebooks-v2/update_key_claims.py``.

Usage: .venv/bin/python notebooks-v2/build_key_claims_notebooks_37_38.py
"""
import datetime as dt, json, subprocess, sys
from pathlib import Path
import nbformat as nbf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import key_claims_3738 as kc

NBDIR = Path(__file__).resolve().parent
TODAY = dt.date.today().isoformat()
MARKER = '## Key Claims (authoritative for paper writers)'

SPECS = {
    '37_engagement_states.ipynb': dict(
        files=kc.FILES_37, rows=kc.rows_37, which='37',
        title="# 37 — Engagement states, continuation, and what the periphery does",
        intro="""**Question.** What are the five engagement states a result can be in, how far
down the page does examination reach under each channel, what does each state
cost, and what does the near periphery contribute: evaluation, guidance, or
nothing?

**Regime:** `[LAB, AdSERP, typed]` throughout. Primary peripheral rule: intake
within 200 px (≈ 5° at the derived 43 px/°) of the band rect, per second of
on-screen-unfixated time, at or above the fixated median of the same element
type (`engagement_state_census.py --max-ogd-px 200`).

**This is a reader notebook.** The numbers are produced by the scripts below
and this notebook reads their summary JSONs, asserts their SHA256, and prints
the Key Claims table from them. Method, tables and caveats live in the notes.

| producer | note |
|---|---|
| `scripts/engagement_state_census.py` | `docs/ablations/engagement_state_census.md` |
| `scripts/engagement_continuation.py` | `docs/ablations/engagement_continuation.md` |
| `scripts/periphery_navigates.py` | `docs/ablations/periphery_navigates.md` |
| `scripts/pai_kernel_validation.py` | `docs/ablations/pai_kernel_validation.md` |
| `scripts/pai_deferred_probe.py` | `docs/ablations/pai_deferred_probe.md` |
| `scripts/bold_term_density.py` | `docs/null-findings/2026-09-14-bold-term-density-null.md` |
| 24 vs 43 px/° reruns | `docs/ablations/px_per_deg_rerun.md` |

**Not in this block:** the duration-accrual argument
(`docs/ablations/duration_parafoveal_accrual.md`) is an inline analysis with no
producer yet; anything from the AI-Overview corpus (collab-only).
"""),
    '38_moves_between_results.ipynb': dict(
        files=kc.FILES_38, rows=kc.rows_38, which='38',
        title="# 38 — Moves between results: returns, major saccades, the stutter step, and the survey",
        intro="""**Question.** How does the gaze move between results: how are returns
executed, what precedes a long jump and where does it go, what happens after
the first fixation on a result, and how does the five-fixation survey treat the
block above the fold?

**Regime:** `[LAB, AdSERP, typed]` throughout. Returns are deferred slots with
≥ 2 gaze visits (label producer's own assignment); moves are first entries onto
a result from a fixation on another result; the survey is the first five
fixations (NB13).

**This is a reader notebook.** The numbers are produced by the scripts below
and this notebook reads their summary JSONs, asserts their SHA256, and prints
the Key Claims table from them. Method, tables and caveats live in the notes.

| producer | note |
|---|---|
| `scripts/return_is_memory.py` | `docs/ablations/return_is_memory.md` |
| `scripts/major_saccade_selection.py` | `docs/ablations/major_saccade_selection.md` |
| `scripts/next_action_by_position.py` | `docs/ablations/next_action_by_position.md` |
| `scripts/survey_above_fold.py` | `docs/ablations/survey_above_fold.md` |

Figures: `scripts/output/figures/idealized_navigation.png`,
`idealized_vs_population.png`, `result_moves.png`.
"""),
}

for name, spec in SPECS.items():
    J = kc.load(spec['files']); rows = spec['rows'](J); inp = kc.inputs(spec['files'])
    nb = nbf.v4.new_notebook()
    nb.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    nb.cells.append(nbf.v4.new_markdown_cell(spec['title'] + '\n\n' + spec['intro']))
    kcmd = (f"{MARKER}\n\n*Regime `[LAB, AdSERP, typed]` for every row. Built and executed {TODAY} by "
            f"`notebooks-v2/build_key_claims_notebooks_37_38.py`. Every value below is rendered from the producers' "
            f"summary JSONs by `notebooks-v2/key_claims_3738.py` and is identical to the executed output of the final cell, "
            f"which prints the same table from the same files; values are never hand-typed. Inputs and their SHA256 are "
            f"asserted in cell 3.*\n\n" + kc.render(rows) + "\n\n**Inputs (SHA256 at build):**\n\n" +
            '\n'.join(f"- `{v['path']}` `{v['sha256'][:16]}…`" for v in inp.values()))
    nb.cells.append(nbf.v4.new_markdown_cell(kcmd))
    nb.cells.append(nbf.v4.new_code_cell(
        "import sys, json\nfrom pathlib import Path\nsys.path.insert(0, str(Path('.').resolve()))\nimport key_claims_3738 as kc\n\n"
        f"FILES = kc.FILES_{spec['which']}\nEXPECTED = {json.dumps({k: v['sha256'] for k, v in inp.items()}, indent=1)}\n"
        "for k, p in FILES.items():\n    got = kc.sha(p)\n    assert got == EXPECTED[k], f'{k}: {p} changed since build ({got[:12]} != {EXPECTED[k][:12]}); rebuild with build_key_claims_notebooks_37_38.py'\n"
        "print(f'{len(FILES)} inputs match their build-time SHA256')"))
    nb.cells.append(nbf.v4.new_markdown_cell("## The Key Claims table, printed from the producers\n\nThe markdown block above is a copy of this cell's output."))
    nb.cells.append(nbf.v4.new_code_cell(
        f"J = kc.load(FILES)\nrows = kc.rows_{spec['which']}(J)\nprint(kc.render(rows))"))
    path = NBDIR / name
    nbf.write(nb, path)
    subprocess.run([sys.executable, '-m', 'nbconvert', '--to', 'notebook', '--execute', '--inplace', str(path)], check=True, cwd=NBDIR)
    # verify: executed output == markdown table
    nb = nbf.read(path, as_version=4)
    out = ''.join(o.get('text', '') for o in nb.cells[-1].outputs)
    assert kc.render(rows) in out, f'{name}: executed table differs from the markdown block'
    print(f'built + executed {name}: {len(rows)} rows, output verified')
