"""Conservative screenshot registration for the saved Google product-card template.

Detects card strokes in the ORIGINAL screenshot independently of DOM counts or
old AOIs, then permits one shared vertical translation per carousel. This is a
geometry check, not a product-content/semantic identity validation. Unknown
border styles, ambiguous matches and inconsistent layouts fail closed.
"""
from __future__ import annotations
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

PARAMETERS = {
    'stroke_rgb': [218, 220, 224], 'stroke_tolerance': 3,
    'corner_search_px': 14, 'straight_run_px': 40,
    'minimum_card_height_px': 60, 'maximum_card_height_px': 700,
    'maximum_vertical_shift_px': 80, 'shape_tolerance_px': 3,
    'translation_spread_px': 2, 'minimum_anchor_fraction': .6,
    'minimum_horizontal_support': .85, 'minimum_vertical_support': .70,
}


def stroke_mask(screenshot):
    with Image.open(screenshot) as im:
        pixels = np.asarray(im.convert('RGB')).astype('int16')
    return np.max(np.abs(pixels - PARAMETERS['stroke_rgb']), axis=2) <= PARAMETERS['stroke_tolerance']


def detect_outlines(mask):
    """Pair horizontal strokes with independently supported left/right edges.

    No DOM box, typed AOI, trial ID or expected card count is used here. The
    fixed color is template-specific; failure is explicit rather than inferred
    geometry on another template. Right-edge arrow occlusion can prevent a
    closed-outline anchor; registration still checks each visible card below.
    """
    horizontal = ndimage.binary_opening(mask, structure=np.ones((1, PARAMETERS['straight_run_px'])))
    labels, _ = ndimage.label(horizontal, np.ones((3, 3)))
    lines = []
    for sy, sx in ndimage.find_objects(labels):
        if 40 <= sx.stop-sx.start <= 650 and sy.stop-sy.start <= 3:
            lines.append((sx.start, sx.stop, (sy.start+sy.stop-1)//2))
    boxes = []
    for x1, x2, y1 in lines:
        for left, right, y2 in lines:
            if abs(left-x1)>2 or abs(right-x2)>2 or not 60 <= y2-y1 <= 700:
                continue
            def edge(lo, hi):
                lo, hi = max(0,lo), min(mask.shape[1],hi)
                scores = mask[y1+10:y2-10,lo:hi].mean(axis=0)
                i = int(np.argmax(scores))
                return lo+i, float(scores[i])
            l, ls = edge(x1-14,x1+1)
            r, rs = edge(x2-1,x2+14)
            if max(ls,rs) < PARAMETERS['minimum_vertical_support']:
                continue
            # A clipped outer edge can leave one side open. Keep that outline
            # for detecting omitted tail/leading cards, never as a registration anchor.
            closed=min(ls,rs)>=PARAMETERS['minimum_vertical_support']
            if ls<PARAMETERS['minimum_vertical_support']:
                l=x1-(r-(x2-1))
            if rs<PARAMETERS['minimum_vertical_support']:
                r=(x2-1)+(x1-l)
            if r-l<60:
                continue
            box = {'closed':closed,'x':l,'y':y1,'w':r-l+1,'h':y2-y1+1,'left_support':ls,'right_support':rs}
            if not any(max(abs(box[k]-b[k]) for k in ('x','y','w','h'))<3 for b in boxes):
                boxes.append(box)
    return sorted(boxes,key=lambda b:(b['y'],b['x']))


def border_support(mask, box):
    x, y = round(box['x']), round(box['y'])
    right, bottom = round(box['x']+box['w'])-1, round(box['y']+box['h'])-1
    if x<1 or y<1 or right>=mask.shape[1]-1 or bottom>=mask.shape[0]-1 or right-x<30 or bottom-y<30:
        return {'top':0.,'bottom':0.,'left':0.,'right':0.}
    # +/-1 permits subpixel rasterization; rounded corners are excluded.
    return {
        'top':float(mask[y-1:y+2,x+10:right-9].any(axis=0).mean()),
        'bottom':float(mask[bottom-1:bottom+2,x+10:right-9].any(axis=0).mean()),
        'left':float(mask[y+10:bottom-9,x-1:x+2].any(axis=1).mean()),
        'right':float(mask[y+10:bottom-9,right-1:right+2].any(axis=1).mean()),
    }


def register_parent(parent, mask, outlines):
    for cell in parent['cells']:
        cell.pop('aligned_visible_rect_screenshot',None)
    cells = [c for c in parent['cells'] if c['visible_rect_screenshot']]
    result = {'status':'rejected','reason':None,'anchors':[], 'dy':None,'card_checks':[]}
    if parent['issues'] or len(cells)<2:
        result['reason']='unresolved_parent_or_too_few_cards'
        return result
    used=set()
    for cell in cells:
        b=cell['visible_rect_screenshot']
        hits=[(i,o) for i,o in enumerate(outlines) if o.get('closed',True) and
              max(abs(o[k]-b[k]) for k in ('x','w','h')) <= PARAMETERS['shape_tolerance_px'] and
              abs(o['y']-b['y']) <= PARAMETERS['maximum_vertical_shift_px']]
        if len(hits)>1 or (hits and hits[0][0] in used):
            result['reason']='ambiguous_outline_match'
            return result
        if hits:
            i,o=hits[0];used.add(i)
            result['anchors'].append({'card_id':cell['card_id'],'outline':o,'dy':o['y']-b['y']})
    required=max(2,math.ceil(len(cells)*PARAMETERS['minimum_anchor_fraction']))
    if len(result['anchors'])<required:
        result['reason']='insufficient_outline_anchors'
        return result
    shifts=[a['dy'] for a in result['anchors']]
    if max(shifts)-min(shifts)>PARAMETERS['translation_spread_px']:
        result['reason']='inconsistent_card_offsets'
        return result
    dy=float(np.median(shifts));result['dy']=round(dy,4)
    aligned=[]
    for c in cells:
        b=dict(c['visible_rect_screenshot']);b['y']=round(b['y']+dy,4)
        supports=border_support(mask,b)
        passed=min(supports['top'],supports['bottom'])>=PARAMETERS['minimum_horizontal_support'] and max(supports['left'],supports['right'])>=PARAMETERS['minimum_vertical_support']
        result['card_checks'].append({'card_id':c['card_id'],'support':supports,'passed':passed})
        aligned.append((c,b))
    if not all(c['passed'] for c in result['card_checks']):
        result['reason']='visible_card_border_mismatch'
        return result
    # Extra supported outlines within the carousel row cannot be silently ignored.
    envelope=parent.get('rendered_visible_rect_screenshot')
    if not envelope:
        result['reason']='missing_parent_clip_extent'
        return result
    left=envelope['x'];right=envelope['x']+envelope['w']
    top=min(b['y'] for _,b in aligned);bottom=max(b['y']+b['h'] for _,b in aligned)
    for i,o in enumerate(outlines):
        clipped=dict(o,x=max(left,o['x']),w=max(0,min(right,o['x']+o['w'])-max(left,o['x'])))
        accounted=any(max(abs(clipped[k]-b[k]) for k in ('x','y','w','h'))<=3 for _,b in aligned)
        if not accounted and clipped['w']>1 and abs(o['y']-top)<=3 and abs(o['y']+o['h']-bottom)<=3:
            result['reason']='unmatched_screenshot_outline'
            return result
    for c,b in aligned:
        c['aligned_visible_rect_screenshot']=b
    result.update(status='accepted',reason=None)
    return result


def register_trial(row, screenshot):
    """Never admit a previously unresolved DOM extraction by fitting pixels."""
    for parent in row['parents']:
        parent.pop('screenshot_registration',None)
        for cell in parent['cells']:
            cell.pop('aligned_visible_rect_screenshot',None)
    if row['status']!='scored':
        row['registration_status']='rejected'
        return row
    mask=stroke_mask(screenshot);outlines=detect_outlines(mask)
    for p in row['parents']:
        p['screenshot_registration']=register_parent(p,mask,outlines)
    row['registration_status']='accepted' if row['parents'] and all(p['screenshot_registration']['status']=='accepted' for p in row['parents']) else 'rejected'
    return row
