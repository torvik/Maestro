"""Universal Context Packet: the data contract from any agent to any executor.

A UCP is a pure in-memory object. It never touches the filesystem, never names
a harness in a type or a field, and can never hold a credential (see the trust
boundary enforcement in `schema.assert_no_secrets`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from packages.core.protocol.schema import (
    ANY_AGENT,
    CONTEXT_PACKET_VERSION,
    as_dict,
    as_optional_float,
    as_optional_int,
    as_str_list,
    as_text,
    assert_no_secrets,
    coerce_schema_version,
    digest_of,
    emit_with_extensions,
    generate_id,
    require_text,
    split_known,
    utc_now,
)

__all__ = [
    "CONTEXT_PACKET_VERSION",
    "BlockSpec",
    "ContextFile",
    "MemoryEntry",
    "Budget",
    "HandoffRef",
    "UCP",
]


# --------------------------------------------------------------------------
# Payload dataclasses
# --------------------------------------------------------------------------


@dataclass
class BlockSpec:
    """What the executor is being asked to do, in structured form.

    Structured rather than a prose blob so that an adapter can read
    `allowed_paths` and `test_command` without parsing Markdown.
    """

    block_id: str
    title: str = ""
    spec_text: str = ""
    spec_path: str = ""
    complexity: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    forbidden_actions: List[str] = field(default_factory=list)
    stop_and_ask: List[str] = field(default_factory=list)
    test_command: str = ""
    extensions: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "block_id",
        "title",
        "spec_text",
        "spec_path",
        "complexity",
        "acceptance_criteria",
        "allowed_paths",
        "forbidden_actions",
        "stop_and_ask",
        "test_command",
    )

    def __post_init__(self) -> None:
        self.block_id = require_text(self.block_id, "block_spec.block_id")
        self.title = as_text(self.title)
        self.spec_text = as_text(self.spec_text)
        self.spec_path = as_text(self.spec_path)
        self.complexity = as_text(self.complexity)
        self.acceptance_criteria = as_str_list(
            self.acceptance_criteria, "block_spec.acceptance_criteria"
        )
        self.allowed_paths = as_str_list(self.allowed_paths, "block_spec.allowed_paths")
        self.forbidden_actions = as_str_list(
            self.forbidden_actions, "block_spec.forbidden_actions"
        )
        self.stop_and_ask = as_str_list(self.stop_and_ask, "block_spec.stop_and_ask")
        self.test_command = as_text(self.test_command)
        self.extensions = as_dict(self.extensions, "block_spec.extensions")

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "block_id": self.block_id,
                "title": self.title,
                "spec_text": self.spec_text,
                "spec_path": self.spec_path,
                "complexity": self.complexity,
                "acceptance_criteria": list(self.acceptance_criteria),
                "allowed_paths": list(self.allowed_paths),
                "forbidden_actions": list(self.forbidden_actions),
                "stop_and_ask": list(self.stop_and_ask),
                "test_command": self.test_command,
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "BlockSpec":
        if isinstance(data, BlockSpec):
            return data
        if data is None:
            raise ValueError("block_spec is required")
        if not isinstance(data, dict):
            raise ValueError(
                f"block_spec must be an object, got {type(data).__name__}"
            )
        return cls(
            block_id=data.get("block_id"),
            title=as_text(data.get("title")),
            spec_text=as_text(data.get("spec_text")),
            spec_path=as_text(data.get("spec_path")),
            complexity=as_text(data.get("complexity")),
            acceptance_criteria=as_str_list(
                data.get("acceptance_criteria"), "block_spec.acceptance_criteria"
            ),
            allowed_paths=as_str_list(
                data.get("allowed_paths"), "block_spec.allowed_paths"
            ),
            forbidden_actions=as_str_list(
                data.get("forbidden_actions"), "block_spec.forbidden_actions"
            ),
            stop_and_ask=as_str_list(data.get("stop_and_ask"), "block_spec.stop_and_ask"),
            test_command=as_text(data.get("test_command")),
            extensions=split_known(data, cls._KNOWN),
        )


@dataclass
class ContextFile:
    """One repository file made available to the executor."""

    path: str
    content: str = ""
    priority: int = 0
    tokens: int = 0
    truncated: bool = False
    extensions: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("path", "content", "priority", "tokens", "truncated")

    def __post_init__(self) -> None:
        self.path = require_text(self.path, "context_files[].path")
        self.content = as_text(self.content)
        self.priority = int(self.priority or 0)
        tokens = as_optional_int(self.tokens, "context_files[].tokens")
        self.tokens = 0 if tokens is None else tokens
        self.truncated = bool(self.truncated)
        self.extensions = as_dict(self.extensions, "context_files[].extensions")

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "path": self.path,
                "content": self.content,
                "priority": self.priority,
                "tokens": self.tokens,
                "truncated": self.truncated,
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "ContextFile":
        if isinstance(data, ContextFile):
            return data
        if not isinstance(data, dict):
            raise ValueError("context_files[] entries must be objects")
        return cls(
            path=data.get("path"),
            content=as_text(data.get("content")),
            priority=data.get("priority") or 0,
            tokens=data.get("tokens") or 0,
            truncated=bool(data.get("truncated", False)),
            extensions=split_known(data, cls._KNOWN),
        )


@dataclass
class MemoryEntry:
    """One recalled memory item. `kind` is free-form data, never a type."""

    text: str = ""
    id: str = ""
    kind: str = ""
    source: str = ""
    score: float = 0.0
    extensions: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = ("text", "id", "kind", "source", "score")

    def __post_init__(self) -> None:
        self.text = as_text(self.text)
        self.id = as_text(self.id)
        self.kind = as_text(self.kind)
        self.source = as_text(self.source)
        try:
            self.score = float(self.score or 0.0)
        except (TypeError, ValueError):
            raise ValueError(f"memory_entries[].score must be a number, got {self.score!r}")
        self.extensions = as_dict(self.extensions, "memory_entries[].extensions")

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "id": self.id,
                "kind": self.kind,
                "text": self.text,
                "source": self.source,
                "score": self.score,
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "MemoryEntry":
        if isinstance(data, MemoryEntry):
            return data
        if isinstance(data, str):
            return cls(text=data)
        if not isinstance(data, dict):
            raise ValueError("memory_entries[] entries must be objects")
        return cls(
            text=as_text(data.get("text")),
            id=as_text(data.get("id")),
            kind=as_text(data.get("kind")),
            source=as_text(data.get("source")),
            score=data.get("score") or 0.0,
            extensions=split_known(data, cls._KNOWN),
        )


@dataclass
class Budget:
    """Execution limits. Every field is optional; None means 'no limit'.

    A negative limit raises: downstream it would read as 'unlimited', which is
    the kind of silent failure this protocol exists to prevent.
    """

    max_turns: Optional[int] = None
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    context_tokens: Optional[int] = None
    exploration_files: Optional[int] = None
    change_files: Optional[int] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "max_turns",
        "max_tokens",
        "max_cost_usd",
        "context_tokens",
        "exploration_files",
        "change_files",
    )

    def __post_init__(self) -> None:
        self.max_turns = as_optional_int(self.max_turns, "budget.max_turns")
        self.max_tokens = as_optional_int(self.max_tokens, "budget.max_tokens")
        self.max_cost_usd = as_optional_float(self.max_cost_usd, "budget.max_cost_usd")
        self.context_tokens = as_optional_int(
            self.context_tokens, "budget.context_tokens"
        )
        self.exploration_files = as_optional_int(
            self.exploration_files, "budget.exploration_files"
        )
        self.change_files = as_optional_int(self.change_files, "budget.change_files")
        self.extensions = as_dict(self.extensions, "budget.extensions")

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "max_turns": self.max_turns,
                "max_tokens": self.max_tokens,
                "max_cost_usd": self.max_cost_usd,
                "context_tokens": self.context_tokens,
                "exploration_files": self.exploration_files,
                "change_files": self.change_files,
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "Budget":
        if isinstance(data, Budget):
            return data
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError(f"budget must be an object, got {type(data).__name__}")
        return cls(
            max_turns=data.get("max_turns"),
            max_tokens=data.get("max_tokens"),
            max_cost_usd=data.get("max_cost_usd"),
            context_tokens=data.get("context_tokens"),
            exploration_files=data.get("exploration_files"),
            change_files=data.get("change_files"),
            extensions=split_known(data, cls._KNOWN),
        )


@dataclass
class HandoffRef:
    """Resume context carried into a block that continues someone else's work.

    Structurally compatible with the handoff package's ResumePacket, but
    deliberately *not* an import of it: the protocol must stay a leaf. Mapping
    between the two is the adapter's job.
    """

    handoff_id: str = ""
    from_agent: str = ""
    to_agent: str = ANY_AGENT
    context_summary: str = ""
    next_steps: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    files_touched: List[str] = field(default_factory=list)
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    extensions: Dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "handoff_id",
        "from_agent",
        "to_agent",
        "context_summary",
        "next_steps",
        "open_questions",
        "files_touched",
        "checkpoint",
    )

    def __post_init__(self) -> None:
        self.handoff_id = as_text(self.handoff_id)
        self.from_agent = as_text(self.from_agent)
        self.to_agent = as_text(self.to_agent) or ANY_AGENT
        self.context_summary = as_text(self.context_summary)
        self.next_steps = as_str_list(self.next_steps, "handoff.next_steps")
        self.open_questions = as_str_list(self.open_questions, "handoff.open_questions")
        self.files_touched = as_str_list(self.files_touched, "handoff.files_touched")
        self.checkpoint = as_dict(self.checkpoint, "handoff.checkpoint")
        self.extensions = as_dict(self.extensions, "handoff.extensions")

    def addressed_to(self, agent: str) -> bool:
        """True when `agent` may pick this work up. `to_agent='any'` matches all."""
        return self.to_agent == ANY_AGENT or self.to_agent == agent

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "handoff_id": self.handoff_id,
                "from_agent": self.from_agent,
                "to_agent": self.to_agent,
                "context_summary": self.context_summary,
                "next_steps": list(self.next_steps),
                "open_questions": list(self.open_questions),
                "files_touched": list(self.files_touched),
                "checkpoint": dict(self.checkpoint),
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> Optional["HandoffRef"]:
        if data is None:
            return None
        if isinstance(data, HandoffRef):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"handoff must be an object or null, got {type(data).__name__}")
        return cls(
            handoff_id=as_text(data.get("handoff_id")),
            from_agent=as_text(data.get("from_agent")),
            to_agent=as_text(data.get("to_agent")) or ANY_AGENT,
            context_summary=as_text(data.get("context_summary")),
            next_steps=as_str_list(data.get("next_steps"), "handoff.next_steps"),
            open_questions=as_str_list(
                data.get("open_questions"), "handoff.open_questions"
            ),
            files_touched=as_str_list(data.get("files_touched"), "handoff.files_touched"),
            checkpoint=as_dict(data.get("checkpoint"), "handoff.checkpoint"),
            extensions=split_known(data, cls._KNOWN),
        )


# --------------------------------------------------------------------------
# The packet
# --------------------------------------------------------------------------

_UCP_KNOWN = (
    "schema_version",
    "ucp_id",
    "run_id",
    "producer_agent",
    "created_at",
    "block_spec",
    "conventions",
    "context_files",
    "memory_entries",
    "budget",
    "handoff",
)


@dataclass
class UCP:
    """Universal Context Packet.

    Everything an executor needs to run one block, and nothing else. No harness
    name appears in any type or field of this contract -- agent identifiers may
    appear only as *data* (`producer_agent`, `handoff.from_agent`).
    """

    block_spec: Any
    conventions: Any = field(default_factory=dict)
    context_files: List[Any] = field(default_factory=list)
    memory_entries: List[Any] = field(default_factory=list)
    budget: Any = field(default_factory=Budget)
    handoff: Optional[Any] = None
    ucp_id: str = ""
    run_id: str = ""
    producer_agent: str = ""
    created_at: str = ""
    schema_version: int = CONTEXT_PACKET_VERSION
    extensions: Dict[str, Any] = field(default_factory=dict)

    # -- construction -----------------------------------------------------

    def __post_init__(self) -> None:
        self.block_spec = BlockSpec.from_dict(self.block_spec)
        self.conventions = _normalize_conventions(self.conventions)
        self.context_files = [
            ContextFile.from_dict(item) for item in _as_sequence(self.context_files, "context_files")
        ]
        self.memory_entries = [
            MemoryEntry.from_dict(item)
            for item in _as_sequence(self.memory_entries, "memory_entries")
        ]
        self.budget = Budget.from_dict(self.budget)
        self.handoff = HandoffRef.from_dict(self.handoff)
        self.ucp_id = as_text(self.ucp_id) or generate_id("U")
        self.run_id = as_text(self.run_id)
        self.producer_agent = as_text(self.producer_agent)
        self.created_at = as_text(self.created_at) or utc_now()
        self.schema_version = coerce_schema_version(
            self.schema_version, CONTEXT_PACKET_VERSION
        )
        self.extensions = as_dict(self.extensions, "extensions")

        # Trust boundary, enforced at construction: no UCP instance can ever
        # exist holding a credential. Fail-closed, no opt-out.
        assert_no_secrets(self.to_dict(), "UCP")

    # -- version ----------------------------------------------------------

    @property
    def is_forward_version(self) -> bool:
        """True when this packet declares a wire version newer than ours."""
        return self.schema_version > CONTEXT_PACKET_VERSION

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "schema_version": self.schema_version,
                "ucp_id": self.ucp_id,
                "run_id": self.run_id,
                "producer_agent": self.producer_agent,
                "created_at": self.created_at,
                "block_spec": self.block_spec.to_dict(),
                "conventions": dict(self.conventions),
                "context_files": [item.to_dict() for item in self.context_files],
                "memory_entries": [item.to_dict() for item in self.memory_entries],
                "budget": self.budget.to_dict(),
                "handoff": self.handoff.to_dict() if self.handoff else None,
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "UCP":
        """Parse a packet. Unknown fields are preserved, never rejected.

        Raises ValueError on a malformed packet and UCPSecurityError when the
        payload crosses the trust boundary with something secret in it.
        """
        if isinstance(data, UCP):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"UCP payload must be an object, got {type(data).__name__}")
        if "block_spec" not in data or data.get("block_spec") is None:
            raise ValueError("UCP is missing required field: block_spec")

        version = coerce_schema_version(
            data.get("schema_version"), CONTEXT_PACKET_VERSION
        )
        payload, version = _migrate(dict(data), version)

        return cls(
            block_spec=BlockSpec.from_dict(payload.get("block_spec")),
            conventions=payload.get("conventions"),
            context_files=payload.get("context_files") or [],
            memory_entries=payload.get("memory_entries") or [],
            budget=payload.get("budget"),
            handoff=payload.get("handoff"),
            ucp_id=as_text(payload.get("ucp_id")),
            run_id=as_text(payload.get("run_id")),
            producer_agent=as_text(payload.get("producer_agent")),
            created_at=as_text(payload.get("created_at")),
            schema_version=version,
            extensions=split_known(payload, _UCP_KNOWN),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "UCP":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"UCP payload is not valid JSON: {exc}") from None
        return cls.from_dict(data)

    # -- identity ---------------------------------------------------------

    def digest(self) -> str:
        """Stable sha256 of the packet content, excluding volatile identity.

        `ucp_id` and `created_at` are excluded so that two packets with the
        same instructions hash the same -- that is what makes the digest useful
        as proof of *what* was executed in a `block_started` event.
        """
        payload = self.to_dict()
        payload.pop("ucp_id", None)
        payload.pop("created_at", None)
        return digest_of(payload)

    # -- convenience ------------------------------------------------------

    @property
    def block_id(self) -> str:
        return self.block_spec.block_id

    def context_paths(self) -> List[str]:
        return [item.path for item in self.context_files]

    def total_context_tokens(self) -> int:
        return sum(item.tokens for item in self.context_files)


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


def _as_sequence(value: Any, label: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, dict)):
        raise ValueError(f"{label} must be a list")
    try:
        return list(value)
    except TypeError:
        raise ValueError(f"{label} must be a list")


def _normalize_conventions(value: Any) -> Dict[str, Any]:
    """Conventions are always an object on the wire.

    A bare string is accepted from producers that only have prose, and is
    normalized to {"notes": ...} so adapters never face two shapes.
    """
    if value is None:
        return {}
    if isinstance(value, str):
        return {"notes": value} if value else {}
    return as_dict(value, "conventions")


#: Migration chain for packets older than the current version. Empty at v1;
#: an entry maps <from_version> -> callable(payload) -> payload.
_MIGRATIONS: Dict[int, Any] = {}


def _migrate(payload: Dict[str, Any], version: int) -> Any:
    """Bring an older payload up to the current version, best effort.

    A version newer than ours is returned untouched: the parser reads what it
    understands and leaves the decision about the rest to the consumer.
    """
    if version >= CONTEXT_PACKET_VERSION:
        return payload, version

    original = version
    while version < CONTEXT_PACKET_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            break
        payload = step(payload)
        version += 1

    payload.setdefault("extensions", {})
    if isinstance(payload["extensions"], dict):
        payload["extensions"]["_migrated_from"] = original
    return payload, CONTEXT_PACKET_VERSION
