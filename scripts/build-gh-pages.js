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
const ANCHOR_DIR = path.join(ROOT, 'fixation-anchors');
const LAYOUT_DIR = path.join(ROOT, 'layout-freeze');
const GAZEPLOT_DIR = path.join(SCRUTINIZER, 'output', 'adserp-fullpage-gazeplots');
const SITE_DIR = path.join(ROOT, 'site');

// Clean site structure — preserve explainer/ and other standalone subdirectories
const preserveDirs = new Set(['explainer']);
if (fs.existsSync(SITE_DIR)) {
    for (const entry of fs.readdirSync(SITE_DIR)) {
        if (preserveDirs.has(entry)) continue;
        const p = path.join(SITE_DIR, entry);
        fs.rmSync(p, { recursive: true, force: true });
    }
}
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
    { tag: 'clean_serp',          trial_id: 'p020-b6-t10', query: 'buy acdelco acdelco 18a753 brake rotor' },
    { tag: 'clean_serp_2',        trial_id: 'p047-b2-t6',  query: 'buy stens solid state module briggs 397358' },
    // ── Behavioral strategy groups (3 per) ──
    { tag: 'satisficer', trial_id: 'p031-b5-t2', query: 'buy ganz rooster oil bottle by walterdrake' },
    { tag: 'satisficer', trial_id: 'p049-b2-t6', query: 'buy robert sorby robert sorby 410 sandmaster' },
    { tag: 'satisficer', trial_id: 'p017-b3-t3', query: 'buy hampton direct microwave egg poacher' },
    { tag: 'optimizer', trial_id: 'p021-b6-t2', query: 'buy clauss clauss 18429 titanium wire cutters' },
    { tag: 'optimizer', trial_id: 'p019-b6-t5', query: 'buy dolce gabbana dolce gabbana dg2075 sunglasses' },
    { tag: 'optimizer', trial_id: 'p021-b2-t10', query: 'buy home win arsenal fc fleece blanket' },
    { tag: 'instant_decision', trial_id: 'p013-b2-t3', query: 'buy romantic music for cello' },
    { tag: 'instant_decision', trial_id: 'p026-b4-t9', query: 'buy shimano shimano bhaltair reel bag medium' },
    { tag: 'instant_decision', trial_id: 'p032-b4-t9', query: 'buy epakitin epakitin powder 180gm' },
    { tag: 'regressive', trial_id: 'p004-b2-t4', query: 'buy acdelco acdelco 6k458 fan belt' },
    { tag: 'regressive', trial_id: 'p007-b6-t8', query: 'buy dermalogica dermalogica active moist 3 5oz' },
    { tag: 'regressive', trial_id: 'p035-b1-t8', query: 'buy imak imak arthritis gloves small' },
    { tag: 'forward_only', trial_id: 'p014-b6-t8', query: 'buy alessi alessi birillo toothbrush holder' },
    { tag: 'forward_only', trial_id: 'p034-b2-t3', query: 'buy portal' },
    { tag: 'forward_only', trial_id: 'p027-b3-t6', query: 'buy denso 673 1306 ignition coil' },
    { tag: 'scanner', trial_id: 'p038-b5-t9', query: 'buy copernicus piezo electric rocks' },
    { tag: 'scanner', trial_id: 'p010-b4-t7', query: 'buy vdo vdo pm151 blower motor' },
    { tag: 'scanner', trial_id: 'p031-b3-t9', query: 'buy timken timken 1932s seal' },
    { tag: 'deep_click', trial_id: 'p024-b3-t5', query: 'buy lego lego dinosaurs mosasaurus 6721' },
    { tag: 'deep_click', trial_id: 'p035-b4-t1', query: 'buy spy spy optic discord square sunglasses' },
    { tag: 'deep_click', trial_id: 'p024-b5-t5', query: 'buy m a c mac lipglass prrr' },
];

async function main() {

console.log(`Building site with ${trials.length} trials...\n`);

// Step 1: Pre-render SERP screenshots at screenWidth (1280px).
// FPOGX/FPOGY are "relative to the top-left corner of the screenshot in pixels"
// (AdSERP docs). The screenshot is at screenWidth, not windowWidth.
console.log('  Rendering SERP screenshots at screen width (1280px)...');
const browser = await chromium.launch();

const trialDocHeights = {};
for (const trial of trials) {
    const serpSrc = path.join(DATA_DIR, 'serps', `${trial.trial_id}.html`);
    if (!fs.existsSync(serpSrc)) continue;
    const metaXml = fs.readFileSync(path.join(DATA_DIR, 'trial-metadata', `${trial.trial_id}.xml`), 'utf8');
    const get = (tag) => { const m = metaXml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)); return m ? m[1].trim() : ''; };
    const scrW = parseInt(get('screen').split('x')[0]) || 1280;
    const scrH = parseInt(get('screen').split('x')[1]) || 1024;

    const playwrightCtx = await browser.newContext({ viewport: { width: scrW, height: scrH } });
    const page = await playwrightCtx.newPage();
    await page.goto(`file://${path.resolve(serpSrc)}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    // Inject layout freeze: force original element dimensions so layout holds
    // even when external resources (images, Maps tiles) fail to load
    const layoutPath = path.join(LAYOUT_DIR, `${trial.trial_id}.json`);
    if (fs.existsSync(layoutPath)) {
        const layoutEntries = JSON.parse(fs.readFileSync(layoutPath, 'utf8'));
        const cssRules = layoutEntries.map(e =>
            `${e.selector} { min-width: ${e.width}px !important; min-height: ${e.height}px !important; max-height: ${e.height}px !important; }`
        ).join('\n');
        await page.addStyleTag({ content: cssRules });
        await page.waitForTimeout(200);
    }

    const docHeight = await page.evaluate(() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight));
    await page.setViewportSize({ width: scrW, height: docHeight });
    await page.waitForTimeout(300);
    await page.screenshot({
        path: path.join(SITE_DIR, 'serp-renders', `${trial.trial_id}.png`),
        clip: { x: 0, y: 0, width: scrW, height: docHeight }
    });
    trialDocHeights[trial.trial_id] = docHeight;

    // Resolve DOM anchors on this page (at the render width) if available
    const anchorPath = path.join(ANCHOR_DIR, `${trial.trial_id}.json`);
    if (fs.existsSync(anchorPath)) {
        const anchors = JSON.parse(fs.readFileSync(anchorPath, 'utf8'));
        const selectors = anchors.map(a => a ? { selector: a.selector, offsetX: a.offsetX, offsetY: a.offsetY } : null);

        const resolved = await page.evaluate(async (items) => {
            const results = [];
            for (const item of items) {
                if (!item) { results.push(null); continue; }
                const el = document.querySelector(item.selector);
                if (!el) { results.push(null); continue; }
                // Scroll to element to ensure layout is computed
                el.scrollIntoView({ block: 'center' });
                await new Promise(r => setTimeout(r, 10));
                const rect = el.getBoundingClientRect();
                results.push({
                    x: Math.round((rect.left + item.offsetX) * 10) / 10,
                    y: Math.round((rect.top + window.scrollY + item.offsetY) * 10) / 10,
                });
            }
            return results;
        }, selectors);

        // Store resolved coordinates per trial for the processing loop
        trial._resolvedAnchors = resolved;
        const count = resolved.filter(r => r).length;
        console.log(`    ${trial.trial_id} (${scrW}x${docHeight}) — ${count}/${anchors.length} anchors resolved`);
    } else {
        console.log(`    ${trial.trial_id} (${scrW}x${docHeight})`);
    }

    await page.close();
    await playwrightCtx.close();
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

    // Load trial data via the adserp-importer (scroll-corrected coordinates)
    const adserp = require(path.join(SCRUTINIZER, 'renderer', 'scanpath', 'importers', 'adserp-importer'));
    const trialData = adserp.loadTrial(DATA_DIR, id);
    const meta = trialData.meta;
    const screenW = meta.screenWidth;
    const screenH = meta.screenHeight;
    const windowW = meta.windowWidth;
    const windowH = meta.windowHeight;
    const docH = meta.documentHeight;
    const query = meta.query;

    // Use DOM-resolved coordinates if available (resolved at the render width).
    // Falls back to raw screen-space pixel coords.
    const resolvedAnchors = trial._resolvedAnchors || null;

    const fixations = trialData.fixations.map((f, i) => {
        const resolved = resolvedAnchors && resolvedAnchors[i];
        const x = resolved ? resolved.x : f.x;
        const y = resolved ? resolved.y : (f.pageY !== undefined ? f.pageY : f.y);
        return {
            t: f.tStart + trialData.fixations[0].tStart,
            x: Math.round(x * 10) / 10,
            y: Math.round(y * 10) / 10,
            d: Math.round(f.tEnd - f.tStart)
        };
    }).filter(f => f.d > 0);

    // Compute inter-fixation saccade displacement (px)
    // vx/vy = displacement from previous fixation to this one
    // Sign: vy positive = downward (forward scan), negative = upward (regression)
    for (let i = 0; i < fixations.length; i++) {
        if (i === 0) {
            fixations[i].vx = 0;
            fixations[i].vy = 0;
        } else {
            fixations[i].vx = Math.round(fixations[i].x - fixations[i - 1].x);
            fixations[i].vy = Math.round(fixations[i].y - fixations[i - 1].y);
        }
    }

    // Load per-fixation pupil data if available
    const pupilPath = path.join(DATA_DIR, 'fixation-pupil', `${id}.json`);
    let hasPupil = false;
    if (fs.existsSync(pupilPath)) {
        const pupilData = JSON.parse(fs.readFileSync(pupilPath, 'utf8'));
        fixations.forEach((f, i) => {
            if (pupilData[i] && pupilData[i].mean_pd != null) {
                f.pd = pupilData[i].mean_pd;
                f.pdc = pupilData[i].pd_change;
            }
        });
        hasPupil = fixations.some(f => f.pd != null);
    }

    // Load per-fixation Butterworth LF/HF cognitive load if available
    const lfhfPath = path.join(DATA_DIR, 'fixation-lfhf-demo.json');
    let hasLFHF = false;
    if (fs.existsSync(lfhfPath)) {
        const lfhfAll = JSON.parse(fs.readFileSync(lfhfPath, 'utf8'));
        if (lfhfAll[id]) {
            const lfhfData = lfhfAll[id];
            fixations.forEach((f, i) => {
                if (lfhfData[i] != null) f.lfhf = lfhfData[i];
            });
            hasLFHF = fixations.some(f => f.lfhf != null);
        }
    }

    // Attach scroll position at each fixation time
    const scrollTL = trialData.scrollTimeline || [];
    if (scrollTL.length > 0) {
        fixations.forEach(f => {
            const ft = f.t - fixations[0].t; // relative time matching scrollTimeline
            let sy = 0;
            for (const s of scrollTL) {
                if (s.t <= ft) sy = s.scrollY;
                else break;
            }
            f.scr = Math.round(sy);
        });
    }

    // Load per-fixation saliency data if available
    const salPath = path.join(DATA_DIR, 'saliency', `${id}.json`);
    let hasSaliency = false;
    if (fs.existsSync(salPath)) {
        const salData = JSON.parse(fs.readFileSync(salPath, 'utf8'));
        const salCoords = salData.coordinates || [];
        fixations.forEach((f, i) => {
            if (salCoords[i] && salCoords[i].saliency_mean != null) {
                f.sal = salCoords[i].saliency_mean;
                f.cong = salCoords[i].congestion_mean;
            }
        });
        hasSaliency = fixations.some(f => f.sal != null);
    }

    // Mouse events: already in page-space from evtrack (pageX/pageY).
    // No Y scaling needed — pageY coordinates match the windowW layout.
    const mouseTimeline = trialData.mouseTimeline || [];
    const T0_offset = trialData.fixations.length > 0 ? trialData.fixations[0].tStart : 0;
    const mouseEvents = mouseTimeline
        .filter(m => ['mousemove','mouseover','click','mousedown','mouseup'].includes(m.event))
        .map(m => ({ t: m.t - T0_offset, x: m.x, y: m.y, e: m.event }));

    // Click: last click event — convert from importer viewport-space to page-space.
    // The adserp-importer transforms mouse Y as: (rawScreenY - scrollY) * ry
    //   where ry = screenH/windowH ≈ 0.9
    // Raw screen Y is viewport-relative. Page-space = rawScreenY + scrollY.
    // So: pageY = c.y / ry + 2 * scrollAtClick
    //   because c.y/ry recovers (rawY - scroll), then + 2*scroll = rawY + scroll = pageY
    const scrollTimeline = trialData.scrollTimeline || [];
    const clickEvts = mouseTimeline.filter(m => m.event === 'click');
    let click = null;
    if (clickEvts.length > 0) {
        const c = clickEvts[clickEvts.length - 1];
        const ry = screenH / windowH;
        let scrollAtClick = 0;
        for (const s of scrollTimeline) {
            if (s.t <= c.t) scrollAtClick = s.scrollY;
            else break;
        }
        click = { x: c.x, y: c.y / ry + 2 * scrollAtClick };
    }

    // SERP render is at windowW × docHeight (original layout, no reflow).
    // Use the Playwright-measured docHeight as authoritative.
    const serpDocH = trialDocHeights[id] || docH;
    const primaryImgH = serpDocH;
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
#serp-img, #gazeplot-img { width: ${screenW}px; height: ${primaryImgH}px; display: block; }
#gazeplot-img { position: absolute; top: 0; left: 0; z-index: 1; }
#prog-canvas { position: absolute; top: 0; left: 0; z-index: 5; pointer-events: none; display: none; }
.scanpath-svg { position: absolute; top: 0; left: 0; z-index: 10; pointer-events: none; }
.foveal-ring { position: absolute; z-index: 11; pointer-events: none; border: 2px solid rgba(255,255,255,0.7);
  border-radius: 50%; width: ${fovealR*2}px; height: ${fovealR*2}px; transform: translate(-50%, -50%);
  box-shadow: 0 0 20px rgba(255,255,255,0.3); transition: left 0.08s, top 0.08s; display: none; }
.mouse-cursor { position: absolute; z-index: 999; pointer-events: none; display: none;
  width: 20px; height: 20px; transition: left 0.03s linear, top 0.03s linear; }
.mouse-cursor svg { width: 20px; height: 28px; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5)); }
.mouse-cursor.clicking svg path { fill: #ff3333; }
.timeline { width: ${screenW}px; background: #1a1a1a; padding: 6px 16px; border-top: 1px solid #333; }
.timeline-tracks { position: relative; cursor: pointer; user-select: none; -webkit-user-select: none; }
.timeline-row { display: flex; align-items: stretch; height: 22px; margin-bottom: 1px; }
.timeline-row:last-child { margin-bottom: 0; }
.timeline-label { width: 60px; flex-shrink: 0; font-size: 9px; font-weight: 700; display: flex; align-items: center; padding-right: 6px; text-align: right; justify-content: flex-end; text-transform: uppercase; letter-spacing: 0.5px; position: relative; z-index: 3; background: #1a1a1a; }
.timeline-label.lbl-saliency { color: #ffa040; text-shadow: 0 0 6px rgba(255,160,64,0.4); }
.timeline-label.lbl-pupil { color: #40e0ff; text-shadow: 0 0 6px rgba(64,224,255,0.4); }
.timeline-label.lbl-lfhf { color: #f59e0b; text-shadow: 0 0 6px rgba(245,158,11,0.4); }
.timeline-label.lbl-gaze-x { color: #e0e050; text-shadow: 0 0 6px rgba(224,224,80,0.4); }
.timeline-label.lbl-gaze-y { color: #50c0e0; text-shadow: 0 0 6px rgba(80,192,224,0.4); }
.timeline-label.lbl-scroll { color: #44dd66; text-shadow: 0 0 6px rgba(68,221,102,0.4); }
.timeline-label.lbl-dwell { color: #c8a8f0; text-shadow: 0 0 6px rgba(200,168,240,0.4); }
.timeline-track { position: relative; flex: 1; background: #222; border-radius: 2px; overflow: hidden; }
.timeline-ticks { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
.timeline-tick { position: absolute; top: 0; min-width: 2px; height: 100%; }
.timeline-playhead { position: absolute; top: 0; width: 2px; height: 100%; background: #ff4444; z-index: 2; pointer-events: none; }
.timeline-info { display: flex; justify-content: space-between; margin-top: 4px; font-size: 11px; color: #aaa; padding-left: 64px; }
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
    ${hasGazeplot ? `<button class="btn" id="mode-btn">Original</button>` : ''}
    <label id="ws-group">Window <input type="range" id="window-size" min="1" max="${N}" value="${N}" style="width:80px;vertical-align:middle;"> <span id="ws-label">All</span></label>
    <button class="btn active" id="gaze-btn">Gaze Points</button>
    <button class="btn" id="color-btn">Color: Sequence</button>
    <button class="btn" id="play-btn">&#9654; Play</button>
    <button class="btn" id="reset-btn">Reset</button>
  </div>
</div>
<div class="viewer" id="viewer">
  <div class="serp-container">
    <img id="serp-img" src="${serpRenderRelPath}" width="${screenW}" height="${primaryImgH}" />
    ${hasGazeplot ? `<img id="gazeplot-img" src="${gazeplotRelPath}" />` : ''}
    <canvas id="prog-canvas" width="${screenW}" height="${primaryImgH}"></canvas>
    <svg class="scanpath-svg" id="scanpath-svg" xmlns="http://www.w3.org/2000/svg"
         width="${screenW}" height="${primaryImgH}" viewBox="0 0 ${screenW} ${primaryImgH}"></svg>
    <div class="foveal-ring" id="foveal-ring"></div>
    <div class="mouse-cursor" id="mouse-cursor"><svg viewBox="0 0 20 28"><path d="M0,0 L0,22 L5.5,17 L10,28 L14,26 L9,16 L16,16 Z" fill="#ff9933" stroke="#000" stroke-width="1"/></svg></div>
  </div>
</div>
<div class="timeline">
  <div class="timeline-tracks" id="timeline-tracks">
    ${hasSaliency ? `<div class="timeline-row">
      <div class="timeline-label lbl-saliency">Saliency</div>
      <div class="timeline-track" id="track-saliency">
        <div class="timeline-ticks" id="ticks-saliency"></div>
      </div>
    </div>` : ''}
    ${hasPupil ? `<div class="timeline-row">
      <div class="timeline-label lbl-pupil">Pupil</div>
      <div class="timeline-track" id="track-pupil">
        <div class="timeline-ticks" id="ticks-pupil"></div>
      </div>
    </div>` : ''}
    ${hasLFHF ? `<div class="timeline-row">
      <div class="timeline-label lbl-lfhf">Pupil LF/HF</div>
      <div class="timeline-track" id="track-lfhf">
        <div class="timeline-ticks" id="ticks-lfhf"></div>
      </div>
    </div>` : ''}
    <div class="timeline-row">
      <div class="timeline-label lbl-gaze-x">Gaze ΔX</div>
      <div class="timeline-track" id="track-gaze-vx">
        <div class="timeline-ticks" id="ticks-gaze-vx"></div>
      </div>
    </div>
    <div class="timeline-row">
      <div class="timeline-label lbl-gaze-y">Gaze ΔY</div>
      <div class="timeline-track" id="track-gaze-vy">
        <div class="timeline-ticks" id="ticks-gaze-vy"></div>
      </div>
    </div>
    <div class="timeline-row">
      <div class="timeline-label lbl-scroll">Scroll</div>
      <div class="timeline-track" id="track-scroll">
        <div class="timeline-ticks" id="ticks-scroll"></div>
      </div>
    </div>
    <div class="timeline-row">
      <div class="timeline-label lbl-dwell">Dwell</div>
      <div class="timeline-track" id="track-dwell">
        <div class="timeline-ticks" id="ticks-dwell"></div>
      </div>
    </div>
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
<div style="width:${screenW}px;padding:6px 16px;background:#1a1a1a;font-size:10px;color:#666;border-top:1px solid #222;">
  Fixation overlay alignment: median &lt;13px offset, max ~45px at page bottom. SERP HTML is re-rendered locally; element heights differ from original Chrome 110/Windows session due to external resource loading (Maps tiles, product images). Fixation coordinates (FPOGX/FPOGY) from <a href="https://github.com/kayhan-latifzadeh/AdSERP" style="color:#888;">AdSERP dataset</a> are pixel-verified accurate against synthetic test pages.
</div>
<script>
const F=${JSON.stringify(fixations)},CK=${JSON.stringify(click)},ME=${JSON.stringify(mouseEvents)},FR=${fovealR},SW=${screenW},N=${N},
T0=${T0},TD=${TOTAL_DUR},MND=${minD},MXD=${maxD},
SERP_SRC='${serpRenderRelPath}',
GAZEPLOT_SRC=${hasGazeplot ? `'${gazeplotRelPath}'` : 'null'};
const rF=d=>8+(d-MND)/(MXD-MND+1)*22;
const cF=(i,n)=>{const t=n>1?i/(n-1):0;return\`rgb(\${Math.round(50+205*t)},\${Math.round(50+100*(1-Math.abs(t-.5)*2))},\${Math.round(255-205*t)})\`};
// Cognitive load color: blue (constricted/low load) → red (dilated/high load)
const PDC=F.filter(f=>f.pdc!=null).map(f=>f.pdc);
const PDC_MIN=PDC.length?Math.min(...PDC):0,PDC_MAX=PDC.length?Math.max(...PDC):1;
// Pupil color: dark cyan → bright cyan
const cPD=(pdc)=>{if(pdc==null)return'#333';const t=(pdc-PDC_MIN)/(PDC_MAX-PDC_MIN+0.001);return\`rgb(\${Math.round(10+30*t)},\${Math.round(40+200*t)},\${Math.round(60+195*t)})\`};
// Saliency color: black → bright orange (unmistakable)
const SAL=F.filter(f=>f.sal!=null).map(f=>f.sal);
const SAL_MIN=SAL.length?Math.min(...SAL):0,SAL_MAX=SAL.length?Math.max(...SAL):1;
const cSal=(s)=>{if(s==null)return'#333';const t=Math.max(0,Math.min(1,(s-SAL_MIN)/(SAL_MAX-SAL_MIN+0.001)));
return\`rgb(\${Math.round(40+215*t)},\${Math.round(20+140*t)},\${Math.round(10+20*t)})\`};
let colorMode='sequence'; // 'sequence', 'load', or 'saliency'
const COLOR_MODES=['sequence','load','lfhf','saliency'];
function getColor(i){if(colorMode==='load'&&F[i].pdc!=null)return cPD(F[i].pdc);if(colorMode==='lfhf'&&F[i].lfhf!=null)return cLFHF(F[i].lfhf);if(colorMode==='saliency'&&F[i].sal!=null)return cSal(F[i].sal);return cF(i,N)}
const svg=document.getElementById('scanpath-svg'),ph=document.getElementById('playhead'),
fr=document.getElementById('foveal-ring'),mc=document.getElementById('mouse-cursor'),
vw=document.getElementById('viewer'),
ws=document.getElementById('window-size'),wl=document.getElementById('ws-label'),
tt=document.getElementById('timeline-tracks');
let ci=N-1,pl=false,pt=null;
// Progressive foveation state
const pc=document.getElementById('prog-canvas');
const pCtx=pc?pc.getContext('2d'):null;
let bgMode=GAZEPLOT_SRC?'gazeplot':'serp';
let gpImg=null,gpLoaded=false;
if(GAZEPLOT_SRC){gpImg=new Image();gpImg.onload=()=>{gpLoaded=true;if(bgMode==='progressive')drawProg()};gpImg.src=GAZEPLOT_SRC}
function drawProg(){if(!pCtx||!gpImg||!gpLoaded)return;
const w=pc.width,h=pc.height;pCtx.clearRect(0,0,w,h);
pCtx.globalCompositeOperation='source-over';
for(let i=0;i<=ci;i++){const f=F[i],r=FR*2.5;
const g=pCtx.createRadialGradient(f.x,f.y,0,f.x,f.y,r);
g.addColorStop(0,'rgba(255,255,255,1)');g.addColorStop(0.5,'rgba(255,255,255,0.7)');g.addColorStop(1,'rgba(255,255,255,0)');
pCtx.fillStyle=g;pCtx.beginPath();pCtx.arc(f.x,f.y,r,0,Math.PI*2);pCtx.fill()}
pCtx.globalCompositeOperation='source-in';
pCtx.drawImage(gpImg,0,0,w,h);pCtx.globalCompositeOperation='source-over'}
const ns='http://www.w3.org/2000/svg';
function se(t,a){const e=document.createElementNS(ns,t);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);return e}
// ── Build multi-track timeline ──────────────────────────────────────
function buildTrack(containerId, colorFn, valueFn) {
    const el = document.getElementById(containerId);
    if (!el) return [];
    const ticks = [];
    F.forEach((f, i) => {
        const t = document.createElement('div');
        t.className = 'timeline-tick';
        t.style.left = (N > 1 ? (f.t - T0) / TD * 100 : 0) + '%';
        t.style.width = Math.max(0.5, f.d / TD * 100) + '%';
        t.style.background = colorFn(i);
        const v = valueFn ? valueFn(i) : 1;
        const hPct = Math.max(15, v * 100);
        t.style.height = hPct + '%';
        t.style.bottom = '0';
        t.style.top = 'auto';
        t.style.opacity = '.8';
        el.appendChild(t);
        ticks.push(t);
    });
    return ticks;
}
// Dwell: height encodes duration (taller = longer fixation)
function buildDwellTrack() {
    const el = document.getElementById('ticks-dwell');
    if (!el) return [];
    const ticks = [];
    F.forEach((f, i) => {
        const t = document.createElement('div');
        t.className = 'timeline-tick';
        t.style.left = (N > 1 ? (f.t - T0) / TD * 100 : 0) + '%';
        t.style.width = Math.max(0.5, f.d / TD * 100) + '%';
        const hPct = Math.min(100, 20 + f.d / 8);
        t.style.height = hPct + '%';
        t.style.bottom = '0';
        t.style.top = 'auto';
        t.style.background = '#b8a0d8';
        t.style.opacity = '.6';
        el.appendChild(t);
        ticks.push(t);
    });
    return ticks;
}
const tkSal = buildTrack('ticks-saliency', i => cSal(F[i].sal), i => {
    if(F[i].sal==null) return 0.15;
    return (F[i].sal - SAL_MIN) / (SAL_MAX - SAL_MIN + 0.001);
});
const tkPup = buildTrack('ticks-pupil', i => cPD(F[i].pdc), i => {
    if(F[i].pdc==null) return 0.15;
    return (F[i].pdc - PDC_MIN) / (PDC_MAX - PDC_MIN + 0.001);
});
// LF/HF cognitive load: amber (low load) → red (high load)
const LFHF=F.filter(f=>f.lfhf!=null).map(f=>f.lfhf);
const LFHF_MIN=LFHF.length?Math.min(...LFHF):0,LFHF_MAX=LFHF.length?Math.max(...LFHF):1;
const cLFHF=(v)=>{if(v==null)return'#333';const t=Math.max(0,Math.min(1,(v-LFHF_MIN)/(LFHF_MAX-LFHF_MIN+0.001)));
return\`rgb(\${Math.round(200+55*t)},\${Math.round(160-110*t)},\${Math.round(40-30*t)})\`};
const tkLFHF = buildTrack('ticks-lfhf', i => cLFHF(F[i].lfhf), i => {
    if(F[i].lfhf==null) return 0.15;
    return (F[i].lfhf - LFHF_MIN) / (LFHF_MAX - LFHF_MIN + 0.001);
});
// Scroll: height = normalized scroll position, color = direction
function buildScrollTrack() {
    const el = document.getElementById('ticks-scroll');
    if (!el) return [];
    const ticks = [];
    const scrVals = F.filter(f => f.scr != null).map(f => f.scr);
    const scrMax = scrVals.length ? Math.max(...scrVals, 1) : 1;
    F.forEach((f, i) => {
        const t = document.createElement('div');
        t.className = 'timeline-tick';
        t.style.left = (N > 1 ? (f.t - T0) / TD * 100 : 0) + '%';
        t.style.width = Math.max(0.5, f.d / TD * 100) + '%';
        const sv = f.scr != null ? f.scr : 0;
        const hPct = Math.max(10, (sv / scrMax) * 100);
        t.style.height = hPct + '%';
        t.style.bottom = '0';
        t.style.top = 'auto';
        // Color: green=forward, red=regression
        const prev = i > 0 && F[i-1].scr != null ? F[i-1].scr : sv;
        const delta = sv - prev;
        if (delta < -5) t.style.background = '#ef4444'; // regression
        else if (delta > 5) t.style.background = '#22c55e'; // forward
        else t.style.background = '#666'; // stationary
        t.style.opacity = '.8';
        el.appendChild(t);
        ticks.push(t);
    });
    return ticks;
}
// Gaze velocity tracks: displacement between consecutive fixations
// Height = |displacement| normalized per-trial; color encodes direction
const VX=F.map(f=>f.vx||0),VY=F.map(f=>f.vy||0);
const VX_MAX=Math.max(1,...VX.map(Math.abs)),VY_MAX=Math.max(1,...VY.map(Math.abs));
// ΔX color: yellow for rightward, blue-gray for leftward
const cVX=(v)=>{if(v==null)return'#333';const t=v/VX_MAX;
if(t>=0)return\`rgb(\${Math.round(80+175*t)},\${Math.round(80+175*t)},\${Math.round(30+20*t)})\`;
return\`rgb(\${Math.round(50+30*(-t))},\${Math.round(50+50*(-t))},\${Math.round(80+80*(-t))})\`};
// ΔY color: teal for downward (forward), red-orange for upward (regression)
const cVY=(v)=>{if(v==null)return'#333';const t=v/VY_MAX;
if(t>=0)return\`rgb(\${Math.round(30+20*t)},\${Math.round(60+140*t)},\${Math.round(80+140*t)})\`;
return\`rgb(\${Math.round(80+175*(-t))},\${Math.round(40+30*(-t))},\${Math.round(20+20*(-t))})\`};
const tkGazeVX = buildTrack('ticks-gaze-vx', i => cVX(F[i].vx), i => Math.abs(F[i].vx||0)/VX_MAX);
const tkGazeVY = buildTrack('ticks-gaze-vy', i => cVY(F[i].vy), i => Math.abs(F[i].vy||0)/VY_MAX);
const tkScroll = buildScrollTrack();
const tkDwell = buildDwellTrack();
const tkE = tkSal; // backward compat for recolor
const lE=[],cE=[],tE=[];
for(let i=0;i<N;i++){const f=F[i],r=rF(f.d),c=cF(i,N);
if(i>0){const p=F[i-1];const l=se('line',{x1:p.x,y1:p.y,x2:f.x,y2:f.y,stroke:c,'stroke-width':1.5,'stroke-opacity':.4});svg.appendChild(l);lE.push(l)}else lE.push(null);
const cr=se('circle',{cx:f.x,cy:f.y,r,fill:c,'fill-opacity':.25,stroke:c,'stroke-width':2,'stroke-opacity':.8});svg.appendChild(cr);cE.push(cr);
const fs=Math.max(9,Math.min(14,r));const tx=se('text',{x:f.x,y:f.y,'text-anchor':'middle','dominant-baseline':'central','font-family':'monospace','font-weight':'bold','font-size':fs,fill:'white',stroke:'rgba(0,0,0,.6)','stroke-width':2,'paint-order':'stroke'});tx.textContent=i+1;svg.appendChild(tx);tE.push(tx)}
if(CK){const s=se('polygon',{points:[0,-16,6,-4,16,-4,8,4,12,16,0,8,-12,16,-8,4,-16,-4,-6,-4].reduce((a,v,i)=>{a.push(i%2===0?CK.x+v:CK.y+v);return a},[]).join(','),fill:'#f00','fill-opacity':.5,stroke:'#f00','stroke-width':2});svg.appendChild(s);
const l=se('text',{x:CK.x+18,y:CK.y+4,'font-family':'monospace','font-weight':'bold','font-size':11,fill:'#f00',stroke:'white','stroke-width':2,'paint-order':'stroke'});l.textContent='CLICK';svg.appendChild(l)}
function uv(){const wn=parseInt(ws.value);
wl.textContent=wn>=N?'All':wn;
const lo=Math.max(0,ci-wn+1);
for(let i=0;i<N;i++){const v=i>=lo&&i<=ci;cE[i].style.display=v?'':'none';tE[i].style.display=v?'':'none';
if(lE[i])lE[i].style.display=(v&&i>lo)?'':'none';cE[i].setAttribute('stroke-width',pl&&i===ci?4:2);cE[i].setAttribute('stroke-opacity',pl&&i===ci?1:.8)}
if(ci>=0&&N>1){const tr=firstTrack.getBoundingClientRect(),tc=tt.getBoundingClientRect();const off=tr.left-tc.left;const pct=(F[ci].t-T0)/TD;ph.style.left=(off+pct*tr.width)+'px';}
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
document.getElementById('duration-label').textContent=((f.t-T0)/1000).toFixed(1)+'s / '+(TD/1000).toFixed(1)+'s'}
if(bgMode==='progressive')drawProg()}
function sf(i){ci=Math.max(-1,Math.min(N-1,i));uv();if(typeof pushHash==='function')pushHash()}
const firstTrack=tt.querySelector('.timeline-track');
let dr=false;function ts(e){const r=firstTrack.getBoundingClientRect(),p=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
let b=0;for(let i=0;i<N;i++)if(F[i].t<=T0+p*TD)b=i;sf(b)}
tt.addEventListener('mousedown',e=>{dr=true;ts(e)});document.addEventListener('mousemove',e=>{if(dr)ts(e)});document.addEventListener('mouseup',()=>{dr=false});
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'){sf(ci+1);e.preventDefault()}if(e.key==='ArrowLeft'){sf(ci-1);e.preventDefault()}
if(e.key===' '){tp();e.preventDefault()}if(e.key==='Home'){sf(0);e.preventDefault()}if(e.key==='End'){sf(N-1);e.preventDefault()}});
function tp(){pl=!pl;document.getElementById('play-btn').textContent=pl?'⏸ Pause':'▶ Play';
document.getElementById('play-btn').classList.toggle('active',pl);if(pl){if(ci>=N-1)ci=-1;pn()}else{clearTimeout(pt);fr.style.display='none';mc.style.display='none';uv()}}
function pn(){if(!pl)return;const n=ci+1;if(n>=N){pl=false;document.getElementById('play-btn').textContent='▶ Play';fr.style.display='none';mc.style.display='none';ci=N-1;uv();return}
sf(n);pt=setTimeout(pn,Math.max(100,F[n].d*.5))}
document.getElementById('play-btn').addEventListener('click',tp);
document.getElementById('reset-btn').addEventListener('click',()=>{pl=false;clearTimeout(pt);document.getElementById('play-btn').textContent='▶ Play';ws.value=N;ci=N-1;uv();vw.scrollTo({top:0})});
uv();
// Gaze points toggle
const gazeBtn=document.getElementById('gaze-btn');
let gazeVisible=true;
gazeBtn.addEventListener('click',()=>{gazeVisible=!gazeVisible;svg.style.display=gazeVisible?'':'none';gazeBtn.classList.toggle('active',gazeVisible);pushHash()});
// Color mode toggle (sequence vs cognitive load)
const colorBtn=document.getElementById('color-btn');
function recolor(){for(let i=0;i<N;i++){const c=getColor(i);
cE[i].setAttribute('fill',c);cE[i].setAttribute('stroke',c);
if(lE[i]){lE[i].setAttribute('stroke',c)}
if(tkE[i])tkE[i].style.background=c}}
const COLOR_LABELS={sequence:'Color: Sequence',load:'Color: Pupil Load',lfhf:'Color: Pupil LF/HF',saliency:'Color: Saliency'};
if(colorBtn){colorBtn.addEventListener('click',()=>{
const ci_cm=COLOR_MODES.indexOf(colorMode);colorMode=COLOR_MODES[(ci_cm+1)%COLOR_MODES.length];
colorBtn.textContent=COLOR_LABELS[colorMode];
colorBtn.classList.toggle('active',colorMode!=='sequence');
recolor();pushHash()})}
// Background mode controls
const modeBtn=document.getElementById('mode-btn');
const progBtn=document.getElementById('prog-btn');
const serpEl=document.getElementById('serp-img');
const gpEl=document.getElementById('gazeplot-img');
function setMode(m){bgMode=m;
// SERP img always visible (defines container height). Gazeplot + progressive canvas toggle on top.
if(m==='gazeplot'){if(gpEl)gpEl.style.display='';pc.style.display='none';modeBtn.textContent='Original';modeBtn.classList.remove('active');progBtn.classList.remove('active')}
else if(m==='serp'){if(gpEl)gpEl.style.display='none';pc.style.display='none';modeBtn.textContent='Foveated';modeBtn.classList.add('active');progBtn.classList.remove('active')}
else if(m==='progressive'){if(gpEl)gpEl.style.display='none';pc.style.display='block';modeBtn.textContent='Foveated';modeBtn.classList.remove('active');progBtn.classList.add('active');drawProg()}}
if(modeBtn){modeBtn.addEventListener('click',()=>{setMode(bgMode==='gazeplot'?'serp':'gazeplot');pushHash()})}
if(progBtn){progBtn.addEventListener('click',()=>{const next=bgMode==='progressive'?'gazeplot':'progressive';setMode(next);progBtn.textContent=next==='progressive'?'Cumulative':'Progressive';pushHash()})}
// Hash permalinks: #fix=50&w=20&mode=progressive
function pushHash(){const p=[];
if(!ws.disabled)p.push('fix='+(ci+1));
if(!ws.disabled)p.push('w='+ws.value);
if(bgMode!=='gazeplot')p.push('mode='+bgMode);
if(!gazeVisible)p.push('gaze=off');
if(colorMode!=='sequence')p.push('color='+colorMode);
history.replaceState(null,'','#'+p.join('&'))}
function readHash(){const h=location.hash.slice(1);if(!h)return;
const p={};h.split('&').forEach(kv=>{const[k,v]=kv.split('=');p[k]=v});
if(p.mode)setMode(p.mode);
if(p.w){ws.value=p.w;wl.textContent=p.w}
if(p.fix){ci=Math.max(0,Math.min(N-1,parseInt(p.fix)-1));uv()}
if(p.gaze==='off'){gazeVisible=false;svg.style.display='none';gazeBtn.classList.remove('active')}
if(p.color&&COLOR_MODES.includes(p.color)){colorMode=p.color;colorBtn.textContent=COLOR_LABELS[colorMode];colorBtn.classList.toggle('active',colorMode!=='sequence');recolor()}}
readHash();
ws.addEventListener('input',()=>{const wn=parseInt(ws.value);if(ci>=N-1||ci<wn)ci=Math.min(wn-1,N-1);uv();pushHash()});
</script></body></html>`;

    fs.writeFileSync(path.join(SITE_DIR, `${id}.html`), html);
    const sizeMB = hasGazeplot ? (fs.statSync(gazeplotSrc).size / 1024 / 1024).toFixed(1) : '—';
    console.log(`  ✓ ${trial.tag}: ${id} (${N} fix, gazeplot: ${hasGazeplot ? sizeMB + 'MB' : 'no'})`);
    results.push({ tag: trial.tag, id, query: trial.query, n: N, hasGazeplot });
}

// Generate PNG exports (scanpath overlay on gazeplot) + thumbnails
console.log('\n  Generating PNG exports...');
const pngBrowser = await chromium.launch();
for (const r of results) {
    const pagePath = path.join(SITE_DIR, `${r.id}.html`);
    const ctx = await pngBrowser.newContext({ viewport: { width: 1280, height: 1024 } });
    const page = await ctx.newPage();
    await page.goto(`file://${path.resolve(pagePath)}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1000);

    // Get the serp-container dimensions (full page height)
    const box = await page.evaluate(() => {
        const el = document.querySelector('.serp-container');
        return el ? { w: el.offsetWidth, h: el.offsetHeight } : null;
    });
    if (!box) { console.log(`    skip ${r.id} — no container`); await ctx.close(); continue; }

    // Scroll viewer to top, capture the serp-container at full height
    await page.evaluate(() => document.querySelector('.viewer').scrollTo(0, 0));
    const serpContainer = await page.$('.serp-container');
    try {
        const pngBuf = await serpContainer.screenshot();
        fs.writeFileSync(path.join(SITE_DIR, 'png', `${r.id}.png`), pngBuf);
        console.log(`    ${r.id}.png (${(pngBuf.length / 1024 / 1024).toFixed(1)}MB, ${box.w}x${box.h})`);
    } catch (err) {
        console.log(`    ⚠ ${r.id}.png FAILED: ${err.message}`);
    }

    await ctx.close();
}
await pngBrowser.close();
console.log('');

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
<p style="background:#332200;border:1px solid #664400;border-radius:6px;padding:8px 12px;color:#ffcc66;font-size:0.85em;margin-bottom:1em;">
  Positional accuracy: fixation overlay has median &lt;13px offset, max ~45px at page bottom.
  SERP HTML is re-rendered locally; element heights differ from the original Chrome 110/Windows session
  due to external resource loading (Maps tiles, product images). Fixation coordinates (FPOGX/FPOGY)
  from <a href="https://github.com/kayhan-latifzadeh/AdSERP" style="color:#ffcc66;">AdSERP</a> are
  pixel-verified accurate against synthetic test pages.
</p>
<p style="background:#1a1a00;border:1px solid #554400;border-radius:6px;padding:8px 12px;color:#f5c542;font-size:0.85em;margin-bottom:1em;">
  <strong>Pupil LF/HF</strong> &mdash; Low/High frequency power ratio of pupil diameter oscillations
  (Duchowski 2026, Butterworth IIR: LF 0&ndash;1.6&thinsp;Hz / HF 1.6&ndash;4&thinsp;Hz, 1s sliding window).
  Higher values = higher cognitive load. Amber timeline track and color mode.
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
<li>The <strong>batch gazeplot mode</strong> bulk-loads all fixation positions into
  the visual memory buffer at once (instead of walking them one-by-one through
  the render loop), then tile-captures the page — reducing capture time from
  minutes to seconds per trial</li>
<li>The interactive overlay is generated as self-contained HTML with the
  gazeplot PNG as background</li>
</ol>

<p style="margin-top:0.8em;"><strong>DOM-anchored fixation positioning:</strong>
Fixation coordinates from the eye tracker are in screen-pixel space
(1280&times;1024), but the SERP was displayed at 1422 CSS pixels (90% display
scaling). Rendering at a different width causes content reflow, shifting
elements vertically. Instead of coordinate transforms, each fixation is
<em>anchored to the DOM element it landed on</em>: during the build step,
<a href="https://github.com/andyed/attentional-foraging/blob/main/scripts/generate-anchors.js" style="color:#6af;">generate-anchors.js</a>
loads each SERP in Playwright at the original window width, uses
<code style="background:#222;padding:1px 4px;border-radius:2px;">elementFromPoint</code>
to map each fixation to a CSS selector + offset, then the build script
re-resolves those anchors at the render width. The fixation dot lands
on the correct element regardless of layout width. This approach was inspired
by DOM-based event logging (Edmonds, 2003) — the same principle that anchors
interaction events to page structure rather than screen coordinates.</p>

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
