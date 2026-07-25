"""
Recomputation server software self-attestation -- a narrow, explicitly
partial software-only slice of SITREP item 11 ("Recomputation server
security", not on track). The hard part of this workstream is physical:
the server sits inside the party being verified's own facility, under
their physical control, and no software running ON a machine can fully
prove that machine's own hardware/firmware hasn't been compromised --
that needs a hardware root of trust (TEE, secure boot chain) this repo
has no access to and does not claim to provide.

What IS a legitimate software-only contribution: a periodic
challenge-response heartbeat that a server running unmodified,
correctly-configured verification code can answer, but a server that has
silently swapped in modified verification logic (e.g. one hardcoded to
always report "compliant") cannot answer correctly for -- catching a
specific, real class of tampering (silent logic substitution, and
rollback of the server's own history) even though it cannot catch every
class (an attacker who fully emulates the original code's behavior while
also running additional undetected logic alongside it gets past this,
which is exactly why this is documented as a partial mitigation, not a
solution -- see spec/PROTOCOL.md).
"""

import os

import blake3


def software_fingerprint(source_bytes: bytes) -> bytes:
    """A hash of the verification server's own code -- what a heartbeat
    challenge gets bound to."""
    return blake3.blake3(source_bytes).digest()


def issue_challenge(seed: bytes = None) -> bytes:
    return seed if seed is not None else os.urandom(32)


def respond_to_challenge(software_fp: bytes, challenge: bytes, secret_state: bytes) -> bytes:
    """The response binds together: which code is running (software_fp),
    the specific challenge (so replaying an old response doesn't work),
    and the server's own accumulated state (secret_state -- e.g. a
    running hash of recent ledger entries, so the response also proves
    the server hasn't rolled back or forked its own history)."""
    return blake3.blake3(software_fp + challenge + secret_state).digest()


def verify_response(expected_software_fp: bytes, challenge: bytes, expected_state: bytes, response: bytes) -> bool:
    return respond_to_challenge(expected_software_fp, challenge, expected_state) == response
