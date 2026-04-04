# Duchowski (PACM CGIT 2026) — Real-Time Cognitive Load Measurement of Pupillary Oscillation

**Paper:** Real-Time Cognitive Load Measurement of Pupillary Oscillation
**Author:** Andrew T. Duchowski
**Venue:** Proc. ACM Comput. Graph. Interact. Tech., Vol 9, No 2
**DOI:** 10.1145/3803537
**Year:** 2026

## Key claims

- Derives three methods for computing the Low/High Frequency (LF/HF) pupil power ratio in real time: FFT (periodogram), DWT (wavelet), and Butterworth IIR filters
- Establishes minimum time windows from first principles:
  - **FFT:** 10 seconds (N = 600 at 60 Hz, Δf = 0.1 Hz)
  - **DWT:** 7.5 seconds (N ≈ 450 at 60 Hz, Level 6 decomposition)
  - **Butterworth (IIR):** 1 second (N = 60 at 60 Hz, variance-based power)
- Frequency bands: LF 0–1.6 Hz (tonic, autonomic), HF 1.6–4 Hz (phasic, cognitive load)
- Higher LF/HF ratio indicates greater cognitive load (low-frequency oscillations dominate under load)
- Butterworth approach is best suited for real-time: O(1) per sample, 15.6 KB memory, 22.6% CPU at 1000 Hz
- Acknowledges LHIPA (Duchowski et al. 2020) never considered minimum window — "likely guessed at using the mid-level decomposition"

## Method

- Simulated pupil signals with known LF/HF characteristics (rest vs cognitive load)
- Derived minimum windows analytically for each method from Nyquist criterion and wavelet decomposition level requirements
- Benchmarked latency, memory, CPU usage on simulated 1000 Hz data
- Python implementation using scipy.signal (Butterworth) and pywt (DWT)

## Connection to our work

This paper directly answers our question to Duchowski about per-position cognitive load measurement. LHIPA requires 7.5–10 seconds minimum — far too long for per-result segments (~2s in AdSERP). The Butterworth IIR approach with a 1-second minimum window enables per-result-position LF/HF ratio computation at 150 Hz (150 samples minimum per segment, we have ~300).

**Implementation for AdSERP:**
- Two 4th-order Butterworth filters: lowpass at 1.6 Hz (LF), bandpass 1.6–4 Hz (HF)
- Filter the entire blink-cleaned trial stream, then segment by result position
- Compute variance (power) of each filtered signal within each position segment
- LF/HF ratio per position tests the working memory hypothesis

## Python code provided

Duchowski sent `PupilFilterRatioDetector` class (streaming, sample-by-sample). For our offline batch analysis, batch `sosfiltfilt` on the full trial stream is cleaner and avoids edge effects.

## Citation

```
Duchowski, A. T. (2026). Real-Time Cognitive Load Measurement of
Pupillary Oscillation. Proc. ACM Comput. Graph. Interact. Tech. 9, 2,
Article fp1141. https://doi.org/10.1145/3803537
```
