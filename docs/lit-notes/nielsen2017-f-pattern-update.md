# Nielsen Norman Group: F-Shaped Pattern — 2017 Update (revised 2024)

Source: https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
Originally published: 2017-11-12. Updated: 2024-02-02.
Authors: Kara Pernice (primary), building on Nielsen 2006.

## Key claims

### The F is a conditional fallback, not a universal behavior
Three conditions must ALL be present for F-scanning:
1. Unformatted text (no bolding, bullets, subheadings)
2. User trying to be efficient
3. User not committed enough to read every word

"The F-pattern is the default pattern when there are no strong cues to attract the eyes towards meaningful information."

### Five other scanning patterns identified
- **Layer-cake**: scan headings, skip body text
- **Spotted**: skip chunks, looking for specific items (links, numbers, keywords)
- **Marking**: eyes stay fixed while scrolling (common on mobile)
- **Bypassing**: skip repeated first words in lists
- **Commitment**: read everything (high motivation)

### F-scanning is framed as a failure mode
"F-scanning is bad for users and businesses" — users skip content on the right side. But they acknowledge this is "globally rational": users optimize across websites, not within any single one.

### The shorter lower bar
Described but not explained: "First few words on the left of each line of text receive more fixations than subsequent words on the same line. Thus, on the first lines of text, people will scan more words on the right than on the following lines."

No analysis of WHY. No survival effect discussion. No temporal decomposition.

### No discussion of SERPs
The 2017 update does not mention search results pages. The F-pattern-on-SERPs extrapolation was done by the broader UX community, not NNG themselves in this article.

### No discussion of heatmap limitations
The temporal collapsing problem (two behaviors superimposed) is not acknowledged. The article uses heatmaps and gaze plots but doesn't discuss what heatmaps lose.

## What they got right
- The F is conditional, not universal
- Multiple scanning patterns exist
- Users are globally rational, not lazy
- Good design prevents F-scanning ("do the work for the users")
- The pattern varies (E, L, inverted-L shapes also observed)

## What's missing (our contribution fills)
- **Temporal decomposition**: The F's three movements are two cognitive operations (survey + evaluate) with different saccade amplitudes, pupil signatures, and cognitive costs
- **Survival effect**: The shorter lower bar is attrition (fewer users scroll), not declining reading depth
- **SERP-specific analysis**: NNG didn't study SERPs in the 2017 update; the F-on-SERPs was an industry extrapolation
- **Pupillometry**: No cognitive load measurement in NNG's work
- **Per-fixation analysis**: NNG used aggregate heatmaps; we have 150Hz per-fixation data from 2,776 trials

## How to cite them charitably
NNG's 2017 update is more nuanced than the 2006 original. They identified multiple patterns, specified conditions, and acknowledged the F as a fallback. The industry's over-application of the F-pattern to SERPs and universal "put everything above the fold" advice was downstream of NNG, not authored by them. Our critique is of the aggregate heatmap methodology and the inferences drawn from it, not of NNG's increasingly careful caveats.
