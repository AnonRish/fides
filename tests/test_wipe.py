import random

from fides.wipe import wipe, spot_check, fill_block, block_addresses
from fides.security import detection_probability


def test_full_wipe_passes_every_spot_check():
    memory = bytearray(b"\xAA" * 4096)  # pretend this is stale data
    challenge = b"challenge-epoch-17"
    wipe(memory, challenge, block_size=64)
    for addr in block_addresses(4096, 64):
        assert spot_check(memory, challenge, addr, 64)


def test_stale_block_fails_its_spot_check_but_others_still_pass():
    memory = bytearray(4096)
    challenge = b"challenge-epoch-18"
    wipe(memory, challenge, block_size=64)
    stale_addr = 640
    memory[stale_addr: stale_addr + 64] = b"\xFF" * 64  # skip-the-wipe simulation
    assert not spot_check(memory, challenge, stale_addr, 64)
    for addr in block_addresses(4096, 64):
        if addr != stale_addr:
            assert spot_check(memory, challenge, addr, 64)


def test_partial_wipe_detection_probability_matches_security_module():
    # This is the same hypergeometric argument as attestation.py's
    # spot-check, applied to memory blocks instead of trace events --
    # cross-validated against the existing formula, not re-derived.
    n_blocks, k_stale, m_sample = 64, 5, 10
    memory = bytearray(n_blocks * 64)
    challenge = b"challenge-epoch-19"
    wipe(memory, challenge, block_size=64)
    for i in range(k_stale):
        addr = i * 64
        memory[addr: addr + 64] = b"\x00" * 64  # first k_stale blocks left unwiped

    all_addrs = block_addresses(n_blocks * 64, 64)
    expected_blocks = [fill_block(challenge, a, 64) for a in all_addrs]
    rng = random.Random(1)
    trials, caught = 20000, 0
    for _ in range(trials):
        sample = rng.sample(range(n_blocks), m_sample)
        if any(bytes(memory[all_addrs[i]: all_addrs[i] + 64]) != expected_blocks[i] for i in sample):
            caught += 1
    empirical = caught / trials
    analytical = detection_probability(n_blocks, k_stale, m_sample)
    assert abs(empirical - analytical) < 0.02, (empirical, analytical)


def test_wipe_is_deterministic_given_the_same_challenge():
    m1, m2 = bytearray(256), bytearray(256)
    wipe(m1, b"same-challenge")
    wipe(m2, b"same-challenge")
    assert bytes(m1) == bytes(m2)


def test_different_challenges_produce_different_fill_patterns():
    m1, m2 = bytearray(256), bytearray(256)
    wipe(m1, b"challenge-a")
    wipe(m2, b"challenge-b")
    assert bytes(m1) != bytes(m2)
