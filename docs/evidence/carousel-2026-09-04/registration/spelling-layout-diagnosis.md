# Saved spelling block and screenshot-layout mismatch

Read-only investigation, 2026-09-04. Production SERPs, screenshots, AOIs, and
analysis outputs were not edited. Probe mutations were confined to ephemeral,
network-blocked Playwright pages.

## Supported cause

The three visibly shifted trials in the retained 61-trial top-carousel sample
are exactly its three raw HTML pages containing `Did you mean:`:
`p006-b5-t2`, `p040-b4-t3`, `p048-b3-t6`. Both raw and cached HTML retain
`#taw > #oFNiHe > p.gqLncc.card-section.KDCVqf`. Original screenshots of all
three lack the spelling block, while preserving the same query/result context.

On all three pages, local rendering puts the first product card at
258.265625 CSS px. Removing only `#oFNiHe` in the ephemeral page moves it to
215 CSS px: a 43.265625 CSS px difference, approximately 39 screenshot px
under the recorded screenshot scaling. The paragraph has a 21 px text line,
5.28 px top margin, and 17 px bottom margin. This explains the direction and
size of the observed displacement. It does not prove how the original
capture process omitted that block.

The same first-card Y is obtained from raw and cached HTML, and at viewport
widths 1389 and 1280. Changing the viewport width changes X, but does not
remove this Y discrepancy. Disabling JavaScript activates Google's noscript
replacement and removes the carousel; it is not a valid rendering remedy.

The local resource-cache writer only replaces resource URL strings in HTML
(`attentional-foraging/scripts/cache-serp-resources.js:283-316`); no spelling
removal occurs there. The independently inspected raw HTML already contains
the block, so this is not insertion by resource caching.

## Independent additional originals

Raw HTML search found 123 spelling-block pages, 79 with original top-ad
annotations. Six additional pages spread through that set were selected and
their original screenshots inspected before screenshot-registration outputs
were consulted. All six screenshots lack the spelling module:

| Trial | Visually counted top product cards |
|---|---:|
| p004-b2-t8 | 5 |
| p011-b5-t10 | 5 |
| p028-b6-t8 | 5 |
| p040-b6-t5 | 4 |
| p045-b5-t1 | 5 |
| p050-b2-t1 | 5 |

Positive-area partial cards are included. The separate right-side shopping
directory on the final page is outside this top-row count. This is a small
held-out visual check, not a claim that all 79 pages share the same mismatch.

## What the public source establishes

The [AdSERP paper, sections 4.1–4.3](https://arxiv.org/html/2507.08003v1)
describes saved HTML, separately produced Selenium screenshots, and DOM-based
Selenium ad-box extraction. The public preprocessing examples
[`aoi-extraction-example.py`](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/extra-preprocessing-scripts/aoi-extraction-example.py),
[`utils.py`](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/extra-preprocessing-scripts/utils.py),
[`find_top_ad.py`](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/extra-preprocessing-scripts/find_top_ad.py),
and [`block-cookie-acceptance.js`](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/extra-preprocessing-scripts/block-cookie-acceptance.js)
do not establish an intentional spelling-removal step. The original complete
screenshot/capture pipeline was not found. Do not attribute this mismatch to
a known dataset-side stripping implementation.

## Repair implication

One unconditional deletion rule would go beyond the established capture
evidence. A bounded translation derived from independent original screenshot
card borders can verify the geometry for a particular trial while retaining
raw DOM rectangles and recording the correction separately. It must reject
ambiguous offsets, missing card borders, unsupported border styles, and
unexplained extra outlines. Border alignment does not validate product
content/semantic identity or establish corpus-wide extraction accuracy.

Evidence: `render-probes.json`, `probe_spelling_render.py`,
`spelling-files.txt`, `additional-spelling-top-trials.json`, and
`additional-spelling-top-contact.png` in this review directory.
