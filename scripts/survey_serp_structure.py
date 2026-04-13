#!/usr/bin/env python
"""Survey AdSERP corpus SERP structure.

Quantifies the distribution of slot counts, ad placements, and click
positions across the 2,776 AdSERP trials. Output is a set of CSV/JSON
tables consumed by docs/serp-structure-survey.md, plus a plain-text
summary printed to stdout.

Run:
    .venv/bin/python scripts/survey_serp_structure.py

All numbers in this survey come from re-executing this script; do not
hand-edit the memo tables.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    count_absolute_ranks,
    absolute_to_organic_rank,
    count_organic_ranks,
    absolute_rank_band_tops,
)
import data_loader as DL  # noqa: E402

OUT_DIR = ROOT / 'scripts' / 'output' / 'serp_structure_survey'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Local query extractor (data_loader.get_query expects a <query> tag the
# AdSERP metadata XML does not have).  The query slug lives inside <url>
# as a ?q= parameter and inside <task> as a pipe-separated suffix.
import xml.etree.ElementTree as _ET
from urllib.parse import urlparse, parse_qs

_QUERY_CACHE: dict[str, str] = {}


def _query_for(tid: str) -> str:
    if tid in _QUERY_CACHE:
        return _QUERY_CACHE[tid]
    path = ROOT / 'AdSERP' / 'data' / 'trial-metadata' / f'{tid}.xml'
    q = ''
    try:
        root = _ET.parse(path).getroot()
        url_el = root.find('url')
        if url_el is not None and url_el.text:
            qs = parse_qs(urlparse(url_el.text).query)
            q = (qs.get('q', [''])[0] or '').replace('-', ' ').strip().lower()
        if not q:
            task_el = root.find('task')
            if task_el is not None and task_el.text and '|' in task_el.text:
                q = task_el.text.split('|', 1)[1].replace('-', ' ').strip().lower()
    except Exception:
        q = ''
    _QUERY_CACHE[tid] = q
    return q


def _safe_int(s: str) -> int:
    try:
        return int(s)
    except Exception:
        return -1


def _participant_of(tid: str) -> str:
    return tid.split('-', 1)[0]


def _block_of(tid: str) -> str:
    # p004-b1-t1 → b1
    parts = tid.split('-')
    return parts[1] if len(parts) >= 2 else ''


def main() -> None:
    t_start = time.time()
    tids = get_trial_ids()
    n_trials = len(tids)
    print(f'[survey] {n_trials} trials')

    # ── Per-trial snapshot ────────────────────────────────────────────────
    # trial_row: dict with structural fields + click outcome
    rows: list[dict] = []
    abs_count_hist: Counter[int] = Counter()
    org_count_hist: Counter[int] = Counter()
    dd_top_hist: Counter[int] = Counter()
    native_hist: Counter[int] = Counter()
    config_hist: Counter[tuple[int, int]] = Counter()
    dd_top_abs_positions: Counter[int] = Counter()
    native_abs_positions: Counter[int] = Counter()
    first_organic_abs_hist: Counter[int] = Counter()

    # click tabulations
    clicks_by_abs_rank: Counter[int] = Counter()
    clicks_by_org_rank: Counter[int] = Counter()
    clicks_in_ad_slot: int = 0
    clicks_no_rank_assigned: int = 0  # click below last slot, etc.
    trials_with_click: int = 0

    # For CTR-by-organic-rank (full corpus)
    impressions_by_org_rank: Counter[int] = Counter()
    click_trials_by_org_rank: Counter[int] = Counter()
    # Plain-top cohort (trials where absolute slot 0 is organic)
    impressions_plain_org: Counter[int] = Counter()
    click_trials_plain_org: Counter[int] = Counter()

    # Participant / block / query stratification
    per_participant_abs: defaultdict[str, list[int]] = defaultdict(list)
    per_participant_ddtop: defaultdict[str, list[int]] = defaultdict(list)
    per_participant_native: defaultdict[str, list[int]] = defaultdict(list)
    per_block_ddtop: defaultdict[str, list[int]] = defaultdict(list)
    per_block_native: defaultdict[str, list[int]] = defaultdict(list)
    per_query_ddtop: defaultdict[str, list[int]] = defaultdict(list)
    per_query_trials: Counter[str] = Counter()

    n_ads_ok = 0
    n_ads_missing = 0
    n_ads_empty = 0
    n_meta_missing = 0
    n_html_missing = 0

    progress_every = 200
    for i, tid in enumerate(tids):
        if i and i % progress_every == 0:
            print(f'[survey]   {i}/{n_trials} '
                  f'({(time.time() - t_start):.1f}s elapsed)')

        doc_h, scr_h, ts = get_trial_meta(tid)
        if doc_h is None:
            n_meta_missing += 1
            doc_h = 2642  # fallback used by data_loader
        n_abs = count_absolute_ranks(tid)
        if n_abs == 0:
            n_html_missing += 1
            continue

        ad_file_exists = (DL.AD_DIR / f'{tid}.json').exists()
        ad_regions = DL._load_ad_regions(tid)
        if ad_regions:
            n_ads_ok += 1
        else:
            # Empty dict → either file missing OR file present but zero rects.
            # Track both separately so downstream can tell "no data" from "no ads".
            if ad_file_exists:
                n_ads_empty += 1
            else:
                n_ads_missing += 1

        n_ddtop = len(ad_regions.get('dd_top', []))
        n_native = len(ad_regions.get('native_ad', []))

        mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
        n_org = sum(1 for v in mapping.values() if v is not None)

        abs_count_hist[n_abs] += 1
        org_count_hist[n_org] += 1
        dd_top_hist[n_ddtop] += 1
        native_hist[n_native] += 1
        config_hist[(n_ddtop, n_native)] += 1

        # ── Ad slot absolute-rank positions (per-slot, not per-ad-rect) ───
        ad_abs_slots_ddtop: list[int] = []
        ad_abs_slots_native: list[int] = []
        # We re-derive per-slot classification by running the same geometry
        # as absolute_to_organic_rank but tracking *which* etype hit.
        tops = absolute_rank_band_tops(n_abs, doc_h)
        for abs_rank in range(n_abs):
            top = tops[abs_rank]
            bot = tops[abs_rank + 1] if abs_rank + 1 < n_abs else doc_h - 200
            center = (top + bot) / 2
            hit_etype = None
            for etype, rects in ad_regions.items():
                for rx, ry, rw, rh in rects:
                    if not DL._rect_in_result_column(rx, rw):
                        continue
                    if ry <= center <= ry + rh:
                        hit_etype = etype
                        break
                if hit_etype:
                    break
            if hit_etype == 'dd_top':
                dd_top_abs_positions[abs_rank] += 1
                ad_abs_slots_ddtop.append(abs_rank)
            elif hit_etype == 'native_ad':
                native_abs_positions[abs_rank] += 1
                ad_abs_slots_native.append(abs_rank)

        # first organic absolute rank
        first_org_abs: int | None = None
        for abs_rank in range(n_abs):
            if mapping.get(abs_rank) is not None:
                first_org_abs = abs_rank
                break
        if first_org_abs is not None:
            first_organic_abs_hist[first_org_abs] += 1

        plain_top = (first_org_abs == 0)

        # impressions: every organic rank that exists in this trial
        for v in mapping.values():
            if v is not None:
                impressions_by_org_rank[v] += 1
                if plain_top:
                    impressions_plain_org[v] += 1

        # ── Clicks ────────────────────────────────────────────────────────
        try:
            _, _, clicks = load_mouse_events(tid)
        except Exception:
            clicks = []
        trial_click_abs = set()
        trial_click_org = set()
        has_any_click = False
        for (ct, cx, cy) in clicks:
            # Clicks are page-space.  Map to absolute rank by band.
            abs_rank = None
            for r in range(n_abs):
                top = tops[r]
                bot = tops[r + 1] if r + 1 < n_abs else doc_h - 200
                if top <= cy < bot:
                    abs_rank = r
                    break
            if abs_rank is None:
                clicks_no_rank_assigned += 1
                continue
            has_any_click = True
            clicks_by_abs_rank[abs_rank] += 1
            org_rank = mapping.get(abs_rank)
            if org_rank is None:
                clicks_in_ad_slot += 1
                continue
            clicks_by_org_rank[org_rank] += 1
            trial_click_abs.add(abs_rank)
            trial_click_org.add(org_rank)
        if has_any_click:
            trials_with_click += 1

        # CTR-by-organic-rank: count once per trial per rank clicked
        for v in trial_click_org:
            click_trials_by_org_rank[v] += 1
            if plain_top:
                click_trials_plain_org[v] += 1

        # Stratification
        pid = _participant_of(tid)
        blk = _block_of(tid)
        q = _query_for(tid)

        per_participant_abs[pid].append(n_abs)
        per_participant_ddtop[pid].append(n_ddtop)
        per_participant_native[pid].append(n_native)
        per_block_ddtop[blk].append(n_ddtop)
        per_block_native[blk].append(n_native)
        per_query_ddtop[q].append(n_ddtop)
        per_query_trials[q] += 1

        rows.append({
            'tid': tid,
            'pid': pid,
            'block': blk,
            'query': q,
            'n_abs': n_abs,
            'n_org': n_org,
            'n_ddtop': n_ddtop,
            'n_native': n_native,
            'first_org_abs': first_org_abs if first_org_abs is not None else -1,
            'plain_top': int(plain_top),
            'n_clicks_in_bands': sum(1 for (_, _, cy) in clicks
                                     if tops and tops[0] <= cy < (doc_h - 200)),
            'clicks_in_ad_slot': sum(1 for (_, _, cy) in clicks
                                     if _click_is_ad(cy, tops, n_abs, doc_h, mapping)),
        })

    elapsed = time.time() - t_start
    print(f'[survey] done in {elapsed:.1f}s')

    # ── Write per-trial snapshot ─────────────────────────────────────────
    snap_path = OUT_DIR / 'trial_snapshot.csv'
    with open(snap_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ── Helpers to write small tables ────────────────────────────────────
    def _write_counter(name: str, counter: Counter, key_label: str) -> None:
        path = OUT_DIR / f'{name}.csv'
        total = sum(counter.values())
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow([key_label, 'count', 'pct'])
            for k in sorted(counter):
                c = counter[k]
                w.writerow([k, c, f'{100 * c / max(total, 1):.2f}'])

    _write_counter('abs_count_hist', abs_count_hist, 'n_abs')
    _write_counter('org_count_hist', org_count_hist, 'n_org')
    _write_counter('ddtop_hist', dd_top_hist, 'n_ddtop')
    _write_counter('native_hist', native_hist, 'n_native')
    _write_counter('dd_top_abs_positions', dd_top_abs_positions, 'abs_rank')
    _write_counter('native_abs_positions', native_abs_positions, 'abs_rank')
    _write_counter('first_organic_abs_hist', first_organic_abs_hist, 'first_org_abs')
    _write_counter('clicks_by_abs_rank', clicks_by_abs_rank, 'abs_rank')
    _write_counter('clicks_by_org_rank', clicks_by_org_rank, 'org_rank')

    # config cross-tab (dd_top × native_ad)
    with open(OUT_DIR / 'ad_config_hist.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['n_ddtop', 'n_native', 'count', 'pct'])
        total = sum(config_hist.values())
        for (k, c) in sorted(config_hist.items(),
                             key=lambda kv: -kv[1]):
            nd, nn = k
            w.writerow([nd, nn, c, f'{100 * c / max(total, 1):.2f}'])

    # CTR-by-organic-rank (full corpus)
    def _ctr_table(imp: Counter, clk: Counter, name: str) -> list[dict]:
        path = OUT_DIR / f'{name}.csv'
        rows_out = []
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['org_rank', 'impressions', 'click_trials', 'ctr'])
            for r in sorted(imp):
                i = imp[r]
                c = clk.get(r, 0)
                ctr = c / i if i else 0.0
                w.writerow([r, i, c, f'{ctr:.4f}'])
                rows_out.append({'org_rank': r, 'impressions': i,
                                 'click_trials': c, 'ctr': ctr})
        return rows_out

    ctr_full = _ctr_table(impressions_by_org_rank, click_trials_by_org_rank,
                          'ctr_by_org_rank_full')
    ctr_plain = _ctr_table(impressions_plain_org, click_trials_plain_org,
                           'ctr_by_org_rank_plain_top')

    # ── Derived trial cohorts ────────────────────────────────────────────
    textbook_tids = [r['tid'] for r in rows
                     if r['n_abs'] == 10 and r['n_org'] == 10
                     and r['n_ddtop'] == 0 and r['n_native'] == 0]
    plain_top_tids = [r['tid'] for r in rows if r['plain_top'] == 1]
    no_ddtop_tids = [r['tid'] for r in rows if r['n_ddtop'] == 0]
    no_any_ad_tids = [r['tid'] for r in rows
                      if r['n_ddtop'] == 0 and r['n_native'] == 0]
    canonical_tids = [r['tid'] for r in rows
                      if r['n_org'] == 10 and r['n_ddtop'] <= 2
                      and r['n_native'] == 0]
    clean_for_ctr_tids = [r['tid'] for r in rows
                          if r['plain_top'] == 1
                          and r['n_org'] in (9, 10, 11)]

    def _cohort_summary(name: str, ids: list[str]) -> dict:
        pids = {t.split('-', 1)[0] for t in ids}
        blks = Counter(t.split('-')[1] if len(t.split('-')) >= 2 else ''
                       for t in ids)
        return {
            'name': name,
            'n_trials': len(ids),
            'pct_of_corpus': round(100 * len(ids) / n_trials, 2),
            'unique_participants': len(pids),
            'block_distribution': dict(blks),
        }

    cohorts = {
        'textbook_10org': _cohort_summary('textbook_10org', textbook_tids),
        'plain_top': _cohort_summary('plain_top', plain_top_tids),
        'no_ddtop': _cohort_summary('no_ddtop', no_ddtop_tids),
        'no_any_ad': _cohort_summary('no_any_ad', no_any_ad_tids),
        'canonical_10org_leq2ddtop': _cohort_summary(
            'canonical_10org_leq2ddtop', canonical_tids),
        'clean_for_ctr': _cohort_summary('clean_for_ctr', clean_for_ctr_tids),
    }
    (OUT_DIR / 'cohort_summary.json').write_text(
        json.dumps(cohorts, indent=2))
    (OUT_DIR / 'textbook_10org_tids.txt').write_text(
        '\n'.join(textbook_tids) + '\n')
    (OUT_DIR / 'no_any_ad_tids.txt').write_text(
        '\n'.join(no_any_ad_tids) + '\n')

    # ── Participant / block / query aggregates ───────────────────────────
    def _mean(xs: list[int]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    with open(OUT_DIR / 'per_participant.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pid', 'n_trials', 'mean_abs', 'mean_ddtop',
                    'mean_native', 'mean_ad_total'])
        for pid in sorted(per_participant_abs):
            xs_abs = per_participant_abs[pid]
            xs_dt = per_participant_ddtop[pid]
            xs_nt = per_participant_native[pid]
            tot = [a + b for a, b in zip(xs_dt, xs_nt)]
            w.writerow([pid, len(xs_abs),
                        f'{_mean(xs_abs):.2f}',
                        f'{_mean(xs_dt):.2f}',
                        f'{_mean(xs_nt):.2f}',
                        f'{_mean(tot):.2f}'])

    with open(OUT_DIR / 'per_block.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['block', 'n_trials', 'mean_ddtop', 'mean_native'])
        for blk in sorted(per_block_ddtop):
            xs_dt = per_block_ddtop[blk]
            xs_nt = per_block_native[blk]
            w.writerow([blk, len(xs_dt),
                        f'{_mean(xs_dt):.2f}',
                        f'{_mean(xs_nt):.2f}'])

    # Per-trial queries are all unique ("buy <brand> <product>" commerce
    # pattern). Aggregate by brand token (second word) instead.
    brand_trials: Counter[str] = Counter()
    brand_ddtop: defaultdict[str, list[int]] = defaultdict(list)
    brand_native: defaultdict[str, list[int]] = defaultdict(list)
    for r in rows:
        toks = (r['query'] or '').split()
        brand = toks[1] if len(toks) >= 2 else '(none)'
        brand_trials[brand] += 1
        brand_ddtop[brand].append(r['n_ddtop'])
        brand_native[brand].append(r['n_native'])

    q_rows = []
    for b, trials_n in brand_trials.items():
        if trials_n < 10:
            continue
        xs_dt = brand_ddtop[b]
        xs_nt = brand_native[b]
        q_rows.append((b, trials_n, _mean(xs_dt), _mean(xs_nt)))
    q_rows.sort(key=lambda r: (-r[2], -r[1]))
    with open(OUT_DIR / 'top_brands_ddtop.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['brand', 'n_trials', 'mean_ddtop', 'mean_native'])
        for b, n, m, mn in q_rows[:20]:
            w.writerow([b, n, f'{m:.2f}', f'{mn:.2f}'])

    unique_queries = sum(1 for q, n in per_query_trials.items() if q)
    unique_brands = sum(1 for b, n in brand_trials.items() if n >= 1)

    # ── Participant ad-exposure min / max summary ────────────────────────
    p_means = [
        (_mean(per_participant_ddtop[p]) + _mean(per_participant_native[p]))
        for p in per_participant_abs
    ]
    p_min = min(p_means) if p_means else 0.0
    p_max = max(p_means) if p_means else 0.0
    p_mean = _mean(p_means)

    # ── Layout heterogeneity summary ─────────────────────────────────────
    frac_canonical = len(canonical_tids) / n_trials
    frac_textbook = len(textbook_tids) / n_trials
    frac_plain = len(plain_top_tids) / n_trials
    frac_clean_ctr = len(clean_for_ctr_tids) / n_trials

    summary = {
        'n_trials': n_trials,
        'n_trials_with_clicks': trials_with_click,
        'n_meta_missing': n_meta_missing,
        'n_html_missing': n_html_missing,
        'n_ads_ok': n_ads_ok,
        'n_ads_missing': n_ads_missing,
        'n_ads_file_empty': n_ads_empty,
        'clicks_total_inside_bands': sum(clicks_by_abs_rank.values()),
        'clicks_in_ad_slot': clicks_in_ad_slot,
        'clicks_no_rank_assigned': clicks_no_rank_assigned,
        'abs_count_mode': abs_count_hist.most_common(1)[0] if abs_count_hist else None,
        'org_count_mode': org_count_hist.most_common(1)[0] if org_count_hist else None,
        'n_ddtop_zero': dd_top_hist.get(0, 0),
        'n_native_zero': native_hist.get(0, 0),
        'n_no_any_ad': len(no_any_ad_tids),
        'n_textbook_10org': len(textbook_tids),
        'n_canonical_10org_leq2ddtop': len(canonical_tids),
        'n_clean_for_ctr': len(clean_for_ctr_tids),
        'frac_canonical': round(frac_canonical, 4),
        'frac_textbook': round(frac_textbook, 4),
        'frac_plain_top': round(frac_plain, 4),
        'frac_clean_for_ctr': round(frac_clean_ctr, 4),
        'participant_ad_exposure_min': round(p_min, 3),
        'participant_ad_exposure_max': round(p_max, 3),
        'participant_ad_exposure_mean': round(p_mean, 3),
        'unique_queries': unique_queries,
        'unique_brands': unique_brands,
        'elapsed_seconds': round(elapsed, 2),
    }
    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Print the summary to stdout for the caller.
    print()
    print('── SUMMARY ──')
    for k, v in summary.items():
        print(f'  {k}: {v}')
    print()
    print('── CTR-by-organic-rank (full corpus) ──')
    for r in ctr_full[:12]:
        print(f'  org_rank={r["org_rank"]:>2}  '
              f'imp={r["impressions"]:>5}  '
              f'clk_trials={r["click_trials"]:>4}  '
              f'CTR={r["ctr"]:.4f}')
    print()
    print('── CTR-by-organic-rank (plain-top cohort) ──')
    for r in ctr_plain[:12]:
        print(f'  org_rank={r["org_rank"]:>2}  '
              f'imp={r["impressions"]:>5}  '
              f'clk_trials={r["click_trials"]:>4}  '
              f'CTR={r["ctr"]:.4f}')
    print()
    print(f'[survey] outputs in {OUT_DIR}')


def _click_is_ad(cy: float, tops: list[float], n_abs: int,
                 doc_h: int, mapping: dict) -> bool:
    """Check whether a click Y falls in an ad slot (helper for trial snap)."""
    if not tops:
        return False
    for r in range(n_abs):
        top = tops[r]
        bot = tops[r + 1] if r + 1 < n_abs else doc_h - 200
        if top <= cy < bot:
            return mapping.get(r) is None
    return False


if __name__ == '__main__':
    main()
