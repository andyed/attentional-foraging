"""Render the sequence poster (A0), its detail crops and the matching-detail figure.

Displayed numbers come from page_values; exports are deterministic (no
creation dates, fixed SVG ids) and embed TrueType fonts.
"""
from pathlib import Path
import os,sys,json,tempfile
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'attention-atlas-mpl'))
import atlas_core as core
from atlas_core import ATLAS, ROOT
import page_values
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle,ConnectionPatch
from matplotlib.transforms import Bbox
from PIL import Image
from plot_style import PARAMS, contrast_ratio
B=Path(__file__).parent;O=ATLAS/'gaze-cursor-echo'
S=core.read_json(O/'summary.json');T=core.read_json(O/'trials.json.gz');K=core.read_json(O/'checks.json');R=core.read_json(ATLAS/'evidence/resting-cursor/summary.json');V=page_values.values()
BG='#fafaf8';INK='#222222';GAZE='#00505e';CURSOR='#683b0b';PALE='#dfe9e6';GRID='#c9cbc5';ACCENT='#782650'
plt.rcParams.update(PARAMS);plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':20,'font.weight':'medium','axes.labelsize':20,'xtick.labelsize':18,'ytick.labelsize':18,'axes.grid':False,'svg.fonttype':'none','svg.hashsalt':'attention-atlas','pdf.fonttype':42,'figure.facecolor':BG,'axes.facecolor':BG,'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,'savefig.bbox':None})
for c in [INK,GAZE,CURSOR,ACCENT]:assert contrast_ratio(c,BG)>=8
F=plt.figure(figsize=(46.8,33.1),dpi=100)
def txt(x,y,s,size=21,weight='medium',color=INK,**kw):return F.text(x,y,s,fontsize=size,fontweight=weight,color=color,**kw)
def line(x1,y1,x2,y2,lw=1,color=GRID):F.add_artist(Line2D([x1,x2],[y1,y2],transform=F.transFigure,color=color,lw=lw))
def title(x,y,n,s):txt(x,y,n,19,'bold',GAZE);txt(x+.020,y,s,26,'bold')
def axes(rect):
 ax=F.add_axes(rect)
 for s in ['top','right']:ax.spines[s].set_visible(False)
 ax.spines['left'].set_color(GRID);ax.spines['bottom'].set_color(GRID)
 return ax
regions={'entry':(.025,.655,.29,.205),'sparsity':(.338,.655,.327,.205),'rest':(.680,.655,.295,.205),'trial':(.025,.317,.615,.329),'pause':(.66,.317,.315,.329),'first-lag':(.025,.037,.445,.266),'matched-lag':(.51,.037,.465,.266)}
first=S['visit_sensitivity']['100'];near=S['matching_sensitivity']['2000'];trial=next(x for x in T if x['trial_id']==S['example']['trial_id']);pa=S['example']['pause'];rank=pa['cursor_aoi']+1
firstlags=np.array([d['lag_ms'] for tr in T for d in tr['first_arrivals']])/1000
nearlags=np.array([z[2] for tr in T for z in tr['matches']['2000']])/1000

txt(.035,.95,'While the mouse waits, the eyes travel.',57,'bold')
txt(.035,.913,'First entries favor gaze; nearby visit pairs have little median lag.',28,color=GAZE)
txt(.035,.884,'2,650 trials · 47 participants · strict result rectangles · first mousemove through final press',20)
txt(.965,.884,'Exploratory timing and sequence analysis',20,ha='right')
line(.035,.868,.965,.868,1.5,INK)

title(.035,.842,'01','FIRST ENTRY TO A RESULT')
txt(.035,.802,f"{first['gaze_first_share']['percent']:.1f}%",48,'bold',GAZE)
txt(.121,.806,'gaze arrives first',24,'bold')
txt(.035,.776,f"95% CI {first['gaze_first_share']['ci95'][0]:.1f}–{first['gaze_first_share']['ci95'][1]:.1f}% · {len(firstlags):,} jointly visited trial–AOIs",18)
ax=F.add_axes([.035,.724,.265,.027]);counts=[np.sum(firstlags>0),np.sum(firstlags==0),np.sum(firstlags<0)];left=0
for count,color in zip(counts,[GAZE,'#dedfd9',CURSOR]):
 width=100*count/len(firstlags);ax.barh(0,width,left=left,color=color,height=.8);left+=width
ax.set_xlim(0,100);ax.set_axis_off()
txt(.035,.703,f"■ Gaze first {counts[0]/len(firstlags)*100:.1f}%",17,'bold',GAZE);txt(.118,.703,f"■ Same onset {counts[1]/len(firstlags)*100:.1f}%",17);txt(.205,.703,f"■ Cursor first {counts[2]/len(firstlags)*100:.1f}%",17,'bold',CURSOR)
txt(.035,.677,f"Median first-entry difference: cursor {first['first_entry_lag_median_ms']/1000:.2f} s later. Ties at the first mousemove count as same onset.",17)

title(.350,.842,'02','THE RECORDED EYE PATH IS BUSIER')
txt(.350,.814,'Rank changes per minute of common signal coverage',19)
ax=axes([.415,.701,.213,.093]);names=['transitions','backward','reversals'];labels=['AOI changes','Backward steps','Direction reversals']
for j,(ch,col,marker) in enumerate([('gaze',GAZE,'o'),('cursor',CURSOR,'s')]):
 for i,key in enumerate(names):
  d=K['common_coverage_rates_per_minute'][ch][key];y=2-i+(.12 if ch=='gaze' else -.12)
  ax.errorbar(d['value'],y,xerr=[[d['value']-d['ci95'][0]],[d['ci95'][1]-d['value']]],fmt=marker,color=col,ms=9,capsize=4,lw=2)
  ax.text(d['ci95'][1]+.7,y,f"{d['value']:.1f}",va='center',fontsize=17,color=col)
ax.set_yticks([2,1,0],labels);ax.set_xlim(0,49);ax.set_xticks([0,20,40]);ax.set_xlabel('Changes / minute',fontsize=17);ax.set_ylim(-.6,2.6)
txt(.350,.677,'● Gaze',18,'bold',GAZE);txt(.392,.677,'■ Cursor',18,'bold',CURSOR);txt(.565,.677,'Bars: 95% participant-cluster CIs',18)

title(.69,.842,'03','WHEN THE CURSOR RESTS IN AN AOI')
rest=R['results']['50'];rm=rest['milliseconds'];restshare=rest['different_aoi_share_by_denominator']['cursor_rest_in_aoi_ms']
txt(.69,.802,f"{restshare['percent']:.1f}%",48,'bold',GAZE)
txt(.784,.806,'gaze is on another AOI',23,'bold')
txt(.69,.775,f"95% CI {V['rest_ci']}% · {V['rest_minutes']} minutes observed overlap",18)
txt(.69,.739,f"Same AOI {V['rest_same']}   ·   Different AOI {V['rest_share']}",21,'bold')
txt(.69,.713,f"Gaze off AOIs {V['rest_gaze_off']}   ·   No matched fixation {V['rest_unmatched']}",18)
txt(.69,.678,f"Rest = <5 px per 100 ms, scrolling excluded. Cursor held ≤2 s; without the cap: {V['rest_uncapped']}.",17)
line(.035,.65,.965,.65)

title(.035,.624,'04','ONE OBSERVED TRIAL, TWO PATHS')
txt(.035,.596,f"{trial['trial_id']} · {trial['span_ms']/1000:.2f} s · same time and rank scales",20)
txt(.38,.596,'Highlight: the same four-second cursor pause →',19,color=ACCENT)
maxrank=max(z[2]+1 for ch in ['gaze_segments','cursor_segments'] for z in trial[ch] if z[2]>=0)

def trace(ax,ch,lo,hi,zoom=False):
 color=GAZE if ch=='gaze' else CURSOR;segs=trial[ch+'_segments'];visit=trial[ch+'_visits']
 ax.axvspan(pa['start']/1000,pa['end']/1000,color='#e9dedf',zorder=0)
 for a,b,k in segs:
  a/=1000;b/=1000
  if b<=lo or a>=hi:continue
  if k>=0:ax.plot([max(a,lo),min(b,hi)],[k+1,k+1],color=color,lw=6 if not zoom else 8,solid_capstyle='butt')
  elif k==-1:ax.plot([max(a,lo),min(b,hi)],[maxrank+1,maxrank+1],color='#66665f',lw=3,solid_capstyle='butt')
  else:ax.plot([max(a,lo),min(b,hi)],[maxrank+2,maxrank+2],color='#7b7b73',lw=3,ls=':',solid_capstyle='butt')
 for a,b in zip(visit,visit[1:]):
  if b['start']-a['end']<=500 and a['aoi']!=b['aoi'] and a['end']/1000>=lo and b['start']/1000<=hi:
   ax.plot([a['end']/1000,b['start']/1000],[a['aoi']+1,b['aoi']+1],color=color,lw=1.5,ls='--')
 ax.set_xlim(lo,hi);ax.set_ylim(maxrank+2.65,.4)
 ax.set_yticks(list(range(1,maxrank+1))+[maxrank+1,maxrank+2],[str(i) for i in range(1,maxrank+1)]+['Off AOIs','Unobserved'])
 for y in range(1,maxrank+1):ax.axhline(y,color=GRID,lw=.5,zorder=-1)
 ax.set_ylabel('AOI position',fontsize=17)
 ax.tick_params(axis='y',labelsize=16);ax.tick_params(axis='x',labelsize=17)
 ax.text(.005,1.045,'GAZE' if ch=='gaze' else 'CURSOR',transform=ax.transAxes,color=color,fontsize=19,fontweight='bold')

axg=axes([.079,.482,.545,.083]);trace(axg,'gaze',0,trial['span_ms']/1000);axg.set_xticklabels([])
axc=axes([.079,.370,.545,.083]);trace(axc,'cursor',0,trial['span_ms']/1000);axc.set_xlabel('Seconds from first mousemove',fontsize=19)
txt(.035,.328,'Solid: observed occupancy. Dashed: nearby AOI changes. Unknown spans stay on the “Unobserved” row.',17)

title(.68,.624,'05','ZOOM INTO THE WAIT')
seq=' → '.join(str(k+1) for k in pa['gaze_sequence'])
txt(.68,.587,f'Gaze: {seq}',32,'bold',GAZE)
txt(.68,.559,f'Cursor: remains on AOI {rank} for {(pa["end"]-pa["start"])/1000:.1f} s',23,'bold',CURSOR)
ax=axes([.725,.395,.237,.127]);lo=pa['start']/1000;hi=pa['end']/1000
for ch,col,offset in [('gaze',GAZE,-.08),('cursor',CURSOR,.08)]:
 for a,b,k in trial[ch+'_segments']:
  a/=1000;b/=1000
  if b<=lo or a>=hi:continue
  y=k+1+offset if k>=0 else maxrank+1 if k==-1 else maxrank+2
  ax.plot([max(lo,a),min(hi,b)],[y,y],color=col,lw=7 if k>=0 else 3,ls='-' if k>=-1 else ':',solid_capstyle='butt')
ax.set_xlim(lo,hi);ax.set_ylim(maxrank+2.55,.45);ax.set_yticks(list(range(1,maxrank+1))+[maxrank+1,maxrank+2],[str(i) for i in range(1,maxrank+1)]+['Off AOIs','Unobserved']);ax.set_xlabel('Seconds from first mousemove',fontsize=17);ax.set_ylabel('AOI position',fontsize=17);ax.set_xticks(np.linspace(lo,hi,5));ax.tick_params(labelsize=17)
for y in range(1,maxrank+1):ax.axhline(y,color=GRID,lw=.5,zorder=-1)
txt(.68,.360,f"{pa['distinct']} gaze AOIs · {pa['returns']} return · {pa['different_ms']/1000:.2f} s on a different AOI",19)
txt(.68,.331,f"Illustration selected by a fixed rule from {S['example']['qualifying_pauses']} qualifying pauses.",17)
line(.035,.311,.965,.311)

title(.035,.286,'06','FIRST ARRIVAL: GAZE OFTEN LEADS')
txt(.035,.258,'Cursor first entry − gaze first entry, for jointly visited AOIs',19)
ax=axes([.069,.116,.381,.12]);clipped=np.clip(firstlags,-9.99,9.99);bins=np.linspace(-10,10,41);counts,edges=np.histogram(clipped,bins);centers=(edges[:-1]+edges[1:])/2
ax.bar(centers,100*counts/len(firstlags),width=.45,color=[CURSOR if x<0 else GAZE for x in centers]);ax.axvline(0,color=INK,lw=1.5);ax.axvline(np.median(firstlags),color=ACCENT,ls='--',lw=2);ax.set_xlim(-10,10);ax.set_xticks([-10,-5,0,5,10],['≤−10','−5','0','+5','≥+10']);ax.tick_params(axis='x',pad=10);ax.set_ylabel('Share of pairs (%)',fontsize=18);ax.set_xlabel('Cursor earlier  ←  onset difference (s)  →  Gaze earlier',fontsize=18)
txt(.035,.076,f"Median {V['first_median_s']} s · IQR {V['first_iqr_s']} s",19,'bold')
txt(.035,.052,'Outer bars include tails beyond ±10 s. The 0–0.5 s bin includes tied onsets; see panel 01.',17)

title(.525,.286,'07','NEARBY VISITS: LITTLE MEDIAN LAG')
txt(.525,.258,f"One-to-one, same-AOI pairs within ±2 s · {near['matched_pairs']:,} matched pairs",19)
ax=axes([.558,.116,.397,.12]);bins=np.linspace(-2,2,41);counts,edges=np.histogram(nearlags,bins);centers=(edges[:-1]+edges[1:])/2
ax.bar(centers,100*counts/len(nearlags),width=.088,color=[CURSOR if x<0 else GAZE for x in centers]);ax.axvline(0,color=INK,lw=1.5);ax.set_xlim(-2,2);ax.set_xticks([-2,-1,0,1,2],['−2','−1','0','+1','+2']);ax.set_ylabel('Share of matched pairs (%)',fontsize=18);ax.set_xlabel('Cursor earlier  ←  onset difference (s)  →  Gaze earlier',fontsize=18)
txt(.525,.076,f"Median {V['matched_median_s']} s · gaze first {V['matched_gaze_first']} [95% CI {V['matched_ci']}%] · ties {V['matched_ties']}",19,'bold')
txt(.525,.052,f"Without pairs starting at the first mousemove: gaze first {V['origin_gaze_first']} [{V['origin_ci']}%], median {V['origin_median_s']} s. Unmatched: {near['gaze_unmatched_visits']:,} gaze, {near['cursor_unmatched_visits']:,} cursor visits.",17)
txt(.035,.019,'Visits: ≥100 ms observed occupancy; same-AOI gaps ≤100 ms merged. AOI position is 1-based and includes ads/widgets. Timing ≠ proof of following.',17)
txt(.965,.019,'AdSERP / AllSERP · 29 September 2026',17,ha='right')

F.savefig(O/'poster.pdf',metadata={'CreationDate':None});F.savefig(O/'poster.svg',metadata={'Date':None});F.savefig(O/'poster.png',dpi=110)
for name,box in regions.items():
 x,y,w,h=box;F.savefig(O/(name+'.png'),dpi=120,bbox_inches=Bbox.from_bounds(x*46.8,y*33.1,w*46.8,h*33.1),pad_inches=.08)
im=Image.open(O/'poster.png');im.thumbnail((2400,1700));im.save(O/'poster-preview.png')
# Additional matching coverage and sensitivity figure, outside the primary poster.
f,(a1,a2)=plt.subplots(1,2,figsize=(23,8),gridspec_kw={'width_ratios':[1,1.1]});f.subplots_adjust(left=.07,right=.96,bottom=.30,top=.8,wspace=.36)
for yy,ch,col in [(1,'gaze',GAZE),(0,'cursor',CURSOR)]:
 total=near[ch+'_visits'];matched=near['matched_pairs'];pct=100*matched/total
 a1.barh(yy,pct,color=col,height=.45);a1.barh(yy,100-pct,left=pct,color='#e0e0d9',height=.45,hatch='//');a1.text(pct/2,yy,f'{pct:.1f}%',color=BG,ha='center',va='center',fontsize=20,fontweight='bold');a1.text(pct+(100-pct)/2,yy,f'{100-pct:.1f}%',ha='center',va='center',fontsize=20,bbox={'facecolor':'#e0e0d9','edgecolor':'none','pad':4})
a1.set_yticks([1,0],['Gaze visits','Cursor visits']);a1.set_xlim(0,100);a1.set_xlabel('Share of each channel’s qualifying visits (%)');a1.set_title('Matched share at ±2 seconds',fontsize=24,pad=24)
for i,w in enumerate(['500','1000','2000','5000']):
 d=S['matching_sensitivity'][w]['gaze_first_share'];a2.errorbar(d['percent'],i,xerr=[[d['percent']-d['ci95'][0]],[d['ci95'][1]-d['percent']]],fmt='o',color=GAZE,capsize=5,ms=10);a2.text(d['ci95'][1]+.35,i,f"{d['percent']:.1f}%",va='center',fontsize=19)
ex=K['matched_pairs_clock_origin_sensitivity']['excluding_pairs_at_clock_origin']['gaze_first']
a2.errorbar(ex['percent'],2.3,xerr=[[ex['percent']-ex['ci95'][0]],[ex['ci95'][1]-ex['percent']]],fmt='o',mfc=BG,color=ACCENT,capsize=5,ms=10);a2.text(ex['percent'],2.62,f"{ex['percent']:.1f}% without clock-origin pairs",ha='center',va='center',fontsize=16,color=ACCENT)
a2.axvline(50,color=INK,ls='--');a2.set_yticks(range(4),['±0.5 s','±1 s','±2 s','±5 s']);a2.set_xlim(42,58);a2.set_xlabel('Gaze arrives first among matched pairs (%)');a2.set_title('The matching window changes the estimate',fontsize=24,pad=24)
f.text(.07,.045,'Dark = matched; hatched = unmatched. Each pair uses one visit per channel.\n95% CIs resample participants; short matching windows preferentially retain near-synchronous visits.',fontsize=19)
f.savefig(O/'matching-detail.png',dpi=130);f.savefig(O/'matching-detail.pdf',metadata={'CreationDate':None});plt.close(f)
(O/'render-manifest.json').write_text(json.dumps({'poster_inches':[46.8,33.1],'regions':regions,'min_text_contrast':min(contrast_ratio(c,BG) for c in [INK,GAZE,CURSOR,ACCENT]),'example':S['example']},indent=2))
print('Rendered poster, seven crops, and matching detail.')
