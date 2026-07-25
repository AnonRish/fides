# Fides Protocol Specification

Status: reference implementation / testbed, not a deployment-ready design.

## 1. Motivation

[AI 2040: Plan A](https://ai-2040.com/) proposes that an international AI slowdown deal is only enforceable if compliance can be checked "without relying on trust" — its own framing. Its [verification supplement](https://ai-2040.com/supplements/verification-plan) splits the problem into verifying that *known* compute is compliant and verifying that *unknown* compute is inconsequential. Fides addresses a narrow slice of the first problem: given a datacenter that is supposed to be running inference only, how does an auditor with no access to weights, prompts, or outputs get evidence that no training happened, without trusting the operator's word for it, and without needing to mirror every byte of traffic off-site?

## 2. Threat model

**In scope.** A prover (the accelerator, or a tap sitting on its network path) that may misreport its own workload class. The prover commits to a trace and later may be asked to reveal a sample of it. We assume the prover cannot predict, before committing, which indices the verifier will sample — this is enforced by having the verifier's random seed and sampling logic live entirely on the verifier's side, chosen after the commitment is published. We also assume a verifier/recomputation-server that may itself be compromised, coerced, or buggy, and could try to under-report or silently edit its own findings after the fact.

**Out of scope for this reference implementation.** Physical tampering with the tap hardware itself (SITREP: "Tap installation and monitoring", "Physical security and audits" — both graded not on track); side-channel exfiltration of information around the tap rather than through it (SITREP: "Side-channel mitigation", "Side-channel wardens" — both not on track); and an adversary that adapts its workload's *structural* signature specifically to evade `classifier.py` (see section 4). None of these are solved here, and none of them should be read as solved by proxy.

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
