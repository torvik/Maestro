"""Typed handoff schema: dataclasses, state machine and validation.

Source of truth for the shape of a handoff. No I/O in this module.
Stdlib only.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1

#: Sentinel for "any agent may claim this handoff".
ANY_AGENT = "any"

#: Fields that must be present and non-blank before a handoff is written.
REQUIRED_FIELDS = ("id", "from_agent", "to_agent", "block_id", "context_summary")

#: A handoff id becomes a file name -- keep it free of path separators.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class HandoffError(Exception):
    """Base class for every error raised by the handoff package."""


class HandoffNotFoundError(HandoffError):
    """The requested handoff does not exist on disk."""


class HandoffExistsError(HandoffError):
    """A handoff with that id already exists; create() never overwrites."""


class InvalidTransitionError(HandoffError):
    """The requested state transition is not in the state machine."""


class ClaimError(HandoffError):
    """The claim could not be granted (already claimed, or wrong agent)."""


class WorkstreamNotFoundError(HandoffError):
    """The workstream is not registered."""


class LeaseError(HandoffError):
    """The workstream lease could not be acquired or released."""


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------


def utc_now() -> str:
    """Current UTC time as ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into an aware datetime, or None if unusable."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_past(value: Optional[str], now: Optional[str] = None) -> bool:
    """True when `value` is a timestamp at or before `now` (default: current UTC)."""
    deadline = parse_ts(value or "")
    if deadline is None:
        return False
    reference = parse_ts(now) if now else datetime.now(timezone.utc)
    if reference is None:
        reference = datetime.now(timezone.utc)
    return deadline <= reference


def generate_handoff_id() -> str:
    """Time-sortable id with a random suffix: H-20260922T101530-a1b2c3d4."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"H-{stamp}-{uuid.uuid4().hex[:8]}"


def validate_id(value: str, label: str = "id") -> str:
    """Ensure an identifier is safe to use as a file name."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required and must be a non-empty string")
    candidate = value.strip()
    if not _ID_RE.match(candidate):
        raise ValueError(
            f"{label} must match [A-Za-z0-9._-]+ (got {value!r}); "
            "path separators are not allowed"
        )
    if candidate in (".", ".."):
        raise ValueError(f"{label} must not be '.' or '..'")
    return candidate


# --------------------------------------------------------------------------
# State machine
# --------------------------------------------------------------------------


class HandoffStatus(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


#: The complete transition table. Anything not listed here is rejected.
ALLOWED_TRANSITIONS = {
    (HandoffStatus.OPEN, HandoffStatus.CLAIMED),
    (HandoffStatus.OPEN, HandoffStatus.EXPIRED),
    (HandoffStatus.OPEN, HandoffStatus.CANCELLED),
    (HandoffStatus.CLAIMED, HandoffStatus.ACCEPTED),
}

TERMINAL_STATES = frozenset(
    {HandoffStatus.ACCEPTED, HandoffStatus.EXPIRED, HandoffStatus.CANCELLED}
)


def check_transition(current: HandoffStatus, target: HandoffStatus) -> None:
    """Raise InvalidTransitionError unless the transition is in the table."""
    if (current, target) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(
            f"transition {current.value} -> {target.value} is not allowed"
        )


def _coerce_status(value: Any) -> HandoffStatus:
    if isinstance(value, HandoffStatus):
        return value
    try:
        return HandoffStatus(str(value))
    except ValueError:
        raise ValueError(f"unknown handoff status: {value!r}")


def _str_list(value: Any, label: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise ValueError(f"{label} must be a list of strings, not a bare string")
    try:
        items = list(value)
    except TypeError:
        raise ValueError(f"{label} must be a list of strings")
    return [str(item) for item in items]


# --------------------------------------------------------------------------
# Payload dataclasses
# --------------------------------------------------------------------------


@dataclass
class Checkpoint:
    """Pointer to the VCS state the receiving agent should resume from."""

    branch: str = ""
    commit: str = ""
    checkpoint_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "commit": self.commit,
            "checkpoint_id": self.checkpoint_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Checkpoint":
        if data is None:
            return cls()
        if isinstance(data, Checkpoint):
            return cls(data.branch, data.commit, data.checkpoint_id)
        if not isinstance(data, dict):
            raise ValueError("checkpoint must be an object")
        return cls(
            branch=str(data.get("branch", "") or ""),
            commit=str(data.get("commit", "") or ""),
            checkpoint_id=str(data.get("checkpoint_id", "") or ""),
        )


@dataclass
class StateSnapshot:
    """Structured state of the interrupted work.

    `context_summary` on the Handoff carries the prose; this carries the
    enumerable facts a receiving agent needs to resume without re-deriving them.
    """

    completed: List[str] = field(default_factory=list)
    remaining: List[str] = field(default_factory=list)
    failed_approaches: List[str] = field(default_factory=list)
    files_touched: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    checkpoint: Checkpoint = field(default_factory=Checkpoint)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completed": list(self.completed),
            "remaining": list(self.remaining),
            "failed_approaches": list(self.failed_approaches),
            "files_touched": list(self.files_touched),
            "next_steps": list(self.next_steps),
            "checkpoint": self.checkpoint.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "StateSnapshot":
        if data is None:
            return cls()
        if isinstance(data, StateSnapshot):
            return cls(
                completed=list(data.completed),
                remaining=list(data.remaining),
                failed_approaches=list(data.failed_approaches),
                files_touched=list(data.files_touched),
                next_steps=list(data.next_steps),
                checkpoint=Checkpoint.from_dict(data.checkpoint),
            )
        if not isinstance(data, dict):
            raise ValueError("state_snapshot must be an object")
        return cls(
            completed=_str_list(data.get("completed"), "state_snapshot.completed"),
            remaining=_str_list(data.get("remaining"), "state_snapshot.remaining"),
            failed_approaches=_str_list(
                data.get("failed_approaches"), "state_snapshot.failed_approaches"
            ),
            files_touched=_str_list(
                data.get("files_touched"), "state_snapshot.files_touched"
            ),
            next_steps=_str_list(data.get("next_steps"), "state_snapshot.next_steps"),
            checkpoint=Checkpoint.from_dict(data.get("checkpoint")),
        )


@dataclass
class Handoff:
    """A typed, validated transfer of work between agents."""

    id: str
    from_agent: str
    to_agent: str
    block_id: str
    context_summary: str
    state_snapshot: StateSnapshot = field(default_factory=StateSnapshot)
    open_questions: List[str] = field(default_factory=list)
    project: str = ""
    workstream: Optional[str] = None
    summary: str = ""
    status: HandoffStatus = HandoffStatus.OPEN
    created_at: str = ""
    updated_at: str = ""
    expires_at: Optional[str] = None
    claimed_by: Optional[str] = None
    claimed_at: Optional[str] = None
    accepted_by: Optional[str] = None
    accepted_at: Optional[str] = None
    cancel_reason: str = ""
    schema_version: int = SCHEMA_VERSION

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "block_id": self.block_id,
            "context_summary": self.context_summary,
            "state_snapshot": self.state_snapshot.to_dict(),
            "open_questions": list(self.open_questions),
            "project": self.project,
            "workstream": self.workstream,
            "summary": self.summary,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at,
            "accepted_by": self.accepted_by,
            "accepted_at": self.accepted_at,
            "cancel_reason": self.cancel_reason,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Handoff":
        """Build a Handoff from a plain dict, validating required fields."""
        if not isinstance(data, dict):
            raise ValueError("handoff payload must be an object")

        validate_required(data)

        handoff = cls(
            id=str(data["id"]).strip(),
            from_agent=str(data["from_agent"]).strip(),
            to_agent=str(data["to_agent"]).strip(),
            block_id=str(data["block_id"]).strip(),
            context_summary=str(data["context_summary"]),
            state_snapshot=StateSnapshot.from_dict(data.get("state_snapshot")),
            open_questions=_str_list(data.get("open_questions"), "open_questions"),
            project=str(data.get("project", "") or ""),
            workstream=(
                str(data["workstream"]) if data.get("workstream") is not None else None
            ),
            summary=str(data.get("summary", "") or ""),
            status=_coerce_status(data.get("status", HandoffStatus.OPEN)),
            created_at=str(data.get("created_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
            expires_at=(
                str(data["expires_at"]) if data.get("expires_at") is not None else None
            ),
            claimed_by=(
                str(data["claimed_by"]) if data.get("claimed_by") is not None else None
            ),
            claimed_at=(
                str(data["claimed_at"]) if data.get("claimed_at") is not None else None
            ),
            accepted_by=(
                str(data["accepted_by"])
                if data.get("accepted_by") is not None
                else None
            ),
            accepted_at=(
                str(data["accepted_at"])
                if data.get("accepted_at") is not None
                else None
            ),
            cancel_reason=str(data.get("cancel_reason", "") or ""),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )
        validate_id(handoff.id, "id")
        return handoff

    # -- convenience ------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def claimable_by(self, agent: str) -> bool:
        """True when `agent` is an eligible recipient for this handoff."""
        return self.to_agent == ANY_AGENT or self.to_agent == agent


@dataclass
class ResumePacket:
    """Bounded context delivered to the agent that claims a handoff.

    Bounded on purpose: everything here already lives in the handoff. Building
    the packet never scans the repository.
    """

    handoff: Handoff
    agent: str
    context_summary: str
    open_questions: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    files_touched: List[str] = field(default_factory=list)
    checkpoint: Checkpoint = field(default_factory=Checkpoint)
    claimed_at: str = ""

    @classmethod
    def assemble(cls, handoff: Handoff, agent: str, claimed_at: str) -> "ResumePacket":
        snap = handoff.state_snapshot
        return cls(
            handoff=handoff,
            agent=agent,
            context_summary=handoff.context_summary,
            open_questions=list(handoff.open_questions),
            next_steps=list(snap.next_steps),
            files_touched=list(snap.files_touched),
            checkpoint=Checkpoint.from_dict(snap.checkpoint),
            claimed_at=claimed_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff.id,
            "agent": self.agent,
            "context_summary": self.context_summary,
            "open_questions": list(self.open_questions),
            "next_steps": list(self.next_steps),
            "files_touched": list(self.files_touched),
            "checkpoint": self.checkpoint.to_dict(),
            "claimed_at": self.claimed_at,
        }


# --------------------------------------------------------------------------
# Workstream dataclasses
# --------------------------------------------------------------------------


@dataclass
class Workstream:
    """A logical line of work inside a project.

    Identity is `id`. `name` is metadata -- renaming it must never break
    handoffs, leases or history, so nothing may index by name.
    """

    id: str
    name: str = ""
    project: str = ""
    blocks: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "project": self.project,
            "blocks": list(self.blocks),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Workstream":
        if not isinstance(data, dict):
            raise ValueError("workstream payload must be an object")
        if not str(data.get("id", "") or "").strip():
            raise ValueError("workstream.id is required")
        return cls(
            id=str(data["id"]).strip(),
            name=str(data.get("name", "") or ""),
            project=str(data.get("project", "") or ""),
            blocks=_str_list(data.get("blocks"), "workstream.blocks"),
            status=str(data.get("status", "active") or "active"),
            created_at=str(data.get("created_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
        )


@dataclass
class Lease:
    """Exclusive execution right over a workstream, valid until expires_at."""

    workstream_id: str
    agent: str
    token: str
    acquired_at: str
    expires_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workstream_id": self.workstream_id,
            "agent": self.agent,
            "token": self.token,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Lease":
        if not isinstance(data, dict):
            raise ValueError("lease payload must be an object")
        return cls(
            workstream_id=str(data.get("workstream_id", "") or ""),
            agent=str(data.get("agent", "") or ""),
            token=str(data.get("token", "") or ""),
            acquired_at=str(data.get("acquired_at", "") or ""),
            expires_at=str(data.get("expires_at", "") or ""),
        )

    @property
    def is_expired(self) -> bool:
        return is_past(self.expires_at)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_required(data: Dict[str, Any]) -> None:
    """Raise ValueError when a required field is missing, None or blank.

    Fail-closed: a handoff that cannot be validated is never written.
    """
    missing = []
    for name in REQUIRED_FIELDS:
        value = data.get(name)
        if value is None:
            missing.append(name)
            continue
        if not isinstance(value, str):
            raise ValueError(f"handoff field '{name}' must be a string, got {type(value).__name__}")
        if not value.strip():
            missing.append(name)
    if missing:
        raise ValueError(
            "handoff is missing required field(s): " + ", ".join(sorted(missing))
        )


def validate_handoff(handoff: Handoff) -> Handoff:
    """Full validation of an assembled Handoff. Returns it for chaining."""
    validate_required(
        {
            "id": handoff.id,
            "from_agent": handoff.from_agent,
            "to_agent": handoff.to_agent,
            "block_id": handoff.block_id,
            "context_summary": handoff.context_summary,
        }
    )
    validate_id(handoff.id, "id")
    if not isinstance(handoff.status, HandoffStatus):
        raise ValueError("handoff.status must be a HandoffStatus")
    if not isinstance(handoff.state_snapshot, StateSnapshot):
        raise ValueError("handoff.state_snapshot must be a StateSnapshot")
    if handoff.workstream is not None:
        validate_id(handoff.workstream, "workstream")
    if handoff.expires_at is not None and parse_ts(handoff.expires_at) is None:
        raise ValueError(f"expires_at is not a valid ISO-8601 timestamp: {handoff.expires_at!r}")
    return handoff
