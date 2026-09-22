"""Shared primitives for the universal protocol: validation, errors, schemas.

This module is a leaf: it imports nothing from this repository, only stdlib.
That is what makes "the core does not import a harness" a statically verifiable
property instead of a review convention.

No I/O anywhere in this package -- UCP and UEP are in-memory objects.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

#: Version of the Context Packet wire format.
CONTEXT_PACKET_VERSION = 1

#: Version of the Event Protocol wire format.
EVENT_PROTOCOL_VERSION = 1

#: Version of the adapter-facing API surface (consumed by F14-02).
ADAPTER_API_VERSION = 1

#: Sentinel meaning "any agent may pick this up".
ANY_AGENT = "any"

_REDACTED = "[REDACTED]"


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class ProtocolError(Exception):
    """Base class for every error raised by the protocol package."""


class UCPSecurityError(ProtocolError):
    """A payload crossing the trust boundary carried something secret.

    The message names the *path* of the offending field and never its value:
    echoing the secret into an exception is the very leak we are preventing.
    """


class UEPError(ProtocolError):
    """An event stream violated the protocol (ordering, terminal events...)."""


# --------------------------------------------------------------------------
# Time / id helpers
# --------------------------------------------------------------------------


def utc_now() -> str:
    """Current UTC time as ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_id(prefix: str) -> str:
    """Time-sortable identifier: <prefix>-20260922T101530-a1b2c3d4."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------
# Coercion helpers
# --------------------------------------------------------------------------


def require_text(value: Any, label: str) -> str:
    """Return a non-blank string or raise ValueError naming the field."""
    if value is None:
        raise ValueError(f"{label} is required and must not be empty")
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"{label} is required and must not be empty")
    return text


def as_text(value: Any, default: str = "") -> str:
    """Best-effort string coercion that never raises."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def as_str_list(value: Any, label: str) -> List[str]:
    """Coerce to a list of strings. A bare string is a bug, not a one-item list."""
    if value is None:
        return []
    if isinstance(value, str):
        raise ValueError(f"{label} must be a list of strings, not a bare string")
    if isinstance(value, dict):
        raise ValueError(f"{label} must be a list of strings, not an object")
    try:
        items = list(value)
    except TypeError:
        raise ValueError(f"{label} must be a list of strings")
    return [as_text(item) for item in items]


def as_dict(value: Any, label: str) -> Dict[str, Any]:
    """Coerce to a plain dict with string keys."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object, got {type(value).__name__}")
    return {as_text(k): v for k, v in value.items()}


def as_optional_int(value: Any, label: str) -> Optional[int]:
    """Optional non-negative integer. None means 'no limit'."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number, got bool")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer, got {value!r}")
    if number < 0:
        raise ValueError(f"{label} must not be negative (got {number})")
    return number


def as_optional_float(value: Any, label: str) -> Optional[float]:
    """Optional non-negative float. None means 'no limit'."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number, got bool")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number, got {value!r}")
    if number < 0:
        raise ValueError(f"{label} must not be negative (got {number})")
    return number


# --------------------------------------------------------------------------
# Versioning
# --------------------------------------------------------------------------


def coerce_schema_version(value: Any, current: int, label: str = "schema_version") -> int:
    """Normalize a declared schema_version.

    Missing -> current (not an error). Malformed or non-positive -> ValueError:
    a broken packet is not the same thing as a packet from the future.
    A version greater than `current` is returned untouched -- deciding what to
    do about it belongs to the consumer, not to the parser.
    """
    if value is None:
        return current
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer, got bool")
    try:
        version = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a positive integer, got {value!r}")
    if version <= 0:
        raise ValueError(f"{label} must be a positive integer, got {version}")
    return version


def split_known(data: Dict[str, Any], known: Tuple[str, ...]) -> Dict[str, Any]:
    """Return the entries of `data` that are not part of the known field set.

    Unknown fields are preserved rather than dropped so that a v1 relay sitting
    between two v2 peers does not destroy data it does not understand.
    """
    extras = {k: v for k, v in data.items() if k not in known and k != "extensions"}
    declared = data.get("extensions")
    if isinstance(declared, dict):
        merged = dict(declared)
        merged.update(extras)
        return merged
    return extras


def emit_with_extensions(
    payload: Dict[str, Any], extensions: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge extensions back into the wire payload.

    Extensions are written first so that known fields always win a collision --
    an unknown key must never be able to shadow a field of the contract.
    """
    out: Dict[str, Any] = dict(extensions or {})
    out.update(payload)
    return out


# --------------------------------------------------------------------------
# Trust boundary: secret scanning
# --------------------------------------------------------------------------

#: Key name tokens that mean "this string is a credential".
#: Matched against the key split on [^a-z0-9]+, so `author` does not match
#: `auth` and `max_tokens` does not match `token`.
_DENY_KEY_TOKENS = frozenset(
    {
        "secret",
        "secrets",
        "password",
        "passwd",
        "pwd",
        "token",
        "credential",
        "credentials",
        "authorization",
        "bearer",
        "privatekey",
        "apikey",
        "accesskey",
        "secretkey",
        "cookie",
        "session",
    }
)

#: Compound key patterns: both tokens present anywhere in the key name.
_DENY_KEY_PAIRS = (
    ("api", "key"),
    ("access", "key"),
    ("private", "key"),
    ("secret", "key"),
    ("auth", "key"),
)

#: Key names that contain a deny token but are known to be safe.
_ALLOW_KEYS = frozenset(
    {
        "token_budget",
        "tokens",
        "max_tokens",
        "context_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "tokens_used",
        "token_count",
        "budget_tokens",
    }
)

#: High-confidence value patterns. False positives are acceptable here;
#: false negatives are not.
_SECRET_VALUE_PATTERNS = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("anthropic-style key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("openai-style key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}")),
    ("github pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    (
        "json web token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    ),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}")),
    (
        "env assignment of a credential",
        re.compile(
            r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*"
            r"(?:SECRET|PASSWORD|PASSWD|TOKEN|API_?KEY|ACCESS_?KEY|CREDENTIALS?)"
            r"[A-Z0-9_]*\s*=\s*\S+"
        ),
    ),
)


@dataclass(frozen=True)
class SecretFinding:
    """Where a secret was found and why it tripped the scanner.

    Deliberately carries no value -- only the location and the rule name.
    """

    path: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - formatting helper
        return f"{self.path} ({self.reason})"


def _key_is_denied(key: str) -> bool:
    lowered = key.lower()
    if lowered in _ALLOW_KEYS:
        return False
    tokens = set(t for t in re.split(r"[^a-z0-9]+", lowered) if t)
    if tokens & _DENY_KEY_TOKENS:
        return True
    joined = "".join(tokens)
    for first, second in _DENY_KEY_PAIRS:
        if first in joined and second in joined and joined != second:
            return True
    return False


def _scan_value(value: str, path: str, findings: List[SecretFinding]) -> None:
    for reason, pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            findings.append(SecretFinding(path, reason))
            return


#: A packet nested deeper than this cannot be scanned reliably, so it is
#: rejected. Well above anything the contract produces (UCP nests 3 deep).
MAX_SCAN_DEPTH = 64


def scan_for_secrets(obj: Any, path: str = "$") -> List[SecretFinding]:
    """Walk `obj` and report every string leaf that looks like a credential.

    Two independent rules (see docs/architecture/protocol.md):
      1. key name denylist -- fires only when the value is a non-empty string,
         so numeric budgets such as `max_tokens` can never trip it;
      2. value pattern matching -- applied to every string leaf, including
         `context_files[].content`, because the realistic leak is a `.env`
         swept in by a glob, not someone typing a key into an `api_key` field.

    Raises ValueError on a cyclic or absurdly deep payload: a payload that
    cannot be fully scanned must be rejected, never waved through.
    """
    findings: List[SecretFinding] = []
    _walk(obj, path, findings, 0, set())
    return findings


def _walk(
    obj: Any,
    path: str,
    findings: List[SecretFinding],
    depth: int,
    seen: set,
) -> None:
    if isinstance(obj, str):
        _scan_value(obj, path, findings)
        return
    if not isinstance(obj, (dict, list, tuple)):
        return  # numbers, bools, None: nothing to scan.

    if depth >= MAX_SCAN_DEPTH:
        raise ValueError(
            f"payload nests deeper than {MAX_SCAN_DEPTH} levels at {path} "
            "and cannot be scanned for secrets"
        )
    marker = id(obj)
    if marker in seen:
        raise ValueError(
            f"payload contains a reference cycle at {path} "
            "and cannot be scanned for secrets"
        )
    seen = seen | {marker}

    if isinstance(obj, dict):
        for key, value in obj.items():
            key_text = as_text(key)
            child = f"{path}.{key_text}" if path else key_text
            if isinstance(value, str) and value.strip() and _key_is_denied(key_text):
                findings.append(SecretFinding(child, "credential-like field name"))
                continue
            _walk(value, child, findings, depth + 1, seen)
        return
    for index, value in enumerate(obj):
        _walk(value, f"{path}[{index}]", findings, depth + 1, seen)


def assert_no_secrets(obj: Any, where: str = "payload") -> None:
    """Fail closed when a payload carries something that must not cross out.

    There is no flag to turn this off. The remedy for a false positive is
    `redact()`, never loosening the protocol.
    """
    findings = scan_for_secrets(obj)
    if not findings:
        return
    locations = ", ".join(sorted(str(f) for f in findings))
    raise UCPSecurityError(
        f"{where} must not carry credentials or secrets; "
        f"offending field(s): {locations}. "
        "Values are intentionally omitted from this message. "
        "Use protocol.redact() to strip them before building the packet."
    )


def redact(obj: Any) -> Any:
    """Return a deep copy of `obj` with every offending string replaced.

    Works on plain data (dicts/lists), not on UCP instances: a UCP carrying a
    secret can never exist, so there is nothing to redact after construction.
    """
    return _redact(obj, False, 0)


def _redact(obj: Any, key_denied: bool, depth: int) -> Any:
    if isinstance(obj, str):
        if key_denied and obj.strip():
            return _REDACTED
        for _reason, pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(obj):
                return _REDACTED
        return obj
    if not isinstance(obj, (dict, list, tuple)):
        return obj
    if depth >= MAX_SCAN_DEPTH:
        raise ValueError(
            f"payload nests deeper than {MAX_SCAN_DEPTH} levels and cannot be redacted"
        )
    if isinstance(obj, dict):
        return {
            key: _redact(value, _key_is_denied(as_text(key)), depth + 1)
            for key, value in obj.items()
        }
    return [_redact(item, False, depth + 1) for item in obj]


# --------------------------------------------------------------------------
# Canonical serialization
# --------------------------------------------------------------------------


def canonical_json(data: Any) -> str:
    """Deterministic JSON: sorted keys, no padding. Same content, same bytes."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_of(data: Any) -> str:
    """sha256 hex of the canonical JSON form of `data`."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# JSON Schemas -- single source of truth, embedded verbatim in docs/
# --------------------------------------------------------------------------

_SCHEMA_BASE = "https://maestro.dev/schemas"

BLOCK_SPEC_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["block_id"],
    "additionalProperties": True,
    "properties": {
        "block_id": {"type": "string", "minLength": 1},
        "title": {"type": "string"},
        "spec_text": {"type": "string"},
        "spec_path": {"type": "string"},
        "complexity": {"type": "string"},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "allowed_paths": {"type": "array", "items": {"type": "string"}},
        "forbidden_actions": {"type": "array", "items": {"type": "string"}},
        "stop_and_ask": {"type": "array", "items": {"type": "string"}},
        "test_command": {"type": "string"},
    },
}

CONTEXT_FILE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["path"],
    "additionalProperties": True,
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "content": {"type": "string"},
        "priority": {"type": "integer"},
        "tokens": {"type": "integer", "minimum": 0},
        "truncated": {"type": "boolean"},
    },
}

MEMORY_ENTRY_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [],
    "additionalProperties": True,
    "properties": {
        "id": {"type": "string"},
        "kind": {"type": "string"},
        "text": {"type": "string"},
        "source": {"type": "string"},
        "score": {"type": "number"},
    },
}

BUDGET_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [],
    "additionalProperties": True,
    "description": "Every limit is optional; null means 'no limit'.",
    "properties": {
        "max_turns": {"type": ["integer", "null"], "minimum": 0},
        "max_tokens": {"type": ["integer", "null"], "minimum": 0},
        "max_cost_usd": {"type": ["number", "null"], "minimum": 0},
        "context_tokens": {"type": ["integer", "null"], "minimum": 0},
        "exploration_files": {"type": ["integer", "null"], "minimum": 0},
        "change_files": {"type": ["integer", "null"], "minimum": 0},
    },
}

HANDOFF_REF_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [],
    "additionalProperties": True,
    "properties": {
        "handoff_id": {"type": "string"},
        "from_agent": {"type": "string"},
        "to_agent": {
            "type": "string",
            "description": "An agent id, or the sentinel 'any'.",
        },
        "context_summary": {"type": "string"},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "files_touched": {"type": "array", "items": {"type": "string"}},
        "checkpoint": {"type": "object"},
    },
}

UCP_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{_SCHEMA_BASE}/ucp-v{CONTEXT_PACKET_VERSION}.json",
    "title": "Universal Context Packet",
    "description": (
        "Data contract handed from any agent to any executor. Carries no "
        "credentials, no raw environment and no user PII."
    ),
    "type": "object",
    "required": ["block_spec"],
    "additionalProperties": True,
    "properties": {
        "schema_version": {"type": "integer", "minimum": 1},
        "ucp_id": {"type": "string"},
        "run_id": {"type": "string"},
        "producer_agent": {"type": "string"},
        "created_at": {
            "type": "string",
            "description": "ISO-8601 UTC with a trailing Z.",
        },
        "block_spec": BLOCK_SPEC_JSON_SCHEMA,
        "conventions": {"type": "object"},
        "context_files": {"type": "array", "items": CONTEXT_FILE_JSON_SCHEMA},
        "memory_entries": {"type": "array", "items": MEMORY_ENTRY_JSON_SCHEMA},
        "budget": BUDGET_JSON_SCHEMA,
        "handoff": {
            "oneOf": [HANDOFF_REF_JSON_SCHEMA, {"type": "null"}],
            "description": "Optional: null when the block is not a resume.",
        },
    },
}

UEP_EVENT_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{_SCHEMA_BASE}/uep-event-v{EVENT_PROTOCOL_VERSION}.json",
    "title": "Universal Event Protocol event",
    "type": "object",
    "required": ["event_type", "block_id"],
    "additionalProperties": True,
    "properties": {
        "schema_version": {"type": "integer", "minimum": 1},
        "event_type": {
            "type": "string",
            "description": (
                "One of the six protocol events. Readers must accept unknown "
                "values from future producers without failing."
            ),
        },
        "block_id": {"type": "string", "minLength": 1},
        "sequence": {"type": "integer", "minimum": 0},
        "timestamp": {"type": "string"},
        "agent": {"type": "string"},
        "run_id": {"type": "string"},
        "event_id": {"type": "string"},
        "payload": {"type": "object"},
    },
}

UEP_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{_SCHEMA_BASE}/uep-v{EVENT_PROTOCOL_VERSION}.json",
    "title": "Universal Event Protocol stream",
    "type": "object",
    "required": ["block_id"],
    "additionalProperties": True,
    "properties": {
        "schema_version": {"type": "integer", "minimum": 1},
        "block_id": {"type": "string", "minLength": 1},
        "run_id": {"type": "string"},
        "ucp_id": {"type": "string"},
        "agent": {"type": "string"},
        "events": {"type": "array", "items": UEP_EVENT_JSON_SCHEMA},
    },
}


def json_schemas() -> Dict[str, Dict[str, Any]]:
    """Every published schema, keyed by short name."""
    return {
        "ucp": UCP_JSON_SCHEMA,
        "uep": UEP_JSON_SCHEMA,
        "uep_event": UEP_EVENT_JSON_SCHEMA,
    }
