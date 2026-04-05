# Backlog: Live External Resources in AdSERP SERP HTML — Foundational Dataset Reuse Issue

## Problem

The AdSERP SERP HTML files reference live external resources:
- Google Maps tiles (for local results)
- Product images (Shopping results, thumbnails)
- Google Fonts (WOFF2)
- Analytics/tracking scripts
- Favicon sprites
- Google-hosted CSS

When these SERPs are re-rendered (by Playwright, by Scrutinizer, by any future researcher), the external resources either:
1. Fail to load (CORS, expired URLs, changed CDN paths) → broken layout
2. Load different versions (updated images, resized tiles) → shifted layout
3. Load successfully but with different timing → non-deterministic rendering

This is the root cause of the fixation overlay drift — DOM snapping resolves CSS selectors correctly, but element positions shift because the images/embeds that defined the original layout are gone or different.

## Impact

- **DOM anchor resolution**: Anchors point to the right elements but elements are in the wrong positions
- **Fixation overlay**: 13px median drift, up to 45px at page bottom
- **Saliency computation**: Saliency maps computed on the degraded render miss visual features that were present in the original session
- **Dataset reproducibility**: Any researcher re-analyzing this data will face the same issue. This is a methodological concern for the field.

## Investigation Needed

1. **Catalog all external resource domains** referenced across the 2,776 SERP HTMLs
2. **Classify by type**: images, fonts, scripts, CSS, maps, tracking
3. **Test load success rate**: What fraction of URLs still resolve in 2026?
4. **Measure layout impact**: For each failed resource, how many pixels of layout shift does it cause?

## Potential Solutions (in order of preference)

### A. Freeze element dimensions (fast, robust)
At anchor-generation time, record each element's `getBoundingClientRect()`. At resolve time, apply `style.width` and `style.height` to force the original dimensions even when images fail to load. Doesn't need the actual images — just their layout footprint.

**Pros**: Fast, no storage cost, deterministic
**Cons**: Saliency computation still sees degraded images (no visual content)

### B. Resource cache (full fidelity)
Download all external resources at build time, rewrite URLs to local copies. Store in `AdSERP/data/resource-cache/`.

**Pros**: Full visual fidelity, saliency maps match original
**Cons**: Large storage (~100MB+?), resources may already be gone, needs periodic refresh

### C. Content Security Policy lockdown
Add `<meta http-equiv="Content-Security-Policy" content="default-src 'self' data:">` to SERP HTMLs at render time. All external requests fail immediately and predictably.

**Pros**: 100% stability (zero external calls), fast rendering
**Cons**: Zero image content, worst visual fidelity

### D. Hybrid: freeze dimensions + CSP
Combine A and C: force original dimensions on all elements AND block external calls. Layout is perfect, rendering is deterministic, no external dependencies.

**Pros**: Stable layout, fast, deterministic, no external dependencies
**Cons**: No image content (affects saliency and visual presentation)

## Priority

**P0 for stability, P1 for fidelity.** The immediate need is deterministic rendering (option D). Full visual fidelity (option B) is nice-to-have and can be layered on later.

## Methodological Note

This should be documented as a limitation / recommendation for future researchers using the AdSERP dataset. Archived SERP datasets that reference live resources have a decay half-life — the longer since data collection, the less faithful the re-rendering. Future datasets should consider:
- Archiving resources at capture time (WARC, MHTML)
- Recording element dimensions alongside coordinates
- Using CSP to ensure deterministic offline rendering
