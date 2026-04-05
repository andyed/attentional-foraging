# LinkedIn: The Search Results F-Heatmap, Frame by Frame

**Attach:** `site/explainer/linkedin-header.png`

---

A heatmap collapses time.

In 2006, Nielsen's F-pattern was a sledgehammer that broke the industry's assumption that users read websites like novels. That was a necessary correction. But the F was captured with 30–60Hz trackers and aggregate heatmaps — tools that couldn't separate *when* things happened.

By decomposing 2,776 eye-tracking sessions from the AdSERP dataset (150Hz + pupillometry), we can now see what the heatmap blurred together. The F is two distinct operations:

🔵 The Survey Phase (~1.3s): Wide saccades sampling the result set. Pupils constrict. It's cheap gist-sampling — the brain is mapping the territory, not reading.
🔴 The Evaluate Phase: Narrow serial reading within results. Pupils dilate. This is where the cognitive work happens.

And the F's vertical fade — the shorter lower bar? That's not users reading less carefully. Reading depth doesn't decline with position. Users who reach result 7 read it with the same horizontal spread as result 1 (~210px std). The heatmap fades because fewer people scroll that far — a commitment problem, not a reading problem.

From years of eye-tracking studies and SERP experiments at eBay, Microsoft, and Meta, I've suspected the first moments on a results page involve a distinct sampling phase before committed reading. The AdSERP dataset finally gave enough resolution to test it. Along the way, the F-pattern fell out of the decomposition.

The F-pattern wasn't a map of how we read; it was a long-exposure photograph of two different behaviors. We just needed 150 frames per second to watch it get drawn.

Full explainer with real-data heatmap decomposition, interactive gaze replays, and pupil trajectories: andyed.github.io/attentional-foraging/explainer/

13 reproducible notebooks: github.com/andyed/attentional-foraging

Data: Latifzadeh, Gwizdka & Leiva, AdSERP, SIGIR 2025
