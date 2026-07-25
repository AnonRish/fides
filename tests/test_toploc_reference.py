import random

from fides.toploc_reference import (
    to_bfloat16_bits,
    bfloat16_parts,
    select_topk_by_magnitude,
    lagrange_coefficients,
    evaluate_polynomial,
    build_proof,
    verify_proof,
    MODULUS,
)


def test_bfloat16_hand_verified_example():
    # 1.0 in IEEE 754 float32 is the well-known constant 0x3F800000;
    # bfloat16 truncates to the top 16 bits, 0x3F80 = 16256.
    bits = to_bfloat16_bits(1.0)
    assert bits == 0x3F80
    sign, exponent, mantissa = bfloat16_parts(bits)
    assert (sign, exponent, mantissa) == (0, 127, 0)  # bias-127 exponent, zero mantissa


def test_bfloat16_negative_value_sign_bit():
    bits = to_bfloat16_bits(-2.0)
    sign, exponent, mantissa = bfloat16_parts(bits)
    assert sign == 1
    assert exponent == 128  # 2.0 = 1.0 * 2^1, biased exponent 128


def test_select_topk_by_magnitude_ignores_sign():
    values = [0.1, -10.0, 3.0, -0.2, 9.0]
    assert set(select_topk_by_magnitude(values, 2)) == {1, 4}  # -10.0 and 9.0


def test_lagrange_interpolation_reproduces_its_own_input_points():
    rng = random.Random(0)
    points = [(x, rng.randrange(0, MODULUS)) for x in (3, 17, 42, 1000, 60000)]
    coeffs = lagrange_coefficients(points)
    for x, y in points:
        assert evaluate_polynomial(coeffs, x) == y


def test_lagrange_interpolation_matches_a_hand_computable_polynomial():
    # f(x) = 3 + 2x + x^2 over the integers -- pick x small enough that
    # no value wraps around MODULUS, so this is checkable by hand.
    def f(x):
        return 3 + 2 * x + x * x

    xs = [1, 2, 3]
    points = [(x, f(x) % MODULUS) for x in xs]
    coeffs = lagrange_coefficients(points)
    assert coeffs == [3, 2, 1]
    for x in (4, 5, 10):
        assert evaluate_polynomial(coeffs, x) == f(x) % MODULUS


def test_identical_recomputation_matches_perfectly():
    rng = random.Random(1)
    values = [rng.gauss(0, 1) for _ in range(200)]
    proof = build_proof(values, k=16)
    result = verify_proof(proof, values)  # exact same values, no jitter
    assert result.exponent_matches == result.exponent_total
    assert result.mantissa_error_mean == 0


def test_honest_recomputation_with_small_jitter_matches_mostly():
    rng = random.Random(2)
    values = [rng.gauss(0, 1) for _ in range(200)]
    proof = build_proof(values, k=16)
    jitter_rng = random.Random(3)
    jittered = [v + jitter_rng.gauss(0, 0.0005) for v in values]
    result = verify_proof(proof, jittered)
    assert result.exponent_matches >= result.exponent_total * 0.8
    assert result.mantissa_error_mean < 4


def test_fabricated_unrelated_values_fail_to_match_well():
    rng = random.Random(4)
    values = [rng.gauss(0, 1) for _ in range(200)]
    proof = build_proof(values, k=16)
    fake_rng = random.Random(999)
    fake = [fake_rng.gauss(0, 1) for _ in range(200)]
    result = verify_proof(proof, fake)
    # unrelated values -> the verifier's own top-k positions almost
    # certainly differ from the ones the proof was built on, so the
    # proof's polynomial evaluated there is essentially uncorrelated with
    # what's actually present
    assert result.exponent_matches < result.exponent_total * 0.5


def test_scheme_characterizes_the_honest_dishonest_gap_across_trials():
    # Empirical characterization across many trials, not one lucky seed.
    honest_matches, fake_matches = [], []
    for trial in range(20):
        rng = random.Random(trial)
        values = [rng.gauss(0, 1) for _ in range(150)]
        proof = build_proof(values, k=12)

        jrng = random.Random(trial + 1000)
        jittered = [v + jrng.gauss(0, 0.0005) for v in values]
        honest_matches.append(verify_proof(proof, jittered).exponent_matches)

        frng = random.Random(trial + 2000)
        fake = [frng.gauss(0, 1) for _ in range(150)]
        fake_matches.append(verify_proof(proof, fake).exponent_matches)

    avg_honest = sum(honest_matches) / len(honest_matches)
    avg_fake = sum(fake_matches) / len(fake_matches)
    assert avg_honest > avg_fake + 4, (avg_honest, avg_fake)
