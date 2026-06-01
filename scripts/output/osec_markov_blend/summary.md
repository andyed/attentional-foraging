# OSEC-Phase Markov over Typed-AOI Episodes — dd_top first pass

- trials kept: **1581** / 1581
- episodes: **55,110**
- saccades: **131,312**

## H/V fingerprint per phase

| phase | n_saccades | H̄ (px) | V̄ (px) | H/V ratio (median) | %H | %V | %diag | %micro | %up-V |
|---|---|---|---|---|---|---|---|---|---|
| Survey | 7,903 | 91.5 | 84.4 | 0.538 | 30.0% | 24.2% | 35.7% | 10.2% | 32.0% |
| Evaluate | 123,409 | 72.2 | 87.6 | 0.487 | 27.3% | 28.0% | 28.5% | 16.2% | 37.0% |

## Phase KL (Survey vs Evaluate transition rows)

- weighted mean symmetric KL: **0.623**
- n rows compared (≥5 saccades in each phase): 17

Top 8 most phase-divergent source states:

| from_state | KL | n_Survey | n_Evaluate |
|---|---|---|---|
| paa | 5.447 | 5 | 1089 |
| organic_5 | 5.122 | 6 | 5009 |
| organic_7 | 2.957 | 5 | 2737 |
| other_widget | 1.642 | 6 | 75 |
| image_pack | 1.021 | 40 | 2873 |
| organic_4 | 0.695 | 14 | 7446 |
| organic_3 | 0.512 | 49 | 9951 |
| off | 0.499 | 1834 | 18740 |

## Regression subtypes (organic→organic, K<J)

- counts: {'local': 5159, 'mid': 274, 'long': 305}
- long-regression top-pull fraction (lands on organic_1 or organic_2): **50.2%**

Per-subtype fixation-index stats (where in the trial they fire):

| subtype | n | median fix_idx | p25 | p75 |
|---|---|---|---|---|
| local | 5159 | 62.0 | 38.0 | 92.0 |
| mid | 274 | 64.0 | 46.0 | 106.0 |
| long | 305 | 68.0 | 46.0 | 99.0 |

Top destinations per subtype:

- **local**: organic_1=1202, organic_2=967, organic_3=867, organic_4=691, organic_5=484, organic_6=372, organic_7=240, organic_8=170
- **mid**: organic_2=64, organic_1=61, organic_3=57, organic_4=32, organic_5=26, organic_6=20, organic_7=9, organic_11=2
- **long**: organic_2=80, organic_1=73, organic_3=69, organic_4=44, organic_5=28, organic_6=6, organic_7=3, organic_9=2

---

_dd_top stratum only · SURVEY_END=5 · micro<30.0px · H if ratio>0.7, V if <0.3_