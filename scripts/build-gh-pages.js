#!/usr/bin/env node
/**
 * Build gh-pages site for attentional-foraging interactive scanpath explorers.
 *
 * Copies SERP HTMLs, gazeplot PNGs, and regenerates interactive viewers
 * with relative paths (no file:// references).
 *
 * Usage:
 *   node scripts/build-gh-pages.js
 *
 * Output: site/ directory ready for gh-pages deployment
 */

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'AdSERP', 'data');
const SCRUTINIZER = path.join(ROOT, '..', 'scrutinizer-repo', 'scrutinizer2025');
const GAZEPLOT_DIR = path.join(SCRUTINIZER, 'output', 'adserp-fullpage-gazeplots');
const SITE_DIR = path.join(ROOT, 'site');

// Clean and create site structure
if (fs.existsSync(SITE_DIR)) fs.rmSync(SITE_DIR, { recursive: true });
fs.mkdirSync(path.join(SITE_DIR, 'serp-renders'), { recursive: true });
fs.mkdirSync(path.join(SITE_DIR, 'gazeplots'), { recursive: true });
fs.mkdirSync(path.join(SITE_DIR, 'png'), { recursive: true });

// Curated trial list — each demonstrates a distinct search behavior.
// Hand-picked for visual clarity and diversity.
const trials = [
    { tag: 'quick_decider',       trial_id: 'p032-b6-t8',  query: 'buy hartleys hartleys lemon jelly 135g' },
    { tag: 'ad_focused',          trial_id: 'p029-b2-t10', query: 'buy nike nike 375833 pro bra' },
    { tag: 'medium_engagement',   trial_id: 'p016-b3-t1',  query: 'buy blues breakers with eric clapton' },
    { tag: 'mouse_follower',      trial_id: 'p047-b1-t9',  query: 'buy dayco dayco wp259k2a timing belt kit' },
    { tag: 'regressive_scroller', trial_id: 'p035-b4-t2',  query: 'buy avon anew ultimate 7s cleanser' },
    { tag: 'deep_explorer',       trial_id: 'p011-b3-t2',  query: 'buy playmobil gymnast on balance beam' },
    { tag: 'long_trial',          trial_id: 'p037-b2-t5',  query: 'buy fusion ms wr600cv dust cover' },
    { tag: 'scanner',             trial_id: 'p045-b2-t6',  query: 'buy gates gates 22650 lower radiator hose' },
];

async function main() {

console.log(`Building site with ${trials.length} trials...\n`);

// Step 1: Pre-render SERP screenshots at 1280px viewport using Playwright.
// This ensures fixation coordinates (in 1280px screenshot space) align exactly.
console.log('  Rendering SERP screenshots at 1280px...');
const browser = await chromium.launch();
const playwrightCtx = await browser.newContext({ viewport: { width: 1280, height: 1024 } });

for (const trial of trials) {
    const serpSrc = path.join(DATA_DIR, 'serps', `${trial.trial_id}.html`);
    if (!fs.existsSync(serpSrc)) continue;
    const page = await playwrightCtx.newPage();
    await page.goto(`file://${path.resolve(serpSrc)}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    // Get full page height, resize viewport to match, then clip to exactly 1280px wide
    const docHeight = await page.evaluate(() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight));
    await page.setViewportSize({ width: 1280, height: docHeight });
    await page.waitForTimeout(300);
    await page.screenshot({
        path: path.join(SITE_DIR, 'serp-renders', `${trial.trial_id}.png`),
        clip: { x: 0, y: 0, width: 1280, height: docHeight }
    });
    await page.close();
    console.log(`    ${trial.trial_id}`);
}
await browser.close();
console.log('');

// Process each trial
const results = [];
for (const trial of trials) {
    const id = trial.trial_id;

    const serpRenderPath = path.join(SITE_DIR, 'serp-renders', `${id}.png`);
    if (!fs.existsSync(serpRenderPath)) {
        console.log(`  ✗ ${id}: no SERP render`);
        continue;
    }

    // Copy gazeplot PNG if available
    const gazeplotCandidates = [
        path.join(GAZEPLOT_DIR, `${id}_fullpage_gazeplot.png`),
        path.join(GAZEPLOT_DIR, `${id}_fullpage.png`),
    ];
    const gazeplotSrc = gazeplotCandidates.find(p => fs.existsSync(p));
    const hasGazeplot = !!gazeplotSrc;
    if (hasGazeplot) {
        fs.copyFileSync(gazeplotSrc, path.join(SITE_DIR, 'gazeplots', `${id}.png`));
    }

    // Load trial data
    const fixCsv = fs.readFileSync(path.join(DATA_DIR, 'fixation-data', `${id}.csv`), 'utf8');
    const mouseCsv = fs.readFileSync(path.join(DATA_DIR, 'mouse-movement-data', `${id}.csv`), 'utf8');
    const metaXml = fs.readFileSync(path.join(DATA_DIR, 'trial-metadata', `${id}.xml`), 'utf8');

    const get = (tag) => { const m = metaXml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)); return m ? m[1].trim() : ''; };
    const screenW = parseInt(get('screen').split('x')[0]) || 1280;
    const screenH = parseInt(get('screen').split('x')[1]) || 1024;
    const windowW = parseInt(get('window').split('x')[0]) || 1422;
    const windowH = parseInt(get('window').split('x')[1]) || 1137;
    const docH = parseInt(get('document').split('x')[1]) || 2642;
    const query = get('task').split('|').pop().trim().replace(/-/g, ' ');

    const fixations = fixCsv.trim().split('\n').slice(1).map(l => {
        const [t, x, y, d] = l.split(',').map(Number);
        return { t, x, y, d };
    }).filter(f => isFinite(f.t) && isFinite(f.x) && f.d > 0);

    const rx = screenW / windowW, ry = screenH / windowH;
    const clickLines = mouseCsv.trim().split('\n').slice(1).filter(l => l.includes(',click,'));
    let click = null;
    if (clickLines.length > 0) {
        const c = clickLines[clickLines.length - 1].split(',');
        // Scale X from window-space (1422) to screenshot-space (1280).
        // Y is raw pageY — document-relative, matches the Playwright screenshot directly.
        click = { x: parseFloat(c[1]) * rx, y: parseFloat(c[2]) };
    }

    // Parse mouse movement events for cursor replay
    // Scale X by rx (window→screenshot space), Y is raw pageY
    const mouseEvents = mouseCsv.trim().split('\n').slice(1)
        .map(l => { const c = l.split(','); return { t: parseInt(c[0]), x: parseFloat(c[1]), y: parseFloat(c[2]), e: (c[3]||'').trim() }; })
        .filter(m => isFinite(m.t) && isFinite(m.x) && ['mousemove','mouseover','click','mousedown','mouseup'].includes(m.e))
        .map(m => ({ t: m.t - (fixations.length > 0 ? fixations[0].t : 0), x: m.x * rx, y: m.y, e: m.e }));

    // Measure actual image heights — SVG must match exactly
    const serpImgH = fs.existsSync(serpRenderPath)
        ? parseInt(require('child_process').execSync(`sips -g pixelHeight "${serpRenderPath}" | tail -1`).toString().match(/\d+/)?.[0] || '0')
        : docH;
    const gazeplotImgH = hasGazeplot
        ? parseInt(require('child_process').execSync(`sips -g pixelHeight "${path.join(SITE_DIR, 'gazeplots', id + '.png')}" | tail -1`).toString().match(/\d+/)?.[0] || '0')
        : serpImgH;
    // Default to serp-render height — no padding, no max(docH, fixY)
    const maxY = serpImgH;
    const fovealR = 60;
    const N = fixations.length;
    const T0 = N > 0 ? fixations[0].t : 0;
    const TOTAL_DUR = N > 0 ? fixations[N-1].t + fixations[N-1].d - T0 : 0;
    const durations = fixations.map(f => f.d);
    const minD = Math.min(...durations) || 50, maxD = Math.max(...durations) || 500;

    // Relative paths for assets
    const serpRenderRelPath = `serp-renders/${id}.png`;
    const gazeplotRelPath = `gazeplots/${id}.png`;

    const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Scanpath: ${id} — ${query}</title>
<meta name="viewport" content="width=${screenW}">
<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
posthog.init('phc_cUZalkUiHgfuv7k5hPzhuLhYQkjUWOQBl82pdDgHAmZ',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only'});</script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #111; color: #eee; font-family: system-ui, -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; }
.header { width: ${screenW}px; padding: 10px 16px; background: #1a1a1a; border-bottom: 1px solid #333;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.header h1 { font-size: 14px; font-weight: 600; }
.header h1 span { color: #aaa; font-weight: 400; }
.controls { display: flex; gap: 12px; align-items: center; font-size: 12px; }
.controls label { cursor: pointer; user-select: none; }
.btn { background: #333; border: 1px solid #555; color: #eee; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 11px; }
.btn:hover { background: #444; }
.btn.active { background: #2a5a8a; border-color: #4a8aca; }
.viewer { position: relative; width: ${screenW}px; height: 70vh; overflow-y: auto; overflow-x: hidden; background: #000; }
.serp-container { position: relative; width: ${screenW}px; }
#bg-img { width: ${screenW}px; display: block; }
.scanpath-svg { position: absolute; top: 0; left: 0; z-index: 10; pointer-events: none; }
.foveal-ring { position: absolute; z-index: 11; pointer-events: none; border: 2px solid rgba(255,255,255,0.7);
  border-radius: 50%; width: ${fovealR*2}px; height: ${fovealR*2}px; transform: translate(-50%, -50%);
  box-shadow: 0 0 20px rgba(255,255,255,0.3); transition: left 0.08s, top 0.08s; display: none; }
.mouse-cursor { position: absolute; z-index: 999; pointer-events: none; display: none;
  width: 20px; height: 20px; transition: left 0.03s linear, top 0.03s linear; }
.mouse-cursor svg { width: 20px; height: 28px; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5)); }
.mouse-cursor.clicking svg path { fill: #ff3333; }
.timeline { width: ${screenW}px; background: #1a1a1a; padding: 8px 16px; border-top: 1px solid #333; }
.timeline-track { position: relative; height: 40px; background: #222; border-radius: 4px; cursor: pointer; overflow: hidden; }
.timeline-ticks { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
.timeline-tick { position: absolute; bottom: 0; border-radius: 2px 2px 0 0; min-width: 2px; }
.timeline-playhead { position: absolute; top: 0; width: 2px; height: 100%; background: #ff4444; z-index: 2; }
.timeline-info { display: flex; justify-content: space-between; margin-top: 4px; font-size: 11px; color: #aaa; }
.info-panel { width: ${screenW}px; padding: 6px 16px; background: #1a1a1a; font-size: 11px; color: #aaa;
  display: flex; gap: 20px; border-top: 1px solid #222; }
.info-panel .val { color: #ccc; }
.info-panel a { color: #ff9933; text-decoration: none; font-weight: 600; }
.info-panel a:hover { text-decoration: underline; }
.back { font-size: 12px; }
.back a { color: #6af; text-decoration: none; }
</style></head><body>
<div class="header">
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="back"><a href="index.html">&larr; All</a></span>
    <h1>${id} <span>— ${query}</span></h1>
  </div>
  <div class="controls">
    ${hasGazeplot ? `<button class="btn" id="mode-btn">Gazeplot</button>` : ''}
    <label><input type="checkbox" id="lines-toggle" checked> Lines</label>
    <label><input type="checkbox" id="numbers-toggle" checked> Numbers</label>
    <button class="btn" id="play-btn">&#9654; Play</button>
    <button class="btn" id="reset-btn">Reset</button>
  </div>
</div>
<div class="viewer" id="viewer">
  <div class="serp-container">
    <img id="bg-img" src="${serpRenderRelPath}" />
    <svg class="scanpath-svg" id="scanpath-svg" xmlns="http://www.w3.org/2000/svg"
         width="${screenW}" height="${serpImgH}" viewBox="0 0 ${screenW} ${serpImgH}"></svg>
    <div class="foveal-ring" id="foveal-ring"></div>
    <div class="mouse-cursor" id="mouse-cursor"><svg viewBox="0 0 20 28"><path d="M0,0 L0,22 L5.5,17 L10,28 L14,26 L9,16 L16,16 Z" fill="#ff9933" stroke="#000" stroke-width="1"/></svg></div>
  </div>
</div>
<div class="timeline">
  <div class="timeline-track" id="timeline-track">
    <div class="timeline-ticks" id="timeline-ticks"></div>
    <div class="timeline-playhead" id="playhead"></div>
  </div>
  <div class="timeline-info">
    <span id="time-label">Fixation 0 / ${N}</span>
    <span id="duration-label">0.0s / ${(TOTAL_DUR/1000).toFixed(1)}s</span>
  </div>
</div>
<div class="info-panel">
  <span><a href="https://github.com/andyed/scrutinizer2025">Scrutinizer rendering</a></span>
  <span>Position: <span class="val" id="info-pos">—</span></span>
  <span>Duration: <span class="val" id="info-dur">—</span></span>
  <span>Fixations: <span class="val" id="info-seen">0</span></span>
  ${click ? `<span>Click: <span class="val">(${Math.round(click.x)}, ${Math.round(click.y)})</span></span>` : ''}
  <span><a href="png/${id}.png" download style="color:#6af;text-decoration:none;">Download PNG</a></span>
</div>
<script>
const F=${JSON.stringify(fixations)},CK=${JSON.stringify(click)},ME=${JSON.stringify(mouseEvents)},FR=${fovealR},SW=${screenW},N=${N},
T0=${T0},TD=${TOTAL_DUR},MND=${minD},MXD=${maxD},
SERP_SRC='${serpRenderRelPath}',SERP_H=${serpImgH},
GAZEPLOT_SRC=${hasGazeplot ? `'${gazeplotRelPath}'` : 'null'},GAZEPLOT_H=${gazeplotImgH};
const rF=d=>8+(d-MND)/(MXD-MND+1)*22;
const cF=(i,n)=>{const t=n>1?i/(n-1):0;return\`rgb(\${Math.round(50+205*t)},\${Math.round(50+100*(1-Math.abs(t-.5)*2))},\${Math.round(255-205*t)})\`};
const svg=document.getElementById('scanpath-svg'),ph=document.getElementById('playhead'),
fr=document.getElementById('foveal-ring'),mc=document.getElementById('mouse-cursor'),
vw=document.getElementById('viewer'),
lt=document.getElementById('lines-toggle'),nt=document.getElementById('numbers-toggle'),
ws=document.getElementById('window-size'),tt=document.getElementById('timeline-track');
let ci=N-1,pl=false,pt=null;
const ns='http://www.w3.org/2000/svg';
function se(t,a){const e=document.createElementNS(ns,t);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);return e}
const tEl=document.getElementById('timeline-ticks');
F.forEach((f,i)=>{const t=document.createElement('div');t.className='timeline-tick';
t.style.left=(N>1?(f.t-T0)/TD*100:0)+'%';t.style.width=Math.max(.5,f.d/TD*100)+'%';
t.style.height=Math.min(100,20+f.d/10)+'%';t.style.background=cF(i,N);t.style.opacity='.5';tEl.appendChild(t)});
const lE=[],cE=[],tE=[];
for(let i=0;i<N;i++){const f=F[i],r=rF(f.d),c=cF(i,N);
if(i>0){const p=F[i-1];const l=se('line',{x1:p.x,y1:p.y,x2:f.x,y2:f.y,stroke:c,'stroke-width':1.5,'stroke-opacity':.4});svg.appendChild(l);lE.push(l)}else lE.push(null);
const cr=se('circle',{cx:f.x,cy:f.y,r,fill:c,'fill-opacity':.25,stroke:c,'stroke-width':2,'stroke-opacity':.8});svg.appendChild(cr);cE.push(cr);
const fs=Math.max(9,Math.min(14,r));const tx=se('text',{x:f.x,y:f.y,'text-anchor':'middle','dominant-baseline':'central','font-family':'monospace','font-weight':'bold','font-size':fs,fill:'white',stroke:'rgba(0,0,0,.6)','stroke-width':2,'paint-order':'stroke'});tx.textContent=i+1;svg.appendChild(tx);tE.push(tx)}
if(CK){const s=se('polygon',{points:[0,-16,6,-4,16,-4,8,4,12,16,0,8,-12,16,-8,4,-16,-4,-6,-4].reduce((a,v,i)=>{a.push(i%2===0?CK.x+v:CK.y+v);return a},[]).join(','),fill:'#f00','fill-opacity':.5,stroke:'#f00','stroke-width':2});svg.appendChild(s);
const l=se('text',{x:CK.x+18,y:CK.y+4,'font-family':'monospace','font-weight':'bold','font-size':11,fill:'#f00',stroke:'white','stroke-width':2,'paint-order':'stroke'});l.textContent='CLICK';svg.appendChild(l)}
function uv(){for(let i=0;i<N;i++){const v=i<=ci;cE[i].style.display=v?'':'none';tE[i].style.display=v&&nt.checked?'':'none';
if(lE[i])lE[i].style.display=v&&lt.checked?'':'none';cE[i].setAttribute('stroke-width',pl&&i===ci?4:2);cE[i].setAttribute('stroke-opacity',pl&&i===ci?1:.8)}
if(ci>=0&&N>1)ph.style.left=(F[ci].t-T0)/TD*100+'%';
if(ci>=0){const f=F[ci];const vr=vw.getBoundingClientRect(),fy=f.y-vw.scrollTop;if(fy<100||fy>vr.height-100)vw.scrollTo({top:f.y-vr.height/2,behavior:'smooth'})}
if(pl&&ci>=0){const f=F[ci];fr.style.display='block';fr.style.left=f.x+'px';fr.style.top=f.y+'px';
// Mouse cursor: interpolate position at current fixation time (relative)
if(ME.length>0){const ft=f.t-T0;let mi=0;for(let i=0;i<ME.length;i++){if(ME[i].t<=ft)mi=i;else break;}
const m0=ME[mi],m1=ME[Math.min(mi+1,ME.length-1)];
let mx=m0.x,my=m0.y;if(m1.t>m0.t){const p=(ft-m0.t)/(m1.t-m0.t);mx=m0.x+(m1.x-m0.x)*p;my=m0.y+(m1.y-m0.y)*p;}
mc.style.display='block';mc.style.left=mx+'px';mc.style.top=my+'px';mc.style.opacity='1';
mc.classList.toggle('clicking',m0.e==='click'||m0.e==='mousedown');
console.log('CURSOR',mx.toFixed(0),my.toFixed(0),m0.e);
}}else{fr.style.display='none';mc.style.display='none';}
if(ci>=0){const f=F[ci];document.getElementById('info-pos').textContent='('+f.x+','+f.y+')';
document.getElementById('info-dur').textContent=f.d+'ms';document.getElementById('info-seen').textContent=ci+1;
document.getElementById('time-label').textContent='Fixation '+(ci+1)+' / '+N;
document.getElementById('duration-label').textContent=((f.t-T0)/1000).toFixed(1)+'s / '+(TD/1000).toFixed(1)+'s'}}
function sf(i){ci=Math.max(-1,Math.min(N-1,i));uv()}
lt.addEventListener('change',uv);nt.addEventListener('change',uv);
let dr=false;function ts(e){const r=tt.getBoundingClientRect(),p=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
let b=0;for(let i=0;i<N;i++)if(F[i].t<=T0+p*TD)b=i;sf(b)}
tt.addEventListener('mousedown',e=>{dr=true;ts(e)});document.addEventListener('mousemove',e=>{if(dr)ts(e)});document.addEventListener('mouseup',()=>{dr=false});
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'){sf(ci+1);e.preventDefault()}if(e.key==='ArrowLeft'){sf(ci-1);e.preventDefault()}
if(e.key===' '){tp();e.preventDefault()}if(e.key==='Home'){sf(0);e.preventDefault()}if(e.key==='End'){sf(N-1);e.preventDefault()}});
function tp(){pl=!pl;document.getElementById('play-btn').textContent=pl?'⏸ Pause':'▶ Play';
document.getElementById('play-btn').classList.toggle('active',pl);if(pl){if(ci>=N-1)ci=-1;pn()}else{clearTimeout(pt);fr.style.display='none';mc.style.display='none';ci=N-1;uv()}}
function pn(){if(!pl)return;const n=ci+1;if(n>=N){pl=false;document.getElementById('play-btn').textContent='▶ Play';fr.style.display='none';mc.style.display='none';ci=N-1;uv();return}
sf(n);pt=setTimeout(pn,Math.max(100,F[n].d*.5))}
document.getElementById('play-btn').addEventListener('click',tp);
document.getElementById('reset-btn').addEventListener('click',()=>{pl=false;clearTimeout(pt);document.getElementById('play-btn').textContent='▶ Play';ci=N-1;uv();vw.scrollTo({top:0})});
uv();
// Gazeplot toggle
let bgMode='serp';
const modeBtn=document.getElementById('mode-btn');
const bgImg=document.getElementById('bg-img');
if(modeBtn&&GAZEPLOT_SRC){modeBtn.addEventListener('click',()=>{
  bgMode=bgMode==='serp'?'gazeplot':'serp';
  modeBtn.textContent=bgMode==='serp'?'Gazeplot':'SERP';
  modeBtn.classList.toggle('active',bgMode==='gazeplot');
  const h=bgMode==='gazeplot'?GAZEPLOT_H:SERP_H;
  const src=bgMode==='gazeplot'?GAZEPLOT_SRC:SERP_SRC;
  bgImg.src=src;
  svg.setAttribute('viewBox','0 0 '+SW+' '+h);
  svg.setAttribute('height',h);
  svg.style.height=h+'px';
})}
</script></body></html>`;

    fs.writeFileSync(path.join(SITE_DIR, `${id}.html`), html);
    const sizeMB = hasGazeplot ? (fs.statSync(gazeplotSrc).size / 1024 / 1024).toFixed(1) : '—';
    console.log(`  ✓ ${trial.tag}: ${id} (${N} fix, gazeplot: ${hasGazeplot ? sizeMB + 'MB' : 'no'})`);
    results.push({ tag: trial.tag, id, query: trial.query, n: N, hasGazeplot });
}

// Build index page
const indexHtml = `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>AdSERP Scanpath Explorer — Attentional Foraging on Search Engine Results</title>
<meta name="description" content="Interactive foveated vision scanpath replays of eye-tracking data from the AdSERP dataset, rendered through Scrutinizer's neuroscience-based peripheral vision simulation.">
<script>!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
posthog.init('phc_cUZalkUiHgfuv7k5hPzhuLhYQkjUWOQBl82pdDgHAmZ',{api_host:'https://us.i.posthog.com',person_profiles:'identified_only'});</script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 2em 1em; background: #111; color: #eee; }
h1 { font-size: 1.6em; margin-bottom: 0.3em; }
h1 a { color: #ff9933; text-decoration: none; }
.subtitle { color: #aaa; margin-bottom: 1.5em; line-height: 1.5; }
.subtitle a { color: #6af; text-decoration: none; }
.trial { margin: 0.6em 0; background: #1a1a1a; border-radius: 6px; border-left: 3px solid #333; transition: border-color 0.2s, background 0.2s; cursor: pointer; }
.trial:hover { border-left-color: #ff9933; background: #222; }
.trial a { display: block; padding: 0.8em 1em; color: #eee; text-decoration: none; cursor: pointer; }
.trial .tag { color: #ff9933; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; }
.trial .id { font-weight: 600; font-size: 0.95em; }
.trial .query { color: #aaa; font-size: 0.85em; margin-top: 2px; }
.trial .meta { color: #888; font-size: 0.8em; margin-top: 2px; }
kbd { background: #333; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; color: #ccc; }
.controls-help { color: #888; font-size: 0.85em; margin-bottom: 1.5em; }
footer { margin-top: 2em; padding-top: 1em; border-top: 1px solid #333; color: #666; font-size: 0.8em; }
footer a { color: #888; }
</style></head><body>
<h1><a href="https://github.com/andyed/scrutinizer2025">Scrutinizer</a> × AdSERP</h1>
<p class="subtitle">
  Each page below replays a complete search session from the
  <a href="https://doi.org/10.1145/3726302.3730325">AdSERP dataset</a>:
  numbered eye fixations, mouse cursor path, page scroll positions, and
  <a href="https://github.com/andyed/scrutinizer2025">Scrutinizer</a>-simulated
  peripheral vision — showing what the searcher could actually resolve
  at each moment. The background image is rendered through Scrutinizer's
  LGN/V1/DoG foveated pipeline with infinite visual memory accumulation.
</p>
<p class="subtitle" style="color:#888;">
  AdSERP: 47 participants, 2,776 transactional Google queries, Gazepoint GP3 HD eye tracker at 150Hz.
  Trials below are prototypical examples of distinct search behaviors.
</p>
<p class="controls-help">
  <kbd>&larr;</kbd><kbd>&rarr;</kbd> step through fixations &middot;
  <kbd>Space</kbd> play/pause &middot;
  drag timeline to scrub &middot;
  Window selector limits visible fixation history
</p>
${results.map(r => `<div class="trial"><a href="${r.id}.html">
  <div style="display:flex;gap:12px;align-items:start;">
    <img src="png/${r.id}.png" style="width:180px;height:120px;object-fit:cover;object-position:center 15%;border-radius:4px;flex-shrink:0;background:#222;" loading="lazy" alt="${r.tag}">
    <div>
      <span class="tag">${r.tag.replace(/_/g, ' ')}</span>
      <div class="id">${r.id}</div>
      <div class="query">"${r.query}"</div>
      <div class="meta">${r.n} fixations${r.hasGazeplot ? ' · Scrutinizer rendered' : ''}</div>
    </div>
  </div>
</a></div>`).join('\n')}
<details style="margin-top:2em;color:#aaa;">
<summary style="cursor:pointer;color:#ccc;font-size:0.95em;margin-bottom:0.8em;">How this was built</summary>
<div style="line-height:1.7;font-size:0.85em;">
<p>Each background image is a full-page foveated render produced by
<a href="https://github.com/andyed/scrutinizer2025" style="color:#ff9933;">Scrutinizer</a>, a
neuroscience-based peripheral vision simulator. Scrutinizer models the
human visual system's resolution falloff from fovea to periphery using
a pipeline inspired by the lateral geniculate nucleus (LGN), primary visual
cortex (V1), and difference-of-Gaussians (DoG) spatial frequency filtering.</p>

<p><strong>Infinite visual memory mode</strong> accumulates every fixation across
the entire scanpath. As each fixation is replayed, the foveal region at
that position is "remembered" — remaining sharp while everything else
degrades through the peripheral pipeline. The final image shows exactly
what the participant could have resolved across their full search session:
sharp where they looked, degraded where they didn't.</p>

<p><strong>Pipeline:</strong></p>
<ol style="margin-left:1.5em;color:#999;">
<li>The <a href="https://github.com/andyed/attentional-foraging/blob/main/scripts/find_interesting_trials.py" style="color:#6af;">interesting trials script</a>
  identifies prototypical search behaviors from 2,776 AdSERP trials</li>
<li>The <a href="https://github.com/andyed/scrutinizer2025/blob/main/renderer/scanpath/importers/adserp-importer.js" style="color:#6af;">AdSERP importer</a>
  parses fixation CSVs (page-space coords from Gazepoint GP3 HD at 150Hz),
  mouse events (evtrack pageX/pageY), scroll timelines, and trial metadata —
  reconciling two coordinate systems
  (<a href="https://github.com/andyed/scrutinizer2025/blob/main/docs/adserp-coordinate-system.md" style="color:#6af;">coordinate reference</a>)</li>
<li>The <a href="https://github.com/andyed/scrutinizer2025/blob/main/scripts/capture-fullpage-gazeplot.js" style="color:#6af;">fullpage gazeplot script</a>
  walks each fixation through Scrutinizer's Electron-based WebGL pipeline with
  <code style="background:#222;padding:1px 4px;border-radius:2px;">TEST_VISUAL_MEMORY=-1</code> (infinite accumulation),
  then tile-captures the full page at each scroll position and stitches them</li>
<li>The interactive overlay (fixation numbers, saccade lines, timeline scrubber)
  is generated as self-contained HTML with the gazeplot PNG as background</li>
</ol>

<p style="margin-top:0.8em;"><strong>Data:</strong>
<a href="https://doi.org/10.1145/3726302.3730325" style="color:#6af;">AdSERP</a> —
Latifzadeh et al., 2,776 transactional Google SERP queries, 47 participants,
Gazepoint GP3 HD eye tracker, simultaneous mouse + scroll + gaze recording.
<a href="https://zenodo.org/records/15236546" style="color:#6af;">Dataset on Zenodo</a>.</p>
</div>
</details>

<footer>
  <a href="https://github.com/andyed/scrutinizer2025">Scrutinizer</a> ·
  <a href="https://github.com/andyed/attentional-foraging">attentional-foraging</a> ·
  <a href="https://doi.org/10.1145/3726302.3730325">AdSERP paper</a> ·
  Built ${new Date().toISOString().slice(0, 10)}
</footer>
</body></html>`;

fs.writeFileSync(path.join(SITE_DIR, 'index.html'), indexHtml);

// .nojekyll for GitHub Pages
fs.writeFileSync(path.join(SITE_DIR, '.nojekyll'), '');

console.log(`\n  Site built: ${SITE_DIR}/`);
console.log(`  ${results.length} trials, ${results.filter(r => r.hasGazeplot).length} with Scrutinizer renders`);
console.log(`\n  Deploy: gh-pages -d site  (or push site/ to gh-pages branch)`);

} // end async main
main().catch(err => { console.error('Fatal:', err); process.exit(1); });
