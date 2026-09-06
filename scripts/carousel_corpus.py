"""Resumable corpus measurement using the frozen candidate implementation.
All metadata trials stay in the ledger; alignment exclusions are measured but
never admitted. Absent top carousels are distinct from failed extraction.
"""
import argparse, asyncio, collections, copy, json, os, platform, time
from pathlib import Path
from importlib.metadata import version
from playwright.async_api import async_playwright
from carousel_dom import extract_trial, digest, write_candidate_csv
from carousel_screenshot import register_trial, PARAMETERS

async def run(args):
    root, out = args.root.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'trials').mkdir(exist_ok=True)
    tids = sorted(p.stem for p in (root/'AdSERP/data/trial-metadata').glob('p*.xml'))
    if args.trials_file: tids=json.loads(args.trials_file.read_text())
    if not tids or len(tids)!=len(set(tids)): raise ValueError('invalid trial inventory')
    exclusions=root/'data/aoi-typed/alignment-exclusions.json'
    excluded=set(json.loads(exclusions.read_text())['tids'])
    here=Path(__file__).parent
    sources={p.name:digest(p) for p in [Path(__file__),here/'carousel_dom.py',here/'carousel_screenshot.py']}
    manifest={'schema':'allserp-carousel-corpus-v1','regime':'LAB','rank_type':'typed parents / candidate top cells',
              'root':str(root),'trial_ids':tids,'sources':sources,'exclusions_sha256':digest(exclusions),
              'alignment_excluded_ids':sorted(excluded),'parameters':PARAMETERS,
              'viewport':{'width':1389,'height':1024},'network':'blocked',
              'python':platform.python_version(),'versions':{k:version(k) for k in ['playwright','numpy','scipy','pillow']}}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        manifest['chromium']=browser.version
        manifest_path=out/'manifest.json'
        if manifest_path.exists() and json.loads(manifest_path.read_text())!=manifest:
            raise ValueError('refusing resume with changed sources/cohort/runtime/exclusions')
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        queue=asyncio.Queue(); completed=[]; started=time.monotonic()
        for tid in tids:
            dest=out/'trials'/f'{tid}.json'
            if dest.exists():
                row=json.loads(dest.read_text())
                if row['trial_id']!=tid or any(digest(root/v['path'])!=v['sha256'] for v in row.get('inputs',{}).values()):
                    raise ValueError(f'changed checkpoint inputs: {tid}')
                completed.append(row)
            else: queue.put_nowait(tid)
        async def worker():
            while not queue.empty():
                tid=queue.get_nowait(); context=None
                try:
                    context=await browser.new_context(viewport=manifest['viewport'])
                    await context.route('http://**/*',lambda route:route.abort())
                    await context.route('https://**/*',lambda route:route.abort())
                    page=await context.new_page()
                    row=await asyncio.wait_for(extract_trial(page,tid,root),timeout=45)
                    if row['status']=='scored' and not row['parents']:
                        row['diagnostic_outcome']='absent';row['registration_status']='not_applicable'
                    elif row['status']=='scored':
                        await asyncio.to_thread(register_trial,row,root/'AdSERP/data/full-page-screenshots'/f'{tid}.png')
                        row['diagnostic_outcome']=row['registration_status']
                    else:
                        row['diagnostic_outcome']='unresolved';row['registration_status']='not_attempted'
                except Exception as e:
                    row={'trial_id':tid,'status':'unresolved','parents':[],'diagnostic_outcome':'unresolved','error':f'{type(e).__name__}: {e}'}
                finally:
                    if context: await context.close()
                row['analysis_eligible']=tid not in excluded
                row['corpus_outcome']=row['diagnostic_outcome'] if row['analysis_eligible'] else 'alignment_excluded'
                dest=out/'trials'/f'{tid}.json'; temp=dest.with_suffix('.tmp')
                temp.write_text(json.dumps(row,separators=(',',':'))+'\n');temp.replace(dest)
                completed.append(row)
                if len(completed)%50==0 or queue.empty():
                    print(json.dumps({'done':len(completed),'total':len(tids),'elapsed_s':round(time.monotonic()-started),
                                      'outcomes':dict(collections.Counter(r['corpus_outcome'] for r in completed))}),flush=True)
                queue.task_done()
        await asyncio.gather(*(worker() for _ in range(args.workers)))
        await browser.close()
    rows=sorted(completed,key=lambda r:r['trial_id'])
    eligible=[r for r in rows if r['analysis_eligible']]
    summary={'trials':len(rows),'analysis_eligible':len(eligible),
             'outcomes':dict(collections.Counter(r['corpus_outcome'] for r in rows)),
             'diagnostic_outcomes_including_excluded':dict(collections.Counter(r['diagnostic_outcome'] for r in rows)),
             'eligible_accepted_cards':sum(sum(bool(c.get('aligned_visible_rect_screenshot')) for p in r['parents'] for c in p['cells']) for r in eligible if r['diagnostic_outcome']=='accepted'),
             'eligible_accepted_large_corrections':sum(any(abs(p.get('screenshot_registration',{}).get('dy') or 0)>3 for p in r['parents']) for r in eligible if r['diagnostic_outcome']=='accepted'),
             'eligible_multiple_dom_parents':sum(len(r['parents'])>1 for r in eligible),
             'rejection_reasons':dict(collections.Counter(p.get('screenshot_registration',{}).get('reason') for r in eligible if r['diagnostic_outcome']=='rejected' for p in r['parents'])),
             'unresolved_issues':dict(collections.Counter(issue for r in eligible if r['diagnostic_outcome']=='unresolved' for p in r['parents'] for issue in p['issues']))}
    write_candidate_csv(eligible,out/'candidate-cells.csv',registered=True)
    report={'manifest':manifest,'summary':summary,'candidate_csv_sha256':digest(out/'candidate-cells.csv'),'trials':rows}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=4);ap.add_argument('--trials-file',type=Path)
    asyncio.run(run(ap.parse_args()))
