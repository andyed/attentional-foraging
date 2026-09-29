"""Verify the shipped atlas from its saved evidence; no raw-data refit.

Every check is fatal (non-zero exit with a message):
1. Local links and anchors in every HTML page resolve, and none points at a
   file the website copy leaves out. Repository links in the Markdown entry
   points (README, not-a-cascade, the atlas guide) resolve.
2. Cohort size, and every spatial partition of every trial conserves its clock.
3. Spatial aggregates re-summed from the per-trial records equal the summary.
4. The earlier target-overlap baseline is reproduced.
5. Resting-cursor gates equal the information-space aggregates; the five
   sequence gates equal the resting-cursor totals.
6. Common-coverage counts recomputed from the saved sequence records equal
   checks.json.
7. Numbers printed in the pages and posters equal their JSON sources.
8. Shipped values equal evidence-pin.json. A deliberate change to any shipped
   number fails here until it is re-pinned with `--pin`.

Writes integration-verification.json (no timestamps; repository-relative paths).
Run: .venv/bin/python scripts/attention_atlas/verify-atlas.py [--pin]
"""
import fnmatch
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import atlas_core as core
from atlas_core import ATLAS, CANONICAL_ATLAS, ROOT, gate

# Files the website copy (scripts/build-gh-pages.js, SITE_EXCLUDE) leaves out.
# Keep the two lists identical; HTML pages must not link to these locally.
SITE_EXCLUDE = ['*.md', '*.json.gz', 'import-manifest.json', 'integration-verification.json', 'evidence-pin.json',
                'render-manifest.json']
PIN = ATLAS / 'evidence-pin.json'
# Pinned evidence: summaries and checks without their provenance hashes, and
# the decoded per-trial records.
PINNED = ['information-space-poster/summary.json', 'information-space-poster/trials.json.gz',
          'information-space-poster/time-budgets.csv', 'gaze-cursor-echo/summary.json', 'gaze-cursor-echo/checks.json',
          'gaze-cursor-echo/trials.json.gz', 'gaze-cursor-echo/common-coverage-trials.json.gz',
          'evidence/resting-cursor/summary.json', 'evidence/resting-cursor/trials.json.gz',
          'evidence/final-approach/summary.json', 'evidence/final-approach/trial-summary.csv',
          'evidence/next-action-by-position.json']


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.refs, self.ids = [], set()
        self.feed(path.read_text())

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('src', 'href'):
            if key in attrs:
                self.refs.append(attrs[key])


def check_html():
    pages = {p.resolve(): Page(p) for p in ATLAS.rglob('*.html')}
    checked = 0
    for path, page in pages.items():
        for ref in page.refs:
            u = urlsplit(ref)
            if u.scheme or u.netloc:
                continue
            target = (path.parent / unquote(u.path)).resolve() if u.path else path
            if target.is_dir():
                target = target / 'index.html'
            gate(target.exists(), f'{core.rel(path)} links to missing {ref}')
            gate(not any(fnmatch.fnmatch(target.name, pat) for pat in SITE_EXCLUDE),
                 f'{core.rel(path)} links to {ref}, which the website copy leaves out')
            if u.fragment and target.suffix == '.html':
                gate(unquote(u.fragment) in pages[target].ids, f'{core.rel(path)}: missing anchor {ref}')
            checked += 1
    return len(pages), checked


def check_markdown():
    checked = 0
    for path in [ROOT / 'README.md', ROOT / 'docs/not-a-cascade.md', ATLAS / 'README.md']:
        for ref in re.findall(r'\]\(([^)\s]+)\)', path.read_text()):
            u = urlsplit(ref)
            if u.scheme or u.netloc or not u.path:
                continue
            target = (path.parent / unquote(u.path)).resolve()
            # An isolated AF_ATLAS_DIR copy has no ../ siblings; resolve those in the repository.
            if not target.exists() and path.parent == ATLAS:
                target = (CANONICAL_ATLAS / unquote(u.path)).resolve()
            gate(target.exists(), f'{core.rel(path)} links to missing {ref}')
            checked += 1
    return checked


def check_evidence():
    info = core.read_json(ATLAS / 'information-space-poster/summary.json')
    echo = core.read_json(ATLAS / 'gaze-cursor-echo/summary.json')
    rest = core.read_json(ATLAS / 'evidence/resting-cursor/summary.json')
    prior = core.read_json(ATLAS / 'evidence/final-approach/summary.json')
    trials = core.read_json(ATLAS / 'information-space-poster/trials.json.gz')
    gate(len(trials) == info['trials'] == echo['trials'] == rest['trials'] == core.COHORT_TRIALS, 'cohort size differs')
    gate(len({t['pid'] for t in trials}) == info['participants'] == core.COHORT_PARTICIPANTS, 'participant count differs')
    gate(sum(t['span_ms'] for t in trials) == info['total_ms'], 'total clock differs from the per-trial spans')
    agg, previous = defaultdict(Counter), defaultdict(Counter)
    for t in trials:
        for lens, values in t['stats'].items():
            agg[lens].update(values)
        for phase, values in t['previous'].items():
            previous[phase].update(values)
        for lens in ('joint', 'target', 'gaze_aoi', 'cursor_aoi', 'gaze_fold', 'cursor_fold', 'viewport'):
            gate(abs(sum(t['stats'][lens].values()) - t['span_ms']) < core.CONSERVATION_TOLERANCE_MS,
                 f"{t['trial_id']}: {lens} does not conserve the clock")
    for lens, values in info['aggregate_ms'].items():
        gate(dict(agg[lens]) == values, f'aggregate {lens} differs from the per-trial records')
    for phase in ('earlier', 'approach'):
        expected = prior['results'][f'xy|cap2000|full|{phase}']['milliseconds']
        for k in set(expected) | set(previous[phase]):
            gate(abs(previous[phase].get(k, 0) - expected.get(k, 0)) < core.GATE_TOLERANCE_MS,
                 f'prior target overlap {phase}.{k} not reproduced')
    # Resting-cursor gates against the information-space aggregates, both directions.
    gated = set()
    for g in rest['gates']:
        _, lens, state = g['source_path'].split('.')
        gate(g['status'] == 'ok' and g['delta'] == 0 and g['reproduced'] == info['aggregate_ms'][lens].get(state, 0),
             f"rest gate {g['source_path']} does not match the information-space summary")
        gated.add((lens, state))
    for lens in ('cursor_aoi', 'joint'):
        for state in info['aggregate_ms'][lens]:
            gate((lens, state) in gated, f'no rest gate covers {lens}.{state}')
    # Sequence gates against the resting-cursor totals.
    gate(len(echo['gates']) == 5, f"expected 5 sequence gates, found {len(echo['gates'])}")
    for g in echo['gates']:
        key = g['source_path'].split('.')[-1]
        expected = rest['results'][str(core.REST_PX_S)]['milliseconds'][key]
        gate(g['status'] == 'ok' and g['delta'] == 0 and g['reproduced'] == expected == echo['totals_ms'][key],
             f"sequence gate {key} does not match the resting-cursor summary")
    return len(rest['gates']) + len(echo['gates'])


def check_common_coverage():
    checks = core.read_json(ATLAS / 'gaze-cursor-echo/checks.json')
    trials = core.read_json(ATLAS / 'gaze-cursor-echo/trials.json.gz')
    totals = defaultdict(Counter)
    for r in map(core.common_coverage, trials):
        totals[r['pid']]['common_ms'] += r['common_ms']
        for ch in ('gaze', 'cursor'):
            for k, v in r[ch].items():
                totals[r['pid']][ch + '_' + k] += v
        totals[r['pid']]['first_count'] += len(r['first_lags_without_boundary'])
        totals[r['pid']]['gaze_first'] += sum(v > 0 for v in r['first_lags_without_boundary'])
    agg = Counter()
    for v in totals.values():
        agg.update(v)
    gate(dict(agg) == checks['common_coverage_totals'], 'common-coverage counts differ from checks.json')


def page_numbers():
    """Formatted values that must appear in the generated pages and posters."""
    import page_values
    expected = page_values.expected()
    missing = []
    for path, strings in expected.items():
        text = path.read_text()
        missing += [f'{core.rel(path)}: {s!r}' for s in strings if s not in text]
    gate(not missing, 'numbers in the pages, posters or prose differ from the JSON (rebuild them):\n  ' + '\n  '.join(missing))
    return sum(len(v) for v in expected.values())


def pinned_values():
    values = {}
    for rel_path in PINNED:
        path = ATLAS / rel_path
        if path.suffix in ('.json', '.gz'):
            obj = core.read_json(path)
            if isinstance(obj, dict):
                obj = {k: v for k, v in obj.items() if k != 'source_hashes'}
            values[rel_path] = core.canonical_digest(obj)
        else:
            values[rel_path] = core.sha256(path)
    return values


def main():
    values = pinned_values()
    if '--pin' in sys.argv:
        core.write_json(PIN, {'note': 'Digests of the shipped evidence, excluding provenance hashes. Re-pin only '
                                      'after a deliberate, reviewed change to the numbers (verify-atlas.py --pin).',
                              'values': values})
        print(f'Pinned {len(values)} evidence files in {core.rel(PIN)}')
    pin = core.read_json(PIN)['values']
    changed = sorted(k for k in set(pin) | set(values) if pin.get(k) != values.get(k))
    gate(not changed, 'shipped values differ from evidence-pin.json: ' + ', '.join(changed))
    pages, html_links = check_html()
    md_links = check_markdown()
    gates = check_evidence()
    check_common_coverage()
    numbers = page_numbers()
    report = {'status': 'passed',
              'scope': 'Verification from saved derived records; raw recordings were not recomputed.',
              'html_pages': pages, 'html_links_and_anchors': html_links, 'markdown_links': md_links,
              'trials': core.COHORT_TRIALS, 'participants': core.COHORT_PARTICIPANTS,
              'occupancy_conservation': 'passed for every trial and spatial partition',
              'aggregate_reproduction': 'all spatial aggregates match the per-trial records',
              'prior_target_overlap': 'earlier and approach durations match the prior baseline in both directions',
              'gates_cross_checked': gates,
              'common_coverage_recomputation': 'recomputed from saved sequence records; identical to checks.json',
              'page_numbers_checked': numbers,
              'pinned_evidence_files': len(values),
              'source_hashes': core.source_hashes(sorted((ROOT / 'scripts/attention_atlas').glob('*.py')))}
    core.write_json(ATLAS / 'integration-verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    main()
