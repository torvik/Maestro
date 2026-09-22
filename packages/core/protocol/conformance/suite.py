"""Conformance suite: what any adapter runs to prove UCP/UEP compatibility.

Manifest-level checks run against any `AdapterManifest` (an adapter with no
Python object, like `claude-code` or `codex` today, still gets full manifest
coverage). Runtime checks additionally run when an adapter object is
supplied, using only the two duck-typed methods any adapter is expected to
expose: `build_invocation(ucp)` and `parse_event_line(line)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from packages.core.protocol import EventType, UCPBuilder, UCPEvent
from packages.core.protocol.conformance.manifest import AdapterManifest, ValidationError

__all__ = ["ConformanceResult", "ConformanceSuite"]

_KNOWN_EVENT_TYPES = frozenset(member.value for member in EventType)

#: Placeholder block id used to build a throwaway UCP for runtime checks.
#: Never a real business identifier -- see F14-01 section 3 (trust boundary)
#: and the "Não faça" list in this bloco's spec.
_SAMPLE_BLOCK_ID = "BLOCO-CONFORMANCE"


@dataclass
class ConformanceResult:
    """Outcome of one check. `detail` is empty on success."""

    name: str
    passed: bool
    detail: str = ""


class ConformanceSuite:
    """Runs every check an adapter must pass to be UCP/UEP compatible."""

    def __init__(self, manifest: Any, adapter: Any = None) -> None:
        self._raw_manifest = manifest
        self._adapter = adapter
        self._manifest: Optional[AdapterManifest] = None
        self._results: List[ConformanceResult] = []

    def run(self) -> List[ConformanceResult]:
        results: List[ConformanceResult] = [
            self._run_check("manifest_parses", self._check_manifest_parses)
        ]

        if self._manifest is not None:
            results.append(
                self._run_check(
                    "supported_events_valid", self._check_supported_events
                )
            )
            results.append(
                self._run_check("capabilities_is_object", self._check_capabilities)
            )

        if self._adapter is not None and self._manifest is not None:
            results.append(
                self._run_check(
                    "adapter_builds_invocation", self._check_build_invocation
                )
            )
            results.append(
                self._run_check(
                    "adapter_parses_event_line", self._check_parse_event_line
                )
            )

        self._results = results
        return results

    @property
    def ok(self) -> bool:
        return bool(self._results) and all(r.passed for r in self._results)

    def failures(self) -> List[ConformanceResult]:
        return [r for r in self._results if not r.passed]

    # -- checks -----------------------------------------------------------

    def _run_check(self, name: str, fn: Any) -> ConformanceResult:
        try:
            fn()
            return ConformanceResult(name=name, passed=True)
        except Exception as exc:  # noqa: BLE001 - conformance must never crash
            return ConformanceResult(name=name, passed=False, detail=str(exc))

    def _check_manifest_parses(self) -> None:
        raw = self._raw_manifest
        if isinstance(raw, AdapterManifest):
            self._manifest = raw
            return
        if isinstance(raw, dict):
            self._manifest = AdapterManifest.from_dict(raw)
            return
        if isinstance(raw, str) or hasattr(raw, "__fspath__"):
            self._manifest = AdapterManifest.from_file(raw)
            return
        raise ValidationError(f"unsupported manifest type: {type(raw).__name__}")

    def _check_supported_events(self) -> None:
        events = self._manifest.supported_events
        if not events:
            raise ValidationError("manifest.supported_events must not be empty")
        unknown = sorted(e for e in events if e not in _KNOWN_EVENT_TYPES)
        if unknown:
            raise ValidationError(
                f"manifest.supported_events has unknown type(s): {unknown}"
            )

    def _check_capabilities(self) -> None:
        if not isinstance(self._manifest.capabilities, dict):
            raise ValidationError("manifest.capabilities must be an object")

    def _check_build_invocation(self) -> None:
        ucp = (
            UCPBuilder()
            .for_block(_SAMPLE_BLOCK_ID, test_command="true")
            .build()
        )
        invocation = self._adapter.build_invocation(ucp)
        if not isinstance(invocation, (list, tuple)) or not invocation:
            raise ValidationError(
                "adapter.build_invocation(ucp) must return a non-empty list"
            )

    def _check_parse_event_line(self) -> None:
        sample = (
            '{"event_type": "block_started", "block_id": "%s"}' % _SAMPLE_BLOCK_ID
        )
        event = self._adapter.parse_event_line(sample)
        if event is not None and not isinstance(event, UCPEvent):
            raise ValidationError(
                "adapter.parse_event_line() must return a UCPEvent or None"
            )
        not_an_event = self._adapter.parse_event_line("this is not json")
        if not_an_event is not None and not isinstance(not_an_event, UCPEvent):
            raise ValidationError(
                "adapter.parse_event_line() must return None for an "
                "unrecognizable line, never raise or return garbage"
            )
