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

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'AdSERP', 'data');
const SCRUTINIZER = path.join(ROOT, '..', 'scrutinizer-repo', 'scrutinizer2025');
const GAZEPLOT_DIR = path.join(SCRUTINIZER, 'output', 'adserp-fullpage-gazeplots');
const SITE_DIR = path.join(ROOT, 'site');

// Clean and create site structure
if (fs.existsSync(SITE_DIR)) fs.rmSync(SITE_DIR, { recursive: true });
fs.mkdirSync(path.join(SITE_DIR, 'serps'), { recursive: true });
fs.mkdirSync(path.join(SITE_DIR, 'gazeplots'), { recursive: true });

// Load interesting trials
const interestingPath = path.join(DATA_DIR, 'interesting-trials.json');
const interesting = JSON.parse(fs.readFileSync(interestingPath, 'utf8'));

const seen = new Set();
const trials = [];
for (const [tag, info] of Object.entries(interesting.prototypical)) {
    if (!info.trial_id || seen.has(info.trial_id)) continue;
    if (info.value === 0 && info.metric === 'fixation_count') continue;
    seen.add(info.trial_id);
    trials.push({ tag, ...info });
}

console.log(`Building site with ${trials.length} trials...\n`);

// Process each trial
const results = [];
for (const trial of trials) {
    const id = trial.trial_id;

    // Copy SERP HTML
    const serpSrc = path.join(DATA_DIR, 'serps', `${id}.html`);
    const serpDest = path.join(SITE_DIR, 'serps', `${id}.html`);
    if (fs.existsSync(serpSrc)) {
        fs.copyFileSync(serpSrc, serpDest);
    } else {
        console.log(`  ✗ ${id}: no SERP HTML`);
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
        click = { x: parseFloat(c[1]) * rx, y: parseFloat(c[2]) * ry };
    }

    const maxY = Math.max(docH, ...fixations.map(f => f.y)) + 100;
    const fovealR = 60;
    const N = fixations.length;
    const T0 = N > 0 ? fixations[0].t : 0;
    const TOTAL_DUR = N > 0 ? fixations[N-1].t + fixations[N-1].d - T0 : 0;
    const durations = fixations.map(f => f.d);
    const minD = Math.min(...durations) || 50, maxD = Math.max(...durations) || 500;

    // Generate HTML with RELATIVE paths
    const serpRelPath = `serps/${id}.html`;
    const gazeplotRelPath = `gazeplots/${id}.png`;

    const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Scanpath: ${id} — ${query}</title>
<meta name="viewport" content="width=${screenW}">
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
.serp-container { position: relative; width: ${screenW}px; min-height: ${maxY}px; }
.gazeplot-img { width: ${screenW}px; display: block; }
.serp-iframe { width: ${screenW}px; height: ${maxY}px; border: none; display: block; }
.scanpath-svg { position: absolute; top: 0; left: 0; z-index: 10; pointer-events: none; }
.foveal-ring { position: absolute; z-index: 11; pointer-events: none; border: 2px solid rgba(255,255,255,0.7);
  border-radius: 50%; width: ${fovealR*2}px; height: ${fovealR*2}px; transform: translate(-50%, -50%);
  box-shadow: 0 0 20px rgba(255,255,255,0.3); transition: left 0.08s, top 0.08s; display: none; }
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
.back { position: fixed; top: 8px; left: 8px; z-index: 100; font-size: 12px; }
.back a { color: #6af; text-decoration: none; }
</style></head><body>
<div class="back"><a href="index.html">&larr; All trials</a></div>
<div class="header">
  <h1>${id} <span>— ${query}</span></h1>
  <div class="controls">
    <label><input type="checkbox" id="lines-toggle" checked> Lines</label>
    <label><input type="checkbox" id="numbers-toggle" checked> Numbers</label>
    <button class="btn" id="play-btn">&#9654; Play</button>
    <button class="btn" id="reset-btn">Reset</button>
  </div>
</div>
<div class="viewer" id="viewer">
  <div class="serp-container">
    ${hasGazeplot
        ? `<img class="gazeplot-img" src="${gazeplotRelPath}" />`
        : `<iframe class="serp-iframe" src="${serpRelPath}" scrolling="no"></iframe>`}
    <svg class="scanpath-svg" id="scanpath-svg" xmlns="http://www.w3.org/2000/svg"
         width="${screenW}" height="${maxY}" viewBox="0 0 ${screenW} ${maxY}"></svg>
    <div class="foveal-ring" id="foveal-ring"></div>
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
  <span><a href="https://github.com/andyed/scrutinizer">Scrutinizer rendering</a></span>
  <span>Position: <span class="val" id="info-pos">—</span></span>
  <span>Duration: <span class="val" id="info-dur">—</span></span>
  <span>Fixations: <span class="val" id="info-seen">0</span></span>
  ${click ? `<span>Click: <span class="val">(${Math.round(click.x)}, ${Math.round(click.y)})</span></span>` : ''}
</div>
<script>
const F=${JSON.stringify(fixations)},CK=${JSON.stringify(click)},FR=${fovealR},SW=${screenW},N=${N},
T0=${T0},TD=${TOTAL_DUR},MND=${minD},MXD=${maxD};
const rF=d=>8+(d-MND)/(MXD-MND+1)*22;
const cF=(i,n)=>{const t=n>1?i/(n-1):0;return\`rgb(\${Math.round(50+205*t)},\${Math.round(50+100*(1-Math.abs(t-.5)*2))},\${Math.round(255-205*t)})\`};
const svg=document.getElementById('scanpath-svg'),ph=document.getElementById('playhead'),
fr=document.getElementById('foveal-ring'),vw=document.getElementById('viewer'),
lt=document.getElementById('lines-toggle'),nt=document.getElementById('numbers-toggle'),
tt=document.getElementById('timeline-track');
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
if(pl&&ci>=0){const f=F[ci];fr.style.display='block';fr.style.left=f.x+'px';fr.style.top=f.y+'px';
const vr=vw.getBoundingClientRect(),fy=f.y-vw.scrollTop;if(fy<100||fy>vr.height-100)vw.scrollTo({top:f.y-vr.height/2,behavior:'smooth'})}else fr.style.display='none';
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
document.getElementById('play-btn').classList.toggle('active',pl);if(pl){if(ci>=N-1)ci=-1;pn()}else{clearTimeout(pt);fr.style.display='none';ci=N-1;uv()}}
function pn(){if(!pl)return;const n=ci+1;if(n>=N){pl=false;document.getElementById('play-btn').textContent='▶ Play';fr.style.display='none';ci=N-1;uv();return}
sf(n);pt=setTimeout(pn,Math.max(100,F[n].d*.5))}
document.getElementById('play-btn').addEventListener('click',tp);
document.getElementById('reset-btn').addEventListener('click',()=>{pl=false;clearTimeout(pt);document.getElementById('play-btn').textContent='▶ Play';ci=N-1;uv();vw.scrollTo({top:0})});
uv();
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
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 2em 1em; background: #111; color: #eee; }
h1 { font-size: 1.6em; margin-bottom: 0.3em; }
h1 a { color: #ff9933; text-decoration: none; }
.subtitle { color: #aaa; margin-bottom: 1.5em; line-height: 1.5; }
.subtitle a { color: #6af; text-decoration: none; }
.trial { margin: 0.6em 0; padding: 0.8em 1em; background: #1a1a1a; border-radius: 6px; border-left: 3px solid #333; transition: border-color 0.2s; }
.trial:hover { border-left-color: #ff9933; }
.trial a { color: #eee; text-decoration: none; font-weight: 600; font-size: 0.95em; }
.trial .tag { color: #ff9933; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; }
.trial .query { color: #aaa; font-size: 0.85em; margin-top: 2px; }
.trial .meta { color: #666; font-size: 0.8em; margin-top: 2px; }
kbd { background: #333; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; color: #ccc; }
.controls-help { color: #888; font-size: 0.85em; margin-bottom: 1.5em; }
footer { margin-top: 2em; padding-top: 1em; border-top: 1px solid #333; color: #666; font-size: 0.8em; }
footer a { color: #888; }
</style></head><body>
<h1><a href="https://github.com/andyed/scrutinizer">Scrutinizer</a> × AdSERP</h1>
<p class="subtitle">
  Interactive scanpath replays of eye-tracking data from the
  <a href="https://doi.org/10.1145/3726302.3730325">AdSERP dataset</a>,
  rendered through Scrutinizer's neuroscience-based foveated vision simulation
  (LGN/V1/DoG peripheral degradation with infinite visual memory).
</p>
<p class="controls-help">
  <kbd>←</kbd><kbd>→</kbd> step &middot; <kbd>Space</kbd> play/pause &middot; drag timeline to scrub
</p>
${results.map(r => `<div class="trial">
  <span class="tag">${r.tag.replace(/_/g, ' ')}</span>
  <div><a href="${r.id}.html">${r.id}</a></div>
  <div class="query">"${r.query}"</div>
  <div class="meta">${r.n} fixations${r.hasGazeplot ? ' · Scrutinizer rendered' : ''}</div>
</div>`).join('\n')}
<footer>
  <a href="https://github.com/andyed/scrutinizer">Scrutinizer</a> ·
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
