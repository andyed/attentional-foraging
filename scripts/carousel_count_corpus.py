"""Independent numbered-link count audit, retaining every requested trial.
Uses the canonical auditor JS/compare_cells unchanged. No candidate extraction
or screenshot-registration code participates in the count measurement.
"""
import argparse, asyncio, collections, hashlib, json, platform, time
from pathlib import Path
from importlib.metadata import version
from playwright.async_api import async_playwright
import aoi_fidelity as audit

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

async def run(args):
    root=Path(audit.ROOT);out=args.out;out.mkdir(parents=True,exist_ok=True);(out/'trials').mkdir(exist_ok=True)
    tids=sorted(p.stem for p in (root/'AdSERP/data/trial-metadata').glob('p*.xml'))
    excluded=set(json.loads((root/'data/aoi-typed/alignment-exclusions.json').read_text())['tids'])
    legacy=audit.cellsplit_inventory();q=asyncio.Queue();done=[];start=time.monotonic()
    manifest={'schema':'allserp-independent-count-corpus-v1','trial_ids':tids,'sources':{Path(__file__).name:digest(__file__),'aoi_fidelity.py':digest(audit.__file__)},
              'legacy_csv_sha256':digest(audit.CELLSPLIT),'exclusions_sha256':digest(root/'data/aoi-typed/alignment-exclusions.json'),
              'python':platform.python_version(),'playwright':version('playwright'),'viewport':{'width':audit.CAPTURE_VIEWPORT,'height':1024},'network':'blocked',
              'measurement':'canonical independent numbered-link JS, after document.fonts.ready; count only'}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch();manifest['chromium']=browser.version
        mp=out/'manifest.json'
        if mp.exists() and json.loads(mp.read_text())!=manifest: raise ValueError('changed run manifest')
        mp.write_text(json.dumps(manifest,indent=2)+'\n')
        for tid in tids:
            dest=out/'trials'/f'{tid}.json'
            if dest.exists():
                row=json.loads(dest.read_text())
                if row['tid']!=tid or any(digest(root/v['path'])!=v['sha256'] for v in row.get('inputs',{}).values()): raise ValueError('changed checkpoint')
                done.append(row)
            else: q.put_nowait(tid)
        async def worker():
            while not q.empty():
                tid=q.get_nowait();ctx=None
                row={'tid':tid,'analysis_eligible':tid not in excluded,'cell_status':'unresolved','cell_issues':[]}
                try:
                    paths={'html':root/'AdSERP/data/serps-cached'/f'{tid}.html','typed':audit.TYPED/f'{tid}.json','metadata':audit.META/f'{tid}.xml','screenshot':audit.SHOTS/f'{tid}.png'}
                    if not paths['html'].exists():paths['html']=audit.SERPS/f'{tid}.html'
                    row['inputs']={k:{'path':str(p.relative_to(root)),'sha256':digest(p)} for k,p in paths.items()}
                    row['typed_top_count']=sum(a.get('type')=='dd_top' and a.get('position',-1)>=0 for a in json.loads(paths['typed'].read_text()))
                    ctx=await browser.new_context(viewport=manifest['viewport'])
                    await ctx.route('http://**/*',lambda r:r.abort());await ctx.route('https://**/*',lambda r:r.abort())
                    page=await ctx.new_page()
                    await page.goto(paths['html'].as_uri(),wait_until='load',timeout=20000)
                    await asyncio.wait_for(page.evaluate('document.fonts.ready'),timeout=25)
                    row['measurement']=await page.evaluate(audit.JS,{'cards':{},'mainMaxX':audit.MAIN_MAX_X,'clickXpath':None})
                    row['ratio_x'],row['ratio_y']=audit.ratios(tid)
                    row.update(audit.compare_cells(row['measurement'],legacy.get(tid),row['ratio_x'],row['ratio_y'],row['typed_top_count']))
                except Exception as e:row.update(error=f'{type(e).__name__}: {e}',cell_issues=['measurement_failed'])
                finally:
                    if ctx:await ctx.close()
                (out/'trials'/f'{tid}.json').write_text(json.dumps(row,separators=(',',':'))+'\n');done.append(row)
                if len(done)%100==0: print(json.dumps({'done':len(done),'total':len(tids),'elapsed_s':round(time.monotonic()-start)}),flush=True)
                q.task_done()
        await asyncio.gather(*(worker() for _ in range(args.workers)));await browser.close()
    rows=sorted(done,key=lambda r:r['tid'])
    summary={'all':audit.cell_summary(rows),'eligible':audit.cell_summary([r for r in rows if r['analysis_eligible']])}
    (out/'report.json').write_text(json.dumps({'manifest':manifest,'summary':summary,'trials':rows},indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=4)
    asyncio.run(run(ap.parse_args()))
