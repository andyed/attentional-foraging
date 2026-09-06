"""Candidate top-carousel card extraction; does not replace the released cellsplit.

python scripts/carousel_dom.py --out /tmp/carousel-review
python scripts/carousel_dom.py --trials p005-b2-t1 p004-b5-t7 --out /tmp/carousel-review

Boxes describe the captured layout in document CSS pixels and screenshot pixels.
Visibility means intersection with horizontal viewport and ancestor overflow clips,
not gaze exposure or visibility throughout a trial. No midpoint/gap expansion.
"""
from __future__ import annotations
import argparse
import csv
import asyncio
import hashlib
import json
import os
import platform
import xml.etree.ElementTree as ET
from pathlib import Path
from importlib.metadata import version

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

ROOT = Path(os.environ.get('AF_ROOT', Path(__file__).resolve().parents[1]))
FIXTURES = Path(__file__).with_name('fixtures') / 'carousel_dom_cases.json'
SCHEMA = 'allserp-carousel-dom-candidate-v2'
EXTRACT_JS = r"""() => {
  const rect = el => { const r=el.getBoundingClientRect(); return {x:r.x+scrollX,y:r.y+scrollY,w:r.width,h:r.height}; };
  const area = r => r ? r.w*r.h : 0;
  const path = el => {
    const parts=[];
    for (let p=el;p && p.nodeType===1;p=p.parentElement) {
      const siblings=p.parentElement ? [...p.parentElement.children].filter(s=>s.tagName===p.tagName) : [p];
      parts.unshift(p.tagName.toLowerCase()+':nth-of-type('+(siblings.indexOf(p)+1)+')');
    }
    return parts.join(' > ');
  };
  const visible = el => {
    const raw=rect(el); let l=Math.max(0,raw.x),r=Math.min(document.documentElement.clientWidth,raw.x+raw.w),t=raw.y,b=raw.y+raw.h;
    const issues=[];
    for(let p=el;p;p=p.parentElement) {
      const s=getComputedStyle(p);
      if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0) return {box:null,issues};
      if(s.clipPath!=='none') issues.push('unsupported_clip_path');
      if(p===el) continue;
      const q=rect(p),sx=p.offsetWidth ? q.w/p.offsetWidth : 1,sy=p.offsetHeight ? q.h/p.offsetHeight : 1;
      const x=q.x+p.clientLeft*sx,y=q.y+p.clientTop*sy;
      if(['hidden','clip','auto','scroll'].includes(s.overflowX)){ l=Math.max(l,x);r=Math.min(r,x+p.clientWidth*sx); }
      if(['hidden','clip','auto','scroll'].includes(s.overflowY)){ t=Math.max(t,y);b=Math.min(b,y+p.clientHeight*sy); }
    }
    return {box:r>l && b>t ? {x:l,y:t,w:r-l,h:b-t} : null,issues};
  };
  const parents=[...document.querySelectorAll('.commercial-unit-desktop-top')].map(parent=>{
    const issues=[],handle=path(parent),v=visible(parent),ids=new Set(),nonProductUnits=[];
    const cells=[...parent.querySelectorAll('.pla-unit')].filter(c=>c.closest('.commercial-unit-desktop-top')===parent).filter(card=>{
      // Saved Google strips end with a comparison-service directory, not a product.
      if(card.querySelector('.CAdYob') && !card.querySelector('[id^=vplaurlg], img')) {
        nonProductUnits.push({dom_handle:path(card),reason:'comparison_service_directory',raw_rect:rect(card),visible_rect:visible(card).box});return false;
      }
      return true;
    }).map((card,order)=>{
      const anchors=[...card.querySelectorAll('[id^="vplaurlg"]')].filter(a=>/^vplaurlg\d+$/.test(a.id));
      const cardIds=[...new Set(anchors.map(a=>a.id))],raw=rect(card),vis=visible(card);
      let identity=cardIds.length===1 ? cardIds[0] : null;
      if(!identity) issues.push('missing_or_ambiguous_card_identity');
      if(identity && ids.has(identity)) issues.push('duplicate_card_identity');
      ids.add(identity);
      issues.push(...vis.issues);
      return {card_id:identity,dom_handle:path(card),dom_order:order,raw_rect:raw,visible_rect:vis.box,
        visible_fraction:area(raw)>0 ? area(vis.box)/area(raw) : 0,visible_index:null};
    });
    const productLinks=[...parent.querySelectorAll('[id^="vplaurlg"]')].filter(a=>/^vplaurlg\d+$/.test(a.id));
    if(productLinks.some(a=>!a.closest('.pla-unit') || a.closest('.pla-unit').closest('.commercial-unit-desktop-top')!==parent)) issues.push('unsupported_card_container');
    if(!cells.length) issues.push('no_supported_cards');
    const exposed=cells.filter(c=>c.visible_rect).sort((a,b)=>a.visible_rect.x-b.visible_rect.x);
    exposed.forEach((c,i)=>c.visible_index=i);
    for(let i=1;i<exposed.length;i++) {
      const a=exposed[i-1].visible_rect,b=exposed[i].visible_rect;
      if(a.x+a.w>b.x+1 && Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y)) issues.push('overlapping_visible_cards');
    }
    issues.push(...v.issues);
    return {dom_handle:handle,raw_rect:rect(parent),visible_rect:v.box,cells,non_product_units:nonProductUnits,issues:[...new Set(issues)]};
  });
  const outside=[...document.querySelectorAll('[id^="vplaurlg"]')].filter(a=>/^vplaurlg\d+$/.test(a.id) && !a.closest('.commercial-unit-desktop-top, .commercial-unit-desktop-rhs, #rhs')).length;
  return {parents,unscoped_product_links:outside,document_width:document.documentElement.scrollWidth};
}"""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scale_rect(rect, rx, ry):
    return {k: round(rect[k]*(rx if k in ('x', 'w') else ry), 4) for k in rect} if rect else None


def intersection(a, b):
    if not a or not b:
        return 0.0
    return max(0, min(a['x']+a['w'], b['x']+b['w'])-max(a['x'], b['x'])) * max(0, min(a['y']+a['h'], b['y']+b['h'])-max(a['y'], b['y']))


def bind_parents(result, typed, rx, ry):
    """Bind only uniquely overlapping parents; preserve ad_only's null html_handle.

    Ad-only dd_top parents have no HTML identity in current typed maps. Keep their
    position plus source hash, and separately record the measured DOM handle.
    At least half the visible DOM parent must overlap exactly one typed AOI; this is a binding check, not a boundary-fidelity score.
    Ambiguity/unmatched parents remain in the report, never guessed or dropped.
    """
    candidates=[a for a in typed if a.get('type')=='dd_top' and a.get('position', -1)>=0]
    claimed={}
    for p in result['parents']:
        shot=scale_rect(p['visible_rect'], rx, ry)
        p['rendered_visible_rect_screenshot']=shot
        matches=[]
        for a in candidates:
            box={'x':a['x'],'y':a['y'],'w':a['width'],'h':a['height']}
            if shot and intersection(shot,box)/max(shot['w']*shot['h'],1)>=0.5:
                matches.append(a)
        p['typed_position']=matches[0]['position'] if len(matches)==1 else None
        p['typed_rect_screenshot']={k:matches[0][v] for k,v in [('x','x'),('y','y'),('w','width'),('h','height')]} if len(matches)==1 else None
        p['typed_html_handle']=matches[0].get('html_handle') if len(matches)==1 else None
        if len(matches)!=1:
            p['issues'].append('unmatched_typed_parent' if not matches else 'ambiguous_typed_parent')
        else:
            claimed.setdefault(p['typed_position'],[]).append(p)
        for c in p['cells']:
            c['raw_rect_screenshot']=scale_rect(c['raw_rect'],rx,ry)
            c['visible_rect_screenshot']=scale_rect(c['visible_rect'],rx,ry)
    for matched in claimed.values():
        if len(matched)>1:
            for p in matched:
                p['issues'].append('duplicate_typed_parent_claim')
    result['unmatched_typed_positions']=[a['position'] for a in candidates if a['position'] not in claimed]
    result['status']='unresolved' if result['unmatched_typed_positions'] or result['unscoped_product_links'] or any(p['issues'] for p in result['parents']) else 'scored'
    return result


async def extract_trial(page, tid, root=ROOT):
    base={'trial_id':tid,'status':'unresolved','parents':[]}
    source=root/'AdSERP/data/serps-cached'/f'{tid}.html'
    if not source.exists():
        source=root/'AdSERP/data/serps'/f'{tid}.html'
    shot=root/'AdSERP/data/full-page-screenshots'/f'{tid}.png'
    meta=root/'AdSERP/data/trial-metadata'/f'{tid}.xml'
    typed_path=root/'data/aoi-typed'/f'{tid}.json'
    try:
        metadata=ET.parse(meta)
        dw,dh=map(int, metadata.find('.//document').text.split('x'))
        ww,wh=map(int, metadata.find('.//window').text.split('x'))
        with Image.open(shot) as im:
            sw,sh=im.size
        if min(dw,dh,ww,wh,sw,sh)<=0:
            raise ValueError('nonpositive dimensions')
        # The screenshot spans the recorded WINDOW, including scrollbar space.
        # Dividing by document width inflates X (~9px by the fifth card in the
        # golden cases). Keep both factors explicit; this candidate does not
        # silently change the shared loader or the historical audit's AOI metric.
        rx,ry=sw/ww,sh/dh
        typed=json.loads(typed_path.read_text())
        provenance={k:{'path':str(p.relative_to(root)),'sha256':digest(p)} for k,p in [('html',source),('screenshot',shot),('metadata',meta),('typed',typed_path)]}
        await page.goto(source.as_uri(),wait_until='load',timeout=20000)
        await page.evaluate('document.fonts.ready')
        data=await page.evaluate(EXTRACT_JS)
        base.update(bind_parents(data,typed,rx,ry),ratio_x=rx,ratio_y=ry,legacy_document_width_ratio_x=sw/dw,
                    coordinate_model='screenshot_width/window_width; screenshot_height/document_height',inputs=provenance)
    except Exception as e:
        base['error']=f'{type(e).__name__}: {e}'
    return base


def check_fixture(row, case, geometry='visible_rect_screenshot'):
    """Independent screenshot annotations are fixed before an extraction run."""
    errors=[]
    if geometry=='aligned_visible_rect_screenshot' and row.get('registration_status')!='accepted':
        errors.append('unresolved_registration')
    visible=[c for p in row['parents'] for c in sorted((c for c in p['cells'] if c['visible_rect']),key=lambda c:c['visible_index'])]
    if row.get('inputs',{}).get('screenshot',{}).get('sha256') != case['screenshot_sha256']:
        errors.append('screenshot_hash')
    if row['status']!='scored':
        errors.append('unresolved_extraction')
    if len(visible)!=case['visible_count']:
        errors.append('visible_count')
    expected=case.get('rects_screenshot',[])
    for i,(cell,box) in enumerate(zip(visible,expected)):
        got=cell.get(geometry)
        if got is None:
            errors.append(f'card_{i}_missing_geometry')
            continue
        # Endpoints avoid a width error cancelling a shifted left edge.
        actual=[got['x'],got['y'],got['x']+got['w'],got['y']+got['h']]
        if any(abs(x-y)>case['tolerance_px'] for x,y in zip(actual,box)):
            errors.append(f'card_{i}_boundary')
    if len(expected)!=len(visible):
        errors.append('annotation_count')
    return errors


def write_overlay(row, root, dest, geometry='visible_rect_screenshot'):
    if not row['parents']:
        return
    shot=root/'AdSERP/data/full-page-screenshots'/f"{row['trial_id']}.png"
    with Image.open(shot) as im:
        im=im.convert('RGB')
    draw=ImageDraw.Draw(im)
    boxes=[]
    for p in row['parents']:
        for c in p['cells']:
            b=c.get(geometry)
            if not b:
                continue
            xy=(b['x'],b['y'],b['x']+b['w'],b['y']+b['h']);boxes.append(xy)
            draw.rectangle(xy,outline='#de1965',width=2)
            draw.text((b['x']+4,b['y']+4),str(c['visible_index']),fill='#de1965',stroke_width=1,stroke_fill='white')
    if boxes:
        crop=(max(0,int(min(b[0] for b in boxes))-12),max(0,int(min(b[1] for b in boxes))-32),min(im.width,int(max(b[2] for b in boxes))+12),min(im.height,int(max(b[3] for b in boxes))+20))
        im.crop(crop).save(dest)


def write_candidate_csv(rows, path, registered=False):
    """Audit adapter only, not the released multi-flavor enrichment CSV.

    Only accepted rows get cells. Every requested parent remains represented so
    a rejected subdivision stays a zero-cell comparison, never disappears.
    Parent bounds come unchanged from the tight typed source. Raw/registered
    geometry choices are explicit; no old cells or gaps are silently filled in.
    """
    fields=['trial_id','role','parent_etype','main_axis','parent_rank','cell_index',
            'left_x','top_y','right_x','bottom_y','n_cells','card_id','dom_handle','geometry_source']
    geometry='aligned_visible_rect_screenshot' if registered else 'visible_rect_screenshot'
    with path.open('w',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader()
        for row in rows:
            admitted=row['status']=='scored' and (not registered or row.get('registration_status')=='accepted')
            for p in row['parents']:
                b=p.get('typed_rect_screenshot')
                if b is None:
                    continue
                cells=[c for c in p['cells'] if c.get(geometry)] if admitted else []
                base={'trial_id':row['trial_id'],'parent_etype':'dd_top','main_axis':True,
                      'parent_rank':p['typed_position'],'n_cells':len(cells)}
                def coordinates(b):
                    return {'left_x':b['x'],'top_y':b['y'],'right_x':b['x']+b['w'],'bottom_y':b['y']+b['h']}
                writer.writerow(dict(base,role='parent',**coordinates(b),geometry_source='typed_parent_unchanged'))
                for c in cells:
                    writer.writerow(dict(base,role='cell',cell_index=c['visible_index'],card_id=c['card_id'],
                                         dom_handle=c['dom_handle'],**coordinates(c[geometry]),
                                         geometry_source='dom_screenshot_registered' if registered else 'dom_rendered'))


async def run(args):
    manifest=json.loads(args.fixtures.read_text())
    cases={c['trial_id']:c for c in manifest['cases']}
    tids=(json.loads(args.trials_file.read_text()) if args.trials_file else args.trials) or list(cases)
    if len(tids)!=len(set(tids)) or not all(isinstance(t,str) for t in tids):
        raise ValueError('Trial list must contain unique string identifiers')
    if args.register_screenshot:
        from carousel_screenshot import register_trial, PARAMETERS
    args.out.mkdir(parents=True,exist_ok=True)
    rows=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        for tid in tids:
            # Fresh context prevents one trial's layout/storage state leaking to another.
            context=await browser.new_context(viewport={'width':1389,'height':1024})
            await context.route('http://**/*',lambda route:route.abort())
            await context.route('https://**/*',lambda route:route.abort())
            page=await context.new_page()
            row=await extract_trial(page,tid,args.root)
            if args.register_screenshot:
                register_trial(row,args.root/'AdSERP/data/full-page-screenshots'/f'{tid}.png')
            if tid in cases:
                if args.register_screenshot:
                    row['raw_fixture_errors']=check_fixture(row,cases[tid])
                geometry='aligned_visible_rect_screenshot' if args.register_screenshot else 'visible_rect_screenshot'
                row['fixture_errors']=check_fixture(row,cases[tid],geometry)
                expected=cases[tid].get('expected_registered_outcome','accept') if args.register_screenshot else cases[tid].get('expected_outcome','accept')
                row['fixture_expected_outcome']=expected
                row['fixture_pass']=(not row['fixture_errors']) if expected=='accept' else (row['status']=='scored' and bool(row['fixture_errors']) and all(e.endswith('_boundary') for e in row['fixture_errors']))
                if row['fixture_errors']:
                    row['status']='screenshot_mismatch'
            rows.append(row)
            write_overlay(row,args.root,args.out/f'{tid}.png',
                          'aligned_visible_rect_screenshot' if args.register_screenshot else 'visible_rect_screenshot')
            await context.close()
            if len(rows)%20==0:
                print(f'{len(rows)}/{len(tids)} trials',flush=True)
        browser_version=browser.version
        await browser.close()
    report={'schema':SCHEMA,'regime':'LAB','flavor':'typed parent / DOM candidate cells; not released cellsplit','source_sha256':digest(__file__),
            'fixture_sha256':digest(args.fixtures),'python':platform.python_version(),'playwright':version('playwright'),'chromium':browser_version,
            'viewport':{'width':1389,'height':1024},'network':'blocked','visibility':'captured horizontal viewport and ancestor overflow clips; no temporal exposure inference',
            'summary':{'trials':len(rows),'scored':sum(r['status']=='scored' for r in rows),'fixture_trials':sum('fixture_errors' in r for r in rows),
                       'fixture_pass':sum(r.get('fixture_pass',False) for r in rows),
                       'accepted_fixtures':sum(r.get('fixture_pass',False) and r.get('fixture_expected_outcome')=='accept' for r in rows),
                       'expected_rejections':sum(r.get('fixture_pass',False) and r.get('fixture_expected_outcome')!='accept' for r in rows)},'trials':rows}
    if args.register_screenshot:
        report['registration']={'source_sha256':digest(Path(__file__).with_name('carousel_screenshot.py')),
                                'parameters':PARAMETERS,'numpy':version('numpy'),'scipy':version('scipy'),
                                'geometry':'single vertical translation, original screenshot strokes; no content identity validation'}
        report['summary']['registration_accepted']=sum(r.get('registration_status')=='accepted' for r in rows)
        report['summary']['large_vertical_corrections']=sum(any(abs(p.get('screenshot_registration',{}).get('dy') or 0)>3 for p in r['parents']) for r in rows)
    write_candidate_csv(rows,args.out/'candidate-cells.csv',args.register_screenshot)
    report['candidate_csv_sha256']=digest(args.out/'candidate-cells.csv')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary']))
    return 1 if any((not r['fixture_pass'] if 'fixture_pass' in r else r['status']!='scored') or
                    (args.register_screenshot and r.get('registration_status')!='accepted') for r in rows) else 0


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--fixtures',type=Path,default=FIXTURES)
    selection=ap.add_mutually_exclusive_group()
    selection.add_argument('--trials',nargs='+')
    selection.add_argument('--trials-file',type=Path,help='JSON list of trial IDs, for fixed-cohort comparisons')
    ap.add_argument('--register-screenshot',action='store_true',help='Require original screenshot border evidence before emitting aligned cards')
    ap.add_argument('--out',type=Path,required=True)
    return asyncio.run(run(ap.parse_args()))


if __name__=='__main__':
    raise SystemExit(main())
