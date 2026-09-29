"""Render the information-space poster (A0), its detail crops and the variation figure.

Needs the worked trial's original AdSERP screenshot. Exports are deterministic
(no creation dates, fixed SVG ids) and embed TrueType fonts.
"""
from pathlib import Path
import os,sys,json,collections,tempfile
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'attention-atlas-mpl'))
import atlas_core as core
from atlas_core import ATLAS, ROOT
import page_values
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,ConnectionPatch,Patch
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
from PIL import Image,ImageEnhance
from plot_style import PARAMS, contrast_ratio
BASE=Path(__file__).parent;OUT=ATLAS/'information-space-poster'
S=core.read_json(OUT/'summary.json');T=core.read_json(OUT/'trials.json.gz');V=page_values.values();A=S['aggregate_ms'];CI=S['ci95_pct'];TOTAL=S['total_ms']
BG='#fafaf8';INK='#222222';TEAL='#173f4b';GAZE='#00505e';MOUSE='#683b0b';MAGENTA='#782650';GRID='#8c8d86';HATCH='#6f7069'
GAZE_ONLY='#6fcc9c';OTHER='#dcecf1';NEITHER='#cbccc4'
C={'in_aoi':TEAL,'off_aoi':'#dbdcd5','unmatched':'#f1f0eb','above':TEAL,'below':'#b3e0e3','outside_page':'#e6d1e5',
 'same':TEAL,'adjacent':'#82c5cf','other':OTHER,'gaze_only':GAZE_ONLY,'cursor_only':'#f1cd8f','both_off':NEITHER,'no_fixation':'#f1f0eb','no_cursor':'#f1f0eb','neither_recorded':'#f1f0eb',
 'both_on':TEAL,'gaze_on_cursor_off':GAZE_ONLY,'cursor_on_gaze_off':'#f1cd8f','both_move':TEAL,'gaze_moves':GAZE_ONLY,'cursor_moves':'#f1cd8f','neither_moves':NEITHER,'unclassified':'#f1f0eb'}
HATCHED={'unmatched','no_fixation','no_cursor','neither_recorded','unclassified'}
N={'in_aoi':'Inside AOI','off_aoi':'Outside AOIs','unmatched':'Unclassified','above':'Above fold','below':'Below fold','outside_page':'Outside page',
 'same':'Same AOI','adjacent':'Adjacent AOI','other':'Other AOI','gaze_only':'Only gaze in AOI','cursor_only':'Only cursor in AOI','both_off':'Both outside AOIs',
 'no_fixation':'No fixation interval','no_cursor':'No cursor coverage','neither_recorded':'Neither recorded','both_on':'Both on target','gaze_on_cursor_off':'Gaze only on target','cursor_on_gaze_off':'Cursor only on target',
 'both_move':'Both moving','gaze_moves':'Gaze only moving','cursor_moves':'Cursor only moving','neither_moves':'Both below threshold','unclassified':'Unclassified'}
plt.rcParams.update(PARAMS);plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':20,'font.weight':'medium','axes.labelsize':20,'xtick.labelsize':18,'ytick.labelsize':18,'axes.grid':False,'svg.fonttype':'none','svg.hashsalt':'attention-atlas','pdf.fonttype':42,'savefig.bbox':None,'figure.facecolor':BG,'axes.facecolor':BG,'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK})
for color in [INK,TEAL,GAZE,MOUSE,MAGENTA]:assert contrast_ratio(color,BG)>=8,(color,contrast_ratio(color,BG))

F=plt.figure(figsize=(46.8,33.1),dpi=100);regions={}
def txt(x,y,s,size=21,weight='medium',color=INK,**kw):return F.text(x,y,s,fontsize=size,fontweight=weight,color=color,**kw)
def line(x1,y1,x2,y2,color=GRID,lw=1):F.add_artist(Line2D([x1,x2],[y1,y2],transform=F.transFigure,color=color,lw=lw))
def title(x,y,num,s,sub):
 txt(x,y,num,size=21,weight='bold',color=TEAL);txt(x+.018,y,s,size=27,weight='bold');txt(x,y-.021,sub,size=18)
def pct(lens,key):return 100*A[lens].get(key,0)/sum(A[lens].values())
def cip(lens,key):return '–'.join(f'{v:.1f}' for v in CI[lens].get(key,[0,0]))
def strip(ax,lens,keys,y=0,h=.55,labels=True,den=None,labelsize=20,minshare=7):
 c=A[lens] if isinstance(lens,str) else lens;total=sum(c.values()) if den is None else den;left=0
 for k in keys:
  v=100*c.get(k,0)/total
  ax.barh(y,v,left=left,height=h,color=C[k],edgecolor=BG,lw=1.3)
  if k in HATCHED:ax.barh(y,v,left=left,height=h,fill=False,edgecolor=HATCH,lw=0,hatch='////')
  if labels and v>=minshare:
   tc=BG if contrast_ratio(BG,C[k])>=8 else INK
   assert contrast_ratio(tc,C[k])>=8,(k,contrast_ratio(tc,C[k]))
   ax.text(left+v/2,y,f'{v:.1f}%',ha='center',va='center',fontsize=labelsize,fontweight='bold',color=tc)
  left+=v
 ax.set_xlim(0,100)
def clean(ax):
 for sp in ax.spines.values():sp.set_visible(False)
 ax.tick_params(axis='both',length=0)
def key(x,y,k,label=None,size=17):
 F.add_artist(Rectangle((x,y-.002),.009,.007,transform=F.transFigure,facecolor=C[k],edgecolor=INK,lw=.5))
 if k in HATCHED:F.add_artist(Rectangle((x,y-.002),.009,.007,transform=F.transFigure,fill=False,edgecolor=HATCH,lw=0,hatch='////'))
 txt(x+.012,y,label or N[k],size=size,va='center')
def sumkeys(c,keys):return sum(c.get(k,0) for k in keys)
missing=['no_fixation','no_cursor','neither_recorded'];jointkeys=['same','adjacent','other','gaze_only','cursor_only','both_off']
# Headline / entry point.
txt(.035,.955,'ONE CLOCK. MANY VIEWS.',size=62,weight='bold')
txt(.035,.919,'Gaze, cursor and click — an information-space atlas',size=33,color=TEAL,weight='bold')
txt(.965,.952,f"{V['trials']} trials  /  {V['participants']} participants",size=23,ha='right')
txt(.965,.93,f'{TOTAL/3600000:.2f} hours from first mousemove to final press',size=21,ha='right')
txt(.965,.909,'All spatial budgets use this clock; motion uses complete 100 ms windows.',size=18,ha='right')
line(.035,.891,.965,.891,color=INK,lw=1.4)
# Level 1: parallel lenses across one observation clock.
xs=[.035,.275,.515,.755];w=.21
for x in xs:regions[f'overview-{len(regions)+1}']=(x-.008,.673,w+.028,.211)
title(xs[0],.864,'01','IN / OUT OF AOIs','Recorded fixation location and held cursor position')
ax=F.add_axes([.065,.758,.18,.068]);strip(ax,'gaze_aoi',['in_aoi','off_aoi','unmatched'],1);strip(ax,'cursor_aoi',['in_aoi','off_aoi','unmatched'],0);ax.set_yticks([1,0],['Gaze','Cursor']);ax.set_xticks([]);clean(ax)
key(.035,.737,'in_aoi');key(.135,.737,'off_aoi');key(.035,.717,'unmatched','No matching interval / coverage')
txt(.035,.689,f"In AOI: gaze {pct('gaze_aoi','in_aoi'):.1f}% [{cip('gaze_aoi','in_aoi')}]; cursor {pct('cursor_aoi','in_aoi'):.1f}% [{cip('cursor_aoi','in_aoi')}]",size=16)
title(xs[1],.864,'02','ABOVE / BELOW FOLD','Point location relative to the initial viewport bottom')
ax=F.add_axes([.305,.758,.18,.068]);strip(ax,'gaze_fold',['above','below','outside_page','unmatched'],1);strip(ax,'cursor_fold',['above','below','outside_page','unmatched'],0);ax.set_yticks([1,0],['Gaze','Cursor']);ax.set_xticks([]);clean(ax)
key(.275,.737,'above');key(.385,.737,'below');key(.275,.717,'unmatched',f"Unclassified; outside page: gaze {pct('gaze_fold','outside_page'):.1f}%, cursor {pct('cursor_fold','outside_page'):.1f}%")
txt(.275,.689,f"Below fold: gaze {pct('gaze_fold','below'):.1f}% [{cip('gaze_fold','below')}]; cursor {pct('cursor_fold','below'):.1f}% [{cip('cursor_fold','below')}]",size=16)
title(xs[2],.864,'03','MOVING / STATIONARY','100 ms displacement, independent of fixation labels')
# four-way motion matrix, denominator excludes unclassified; missing shown outside.
m=A['motion'];mden=sum(m.values())-m.get('unclassified',0)
ax=F.add_axes([.555,.733,.153,.095]);ax.set_xlim(0,2);ax.set_ylim(0,2)
for i,j,k in [(0,1,'gaze_moves'),(1,1,'both_move'),(0,0,'neither_moves'),(1,0,'cursor_moves')]:
 ax.add_patch(Rectangle((i,j),1,1,facecolor=C[k],edgecolor=BG,lw=3));tc=BG if k=='both_move' else INK
 ax.text(i+.5,j+.56,f'{100*m.get(k,0)/mden:.1f}%',ha='center',va='center',fontsize=25,weight='bold',color=tc)
 ax.text(i+.5,j+.21,{'gaze_moves':'gaze only','both_move':'both','neither_moves':'neither','cursor_moves':'cursor only'}[k],ha='center',va='center',fontsize=17,color=tc)
ax.set_xticks([.5,1.5],['Cursor still','Cursor moving']);ax.set_yticks([.5,1.5],['Gaze still','Gaze moving']);clean(ax)
txt(.515,.702,f'{100*mden/sum(m.values()):.1f}% of complete windows classifiable; others excluded here.',size=17)
txt(.515,.683,'Moving = gaze ≥300 px/s; cursor ≥50 px/s. Still = below threshold.',size=16)
title(xs[3],.864,'04','TOGETHER / APART','AOI identity when both signals occupy mapped AOIs')
d=A['joint'];den=sumkeys(d,['same','adjacent','other']);sp={k:100*d.get(k,0)/den for k in ['same','adjacent','other']}
ax=F.add_axes([.755,.79,.205,.037]);strip(ax,{k:d.get(k,0) for k in ['same','adjacent','other']},['same','adjacent','other']);ax.set_xticks([]);ax.set_yticks([]);clean(ax)
for j,k in enumerate(['same','adjacent','other']):key(.755,.763-j*.020,k,f"{N[k]}  {sp[k]:.1f}%")
txt(.755,.691,f"Both in AOIs: {100*den/TOTAL:.1f}% of the full clock. Exact xy boxes.",size=17)
# Convergence motif into the shared timecourse, instead of unrelated cards.
for x in xs:
 F.add_artist(ConnectionPatch((x+w/2,.668),(.49,.644),'figure fraction','figure fraction',arrowstyle='-',lw=1,color=GRID))
txt(.50,.647,'SHARED TRIAL CLOCK  →  REASSEMBLE IN TIME',size=17,weight='bold',color=TEAL,ha='center',bbox={'facecolor':BG,'edgecolor':'none','pad':5})
# Level 2: the most visually dominant plot, the full cohort across normalized time.
title(.035,.623,'05','HOW THE SHARED CLOCK CHANGES','Duration-weighted composition within each twentieth of a trial')
time=np.array(S['timecourse_ms']);jorder=S['joint_state_order'];vals=np.column_stack([time[:,jorder.index(k)] for k in jointkeys]+[time[:,[jorder.index(k) for k in missing]].sum(1)])
vals=100*vals/vals.sum(1)[:,None];plotkeys=jointkeys+['no_fixation']
ax=F.add_axes([.062,.469,.574,.109]);bottom=np.zeros(20)
for i,k in enumerate(plotkeys):
 ax.bar(np.arange(20)*5,vals[:,i],width=5,bottom=bottom,align='edge',color=C[k],edgecolor=BG,lw=.6)
 if k in HATCHED:ax.bar(np.arange(20)*5,vals[:,i],width=5,bottom=bottom,align='edge',fill=False,edgecolor=HATCH,lw=0,hatch='////')
 bottom+=vals[:,i]
ax.set_xlim(0,100);ax.set_ylim(0,100);ax.set_yticks([0,50,100],['0%','50%','100%']);ax.set_xticks([0,25,50,75,100],['First move','25%','50%','75%','Final press']);ax.tick_params(axis='x',pad=12);ax.set_ylabel('Share of interval time');clean(ax)
for j,k in enumerate(plotkeys):key(.035+(j%4)*.159,.434-(j//4)*.019,k,'Unclassified interval' if k=='no_fixation' else None,size=16)
regions['time-course']=(.025,.402,.628,.235)
# Target-conditioned phase chart, linked to the previous computation.
title(.682,.623,'06','THE EVENTUAL CLICK TARGET','Same clock, conditioned on the clicked AOI and phase')
ax=F.add_axes([.739,.501,.224,.077]);tk=['both_on','gaze_on_cursor_off','cursor_on_gaze_off','both_off']+missing

for yy,phase in [(1,'earlier'),(0,'approach')]:
 cc=A['target_'+phase];merged={k:cc.get(k,0) for k in tk[:4]};merged['unclassified']=sumkeys(cc,missing);strip(ax,merged,tk[:4]+['unclassified'],yy)
ax.set_yticks([1,0],['Earlier','Final approach']);ax.set_xticks([]);clean(ax)
for j,k in enumerate(tk[:3]):key(.682,.476-j*.019,k,size=17)
key(.847,.476,'both_off','Both off target',size=17)
key(.847,.457,'no_fixation','Unclassified',size=17)
txt(.682,.411,'Final approach: geometric cursor onset → press; gaps stay visible.',size=17)
regions['click-target']=(.673,.401,.3,.235)
# Level 3: actual trial coordinates provide common ground for every lens.
line(.035,.394,.965,.394,color=INK,lw=1.3)
tr=next(t for t in T if t['trial_id']=='p047-b6-t1');ex=tr['example'];duration=tr['span_ms']/1000;on=(tr['onset_ms']-tr['start_ms'])/1000;target=ex['target'];fold=tr['fold_px'];moves=np.array(ex['moves']);fix=np.array(ex['fixations']);cards=ex['cards']
title(.035,.371,'07','ZOOM TO ONE OBSERVED TRIAL',f"{tr['trial_id']}  ·  {duration:.1f} s to final press  ·  clicked AOI {tr['target_position']+1}  ·  original screenshot + same time axis")
txt(.755,.371,'08   ZOOM TO THE FINAL 3 SECONDS',size=25,weight='bold')
txt(.755,.35,'Target-relative location and motion, on the same clock',size=17)
# Pull original stimulus, not a reconstruction.
shot=(ROOT/'AdSERP/data/full-page-screenshots')/(tr['trial_id']+'.png')
sys.path.insert(0,str(ROOT/'notebooks-v2'))
import data_loader as dl
ev,_,_=dl.load_mouse_events(tr['trial_id'],space='screenshot')
presspoint=next((x,y) for t,e,x,y in ev if e=='mousedown' and t==tr['press_ms'])
im=Image.open(shot).convert('RGB');im=ImageEnhance.Color(im).enhance(.3)
ymax=min(im.height,max(1800,int(max(moves[:,2].max(),fix[fix[:,0]<=tr['span_ms'],2].max()))+120))
spax=F.add_axes([.059,.144,.153,.19]);spax.imshow(im,alpha=.65);spax.set_xlim(100,850);spax.set_ylim(ymax,0);spax.set_aspect('equal',adjustable='box');spax.set_ylabel('Page y (screenshot px)');spax.set_xticks([200,500,800]);spax.set_xlabel('Page x (px)');spax.tick_params(labelsize=16)
for c in cards:
 if c['y']<ymax:spax.add_patch(Rectangle((c['x'],c['y']),c['width'],c['height'],fill=False,edgecolor=MAGENTA if c==target else '#626761',lw=2 if c==target else 1))
 if c['y']+60<ymax:spax.text(790,c['y']+15,str(c['position']+1),fontsize=16,color=INK,va='top')
spax.axhline(fold,color=INK,ls='--',lw=1.5)
# Scatter gaze only before press. Cursor joins only short gaps.
fsel=(fix[:,0]>=0)&(fix[:,0]<tr['span_ms']);spax.scatter(fix[fsel,1],fix[fsel,2],s=30,facecolors='none',edgecolors=GAZE,lw=1.5,zorder=5)
mx=[];my=[];mt=[]
for i,(t,x,y) in enumerate(moves):
 if i and t-moves[i-1,0]>250:mx.append(np.nan);my.append(np.nan);mt.append(np.nan)
 mx.append(x);my.append(y);mt.append(t/1000)
spax.plot(mx,my,color=MOUSE,lw=1.1,zorder=4);spax.scatter(*presspoint,marker='*',s=200,color=MAGENTA,zorder=6)
# Main trace shares y with the screenshot and target/fold bands.
tax=F.add_axes([.269,.144,.416,.19]);tax.set_ylim(ymax,0);tax.set_xlim(0,duration);tax.set_xlabel('Seconds since first mousemove');tax.set_yticks([])
for c in cards:
 if c['y']<ymax:tax.axhspan(c['y'],c['y']+c['height'],color='#f1e3ed' if c==target else '#eaece5',zorder=0)
tax.axhline(fold,color=INK,ls='--',lw=1.5);tax.text(.2,fold-30,'Initial fold',fontsize=16,color=INK)
for t,x,y,dur in fix:
 if t<tr['span_ms'] and t+dur>0:tax.plot([max(0,t)/1000,min(t+dur,tr['span_ms'])/1000],[y,y],color=GAZE,lw=3,solid_capstyle='butt')
tax.plot(mt,my,color=MOUSE,lw=1.8);tax.axvline(on,color=MAGENTA,ls=':',lw=2);tax.scatter(duration,presspoint[1],marker='*',s=280,color=MAGENTA,clip_on=False,zorder=6)
tax.axvspan(max(0,duration-3),duration,facecolor='none',edgecolor=MAGENTA,lw=2.5)
tax.text(on-.2,60,'Approach onset',fontsize=16,rotation=90,ha='right',va='top',color=MAGENTA,bbox={'facecolor':BG,'edgecolor':'none','pad':2})
F.legend(handles=[Line2D([],[],color=GAZE,lw=3,label='Recorded fixation'),Line2D([],[],color=MOUSE,lw=2,label='Cursor'),Line2D([],[],color=INK,ls='--',label='Initial fold'),Line2D([],[],color=MAGENTA,marker='*',lw=0,markersize=12,label='Final press')],loc='lower left',bbox_to_anchor=(.263,.102),ncol=4,fontsize=17,frameon=False)
# Enlarged target-location strip: exact intervals, no hidden missingness.
zoomstart=max(0,duration-3);ints=ex['intervals'];zax=F.add_axes([.777,.259,.186,.067]);zax.set_xlim(-3,0);zax.set_ylim(-.7,1.7)
for aa,bb,k in zip(ints['start'],ints['end'],ints['target']):
 aa=max(aa/1000,zoomstart);bb=min(bb/1000,duration)
 if bb<=aa:continue
 for yy,who in [(1,'gaze'),(0,'cursor')]:
  unknown=k in (['no_fixation','neither_recorded'] if who=='gaze' else ['no_cursor','neither_recorded'])
  on_target=k in (['both_on','gaze_on_cursor_off'] if who=='gaze' else ['both_on','cursor_on_gaze_off'])
  # For a missing counterpart, derive this signal directly below instead of losing its state.
  mid=(aa+bb)*500;idx=np.searchsorted(moves[:,0],mid,side='right')-1;fidx=np.searchsorted(fix[:,0],mid,side='right')-1
  if not unknown:
   pt=fix[fidx,1:3] if who=='gaze' else moves[idx,1:3];on_target=target['x']<=pt[0]<=target['x']+target['width'] and target['y']<=pt[1]<=target['y']+target['height']
  zax.barh(yy,bb-aa,left=aa-duration,height=.65,color=TEAL if on_target else C['off_aoi'],lw=0)
  if unknown:zax.barh(yy,bb-aa,left=aa-duration,height=.65,fill=False,edgecolor=HATCH,lw=0,hatch='////')
zax.set_yticks([1,0],['Gaze','Cursor']);zax.set_xticks([-3,-2,-1,0],['−3','−2','−1','Press']);clean(zax)
key(.755,.238,'in_aoi','On clicked AOI');key(.865,.238,'off_aoi','Off clicked AOI')
# Motion track; vertical categories serve readable labels and raw threshold boundary.
mex=ex['motion'];vax=F.add_axes([.777,.148,.186,.047]);vax.set_xlim(-3,0);vax.set_ylim(0,1)
for t,k in zip(mex['start'],mex['state']):
 aa=max(t/1000,zoomstart);bb=min(t/1000+.1,duration)
 if bb>aa:
  vax.axvspan(aa-duration,bb-duration,color=C[k],ec=BG,lw=.3)
  if k in HATCHED:vax.axvspan(aa-duration,bb-duration,fill=False,ec=HATCH,lw=0,hatch='////')
vax.axvspan((mex['start'][-1]+100)/1000-duration,0,color=C['unclassified'],lw=0);vax.axvspan((mex['start'][-1]+100)/1000-duration,0,fill=False,ec=HATCH,lw=0,hatch='////')
vax.set_yticks([]);vax.set_xticks([-3,-2,-1,0],['−3','−2','−1','Press']);vax.set_xlabel('Seconds before final press',fontsize=18);clean(vax)
txt(.755,.224,'Hatched = no matched interval / unclassified',size=16)
txt(.755,.204,'Joint motion state · same thresholds as 03',size=17)
for j,k in enumerate(['both_move','gaze_moves','cursor_moves','neither_moves']):key(.755+(j%2)*.111,.114-(j//2)*.017,k,{'both_move':'Both moving','gaze_moves':'Gaze only','cursor_moves':'Cursor only','neither_moves':'Neither'}[k],size=16)
# Explicit zoom connectors.
F.add_artist(ConnectionPatch((duration-3,0),(.75,.32),tax.transData,F.transFigure,arrowstyle='-',color=MAGENTA,lw=1.4))
regions['observed-trial']=(.025,.10,.687,.285);regions['final-seconds']=(.744,.083,.23,.302)
# Methods as a compact foundation, not disclaimer banners.
line(.035,.079,.965,.079,color=INK,lw=1.2)
txt(.035,.061,'READING THE MEASURES',size=19,weight='bold',color=TEAL)
txt(.035,.043,'AOI = mapped main-column rectangle (strict x,y).\nOff-AOI includes gutters and gaps. Missing fixation ≠ eye motion.',size=17,linespacing=1.45)
txt(.365,.061,'ONE CLOCK, EXPLICIT COVERAGE',size=19,weight='bold',color=TEAL)
txt(.365,.043,'Cursor held ≤2 s; recorded fixation durations overlap exactly.\nFold = initial viewport bottom in page coordinates; it does not move.',size=17,linespacing=1.45)
txt(.705,.061,'MOTION & UNCERTAINTY',size=19,weight='bold',color=TEAL)
txt(.705,.043,'Motion = smoothed endpoint displacement; scrolling bins excluded.\nBrackets: 95% participant-cluster bootstrap CI. Full methods linked.',size=17,linespacing=1.45)
txt(.035,.015,'AdSERP · typed AOI maps 2cb789eb8febd234 · descriptive analysis · 27 September 2026',size=16)
txt(.965,.015,'WHOLE COHORT  →  SHARED TIME  →  OBSERVED TRIAL  →  FINAL SECONDS',size=17,weight='bold',ha='right',color=TEAL)
# Standard scientific exports with a true A0 landscape page.
F.canvas.draw()
F.savefig(OUT/'poster.pdf',dpi=150,facecolor=BG,metadata={'CreationDate':None});F.savefig(OUT/'poster.svg',dpi=150,facecolor=BG,metadata={'Date':None});F.savefig(OUT/'poster.png',dpi=150,facecolor=BG)
F.savefig(OUT/'poster-preview.png',dpi=70,facecolor=BG)
for name,(x,y,w,h) in regions.items():F.savefig(OUT/f'{name}.png',dpi=150,bbox_inches=Bbox.from_bounds(x*46.8,y*33.1,w*46.8,h*33.1),facecolor=BG)
plt.close(F)
# Linked participant / threshold detail: distributions and sensitivity, no hidden interaction.
f,axes=plt.subplots(1,2,figsize=(18,7),gridspec_kw={'left':.09,'right':.97,'top':.79,'bottom':.23,'wspace':.33})
f.suptitle('How much do the aggregate views depend on who and how?',fontsize=27,weight='bold',y=.96)
pids=sorted(set(t['pid'] for t in T));pstats=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
for t in T:
 for lens,c in t['stats'].items():pstats[t['pid']][lens].update(c)
for i,(lens,label,color) in enumerate([('gaze_aoi','Gaze',GAZE),('cursor_aoi','Cursor',MOUSE)]):
 vals=[100*pstats[p][lens]['in_aoi']/sum(pstats[p][lens].values()) for p in pids]
 axes[0].scatter(np.full(len(vals),i)+np.linspace(-.12,.12,len(vals)),vals,s=34,color=color,alpha=.8)
 axes[0].errorbar(i+.22,pct(lens,'in_aoi'),yerr=np.array([[pct(lens,'in_aoi')-CI[lens]['in_aoi'][0]],[CI[lens]['in_aoi'][1]-pct(lens,'in_aoi')]]),fmt='D',color=INK,capsize=6)
axes[0].set_xticks([0,1],['Gaze','Cursor']);axes[0].set_ylabel('Time inside AOI (% of participant clock)');axes[0].set_ylim(0,100);axes[0].set_title('Participant variation',loc='left',fontsize=23)
thresholds=['150|25','300|50','600|100'];ks=['both_move','gaze_moves','cursor_moves','neither_moves']
for j,th in enumerate(thresholds):
 c=S['motion_sensitivity_ms'][th];strip(axes[1],{k:c.get(k,0) for k in ks},ks,j,h=.62,labelsize=16,minshare=9)
axes[1].set_yticks(range(3),['150 / 25','300 / 50','600 / 100']);axes[1].set_xlabel('Classifiable motion-window time (%)');axes[1].set_ylabel('Gaze / cursor threshold (px/s)');axes[1].set_title('Motion threshold sensitivity',loc='left',fontsize=23)
f.text(.09,.105,'Dots = 47 participant budgets.',fontsize=16)
f.text(.09,.055,'Diamonds = pooled share, 95% participant-cluster CI.',fontsize=16)
f.legend(handles=[Patch(facecolor=C[k],label={'both_move':'Both moving','gaze_moves':'Gaze only','cursor_moves':'Cursor only','neither_moves':'Neither'}[k]) for k in ks],loc='lower left',bbox_to_anchor=(.575,.018),ncol=2,fontsize=16,frameon=False)
f.savefig(OUT/'variation.png',dpi=150);f.savefig(OUT/'variation.pdf',metadata={'CreationDate':None});plt.close(f)
# Numeric claim / export manifest supports mechanical checking.
manifest={'poster_inches':[46.8,33.1],'regions':regions,'primary_reproduction_ms':S['previous_reproduction_max_error_ms'],'motion_classifiable_pct':100*mden/sum(m.values()),'same_aoi_pct_among_both_in_aois':sp['same'],'all_text_palette_contrast':{k:contrast_ratio(k,BG) for k in [INK,TEAL,GAZE,MOUSE,MAGENTA]}}
(OUT/'render-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
