"""AdapterRegistry: registers adapters, validating their manifest first.

"Registered" here means "a caller invoked `register()`" -- there is no OS
hook, no filesystem watcher, no discovery scan. See
`plano/specs/F14-02-adapter-sdk.md` section 4 for why that keeps criterion 3
implementable directly, in scope, with no restriction needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from packages.core.protocol.conformance.manifest import AdapterManifest, ValidationError

__all__ = ["AdapterRegistry", "RegisteredAdapter"]


@dataclass
class RegisteredAdapter:
    """A validated manifest, plus the optional Python object behind it."""

    manifest: AdapterManifest
    adapter: Any = None


class AdapterRegistry:
    """In-memory registry of adapters, keyed by `manifest.name`.

    `register()` validates before it activates: the manifest is parsed and
    checked first, and the internal dict is written to only after that
    succeeds. A failed validation leaves the registry byte-for-byte as it
    was -- there is no partial or half-registered adapter.
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, RegisteredAdapter] = {}

    def register(self, manifest: Any, adapter: Any = None) -> AdapterManifest:
        """Validate `manifest`, then activate `adapter` under its name.

        `manifest` may be an `AdapterManifest`, a raw `dict`, or a path
        (`str`/`Path`) to an `adapter.manifest.json`. Raises
        `ValidationError` and registers nothing when the manifest is
        invalid.
        """
        parsed = self._parse(manifest)
        self._adapters[parsed.name] = RegisteredAdapter(manifest=parsed, adapter=adapter)
        return parsed

    @staticmethod
    def _parse(manifest: Any) -> AdapterManifest:
        if isinstance(manifest, AdapterManifest):
            return manifest
        if isinstance(manifest, dict):
            return AdapterManifest.from_dict(manifest)
        if isinstance(manifest, (str, Path)):
            return AdapterManifest.from_file(manifest)
        raise ValidationError(
            f"manifest must be an AdapterManifest, dict, or path; got "
            f"{type(manifest).__name__}"
        )

    def get(self, name: str) -> Optional[RegisteredAdapter]:
        return self._adapters.get(name)

    def is_registered(self, name: str) -> bool:
        return name in self._adapters

    def names(self) -> List[str]:
        return list(self._adapters.keys())

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)
