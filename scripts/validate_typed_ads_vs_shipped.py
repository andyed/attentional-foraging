"""Validate typed AOI pipeline's ad classifications against shipped AdSERP
ad bboxes (gold standard).

AdSERP v1 ships per-trial ad bounding boxes for `native_ad`, `dd_top`, and
`dd_right` at AdSERP/data/ad-boundary-data/<tid>.json. These are the corpus
authors' ground-truth ad locations. Our typed pipeline classifies cards
into etypes including `native_ad` / `dd_top` / `dd_right` via Phase B+C
ad-overlap arbitration.

Validation metrics computed:

  Precision (typed → shipped): For each typed ad entry, does it spatially
    overlap a shipped ad bbox of the matching type?

  Recall (shipped → typed): For each shipped ad bbox, does the typed
    pipeline emit ≥ 1 entry of matching type whose geometry overlaps it?
    (Some shipped ad rails are subdivided in typed; counting at rail-level.)

  IoU on matched ad pairs.

  Confusion matrix on type-label disagreements.

Outputs:
  scripts/output/typed_ads_vs_shipped/summary.json
  scripts/output/typed_ads_vs_shipped/per_trial.jsonl

Run:
  .venv/bin/python scripts/validate_typed_ads_vs_shipped.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPED_DIR = ROOT / 'data/aoi-typed'
SHIPPED_DIR = ROOT / 'AdSERP/data/ad-boundary-data'
ORGANIC_BBOX_DIR = ROOT / 'AdSERP/data/organic-boundary-data'
OUT_DIR = ROOT / 'scripts/output/typed_ads_vs_shipped'
OUT_DIR.mkdir(parents=True, exist_ok=True)

AD_TYPES = ('native_ad', 'dd_top', 'dd_right')
# Min IoU for a typed entry to "match" a shipped bbox
MATCH_IOU_THRESHOLD = 0.30


def bbox_iou(a, b):
    """IoU between two bboxes given as (x, y, w, h) tuples."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def bbox_contained_frac(small, big):
    """Fraction of small's area that lies inside big."""
    sx1, sy1, sw, sh = small
    bx1, by1, bw, bh = big
    sx2, sy2 = sx1 + sw, sy1 + sh
    bx2, by2 = bx1 + bw, by1 + bh
    ix1 = max(sx1, bx1)
    iy1 = max(sy1, by1)
    ix2 = min(sx2, bx2)
    iy2 = min(sy2, by2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    s_area = sw * sh
    return inter / s_area if s_area > 0 else 0.0


def shipped_to_bboxes(shipped):
    """Return list of (etype, bbox) from shipped ad-boundary JSON."""
    out = []
    for et in AD_TYPES:
        for ad in shipped.get(et, []):
            loc = ad.get('location', {})
            sz = ad.get('size', {})
            out.append((et, (float(loc.get('x', 0)), float(loc.get('y', 0)),
                             float(sz.get('width', 0)), float(sz.get('height', 0)))))
    return out


def typed_to_ad_entries(typed):
    """Return list of (etype, bbox, source) for typed entries that claim
    to be ads (native_ad, dd_top, dd_right)."""
    out = []
    for e in typed:
        if e.get('type') not in AD_TYPES:
            continue
        if e.get('x') is None or e.get('y') is None:
            continue
        out.append((e['type'],
                    (float(e['x']), float(e['y']),
                     float(e.get('width', 0)), float(e.get('height', 0))),
                    e.get('source', '')))
    return out


def validate_trial(tid):
    """Returns per-trial audit dict + per-shipped-bbox match records."""
    typed_path = TYPED_DIR / f'{tid}.json'
    shipped_path = SHIPPED_DIR / f'{tid}.json'
    if not typed_path.exists() or not shipped_path.exists():
        return None

    typed = json.loads(typed_path.read_text())
    shipped = json.loads(shipped_path.read_text())

    typed_ads = typed_to_ad_entries(typed)
    shipped_ads = shipped_to_bboxes(shipped)

    # ── Recall: for each shipped bbox, find best-IoU typed match (any type)
    #    and best-IoU typed match of MATCHING type
    shipped_match_records = []
    used_typed = set()  # indices of typed_ads used as best matches
    for sh_idx, (sh_type, sh_bb) in enumerate(shipped_ads):
        best_iou = 0.0
        best_idx = None
        best_same_iou = 0.0
        best_same_idx = None
        # Also: for rails that are subdivided in typed, sum up contained fraction
        contained_total_same = 0.0
        contained_count_same = 0
        for ty_idx, (ty_type, ty_bb, _src) in enumerate(typed_ads):
            iou = bbox_iou(ty_bb, sh_bb)
            if iou > best_iou:
                best_iou = iou
                best_idx = ty_idx
            if ty_type == sh_type:
                if iou > best_same_iou:
                    best_same_iou = iou
                    best_same_idx = ty_idx
                # Sum coverage: how much of typed entry is inside shipped
                cf = bbox_contained_frac(ty_bb, sh_bb)
                if cf >= 0.5:
                    contained_total_same += ty_bb[2] * ty_bb[3]
                    contained_count_same += 1

        # Recall: covered if any same-type entry has IoU >= threshold OR
        #         contained-coverage of shipped area is >= 50%
        coverage_frac = (contained_total_same /
                         (sh_bb[2] * sh_bb[3])) if sh_bb[2] * sh_bb[3] > 0 else 0.0
        covered_same = (best_same_iou >= MATCH_IOU_THRESHOLD or
                        coverage_frac >= 0.5)
        wrong_type_match = (best_idx is not None and best_iou >= MATCH_IOU_THRESHOLD
                            and typed_ads[best_idx][0] != sh_type)

        shipped_match_records.append({
            'shipped_type': sh_type,
            'best_iou': best_iou,
            'best_iou_typed_type': typed_ads[best_idx][0] if best_idx is not None else None,
            'best_same_type_iou': best_same_iou,
            'coverage_frac': coverage_frac,
            'contained_count_same': contained_count_same,
            'covered': covered_same,
            'wrong_type_match': wrong_type_match,
        })
        if covered_same and best_same_idx is not None:
            used_typed.add(best_same_idx)

    # ── Precision: for each typed ad entry, find best-IoU shipped match
    typed_match_records = []
    for ty_idx, (ty_type, ty_bb, src) in enumerate(typed_ads):
        best_iou = 0.0
        best_idx = None
        best_same_iou = 0.0
        for sh_idx, (sh_type, sh_bb) in enumerate(shipped_ads):
            iou = bbox_iou(ty_bb, sh_bb)
            if iou > best_iou:
                best_iou = iou
                best_idx = sh_idx
            if sh_type == ty_type and iou > best_same_iou:
                best_same_iou = iou

        match_type = (shipped_ads[best_idx][0] if best_idx is not None
                      and best_iou >= MATCH_IOU_THRESHOLD else None)
        typed_match_records.append({
            'typed_type': ty_type,
            'source': src,
            'best_iou': best_iou,
            'matched_shipped_type': match_type,
            'same_type_match': best_same_iou >= MATCH_IOU_THRESHOLD,
            'matched_any_ad': best_iou >= MATCH_IOU_THRESHOLD,
        })

    # Trial-level summary
    n_shipped = len(shipped_ads)
    n_typed = len(typed_ads)
    n_recalled = sum(1 for r in shipped_match_records if r['covered'])
    n_precision_match = sum(1 for r in typed_match_records if r['same_type_match'])
    n_precision_any = sum(1 for r in typed_match_records if r['matched_any_ad'])

    # ── Phase A consistency check: do any organic_result bboxes
    #    overlap any shipped ad? If yes, Phase A's `is_ad` failed to
    #    subtract — typed pipeline would re-classify via cv_bbox+ad_overlap.
    organic_path = ORGANIC_BBOX_DIR / f'{tid}.json'
    phase_a_collisions = []  # list of (organic_pos, shipped_type, iou)
    if organic_path.exists():
        organic_data = json.loads(organic_path.read_text())
        for org in organic_data.get('organic_result', []):
            loc = org.get('location', {})
            sz = org.get('size', {})
            org_bb = (float(loc.get('x', 0)), float(loc.get('y', 0)),
                      float(sz.get('width', 0)), float(sz.get('height', 0)))
            for sh_type, sh_bb in shipped_ads:
                iou = bbox_iou(org_bb, sh_bb)
                # Use asymmetric containment: if 30% of organic area is
                # inside a shipped ad, it's a Phase-A miss
                contained = bbox_contained_frac(org_bb, sh_bb)
                ad_contained = bbox_contained_frac(sh_bb, org_bb)
                if iou >= 0.30 or contained >= 0.50 or ad_contained >= 0.50:
                    phase_a_collisions.append({
                        'organic_pos': org.get('position'),
                        'shipped_type': sh_type,
                        'iou': iou,
                        'organic_in_ad_frac': contained,
                        'ad_in_organic_frac': ad_contained,
                    })
                    break  # one collision per organic; don't double-count

    return {
        'tid': tid,
        'n_shipped': n_shipped,
        'n_typed': n_typed,
        'n_recalled': n_recalled,
        'n_precision_match': n_precision_match,
        'n_precision_any': n_precision_any,
        'phase_a_collisions': phase_a_collisions,
        'n_phase_a_organic': len(json.loads(organic_path.read_text()).get('organic_result', []))
                               if organic_path.exists() else 0,
        'shipped_match_records': shipped_match_records,
        'typed_match_records': typed_match_records,
    }


def main():
    tids = sorted(p.stem for p in TYPED_DIR.glob('*.json'))
    print(f"[validate-typed-ads] {len(tids):,} trials with typed AOI", file=sys.stderr)

    # Per-trial audits
    audits = []
    skipped = 0
    for i, tid in enumerate(tids):
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(tids)}", file=sys.stderr)
        a = validate_trial(tid)
        if a is None:
            skipped += 1
            continue
        audits.append(a)

    # Aggregate
    total_shipped = sum(a['n_shipped'] for a in audits)
    total_typed = sum(a['n_typed'] for a in audits)
    total_recalled = sum(a['n_recalled'] for a in audits)
    total_precision = sum(a['n_precision_match'] for a in audits)
    total_precision_any = sum(a['n_precision_any'] for a in audits)

    # Phase A consistency aggregate
    total_phase_a_organic = sum(a.get('n_phase_a_organic', 0) for a in audits)
    total_phase_a_collisions = sum(len(a.get('phase_a_collisions', []))
                                    for a in audits)
    trials_with_collision = sum(1 for a in audits
                                 if a.get('phase_a_collisions'))

    recall_overall = total_recalled / total_shipped if total_shipped else 0.0
    precision_overall = total_precision / total_typed if total_typed else 0.0
    precision_any_overall = total_precision_any / total_typed if total_typed else 0.0

    # Per-etype breakdown
    by_type_shipped = defaultdict(lambda: {'n': 0, 'recalled': 0, 'mean_iou_same': []})
    by_type_typed = defaultdict(lambda: {'n': 0, 'precision_match': 0,
                                          'precision_any': 0, 'mean_iou_same': []})
    by_typed_source = defaultdict(lambda: {'n': 0, 'precision_match': 0})

    for a in audits:
        for r in a['shipped_match_records']:
            t = r['shipped_type']
            by_type_shipped[t]['n'] += 1
            if r['covered']:
                by_type_shipped[t]['recalled'] += 1
            if r['best_same_type_iou'] > 0:
                by_type_shipped[t]['mean_iou_same'].append(r['best_same_type_iou'])
        for r in a['typed_match_records']:
            t = r['typed_type']
            by_type_typed[t]['n'] += 1
            if r['same_type_match']:
                by_type_typed[t]['precision_match'] += 1
            if r['matched_any_ad']:
                by_type_typed[t]['precision_any'] += 1
            by_typed_source[r['source']]['n'] += 1
            if r['same_type_match']:
                by_typed_source[r['source']]['precision_match'] += 1

    # Cross-type confusion: when typed ≠ shipped, what's the swap?
    wrong_swap = Counter()
    for a in audits:
        for r in a['typed_match_records']:
            mt = r['matched_shipped_type']
            if mt is not None and mt != r['typed_type']:
                wrong_swap[(r['typed_type'], mt)] += 1

    # Build summary dict (compact)
    by_type_summary = {}
    for t in AD_TYPES:
        sh = by_type_shipped.get(t, {'n': 0, 'recalled': 0, 'mean_iou_same': []})
        ty = by_type_typed.get(t, {'n': 0, 'precision_match': 0,
                                    'precision_any': 0, 'mean_iou_same': []})
        ious = sh['mean_iou_same']
        by_type_summary[t] = {
            'shipped_n': sh['n'],
            'shipped_recalled': sh['recalled'],
            'recall': sh['recalled'] / sh['n'] if sh['n'] else None,
            'typed_n': ty['n'],
            'typed_precision_match': ty['precision_match'],
            'precision': ty['precision_match'] / ty['n'] if ty['n'] else None,
            'precision_any_ad': ty['precision_any'] / ty['n'] if ty['n'] else None,
            'mean_iou_same_type_match': (sum(ious) / len(ious)) if ious else None,
            'median_iou_same_type_match': (sorted(ious)[len(ious) // 2]
                                            if ious else None),
        }

    summary = {
        'date': '2026-05-04',
        'attribution': 'typed',
        'n_trials_audited': len(audits),
        'n_trials_skipped': skipped,
        'match_iou_threshold': MATCH_IOU_THRESHOLD,
        'phase_a_consistency': {
            'n_organic_bboxes_total': total_phase_a_organic,
            'n_organic_bboxes_overlapping_shipped_ad': total_phase_a_collisions,
            'collision_rate': (total_phase_a_collisions /
                               total_phase_a_organic) if total_phase_a_organic else 0.0,
            'n_trials_with_any_collision': trials_with_collision,
            'note': ('zero collisions means Phase A is_ad subtraction never '
                     'leaks ads into organic_result; non-zero indicates ads '
                     'that Phase A missed and Phase C had to reclassify'),
        },
        'overall': {
            'shipped_n': total_shipped,
            'typed_n': total_typed,
            'shipped_recalled': total_recalled,
            'typed_precision_match': total_precision,
            'typed_precision_any_ad': total_precision_any,
            'recall': recall_overall,
            'precision_same_type': precision_overall,
            'precision_any_ad': precision_any_overall,
            'f1_same_type': (2 * recall_overall * precision_overall /
                             (recall_overall + precision_overall)
                             if (recall_overall + precision_overall) else None),
        },
        'by_etype': by_type_summary,
        'by_typed_source': {s: v for s, v in by_typed_source.items()},
        'cross_type_swaps': {f'{t}->{m}': n for (t, m), n in wrong_swap.most_common()},
    }

    out_path = OUT_DIR / 'summary.json'
    out_path.write_text(json.dumps(summary, indent=2))

    # Per-trial JSONL (without the giant match-record arrays — just headlines)
    pt_path = OUT_DIR / 'per_trial.jsonl'
    with pt_path.open('w') as f:
        for a in audits:
            f.write(json.dumps({
                'tid': a['tid'],
                'n_shipped': a['n_shipped'],
                'n_typed': a['n_typed'],
                'n_recalled': a['n_recalled'],
                'n_precision_match': a['n_precision_match'],
            }) + '\n')

    # Print headlines
    print(f"\n=== Typed AOI ad-typing validation against shipped AdSERP ad bboxes ===\n", file=sys.stderr)
    print(f"  trials audited       : {len(audits):,}", file=sys.stderr)
    print(f"  shipped ad bboxes    : {total_shipped:,}", file=sys.stderr)
    print(f"  typed ad entries     : {total_typed:,}", file=sys.stderr)
    print(f"  Phase A organic bboxes: {total_phase_a_organic:,}", file=sys.stderr)
    print(f"  Phase A collisions   : {total_phase_a_collisions:,}  "
          f"({trials_with_collision:,} trials affected)", file=sys.stderr)
    if total_phase_a_organic:
        print(f"  Phase A collision rate: "
              f"{total_phase_a_collisions / total_phase_a_organic:.4f}",
              file=sys.stderr)
    print(f"\n  Recall (shipped → typed, IoU≥{MATCH_IOU_THRESHOLD} or coverage≥50%):"
          f"\n    overall   : {recall_overall:.3f}  ({total_recalled:,}/{total_shipped:,})",
          file=sys.stderr)
    for t in AD_TYPES:
        s = by_type_summary[t]
        if s['shipped_n']:
            print(f"    {t:10s}: {s['recall']:.3f}  "
                  f"({s['shipped_recalled']:,}/{s['shipped_n']:,})",
                  file=sys.stderr)
    print(f"\n  Precision (typed → shipped, same type, IoU≥{MATCH_IOU_THRESHOLD}):"
          f"\n    overall   : {precision_overall:.3f}  ({total_precision:,}/{total_typed:,})",
          file=sys.stderr)
    for t in AD_TYPES:
        s = by_type_summary[t]
        if s['typed_n']:
            print(f"    {t:10s}: {s['precision']:.3f}  "
                  f"({s['typed_precision_match']:,}/{s['typed_n']:,})  "
                  f"any-ad: {s['precision_any_ad']:.3f}",
                  file=sys.stderr)
    print(f"\n  F1 (same-type)       : "
          f"{summary['overall']['f1_same_type']:.3f}", file=sys.stderr)
    print(f"\n  Mean / median IoU on same-type matches:", file=sys.stderr)
    for t in AD_TYPES:
        s = by_type_summary[t]
        if s['mean_iou_same_type_match'] is not None:
            print(f"    {t:10s}: mean={s['mean_iou_same_type_match']:.3f}  "
                  f"median={s['median_iou_same_type_match']:.3f}",
                  file=sys.stderr)

    if wrong_swap:
        print(f"\n  Cross-type misclassifications (typed → matched shipped):",
              file=sys.stderr)
        for (t, m), n in wrong_swap.most_common(5):
            print(f"    {t} → {m}: {n}", file=sys.stderr)
    else:
        print(f"\n  No cross-type misclassifications", file=sys.stderr)

    print(f"\n  Precision by typed-entry source:", file=sys.stderr)
    for src, v in sorted(by_typed_source.items(), key=lambda kv: -kv[1]['n']):
        if v['n']:
            print(f"    {src:35s}: n={v['n']:6,d}  "
                  f"precision={v['precision_match'] / v['n']:.3f}",
                  file=sys.stderr)

    print(f"\nWrote {out_path}", file=sys.stderr)
    print(f"Wrote {pt_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
