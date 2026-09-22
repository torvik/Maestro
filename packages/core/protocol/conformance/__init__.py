"""Adapter SDK: manifest, registry, and conformance suite for UCP/UEP.

    from packages.core.protocol.conformance import (
        AdapterManifest, ValidationError,
        AdapterRegistry, RegisteredAdapter,
        ConformanceSuite, ConformanceResult,
        GenericCLIAdapter,
    )

See `plano/specs/F14-02-adapter-sdk.md` for the full contract.
"""

from packages.core.protocol.conformance.manifest import (
    REQUIRED_MANIFEST_FIELDS,
    AdapterManifest,
    ValidationError,
)
from packages.core.protocol.conformance.registry import AdapterRegistry, RegisteredAdapter
from packages.core.protocol.conformance.suite import ConformanceResult, ConformanceSuite
from packages.core.protocol.conformance.generic_cli import GenericCLIAdapter

__all__ = [
    "AdapterManifest",
    "ValidationError",
    "REQUIRED_MANIFEST_FIELDS",
    "AdapterRegistry",
    "RegisteredAdapter",
    "ConformanceSuite",
    "ConformanceResult",
    "GenericCLIAdapter",
]
