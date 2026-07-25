from fides.warden import (
    generate_baseline_noise,
    inject_covert_signal,
    detect_periodic_signal,
)


def test_pure_baseline_noise_does_not_trigger_detection():
    false_positives = 0
    trials = 30
    for seed in range(trials):
        signal = generate_baseline_noise(2000, stdev=1.0, seed=seed)
        detected, _, _ = detect_periodic_signal(signal, max_lag=100, threshold=0.15)
        if detected:
            false_positives += 1
    assert false_positives <= 2, f"{false_positives}/{trials} false positives on clean noise -- threshold too loose"


def test_injected_periodic_signal_is_detected():
    caught = 0
    trials = 20
    for seed in range(trials):
        baseline = generate_baseline_noise(2000, stdev=1.0, seed=seed)
        modulated = inject_covert_signal(baseline, period=17, amplitude=0.6)
        detected, best_lag, peak = detect_periodic_signal(modulated, max_lag=100, threshold=0.15)
        if detected:
            caught += 1
    assert caught >= 18, f"only caught {caught}/{trials} injected signals"


def test_detected_lag_is_the_true_period_or_one_of_its_harmonics():
    # Autocorrelation of a periodic signal peaks at the true period AND
    # its integer multiples; a simple peak-picking detector can land on
    # any of them. This is a real, documented limitation (see warden.py),
    # not a bug -- so the honest test is "landed on a harmonic", not
    # "landed on the fundamental".
    baseline = generate_baseline_noise(4000, stdev=1.0, seed=1)
    true_period = 23
    modulated = inject_covert_signal(baseline, period=true_period, amplitude=0.7)
    detected, best_lag, peak = detect_periodic_signal(modulated, max_lag=100, threshold=0.15)
    assert detected
    remainder = best_lag % true_period
    assert remainder <= 1 or remainder >= true_period - 1, (best_lag, true_period)


def test_detection_floor_empirical_characterization():
    # Not asserting detection works at every amplitude -- characterizing
    # WHERE it stops working, which is the actually useful and honest
    # output of a detector like this.
    results = {}
    for amplitude in (0.05, 0.15, 0.3, 0.6, 1.0):
        caught = 0
        for seed in range(15):
            baseline = generate_baseline_noise(2000, stdev=1.0, seed=seed)
            modulated = inject_covert_signal(baseline, period=17, amplitude=amplitude)
            detected, _, _ = detect_periodic_signal(modulated, max_lag=100, threshold=0.15)
            caught += detected
        results[amplitude] = caught / 15
    # monotonicity: higher injected amplitude should not detect *less*
    # reliably than a lower one, on average
    amplitudes_sorted = sorted(results)
    for a, b in zip(amplitudes_sorted, amplitudes_sorted[1:]):
        assert results[b] >= results[a] - 0.2, results  # allow noise slack, not strict monotonicity
    # and detection should clearly work at the high end
    assert results[1.0] >= 0.8
