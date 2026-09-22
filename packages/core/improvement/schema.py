"""Proposal schema: dataclasses, state machine and validation.

Source of truth for the shape of an improvement proposal. No I/O in this
module. Stdlib only.

The governing rule of this package: the system proposes, the owner decides.
Nothing here -- and nothing that imports this -- writes to ``plano/``.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional

SCHEMA_VERSION = 1

#: Fields that must be present and non-blank before a proposal is written.
REQUIRED_FIELDS = ("id", "problem", "improvement", "estimated_impact")

#: A proposal id becomes a file name -- keep it free of path separators.
_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

#: Number of *distinct blocks* that must share an error type before the
#: pattern counts as recurring.
DEFAULT_THRESHOLD = 3


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class ImprovementError(Exception):
    """Base class for every error raised by the improvement package."""


class ProposalNotFoundError(ImprovementError):
    """The requested proposal does not exist on disk."""


class ProposalExistsError(ImprovementError):
    """A proposal with that id already exists; create() never overwrites."""


class InvalidTransitionError(ImprovementError):
    """The requested state transition is not in the state machine."""


class EvalGateError(ImprovementError):
    """High-impact proposal without a passing eval result."""


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------


def utc_now() -> str:
    """Current UTC time as ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_proposal_id() -> str:
    """Time-sortable id with a random suffix: P-20260922T101530-a1b2c3d4.

    The timestamp lives inside the id, so ``<ID>.md`` satisfies the
    ``<timestamp>.md`` requirement while keeping O(1) lookup by id.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"P-{stamp}-{uuid.uuid4().hex[:8]}"


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


def _slugify(text: str, max_len: int = 48) -> str:
    """Lowercase ascii slug, safe for a file name. Empty input -> 'melhoria'."""
    lowered = (text or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not slug:
        return "melhoria"
    return slug[:max_len].strip("-") or "melhoria"


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class TargetType(str, Enum):
    GOTCHA = "gotcha"
    CONCEPT = "concept"
    PROCEDURE = "procedure"
    DECISION = "decision"
    RULE = "rule"
    #: Proposals aimed at the plan itself -- what detect_patterns() produces.
    PLAN = "plan"


#: Areas where a wrong change is expensive to undo. Approving one of these
#: requires a passing eval result (fail-closed).
HIGH_IMPACT_TYPES: FrozenSet[TargetType] = frozenset(
    {TargetType.RULE, TargetType.PROCEDURE, TargetType.DECISION, TargetType.PLAN}
)


#: The complete transition table. Anything not listed here is rejected.
ALLOWED_TRANSITIONS = {
    (ProposalStatus.PENDING, ProposalStatus.APPROVED),
    (ProposalStatus.PENDING, ProposalStatus.REJECTED),
    (ProposalStatus.APPROVED, ProposalStatus.IMPLEMENTED),
}

TERMINAL_STATES = frozenset({ProposalStatus.REJECTED, ProposalStatus.IMPLEMENTED})


def check_transition(current: ProposalStatus, target: ProposalStatus) -> None:
    """Raise InvalidTransitionError unless the transition is in the table."""
    if (current, target) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(
            f"transition {current.value} -> {target.value} is not allowed"
        )


def _coerce_status(value: Any) -> ProposalStatus:
    if isinstance(value, ProposalStatus):
        return value
    try:
        return ProposalStatus(str(value))
    except ValueError:
        raise ValueError(f"unknown proposal status: {value!r}")


def _coerce_target_type(value: Any) -> TargetType:
    if isinstance(value, TargetType):
        return value
    try:
        return TargetType(str(value))
    except ValueError:
        raise ValueError(f"unknown target type: {value!r}")


# --------------------------------------------------------------------------
# Payload dataclasses
# --------------------------------------------------------------------------


@dataclass
class Evidence:
    """One observed fact backing a proposal. `block_id` is the load-bearing part."""

    block_id: str
    error_type: str = ""
    detail: str = ""
    occurred_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "error_type": self.error_type,
            "detail": self.detail,
            "occurred_at": self.occurred_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Evidence":
        if isinstance(data, Evidence):
            return cls(data.block_id, data.error_type, data.detail, data.occurred_at)
        if not isinstance(data, dict):
            raise ValueError("evidence entry must be an object")
        block_id = str(data.get("block_id", "") or "").strip()
        if not block_id:
            raise ValueError("evidence entry requires a non-empty 'block_id'")
        return cls(
            block_id=block_id,
            error_type=str(data.get("error_type", "") or ""),
            detail=str(data.get("detail", "") or ""),
            occurred_at=str(data.get("occurred_at", "") or ""),
        )


@dataclass
class EvalResult:
    """Outcome of an evaluation run. Produced elsewhere; never computed here."""

    score_before: float
    score_after: float
    passed: bool
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_before": self.score_before,
            "score_after": self.score_after,
            "passed": self.passed,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "EvalResult":
        if isinstance(data, EvalResult):
            return cls(data.score_before, data.score_after, data.passed, data.notes)
        if not isinstance(data, dict):
            raise ValueError("eval_result must be an object")
        if "passed" not in data:
            raise ValueError("eval_result requires a 'passed' boolean")
        try:
            score_before = float(data.get("score_before", 0.0))
            score_after = float(data.get("score_after", 0.0))
        except (TypeError, ValueError):
            raise ValueError("eval_result scores must be numbers")
        # `passed` is read as given: whoever ran the eval owns the criterion.
        # Recomputing it from the scores would duplicate the rule in two places.
        return cls(
            score_before=score_before,
            score_after=score_after,
            passed=bool(data["passed"]),
            notes=str(data.get("notes", "") or ""),
        )


@dataclass
class ApprovalPolicy:
    """Decides only whether an eval is *required* -- never whether approval is.

    Acceptance criterion 3 ("explicit owner approval before implementing any
    proposal") is absolute: there is no field here that can waive approve().
    """

    require_eval: FrozenSet[TargetType] = HIGH_IMPACT_TYPES
    min_confidence: float = 0.0

    def needs_eval(self, target_type: TargetType) -> bool:
        return target_type in self.require_eval


@dataclass
class Proposal:
    """A proposed improvement, awaiting the owner's decision."""

    # required
    id: str
    problem: str
    improvement: str
    estimated_impact: str
    evidence: List[Evidence] = field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: str = ""
    # optional
    block_id_origem: Optional[str] = None
    target_type: TargetType = TargetType.PLAN
    target_path: str = ""
    confidence: Optional[float] = None
    rationale: str = ""
    eval_result: Optional[EvalResult] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    reject_reason: str = ""
    implemented_at: Optional[str] = None
    implemented_ref: str = ""
    updated_at: str = ""
    schema_version: int = SCHEMA_VERSION

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "problem": self.problem,
            "evidence": [item.to_dict() for item in self.evidence],
            "improvement": self.improvement,
            "estimated_impact": self.estimated_impact,
            "status": self.status.value,
            "created_at": self.created_at,
            "block_id_origem": self.block_id_origem,
            "target_type": self.target_type.value,
            "target_path": self.target_path,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "eval_result": self.eval_result.to_dict() if self.eval_result else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejected_by": self.rejected_by,
            "rejected_at": self.rejected_at,
            "reject_reason": self.reject_reason,
            "implemented_at": self.implemented_at,
            "implemented_ref": self.implemented_ref,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Proposal":
        """Build a Proposal from a plain dict, validating required fields."""
        if not isinstance(data, dict):
            raise ValueError("proposal payload must be an object")

        validate_required(data)

        raw_eval = data.get("eval_result")
        proposal = cls(
            id=str(data["id"]).strip(),
            problem=str(data["problem"]),
            improvement=str(data["improvement"]),
            estimated_impact=str(data["estimated_impact"]),
            evidence=coerce_evidence(data.get("evidence")),
            status=_coerce_status(data.get("status", ProposalStatus.PENDING)),
            created_at=str(data.get("created_at", "") or ""),
            block_id_origem=(
                str(data["block_id_origem"])
                if data.get("block_id_origem") is not None
                else None
            ),
            target_type=_coerce_target_type(data.get("target_type", TargetType.PLAN)),
            target_path=str(data.get("target_path", "") or ""),
            confidence=(
                _coerce_confidence(data["confidence"])
                if data.get("confidence") is not None
                else None
            ),
            rationale=str(data.get("rationale", "") or ""),
            eval_result=EvalResult.from_dict(raw_eval) if raw_eval else None,
            approved_by=(
                str(data["approved_by"]) if data.get("approved_by") is not None else None
            ),
            approved_at=(
                str(data["approved_at"]) if data.get("approved_at") is not None else None
            ),
            rejected_by=(
                str(data["rejected_by"]) if data.get("rejected_by") is not None else None
            ),
            rejected_at=(
                str(data["rejected_at"]) if data.get("rejected_at") is not None else None
            ),
            reject_reason=str(data.get("reject_reason", "") or ""),
            implemented_at=(
                str(data["implemented_at"])
                if data.get("implemented_at") is not None
                else None
            ),
            implemented_ref=str(data.get("implemented_ref", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )
        validate_id(proposal.id, "id")
        return proposal

    # -- convenience ------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    @property
    def block_ids(self) -> List[str]:
        """Distinct block ids cited as evidence, sorted."""
        return sorted({item.block_id for item in self.evidence})

    def slug(self) -> str:
        return _slugify(self.improvement or self.problem)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"confidence must be a number in [0.0, 1.0], got {value!r}")
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"confidence must be within [0.0, 1.0], got {number!r}")
    return number


def coerce_evidence(value: Any) -> List[Evidence]:
    """Normalize evidence into a list of Evidence. Never accepts an empty list.

    A proposal without evidence is a guess, and guesses do not belong in the
    owner's approval queue.
    """
    if value is None:
        raise ValueError("proposal requires at least one evidence entry")
    if isinstance(value, (str, bytes, dict)):
        raise ValueError("evidence must be a list of evidence objects")
    try:
        items = list(value)
    except TypeError:
        raise ValueError("evidence must be a list of evidence objects")
    if not items:
        raise ValueError("proposal requires at least one evidence entry")
    return [Evidence.from_dict(item) for item in items]


def validate_required(data: Dict[str, Any]) -> None:
    """Raise ValueError when a required field is missing, None or blank.

    Fail-closed: a proposal that cannot be validated is never written.
    """
    missing = []
    for name in REQUIRED_FIELDS:
        value = data.get(name)
        if value is None:
            missing.append(name)
            continue
        if not isinstance(value, str):
            raise ValueError(
                f"proposal field '{name}' must be a string, got {type(value).__name__}"
            )
        if not value.strip():
            missing.append(name)
    if missing:
        raise ValueError(
            "proposal is missing required field(s): " + ", ".join(sorted(missing))
        )


def validate_proposal(proposal: Proposal) -> Proposal:
    """Full validation of an assembled Proposal. Returns it for chaining."""
    validate_required(
        {
            "id": proposal.id,
            "problem": proposal.problem,
            "improvement": proposal.improvement,
            "estimated_impact": proposal.estimated_impact,
        }
    )
    validate_id(proposal.id, "id")
    if not isinstance(proposal.status, ProposalStatus):
        raise ValueError("proposal.status must be a ProposalStatus")
    if not isinstance(proposal.target_type, TargetType):
        raise ValueError("proposal.target_type must be a TargetType")
    if not proposal.evidence:
        raise ValueError("proposal requires at least one evidence entry")
    for item in proposal.evidence:
        if not isinstance(item, Evidence) or not str(item.block_id).strip():
            raise ValueError("every evidence entry requires a non-empty 'block_id'")
    if proposal.confidence is not None:
        _coerce_confidence(proposal.confidence)
    if proposal.eval_result is not None and not isinstance(
        proposal.eval_result, EvalResult
    ):
        raise ValueError("proposal.eval_result must be an EvalResult")
    return proposal
