"""Adapter manifest: the declarative contract of what an adapter supports.

`adapter.manifest.json` is the one file every adapter -- with or without a
Python object behind it -- must publish to be recognized by the Maestro
registry. See `plano/specs/F14-02-adapter-sdk.md` section 5.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from packages.core.protocol import ADAPTER_API_VERSION, EventType

__all__ = [
    "AdapterManifest",
    "ValidationError",
    "REQUIRED_MANIFEST_FIELDS",
]


class ValidationError(ValueError):
    """Raised when an adapter.manifest.json fails validation.

    Subclasses ValueError so existing `except ValueError` call sites keep
    working; code that wants to be specific can catch ValidationError.
    """


#: The five fields the spec (section 5) requires every manifest to declare.
REQUIRED_MANIFEST_FIELDS = (
    "name",
    "version",
    "harness",
    "supported_events",
    "capabilities",
)

_KNOWN_EVENT_TYPES = frozenset(member.value for member in EventType)

_KNOWN_FIELDS = (
    "name",
    "version",
    "harness",
    "supported_events",
    "capabilities",
    "adapter_api_version",
    "description",
)


@dataclass
class AdapterManifest:
    """Parsed and validated `adapter.manifest.json`.

    All five required fields have empty defaults so that construction never
    raises TypeError for a missing keyword -- validation always raises the
    same `ValidationError`, whether the manifest arrives via direct
    construction, `from_dict`, or `from_file`.
    """

    name: str = ""
    version: str = ""
    harness: str = ""
    supported_events: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    adapter_api_version: int = ADAPTER_API_VERSION
    description: str = ""
    extensions: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _require_nonblank_str(self.name, "name")
        self.version = _require_nonblank_str(self.version, "version")
        self.harness = _require_nonblank_str(self.harness, "harness")

        if not isinstance(self.supported_events, list):
            raise ValidationError(
                f"adapter manifest field 'supported_events' must be a list, "
                f"got {type(self.supported_events).__name__}"
            )
        self.supported_events = [str(item) for item in self.supported_events]
        if not self.supported_events:
            raise ValidationError(
                "adapter manifest field 'supported_events' must not be empty"
            )
        unknown = sorted(
            e for e in self.supported_events if e not in _KNOWN_EVENT_TYPES
        )
        if unknown:
            raise ValidationError(
                f"adapter manifest 'supported_events' contains unknown event "
                f"type(s): {unknown}; expected subset of "
                f"{sorted(_KNOWN_EVENT_TYPES)}"
            )

        if not isinstance(self.capabilities, dict):
            raise ValidationError(
                f"adapter manifest field 'capabilities' must be an object, "
                f"got {type(self.capabilities).__name__}"
            )

        try:
            self.adapter_api_version = int(
                self.adapter_api_version or ADAPTER_API_VERSION
            )
        except (TypeError, ValueError):
            raise ValidationError(
                "adapter manifest field 'adapter_api_version' must be an integer"
            )

        self.description = "" if self.description is None else str(self.description)

        if not isinstance(self.extensions, dict):
            raise ValidationError(
                "adapter manifest field 'extensions' must be an object"
            )

    # -- construction -------------------------------------------------

    @classmethod
    def from_dict(cls, data: Any) -> "AdapterManifest":
        """Parse a raw dict. Raises ValidationError for any structural fault.

        Unlike UCP/UEP (which tolerate unknown fields at every version), a
        manifest is small and locally authored -- a missing required field
        is caught here explicitly, before the friendlier per-field checks in
        `__post_init__` even run, so the error names the exact missing key.
        """
        if not isinstance(data, dict):
            raise ValidationError(
                f"adapter manifest must be an object, got {type(data).__name__}"
            )
        missing = [key for key in REQUIRED_MANIFEST_FIELDS if key not in data]
        if missing:
            raise ValidationError(
                f"adapter manifest missing required field(s): {missing}"
            )
        return cls(
            name=data.get("name"),
            version=data.get("version"),
            harness=data.get("harness"),
            supported_events=list(data.get("supported_events") or []),
            capabilities=dict(data.get("capabilities") or {}),
            adapter_api_version=data.get("adapter_api_version", ADAPTER_API_VERSION),
            description=data.get("description", ""),
            extensions={k: v for k, v in data.items() if k not in _KNOWN_FIELDS},
        )

    @classmethod
    def from_file(cls, path: Any) -> "AdapterManifest":
        """Load and parse an `adapter.manifest.json` from disk."""
        file_path = Path(path)
        try:
            raw = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationError(
                f"cannot read adapter manifest at {file_path}: {exc}"
            ) from None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"adapter manifest at {file_path} is not valid JSON: {exc}"
            ) from None
        return cls.from_dict(data)

    # -- serialization --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(self.extensions)
        out.update(
            {
                "name": self.name,
                "version": self.version,
                "harness": self.harness,
                "supported_events": list(self.supported_events),
                "capabilities": dict(self.capabilities),
                "adapter_api_version": self.adapter_api_version,
                "description": self.description,
            }
        )
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _require_nonblank_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"adapter manifest field '{field_name}' is required and must be "
            f"a non-empty string"
        )
    return value
