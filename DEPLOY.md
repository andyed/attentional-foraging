# Deploy — attentional-foraging

**Live URL:** https://andyed.github.io/attentional-foraging/
**Source branch:** `gh-pages`, path `/`
**Deploy trigger:** **Manual.** Push to `main` does NOT auto-deploy — the
`gh-pages` branch holds the built artifact and is what GitHub Pages serves.
**Build command:** `node scripts/build-gh-pages.js` — Playwright-driven,
long-running (renders gazeplots via Scrutinizer for each curated trial).
**Deploy command:** `gh-pages -d site` (or equivalent push of `site/` contents
to the `gh-pages` branch root).

Deploy path is documented at the tail of `scripts/build-gh-pages.js` (line 1037):
> `Deploy: gh-pages -d site  (or push site/ to gh-pages branch)`

## Minimal-change protocol (text-only patches)

**Do NOT run the full build for analytics-key changes, copy edits, or other
text-only patches.** The build regenerates Playwright screenshots against current
Scrutinizer state and can drift output beyond your intended change.

Instead — edit the `gh-pages` branch directly:

```bash
# 1. Check out gh-pages in a worktree (leaves your main working tree alone)
cd ~/Documents/dev/attentional-foraging
git fetch origin gh-pages
git worktree add /tmp/af-gh-pages gh-pages
cd /tmp/af-gh-pages
git rebase origin/gh-pages   # in case local gh-pages pointer is stale

# 2. Make the surgical edit
find . -name '*.html' -exec sed -i '' 's|OLD_TEXT|NEW_TEXT|g' {} +

# 3. Commit and push
git add -A
git commit -m "analytics: …"
git push origin gh-pages

# 4. Remove the worktree
cd ~/Documents/dev/attentional-foraging
git worktree remove /tmp/af-gh-pages
```

Also update `scripts/build-gh-pages.js` on `main` so the **next** full rebuild
produces matching output. The gh-pages branch is the source of truth for
"what's served now"; the build script on main is the source of truth for
"what the next build will produce."

## Full rebuild (when you actually need a build)

```bash
cd ~/Documents/dev/attentional-foraging
node scripts/build-gh-pages.js    # regenerates site/ (gitignored on main)
npx gh-pages -d site              # push site/ to gh-pages branch
```

Requires Playwright + Chromium + Scrutinizer available at
`../scrutinizer-repo/scrutinizer2025`. Expect minutes per trial (31 curated
trials as of 2026-04-23).

## Verification

```bash
curl -s https://andyed.github.io/attentional-foraging/ | grep -o "phc_[A-Za-z0-9]*"
# expect phc_pJJNd2... (approach-retreat shared research project)
```

## Files to know

- `site/` — **gitignored** on `main`, generated locally by `build-gh-pages.js`
- `gh-pages` branch — the deployed artifact; edit surgically for text-only patches
- `scripts/build-gh-pages.js` — the template / source-of-truth for the next build
- `scripts/find_interesting_trials.py`, `scripts/generate-anchors.js` — upstream
  of the build; don't touch for analytics-only changes

## PostHog

Writes to **approach-retreat project (374762)** as of 2026-04-23. This project
is the shared "research viewers" project for both `attentional-foraging` and
the sister `approach-retreat` repo. Previously writing to Scrutinizer.
