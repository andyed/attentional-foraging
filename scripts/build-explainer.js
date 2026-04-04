#!/usr/bin/env node
/**
 * Pre-render the OSEC explainer from marginalia markdown to static HTML.
 * Runs at build time — no client-side JS needed for rendering.
 *
 * Usage: node scripts/build-explainer.js
 * Output: site/explainer/index.html
 */

const fs = require('fs');
const path = require('path');
const { convert } = require(path.join(__dirname, '..', '..', 'marginalia', 'marginalia-md.js'));

const ROOT = path.join(__dirname, '..');
const DRAFT = path.join(ROOT, 'docs', 'drafts', 'osec-explainer.md');
const OUT_DIR = path.join(ROOT, 'site', 'explainer');
const OUT = path.join(OUT_DIR, 'index.html');

fs.mkdirSync(OUT_DIR, { recursive: true });

const md = fs.readFileSync(DRAFT, 'utf8');
// Strip the markdown H1 — we use a custom HTML header
const body = md.replace(/^# .+\n/, '');
let content = convert(body);
// Fix dropcap: marginalia-md renders {dropcap} as a badge span.
// Replace the badge + following text with a proper dropcap wrapper.
content = content.replace(
  /<p><span class="mg-badge">dropcap<\/span>\s*/g,
  '<p class="has-dropcap">'
);

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Search Results F-Heatmap, Stroke by Stroke</title>
  <meta name="description" content="The F-pattern is two cognitive phases superimposed in one heatmap. 2,776 eye-tracked search sessions decomposed stroke by stroke.">
  <meta property="og:title" content="The Search Results F-Heatmap, Stroke by Stroke">
  <meta property="og:description" content="The F-pattern is two cognitive phases superimposed in one heatmap. We decomposed 2,776 eye-tracked search sessions stroke by stroke.">
  <meta property="og:type" content="article">
  <meta property="article:published_time" content="2026-04-04">
  <meta name="author" content="Andy Edmonds">

  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/marginalia@latest/marginalia.css">

  <style>
    :root { --mg-max-width: 900px; }
    body {
      font-family: 'Georgia', 'Times New Roman', serif;
      background: #fafaf8;
      color: #222;
      line-height: 1.75;
      margin: 0; padding: 0;
    }
    .page-header {
      max-width: 660px; margin: 3em auto 0; padding: 0 2em;
    }
    .page-header h1 {
      font-size: 2.2em; line-height: 1.2; margin-bottom: 0.2em; color: #111;
    }
    .page-header .subtitle {
      font-size: 1.05em; color: #666; margin-bottom: 0.5em;
    }
    .page-header .byline {
      font-size: 0.85em; color: #999; margin-bottom: 2em;
    }
    .page-header .byline a { color: #888; }
    /* Outside-margin callouts — short punchy labels on wide screens */
    .outer-note {
      position: absolute;
      right: -180px;
      width: 150px;
      font-size: 0.75em;
      font-weight: 600;
      color: #b08050;
      line-height: 1.3;
    }
    @media (max-width: 1100px) { .outer-note { display: none; } }
    @media (max-width: 768px) {
      .mg-margin, aside.mg-sidebar {
        float: none;
        width: 100%;
        margin: 1em 0;
        font-size: 0.85em;
      }
      .page-header h1 { font-size: 1.6em; }
      #content { padding: 0 1em 3em; }
      .page-header { padding: 0 1em; }
    }
    /* Links */
    #content a { color: #2a6496; text-decoration: none; border-bottom: 1px solid #2a649640; }
    #content a:visited { color: #6a4c93; border-bottom-color: #6a4c9340; }
    #content a:hover { color: #1a4a7a; border-bottom-color: #1a4a7a; }
    #content {
      max-width: 920px; margin: 0 auto; padding: 0 2em 4em;
    }
    /* Margin notes and sidebars float right within the content area */
    .mg-margin, aside.mg-sidebar {
      float: right;
      clear: right;
      width: 230px;
      margin: 0 0 1em 1.5em;
      font-size: 0.8em;
      line-height: 1.5;
      color: #5a4a3a;
      border-left: 3px solid #d4a574;
      background: #fdf8f2;
      border-radius: 0 4px 4px 0;
      padding: 8px 12px;
    }
    #content img {
      max-width: 100%; display: block; margin: 1.5em auto;
      clear: both;
    }
    /* Callouts — subtle tinted backgrounds with left accent */
    .mg-callout { font-size: 0.9em; border: none; border-radius: 0 4px 4px 0; padding: 10px 14px; margin: 1em 0; }
    .mg-callout[data-type="important"] { background: #fdf5f5; border-left: 3px solid #cc444480; }
    .mg-callout[data-type="note"] { background: #f5f8fd; border-left: 3px solid #2266cc80; }
    .mg-callout[data-type="warning"] { background: #fdf9f0; border-left: 3px solid #cc880080; }
    .mg-callout[data-type="tip"] { background: #f2faf4; border-left: 3px solid #22883380; }
    .stats-detail {
      font-size: 0.82em; color: #6a5a4a; background: #f8f4ee; border-radius: 3px;
      padding: 3px 8px; margin: 0.2em 0; display: inline;
      border-bottom: 1px dashed #d4a574;
    }
    #content h2 {
      font-size: 1.5em; margin-top: 2.5em;
      border-bottom: 1px solid #ddd; padding-bottom: 0.3em;
    }
    #content h3 { font-size: 1.15em; margin-top: 1.8em; }
    /* References: two-column, compact */
    #content h3:last-of-type, #content h3:nth-last-of-type(2) { margin-top: 1.2em; }
    #content ul:last-of-type, #content ul:nth-last-of-type(2) {
      columns: 2; column-gap: 2em; font-size: 0.82em; line-height: 1.5;
    }
    #content ul:last-of-type li, #content ul:nth-last-of-type(2) li {
      break-inside: avoid; margin-bottom: 0.4em;
    }
    #content table { font-size: 0.9em; border-collapse: collapse; width: 100%; margin: 1em 0; }
    #content th, #content td { text-align: left; padding: 6px 12px; border-bottom: 1px solid #eee; }
    #content th { font-weight: 600; border-bottom: 2px solid #ddd; }
    #content code {
      font-size: 0.85em; background: #f0efe8; padding: 1px 5px; border-radius: 3px;
    }
    #content pre {
      background: #f0efe8; padding: 1em; border-radius: 6px;
      overflow-x: auto; font-size: 0.8em; line-height: 1.5;
    }
    #content hr { border: none; border-top: 1px solid #ddd; margin: 2.5em 0; }
    /* OSEC stage colors */
    #content h2:nth-of-type(1) { color: #b8860b; border-bottom-color: #b8860b40; } /* Orient = gold */
    #content h2:nth-of-type(2) { color: #cc4444; border-bottom-color: #cc444440; } /* Survey = red */
    #content h2:nth-of-type(3) { color: #2266cc; border-bottom-color: #2266cc40; } /* Evaluate = blue */
    #content h2:nth-of-type(4) { color: #228833; border-bottom-color: #22883340; } /* Commit = green */
    /* Dropcap */
    p.has-dropcap::first-letter {
      float: left; font-size: 3.4em; line-height: 0.8;
      padding-right: 0.08em; padding-top: 0.05em;
      color: #333; font-family: Georgia, serif;
    }
    footer {
      max-width: 660px; margin: 0 auto; padding: 2em 2em;
      border-top: 1px solid #ddd; font-size: 0.8em; color: #999;
    }
    footer a { color: #888; }
  </style>
</head>
<body>

<div class="page-header">
  <h1>The Search Results F-Heatmap, Stroke by Stroke</h1>
  <div class="subtitle">2,776 eye-tracked search sessions reveal that the F-pattern's horizontal bars and vertical stem are two distinct cognitive operations — drawn 1.3 seconds apart</div>
  <div class="byline">Andy Edmonds · April 2026 · Based on <a href="https://doi.org/10.1145/3726302.3730325">AdSERP</a> (Latifzadeh, Gwizdka &amp; Leiva, SIGIR 2025)</div>
</div>

<div id="content">
${content}
</div>

<footer>
  Andy Edmonds · andyed@alum.cmu.edu · github.com/andyed/attentional-foraging
</footer>

</body>
</html>`;

fs.writeFileSync(OUT, html);
console.log(`✓ ${OUT} (${(html.length / 1024).toFixed(1)}KB)`);
