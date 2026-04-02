#!/usr/bin/env node
/**
 * Visual regression test for scanpath overlay alignment.
 *
 * Verifies that fixation coordinates land on actual SERP content,
 * not whitespace, by loading the SERP HTML and using elementFromPoint.
 *
 * Also checks that the generated viewer HTML has matching dimensions
 * between the background image and SVG overlay.
 *
 * Usage:
 *   node scripts/test-scanpath-alignment.js --trial=p037-b2-t5
 *   node scripts/test-scanpath-alignment.js --all
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(2);
const hasFlag = (name) => args.includes(`--${name}`);
function getArg(name, def) {
    const a = args.find(x => x.startsWith(`--${name}=`));
    return a ? a.split('=').slice(1).join('=') : def;
}

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'AdSERP', 'data');
const SITE_DIR = path.join(ROOT, 'site');

// Curated trials (must match build-gh-pages.js)
const ALL_TRIALS = [
    'p032-b6-t8', 'p029-b2-t10', 'p016-b3-t1', 'p047-b1-t9',
    'p035-b4-t2', 'p011-b3-t2', 'p037-b2-t5', 'p045-b2-t6',
];

const singleTrial = getArg('trial', null);
const trials = singleTrial ? [singleTrial] : (hasFlag('all') ? ALL_TRIALS : ALL_TRIALS.slice(0, 1));

async function main() {
    console.log(`\n═══ Scanpath Alignment Test ═══\n`);
    console.log(`Testing ${trials.length} trial(s)\n`);

    const browser = await chromium.launch();
    const results = [];

    for (const trialId of trials) {
        console.log(`  ${trialId}:`);
        const result = { trialId, tests: [] };

        // Load trial data
        const fixCsv = fs.readFileSync(path.join(DATA_DIR, 'fixation-data', `${trialId}.csv`), 'utf8');
        const mouseCsv = fs.readFileSync(path.join(DATA_DIR, 'mouse-movement-data', `${trialId}.csv`), 'utf8');
        const metaXml = fs.readFileSync(path.join(DATA_DIR, 'trial-metadata', `${trialId}.xml`), 'utf8');
        const serpPath = path.join(DATA_DIR, 'serps', `${trialId}.html`);

        const get = (tag) => { const m = metaXml.match(new RegExp(`<${tag}>([^<]*)</${tag}>`)); return m ? m[1].trim() : ''; };
        const screenW = parseInt(get('screen').split('x')[0]) || 1280;
        const windowW = parseInt(get('window').split('x')[0]) || 1422;
        const windowH = parseInt(get('window').split('x')[1]) || 1137;
        const screenH = parseInt(get('screen').split('x')[1]) || 1024;
        const rx = screenW / windowW;

        const fixations = fixCsv.trim().split('\n').slice(1).map(l => {
            const [t, x, y, d] = l.split(',').map(Number);
            return { t, x, y, d };
        }).filter(f => isFinite(f.t) && isFinite(f.x) && f.d > 0);

        // Parse scroll events
        const scrollEvents = mouseCsv.trim().split('\n').slice(1)
            .filter(l => l.includes(',scroll,'))
            .map(l => { const c = l.split(','); return { t: parseInt(c[0]), s: parseFloat(c[2]) }; })
            .filter(e => isFinite(e.t) && isFinite(e.s));

        // Find last click
        const clickLines = mouseCsv.trim().split('\n').slice(1).filter(l => l.includes(',click,'));
        let click = null;
        if (clickLines.length > 0) {
            const c = clickLines[clickLines.length - 1].split(',');
            const clickT = parseInt(c[0]);
            let scrollAtClick = 0;
            for (const s of scrollEvents) { if (s.t <= clickT) scrollAtClick = s.s; else break; }
            click = {
                pageX: parseFloat(c[1]),
                pageY: parseFloat(c[2]),
                viewportX: parseFloat(c[1]) * rx,
                viewportY: parseFloat(c[2]) - scrollAtClick,
                scrollY: scrollAtClick
            };
        }

        // ── Test 1: Element hit test on raw SERP HTML ──
        {
            const ctx = await browser.newContext({ viewport: { width: 1280, height: 1024 } });
            const page = await ctx.newPage();
            await page.goto(`file://${path.resolve(serpPath)}`, { waitUntil: 'networkidle' });
            await page.waitForTimeout(1000);

            // Test click position
            if (click) {
                await page.evaluate(y => window.scrollTo(0, y), click.scrollY);
                await page.waitForTimeout(200);

                const clickHit = await page.evaluate(({ x, y }) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return { tag: 'null', hit: false };
                    // Walk up to find nearest link/button
                    let node = el;
                    while (node && node !== document.body) {
                        if (node.tagName === 'A' || node.tagName === 'BUTTON') return { tag: node.tagName, text: node.textContent.slice(0, 50), hit: true };
                        node = node.parentElement;
                    }
                    return { tag: el.tagName, id: el.id, className: (el.className || '').toString().slice(0, 30), hit: false };
                }, { x: click.viewportX, y: click.viewportY });

                const pass = clickHit.hit || clickHit.tag !== 'BODY';
                result.tests.push({
                    name: 'click_hits_content',
                    pass,
                    detail: `click(${Math.round(click.viewportX)},${Math.round(click.viewportY)}) → ${clickHit.tag}${clickHit.hit ? ' ✓ link' : ''}${clickHit.text ? ': "' + clickHit.text + '"' : ''}`
                });
                console.log(`    click hit: ${pass ? '✓' : '✗'} ${clickHit.tag}${clickHit.text ? ' "' + clickHit.text.slice(0, 40) + '"' : ''}`);
            }

            // Test sampled fixations
            let fixHits = 0;
            const sampleIndices = fixations.length <= 5
                ? fixations.map((_, i) => i)
                : [0, Math.floor(fixations.length * 0.25), Math.floor(fixations.length * 0.5), Math.floor(fixations.length * 0.75), fixations.length - 1];

            for (const i of sampleIndices) {
                const f = fixations[i];
                // Compute scroll at fixation time
                let scrollY = 0;
                for (const s of scrollEvents) { if (s.t <= f.t) scrollY = s.s; else break; }
                const viewportY = f.y - scrollY;

                // Only test if fixation is within viewport
                if (viewportY < 0 || viewportY > 1024) continue;

                await page.evaluate(y => window.scrollTo(0, y), scrollY);
                await page.waitForTimeout(100);

                const hit = await page.evaluate(({ x, y }) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return 'null';
                    return el.tagName === 'BODY' || el.tagName === 'HTML' ? 'whitespace' : 'content';
                }, { x: f.x, y: viewportY });

                if (hit === 'content') fixHits++;
            }

            const fixPass = fixHits >= sampleIndices.length * 0.5;
            result.tests.push({
                name: 'fixations_hit_content',
                pass: fixPass,
                detail: `${fixHits}/${sampleIndices.length} sampled fixations hit content (need ≥50%)`
            });
            console.log(`    fixation hits: ${fixPass ? '✓' : '✗'} ${fixHits}/${sampleIndices.length}`);

            await ctx.close();
        }

        // ── Test 2: Viewer dimension match ──
        {
            const viewerPath = path.join(SITE_DIR, `${trialId}.html`);
            if (fs.existsSync(viewerPath)) {
                const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
                const page = await ctx.newPage();
                await page.goto(`file://${path.resolve(viewerPath)}`, { waitUntil: 'networkidle' });
                await page.waitForTimeout(2000);

                const dims = await page.evaluate(() => {
                    const bg = document.getElementById('bg-img') || document.querySelector('.serp-render');
                    const svg = document.getElementById('scanpath-svg') || document.querySelector('.scanpath-svg');
                    if (!bg || !svg) return null;

                    const bgRect = bg.getBoundingClientRect();
                    const svgRect = svg.getBoundingClientRect();
                    const vb = svg.getAttribute('viewBox')?.split(' ').map(Number) || [];

                    return {
                        bgW: Math.round(bgRect.width),
                        bgH: Math.round(bgRect.height),
                        bgNatW: bg.naturalWidth,
                        bgNatH: bg.naturalHeight,
                        svgW: Math.round(svgRect.width),
                        svgH: Math.round(svgRect.height),
                        vbW: vb[2],
                        vbH: vb[3],
                    };
                });

                if (dims) {
                    const widthMatch = dims.bgW === dims.svgW;
                    const heightMatch = Math.abs(dims.bgH - dims.svgH) < 5; // 5px tolerance
                    const natWidth1280 = dims.bgNatW === 1280;
                    const vbWidth1280 = dims.vbW === 1280;

                    result.tests.push({
                        name: 'bg_width_1280',
                        pass: natWidth1280,
                        detail: `bg.naturalWidth=${dims.bgNatW} (need 1280)`
                    });
                    result.tests.push({
                        name: 'viewBox_width_1280',
                        pass: vbWidth1280,
                        detail: `viewBox width=${dims.vbW} (need 1280)`
                    });
                    result.tests.push({
                        name: 'rendered_width_match',
                        pass: widthMatch,
                        detail: `bg=${dims.bgW}px, svg=${dims.svgW}px`
                    });
                    result.tests.push({
                        name: 'rendered_height_match',
                        pass: heightMatch,
                        detail: `bg=${dims.bgH}px, svg=${dims.svgH}px (Δ${Math.abs(dims.bgH - dims.svgH)})`
                    });

                    console.log(`    bg width:  ${natWidth1280 ? '✓' : '✗'} ${dims.bgNatW}px`);
                    console.log(`    vb width:  ${vbWidth1280 ? '✓' : '✗'} ${dims.vbW}px`);
                    console.log(`    w match:   ${widthMatch ? '✓' : '✗'} bg=${dims.bgW} svg=${dims.svgW}`);
                    console.log(`    h match:   ${heightMatch ? '✓' : '✗'} bg=${dims.bgH} svg=${dims.svgH}`);
                } else {
                    result.tests.push({ name: 'viewer_dims', pass: false, detail: 'Could not find bg-img or scanpath-svg elements' });
                    console.log(`    dims: ✗ elements not found`);
                }

                await ctx.close();
            } else {
                console.log(`    viewer: skipped (${viewerPath} not found — run build-gh-pages.js first)`);
            }
        }

        results.push(result);
        console.log();
    }

    await browser.close();

    // Summary
    const allTests = results.flatMap(r => r.tests);
    const passed = allTests.filter(t => t.pass).length;
    const failed = allTests.filter(t => !t.pass).length;

    console.log(`═══ Results: ${passed} passed, ${failed} failed ═══\n`);

    if (failed > 0) {
        console.log('Failures:');
        for (const r of results) {
            for (const t of r.tests.filter(t => !t.pass)) {
                console.log(`  ${r.trialId} / ${t.name}: ${t.detail}`);
            }
        }
        console.log();
    }

    // Write results JSON
    const outPath = path.join(ROOT, 'site', 'test-results.json');
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, JSON.stringify({ timestamp: new Date().toISOString(), results }, null, 2));

    process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error('Fatal:', err); process.exit(1); });
