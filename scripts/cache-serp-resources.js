#!/usr/bin/env node
/**
 * cache-serp-resources.js — Download and cache all external resources from SERP HTML files.
 *
 * Dataset preservation: Google CDN URLs for product thumbnails, fonts, icons, and
 * sprites will eventually go stale. This script downloads them once and rewrites
 * the HTML to use local paths.
 *
 * Usage:
 *   node scripts/cache-serp-resources.js                     # all SERPs
 *   node scripts/cache-serp-resources.js --trial=p011-b3-t2  # single trial
 *   node scripts/cache-serp-resources.js --dry-run            # scan only, no downloads
 *
 * Output:
 *   AdSERP/data/resource-cache/       — downloaded files, keyed by content hash
 *   AdSERP/data/resource-cache/manifest.json — URL → local path mapping
 *   AdSERP/data/serps-cached/         — rewritten HTML using local paths
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const crypto = require('crypto');

const ROOT = path.join(__dirname, '..');
const SERP_DIR = path.join(ROOT, 'AdSERP', 'data', 'serps');
const CACHE_DIR = path.join(ROOT, 'AdSERP', 'data', 'resource-cache');
const CACHED_SERPS_DIR = path.join(ROOT, 'AdSERP', 'data', 'serps-cached');

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const singleTrial = (args.find(a => a.startsWith('--trial=')) || '').split('=')[1];

// Domains worth caching (from the audit)
const CACHE_DOMAINS = new Set([
    'encrypted-tbn0.gstatic.com',
    'encrypted-tbn1.gstatic.com',
    'encrypted-tbn2.gstatic.com',
    'encrypted-tbn3.gstatic.com',
    'fonts.gstatic.com',
    'ssl.gstatic.com',
    'www.gstatic.com',
    'www.google.com',
    'lh3.googleusercontent.com',
    'lh4.googleusercontent.com',
    'lh5.googleusercontent.com',
    'lh6.googleusercontent.com',
]);

// URL patterns to skip even from cacheable domains
const SKIP_PATTERNS = [
    /\/aclk\?/,           // ad click redirects
    /gen_204/,            // tracking pixels
    /\/sorry\//,          // captcha
    /\/ServiceLogin/,     // auth
    /consent\.google/,    // cookie consent
    /accounts\.google/,   // login
];

// URL patterns to always cache
const CACHE_PATTERNS = [
    /encrypted-tbn\d\.gstatic\.com\/images/,   // product thumbnails
    /fonts\.gstatic\.com\/s\//,                 // fonts
    /ssl\.gstatic\.com\/ui\//,                  // UI assets
    /www\.gstatic\.com\/shopping\//,            // shopping sprites
    /www\.gstatic\.com\/images\//,              // material icons
    /www\.gstatic\.com\/local\//,               // local icons
    /www\.google\.com\/images\/branding/,       // Google logo
    /www\.google\.com\/images\/nav_logo/,       // nav sprites
    /www\.google\.com\/images\/searchbox/,      // searchbox sprites
    /www\.google\.com\/images\/experiments/,    // UI experiments
    /www\.google\.com\/maps\/vt\/data/,         // map tiles
    /lh\d\.googleusercontent\.com/,             // proxied images
];

function shouldCache(url) {
    if (SKIP_PATTERNS.some(p => p.test(url))) return false;
    if (CACHE_PATTERNS.some(p => p.test(url))) return true;
    try {
        const host = new URL(url).hostname;
        return CACHE_DOMAINS.has(host);
    } catch { return false; }
}

// Extract all URLs from HTML
function extractUrls(html) {
    const urls = new Set();
    // src="..." and src='...'
    const srcRe = /\bsrc\s*=\s*["']([^"']+)["']/gi;
    let m;
    while ((m = srcRe.exec(html)) !== null) {
        if (!m[1].startsWith('data:')) urls.add(m[1]);
    }
    // href="..." for stylesheets
    const hrefRe = /<link[^>]+href\s*=\s*["']([^"']+)["'][^>]*rel\s*=\s*["']stylesheet["']/gi;
    while ((m = hrefRe.exec(html)) !== null) urls.add(m[1]);
    // Also catch link with rel before href
    const hrefRe2 = /<link[^>]+rel\s*=\s*["']stylesheet["'][^>]+href\s*=\s*["']([^"']+)["']/gi;
    while ((m = hrefRe2.exec(html)) !== null) urls.add(m[1]);
    // url(...) in inline styles and style blocks
    const urlRe = /url\s*\(\s*["']?([^)"'\s]+)["']?\s*\)/gi;
    while ((m = urlRe.exec(html)) !== null) {
        if (!m[1].startsWith('data:')) urls.add(m[1]);
    }
    // @font-face src
    const fontRe = /src:\s*url\s*\(\s*["']?([^)"'\s]+)["']?\s*\)/gi;
    while ((m = fontRe.exec(html)) !== null) {
        if (!m[1].startsWith('data:')) urls.add(m[1]);
    }
    return urls;
}

function normalizeUrl(url) {
    // Normalize protocol-relative URLs
    if (url.startsWith('//')) return 'https:' + url;
    if (url.startsWith('http://')) return url.replace('http://', 'https://');
    return url;
}

function hashUrl(url) {
    return crypto.createHash('sha256').update(url).digest('hex').slice(0, 16);
}

function extensionFor(url, contentType) {
    // Try content-type first
    if (contentType) {
        if (contentType.includes('png')) return '.png';
        if (contentType.includes('jpeg') || contentType.includes('jpg')) return '.jpg';
        if (contentType.includes('gif')) return '.gif';
        if (contentType.includes('webp')) return '.webp';
        if (contentType.includes('svg')) return '.svg';
        if (contentType.includes('woff2')) return '.woff2';
        if (contentType.includes('woff')) return '.woff';
        if (contentType.includes('css')) return '.css';
        if (contentType.includes('javascript')) return '.js';
    }
    // Fall back to URL extension
    const ext = path.extname(new URL(url).pathname).split('?')[0];
    return ext || '.bin';
}

function download(url) {
    return new Promise((resolve, reject) => {
        const client = url.startsWith('https:') ? https : http;
        const req = client.get(url, { timeout: 15000, headers: {
            'User-Agent': 'Mozilla/5.0 (research dataset preservation)',
            'Accept': '*/*',
        }}, (res) => {
            // Follow redirects
            if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
                download(normalizeUrl(res.headers.location)).then(resolve).catch(reject);
                return;
            }
            if (res.statusCode !== 200) {
                resolve({ status: res.statusCode, data: null, contentType: null });
                return;
            }
            const chunks = [];
            res.on('data', c => chunks.push(c));
            res.on('end', () => {
                resolve({
                    status: 200,
                    data: Buffer.concat(chunks),
                    contentType: res.headers['content-type'] || '',
                });
            });
        });
        req.on('error', e => resolve({ status: 0, data: null, contentType: null, error: e.message }));
        req.on('timeout', () => { req.destroy(); resolve({ status: 0, data: null, contentType: null, error: 'timeout' }); });
    });
}

async function main() {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.mkdirSync(CACHED_SERPS_DIR, { recursive: true });

    // Load existing manifest if resuming
    const manifestPath = path.join(CACHE_DIR, 'manifest.json');
    let manifest = {};
    if (fs.existsSync(manifestPath)) {
        manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    }

    // Scan SERPs
    const serpFiles = singleTrial
        ? [`${singleTrial}.html`]
        : fs.readdirSync(SERP_DIR).filter(f => f.endsWith('.html'));

    console.log(`Scanning ${serpFiles.length} SERP files for external resources...\n`);

    // Phase 1: Collect all unique URLs
    const allUrls = new Map(); // url → Set of trial IDs
    for (const file of serpFiles) {
        const html = fs.readFileSync(path.join(SERP_DIR, file), 'utf8');
        const trialId = path.basename(file, '.html');
        const urls = extractUrls(html);
        for (const rawUrl of urls) {
            const url = normalizeUrl(rawUrl);
            if (!shouldCache(url)) continue;
            if (!allUrls.has(url)) allUrls.set(url, new Set());
            allUrls.get(url).add(trialId);
        }
    }

    console.log(`Found ${allUrls.size} unique cacheable URLs across ${serpFiles.length} SERPs`);

    // Categorize
    const categories = {};
    for (const url of allUrls.keys()) {
        let cat = 'other';
        if (/encrypted-tbn/.test(url)) cat = 'thumbnail';
        else if (/fonts\.gstatic/.test(url)) cat = 'font';
        else if (/\/images\/branding|nav_logo|searchbox/.test(url)) cat = 'branding';
        else if (/\/shopping\//.test(url)) cat = 'shopping-sprite';
        else if (/\/ui\//.test(url)) cat = 'ui-icon';
        else if (/\/maps\/vt\//.test(url)) cat = 'map-tile';
        else if (/googleusercontent/.test(url)) cat = 'proxied-image';
        else if (/\.js(\?|$)/.test(url)) cat = 'script';
        else if (/\.css(\?|$)/.test(url)) cat = 'stylesheet';
        categories[cat] = (categories[cat] || 0) + 1;
    }
    console.log('\nBy category:');
    for (const [cat, n] of Object.entries(categories).sort((a, b) => b[1] - a[1])) {
        console.log(`  ${cat}: ${n}`);
    }

    if (dryRun) {
        console.log('\n--dry-run: skipping downloads');
        return;
    }

    // Phase 2: Download missing URLs
    const toDownload = [...allUrls.keys()].filter(url => !manifest[url]);
    console.log(`\nDownloading ${toDownload.length} new resources (${Object.keys(manifest).length} already cached)...`);

    let downloaded = 0, failed = 0;
    const BATCH_SIZE = 10; // concurrent downloads

    for (let i = 0; i < toDownload.length; i += BATCH_SIZE) {
        const batch = toDownload.slice(i, i + BATCH_SIZE);
        const results = await Promise.all(batch.map(async url => {
            const result = await download(url);
            if (result.status === 200 && result.data) {
                const hash = hashUrl(url);
                const ext = extensionFor(url, result.contentType);
                const filename = hash + ext;
                fs.writeFileSync(path.join(CACHE_DIR, filename), result.data);
                manifest[url] = {
                    file: filename,
                    size: result.data.length,
                    contentType: result.contentType,
                    cached: new Date().toISOString(),
                };
                downloaded++;
                return true;
            } else {
                manifest[url] = {
                    file: null,
                    status: result.status,
                    error: result.error || `HTTP ${result.status}`,
                    attempted: new Date().toISOString(),
                };
                failed++;
                return false;
            }
        }));

        if ((i + BATCH_SIZE) % 100 < BATCH_SIZE) {
            console.log(`  ${Math.min(i + BATCH_SIZE, toDownload.length)}/${toDownload.length} (${downloaded} ok, ${failed} failed)`);
        }

        // Save manifest periodically
        if ((i + BATCH_SIZE) % 200 < BATCH_SIZE) {
            fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
        }
    }

    // Save final manifest
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
    console.log(`\nDownloaded: ${downloaded}, Failed: ${failed}, Total cached: ${Object.keys(manifest).filter(u => manifest[u].file).length}`);

    // Phase 3: Rewrite SERPs to use local paths
    console.log(`\nRewriting ${serpFiles.length} SERP files to use cached resources...`);

    let rewritten = 0;
    for (const file of serpFiles) {
        let html = fs.readFileSync(path.join(SERP_DIR, file), 'utf8');
        let replacements = 0;

        for (const [originalUrl, entry] of Object.entries(manifest)) {
            if (!entry.file) continue;
            const localPath = `../resource-cache/${entry.file}`;

            // Try all URL forms that might appear in the HTML
            const variants = [originalUrl];
            if (originalUrl.startsWith('https://')) {
                variants.push(originalUrl.replace('https://', 'http://'));
                variants.push(originalUrl.replace('https://', '//'));
            }

            for (const variant of variants) {
                if (html.includes(variant)) {
                    html = html.split(variant).join(localPath);
                    replacements++;
                }
            }
        }

        if (replacements > 0) {
            fs.writeFileSync(path.join(CACHED_SERPS_DIR, file), html);
            rewritten++;
        }
    }

    console.log(`Rewrote ${rewritten} SERPs → ${CACHED_SERPS_DIR}`);
    console.log('\nDone. Manifest: ' + manifestPath);

    // Summary stats
    const cached = Object.values(manifest).filter(e => e.file);
    const totalBytes = cached.reduce((s, e) => s + (e.size || 0), 0);
    console.log(`Total cache size: ${(totalBytes / 1024 / 1024).toFixed(1)} MB across ${cached.length} files`);
}

main().catch(e => { console.error(e); process.exit(1); });
