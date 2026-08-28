# Typed-flavor re-derivation delta — 2026-08-28 y-DP realignment

What moved when the typed AOI maps were rebuilt under y-aware geometric
alignment (see [`local-pack-aoi-shift.md`](local-pack-aoi-shift.md)) and
the 14 `alignment_suspect` trials were excluded.

**Headline: the published LF/HF findings are unchanged. RIPA2's rank
gradient is fragile to rank-window choice, in both the old and new
substrate — that fragility is the finding, not a value change.**

## Producer gap found and closed

`compute_butterworth_lfhf.py` and `compute_ripa2.py` had **no `typed`
branch** — the 2026-05-04 producer migration (`e922f1e5`) extended
`k_coefficient` / `saccade_orientation` / `retreat_arcs` /
`content_features` for typed and skipped these two. Yet
`butterworth-lfhf-by-position-typed.json` and
`ripa2-by-position-typed.json` existed, dated 2026-05-04 06:54 — before
that commit — produced by something never committed to the tree. Their
provenance was unrecoverable.

Both producers now take `--attribution typed` (via `typed_aoi_tops`,
which returns `[]` for alignment-excluded trials, so the exclusion
propagates automatically) and default their output path per flavor. The
regenerated files are the first ones in this repo's history with a
reproducible producer.

Pre-alignment copies: `*-typed.stale-preAlignment-2026-08-28.json`.

## Coverage

| product | old | new |
|---|---|---|
| `butterworth-lfhf-by-position-typed` | 2,719 trials | 2,706 |
| `ripa2-by-position-typed` | 2,719 trials | 2,706 |

13 trials dropped (alignment-excluded ∩ had usable pupil), 0 added.
Among the 2,706 common trials: **557 (21%) changed their visited-position
set** and **195 (7%) changed `click_pos`** — the realignment is doing
real work at the trial level even where aggregates hold.

## LF/HF (NB14) — unchanged

Per-rank medians move by < 0.6 at every rank (pos 0: 31.04 → 31.04;
pos 4: 18.87 → 18.29; pos 9: 13.59 → 13.68). Key Claim statistics are
**identical to three decimals**:

| window | old ρ | new ρ |
|---|---|---|
| steep (pos 0–3) | −1.000 (p<0.001) | **−1.000 (p<0.001)** |
| plateau (pos 4–9) | −0.600 (p=0.208, n.s.) | **−0.600 (p=0.208, n.s.)** |
| full (pos 0–9) | −0.903 (p<0.001) | **−0.903 (p<0.001)** |

The ETTAC/Duchowski LF/HF claims survive the realignment untouched. Rank
medians over thousands of trials are robust to per-trial label shifts —
which is why the aggregate held while a fifth of trials moved.

## RIPA2 — fragile to rank window, in BOTH substrates

Per-rank medians barely move (0.00049 → 0.00049 at pos 0). But the
rank-vs-median Spearman does:

| rank window | old ρ | new ρ | support at deepest rank |
|---|---|---|---|
| 0–7 | −0.762 (p=0.028) | **−0.881 (p=0.004)** | n=176 |
| 0–9 | −0.806 (p=0.005) | −0.576 (p=0.082, n.s.) | n=103 |
| 0–11 | −0.776 (p=0.003) | −0.615 (p=0.033) | — |

Read this correctly: the 0–9 window flips to non-significant, but the
**0–7 window gets stronger and more significant**, and 0–11 stays
significant. A ρ over 10 rank-medians has 10 data points regardless of
how many trials feed each one, and the deep ranks are thin (rank 9:
n=103 vs rank 0: n=1,366). The p-value swings with an arbitrary window
choice in the old substrate too — that is a pre-existing fragility the
realignment exposed, not damage it caused.

**Implication:** do not report a bare "RIPA2 declines with rank,
ρ = −0.81, p = 0.005." Either report the window sensitivity explicitly,
or use a trial-level / mixed-effects test that uses all the data instead
of 10 rank medians.

## Downstream re-derived

`k-coefficient-by-position-typed.json`,
`saccade-orientation-by-{position,trial}-typed.json` (both consume the
regenerated LF/HF + RIPA2). Spot values after re-derivation: K at clicked
vs non-clicked positions Δ = +0.090, MW p = 2.99e-09, rank-biserial
r = +0.077 (N = 2,313 / 14,086); K × LF/HF per-position ρ = +0.142,
p = 0.586 (N = 17 positions, still null).

## K-ID handling

Per the update-in-place policy, re-derived rows keep their K-IDs and get
a `(re-derived 2026-08-28: y-DP aligned typed maps)` annotation. LF/HF
rows need no value edits — the numbers are identical. RIPA2 rows need
the window-sensitivity caveat added, which is a **claim change, not a
value change**.
