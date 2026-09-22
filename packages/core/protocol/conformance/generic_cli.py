"""GenericCLIAdapter: universal adapter for any command-line tool.

For a harness with no dedicated adapter, wrapping the tool's command in
`GenericCLIAdapter` is enough to get a valid manifest and to pass the
conformance suite -- no bespoke adapter class required. It does not spawn a
subprocess (out of scope for this bloco, see
`plano/specs/F14-02-adapter-sdk.md` section 3): it only translates a UCP into
an argv list and best-effort parses UEP event lines.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from packages.core.protocol import UCP, EventType, UCPEvent
from packages.core.protocol.conformance.manifest import AdapterManifest

__all__ = ["GenericCLIAdapter"]

_ALL_EVENT_TYPES = [member.value for member in EventType]


class GenericCLIAdapter:
    """Wraps a base command so any CLI tool can act as a Maestro adapter."""

    def __init__(
        self,
        name: str,
        command: List[str],
        *,
        version: str = "1.0.0",
        capabilities: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.command = list(command)
        self.manifest = AdapterManifest(
            name=name,
            version=version,
            harness="generic-cli",
            supported_events=list(_ALL_EVENT_TYPES),
            capabilities=dict(
                capabilities
                if capabilities is not None
                else {
                    "streaming_events": False,
                    "structured_output": False,
                    "shell_execution": True,
                }
            ),
            description=description or f"Generic CLI adapter wrapping '{name}'.",
        )

    # -- adapter protocol (see spec section 6) -----------------------------

    def build_invocation(self, ucp: UCP) -> List[str]:
        """Complete the base command with the block's test_command, if any.

        Never inspects harness-specific state: everything it reads comes
        from the UCP contract (`block_spec.test_command`), so this method
        works the same for any command passed at construction.
        """
        invocation = list(self.command)
        test_command = getattr(ucp.block_spec, "test_command", "") or ""
        if test_command.strip():
            invocation.append(test_command)
        return invocation

    def parse_event_line(self, line: str) -> Optional[UCPEvent]:
        """Best-effort parse of one line of CLI output as a UCPEvent.

        Returns None for anything that is not a JSON object shaped like a
        UEP event -- a generic CLI that does not speak the protocol simply
        produces no events, it never crashes the adapter.
        """
        stripped = (line or "").strip()
        if not stripped:
            return None
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        try:
            return UCPEvent.from_dict(data)
        except ValueError:
            return None
