#!/usr/bin/env node
/**
 * Generate DOM anchors for fixation data.
 *
 * For each fixation in a trial, loads the SERP HTML at the original window
 * width (1422px) and uses elementFromPoint to find the DOM element under
 * the gaze. Stores a CSS selector + offset so the fixation can be resolved
 * from the DOM at any render width — no coordinate transforms needed.
 *
 * Usage:
 *   node scripts/generate-anchors.js                    # all curated trials
 *   node scripts/generate-anchors.js --trial=p037-b2-t5 # single trial
 *
 * Output: fixation-anchors/{trialId}.json
 */

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'AdSERP', 'data');
const SCRUTINIZER = path.join(ROOT, '..', 'scrutinizer-repo', 'scrutinizer2025');
const OUT_DIR = path.join(ROOT, 'fixation-anchors');
const LAYOUT_DIR = path.join(ROOT, 'layout-freeze');

// Use the same importer as the capture pipeline so fixation indices match
const adserp = require(path.join(SCRUTINIZER, 'renderer', 'scanpath', 'importers', 'adserp-importer'));

const args = process.argv.slice(2);
function getArg(name, def) {
    const a = args.find(x => x.startsWith(`--${name}=`));
    return a ? a.split('=').slice(1).join('=') : def;
}

// Same curated trials as build-gh-pages.js
const ALL_TRIALS = [
    'p032-b6-t8', 'p029-b2-t10', 'p016-b3-t1', 'p047-b1-t9',
    'p035-b4-t2', 'p011-b3-t2', 'p037-b2-t5', 'p045-b2-t6',
    'p020-b6-t10', 'p047-b2-t6',
    'p031-b5-t2', 'p049-b2-t6', 'p017-b3-t3',
    'p021-b6-t2', 'p019-b6-t5', 'p021-b2-t10',
    'p013-b2-t3', 'p026-b4-t9', 'p032-b4-t9',
    'p004-b2-t4', 'p007-b6-t8', 'p035-b1-t8',
    'p014-b6-t8', 'p034-b2-t3', 'p027-b3-t6',
    'p038-b5-t9', 'p010-b4-t7', 'p031-b3-t9',
    'p024-b3-t5', 'p035-b4-t1', 'p024-b5-t5',
];

const singleTrial = getArg('trial', null);
const trials = singleTrial ? [singleTrial] : ALL_TRIALS;

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.mkdirSync(LAYOUT_DIR, { recursive: true });

(async () => {
    console.log(`Generating DOM anchors for ${trials.length} trial(s)...\n`);
    const browser = await chromium.launch();

    for (const trialId of trials) {
        const serpPath = path.join(DATA_DIR, 'serps', `${trialId}.html`);

        if (!fs.existsSync(serpPath)) {
            console.log(`  ✗ ${trialId}: missing SERP HTML`);
            continue;
        }

        // Use the adserp-importer to get the SAME filtered fixation list
        // as the capture pipeline and viewer. This ensures anchor indices
        // match fixation indices everywhere.
        let scanpathData;
        try {
            scanpathData = adserp.loadTrial(DATA_DIR, trialId);
        } catch (e) {
            console.log(`  ✗ ${trialId}: importer failed: ${e.message}`);
            continue;
        }
        const meta = scanpathData.meta;
        const fixations = scanpathData.fixations;
        const windowW = meta.windowWidth || 1422;
        const windowH = meta.windowHeight || 1137;
        const screenW = meta.screenWidth || 1280;
        const screenH = meta.screenHeight || 1024;

        // Importer fixations have x in screen-space, pageY in page-space.
        // For elementFromPoint we need CSS page-space at windowW.
        const cssFixations = fixations.map(f => ({
            x: f.x * (windowW / screenW),
            y: (f.pageY !== undefined ? f.pageY : f.y) * (windowH / screenH),
        }));

        // Load SERP at original window width
        const ctx = await browser.newContext({ viewport: { width: windowW, height: windowH } });
        const page = await ctx.newPage();
        await page.goto(`file://${path.resolve(serpPath)}`, { waitUntil: 'networkidle' });
        await page.waitForTimeout(500);

        // Generate anchors for each fixation
        const anchors = [];
        let resolved = 0;

        for (let i = 0; i < cssFixations.length; i++) {
            const fix = cssFixations[i];

            const anchor = await page.evaluate(({ x, y }) => {
                // Scroll so the fixation point is in the viewport
                window.scrollTo(0, Math.max(0, y - window.innerHeight / 2));

                const viewportY = y - window.scrollY;
                if (viewportY < 0 || viewportY > window.innerHeight) return null;

                const el = document.elementFromPoint(x, viewportY);
                if (!el || el === document.body || el === document.documentElement) return null;

                // Build a stable CSS selector path using IDs and nth-of-type
                const parts = [];
                let node = el;
                while (node && node !== document.body && node !== document.documentElement) {
                    let sel = node.tagName.toLowerCase();
                    if (node.id) {
                        parts.unshift('#' + CSS.escape(node.id));
                        break;
                    }
                    const parent = node.parentNode;
                    if (parent) {
                        const siblings = [...parent.children].filter(c => c.tagName === node.tagName);
                        if (siblings.length > 1) {
                            sel += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
                        }
                    }
                    parts.unshift(sel);
                    node = node.parentNode;
                }

                const rect = el.getBoundingClientRect();
                return {
                    selector: parts.join(' > '),
                    offsetX: Math.round((x - rect.left) * 10) / 10,
                    offsetY: Math.round((viewportY - rect.top) * 10) / 10,
                    // Resolved CSS page-space coordinates at this render width
                    resolvedX: Math.round((rect.left + (x - rect.left)) * 10) / 10,
                    resolvedY: Math.round((rect.top + window.scrollY + (viewportY - rect.top)) * 10) / 10,
                    tag: el.tagName.toLowerCase(),
                };
            }, { x: fix.x, y: fix.y });

            anchors.push(anchor);
            if (anchor) resolved++;
        }

        // ── Layout freeze: capture rendered dimensions of all layout-affecting elements ──
        // Walk the DOM and record selector + width/height for elements that could shift
        // if external resources fail to load (images, iframes, replaced content, and any
        // element with explicit dimensions that holds space for async content).
        const layoutFreeze = await page.evaluate(() => {
            const entries = [];
            const seen = new Set();

            function selectorFor(el) {
                const parts = [];
                let node = el;
                while (node && node !== document.body && node !== document.documentElement) {
                    let sel = node.tagName.toLowerCase();
                    if (node.id) {
                        parts.unshift('#' + CSS.escape(node.id));
                        break;
                    }
                    const parent = node.parentNode;
                    if (parent) {
                        const siblings = [...parent.children].filter(c => c.tagName === node.tagName);
                        if (siblings.length > 1) {
                            sel += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
                        }
                    }
                    parts.unshift(sel);
                    node = node.parentNode;
                }
                return parts.join(' > ');
            }

            // Capture images, iframes, video, canvas, svg, and any element with
            // explicit width/height attributes or background-image
            const candidates = document.querySelectorAll('img, iframe, video, canvas, svg, [width], [height]');
            for (const el of candidates) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 2 && rect.height < 2) continue; // skip invisible
                const sel = selectorFor(el);
                if (seen.has(sel)) continue;
                seen.add(sel);
                entries.push({
                    selector: sel,
                    width: Math.round(rect.width * 10) / 10,
                    height: Math.round(rect.height * 10) / 10,
                    tag: el.tagName.toLowerCase(),
                });
            }

            // Also capture any element with a computed background-image (non-none)
            // that has significant size — these hold space for CSS background images
            const allDivs = document.querySelectorAll('div, span, a');
            for (const el of allDivs) {
                const bg = getComputedStyle(el).backgroundImage;
                if (bg === 'none' || bg === '') continue;
                const rect = el.getBoundingClientRect();
                if (rect.width < 10 || rect.height < 10) continue;
                const sel = selectorFor(el);
                if (seen.has(sel)) continue;
                seen.add(sel);
                entries.push({
                    selector: sel,
                    width: Math.round(rect.width * 10) / 10,
                    height: Math.round(rect.height * 10) / 10,
                    tag: el.tagName.toLowerCase(),
                });
            }

            return entries;
        });

        await page.close();
        await ctx.close();

        // Write anchors JSON
        const outPath = path.join(OUT_DIR, `${trialId}.json`);
        fs.writeFileSync(outPath, JSON.stringify(anchors, null, 2));

        // Write layout freeze JSON
        const layoutPath = path.join(LAYOUT_DIR, `${trialId}.json`);
        fs.writeFileSync(layoutPath, JSON.stringify(layoutFreeze, null, 2));

        const pct = ((resolved / fixations.length) * 100).toFixed(0);
        console.log(`  ✓ ${trialId}: ${resolved}/${fixations.length} anchored (${pct}%), ${layoutFreeze.length} elements frozen`);
    }

    await browser.close();
    console.log('\nDone.');
})();
