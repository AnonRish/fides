# Fides Protocol Specification

Status: reference implementation / testbed, not a deployment-ready design.

## 1. Motivation

[AI 2040: Plan A](https://ai-2040.com/) proposes that an international AI slowdown deal is only enforceable if compliance can be checked "without relying on trust" — its own framing. Its [verification supplement](https://ai-2040.com/supplements/verification-plan) splits the problem into verifying that *known* compute is compliant and verifying that *unknown* compute is inconsequential. Fides addresses a narrow slice of the first problem: given a datacenter that is supposed to be running inference only, how does an auditor with no access to weights, prompts, or outputs get evidence that no training happened, without trusting the operator's word for it, and without needing to mirror every byte of traffic off-site?

## 2. Threat model

**In scope.** A prover (the accelerator, or a tap sitting on its network path) that may misreport its own workload class. The prover commits to a trace and later may be asked to reveal a sample of it. We assume the prover cannot predict, before committing, which indices the verifier will sample — this is enforced by having the verifier's random seed and sampling logic live entirely on the verifier's side, chosen after the commitment is published. We also assume a verifier/recomputation-server that may itself be compromised, coerced, or buggy, and could try to under-report or silently edit its own findings after the fact.

**Out of scope for this reference implementation.** Physical tampering with the tap hardware itself (SITREP: "TAP installation and network links", "Physical security and audits" — both graded not on track); side-channel exfiltration of information around the tap rather than through it (SITREP: "Side channel mitigation", "Side channel wardens" — both not on track); and an adversary that adapts its workload's *structural* signature specifically to evade `classifier.py` (see section 4). None of these are solved here, and none of them should be read as solved by proxy.

## 3. Commitment scheme

Every kernel event in an epoch (`op`, `timestamp_ns`, `duration_ns`, `bytes_read`, `bytes_written`, `flops`) is serialized deterministically (`commitment.py::_event_bytes`, a fixed `struct` layout, not a language-level hash of the operation name — string/enum hashing in Python is per-process randomized and would make two honest parties compute different roots for the same trace) and becomes a leaf in a BLAKE3 Merkle tree.

BLAKE3 specifically because:

1. It is a tree hash by construction, so a Merkle proof for any leaf is close to free to produce, rather than requiring a separately-built proof structure over a different hash.
2. Its throughput on modern hardware (SIMD, and AES-NI-class acceleration where available) matters because whatever computes commitments has to keep pace with live traffic on the same device serving production workloads — this is the tap's actual bandwidth constraint, and the reason the SITREP frames "packet-hashing taps" as a bandwidth-limiting alternative to full mirroring in the first place.

The prover publishes only the Merkle root plus its self-declared workload class, signed with an Ed25519 device key (`identity.py`). Nothing about the trace's content is revealed at commit time.

## 4. Structural classification: what it catches and what it doesn't

`features.py` extracts five aggregate statistics from a trace — backward/forward kernel ratio, presence of an optimizer-update kernel, mean all-reduce payload size, presence of KV-cache writes, and arithmetic intensity — and `classifier.py` thresholds on them. This is deliberately a transparent scoring function rather than a learned model: the classifier's own output feeds directly into what gets flagged for audit, so it needs to be inspectable by a human auditor, not itself a black box requiring separate verification.

**What this catches:** the tests in `test_attestation.py` show it catches (a) a full training epoch mislabeled as inference essentially every time at even a 20% sample rate, since roughly half of a training epoch's events carry the backward/optimizer signal, and (b) a handful of covert gradient steps hidden inside an otherwise-legitimate inference epoch, at a per-epoch probability matching the sampling math in section 5, compounding toward certainty as the device keeps operating.

**What this doesn't catch:** an adversary that specifically re-shapes its covert workload's *metadata* to imitate an inference-shaped trace at the kernel level — e.g., structuring gradient computation to avoid triggering an obvious optimizer-update kernel, or padding all-reduce traffic to look like activation communication rather than gradient communication. This is not a hypothetical concern: the Compute Verification Project's public working draft on structurally distinguishing inference from training via communication patterns is explicitly paired with an open competition to find training algorithms that evade it. Anyone hardening `classifier.py` past a first pass should engage with that competition rather than assume this repo's five features are the ceiling.

## 5. Spot-check audit and detection probability

The verifier samples `m` of the epoch's `n` events uniformly at random, without replacement, only after the commitment (and hence `n`) is already fixed and public. If `k` of those `n` events are "bad" (training-signal) events smuggled into a declared-inference epoch, the exact probability the audit catches at least one of them is the hypergeometric tail:

```
P(catch >= 1) = 1 - C(n-k, m) / C(n, m)
```

implemented in `security.py::detection_probability` and cross-checked against direct Monte Carlo simulation in `test_security.py`.

For large populations, the [AI 2040 verification supplement's own appendix](https://ai-2040.com/supplements/verification-plan#a2-detection-by-random-sampling) derives a Poisson approximation, `P(detected) ≈ 1 - exp(-N_verified · F_fake)`, and notes it independently converges with [Rinberg et al., 2025](https://arxiv.org/abs/2511.02620). `security.py::poisson_detection_probability` implements the same formula, and `test_poisson_approximation_converges_to_exact_for_large_populations` checks it agrees with the exact hypergeometric result once `n` is large — i.e., this repo's math matches the field's math, not just its own internal assumptions.

**The single-epoch number is not the operative guarantee.** A device has to sustain a false "inference-only" declaration across every epoch it operates, not just one. `repeated_detection_probability(p, T) = 1 - (1-p)^T` shows how fast a modest per-epoch catch probability compounds: at `p ≈ 0.46` (the demo's subtle-attacker scenario), the chance of being caught at least once passes 99% within 10 epochs. This is the same qualitative point the AI 2040 appendix makes about coverage and confidence trading off against recomputation budget and packet size — smaller packets and/or a higher sampling rate shift the curve, but even a modest, cheap sampling rate becomes overwhelming given enough repeated epochs.

## 6. Verification reporting: the auditor's own accountability

Section 3–5 assume the verifier is honest. `ledger.py` doesn't assume that. Every `AuditResult` is hash-chained (each entry covers the previous entry's hash) and signed by the auditor's key. If a compromised or coerced auditor tries to quietly rewrite a past finding — e.g. to erase a caught violation — `verify_chain()` will detect it, because the recomputed hash of the (now-edited) entry no longer matches the stored `entry_hash`. This requires no ongoing trust in the auditor, only that `entry_hash` values were published to at least one independent party at the time each entry was created. This is a direct, if minimal, answer to the SITREP's "Verification reporting" gap: *"the integrity of what the recomputation server reports back to the verifier has not been explored."*

## 7. Limitations and future work

- No real trace source. The highest-value next step is swapping `trace.py`'s synthetic generator for a real one (CUPTI/Nsight hooks, or an eBPF-based network-layer capture matching the actual passive-optical-tap design in the verification supplement) behind the same `ExecutionEpoch` interface.
- No adversarial hardening of the classifier past section 4's honest limitations.
- No physical security model — tap tampering and side-channel exfiltration are explicitly out of scope (section 2).
- No treatment of reproducibility under legitimate nondeterminism (this is what Token-DiFR and TOPLOC solve for the "is this inference output actually correct" question, which is complementary to and not addressed by this repo's "is this workload structurally inference-shaped at all" question).

## 8. A second mechanism: RSA-accumulator zero-knowledge proofs

Sections 3–7 describe a probabilistic scheme: the verifier samples, and a lie gets caught with a computable but non-unit probability per epoch, compounding toward certainty only as the device keeps operating. The covert-project supplement names two technologies Plan A's 2040 endpoint assumes exist — lie detectors, and privacy-preserving AI verification — as what makes covert projects implausible by then. `accumulator.py` and `zk_verification.py` are a reference implementation of the second one, built as a genuinely different mechanism rather than a restatement of sections 3-5.

**Construction.** Each distinct op-code present in an epoch is mapped to a large prime via a hash-to-prime function (`accumulator.py::hash_to_prime`), and the whole set is accumulated into one RSA-group element following Benaloh & de Mare (1993) and Barić & Pfitzmann (1997). `ZKProver.prove_inference_only` then produces, for each of the three forbidden op-codes, a non-membership witness using the construction from Li, Li & Xue (2007): given the product `u` of accumulated primes and a candidate `y`, the extended Euclidean algorithm either finds integers `(a, b)` with `a·y + b·u = 1` (proof of exclusion), or finds that `gcd(y, u) ≠ 1` — which, for prime `y`, only happens when `y` is itself one of the accumulated primes.

**Why this is a different kind of guarantee, not just a smaller detection window.** In section 5's scheme, a prover hiding `k` bad events among `n` always *can* produce a commitment; it just risks the verifier's sample landing on one of the `k`. Here, if a forbidden op is actually present, its prime divides `u`, so no integers `(a, b)` satisfying the Bézout identity exist at all — `nonmembership_witness` returns `None`, not a witness that happens to be wrong. `test_accumulator.py::test_nonmembership_witness_does_not_exist_for_an_actual_member` and `test_zk_verification.py::test_mixed_epoch_with_even_one_covert_op_cannot_verify` check this directly: the latter runs the exact same subtle single-covert-op attack from section 5's motivating example across 50 independent trials and it fails to verify in all 50, where the sampling scheme in section 5 catches it roughly 40–50% of the time per epoch.

**What this does not get you for free.** The accumulator proves a set-membership claim over *which op-codes occurred at least once* — it says nothing about timing, ordering, byte counts, or how many times each op ran, all of which the Merkle commitment in section 3 does expose (to the sampled subset, at least). The two mechanisms answer overlapping but non-identical questions, and a real deployment likely wants both: the accumulator for a hard compliance gate, sampling for the richer behavioral signal.

**The honest limitation.** Security here rests on the strong RSA assumption in a group whose order nobody knows. `trusted_setup()` generates that group's modulus by generating a fresh RSA keypair and discarding the factorization — but *this repository's own code* is the party doing that discarding, which is exactly the trust assumption a real deployment cannot make of a single party. Production use needs either an actual mutually-trusted third party to run setup once, or a proper multi-party ceremony, or a switch to a trapdoor-free group construction (class groups of imaginary quadratic order are the standard answer in the literature, and are real future work for this repo, not implemented here). This is stated plainly in `accumulator.py`'s module docstring, not buried.

## 9. Full audit against all 17 SITREP workstreams

This section exists so nobody, including the author, can quietly round "covers 2 named gaps" up to "covers the field." Grades and workstream names below are taken directly from [Amodo Design's SITREP](https://amododesign.com/ai-verification/plan-a-sitrep/) as published; software-addressability is this repo's own judgment call, not Amodo's.

| # | Workstream | Grade | Any software-only path exists? | Fides status |
|---|---|---|---|---|
| 1 | Passive optical TAPs | Active | No — physical optical hardware | Out of scope |
| 2 | Recomputation servers (capture) | Active | No — physical NIC/network capture infrastructure | Out of scope |
| 3 | New TAP types & bandwidth limits | Not started | Yes | **Covered — `commitment.py`** |
| 4 | Path from storage bank to inference units | Not on track | Mostly no — data diodes, physical network partitioning | Out of scope |
| 5 | Inference reproducibility workarounds (TOPLOC, DiFR) | Active | Yes | Not attempted — cited as related work only |
| 6 | Reproducible inference stack | Not started | Yes | Not attempted — needs a real inference stack; this repo simulates trace metadata, it runs no inference |
| 7 | Network reproducibility | Not started | Partially — the supplement itself says this may need firmware/hardware work too | Not attempted |
| 8 | Recomputation algorithms (TOPLOC, DiFR) | Active | Yes | Not attempted — same caveat as #5 |
| 9 | Frontier recomputation algorithms | Not started | Yes | **Not attempted** — `classifier.py` answers a different question (workload *type*, not output *correctness*); an earlier draft of the README overstated this and has been corrected |
| 10 | Recomputation red-teaming | Not started | Yes | Fides red-teams its own classifier and its own sampling scheme (`test_attestation.py`, `test_zk_verification.py`); it does not red-team TOPLOC/DiFR, which is what this workstream actually means |
| 11 | Recomputation server security | Not on track | Partially — a software attestation layer is plausible but the hard part is defending a machine inside the adversary's own facility | Not attempted — do not conflate with #13 below |
| 12 | TAP installation & network links | Not on track | No — physical installation at up to 100,000-cable scale | Out of scope |
| 13 | Verification reporting | Not on track | Yes | **Covered — `ledger.py`** (this is reporting-integrity only, not #11's server-compute-integrity) |
| 14 | Physical security and audits | Not on track | No — in-person inspection of compute and installed hardware | Out of scope |
| 15 | Memory wipes (PoSE) | Uncertain | Partially — the wipe *algorithm* is software; credible validation needs real hardware, per Amodo's own testing note | Not attempted — a software simulation testbed (analogous to `trace.py`'s role for the classifier) is plausible future work |
| 16 | Side channel mitigation (shielding + noise) | Not on track | No — physical shielding, by the SITREP's own framing | Out of scope |
| 17 | Side channel wardens | Not on track | Yes, as a monitoring/anomaly-detection layer, even without real EM/power sensor data to start | Not attempted — plausible future work, same shape as #15 |

**Tally.** 6 of 17 are physical by construction and no software project touches them regardless of effort (#1, #2, #4, #12, #14, #16). Of the 11 that have a real software component, Fides directly closes 2 (#3, #13). #5, #8 are already active elsewhere (TOPLOC/DiFR) and re-implementing them would be duplicated effort, not a gap closed. That leaves #6, #7, #9, #10, #11 (partial), #15, and #17 as genuine, honestly-open, software-touchable gaps this repo has not attempted — of which #15 and #17 are the most tractable next targets, for the same reason #3 and #13 were: they don't require real datacenter access to build a credible first version.

`accumulator.py` and `zk_verification.py` sit outside this table entirely — they target "Cryptographic/ZKP verification," which Amodo's SITREP names as a separate, roughly-$100M-funded parallel research track to the network-tap approach these 17 workstreams describe, not a 18th row in it.
