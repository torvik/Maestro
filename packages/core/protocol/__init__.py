"""Universal protocol: UCP (data in) and UEP (events out).

The two contracts every adapter -- present and future -- implements:

    Planner / Context Builder / Memory  --UCP-->  any executor
    any executor                        --UEP-->  Evidence / Telemetry / State

This package is a leaf. It imports nothing from this repository, only stdlib,
which is what makes "the core never imports a harness" a statically verifiable
property rather than a review convention. No I/O at import time or anywhere
else: UCP and UEP are in-memory objects.

    from packages.core.protocol import UCPBuilder, UEP, EventType

    packet = UCPBuilder().for_block("BLOCO-EXEMPLO").build()
    stream = UEP(block_id=packet.block_id, ucp_id=packet.ucp_id)
    stream.emit(EventType.BLOCK_STARTED, ucp_digest=packet.digest())
"""

from packages.core.protocol.schema import (
    ADAPTER_API_VERSION,
    ANY_AGENT,
    BUDGET_JSON_SCHEMA,
    BLOCK_SPEC_JSON_SCHEMA,
    CONTEXT_FILE_JSON_SCHEMA,
    CONTEXT_PACKET_VERSION,
    EVENT_PROTOCOL_VERSION,
    HANDOFF_REF_JSON_SCHEMA,
    MEMORY_ENTRY_JSON_SCHEMA,
    ProtocolError,
    SecretFinding,
    UCP_JSON_SCHEMA,
    UEP_EVENT_JSON_SCHEMA,
    UEP_JSON_SCHEMA,
    UCPSecurityError,
    UEPError,
    assert_no_secrets,
    canonical_json,
    digest_of,
    json_schemas,
    redact,
    scan_for_secrets,
    utc_now,
)
from packages.core.protocol.ucp import (
    UCP,
    BlockSpec,
    Budget,
    ContextFile,
    HandoffRef,
    MemoryEntry,
)
from packages.core.protocol.uep import (
    REQUIRED_PAYLOAD_KEYS,
    TERMINAL_EVENT_TYPES,
    UEP,
    EventType,
    UCPEvent,
)
from packages.core.protocol.builder import UCPBuilder

__all__ = [
    # contracts
    "UCP",
    "UEP",
    "UCPEvent",
    "EventType",
    "UCPBuilder",
    # UCP payload types
    "BlockSpec",
    "ContextFile",
    "MemoryEntry",
    "Budget",
    "HandoffRef",
    # errors
    "ProtocolError",
    "UCPSecurityError",
    "UEPError",
    # trust boundary
    "scan_for_secrets",
    "assert_no_secrets",
    "redact",
    "SecretFinding",
    # versions
    "CONTEXT_PACKET_VERSION",
    "EVENT_PROTOCOL_VERSION",
    "ADAPTER_API_VERSION",
    # constants / helpers
    "ANY_AGENT",
    "TERMINAL_EVENT_TYPES",
    "REQUIRED_PAYLOAD_KEYS",
    "canonical_json",
    "digest_of",
    "utc_now",
    # published schemas
    "json_schemas",
    "UCP_JSON_SCHEMA",
    "UEP_JSON_SCHEMA",
    "UEP_EVENT_JSON_SCHEMA",
    "BLOCK_SPEC_JSON_SCHEMA",
    "CONTEXT_FILE_JSON_SCHEMA",
    "MEMORY_ENTRY_JSON_SCHEMA",
    "BUDGET_JSON_SCHEMA",
    "HANDOFF_REF_JSON_SCHEMA",
]
