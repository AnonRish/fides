from fides.server_attestation import (
    software_fingerprint,
    issue_challenge,
    respond_to_challenge,
    verify_response,
)


def test_honest_server_passes_challenge():
    software_fp = software_fingerprint(b"verification-server-v1-source")
    state = b"ledger-head-hash-at-epoch-42"
    challenge = issue_challenge(b"fixed-test-challenge")
    response = respond_to_challenge(software_fp, challenge, state)
    assert verify_response(software_fp, challenge, state, response)


def test_modified_software_fails_even_with_correct_state():
    real_fp = software_fingerprint(b"verification-server-v1-source")
    tampered_fp = software_fingerprint(b"verification-server-v1-source-BUT-ALWAYS-REPORTS-COMPLIANT")
    state = b"ledger-head-hash-at-epoch-42"
    challenge = issue_challenge(b"fixed-test-challenge")
    forged_response = respond_to_challenge(tampered_fp, challenge, state)
    assert not verify_response(real_fp, challenge, state, forged_response)


def test_rolled_back_state_fails_even_with_correct_software():
    software_fp = software_fingerprint(b"verification-server-v1-source")
    real_state = b"ledger-head-hash-at-epoch-42"
    rolled_back_state = b"ledger-head-hash-at-epoch-10"  # server pretends it's earlier
    challenge = issue_challenge(b"fixed-test-challenge")
    forged_response = respond_to_challenge(software_fp, challenge, rolled_back_state)
    assert not verify_response(software_fp, challenge, real_state, forged_response)


def test_replayed_response_fails_against_a_new_challenge():
    software_fp = software_fingerprint(b"verification-server-v1-source")
    state = b"ledger-head-hash-at-epoch-42"
    old_challenge = issue_challenge(b"challenge-1")
    new_challenge = issue_challenge(b"challenge-2")
    old_response = respond_to_challenge(software_fp, old_challenge, state)
    assert not verify_response(software_fp, new_challenge, state, old_response)


def test_random_challenges_are_not_predictable_or_repeating():
    challenges = {issue_challenge() for _ in range(50)}
    assert len(challenges) == 50
