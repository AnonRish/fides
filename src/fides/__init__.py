from .trace import (
    KernelOp,
    KernelEvent,
    ExecutionEpoch,
    generate_training_epoch,
    generate_inference_epoch,
    generate_mixed_epoch,
)
from .features import extract, EpochFingerprint
from .classifier import classify, WorkloadClass
from .identity import DeviceIdentity, verify_signature
from .attestation import Prover, Verifier, Commitment, AuditResult
from .ledger import AuditLedger, LedgerEntry
from .protocol import Tap, Registry
from .security import (
    detection_probability,
    poisson_detection_probability,
    repeated_detection_probability,
    monte_carlo_detection_rate,
)
from .accumulator import (
    AccumulatorSetup,
    trusted_setup,
    hash_to_prime,
    is_probable_prime,
    accumulate,
    membership_witness,
    verify_membership,
    nonmembership_witness,
    verify_nonmembership,
)
from .zk_verification import ZKProver, ZKVerifier, ZKComplianceProof, FORBIDDEN_OPS
from .wipe import wipe, spot_check, fill_block, block_addresses
from .warden import (
    generate_baseline_noise,
    inject_covert_signal,
    autocorrelation,
    autocorrelation_spectrum,
    detect_periodic_signal,
)
from .determinism import deterministic_sum, racy_sum
from .recompute import (
    RecomputationVerifier,
    RecomputationFingerprint,
    generate_activation_vector,
    perturb,
    fabricate,
    simhash,
    hamming_distance,
)
from .packet_reconstruction import (
    PacketCommitment,
    commit_message,
    chunk_message,
    reconstruct_and_verify,
)
from .server_attestation import (
    software_fingerprint,
    issue_challenge,
    respond_to_challenge,
    verify_response,
)
from .toploc_reference import (
    to_bfloat16_bits,
    bfloat16_parts,
    select_topk_by_magnitude,
    lagrange_coefficients,
    evaluate_polynomial,
    build_proof as build_toploc_style_proof,
    verify_proof as verify_toploc_style_proof,
    TopKProof,
    VerificationResult as TopKVerificationResult,
)

__all__ = [
    "KernelOp",
    "KernelEvent",
    "ExecutionEpoch",
    "generate_training_epoch",
    "generate_inference_epoch",
    "generate_mixed_epoch",
    "extract",
    "EpochFingerprint",
    "classify",
    "WorkloadClass",
    "DeviceIdentity",
    "verify_signature",
    "Prover",
    "Verifier",
    "Commitment",
    "AuditResult",
    "AuditLedger",
    "LedgerEntry",
    "Tap",
    "Registry",
    "detection_probability",
    "poisson_detection_probability",
    "repeated_detection_probability",
    "monte_carlo_detection_rate",
    "AccumulatorSetup",
    "trusted_setup",
    "hash_to_prime",
    "is_probable_prime",
    "accumulate",
    "membership_witness",
    "verify_membership",
    "nonmembership_witness",
    "verify_nonmembership",
    "ZKProver",
    "ZKVerifier",
    "ZKComplianceProof",
    "FORBIDDEN_OPS",
    "wipe",
    "spot_check",
    "fill_block",
    "block_addresses",
    "generate_baseline_noise",
    "inject_covert_signal",
    "autocorrelation",
    "autocorrelation_spectrum",
    "detect_periodic_signal",
    "deterministic_sum",
    "racy_sum",
    "RecomputationVerifier",
    "RecomputationFingerprint",
    "generate_activation_vector",
    "perturb",
    "fabricate",
    "simhash",
    "hamming_distance",
    "PacketCommitment",
    "commit_message",
    "chunk_message",
    "reconstruct_and_verify",
    "software_fingerprint",
    "issue_challenge",
    "respond_to_challenge",
    "verify_response",
    "to_bfloat16_bits",
    "bfloat16_parts",
    "select_topk_by_magnitude",
    "lagrange_coefficients",
    "evaluate_polynomial",
    "build_toploc_style_proof",
    "verify_toploc_style_proof",
    "TopKProof",
    "TopKVerificationResult",
]

__version__ = "0.1.0"
