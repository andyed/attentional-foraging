"""Compare a candidate on a fixed audit cohort without dropping failures.

The reference is the repaired audit's per-parent DOM count diagnostic. This
comparison is not independent content identity accuracy or a corpus-wide rate.
Screenshot-registration status is reported separately from count agreement.
"""
import argparse
import hashlib
import json
from pathlib import Path


def compare(reference, candidate):
    cohort=[r for r in reference if r.get('cell_status')=='scored']
    expected={r['tid'] for r in cohort}
    if len(expected)!=len(cohort):
        raise ValueError('Duplicate reference trial identifiers')
    rows=candidate['trials']
    by_id={r['trial_id']:r for r in rows}
    if len(by_id)!=len(rows) or set(by_id)-expected:
        raise ValueError('Duplicate or out-of-cohort candidate trials')
    comparisons=[]
    for old in cohort:
        new=by_id.get(old['tid'])
        admitted=bool(new and new['status']=='scored' and new.get('registration_status')=='accepted')
        count=sum(bool(c.get('aligned_visible_rect_screenshot')) for p in new['parents'] for c in p['cells']) if admitted else 0
        # The sample has one top parent per trial; reject a changed grain rather
        # than let offsetting per-parent errors agree on a trial-level total.
        if len(old['cell_parent_comparisons'])!=1 or (new and len(new['parents'])!=1):
            raise ValueError('Comparison requires exactly one top parent per trial')
        comparisons.append({'trial_id':old['tid'],'reference_count':old['dom_cells'],
                            'legacy_count':old['export_cells'],'candidate_count':count,
                            'legacy_match':bool(old['cell_count_agree']),
                            'candidate_match':admitted and count==old['dom_cells'],
                            'candidate_present':new is not None,'registration_accepted':admitted,
                            'vertical_shift_px':new['parents'][0].get('screenshot_registration',{}).get('dy') if new else None})
    return {'schema':'allserp-carousel-match-comparison-v1','regime':'LAB','flavor':'typed parents / screenshot-registered DOM candidate cells',
            'scope':'fixed retained sample; count agreement and screenshot-stroke support, not independent semantic identity accuracy',
            'summary':{'cohort_trials':len(cohort),'legacy_match':sum(r['legacy_match'] for r in comparisons),
                       'candidate_match':sum(r['candidate_match'] for r in comparisons),
                       'registration_accepted':sum(r['registration_accepted'] for r in comparisons),
                       'missing_candidates':sum(not r['candidate_present'] for r in comparisons),
                       'large_vertical_corrections':sum(r['registration_accepted'] and abs(r['vertical_shift_px'] or 0)>3 for r in comparisons),
                       'reference_cards':sum(r['reference_count'] for r in comparisons),
                       'candidate_cards':sum(r['candidate_count'] for r in comparisons)},'trials':comparisons}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    report=compare(json.loads(args.reference.read_text()),json.loads(args.candidate.read_text()))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report['inputs']={'reference_sha256':sha(args.reference),'candidate_sha256':sha(args.candidate),'producer_sha256':sha(Path(__file__))}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary']))


if __name__=='__main__':
    main()
