"""Typed handoff between agents: claim, workstreams and cross-agent resume.

An agent that ends a session writes a typed handoff to
``.maestro/handoffs/<ID>.json``; another agent claims it exactly once and
resumes from the bounded context it carries.

No I/O at import time.
"""

from packages.core.handoff.schema import (
    ANY_AGENT,
    ALLOWED_TRANSITIONS,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    TERMINAL_STATES,
    Checkpoint,
    ClaimError,
    Handoff,
    HandoffError,
    HandoffExistsError,
    HandoffNotFoundError,
    HandoffStatus,
    InvalidTransitionError,
    Lease,
    LeaseError,
    ResumePacket,
    StateSnapshot,
    Workstream,
    WorkstreamNotFoundError,
    utc_now,
)
from packages.core.handoff.storage import HandoffStorage
from packages.core.handoff.manager import HandoffManager
from packages.core.handoff.workstreams import (
    DEFAULT_LEASE_TTL_SECONDS,
    WorkstreamRegistry,
)

__all__ = [
    # manager + registry
    "HandoffManager",
    "WorkstreamRegistry",
    "HandoffStorage",
    # data types
    "Handoff",
    "HandoffStatus",
    "StateSnapshot",
    "Checkpoint",
    "ResumePacket",
    "Workstream",
    "Lease",
    # errors
    "HandoffError",
    "HandoffNotFoundError",
    "HandoffExistsError",
    "InvalidTransitionError",
    "ClaimError",
    "WorkstreamNotFoundError",
    "LeaseError",
    # constants / helpers
    "ANY_AGENT",
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "DEFAULT_LEASE_TTL_SECONDS",
    "utc_now",
]
