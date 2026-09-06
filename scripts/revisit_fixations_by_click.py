"""First-visit vs revisit fixations on organic results, by click status, AdSERP.

CHI27 Sara ask (04-results §4.1): support the alternation section with the
AdSERP first-visit/revisit fixation contrast. The draft currently quotes
"+32% more fixation (clicked) / -17% (non-clicked)" — prose-only numbers with
no K-ID whose current NB07b execution reads +12.5% / -7.9%, computed under the
retracted pre-2026-04-12 coordinate convention. This producer recomputes the
contrast on the current typed_gapfill substrate and restores the opportunity
denominators that the earlier intensity-only output omitted:

- Revisit prevalence: among organic element-trials with at least one fixation
  episode, the share with a later episode. This is a whole-trial gaze-defined
  baseline, not a post-click/browser-back rate.
- Upward-scroll + gaze retrieval: among upward gestures after prior fixation on
  the target set, whether gaze returns to that set before the next scroll.
  Gesture-level and any-success-per-trial denominators are both reported.

Conditional intensity remains under the original two constructs:

- Construct A ("episode"): the AO-paper-parallel construct. A visit to an
  element is a maximal run of consecutive fixations assigned to it. First
  visit = the first run; revisits = all later runs. Reported: mean fixations
  (and dwell ms) in the first visit vs mean per revisit and vs mean over all
  revisit fixations.
- Construct B ("regression-split", NB07b semantics rebuilt clean): for each
  element, the split time is the end of the first upward scroll gesture whose
  landing fixation (first fixation after the gesture) is that element.
  First = fixations before the split, revisit = at/after. Elements lacking a
  matched gesture or empty on either side are skipped (NB07b's restriction).

Shared definitions: gestures NB07a-parity (200 ms gap / net ±10 px, document
space). Fixation->element by gap-free y-band bisection against typed_gapfill
tops (FPOGY page-space, no scroll arithmetic). Click attribution via
attribute_click_to_typed_gapfill on the trial's final click, with mouse
events loaded in screenshot space (the coordinate-safe path). Organic
elements only for the clicked/non-clicked split.

Run:    .venv/bin/python scripts/revisit_fixations_by_click.py
Output: scripts/output/revisit_fixations_by_click/{summary.json,report.md}
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    assign_fixation_to_position,
    attribute_click_to_typed_gapfill,
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    load_typed_gapfill_aois,
    typed_alignment_exclusions,
    typed_gapfill_aoi_etypes,
    typed_gapfill_aoi_tops,
)

OUT = ROOT / 'scripts' / 'output' / 'revisit_fixations_by_click'
GAP_MS, NET_PX = 200, 10


def gestures(scrolls):
    if len(scrolls) < 2:
        return []
    runs, cur = [], [scrolls[0]]
    for s in scrolls[1:]:
        if s[0] - cur[-1][0] > GAP_MS:
            runs.append(cur)
            cur = [s]
        else:
            cur.append(s)
    runs.append(cur)
    return [{'t_start': g[0][0], 't_end': g[-1][0],
             'direction': 'down' if (g[-1][1] - g[0][1]) > NET_PX
             else ('up' if (g[-1][1] - g[0][1]) < -NET_PX else 'neutral')}
            for g in runs]


def agg(records):
    """records: list of dicts with first_n, first_ms, rev_n_mean, rev_ms_mean."""
    if not records:
        return None
    n = len(records)
    m = lambda k: sum(r[k] for r in records) / n  # noqa: E731
    fn, rn = m('first_n'), m('rev_n_mean')
    fms, rms = m('first_ms'), m('rev_ms_mean')
    return {
        'n_records': n,
        'first_visit_mean_fix': round(fn, 2),
        'revisit_mean_fix': round(rn, 2),
        'pct_change_fix': round(rn / fn - 1, 4) if fn else None,
        'first_visit_mean_ms': round(fms, 1),
        'revisit_mean_ms': round(rms, 1),
        'pct_change_ms': round(rms / fms - 1, 4) if fms else None,
    }


def prevalence(records):
    """Summarize a binary revisit/retrieval opportunity without conditioning on success."""
    if not records:
        return None
    by_trial = defaultdict(list)
    by_participant = defaultdict(list)
    for record in records:
        value = bool(record['revisited'])
        by_trial[record['trial_id']].append(value)
        by_participant[record['participant_id']].append(value)
    n = len(records)
    hits = sum(bool(record['revisited']) for record in records)
    return {
        'n_opportunities': n,
        'n_revisited': hits,
        'revisit_rate': hits / n,
        'n_trials': len(by_trial),
        'n_participants': len(by_participant),
        'equal_trial_mean_rate': sum(
            sum(values) / len(values) for values in by_trial.values()
        ) / len(by_trial),
        'equal_participant_mean_rate': sum(
            sum(values) / len(values) for values in by_participant.values()
        ) / len(by_participant),
    }


def collapse_gestures_to_trials(records):
    """Collapse gesture opportunities to one any-retrieval outcome per trial."""
    by_trial = defaultdict(list)
    participants = {}
    for record in records:
        by_trial[record['trial_id']].append(bool(record['revisited']))
        participants[record['trial_id']] = record['participant_id']
    return [
        {
            'trial_id': trial_id,
            'participant_id': participants[trial_id],
            'revisited': any(values),
        }
        for trial_id, values in by_trial.items()
    ]


def main():
    excluded = typed_alignment_exclusions()
    trials = [t for t in get_trial_ids() if t not in excluded]

    ep_rec = defaultdict(list)   # (etype, clicked) -> successful revisit records
    rs_rec = defaultdict(list)   # successful regression-split revisit records
    ep_opportunities = defaultdict(list)  # organic element-trial opportunities
    scroll_opportunities = defaultdict(list)  # upward-gesture opportunities
    pop = {'trials_analyzed': 0, 'skipped_no_gapfill_map': 0,
           'skipped_no_fixations': 0, 'trials_with_attributed_click': 0}

    for tid in trials:
        if not load_typed_gapfill_aois(tid):
            pop['skipped_no_gapfill_map'] += 1
            continue
        fixes = load_fixations(tid)
        if not fixes:
            pop['skipped_no_fixations'] += 1
            continue
        tops = typed_gapfill_aoi_tops(tid)
        etypes = typed_gapfill_aoi_etypes(tid)
        n = len(tops)
        pop['trials_analyzed'] += 1

        _, scrolls, clicks = load_mouse_events(tid, space='screenshot')
        clicked_pos = None
        if clicks:
            hit = attribute_click_to_typed_gapfill(clicks[-1][1], clicks[-1][2], tid)
            if hit is not None:
                clicked_pos = hit[0]
                pop['trials_with_attributed_click'] += 1

        seq = [(assign_fixation_to_position(f['y'], tops, n), f) for f in fixes]

        # Construct A: visit episodes per element
        episodes = defaultdict(list)  # pos -> list of [fix, ...] runs
        cur_pos, cur_run = None, []
        for pos, f in seq:
            if pos == cur_pos:
                cur_run.append(f)
            else:
                if cur_pos is not None and cur_pos >= 0:
                    episodes[cur_pos].append(cur_run)
                cur_pos, cur_run = pos, [f]
        if cur_pos is not None and cur_pos >= 0:
            episodes[cur_pos].append(cur_run)
        participant_id = tid.split('-')[0]
        for pos, runs in episodes.items():
            clicked = clicked_pos is not None and pos == clicked_pos
            if etypes[pos] == 'organic':
                opportunity = {
                    'trial_id': tid,
                    'participant_id': participant_id,
                    'revisited': len(runs) >= 2,
                }
                ep_opportunities['all'].append(opportunity)
                ep_opportunities['clicked' if clicked else 'non_clicked'].append(
                    opportunity
                )
            if len(runs) < 2:
                continue
            first, revs = runs[0], runs[1:]
            rec = {
                'first_n': len(first),
                'first_ms': sum(f['d'] for f in first),
                'rev_n_mean': sum(len(r) for r in revs) / len(revs),
                'rev_ms_mean': sum(sum(f['d'] for f in r) for r in revs) / len(revs),
            }
            key = (etypes[pos], clicked)
            ep_rec[key].append(rec)

        # Construct B: regression-split via landing fixation of first up-gesture
        all_gestures = gestures(scrolls)
        ups = [g for g in all_gestures if g['direction'] == 'up']
        for gesture in ups:
            later_starts = [
                other['t_start'] for other in all_gestures
                if gesture['t_end'] < other['t_start']
            ]
            window_end = min(later_starts) if later_starts else float('inf')
            prior_organic = {
                pos for pos, fixation in seq
                if fixation['t'] < gesture['t_end']
                and pos >= 0 and etypes[pos] == 'organic'
            }
            post_organic = {
                pos for pos, fixation in seq
                if gesture['t_end'] <= fixation['t'] < window_end
                and pos >= 0 and etypes[pos] == 'organic'
            }
            retrieved = prior_organic.intersection(post_organic)
            base = {'trial_id': tid, 'participant_id': participant_id}
            if prior_organic:
                scroll_opportunities['any_prior_organic'].append({
                    **base, 'revisited': bool(retrieved),
                })
            if clicked_pos is not None and clicked_pos in prior_organic:
                scroll_opportunities['clicked'].append({
                    **base, 'revisited': clicked_pos in retrieved,
                })
        split_t = {}
        for g in ups:
            land = next(((p, f) for p, f in seq if f['t'] >= g['t_end']), None)
            if land is None or land[0] < 0:
                continue
            if land[0] not in split_t:
                split_t[land[0]] = g['t_end']
        for pos, rt in split_t.items():
            before = [f for p, f in seq if p == pos and f['t'] < rt]
            after = [f for p, f in seq if p == pos and f['t'] >= rt]
            if not before or not after:
                continue
            rec = {
                'first_n': len(before),
                'first_ms': sum(f['d'] for f in before),
                'rev_n_mean': float(len(after)),
                'rev_ms_mean': float(sum(f['d'] for f in after)),
            }
            key = (etypes[pos], clicked_pos is not None and pos == clicked_pos)
            rs_rec[key].append(rec)

    def by_click(recs, etype):
        return {
            'clicked': agg(recs.get((etype, True), [])),
            'non_clicked': agg(recs.get((etype, False), [])),
        }

    stamp = {}
    sub = ROOT / 'data' / 'aoi-typed' / 'substrate.json'
    if sub.exists():
        stamp['substrate_json'] = json.loads(sub.read_text())
    try:
        stamp['allserp_git_sha'] = subprocess.run(
            ['git', 'rev-parse', '--short=12', 'HEAD'], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        stamp['allserp_git_sha'] = None

    summary = {
        'experiment': 'First-visit vs revisit fixations on organic results by click status, AdSERP (CHI27 alternation-support ask; replaces the un-K-IDed +32%/-17% prose figures)',
        'regime_tag': '[LAB, AdSERP, typed_gapfill]',
        'rank_type': 'typed_gapfill',
        'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'construct_A_episode': 'Visit = maximal run of consecutive fixations assigned (gap-free y-band bisection) to the element; first run vs mean per later run. Elements with >=2 runs only.',
        'construct_B_regression_split': 'Split time = end of first upward gesture (NB07a parity, 200ms/10px, document space) whose first subsequent fixation lands on the element; fixations before vs at/after. Both sides non-empty.',
        'click_attribution': 'attribute_click_to_typed_gapfill on final click, mouse events in screenshot space.',
        'population': pop,
        'organic': {
            'whole_trial_revisit_prevalence': {
                group: prevalence(ep_opportunities.get(group, []))
                for group in ('clicked', 'non_clicked', 'all')
            },
            'upward_scroll_gaze_retrieval': {
                'definition': (
                    'Opportunity = an upward scroll gesture after at least one prior '
                    'fixation on the target organic set. Retrieval = a fixation assigned '
                    'to that target after the gesture and before the next scroll gesture. '
                    'Gesture-level and trial-level denominators are reported separately.'
                ),
                'gesture_level': {
                    group: prevalence(scroll_opportunities.get(group, []))
                    for group in ('clicked', 'any_prior_organic')
                },
                'trial_level': {
                    group: prevalence(collapse_gestures_to_trials(
                        scroll_opportunities.get(group, [])
                    ))
                    for group in ('clicked', 'any_prior_organic')
                },
            },
            'construct_A_episode': by_click(ep_rec, 'organic'),
            'construct_B_regression_split': by_click(rs_rec, 'organic'),
        },
        'other_etypes_construct_A': {
            ety: agg(ep_rec.get((ety, False), []) + ep_rec.get((ety, True), []))
            for ety in ('dd_top', 'native_ad', 'image_pack', 'paa')
        },
        'prior_values_for_reference': {
            'chi_draft_prose': {'clicked': '+32%', 'non_clicked': '-17%', 'status': 'no K-ID; not reproducible from any executed cell; treat as stale'},
            'nb07b_cell10_current_execution': {'clicked': '+12.5% (12.8->14.4)', 'non_clicked': '-7.9% (8.9->8.2)', 'status': 'retracted pre-2026-04-12 coordinate convention (double-counts scroll)'},
            'sara_ao_port_all_trials': {'clicked': '-31% (11.4->7.9)', 'non_clicked': '-1% (8.8->8.7)'},
        },
        'substrate_stamp': stamp,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    def fmt(block):
        if block is None:
            return '| — | — | — | — |'
        return (f"| {block['n_records']} | {block['first_visit_mean_fix']} -> "
                f"{block['revisit_mean_fix']} ({block['pct_change_fix']:+.1%}) | "
                f"{block['first_visit_mean_ms']:.0f} -> {block['revisit_mean_ms']:.0f} ms "
                f"({block['pct_change_ms']:+.1%}) |")

    lines = ['# First-visit vs revisit fixations by click status — AdSERP organic',
             '', f"Tag: `{summary['regime_tag']}` · generated {summary['generated']}",
             '', '## Revisit prevalence (denominator-explicit)', '',
             '| group | revisited / visited element-trials | event rate | equal-trial rate | equal-participant rate |',
             '|---|---:|---:|---:|---:|']
    for group in ('clicked', 'non_clicked', 'all'):
        block = summary['organic']['whole_trial_revisit_prevalence'][group]
        lines.append(
            f"| {group} | {block['n_revisited']} / {block['n_opportunities']} | "
            f"{block['revisit_rate']:.1%} | {block['equal_trial_mean_rate']:.1%} | "
            f"{block['equal_participant_mean_rate']:.1%} |"
        )
    lines += ['', '## Upward-scroll + gaze retrieval (denominator-explicit)', '',
              '| target | gesture-level | trial-level |', '|---|---:|---:|']
    for group in ('clicked', 'any_prior_organic'):
        gesture = summary['organic']['upward_scroll_gaze_retrieval']['gesture_level'][group]
        trial = summary['organic']['upward_scroll_gaze_retrieval']['trial_level'][group]
        lines.append(
            f"| {group} | {gesture['n_revisited']} / {gesture['n_opportunities']} "
            f"({gesture['revisit_rate']:.1%}) | {trial['n_revisited']} / "
            f"{trial['n_opportunities']} ({trial['revisit_rate']:.1%}) |"
        )
    lines.append('')
    for cname, key in (('Construct A (episode, AO-parallel)', 'construct_A_episode'),
                       ('Construct B (regression-split, NB07b semantics clean)', 'construct_B_regression_split')):
        lines += [f'## {cname}', '', '| group | n | fixations first->revisit | dwell first->revisit |', '|---|---|---|---|']
        for grp in ('clicked', 'non_clicked'):
            lines.append(f"| {grp} " + fmt(summary['organic'][key][grp]))
        lines.append('')
    (OUT / 'report.md').write_text('\n'.join(lines))
    print(json.dumps({'population': pop, 'organic': summary['organic']}, indent=1))


if __name__ == '__main__':
    main()
