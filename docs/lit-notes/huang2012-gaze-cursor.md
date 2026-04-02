# Huang, White & Buscher (2012) — User See, User Point

**Paper:** "User See, User Point: Gaze and Cursor Alignment in Web Search"
**Authors:** Jeff Huang (U. Washington), Ryen W. White (Microsoft Research), Georg Buscher (Microsoft Bing)
**Venue:** CHI '12, Austin, TX
**DOI:** [10.1145/2207676.2208591](https://doi.org/10.1145/2207676.2208591)
**Citations:** 157

## Study Design

- 36 subjects, 32 search tasks (half navigational, half informational) on Bing
- Tobii x50 eye tracker at 50 Hz, 1280×1024 display
- Cursor recorded at ~10 Hz
- 1,210 search tasks yielding 1,336,647 gaze positions and 87,227 cursor positions
- Gaze interpolated to cursor timestamps for alignment analysis

## Core Findings

### 1. Cursor lags gaze by ~700ms

Cross-correlation analysis shows minimum RMSE when cursor positions are shifted 700ms into the future — the user looks at something, then ~700ms later the cursor arrives there. This is consistent across subjects, though the lag varies from 250ms (fast movers) to >1000ms (slow movers). The inverse (gaze lagging cursor) never occurs.

**Relevance to us:** This 700ms lag is a stable individual difference. Our TTI calibrator may be capturing the same underlying dimension — users with longer TTI-to-first-scroll may also have longer gaze-cursor lag.

### 2. Alignment depends on time since page load

- **0-0.5s:** Gaze-cursor distance is LOW (~170px) — residual alignment from previous page
- **0.5-1s:** Distance PEAKS at ~240px — eyes scanning, cursor idle
- **1-2s:** Distance narrows — cursor begins following gaze
- **2-5s:** Gradual decrease as user enters examination/reading mode

**Relevance to us:** The 0.5-1s peak maps exactly onto our TTI observation: "the first 2 seconds are dominated by mouse movement for both groups." The initial scan phase (eyes move, cursor stays) is the assessment window we identified.

### 3. Five cursor behavior categories with distinct alignment

| Behavior | Time | Gaze-Cursor Distance | Description |
|----------|------|---------------------|-------------|
| **Inactive** | 58.8% | 233 px | Cursor parked, not moving |
| **Examining** | 32.9% | 167 px | Moving around page, not reading |
| **Reading** | 2.5% | 150 px | Following text horizontally |
| **Action** | 5.7% | 77 px | About to click |
| **Click** | — | 74 px | At moment of click |

Key insight: **cursor is inactive 59% of the time.** During inactivity, gaze-cursor distance is worst (233px). The cursor is a poor proxy for gaze more than half the time. Alignment is only strong during action (77px) and reading (150px).

**Relevance to us:** This explains why AdSight needs a full Transformer to predict fixation from cursor — raw cursor position is ambiguous ~60% of the time. Our approach (using eye tracking directly) avoids this problem entirely.

### 4. Individual differences dominate task differences

- Between-subject SD in gaze-cursor distance: **33.9 px**
- Between-task SD: **20.2 px**
- Levene's test confirms individual variance > task variance (p=0.037)
- No significant gender effect (t(34)=1.31, p=0.20)
- Weak age correlation (ρ=0.22, p=0.18)

Alignment style is a **personal trait**, not driven by demographics. Some subjects keep cursor within 130px of gaze; others average 280px.

**Relevance to us:** This is the same individual-differences finding as our user strategy segmentation. Some users are "cursor-trackers" (tight alignment), others are "cursor-parkers" (loose alignment). This likely correlates with our satisfice/optimize dimension — optimizers who scroll and regress probably have different cursor behavior patterns than satisficers who click from the first viewport.

### 5. Gaze prediction from cursor features: 23.5% improvement over cursor-alone

Prediction model: `gx ~ cx + log(td) + log(tm) + cx × log(td) + cx × log(tm) + fx`

Where:
- `cx` = cursor x position
- `td` = dwell time (time since page load)
- `tm` = time since last cursor movement
- `fx` = future cursor x position (most likely next position)

| Model | RMSE_x | RMSE_y | RMSE_d |
|-------|--------|--------|--------|
| Cursor position only | 185.0 | 145.0 | 236.6 |
| + Behavior + Dwell | 125.2 | 137.1 | 186.3 |
| + Behavior + Dwell + Future | 125.1 | 129.9 | 181.1 |

Feature importance (LMG metric, x-coordinate): `log(td)` > `cx` > `fx` > `cx × log(tm)` > `log(tm)` > `cx × log(td)`

**Dwell time is the most important feature** — more important than cursor position itself. This connects to our TTI finding: time-on-page is a fundamental signal for where attention is.

### 6. Cursor ≠ gaze (the key warning)

> "Claiming that the cursor approximates the gaze — as we have shown, this is often not the case depending on time and behavior. Instead, it is important to predict the real location of the attention when an eye-tracker is unavailable."

The paper explicitly warns against equating cursor with gaze. This is why the AdSERP dataset (with simultaneous eye tracking + mouse tracking) is valuable — and why our fixation-based analyses are more trustworthy than cursor-based proxies.

## Methodological Notes

- **Interpolation:** Gaze positions interpolated between nearest coordinates weighted by time (Eq. 1). Cursor positions only included if within 100ms of a gaze position. Same approach we use for scroll interpolation in our notebooks.
- **Behavior classification:** Heuristic-based, not ML. Inactive = cursor still ≥1s. Reading = horizontal movement ≥150px with ≤50px vertical drift and leftward return. Examining = active but not reading or clicking. Action = 1s before a click.
- **Cross-validation:** Leave-one-subject-out (36-fold). Practical: train on 35 subjects, predict gaze for unseen user.

## Connections to Our Work

| Their finding | Our finding | Connection |
|---|---|---|
| Cursor lags gaze by 700ms (individual range 250-1000ms) | TTI correlates with fixation time at r=0.77 | Both capture individual processing speed |
| Alignment peaks at 0.5-1s post-pageload | First 2s are assessment, no clicks | Same initial scanning phase |
| Individual differences > task differences | Satisfice/optimize is a stable user trait | Personal browsing style dominates |
| Inactive cursor 59% of the time | First-VP clickers don't look past position 2 | Cursor data misses most of the evaluation |
| Dwell time is the most important predictor | Position (temporal order) drives fixation | Time-on-task is the fundamental signal |
| 23.5% improvement over cursor-only | AdSight achieves ~1.69s fixation prediction error | AdSight is the modern ML version of this approach |

## Open Questions for Us

1. **Can we compute gaze-cursor lag per user in AdSERP?** We have both data streams. If lag correlates with our TTI measure, that's a tighter mechanistic link.
2. **Do cursor behavior categories predict our satisfice/optimize segmentation?** Users with more "reading" cursor behavior may be optimizers.
3. **Does the 700ms lag affect our fixation-to-result mapping?** Our scroll interpolation assigns fixations to results based on timestamps. If gaze leads cursor by 700ms, and scroll is measured via cursor/mouse events, there could be a systematic offset in our position assignments.
