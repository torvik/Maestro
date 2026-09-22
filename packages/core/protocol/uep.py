"""Universal Event Protocol: what any executor emits while running a block.

Six events, one ordering rule, one fail-closed outcome rule. Pure in-memory:
serialization produces strings, never files.

Postel split, applied on purpose:
  - as a *producer* (`UEP.emit`) the protocol is strict, because emitting
    garbage contaminates every downstream consumer;
  - as a *consumer* (`from_dict` / `from_ndjson`) it is tolerant, because
    rejecting an event from a future producer breaks the interoperability this
    protocol exists to create.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from packages.core.protocol.schema import (
    EVENT_PROTOCOL_VERSION,
    UEPError,
    as_dict,
    as_text,
    assert_no_secrets,
    coerce_schema_version,
    emit_with_extensions,
    generate_id,
    require_text,
    split_known,
    utc_now,
)

__all__ = [
    "EVENT_PROTOCOL_VERSION",
    "EventType",
    "TERMINAL_EVENT_TYPES",
    "REQUIRED_PAYLOAD_KEYS",
    "UCPEvent",
    "UEP",
    "UEPError",
]


class EventType(str, Enum):
    """The six events of the protocol. Adding one is a minor version bump;
    removing or renaming one requires event_protocol_version = 2."""

    BLOCK_STARTED = "block_started"
    FILE_READ = "file_read"
    FILE_WRITTEN = "file_written"
    TEST_RUN = "test_run"
    BLOCK_COMPLETED = "block_completed"
    BLOCK_FAILED = "block_failed"


TERMINAL_EVENT_TYPES = frozenset(
    {EventType.BLOCK_COMPLETED.value, EventType.BLOCK_FAILED.value}
)

#: Payload keys demanded at emission time only. Readers never enforce these.
REQUIRED_PAYLOAD_KEYS: Dict[str, tuple] = {
    EventType.BLOCK_STARTED.value: (),
    EventType.FILE_READ.value: ("path",),
    EventType.FILE_WRITTEN.value: ("path",),
    EventType.TEST_RUN.value: ("command", "passed"),
    EventType.BLOCK_COMPLETED.value: (),
    EventType.BLOCK_FAILED.value: ("reason",),
}

_EVENT_KNOWN = (
    "schema_version",
    "event_type",
    "block_id",
    "sequence",
    "timestamp",
    "agent",
    "run_id",
    "event_id",
    "payload",
)

_UEP_KNOWN = ("schema_version", "block_id", "run_id", "ucp_id", "agent", "events")


def _event_type_value(value: Any) -> str:
    """Normalize an event type to its wire string. Never raises."""
    if isinstance(value, EventType):
        return value.value
    return as_text(value)


@dataclass
class UCPEvent:
    """A single observation emitted during the execution of one block."""

    event_type: str
    block_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    timestamp: str = ""
    agent: str = ""
    run_id: str = ""
    event_id: str = ""
    schema_version: int = EVENT_PROTOCOL_VERSION
    extensions: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_type = require_text(
            _event_type_value(self.event_type), "event_type"
        )
        self.block_id = require_text(self.block_id, "block_id")
        self.payload = as_dict(self.payload, "payload")
        try:
            self.sequence = int(self.sequence or 0)
        except (TypeError, ValueError):
            raise ValueError(f"sequence must be an integer, got {self.sequence!r}")
        if self.sequence < 0:
            raise ValueError(f"sequence must not be negative (got {self.sequence})")
        self.timestamp = as_text(self.timestamp) or utc_now()
        self.agent = as_text(self.agent)
        self.run_id = as_text(self.run_id)
        self.event_id = as_text(self.event_id) or generate_id("E")
        self.schema_version = coerce_schema_version(
            self.schema_version, EVENT_PROTOCOL_VERSION
        )
        self.extensions = as_dict(self.extensions, "extensions")

        # Same trust boundary as the UCP: an event payload also leaves the
        # process and lands in logs. Fail-closed, no opt-out.
        assert_no_secrets(self.to_dict(), "UEP event")

    # -- introspection ----------------------------------------------------

    @property
    def is_known_type(self) -> bool:
        """False for an event emitted by a newer producer. Not an error."""
        return self.event_type in {member.value for member in EventType}

    @property
    def is_terminal(self) -> bool:
        return self.event_type in TERMINAL_EVENT_TYPES

    @property
    def is_forward_version(self) -> bool:
        return self.schema_version > EVENT_PROTOCOL_VERSION

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "block_id": self.block_id,
                "sequence": self.sequence,
                "timestamp": self.timestamp,
                "agent": self.agent,
                "run_id": self.run_id,
                "event_id": self.event_id,
                "payload": dict(self.payload),
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "UCPEvent":
        """Tolerant parse: unknown fields and unknown event types are kept."""
        if isinstance(data, UCPEvent):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"event payload must be an object, got {type(data).__name__}")
        return cls(
            event_type=data.get("event_type"),
            block_id=data.get("block_id"),
            payload=as_dict(data.get("payload"), "payload"),
            sequence=data.get("sequence") or 0,
            timestamp=as_text(data.get("timestamp")),
            agent=as_text(data.get("agent")),
            run_id=as_text(data.get("run_id")),
            event_id=as_text(data.get("event_id")),
            schema_version=coerce_schema_version(
                data.get("schema_version"), EVENT_PROTOCOL_VERSION
            ),
            extensions=split_known(data, _EVENT_KNOWN),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class UEP:
    """An ordered stream of events for one execution of one block."""

    block_id: str
    run_id: str = ""
    ucp_id: str = ""
    agent: str = ""
    events: List[Any] = field(default_factory=list)
    schema_version: int = EVENT_PROTOCOL_VERSION
    extensions: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.block_id = require_text(self.block_id, "block_id")
        self.run_id = as_text(self.run_id)
        self.ucp_id = as_text(self.ucp_id)
        self.agent = as_text(self.agent)
        self.events = [UCPEvent.from_dict(item) for item in (self.events or [])]
        self.schema_version = coerce_schema_version(
            self.schema_version, EVENT_PROTOCOL_VERSION
        )
        self.extensions = as_dict(self.extensions, "extensions")

    # -- production -------------------------------------------------------

    @staticmethod
    def supported_event_types() -> List[str]:
        """The event vocabulary an adapter must be able to emit."""
        return [member.value for member in EventType]

    def emit(
        self,
        event_type: Any,
        payload: Optional[Dict[str, Any]] = None,
        **extra: Any,
    ) -> UCPEvent:
        """Append a new event, assigning the next sequence number.

        Strict on purpose: an unknown event type or a missing required payload
        key raises ValueError. Producing garbage is cheaper to stop here than
        to detect in every consumer.
        """
        wire_type = _event_type_value(event_type)
        if wire_type not in REQUIRED_PAYLOAD_KEYS:
            raise ValueError(
                f"unknown event_type for emission: {wire_type!r}; "
                f"expected one of {', '.join(self.supported_event_types())}"
            )
        body: Dict[str, Any] = dict(payload or {})
        body.update(extra)
        missing = [key for key in REQUIRED_PAYLOAD_KEYS[wire_type] if key not in body]
        if missing:
            raise ValueError(
                f"event '{wire_type}' requires payload key(s): {', '.join(missing)}"
            )
        event = UCPEvent(
            event_type=wire_type,
            block_id=self.block_id,
            payload=body,
            sequence=self._next_sequence(),
            agent=self.agent,
            run_id=self.run_id,
            schema_version=self.schema_version,
        )
        self.events.append(event)
        return event

    def append(self, event: Any) -> UCPEvent:
        """Append an already-built event, renumbering it if it has no sequence.

        Used when relaying events parsed from another producer. Tolerant: an
        unknown event type is accepted here, unlike in `emit`.
        """
        parsed = UCPEvent.from_dict(event)
        if parsed.sequence <= 0:
            parsed.sequence = self._next_sequence()
        self.events.append(parsed)
        return parsed

    def _next_sequence(self) -> int:
        return (self.events[-1].sequence + 1) if self.events else 1

    # -- integrity --------------------------------------------------------

    def validate(self) -> "UEP":
        """Check ordering and terminal-event rules. Returns self for chaining."""
        if not self.block_id.strip():
            raise UEPError("UEP.block_id must not be empty")
        previous = 0
        terminal_at: Optional[int] = None
        for index, event in enumerate(self.events):
            if event.sequence <= previous:
                raise UEPError(
                    f"event sequence must be strictly increasing; "
                    f"event #{index} has sequence {event.sequence} after {previous}"
                )
            previous = event.sequence
            if terminal_at is not None:
                raise UEPError(
                    f"event #{index} ('{event.event_type}') comes after the "
                    f"terminal event at #{terminal_at}"
                )
            if event.is_terminal:
                terminal_at = index
        if self.events and self.events[0].event_type != EventType.BLOCK_STARTED.value:
            raise UEPError(
                "an event stream must open with 'block_started'; "
                f"got '{self.events[0].event_type}'"
            )
        return self

    # -- outcome, fail-closed ---------------------------------------------

    @property
    def outcome(self) -> str:
        """'completed' | 'failed' | 'incomplete'.

        Anything that is not an explicit `block_completed` terminal is NOT a
        success. A process killed mid-run must be indistinguishable from one
        that failed: absence of evidence of success is not evidence of success.
        """
        if not self.events:
            return "incomplete"
        last = self.events[-1]
        if last.event_type == EventType.BLOCK_COMPLETED.value:
            return "completed"
        if last.event_type == EventType.BLOCK_FAILED.value:
            return "failed"
        return "incomplete"

    @property
    def succeeded(self) -> bool:
        """True only for a stream terminated by `block_completed`."""
        return self.outcome == "completed"

    @property
    def is_forward_version(self) -> bool:
        return self.schema_version > EVENT_PROTOCOL_VERSION

    # -- queries ----------------------------------------------------------

    def events_of(self, event_type: Any) -> List[UCPEvent]:
        wire_type = _event_type_value(event_type)
        return [event for event in self.events if event.event_type == wire_type]

    def files_read(self) -> List[str]:
        return self._paths(EventType.FILE_READ)

    def files_written(self) -> List[str]:
        return self._paths(EventType.FILE_WRITTEN)

    def _paths(self, event_type: EventType) -> List[str]:
        seen: List[str] = []
        for event in self.events_of(event_type):
            path = as_text(event.payload.get("path"))
            if path and path not in seen:
                seen.append(path)
        return seen

    def tests_passed(self) -> bool:
        """True when at least one test ran and every test run passed."""
        runs = self.events_of(EventType.TEST_RUN)
        if not runs:
            return False
        return all(bool(event.payload.get("passed")) for event in runs)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return emit_with_extensions(
            {
                "schema_version": self.schema_version,
                "block_id": self.block_id,
                "run_id": self.run_id,
                "ucp_id": self.ucp_id,
                "agent": self.agent,
                "events": [event.to_dict() for event in self.events],
            },
            self.extensions,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "UEP":
        if isinstance(data, UEP):
            return data
        if not isinstance(data, dict):
            raise ValueError(f"UEP payload must be an object, got {type(data).__name__}")
        if not as_text(data.get("block_id")).strip():
            raise ValueError("UEP is missing required field: block_id")
        return cls(
            block_id=data.get("block_id"),
            run_id=as_text(data.get("run_id")),
            ucp_id=as_text(data.get("ucp_id")),
            agent=as_text(data.get("agent")),
            events=list(data.get("events") or []),
            schema_version=coerce_schema_version(
                data.get("schema_version"), EVENT_PROTOCOL_VERSION
            ),
            extensions=split_known(data, _UEP_KNOWN),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "UEP":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"UEP payload is not valid JSON: {exc}") from None
        return cls.from_dict(data)

    def to_ndjson(self) -> str:
        """One JSON object per line -- append-only and truncation resistant."""
        return "\n".join(event.to_json() for event in self.events)

    @classmethod
    def from_ndjson(cls, text: str, block_id: str = "") -> "UEP":
        """Parse an NDJSON stream, skipping lines that cannot be read.

        A corrupt line is skipped rather than fatal: one bad record must not
        blind the whole stream, which is the situation this format exists for.
        """
        events: List[UCPEvent] = []
        for line in (text or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            try:
                events.append(UCPEvent.from_dict(parsed))
            except ValueError:
                continue
        resolved = as_text(block_id) or (events[0].block_id if events else "")
        if not resolved.strip():
            raise ValueError(
                "cannot infer block_id from an empty NDJSON stream; pass block_id"
            )
        stream = cls(block_id=resolved)
        stream.events = events
        if events:
            stream.run_id = stream.run_id or events[0].run_id
            stream.agent = stream.agent or events[0].agent
        return stream
