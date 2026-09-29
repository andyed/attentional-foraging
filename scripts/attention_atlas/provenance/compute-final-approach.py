"""Target-relative gaze/cursor overlap; preserved legacy-table reproduction gate.

Writes only task artifacts. Primary: strict xy target membership, exact fixation
intervals, held cursor samples capped at 2 s. Sensitivity: 250 ms hold / y bands.
Approach rule adapted from approach_truncation_ablation to screenshot-space
native mousemove before the final press; same 50 px prominence / 100 px radius.
"""
from pathlib import Path
import os,sys,json,math,bisect,hashlib,datetime,csv
from collections import Counter,defaultdict
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
ROOT=Path('/Users/andyed/Documents/dev/attentional-foraging')
OUT=Path(__file__).parent/'gaze-cursor-atlas/final-approach'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'notebooks-v2'))
import data_loader as dl

def inside(x,y,c):return c['x']<=x<=c['x']+c['width'] and c['y']<=y<=c['y']+c['height']
def band(y,cards):
 for c in cards:
  if c['y']<=y<=c['y']+c['height']:return c
 return None
def onset(moves,cx,cy):
 d=np.array([math.hypot(x-cx,y-cy) for t,x,y in moves]);n=len(d)
 if n<3:return moves[0][0],'short_stream'
 suffix=np.empty(n);suffix[-1]=d[-1]
 for i in range(n-2,-1,-1):suffix[i]=min(d[i+1],suffix[i+1])
 for i in range(n-2,0,-1):
  if d[i]>=d[i-1] and d[i]>=d[i+1] and d[i]-suffix[i]>=50 and d[i]>=100:
   return moves[i][0],'local_max'
 ix=np.flatnonzero(d>=np.median(d))
 return moves[ix[-1]][0],'median_fallback'
def describe(c):
 total=sum(c.values());valid=total-c['unmatched'];off=c['gaze_on_cursor_off']+c['both_off']
 return {'milliseconds':dict(c),'total_s':total/1000,'matched_s':valid/1000,
  'unmatched_pct':100*c['unmatched']/total if total else None,
  'gaze_on_cursor_off_pct_matched':100*c['gaze_on_cursor_off']/valid if valid else None,
  'gaze_on_pct_when_cursor_off':100*c['gaze_on_cursor_off']/off if off else None,
  'shares_pct_matched':{k:100*c[k]/valid if valid else None for k in ['both_on','gaze_on_cursor_off','cursor_on_gaze_off','both_off']}}

prior=json.loads((ROOT/'scripts/output/gaze_cursor_divergence/summary.json').read_text())
stamp=json.loads((ROOT/'data/aoi-typed/substrate.json').read_text())
h=hashlib.sha256()
for p in sorted((ROOT/'data/aoi-typed').glob('p*.json')):h.update(p.name.encode());h.update(p.read_bytes())
assert h.hexdigest()[:16]==stamp['typed_maps_content_hash']
assert stamp['typed_maps_content_hash']==prior['provenance']['substrate']['typed_maps_content_hash']
excl=dl.typed_alignment_exclusions();counts=Counter();legacy=Counter();legacy_phases=defaultdict(Counter)
aggregate=defaultdict(Counter);participants=defaultdict(lambda:defaultdict(Counter));trial_rows=[]
rules=Counter();durations=[];raw_split=Counter()
for idx,tid in enumerate(dl.get_trial_ids()):
 if tid in excl:counts['alignment_excluded']+=1;continue
 cards=[c for c in dl.load_typed_aois(tid) if c.get('position',-1)>=0 and all(isinstance(c.get(k),(int,float)) and math.isfinite(c[k]) for k in ['x','y','width','height'])]
 if len(cards)<2:counts['fewer_than_two_aois']+=1;continue
 geo=dl.get_trial_geometry(tid);sx,sy=geo['ratio_x'],geo['ratio_y']
 events,_,clicks=dl.load_mouse_events(tid,space='document')
 if not clicks:counts['no_click']+=1;continue
 click=max(clicks,key=lambda c:c[0]);presses=[e for e in events if e[1]=='mousedown' and math.isfinite(e[0]) and e[0]<=click[0]]
 if not presses:counts['no_mousedown_for_final_click']+=1;continue
 press=max(presses,key=lambda e:e[0]);end=press[0];cutoff=end-500
 cx,cy=click[1]*sx,click[2]*sy;hits=[c for c in cards if inside(cx,cy,c)]
 if len(hits)!=1:counts['ambiguous_click' if hits else 'click_outside_main_boxes']+=1;continue
 target=hits[0];cards.sort(key=lambda c:c['position'])
 allmoves=[(t,x*sx,y*sy) for t,e,x,y in events if e=='mousemove' and t<end and all(math.isfinite(v) for v in [t,x,y])]
 oldmoves=[m for m in allmoves if m[0]<cutoff]
 if len(oldmoves)<2:counts['insufficient_prebuffer_mousemove']+=1;continue
 if any(b[0]<a[0] for a,b in zip(oldmoves,oldmoves[1:])):counts['nonmonotonic_mouse_time']+=1;continue
 fix=sorted([f for f in dl.load_fixations(tid) if all(math.isfinite(f[k]) for k in ['t','x','y','d'])],key=lambda f:f['t'])
 ft=[f['t'] for f in fix]
 start,rule=onset(allmoves,cx,cy)
 # Legacy table reproduced on precisely its own cursor-sample / +50 ms rule.
 for i,(t,x,y) in enumerate(oldmoves[:-1]):
  dt=min(oldmoves[i+1][0]-t,2000)
  if dt<=0:continue
  c=band(y,cards)
  if c is None or not inside(x,y,c):continue
  j=bisect.bisect_right(ft,t)-1
  g=fix[j] if j>=0 and t<fix[j]['t']+fix[j]['d']+50 else None
  gb=band(g['y'],cards) if g else None
  key='on_same' if gb and gb['position']==c['position'] else 'adjacent' if gb and abs(gb['position']-c['position'])==1 else 'other_aoi' if gb else 'off_or_none'
  legacy[key]+=dt
  raw_split['unmatched' if g is None else 'matched_off_band' if gb is None else 'matched_in_band']+=dt
  for phase,a,b in [('earlier',t,min(t+dt,start)),('approach',max(t,start),t+dt)]:
   if b>a:legacy_phases[phase][key]+=b-a
   if b>a and key in ['adjacent','other_aoi'] and gb['position']==target['position']:
    legacy_phases[phase]['different_result_gaze_on_click_target']+=b-a
 counts['included']+=1
 if any(b[0]<a[0] for a,b in zip(allmoves,allmoves[1:])):
  counts['primary_nonmonotonic_after_buffer']+=1;continue
 if not all(math.isfinite(v) for v in press[2:]) or not inside(press[2]*sx,press[3]*sy,target):
  counts['primary_press_target_mismatch']+=1;continue
 rules[rule]+=1;durations.append(end-start);pid=tid.split('-')[0]
 boundaries=sorted(set([start,cutoff]+[f['t'] for f in fix]+[f['t']+f['d'] for f in fix]))
 local=defaultdict(Counter)
 for i,(t,x,y) in enumerate(allmoves):
  nxt=allmoves[i+1][0] if i+1<len(allmoves) else end
  stop=min(nxt,t+2000,end)
  if stop<=t:continue
  points=[t]+boundaries[bisect.bisect_right(boundaries,t):bisect.bisect_left(boundaries,stop)]+[stop]
  if t<t+250<stop:points=sorted(set(points+[t+250]))
  cursor_on=inside(x,y,target)
  for a,b in zip(points,points[1:]):
   mid=(a+b)/2;dt=b-a;j=bisect.bisect_right(ft,mid)-1
   g=fix[j] if j>=0 and mid<fix[j]['t']+fix[j]['d'] else None
   phase='approach' if mid>=start else 'earlier'
   windows=['full']+(['buf500'] if mid<cutoff else ['last500'])
   for membership in ['xy','band_y']:
    gaze_on=(inside(g['x'],g['y'],target) if membership=='xy' else target['y']<=g['y']<=target['y']+target['height']) if g else False
    state='unmatched' if g is None else 'both_on' if gaze_on and cursor_on else 'gaze_on_cursor_off' if gaze_on else 'cursor_on_gaze_off' if cursor_on else 'both_off'
    for cap in [2000,250]:
     if a>=t+cap:continue
     for window in windows:
      key=f'{membership}|cap{cap}|{window}|{phase}'
      local[key][state]+=dt
 for key,c in local.items():aggregate[key].update(c);participants[pid][key].update(c)
 row={'trial_id':tid,'onset_rule':rule,'approach_ms':end-start,'press_ms':end,'onset_ms':start}
 for phase in ['earlier','approach']:
  c=local[f'xy|cap2000|full|{phase}'];d=describe(c)
  row[phase+'_matched_s']=d['matched_s'];row[phase+'_gaze_on_cursor_off_pct_matched']=d['gaze_on_cursor_off_pct_matched']
 trial_rows.append(row)
 if (idx+1)%250==0:print(f'processed {idx+1}; included {counts["included"]}',flush=True)

observed={k:legacy[k]/sum(legacy.values()) for k in prior['whitespace']['gaze_while_cursor_in_box']}
expected=prior['whitespace']['gaze_while_cursor_in_box']
maxdiff=max(abs(observed[k]-expected[k]) for k in expected)
assert counts['included']==prior['counts']['included'],counts
assert maxdiff<1e-10,(observed,expected,maxdiff)
results={k:describe(c) for k,c in aggregate.items()}
# Cluster bootstrap: resample participants and recompute pooled duration ratios.
rng=np.random.default_rng(20260927);pids=sorted(participants)
samples=rng.integers(0,len(pids),size=(4000,len(pids)))
for window in ['full','buf500']:
 vals={}
 for phase in ['earlier','approach']:
  key=f'xy|cap2000|{window}|{phase}'
  nums=np.array([participants[p][key]['gaze_on_cursor_off'] for p in pids])
  dens=np.array([sum(participants[p][key].values())-participants[p][key]['unmatched'] for p in pids])
  boots=100*nums[samples].sum(axis=1)/dens[samples].sum(axis=1)
  results[key]['participant_cluster_bootstrap_ci95_pct_matched']=np.percentile(boots,[2.5,97.5]).tolist()
  vals[phase]=boots
 results[f'xy|cap2000|{window}|approach_minus_earlier_ci95_pp']=np.percentile(vals['approach']-vals['earlier'],[2.5,97.5]).tolist()

def shares(c):
 den=sum(c[k] for k in ['on_same','adjacent','other_aoi','off_or_none'])
 valid=sum(c[k] for k in ['on_same','adjacent','other_aoi'])
 return {'interval_weight_s':den/1000,'same_pct_all':100*c['on_same']/den,
 'different_pct_classifiable':100*(c['adjacent']+c['other_aoi'])/valid,
 'different_result_gaze_on_click_target_s':c['different_result_gaze_on_click_target']/1000}
all_diff=legacy['adjacent']+legacy['other_aoi']
decomp={k:shares(v) for k,v in legacy_phases.items()}
decomp['approach_share_of_all_different_result_weight_pct']=100*(legacy_phases['approach']['adjacent']+legacy_phases['approach']['other_aoi'])/all_diff
decomp['approach_gaze_on_click_target_share_of_all_different_result_weight_pct']=100*legacy_phases['approach']['different_result_gaze_on_click_target']/all_diff
out={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'counts':dict(counts),'primary_trials':len(trial_rows),'participants':len(pids),
 'legacy_reproduction':{'max_absolute_share_difference':maxdiff,'shares':observed,'merged_category_split_pct_all_inbox':{k:100*v/sum(raw_split.values()) for k,v in raw_split.items()}},
 'legacy_table_phase_decomposition':decomp,'approach_rules':dict(rules),'approach_duration_ms_quantiles':np.percentile(durations,[25,50,75]).tolist(),
 'protocol':{'target':'final click strict xy AOI; final press must hit same AOI','approach':'last prepress native-mousemove distance local maximum, prominence >=50px and distance >=100px; otherwise latest sample >= median distance. Screenshot coordinates. Adapted from prior approach-truncation rule.',
 'time':'cursor held until next mousemove or press, maximum 2000ms; 250ms sensitivity. Exact temporal overlap with recorded fixation durations, no +50ms slack. Overlapping fixations use latest-starting fixation.',
 'denominator':'gaze-on-target/cursor-off-target duration divided by fixation-matched cursor-covered phase time; alternative conditional denominator is matched cursor-off-target time.',
 'membership':'primary strict xy target rectangle; band_y sensitivity uses gaze y band and strict xy cursor.',
 'phases':'earlier: first mousemove to approach onset; approach: onset to final press. full includes final 500ms; buf500 clips at press-500ms.',
 'limits':'geometric approach heuristic, not decision onset or causal proof. Held page-space cursor samples do not reconstruct scroll-induced motion between mousemoves. Missing fixation intervals do not establish missing raw gaze.'},
 'results':results,'provenance':{'typed_maps_hash':h.hexdigest(),'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'notebooks-v2/data_loader.py',ROOT/'scripts/gaze_cursor_divergence.py',ROOT/'scripts/approach_truncation_ablation.py',ROOT/'scripts/output/gaze_cursor_divergence/summary.json']}}}
(OUT/'summary.json').write_text(json.dumps(out,indent=2))
with (OUT/'trial-summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(trial_rows[0]));w.writeheader();w.writerows(trial_rows)
print(json.dumps({k:out[k] for k in ['counts','primary_trials','legacy_reproduction','legacy_table_phase_decomposition','approach_rules','approach_duration_ms_quantiles']},indent=2))
for window in ['full','buf500']:
 for phase in ['earlier','approach']:print(window,phase,json.dumps(results[f'xy|cap2000|{window}|{phase}']))
