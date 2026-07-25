"""
Side-channel warden -- addresses SITREP item 17 ("Side channel wardens":
scanning/observing side channels to detect covert communication, graded
not on track). This module does not mitigate side channels (that's item
16, physical shielding, genuinely out of software's reach); it detects
when a telemetry stream that should look like ordinary system noise
instead carries a statistically detectable injected signal -- the
signature of a covert channel encoding information onto a side channel
(power draw, EM emission, timing) that a network tap doesn't observe
directly.

Detection uses autocorrelation. Genuine thermal/electrical noise is close
to white noise: autocorrelation near zero at every nonzero lag. An
injected periodic signal -- the simplest, most bandwidth-efficient way to
encode bits onto an otherwise-unwatched channel -- produces a detectable
peak in the autocorrelation at the injection period, even at amplitudes
well below what's visible by eye in the raw signal. This is standard
signal-processing, not novel cryptography; the contribution here is
wiring it up as a tested detector with an empirically characterized
detection floor, not the underlying math.

Known limitation: autocorrelation of a periodic signal peaks at the true
period AND at every integer multiple of it (its harmonics), and
`detect_periodic_signal` just reports whichever lag has the tallest peak
within the search window -- so it reliably flags that *something*
periodic is present, but the specific lag it reports can land on a
harmonic rather than the fundamental period (see test_warden.py). Telling
those apart reliably needs a proper spectral (FFT) analysis with harmonic
suppression, which is real future work, not implemented here.
"""

import math
import random


def generate_baseline_noise(n_samples: int, mean: float = 0.0, stdev: float = 1.0, seed: int = None) -> list:
    rng = random.Random(seed)
    return [rng.gauss(mean, stdev) for _ in range(n_samples)]


def inject_covert_signal(baseline: list, period: int, amplitude: float) -> list:
    """Adds a periodic component to an existing signal -- simulates a
    covert channel modulating a side channel at a fixed period."""
    return [x + amplitude * math.sin(2 * math.pi * i / period) for i, x in enumerate(baseline)]


def autocorrelation(signal: list, lag: int) -> float:
    n = len(signal)
    mean = sum(signal) / n
    centered = [x - mean for x in signal]
    variance = sum(x * x for x in centered) / n
    if variance == 0:
        return 0.0
    covariance = sum(centered[i] * centered[i + lag] for i in range(n - lag)) / (n - lag)
    return covariance / variance


def autocorrelation_spectrum(signal: list, max_lag: int) -> list:
    return [autocorrelation(signal, lag) for lag in range(1, max_lag + 1)]


def detect_periodic_signal(signal: list, max_lag: int, threshold: float = 0.15):
    """Returns (detected: bool, best_lag: int | None, peak_value: float)."""
    spectrum = autocorrelation_spectrum(signal, max_lag)
    peak_value = max(spectrum)
    peak_lag = spectrum.index(peak_value) + 1
    return (peak_value >= threshold, peak_lag if peak_value >= threshold else None, peak_value)
