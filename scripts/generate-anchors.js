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
const OUT_DIR = path.join(ROOT, 'fixation-anchors');

const args = process.argv.slice(2);
function getArg(name, def) {
    const a = args.find(x => x.startsWith(`--${name}=`));
    return a ? a.split('=').slice(1).join('=') : def;
}

// Same curated trials as build-gh-pages.js
const ALL_TRIALS = [
    'p032-b6-t8', 'p029-b2-t10', 'p016-b3-t1', 'p047-b1-t9',
    'p035-b4-t2', 'p011-b3-t2', 'p037-b2-t5', 'p045-b2-t6',
];

const singleTrial = getArg('trial', null);
const trials = singleTrial ? [singleTrial] : ALL_TRIALS;

fs.mkdirSync(OUT_DIR, { recursive: true });

(async () => {
    console.log(`Generating DOM anchors for ${trials.length} trial(s)...\n`);
    const browser = await chromium.launch();

    for (const trialId of trials) {
        const serpPath = path.join(DATA_DIR, 'serps', `${trialId}.html`);
        const fixPath = path.join(DATA_DIR, 'fixation-data', `${trialId}.csv`);
        const metaPath = path.join(DATA_DIR, 'trial-metadata', `${trialId}.xml`);

        if (!fs.existsSync(serpPath) || !fs.existsSync(fixPath)) {
            console.log(`  ✗ ${trialId}: missing data`);
            continue;
        }

        // Read metadata for coordinate scaling
        const metaXml = fs.readFileSync(metaPath, 'utf8');
        const get = (tag) => { const m = metaXml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)); return m ? m[1].trim() : ''; };
        const screenW = parseInt(get('screen').split('x')[0]) || 1280;
        const screenH = parseInt(get('screen').split('x')[1]) || 1024;
        const windowW = parseInt(get('window').split('x')[0]) || 1422;
        const windowH = parseInt(get('window').split('x')[1]) || 1137;

        // Parse fixations — raw screen-space coordinates
        const fixCsv = fs.readFileSync(fixPath, 'utf8');
        const fixations = fixCsv.trim().split('\n').slice(1).map(l => {
            const [t, x, y, d] = l.split(',').map(Number);
            return { t, x, y, d };
        }).filter(f => isFinite(f.t) && isFinite(f.x) && f.d > 0);

        // Convert fixations to CSS page-space at windowW
        const cssFixations = fixations.map(f => ({
            x: f.x * (windowW / screenW),
            y: f.y * (windowH / screenH),
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

        await page.close();
        await ctx.close();

        // Write anchors JSON
        const outPath = path.join(OUT_DIR, `${trialId}.json`);
        fs.writeFileSync(outPath, JSON.stringify(anchors, null, 2));

        const pct = ((resolved / fixations.length) * 100).toFixed(0);
        console.log(`  ✓ ${trialId}: ${resolved}/${fixations.length} anchored (${pct}%) → ${outPath}`);
    }

    await browser.close();
    console.log('\nDone.');
})();
