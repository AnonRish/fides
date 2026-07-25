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
]

__version__ = "0.1.0"
