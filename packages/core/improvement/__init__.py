"""Auto-improvement: proposals, approval/eval gate and audit trail (F13-02).

The system proposes; the owner decides. This package turns recurring failure
patterns into explicit `Proposal` records that wait for an owner's approval,
and records every decision in an append-only audit trail.

It never modifies the plan. `ProposalEngine.to_block_spec()` *returns* the
block dict; writing it into `plano/blocos.json` is the operator's act.

    from packages.core.improvement import ProposalEngine

Stdlib only. No I/O at import time.
"""

from .audit import (
    EVENT_APPROVED,
    EVENT_CREATED,
    EVENT_EVAL_FAILED,
    EVENT_IMPLEMENTED,
    EVENT_REJECTED,
    AuditTrail,
)
from .engine import ProposalEngine, render_sidecar
from .schema import (
    DEFAULT_THRESHOLD,
    HIGH_IMPACT_TYPES,
    SCHEMA_VERSION,
    ApprovalPolicy,
    EvalGateError,
    EvalResult,
    Evidence,
    ImprovementError,
    InvalidTransitionError,
    Proposal,
    ProposalExistsError,
    ProposalNotFoundError,
    ProposalStatus,
    TargetType,
)
from .storage import ProposalStorage

__all__ = [
    "ProposalEngine",
    "Proposal",
    "ProposalStatus",
    "TargetType",
    "Evidence",
    "EvalResult",
    "ApprovalPolicy",
    "AuditTrail",
    "ProposalStorage",
    "ImprovementError",
    "ProposalNotFoundError",
    "ProposalExistsError",
    "InvalidTransitionError",
    "EvalGateError",
    "HIGH_IMPACT_TYPES",
    "DEFAULT_THRESHOLD",
    "SCHEMA_VERSION",
    "EVENT_CREATED",
    "EVENT_APPROVED",
    "EVENT_REJECTED",
    "EVENT_IMPLEMENTED",
    "EVENT_EVAL_FAILED",
    "render_sidecar",
]
