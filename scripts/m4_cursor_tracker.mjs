#!/usr/bin/env node
// JSON-lines bridge to the real browser feature accumulator. Geometry,
// sampling, labels, and evaluation are owned by m4_cursor_aoi_rerun.py.
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

const { ResultFeatureTracker } = await import(pathToFileURL(process.argv[2]).href);
for await (const line of readline.createInterface({ input: process.stdin })) {
  if (!line.trim()) continue;
  const trial = JSON.parse(line);
  const conditions = {};
  for (const buffer of trial.buffers_ms) {
    // anchor_t is the click by default, or the final mousedown (see producer docstring).
    const anchorT = trial.anchor_t ?? trial.click_t;
    const samples = trial.samples.filter(([t]) => t < anchorT - buffer);
    conditions[`buf${buffer}`] = trial.aois.map(aoi => {
      const tracker = new ResultFeatureTracker(aoi.center_document_y, 100);
      for (const [t, pageY] of samples) tracker.update(pageY, t);
      return {
        trial_id: trial.trial_id,
        position: aoi.position,
        etype: aoi.etype,
        was_clicked: aoi.position === trial.click_position,
        ...tracker.getFeatures(),
      };
    });
  }
  process.stdout.write(JSON.stringify(conditions) + '\n');
}
