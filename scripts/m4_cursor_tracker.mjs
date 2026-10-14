#!/usr/bin/env node
// JSON-lines bridge to the real browser feature accumulator. Geometry,
// sampling, labels, and evaluation are owned by m4_cursor_aoi_rerun.py.
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

const { ResultFeatureTracker } = await import(pathToFileURL(process.argv[2]).href);

// Episode crop (producer `--window episode` / `episode-pad`). A proximity
// episode is a maximal run of consecutive post-buffer samples with
// |pageY - center| < proximityPx for THIS AOI (the paper's §3.2 zone, strict
// inequality to match the tracker's dwell test). `padMs` extends every run by
// that many ms on both sides so the approach into the zone and the retreat
// out of it are kept; padded runs may merge. Returns the kept samples plus
// counts. Zero kept samples leaves the tracker in its empty state (all-zero
// feature vector, including min_dist = 0); the producer reports those rows.
function cropToEpisodes(samples, center, proximityPx, padMs) {
  const n = samples.length;
  const runs = [];
  let start = -1;
  for (let i = 0; i < n; i++) {
    const inside = Math.abs(samples[i][1] - center) < proximityPx;
    if (inside && start < 0) start = i;
    if (!inside && start >= 0) { runs.push([start, i - 1]); start = -1; }
  }
  if (start >= 0) runs.push([start, n - 1]);
  const keep = new Array(n).fill(false);
  for (const [a, b] of runs) {
    if (padMs > 0) {
      const t0 = samples[a][0] - padMs, t1 = samples[b][0] + padMs;
      for (let i = 0; i < n; i++) if (samples[i][0] >= t0 && samples[i][0] <= t1) keep[i] = true;
    } else {
      for (let i = a; i <= b; i++) keep[i] = true;
    }
  }
  let keptRuns = 0;
  for (let i = 0; i < n; i++) if (keep[i] && (i === 0 || !keep[i - 1])) keptRuns += 1;
  return { kept: samples.filter((_, i) => keep[i]), episodes: runs.length, keptRuns };
}

for await (const line of readline.createInterface({ input: process.stdin })) {
  if (!line.trim()) continue;
  const trial = JSON.parse(line);
  const conditions = {};
  const episode = trial.episode_window ?? null; // absent = whole post-buffer stream (default)
  for (const buffer of trial.buffers_ms) {
    // anchor_t is the click by default, or the final mousedown (see producer docstring).
    const anchorT = trial.anchor_t ?? trial.click_t;
    const samples = trial.samples.filter(([t]) => t < anchorT - buffer);
    conditions[`buf${buffer}`] = trial.aois.map(aoi => {
      const tracker = new ResultFeatureTracker(aoi.center_document_y, 100);
      let fed = samples, crop = null;
      if (episode) {
        crop = cropToEpisodes(samples, aoi.center_document_y, episode.proximity_px, episode.pad_ms);
        fed = crop.kept;
      }
      for (const [t, pageY] of fed) tracker.update(pageY, t);
      return {
        trial_id: trial.trial_id,
        position: aoi.position,
        etype: aoi.etype,
        was_clicked: aoi.position === trial.click_position,
        ...tracker.getFeatures(),
        ...(crop ? { window_samples: samples.length, kept_samples: fed.length,
                     episode_count: crop.episodes,
                     kept_run_count: crop.keptRuns } : {}),
      };
    });
  }
  process.stdout.write(JSON.stringify(conditions) + '\n');
}
