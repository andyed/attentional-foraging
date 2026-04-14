# Figure index — scripts/output/figures/

Canonical visualizations for the approach-retreat / attentional-foraging work.
Each entry records the source script, the creation timestamp, and the intent
(what question the figure answers). Update this file whenever a new figure
lands here.

| File | Source script | Created | Intent |
|---|---|---|---|
| `coupling_traces.png` | `scripts/render_coupling_traces.py` | 2026-04-14 08:23 | **Canonical.** Cursor–gaze distance vs time-from-episode-entry, pooled median + IQR ribbon per class. Eval-rejected (red, tightest), deferred (orange, mid), clicked (green, widest). Duration truncation via 40% min_frac — eval-rejected visibly ends at ~2.5s, clicked/deferred run the full 6s. Sample-count strip below shows the decay. Supports the "coupling set at episode entry, held for the duration" mechanism claim. |
| `gaze_density_class.png` | `scripts/render_gaze_density.py` | 2026-04-14 08:33 | **Canonical.** Pooled Tobii-style gaze density centered on each episode's cursor anchor (cursor median position subtracted per-episode). Three panels, one per class, each normalized to its own peak. Shows the *spatial* flipside of coupling_traces: eval-rejected density is tight around the cursor, clicked is most diffuse. ±600 px window, 12 px bins, σ=3 Gaussian smoothing, duration-weighted. |
| `cursor_gaze_array.png` | `scripts/render_cursor_gaze_array.py` | 2026-04-14 07:47 | Spatial-trajectory small multiples — 3×3 grid of individual episode exemplars with blue cursor path + numbered fixation circles sized by duration. *Superseded for the main narrative by `gaze_density_class.png`* because exemplar variance drowns the population pattern; retained for illustrative use. |
| `cursor_gaze_timeseries.png` | `scripts/render_cursor_gaze_timeseries.py` | 2026-04-14 07:46 | Time-aligned view — cursor-y vs time with fixation events overlaid. Companion to `cursor_gaze_array.png`. |
| `deferred_vs_rejected_four_panel.png` | `scripts/render_deferred_vs_rejected.py` | 2026-04-14 07:38 | Four-panel violin/swarm contrasting deferred vs evaluated-rejected on motor-signature metrics (min_dist, retreat_dist, total_dwell, duration). Aggregate view of the hard-negative contrast. |
| `deferred_vs_rejected_trajectory.png` | `scripts/render_deferred_vs_rejected.py` | 2026-04-14 07:38 | Aggregate cursor-to-target-band distance trajectory, deferred vs evaluated-rejected, time-from-entry. Precursor to `coupling_traces.png`. |
| `gaze_around_cursor.png` | `scripts/render_gaze_around_cursor.py` | 2026-04-14 08:25 | *Retired exemplar variant.* 3×4 grid of per-episode gaze scanpaths anchored on the cursor's median position with dashed IQR halo. Attempted to show the spatial pattern at the exemplar level but individual variance obscured it. Kept for reference; `gaze_density_class.png` is the correct aggregate form. |

## Conventions

- **Class colors:** eval-rejected = `#b2182b` (red), deferred = `#e08214` (orange), clicked = `#2ca25f` (green). Consistent across every figure.
- **Coordinate system:** all px values are page-space (document coordinates, mouse-y already includes scroll offset — see `notebooks-v2/data_loader.py` docstring).
- **Contrast:** every figure passes 8:1 WCAG on text elements; decorative elements ≥55/255 against background.
- **Caches:** figures that loop every record cache intermediates next to this INDEX (`per_record_fixation_traces.json`, `per_record_gaze_offsets.json`). Delete and re-render if upstream data changes.

## When to touch

- New canonical figure for the paper: add a row, mark it **Canonical**.
- Exploratory variant: add a row with intent stated plainly; mark as *Retired* or *Superseded* when a stronger version lands.
- Upstream data changes (features JSON, regression labels): bump the cache files and re-render the canonical figures; update timestamps.
