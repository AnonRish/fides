# Fides

**A reference implementation of a packet-hashing inference-only verification tap, built against the AI 2040: Plan A verification agenda.**

[AI 2040: Plan A](https://ai-2040.com/) is the AI Futures Project's (the team behind [AI 2027](https://ai-2027.com/)) recommendation for how the US and China could verifiably slow down the race to superintelligence. The plan's [verification supplement](https://ai-2040.com/supplements/verification-plan) argues the whole deal is only as strong as the ability to check compliance without relying on trust, and its [get-involved page](https://ai-2040.com/supplements/verification-plan/get-involved) publishes a graded status report — [Amodo Design's Verification SITREP](https://amododesign.com/ai-verification/plan-a-sitrep/) — of the 17 engineering workstreams the plan's proposed solution needs. As of writing, 7 are "not on track" and 5 are "not started."

Fides is a from-scratch, tested, open-source testbed for three of those specific named gaps:

| Workstream (SITREP grade) | What Fides does about it |
|---|---|
| **New tap types and bandwidth limits** — *"sampling or packet-hashing taps"* (not started) | `commitment.py`: a BLAKE3 Merkle-tree tap that commits to every event locally and cheaply, and only ever transmits full data for a small, auditor-chosen sample — instead of mirroring 100% of traffic to a recomputation server. |
| **Verification reporting** — *"the integrity of what the recomputation server reports back to the verifier has not been explored"* (not on track) | `ledger.py`: a hash-chained, signed audit log. A compromised or coerced auditor can't quietly rewrite a past finding without breaking the chain from that point forward. |
| **Frontier recomputation algorithms** / structural workload classification (not started; related work ongoing) | `classifier.py` + `features.py`: an interpretable, privacy-preserving classifier that separates inference-shaped from training-shaped kernel traces from metadata alone (no weights, no tokens). |
| **Privacy-preserving AI verification** — named alongside lie detectors in the covert-project supplement as one of two technologies Plan A's endpoint assumes exist | `accumulator.py` + `zk_verification.py`: an RSA-accumulator zero-knowledge proof that an epoch contains *no* forbidden op anywhere in it — a soundness guarantee instead of a spot-check probability. See "Two verification mechanisms" below. |

This is **not** a claim to have solved any of these — it's a solid, honest, working reference point. In particular, the [Compute Verification Project](mailto:dreuter14@gmail.com) has already published a more advanced working draft that structurally distinguishes inference from training via communication patterns, and is running an open red-teaming competition against it; anyone extending the classifier here should treat that as the standard to beat, not this repo.

## How it fits together

```mermaid
flowchart LR
    subgraph Device["Accelerator / host"]
        K["Kernel-level trace\n(op, timing, bytes — no weights, no tokens)"] --> F["Feature extraction\n(features.py)"]
        F --> C["Classifier\ndeclares inference / training\n(classifier.py)"]
        K --> M["BLAKE3 Merkle commitment\n— the packet-hashing tap\n(commitment.py)"]
        M --> S["Ed25519 signature\n(identity.py)"]
        C --> S
    end
    S --> R[("Registry\npublished commitments")]
    R --> V{"Verifier"}
    V -- "spot-check sample\n(chosen after commitment)" --> Device
    Device -- "revealed leaves +\nMerkle proofs" --> V
    V --> AR["Audit result:\nconsistent / caught"]
    AR --> L[("AuditLedger\nhash-chained, signed\n— tamper-evident reporting")]
```

The prover (device/tap) never reveals the full trace by default — only the small sample the verifier asks for, chosen *after* the commitment is published, so the prover can't predict and hide the bad ones. This mirrors the "packet-based verification" appendix in the [AI 2040 verification supplement](https://ai-2040.com/supplements/verification-plan#appendix-packet-based-verification), which derives the same detection-probability math this repo implements and tests against.

## Two verification mechanisms, not one

`attestation.py` and `zk_verification.py` answer the same question — does the declared workload match what actually ran? — with two different, complementary guarantees:

| | `attestation.py` (Merkle + spot-check) | `zk_verification.py` (RSA accumulator) |
|---|---|---|
| Guarantee | Bounded detection **probability** per epoch, compounding toward certainty over repeated epochs (`security.py`) | Detection **certainty**: a forbidden op's non-membership witness provably cannot be constructed if the op is present |
| What's revealed | A small random sample of raw events, chosen after commitment | Only the accumulator value and non-membership witnesses — no event ever leaves the device |
| Cost | Cheap per epoch; needs many epochs for confidence | One accumulator + 3 witnesses per epoch; RSA exponentiation cost, no sampling |
| What it can express | Anything visible in the revealed sample (timing, byte counts, ordering) | Only set-membership claims ("no forbidden op occurred") over the accumulated set |

Running `examples/demo.py` section [6] reproduces the same subtle covert-training attack from section [3] and catches it 20/20 independent trials under the accumulator, against roughly 40-50% per epoch under sampling — not because one implementation is better than the other, but because they're different kinds of guarantee. See `spec/PROTOCOL.md` section 8 for when you'd actually want each.

## Quickstart

```bash
pip install -e ".[dev]"
python examples/demo.py     # honest device, a blatant liar, a subtle attacker, and a tampered ledger
pytest tests/ -v             # 59 tests
```

The demo runs a device sneaking one covert training step into otherwise-legitimate inference epochs while declaring everything "inference." In a real run it gets caught at epoch 3 out of 15 — consistent with the model's own prediction that a single epoch at this attack size has roughly a 46% catch probability, compounding to >99.7% by epoch 10 (see `examples/demo.py` section 5, and `spec/PROTOCOL.md` section 5).

## What's real here and what isn't

This is a **software testbed**, not hardware, and it should be read that way:

- `trace.py` **simulates** kernel-level execution traces with the statistical shape training and inference workloads are documented to have (backward-pass kernels, optimizer writes, KV-cache growth, gradient vs. activation all-reduce patterns). It does not hook into a real profiler (CUPTI/Nsight) or real GPU traffic. Swapping in a real trace source behind the same `ExecutionEpoch` interface is the natural next step and is the actual "not started" engineering work.
- The commitment, signature, spot-check, and ledger logic are real, tested, and not simplified toy versions of the cryptography — BLAKE3 Merkle proofs and Ed25519 signatures work exactly as they would in a production system, just running in-process instead of on tap hardware sitting inside a datacenter.
- The RSA accumulator in `accumulator.py` is likewise real, tested cryptography, not a simulation of one — but it has a genuine, named limitation: `trusted_setup()` generates the RSA modulus itself, and whoever runs that step could in principle know its factorization and forge proofs. A real deployment needs an actual trusted third party or a multi-party ceremony for that one step; this repo is honest about not solving it, in the same docstring that explains the rest of the math.
- The classifier is intentionally simple and interpretable, not adversarially robust. Section 4 of `spec/PROTOCOL.md` is explicit about what it would take to beat it, and points at the Compute Verification Project's open competition on exactly this problem.

## Repository layout

```
src/fides/
  trace.py         synthetic kernel-event trace generator (training / inference / mixed)
  features.py      privacy-preserving statistical fingerprint of a trace
  classifier.py     interpretable inference-vs-training classifier
  commitment.py     BLAKE3 Merkle commitment + proofs — the packet-hashing tap
  identity.py       Ed25519 device identity (signing / verification)
  attestation.py    Prover / Verifier: commit, spot-check reveal, audit
  ledger.py         hash-chained, signed audit ledger (tamper-evident reporting)
  security.py       detection-probability math (exact + Poisson approximation)
  accumulator.py    RSA accumulator: membership / non-membership proofs
  zk_verification.py ZKProver / ZKVerifier: certainty-based compliance proof
  protocol.py       Tap: wires prover + verifier + registry + ledger together
spec/PROTOCOL.md     RFC-style writeup: threat model, math, limitations
docs/ARCHITECTURE.md  the diagram above plus a walk through each module
examples/demo.py      end-to-end runnable demo, both mechanisms
tests/                59 tests, all passing
```

## References

- Shavit, 2023. [What does it take to catch a Chinchilla?](https://arxiv.org/abs/2303.11341)
- Wasil et al., 2024. [Verification Methods for International AI Agreements](https://arxiv.org/abs/2408.16074)
- Baker et al., 2025 (RAND). [Verifying International Agreements on AI](https://www.rand.org/pubs/working_papers/WRA4077-1.html)
- Petrie et al., 2025. [Flexible Hardware-Enabled Guarantees (flexHEG)](https://arxiv.org/abs/2506.15093)
- Scher & Thiergart, 2025. [Mechanisms to Verify International Agreements About AI Development](https://arxiv.org/abs/2506.15867)
- Harack et al., 2025 (Oxford AIGI). [Verification for International AI Governance](https://aigi.ox.ac.uk/publications/verification-for-international-ai-governance/)
- Rinberg et al., 2025. [Verifying LLM Inference to Detect Model Weight Exfiltration](https://arxiv.org/abs/2511.02620) — `security.py`'s Poisson approximation is tested against this derivation.
- Ong et al., 2025. [TOPLOC: A Locality Sensitive Hashing Scheme for Trustless Verifiable Inference](https://arxiv.org/abs/2501.16007) ([code](https://github.com/PrimeIntellect-ai/toploc))
- Karvonen et al., 2025. [DiFR: Inference Verification Despite Nondeterminism](https://arxiv.org/abs/2511.20621) — the "Token-DiFR" recomputation scheme referenced in the AI 2040 SITREP.
- Cankaya, 2026. [Bit-Exact AI Inference Verification Without Performance Tradeoffs](https://arxiv.org/abs/2606.00279)
- [AI 2040: Plan A — Verification Plan](https://ai-2040.com/supplements/verification-plan)
- [Amodo Design — AI 2040 Plan A Verification SITREP](https://amododesign.com/ai-verification/plan-a-sitrep/)
- Benaloh & de Mare, 1993. One-Way Accumulators: A Decentralized Alternative to Digital Signatures. EUROCRYPT '93.
- Barić & Pfitzmann, 1997. Collision-Free Accumulators and Fail-Stop Signature Schemes Without Trees. EUROCRYPT '97.
- Li, Li & Xue, 2007. Universal Accumulators with Efficient Nonmembership Proofs. ACNS 2007 — `accumulator.py`'s non-membership witness construction.

## License

MIT — see `LICENSE`.
