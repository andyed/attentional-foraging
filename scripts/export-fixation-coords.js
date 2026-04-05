#!/usr/bin/env node
/**
 * export-fixation-coords.js — Generate coordinate JSONs for Scrutinizer's export-saliency CLI.
 *
 * Reads fixation CSVs from AdSERP/data/fixation-data/, converts FPOGY screen-space
 * to page-space (clamped + scroll-corrected), and writes one JSON per trial to
 * AdSERP/data/fixation-coords/.
 *
 * Usage:
 *   node scripts/export-fixation-coords.js [--output-dir AdSERP/data/fixation-coords]
 */

const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', 'AdSERP', 'data');
const FIX_DIR = path.join(DATA, 'fixation-data');
const MOUSE_DIR = path.join(DATA, 'mouse-movement-data');
const SCREEN_H = 1024;

function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    return lines.slice(1).map(line => {
        const vals = line.split(',');
        const obj = {};
        headers.forEach((h, i) => { obj[h] = (vals[i] || '').trim(); });
        return obj;
    });
}

function loadScrollEvents(trialId) {
    const csvPath = path.join(MOUSE_DIR, `${trialId}.csv`);
    if (!fs.existsSync(csvPath)) return [];
    const rows = parseCSV(fs.readFileSync(csvPath, 'utf-8'));
    return rows
        .filter(r => r.event && r.event.trim() === 'scroll')
        .map(r => ({ t: parseFloat(r.timestamp), y: parseFloat(r.ypos) }))
        .filter(r => isFinite(r.t) && isFinite(r.y));
}

function interpolateScroll(t, scrolls) {
    if (!scrolls.length) return 0;
    if (t <= scrolls[0].t) return scrolls[0].y;
    if (t >= scrolls[scrolls.length - 1].t) return scrolls[scrolls.length - 1].y;
    for (let i = 0; i < scrolls.length - 1; i++) {
        if (scrolls[i].t <= t && t < scrolls[i + 1].t) {
            const frac = (t - scrolls[i].t) / (scrolls[i + 1].t - scrolls[i].t);
            return scrolls[i].y + frac * (scrolls[i + 1].y - scrolls[i].y);
        }
    }
    return scrolls[scrolls.length - 1].y;
}

function main() {
    const outDir = process.argv.includes('--output-dir')
        ? process.argv[process.argv.indexOf('--output-dir') + 1]
        : path.join(DATA, 'fixation-coords');

    fs.mkdirSync(outDir, { recursive: true });

    const fixFiles = fs.readdirSync(FIX_DIR).filter(f => f.endsWith('.csv'));
    console.log(`Processing ${fixFiles.length} fixation files...`);

    let processed = 0;
    const t0 = Date.now();

    for (const file of fixFiles) {
        const trialId = path.basename(file, '.csv');
        const raw = fs.readFileSync(path.join(FIX_DIR, file), 'utf-8');
        const rows = parseCSV(raw);
        const scrolls = loadScrollEvents(trialId);

        const coords = [];
        for (let i = 0; i < rows.length; i++) {
            const r = rows[i];
            const t = parseFloat(r.timestamp);
            const x = parseFloat(r.FPOGX);
            const y = parseFloat(r.FPOGY);
            const d = parseFloat(r.FPOGD);

            if (!isFinite(x) || !isFinite(y) || d <= 0) continue;

            // Clamp FPOGY to [0, SCREEN_H] then add scroll offset → page-space
            const yClamped = Math.max(0, Math.min(y, SCREEN_H));
            const scrollY = interpolateScroll(t, scrolls);
            const pageY = yClamped + scrollY;

            coords.push({
                id: `fix_${i}`,
                x: Math.round(x),
                y: Math.round(pageY),
                t: Math.round(t),
                d: Math.round(d),
            });
        }

        fs.writeFileSync(
            path.join(outDir, `${trialId}.json`),
            JSON.stringify(coords)
        );
        processed++;

        if (processed % 500 === 0) {
            console.log(`  ${processed}/${fixFiles.length}...`);
        }
    }

    console.log(`Done: ${processed} trials, ${Date.now() - t0}ms`);
}

main();
