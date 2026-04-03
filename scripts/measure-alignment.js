#!/usr/bin/env node
/**
 * Measure fixation-to-DOM alignment deviation across trials.
 *
 * For each trial: renders the SERP at 1280px, extracts Y positions of
 * all h3 elements (result titles), matches fixation clusters to nearby
 * h3s, and reports the offset. Produces per-trial and aggregate stats.
 *
 * Usage:
 *   node scripts/measure-alignment.js
 *   node scripts/measure-alignment.js --trial=p037-b2-t5
 */

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'AdSERP', 'data');
const SCRUTINIZER = path.join(ROOT, '..', 'scrutinizer-repo', 'scrutinizer2025');

const adserp = require(path.join(SCRUTINIZER, 'renderer', 'scanpath', 'importers', 'adserp-importer'));

const args = process.argv.slice(2);
const singleTrial = args.find(a => a.startsWith('--trial='))?.split('=')[1];

// All 8 curated trials, or just one
const trials = singleTrial ? [singleTrial] : [
    'p032-b6-t8', 'p029-b2-t10', 'p016-b3-t1', 'p047-b1-t9',
    'p035-b4-t2', 'p011-b3-t2', 'p037-b2-t5', 'p045-b2-t6'
];

const MATCH_RADIUS = 60; // px — max distance to match a fixation cluster to an h3

async function main() {
    const browser = await chromium.launch();
    const allOffsets = [];
    const trialSummaries = [];

    for (const trialId of trials) {
        const serpPath = path.join(DATA_DIR, 'serps', `${trialId}.html`);
        if (!fs.existsSync(serpPath)) { console.log(`  skip ${trialId} — no SERP`); continue; }

        // Load fixation data
        let trialData;
        try { trialData = adserp.loadTrial(DATA_DIR, trialId); } catch (e) { console.log(`  skip ${trialId} — ${e.message}`); continue; }
        const fixations = trialData.fixations;

        // Render SERP and extract h3 positions
        const ctx = await browser.newContext({ viewport: { width: 1280, height: 1024 } });
        const page = await ctx.newPage();
        await page.goto(`file://${path.resolve(serpPath)}`, { waitUntil: 'networkidle', timeout: 10000 }).catch(() => {});
        await page.waitForTimeout(500);

        const landmarks = await page.evaluate(() => {
            const results = [];
            // h3 elements (result titles — most reliable anchor)
            document.querySelectorAll('h3').forEach((el, i) => {
                const r = el.getBoundingClientRect();
                const y = Math.round(r.top + window.scrollY + r.height / 2); // center Y
                results.push({
                    type: 'h3',
                    index: i,
                    y,
                    height: el.offsetHeight,
                    text: el.textContent.slice(0, 40)
                });
            });
            // Search input
            const input = document.querySelector('input[name="q"], textarea[name="q"]');
            if (input) {
                const r = input.getBoundingClientRect();
                results.push({ type: 'input', index: 0, y: Math.round(r.top + window.scrollY + r.height / 2), height: input.offsetHeight, text: 'search input' });
            }
            return results;
        });

        await page.close();
        await ctx.close();

        if (landmarks.length === 0) { console.log(`  skip ${trialId} — no landmarks`); continue; }

        // Match fixation clusters to landmarks
        const matches = [];
        for (const lm of landmarks) {
            // Find fixations near this landmark (within MATCH_RADIUS, x in main content 50-800)
            const nearby = fixations.filter(f =>
                f.pageY > lm.y - MATCH_RADIUS && f.pageY < lm.y + MATCH_RADIUS &&
                f.x > 50 && f.x < 800
            );
            if (nearby.length < 2) continue; // need at least 2 fixations for confidence

            const avgFixY = nearby.reduce((s, f) => s + f.pageY, 0) / nearby.length;
            const offset = avgFixY - lm.y;
            const stdDev = Math.sqrt(nearby.reduce((s, f) => s + (f.pageY - avgFixY) ** 2, 0) / nearby.length);

            matches.push({
                landmark: lm.text,
                domY: lm.y,
                fixY: Math.round(avgFixY),
                offset: Math.round(offset * 10) / 10,
                stdDev: Math.round(stdDev * 10) / 10,
                n: nearby.length
            });
            allOffsets.push(offset);
        }

        // Per-trial summary
        if (matches.length > 0) {
            const offsets = matches.map(m => m.offset);
            const mean = offsets.reduce((a, b) => a + b, 0) / offsets.length;
            const absOffsets = offsets.map(Math.abs);
            const meanAbs = absOffsets.reduce((a, b) => a + b, 0) / absOffsets.length;
            const max = Math.max(...absOffsets);
            const min = Math.min(...absOffsets);

            trialSummaries.push({
                trial: trialId,
                landmarks: matches.length,
                fixations: fixations.length,
                meanOffset: Math.round(mean * 10) / 10,
                meanAbsOffset: Math.round(meanAbs * 10) / 10,
                maxAbsOffset: Math.round(max * 10) / 10,
                range: `${Math.round(Math.min(...offsets))} to ${Math.round(Math.max(...offsets))}`
            });

            console.log(`\n${trialId} (${fixations.length} fix, ${matches.length} anchors):`);
            console.log(`  mean offset: ${mean.toFixed(1)}px  |  mean |offset|: ${meanAbs.toFixed(1)}px  |  max: ${max.toFixed(1)}px  |  range: ${Math.min(...offsets).toFixed(0)}..${Math.max(...offsets).toFixed(0)}px`);
            for (const m of matches) {
                const bar = m.offset > 0 ? '+'.repeat(Math.min(30, Math.round(m.offset))) : '-'.repeat(Math.min(30, Math.round(-m.offset)));
                console.log(`  ${String(m.domY).padStart(5)}px  ${m.offset > 0 ? '+' : ''}${m.offset.toFixed(1).padStart(6)}px  (n=${m.n})  ${bar}  ${m.landmark}`);
            }
        }
    }

    await browser.close();

    // Aggregate
    if (allOffsets.length > 0) {
        const mean = allOffsets.reduce((a, b) => a + b, 0) / allOffsets.length;
        const meanAbs = allOffsets.map(Math.abs).reduce((a, b) => a + b, 0) / allOffsets.length;
        const stdDev = Math.sqrt(allOffsets.reduce((s, v) => s + (v - mean) ** 2, 0) / allOffsets.length);
        const max = Math.max(...allOffsets.map(Math.abs));
        const p50 = allOffsets.map(Math.abs).sort((a, b) => a - b)[Math.floor(allOffsets.length * 0.5)];
        const p90 = allOffsets.map(Math.abs).sort((a, b) => a - b)[Math.floor(allOffsets.length * 0.9)];

        console.log(`\n${'═'.repeat(60)}`);
        console.log(`AGGREGATE (${allOffsets.length} anchor matches across ${trialSummaries.length} trials)`);
        console.log(`  mean offset:     ${mean.toFixed(1)}px`);
        console.log(`  mean |offset|:   ${meanAbs.toFixed(1)}px`);
        console.log(`  std dev:         ${stdDev.toFixed(1)}px`);
        console.log(`  median |offset|: ${p50.toFixed(1)}px`);
        console.log(`  p90 |offset|:    ${p90.toFixed(1)}px`);
        console.log(`  max |offset|:    ${max.toFixed(1)}px`);
        console.log(`${'═'.repeat(60)}`);

        // Per-trial table
        console.log(`\nPer-trial summary:`);
        console.log(`${'Trial'.padEnd(15)} ${'Fix'.padStart(4)} ${'Anchors'.padStart(7)} ${'Mean'.padStart(7)} ${'|Mean|'.padStart(7)} ${'Max'.padStart(6)} Range`);
        for (const s of trialSummaries) {
            console.log(`${s.trial.padEnd(15)} ${String(s.fixations).padStart(4)} ${String(s.landmarks).padStart(7)} ${String(s.meanOffset).padStart(6)}px ${String(s.meanAbsOffset).padStart(5)}px ${String(s.maxAbsOffset).padStart(5)}px ${s.range}`);
        }
    }
}

main().catch(console.error);
