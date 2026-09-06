"""Compare frozen and registered top cells on a fixed, complete corpus ledger."""
import argparse, collections, csv, hashlib, json
from pathlib import Path
import aoi_fidelity as audit

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def reconcile(candidate, reference, inventory):
    expected=candidate['manifest']['trial_ids']
    if len(expected)!=len(set(expected)):raise ValueError('duplicate cohort IDs')
    def index(rows,key):
        out={}
        for r in rows:
            if r[key] in out:raise ValueError('duplicate measured IDs')
            out[r[key]]=r
        if set(out)!=set(expected):raise ValueError('incomplete or changed cohort')
        return out
    candidates=index(candidate['trials'],'trial_id');refs=index(reference['trials'],'tid')
    if reference['manifest']['trial_ids']!=expected:raise ValueError('different audit cohort/order')
    if candidate['manifest']['exclusions_sha256']!=reference['manifest']['exclusions_sha256']:raise ValueError('different exclusion policy')
    ledger=[]
    for tid in expected:
        row=candidates[tid];ref=refs[tid]
        if row['analysis_eligible']!=ref['analysis_eligible']:raise ValueError('different admission policy')
        for key in ('html','screenshot','metadata','typed'):
            for record in (row,ref):
                value=record.get('inputs',{}).get(key)
                if not isinstance(value,dict) or not value.get('path') or not value.get('sha256'):
                    raise ValueError(f'missing {key} provenance: {tid}')
            if row.get('inputs',{}).get(key)!=ref.get('inputs',{}).get(key):raise ValueError(f'different or missing {key} input: {tid}')
        if not row.get('inputs') or not ref.get('measurement'):raise ValueError(f'unmeasured trial: {tid}')
        excluded=not row['analysis_eligible']
        if excluded and tid in inventory:raise ValueError('excluded trial leaked into candidate CSV')
        comparison=audit.compare_cells(ref['measurement'],inventory.get(tid),ref['ratio_x'],ref['ratio_y'],ref['typed_top_count'])
        admitted=not excluded and row['diagnostic_outcome']=='accepted'
        if admitted and (row['status']!='scored' or row.get('registration_status')!='accepted'):
            raise ValueError(f'inconsistent accepted state: {tid}')
        aligned_count=sum(bool(c.get('aligned_visible_rect_screenshot')) for p in row['parents'] for c in p['cells'])
        if admitted and comparison['export_cells']!=aligned_count:
            raise ValueError(f'CSV and accepted geometry differ: {tid}')
        if not admitted and comparison['export_cells']:
            raise ValueError(f'non-admitted cells leaked into CSV: {tid}')
        counts=[p['count'] for p in ref['measurement'].get('cell_parents',[])]
        # Preserve the current parent grain explicitly; never equate summed counts
        # when an unexpected split/merge changes what a parent denotes.
        if ref['typed_top_count']>1 or len(counts)>1 or len(row['parents'])>1:raise ValueError(f'new multiple-parent grain: {tid}')
        top=ref['typed_top_count']>0 or bool(counts)
        presence='present' if top else ('absent' if row['diagnostic_outcome']=='absent' and ref['cell_status']=='absent' else 'unresolved')
        match=bool(admitted and comparison['cell_status']=='scored' and comparison['cell_count_agree'])
        visible=[c for p in row['parents'] for c in p['cells'] if c.get('visible_rect_screenshot')]
        ledger.append({'trial_id':tid,'participant':tid.split('-')[0],'analysis_eligible':not excluded,'top_comparison':top,'top_presence':presence,
                       'candidate_outcome':row['diagnostic_outcome'],'legacy_status':ref['cell_status'],
                       'reference_count':ref.get('dom_cells'),'legacy_count':ref.get('export_cells'),
                       'candidate_count':comparison['export_cells'] if admitted else 0,
                       'legacy_match':bool(ref['cell_status']=='scored' and ref['cell_count_agree']),
                       'candidate_match':match,'candidate_audit_status':comparison['cell_status'],
                       'candidate_audit_issues':comparison['cell_issues'],
                       'large_vertical_correction':bool(admitted and any(abs(p.get('screenshot_registration',{}).get('dy') or 0)>3 for p in row['parents'])),
                       'has_clipped_card':any(c.get('visible_fraction',1)<.999 for c in visible),
                       'reasons':sorted(set([issue for p in row['parents'] for issue in p['issues']]+[p['screenshot_registration']['reason'] for p in row['parents'] if p.get('screenshot_registration',{}).get('reason')]))})
    eligible=[r for r in ledger if r['analysis_eligible']]
    top=[r for r in eligible if r['top_comparison']]
    def tally(rows):
        return {'trials':len(rows),'legacy_match':sum(r['legacy_match'] for r in rows),'candidate_match':sum(r['candidate_match'] for r in rows),
                'legacy_short':sum(r['legacy_count']<r['reference_count'] for r in rows if r['legacy_status']=='scored'),
                'legacy_over':sum(r['legacy_count']>r['reference_count'] for r in rows if r['legacy_status']=='scored'),
                'candidate_cards':sum(r['candidate_count'] for r in rows),'reference_cards':sum(r['reference_count'] or 0 for r in rows),
                'large_vertical_corrections':sum(r['large_vertical_correction'] for r in rows),
                'candidate_outcomes':dict(collections.Counter(r['candidate_outcome'] for r in rows))}
    summary={'requested_trials':len(ledger),'excluded_trials':len(ledger)-len(eligible),'eligible_trials':len(eligible),
             'eligible_without_top':sum(r['top_presence']=='absent' for r in eligible),
             'eligible_unresolved_top_presence':sum(r['top_presence']=='unresolved' for r in eligible),'eligible_top':tally(top),
             'excluded_top':tally([r for r in ledger if not r['analysis_eligible'] and r['top_comparison']]),
             'eligible_top_with_clipped_card':tally([r for r in top if r['has_clipped_card']]),
             'by_card_count':{str(k):tally([r for r in top if r['reference_count']==k]) for k in sorted(set(r['reference_count'] for r in top))},
             'by_participant':{k:tally([r for r in top if r['participant']==k]) for k in sorted(set(r['participant'] for r in top))}}
    return {'schema':'allserp-carousel-corpus-comparison-v1','regime':'LAB','rank_type':'typed parent / candidate top cells',
            'metric':'per-top-parent count agreement; registration is screenshot border support, not semantic accuracy',
            'summary':summary,'trials':ledger}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True)
    ap.add_argument('--candidate-csv',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    candidate=json.loads(args.candidate.read_text());reference=json.loads(args.reference.read_text())
    if candidate['candidate_csv_sha256']!=digest(args.candidate_csv):raise ValueError('candidate CSV hash mismatch')
    result=reconcile(candidate,reference,audit.cellsplit_inventory(args.candidate_csv))
    result['inputs']={k:{'path':str(p),'sha256':digest(p)} for k,p in [('candidate_report',args.candidate),('reference_report',args.reference),('candidate_csv',args.candidate_csv),('summarizer',Path(__file__))]}
    result['candidate_manifest']=candidate['manifest'];result['reference_manifest']=reference['manifest']
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result['summary'].items() if not k.startswith('by_')},indent=2))

if __name__=='__main__':main()
