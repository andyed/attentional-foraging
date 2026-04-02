const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const siteDir = 'site';
fs.mkdirSync(path.join(siteDir, 'png'), { recursive: true });
const files = fs.readdirSync(siteDir).filter(f => f.match(/^p\d+-b\d+-t\d+\.html$/)).sort();
(async () => {
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ viewport: { width: 1320, height: 1024 }, deviceScaleFactor: 2 });
    for (const f of files) {
        const id = f.replace('.html', '');
        const page = await ctx.newPage();
        await page.goto('file://' + path.resolve(siteDir, f), { waitUntil: 'networkidle' });
        await page.waitForTimeout(2000);

        // Screenshot the full serp-container (gazeplot + overlay, full page height)
        const container = await page.$('.serp-container');
        if (container) {
            await container.screenshot({ path: path.join(siteDir, 'png', id + '.png') });
            const mb = (fs.statSync(path.join(siteDir, 'png', id + '.png')).size / 1024 / 1024).toFixed(1);
            console.log('  ✓ ' + id + ' ' + mb + 'MB');
        }
        await page.close();
    }
    await browser.close();
})();
