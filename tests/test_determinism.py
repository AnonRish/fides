import random

from fides.determinism import deterministic_sum, racy_sum


def _realistic_values(rng, n=500):
    # a wide dynamic range, similar in spirit to accumulated neural-
    # network activation magnitudes, where floating-point rounding
    # differences actually show up.
    return [rng.uniform(-1e6, 1e6) * (10 ** rng.randint(-8, 8)) for _ in range(n)]


def test_deterministic_sum_gives_identical_bits_across_repeated_calls():
    rng = random.Random(0)
    values = _realistic_values(rng)
    results = {deterministic_sum(values) for _ in range(50)}
    assert len(results) == 1


def test_racy_sum_demonstrates_the_real_nondeterminism_problem():
    # Empirical demonstration, not an assertion: check that summing the
    # SAME values in different (simulated schedule-dependent) orders
    # actually produces different bit patterns for a healthy fraction of
    # realistic value sets -- this is the real, well-documented phenomenon
    # deterministic reduction exists to fix (see e.g. PyTorch's and
    # cuDNN's deterministic-algorithms documentation).
    rng = random.Random(0)
    trials = 200
    distinct_result_trials = 0
    for _ in range(trials):
        values = _realistic_values(rng)
        results = {racy_sum(values, seed=s) for s in range(20)}
        if len(results) > 1:
            distinct_result_trials += 1
    assert distinct_result_trials > trials * 0.5, (
        f"only {distinct_result_trials}/{trials} trials showed order-dependence"
    )


def test_deterministic_and_racy_sum_agree_in_expectation():
    # deterministic_sum isn't "more correct" arithmetically, just
    # reproducible -- it should land within the same ballpark as the
    # racy variants, not systematically biased.
    rng = random.Random(1)
    values = _realistic_values(rng, n=200)
    det = deterministic_sum(values)
    racy_results = [racy_sum(values, seed=s) for s in range(30)]
    naive_total = sum(values)
    # all variants should be close to a plain Python sum() of the same
    # values, since the differences are rounding-level, not algorithmic
    for r in racy_results + [det]:
        if naive_total != 0:
            assert abs(r - naive_total) / (abs(naive_total) + 1e-300) < 1e-6


def test_deterministic_sum_handles_edge_cases():
    assert deterministic_sum([]) == 0.0
    assert deterministic_sum([5.0]) == 5.0
    assert deterministic_sum([1.0, 2.0, 3.0]) == 6.0
