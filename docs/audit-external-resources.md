# Audit: External Resources in SERP HTML Snapshots

**Date:** 2026-04-02
**Sample:** 20 files across 20 participants, varied blocks and trials
**Total corpus:** 2,776 SERP HTML files
**Average file size:** 569 KB (range: 349 KB -- 854 KB)

All SERPs are Google Search results for product purchase queries (e.g., "buy momentum brands 9 led flashlight"), captured from google.es with `hl=en`. They contain organic results, ads (Shopping/PLA), image carousels, Maps links, and knowledge panels.

---

## Summary Table: Domains by Frequency and Resource Type

| Domain | Freq (N/20) | Resource Types | Layout Impact |
|--------|-------------|----------------|---------------|
| www.google.com | 20 | search links, images, Maps, ad clicks (aclk) | HIGH -- branding images, map tiles, ad product images |
| fonts.gstatic.com | 20 | fonts (Google Sans woff2) | HIGH -- text rendering |
| ssl.gstatic.com | 20 | UI images (checkmark icons) | LOW -- small UI chrome |
| www.gstatic.com | 20 | JS, CSS, UI images, Shopping CSS sprites | MEDIUM -- JS drives interactivity, CSS sprites for Shopping |
| encrypted-tbn0.gstatic.com | 18 | images (Google-proxied thumbnails) | HIGH -- product/result thumbnails |
| encrypted-tbn1/2/3.gstatic.com | 11--14 | images (additional thumbnail shards) | HIGH -- same as above |
| maps.google.com | 20 | Maps links | LOW -- link targets only, not rendered assets |
| accounts.google.com | 20 | meta (login link) | NONE |
| consent.google.com | 20 | meta (cookie consent) | NONE |
| policies.google.com | 20 | meta (privacy/terms links) | NONE |
| support.google.com | 20 | meta (help links) | NONE |
| apis.google.com | 20 | JS API endpoint | LOW |
| ogs.google.com | 20 | widget/app loader | LOW |
| webcache.googleusercontent.com | 20 | cached page links | NONE |
| en.wikipedia.org | 20 | knowledge panel links | NONE -- link target |
| www.google.es | 20 | locale-specific links | NONE |
| schema.org | 20 | HTML metadata (itemtype) | NONE |
| www.w3.org | 20 | SVG/XML namespace URIs | NONE |
| www.googleadservices.com | 19 | ad tracking/redirect | NONE -- click tracking |
| www.amazon.com | 19 | organic result links | NONE -- link target |
| www.ebay.com | 15 | organic result links | NONE -- link target |
| m.media-amazon.com | 10 | product images (in href, not src) | NONE -- linked, not rendered |
| www.amazon.es / .de / .ca | 9--12 | organic result links | NONE |
| www.walmart.com | 5 | organic result links | NONE |
| i.ebayimg.com | 4 | product images (in href, not src) | NONE -- linked, not rendered |
| www.aliexpress.com | 2 | organic result links | NONE |
| ae01.alicdn.com / s.alicdn.com | 2 | product images (in href) | NONE |
| cdn.shopify.com | 3 | product images (in href) | NONE |
| lh4/5.googleusercontent.com | 3 | Google-proxied images | MEDIUM |
| ajax.googleapis.com | 2 | jQuery/JS library | MEDIUM -- if loaded, drives behavior |
| translate.google.com | 4 | translation links | NONE |

---

## Resource Categories in Detail

### 1. Fonts (fonts.gstatic.com) -- 20/20 SERPs

Five `@font-face` blocks per file (100 total across 20 files), all for Google Sans 400 weight:

```
http://fonts.gstatic.com/s/googlesans/v14/4UaGrENHsxJlGDuGo1OIlL3Owp4.woff2  (Latin)
http://fonts.gstatic.com/s/googlesans/v14/4UaGrENHsxJlGDuGo1OIlL3Awp5MKg.woff2 (Latin Extended)
http://fonts.gstatic.com/s/googlesans/v14/4UaGrENHsxJlGDuGo1OIlL3Bwp5MKg.woff2 (Vietnamese)
http://fonts.gstatic.com/s/googlesans/v14/4UaGrENHsxJlGDuGo1OIlL3Kwp5MKg.woff2 (Cyrillic)
http://fonts.gstatic.com/s/googlesans/v14/4UaGrENHsxJlGDuGo1OIlL3Nwp5MKg.woff2 (Greek)
```

Also: `fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg` (Google "G" icon).

All declared with `font-display: optional` -- the browser can skip them if they don't load in time. This means blocking these fonts will cause a fallback font but won't break layout.

### 2. Google-Proxied Thumbnails (encrypted-tbn*.gstatic.com) -- 18/20 SERPs

These are the **product/result images visible in the SERP**. Google proxies external images through its own CDN for the thumbnail carousel and shopping results.

- **261 unique thumbnail URLs** across the 20-file sample
- Per-file range: 0--25 thumbnails (mean ~10)
- Pattern: `//encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR...&s` or `&s=0`
- These appear in `<img src>` attributes with explicit `width` and `height`
- Common widths: 142px (most frequent), 114px, 160px, 34px, 92px

**These are the main layout-affecting external images.** They are Google's own re-encoded copies of product photos, not direct merchant URLs.

### 3. Google UI Assets (ssl.gstatic.com, www.gstatic.com) -- 20/20 SERPs

Small UI elements:
```
http://ssl.gstatic.com/ui/v1/menu/checkmark.png
http://ssl.gstatic.com/ui/v1/menu/checkmark2.png
http://www.gstatic.com/ui/v1/activityindicator/loading_24.gif
https://www.gstatic.com/images/icons/material/system/1x/keyboard_arrow_right_grey600_24dp.png
https://www.gstatic.com/shopping/scu/images/css/css_3831351_1.png  (Shopping CSS sprite)
https://www.gstatic.com/shopping/scu/images/css/css_4051689.png
https://www.gstatic.com/local/photos/confirmation.svg
```

### 4. Google Branding Images (www.google.com) -- 20/20 SERPs

```
http://www.google.com/images/branding/googlelogo/2x/googlelogo_color_92x30dp.png
http://www.google.com/images/nav_logo321.webp
http://www.google.com/images/searchbox/desktop_searchbox_sprites318_hr.webp
http://www.google.com/images/experiments/wavy-underline.png
```

### 5. JavaScript (www.gstatic.com, ajax.googleapis.com) -- 20/20 SERPs

```
https://www.gstatic.com/og/_/js/k=og.qtm.en_US.5PidA0mG0wE.O/rt=j/m=qabr,...
https://www.gstatic.com/og/_/js/k=og.qtm.en_US.5PidA0mG0wE.O/rt=j/m=qdsh/...
https://ajax.googleapis.com/... (jQuery, 2/20 files)
```

### 6. CSS (www.gstatic.com) -- 20/20 SERPs

```
https://www.gstatic.com/og/_/ss/k=og.qtm.WrQ52X1LL84.L.W.O/m=qcwid/...
```

### 7. Data URI Images (inline, no external fetch) -- 1,614 across 20 files

Substantial use of inline data URIs for:
- SVG icons (navigation arrows, star ratings, tab icons)
- Small PNG decorations
- 1px transparent GIF spacers

These are **embedded in the HTML** and require no external fetch.

### 8. Google Ad/Shopping URLs (www.google.com/aclk) -- 19/20 SERPs

**1,065 ad click URLs** across the sample. These are `href` targets for Google Shopping product listing ads, not resources that load automatically. Pattern:
```
http://www.google.com/aclk?sa=L&ai=DChcSEw...&sig=AOD64_...&ctype=5&...
```

Some SERPs contain Shopping carousels with `data-merchant`, `pla-*`, and `commercial-unit` markup (observed in 3/3 files checked for these patterns).

### 9. Maps Tile (www.google.com) -- 1/20 SERPs

One file (p040-b3-t8.html, the CPAP query) contained an actual map tile image:
```
http://www.google.com/maps/vt/data=tCPGmMiU7uP...
```

This is rare -- only product queries that triggered a local business panel would include one.

### 10. Google Tracking (gen_204) -- 20/20 SERPs

103 `gen_204` references across 20 files. These are 1x1 tracking pixels fired via JavaScript -- they don't affect layout.

---

## Merchant Domain Analysis

**Do any SERPs reference resources from actual merchant sites?**

**No merchant images appear in `<img src>` attributes.** Google proxies all product thumbnails through `encrypted-tbn*.gstatic.com`. Merchant domains appear only as:

| Role | Examples | Count |
|------|----------|-------|
| Organic result `href` targets | www.amazon.com, www.ebay.com, www.walmart.com | 19, 15, 5 /20 |
| Product image URLs in `href` (link targets, not loaded) | m.media-amazon.com, i.ebayimg.com, ae01.alicdn.com | 10, 4, 2 /20 |
| Knowledge panel text | en.wikipedia.org/wiki/Amazon_(company), .../EBay | 20/20 |

Merchant CDN domains found (linked, not rendered):
- **Amazon:** m.media-amazon.com (10/20), images-na.ssl-images-amazon.com (3/20)
- **eBay:** i.ebayimg.com (4/20)
- **AliExpress:** ae01.alicdn.com (2/20), s.alicdn.com (1/20), sc04.alicdn.com (1/20)
- **Shopify:** cdn.shopify.com (3/20)
- **Walmart:** i5.walmartimages.com (1/20)
- **Other retailers:** cdn.autocontent.lv, cdn11.bigcommerce.com, images.ctfassets.net

These appear in the full URL of organic search result links (Google includes the destination page's og:image in structured data), not as rendered resources.

---

## Layout Impact Assessment

### Affects layout (missing = broken/shifted rendering)

| Resource | Mechanism | Consequence if missing |
|----------|-----------|----------------------|
| encrypted-tbn*.gstatic.com thumbnails | `<img>` with width/height | Image carousel and shopping results show blank boxes (dimensions preserved by HTML attributes) |
| Google branding images | `<img>` for logo, search bar | Google chrome area looks broken |
| Maps tile | `<img src>` in local panel | Local business panel shows blank map |
| Shopping CSS sprites (www.gstatic.com) | Background-image in CSS | Shopping result formatting broken |

### Cosmetic only (missing = degraded but functional)

| Resource | Mechanism | Consequence if missing |
|----------|-----------|----------------------|
| Google Sans fonts | @font-face with `font-display: optional` | Falls back to system font; text still readable, minor metrics shift |
| UI icons (checkmarks, arrows) | Small decorative images | Missing checkmarks in menus; arrows gone |
| SVG data URIs | Inline in HTML | Already embedded, can't be "missing" |

### No render impact (link targets, tracking, metadata)

| Resource | Count |
|----------|-------|
| schema.org, www.w3.org namespace URIs | 20/20 |
| Merchant site links (amazon, ebay, walmart, etc.) | varies |
| Google consent/accounts/support/policies links | 20/20 |
| gen_204 tracking pixels | 103 refs |
| Ad click-through URLs (aclk) | 1,065 refs |
| webcache.googleusercontent.com links | 20/20 |
| maps.google.com links (not tile images) | 20/20 |

---

## Recommendations: Cache vs Block

### Cache locally (needed for faithful rendering)

| Resource | Why |
|----------|-----|
| `encrypted-tbn*.gstatic.com/images?*` | Product thumbnails. These are the most important visual content. Without them, the SERP looks empty. Cache all unique URLs. |
| `www.google.com/images/branding/*` | Google logo and search bar sprites. Small set, stable URLs. |
| `www.google.com/maps/vt/data=*` | Map tiles (rare, only 1/20 SERPs). |
| `fonts.gstatic.com/s/googlesans/v14/*` | 5 font files. Identical across all SERPs. |
| `ssl.gstatic.com/ui/v1/*` | 2 checkmark PNGs. Identical across all SERPs. |
| `www.gstatic.com/shopping/scu/images/css/*` | Shopping result sprites. Small set. |
| `www.gstatic.com/images/icons/material/*` | Material icons. Small set. |
| `lh*.googleusercontent.com/proxy/*` | Google-proxied images in knowledge panels (3/20 SERPs). |

### Block / ignore (no rendering value)

| Resource | Why |
|----------|-----|
| `www.google.com/aclk?*` | Ad click redirects. No visual content. |
| `www.googleadservices.com/*` | Ad tracking. |
| `gen_204` URLs | Tracking beacons. |
| `consent.google.com/*` | Cookie consent dialog -- irrelevant to SERP layout. |
| `accounts.google.com/*` | Login redirect. |
| `www.gstatic.com/og/_/js/*` | Google's interactive JS. Blocks these to prevent dynamic DOM mutation if rendering statically. |
| `ajax.googleapis.com/*` | jQuery/utility JS. Same rationale. |
| `apis.google.com` | API loader. |
| `ogs.google.com/*` | Widget loader. |

### Neither cache nor block (harmless link targets)

All merchant domains (amazon.com, ebay.com, etc.), Wikipedia, translate.google.com, support/policies pages. These are just `href` values in anchor tags -- the browser won't fetch them unless clicked.

---

## Resource Cache

A partial cache of external resources was captured on 2026-04-04 using `scripts/cache-serp-resources.js`. Results:

- **6,466 of 29,905 unique URLs cached** (22%) — 22.1 MB uncompressed, 25 MB zipped
- **23,439 URLs already returned HTTP 404** (78%) — Google's CDN thumbnail URLs have decayed since the December 2022 data collection
- Cached resources are in `AdSERP/data/resource-cache/` (gitignored due to size)
- Rewritten SERP HTMLs using local paths are in `AdSERP/data/serps-cached/` (gitignored)
- Available on request from the project maintainers

The layout-freeze approach (`scripts/generate-anchors.js` + `layout-freeze/`) ensures fixation overlay stability regardless of image availability. The cached images improve visual fidelity and saliency computation accuracy for the 22% that survived.

## Key Finding

The SERP snapshots are **self-contained for layout purposes** with only two categories of external fetches that matter:

1. **~10 Google-proxied product thumbnails per SERP** (encrypted-tbn*.gstatic.com) -- these are the primary visual content
2. **~10 static Google UI assets** (fonts, logos, icons, sprites) -- identical across all SERPs, trivial to cache once

No merchant site resources are loaded as rendered content. Google's thumbnail proxy means the SERPs never make direct requests to amazon.com, ebay.com, etc. for images -- all product photos are re-served through Google's own CDN.
