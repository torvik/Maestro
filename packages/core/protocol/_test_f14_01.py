"""Tests for F14-01 -- Universal Context Packet and Universal Event Protocol.

Stdlib only, no pytest. Run:

    python packages/core/protocol/_test_f14_01.py

Prints ALL TESTS PASSED and exits 0 when the contract holds.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from packages.core.protocol import (  # noqa: E402
    ADAPTER_API_VERSION,
    BLOCK_SPEC_JSON_SCHEMA,
    CONTEXT_PACKET_VERSION,
    EVENT_PROTOCOL_VERSION,
    UCP,
    UCP_JSON_SCHEMA,
    UEP,
    UEP_EVENT_JSON_SCHEMA,
    BlockSpec,
    Budget,
    ContextFile,
    EventType,
    HandoffRef,
    MemoryEntry,
    UCPBuilder,
    UCPEvent,
    UCPSecurityError,
    UEPError,
    redact,
    scan_for_secrets,
)

_FAILURES = []


def check(condition, label):
    if not condition:
        _FAILURES.append(label)
        print(f"  FAIL  {label}")
    return condition


def expect_raises(exc_type, fn, label):
    try:
        fn()
    except exc_type:
        return True
    except Exception as exc:  # noqa: BLE001
        _FAILURES.append(label)
        print(f"  FAIL  {label}: raised {type(exc).__name__} instead of {exc_type.__name__}")
        return False
    _FAILURES.append(label)
    print(f"  FAIL  {label}: did not raise {exc_type.__name__}")
    return False


def expect_no_raise(fn, label):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        _FAILURES.append(label)
        print(f"  FAIL  {label}: raised {type(exc).__name__}: {exc}")
        return None


def sample_ucp():
    return (
        UCPBuilder()
        .for_block(
            "BLOCO-EXEMPLO",
            title="Bloco de exemplo",
            spec_text="Implemente a funcao exemplo().",
            spec_path="plano/specs/BLOCO-EXEMPLO.md",
            complexity="C2",
            acceptance_criteria=["O SISTEMA DEVE expor exemplo()."],
            allowed_paths=["pacote/**"],
            forbidden_actions=["Nao escreva fora de pacote/."],
            stop_and_ask=["Se o schema mudar, pare."],
            test_command="python -c \"print('ok')\"",
        )
        .with_conventions({"language": "python", "style": "stdlib only"})
        .add_context_file("arquivo.py", "def exemplo():\n    return 1\n", tokens=12)
        .add_memory_entry("Evite reescrever arquivo.py inteiro.", kind="procedural")
        .with_budget(max_turns=20, max_tokens=8000, max_cost_usd=1.5)
        .with_run(run_id="R-EXEMPLO", producer_agent="agent-a")
        .build()
    )


# --------------------------------------------------------------------------


def t01_required_fields():
    packet = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"})
    check(packet.schema_version == 1, "T01 schema_version == 1")
    check(CONTEXT_PACKET_VERSION == 1, "T01 CONTEXT_PACKET_VERSION == 1")
    check(packet.block_id == "BLOCO-EXEMPLO", "T01 block_id readable")
    check(packet.conventions == {}, "T01 conventions defaults to empty object")
    check(packet.context_files == [], "T01 context_files defaults to empty list")
    check(packet.memory_entries == [], "T01 memory_entries defaults to empty list")
    check(isinstance(packet.budget, Budget), "T01 budget defaults to a Budget")
    check(packet.handoff is None, "T01 handoff defaults to None")
    check(packet.ucp_id.startswith("U-"), "T01 ucp_id auto-generated")
    check(packet.created_at.endswith("Z"), "T01 created_at is ISO-8601 UTC")


def t02_unknown_field_is_forward_compatible():
    raw = {
        "block_spec": {"block_id": "BLOCO-EXEMPLO", "campo_do_futuro": [1, 2]},
        "um_campo_que_nao_existe": {"nested": "valor"},
    }
    packet = expect_no_raise(lambda: UCP.from_dict(raw), "T02 unknown field must not raise")
    if packet is None:
        return
    check(
        packet.extensions.get("um_campo_que_nao_existe") == {"nested": "valor"},
        "T02 unknown top-level field preserved in extensions",
    )
    check(
        packet.block_spec.extensions.get("campo_do_futuro") == [1, 2],
        "T02 unknown nested field preserved in block_spec.extensions",
    )
    check(
        packet.to_dict().get("um_campo_que_nao_existe") == {"nested": "valor"},
        "T02 unknown field re-emitted at the top level",
    )


def t03_missing_block_spec():
    expect_raises(ValueError, lambda: UCP.from_dict({}), "T03 from_dict without block_spec")
    expect_raises(
        ValueError, lambda: UCP.from_dict({"block_spec": None}), "T03 block_spec=None"
    )
    expect_raises(ValueError, lambda: UCP(block_spec=None), "T03 UCP(block_spec=None)")
    expect_raises(
        ValueError,
        lambda: UCP(block_spec={"block_id": "   "}),
        "T03 blank block_id",
    )
    expect_raises(
        ValueError,
        lambda: UCP(block_spec={"title": "sem id"}),
        "T03 block_spec without block_id",
    )


def t04_round_trip():
    original = sample_ucp()
    original = UCP.from_dict(
        dict(original.to_dict(), handoff={"handoff_id": "H-1", "to_agent": "any"})
    )
    restored = UCP.from_dict(original.to_dict())
    check(restored.to_dict() == original.to_dict(), "T04 dict round-trip is lossless")
    check(restored.block_spec == original.block_spec, "T04 block_spec preserved")
    check(restored.conventions == original.conventions, "T04 conventions preserved")
    check(restored.context_files == original.context_files, "T04 context_files preserved")
    check(restored.memory_entries == original.memory_entries, "T04 memory_entries preserved")
    check(restored.budget == original.budget, "T04 budget preserved")
    check(restored.handoff == original.handoff, "T04 handoff preserved")
    check(restored.ucp_id == original.ucp_id, "T04 ucp_id preserved")
    check(restored.run_id == original.run_id, "T04 run_id preserved")
    check(restored.created_at == original.created_at, "T04 created_at preserved")
    check(UCP.from_json(original.to_json()).to_dict() == original.to_dict(), "T04 json round-trip")


def t05_event_types():
    expected = {
        "block_started",
        "file_read",
        "file_written",
        "test_run",
        "block_completed",
        "block_failed",
    }
    actual = {member.value for member in EventType}
    check(actual == expected, f"T05 EventType has exactly the 6 events (got {sorted(actual)})")
    check(len(EventType) == 6, "T05 EventType has no extra members")
    check(
        set(UEP.supported_event_types()) == expected,
        "T05 supported_event_types matches EventType",
    )


def t06_event_of_each_type():
    payloads = {
        EventType.BLOCK_STARTED: {"ucp_digest": "deadbeef"},
        EventType.FILE_READ: {"path": "arquivo.py"},
        EventType.FILE_WRITTEN: {"path": "arquivo.py"},
        EventType.TEST_RUN: {"command": "python -m unittest", "passed": True},
        EventType.BLOCK_COMPLETED: {"summary": "pronto"},
        EventType.BLOCK_FAILED: {"reason": "teste falhou"},
    }
    for event_type, payload in payloads.items():
        event = UCPEvent(
            event_type=event_type, block_id="BLOCO-EXEMPLO", payload=payload
        )
        check(
            event.schema_version == 1,
            f"T06 {event_type.value} schema_version == 1",
        )
        check(event.is_known_type, f"T06 {event_type.value} is a known type")
        check(event.timestamp.endswith("Z"), f"T06 {event_type.value} timestamp is UTC")
        check(event.event_id.startswith("E-"), f"T06 {event_type.value} event_id generated")
    check(EVENT_PROTOCOL_VERSION == 1, "T06 EVENT_PROTOCOL_VERSION == 1")
    check(ADAPTER_API_VERSION == 1, "T06 ADAPTER_API_VERSION == 1")


def t07_event_unknown_field():
    raw = {
        "event_type": "file_read",
        "block_id": "BLOCO-EXEMPLO",
        "payload": {"path": "arquivo.py", "chave_do_futuro": 7},
        "campo_do_futuro": "valor",
    }
    event = expect_no_raise(
        lambda: UCPEvent.from_dict(raw), "T07 unknown event field must not raise"
    )
    if event is None:
        return
    check(
        event.extensions.get("campo_do_futuro") == "valor",
        "T07 unknown event field preserved in extensions",
    )
    check(
        event.payload.get("chave_do_futuro") == 7,
        "T07 unknown payload key preserved verbatim",
    )
    check(
        UCPEvent.from_dict(event.to_dict()).to_dict() == event.to_dict(),
        "T07 event round-trip is lossless",
    )


def t08_builder_is_harness_agnostic():
    packet = sample_ucp()
    check(isinstance(packet, UCP), "T08 builder produces a UCP")
    check(packet.block_id == "BLOCO-EXEMPLO", "T08 builder set the block")
    check(packet.context_paths() == ["arquivo.py"], "T08 builder collected context files")
    check(packet.total_context_tokens() == 12, "T08 builder preserved token counts")
    check(packet.budget.max_turns == 20, "T08 builder set the budget")
    check(packet.producer_agent == "agent-a", "T08 producer_agent is data, not a type")

    forbidden = ("claude", "codex", "anthropic", "openai", "gemini", "copilot")
    names = set(dir(UCPBuilder)) | set(dir(UCP)) | set(dir(UEP)) | set(dir(UCPEvent))
    names |= set(BLOCK_SPEC_JSON_SCHEMA.get("properties", {}))
    names |= set(UCP_JSON_SCHEMA.get("properties", {}))
    names |= set(UEP_EVENT_JSON_SCHEMA.get("properties", {}))
    for field_ in dataclasses.fields(UCP):
        names.add(field_.name)
    offenders = sorted(
        name for name in names if any(word in name.lower() for word in forbidden)
    )
    check(not offenders, f"T08 no harness name in the public surface (got {offenders})")

    wire = packet.to_json().lower()
    leaked = [word for word in forbidden if word in wire]
    check(not leaked, f"T08 serialized packet names no harness (got {leaked})")


def t09_handoff_is_optional():
    packet = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, handoff=None)
    check(packet.handoff is None, "T09 handoff=None accepted")
    check(packet.to_dict()["handoff"] is None, "T09 handoff serialized as null")
    check(UCP.from_dict(packet.to_dict()).handoff is None, "T09 null handoff round-trips")

    with_handoff = UCP(
        block_spec={"block_id": "BLOCO-EXEMPLO"},
        handoff={"handoff_id": "H-1", "from_agent": "agent-a", "to_agent": "any"},
    )
    check(isinstance(with_handoff.handoff, HandoffRef), "T09 handoff parsed into HandoffRef")
    check(
        with_handoff.handoff.addressed_to("agent-b"),
        "T09 to_agent='any' is claimable by any agent",
    )


def t10_schema_version_paths():
    base = {"block_spec": {"block_id": "BLOCO-EXEMPLO"}}

    current = UCP.from_dict(dict(base, schema_version=1))
    check(current.schema_version == 1, "T10 v1 parsed as v1")
    check(not current.is_forward_version, "T10 v1 is not a forward version")

    future = expect_no_raise(
        lambda: UCP.from_dict(
            dict(base, schema_version=2, recurso_da_v2={"flag": True})
        ),
        "T10 future schema_version must not raise",
    )
    if future is not None:
        check(future.schema_version == 2, "T10 declared future version preserved")
        check(future.is_forward_version, "T10 is_forward_version True for v2")
        check(
            future.extensions.get("recurso_da_v2") == {"flag": True},
            "T10 v2-only field preserved in extensions",
        )
        check(future.block_id == "BLOCO-EXEMPLO", "T10 known fields still parsed from v2")
        check(
            current.block_spec == future.block_spec,
            "T10 same block_spec across versions",
        )

    check(
        UCP.from_dict(base).schema_version == 1,
        "T10 missing schema_version defaults to current",
    )
    expect_raises(
        ValueError,
        lambda: UCP.from_dict(dict(base, schema_version="abc")),
        "T10 malformed schema_version",
    )
    expect_raises(
        ValueError,
        lambda: UCP.from_dict(dict(base, schema_version=0)),
        "T10 non-positive schema_version",
    )


def t11_no_harness_imports():
    """The package must be a leaf: stdlib only, no repository imports."""
    forbidden = ("claude", "codex", "anthropic", "openai", "gemini", "copilot")
    modules = sorted(
        name
        for name in os.listdir(_HERE)
        if name.endswith(".py") and not name.startswith("_test")
    )
    check(len(modules) >= 5, f"T11 found the package modules (got {modules})")

    for module_name in modules:
        path = os.path.join(_HERE, module_name)
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imported.append("." * node.level + (node.module or ""))
                else:
                    imported.append(node.module or "")
        for name in imported:
            lowered = name.lower()
            check(
                not any(word in lowered for word in forbidden),
                f"T11 {module_name} imports no harness package (got {name})",
            )
            is_repo_import = name.startswith("packages") or name.startswith(".")
            if is_repo_import:
                check(
                    name.startswith("packages.core.protocol"),
                    f"T11 {module_name} imports nothing from the repo "
                    f"outside packages.core.protocol (got {name})",
                )

    # Ancestor packages are loaded by Python itself when importing a submodule;
    # they are not dependencies. Everything else would be.
    ancestors = {"packages", "packages.core"}
    loaded = sorted(
        name
        for name in sys.modules
        if name.split(".")[0] == "packages"
        and name not in ancestors
        and not name.startswith("packages.core.protocol")
    )
    check(not loaded, f"T11 importing the protocol loads no other repo package (got {loaded})")
    for ancestor in sorted(ancestors):
        module = sys.modules.get(ancestor)
        source = getattr(module, "__file__", None)
        if not source:
            continue
        with open(source, "r", encoding="utf-8") as handle:
            body = ast.parse(handle.read(), filename=source).body
        check(
            not body,
            f"T11 ancestor package {ancestor} stays empty (it is loaded implicitly)",
        )


def t12_budget_is_all_optional():
    empty = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, budget={})
    check(empty.budget.max_turns is None, "T12 max_turns optional")
    check(empty.budget.max_tokens is None, "T12 max_tokens optional")
    check(empty.budget.max_cost_usd is None, "T12 max_cost_usd optional")

    full = UCP(
        block_spec={"block_id": "BLOCO-EXEMPLO"},
        budget={"max_turns": 10, "max_tokens": 8000, "max_cost_usd": 2.5},
    )
    check(full.budget.max_turns == 10, "T12 max_turns accepted from dict")
    check(full.budget.max_tokens == 8000, "T12 max_tokens accepted from dict")
    check(abs(full.budget.max_cost_usd - 2.5) < 1e-9, "T12 max_cost_usd accepted from dict")

    partial = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, budget={"max_turns": 3})
    check(partial.budget.max_turns == 3, "T12 partial budget keeps the given limit")
    check(partial.budget.max_tokens is None, "T12 partial budget leaves the rest unset")

    extra = Budget.from_dict({"max_turns": 1, "limite_do_futuro": 9})
    check(extra.extensions.get("limite_do_futuro") == 9, "T12 unknown budget key preserved")
    check(
        Budget.from_dict(extra.to_dict()) == extra,
        "T12 budget round-trip with unknown key",
    )


def t13_json_schema_matches_dataclasses():
    pairs = (
        (UCP_JSON_SCHEMA, UCP, "UCP"),
        (BLOCK_SPEC_JSON_SCHEMA, BlockSpec, "BlockSpec"),
        (UEP_EVENT_JSON_SCHEMA, UCPEvent, "UCPEvent"),
    )
    for schema, klass, label in pairs:
        names = {f.name for f in dataclasses.fields(klass)}
        for required in schema.get("required", []):
            check(required in names, f"T13 {label} has the required field '{required}'")
        for prop in schema.get("properties", {}):
            check(prop in names, f"T13 {label} declares schema property '{prop}'")
        check(
            schema.get("additionalProperties") is True,
            f"T13 {label} schema allows unknown fields (forward compatibility)",
        )
    for name in ("block_spec", "conventions", "context_files", "memory_entries",
                 "budget", "handoff"):
        check(
            name in UCP_JSON_SCHEMA["properties"],
            f"T13 UCP schema publishes '{name}'",
        )


def t14_secret_in_conventions():
    def build():
        return UCP(
            block_spec={"block_id": "BLOCO-EXEMPLO"},
            conventions={"api_key": "valor-super-secreto-que-nao-pode-vazar"},
        )

    expect_raises(UCPSecurityError, build, "T14 api_key in conventions is rejected")
    try:
        build()
    except UCPSecurityError as exc:
        message = str(exc)
        check(
            "valor-super-secreto-que-nao-pode-vazar" not in message,
            "T14 the secret value never appears in the error message",
        )
        check("conventions.api_key" in message, "T14 the error names the offending path")


def t15_env_file_in_context():
    env_body = "ANTHROPIC_API_KEY=sk-ant-abcdefghijklmnopqrstuvwxyz0123456789\n"

    expect_raises(
        UCPSecurityError,
        lambda: UCPBuilder()
        .for_block("BLOCO-EXEMPLO")
        .add_context_file(".env", env_body)
        .build(),
        "T15 .env content in context_files is rejected",
    )

    findings = scan_for_secrets({"context_files": [{"path": ".env", "content": env_body}]})
    check(findings, "T15 scanner reports a finding")
    check(
        all("sk-ant" not in finding.path for finding in findings),
        "T15 findings carry a path, never a value",
    )

    raw = {
        "block_spec": {"block_id": "BLOCO-EXEMPLO"},
        "context_files": [{"path": ".env", "content": env_body}],
    }
    cleaned = expect_no_raise(
        lambda: UCP.from_dict(redact(raw)), "T15 redact() makes the packet acceptable"
    )
    if cleaned is not None:
        check(
            cleaned.context_files[0].content == "[REDACTED]",
            "T15 the offending value was replaced",
        )
        check(cleaned.context_files[0].path == ".env", "T15 redact keeps non-secret data")


def t16_no_false_positives():
    packet = expect_no_raise(
        lambda: UCP(
            block_spec={"block_id": "BLOCO-EXEMPLO"},
            conventions={
                "author": "nome-do-dono",
                "authors": ["a", "b"],
                "keyword": "protocolo",
                "token_count": 42,
                "notes": "Use tokens com parcimonia; o campo max_tokens limita o gasto.",
            },
            budget={"max_turns": 20, "max_tokens": 8000, "context_tokens": 4000},
            context_files=[
                {"path": "arquivo.py", "content": "def exemplo():\n    return 'sk-' \n"}
            ],
        ),
        "T16 ordinary content must not trip the scanner",
    )
    if packet is not None:
        check(packet.budget.max_tokens == 8000, "T16 max_tokens survived the scanner")
        check(
            packet.conventions["author"] == "nome-do-dono",
            "T16 'author' is not treated as 'auth'",
        )
    check(not scan_for_secrets({"max_tokens": 8000}), "T16 numeric max_tokens is clean")
    check(not scan_for_secrets({"author": "nome"}), "T16 author key is clean")
    check(scan_for_secrets({"password": "alguma-coisa"}), "T16 password key is caught")


def t17_incomplete_stream_is_not_success():
    stream = UEP(block_id="BLOCO-EXEMPLO", run_id="R-EXEMPLO", agent="agent-a")
    check(stream.outcome == "incomplete", "T17 empty stream is incomplete")
    check(stream.succeeded is False, "T17 empty stream did not succeed")

    stream.emit(EventType.BLOCK_STARTED, ucp_digest="deadbeef")
    stream.emit(EventType.FILE_READ, path="arquivo.py")
    stream.emit(EventType.FILE_WRITTEN, path="arquivo.py")
    check(stream.outcome == "incomplete", "T17 stream without terminal is incomplete")
    check(stream.succeeded is False, "T17 stream without terminal did not succeed")

    failed = UEP.from_dict(stream.to_dict())
    failed.emit(EventType.BLOCK_FAILED, reason="processo encerrado")
    check(failed.outcome == "failed", "T17 block_failed terminal yields 'failed'")
    check(failed.succeeded is False, "T17 failed stream did not succeed")

    done = UEP.from_dict(stream.to_dict())
    done.emit(EventType.BLOCK_COMPLETED, summary="pronto")
    check(done.outcome == "completed", "T17 block_completed terminal yields 'completed'")
    check(done.succeeded is True, "T17 completed stream succeeded")
    check(done.files_written() == ["arquivo.py"], "T17 files_written derived from events")
    check(done.files_read() == ["arquivo.py"], "T17 files_read derived from events")


def t18_emit_requires_payload_keys():
    stream = UEP(block_id="BLOCO-EXEMPLO")
    expect_raises(
        ValueError, lambda: stream.emit(EventType.FILE_READ), "T18 file_read without path"
    )
    expect_raises(
        ValueError,
        lambda: stream.emit(EventType.FILE_WRITTEN, {}),
        "T18 file_written without path",
    )
    expect_raises(
        ValueError,
        lambda: stream.emit(EventType.TEST_RUN, command="python -m unittest"),
        "T18 test_run without 'passed'",
    )
    expect_raises(
        ValueError, lambda: stream.emit(EventType.BLOCK_FAILED), "T18 block_failed without reason"
    )
    expect_raises(
        ValueError,
        lambda: stream.emit("evento_do_futuro", {"x": 1}),
        "T18 emitting an unknown event type is strict",
    )
    check(not stream.events, "T18 no event was appended by the failed emissions")
    expect_no_raise(
        lambda: stream.emit(EventType.BLOCK_STARTED), "T18 block_started needs no payload"
    )


def t19_reader_accepts_unknown_event_type():
    raw = {"event_type": "evento_do_futuro", "block_id": "BLOCO-EXEMPLO", "sequence": 2}
    event = expect_no_raise(
        lambda: UCPEvent.from_dict(raw), "T19 unknown event_type must not raise on read"
    )
    if event is None:
        return
    check(event.is_known_type is False, "T19 unknown event type flagged, not rejected")
    check(event.event_type == "evento_do_futuro", "T19 raw event type preserved")
    check(event.is_terminal is False, "T19 unknown type is not terminal")

    stream = UEP(block_id="BLOCO-EXEMPLO")
    stream.emit(EventType.BLOCK_STARTED)
    relayed = expect_no_raise(
        lambda: stream.append(raw), "T19 append() relays an unknown event type"
    )
    if relayed is not None:
        check(relayed.sequence == 2, "T19 relayed event keeps its own sequence")
    check(stream.outcome == "incomplete", "T19 unknown trailing event is not success")


def t20_ndjson_round_trip():
    stream = UEP(block_id="BLOCO-EXEMPLO", run_id="R-EXEMPLO", agent="agent-a")
    stream.emit(EventType.BLOCK_STARTED, ucp_digest="deadbeef")
    stream.emit(EventType.FILE_WRITTEN, path="arquivo.py", bytes=120)
    stream.emit(EventType.TEST_RUN, command="python -m unittest", passed=True)
    stream.emit(EventType.BLOCK_COMPLETED, summary="pronto")

    text = stream.to_ndjson()
    check(len(text.splitlines()) == 4, "T20 one line per event")

    restored = UEP.from_ndjson(text)
    check(
        [e.to_dict() for e in restored.events] == [e.to_dict() for e in stream.events],
        "T20 NDJSON round-trip preserves every event",
    )
    check(restored.block_id == "BLOCO-EXEMPLO", "T20 block_id inferred from the stream")
    check(restored.succeeded is True, "T20 outcome survives the round-trip")

    lines = text.splitlines()
    corrupted = "\n".join([lines[0], "{nao e json", "", lines[2], lines[3]])
    salvaged = expect_no_raise(
        lambda: UEP.from_ndjson(corrupted, block_id="BLOCO-EXEMPLO"),
        "T20 a corrupt line must not break the parse",
    )
    if salvaged is not None:
        check(len(salvaged.events) == 3, "T20 corrupt line skipped, others preserved")
        check(salvaged.succeeded is True, "T20 salvaged stream keeps its terminal event")

    check(
        UEP.from_json(stream.to_json()).to_dict() == stream.to_dict(),
        "T20 UEP json round-trip",
    )


def t21_sequence_and_validate():
    stream = UEP(block_id="BLOCO-EXEMPLO")
    first = stream.emit(EventType.BLOCK_STARTED)
    second = stream.emit(EventType.FILE_READ, path="arquivo.py")
    third = stream.emit(EventType.BLOCK_COMPLETED)
    check([first.sequence, second.sequence, third.sequence] == [1, 2, 3], "T21 sequence starts at 1")
    expect_no_raise(stream.validate, "T21 a well-formed stream validates")

    out_of_order = UEP.from_dict(stream.to_dict())
    out_of_order.events[1].sequence = 1
    expect_raises(UEPError, out_of_order.validate, "T21 non-increasing sequence is rejected")

    after_terminal = UEP(block_id="BLOCO-EXEMPLO")
    after_terminal.emit(EventType.BLOCK_STARTED)
    after_terminal.emit(EventType.BLOCK_COMPLETED)
    after_terminal.events.append(
        UCPEvent(event_type=EventType.FILE_READ, block_id="BLOCO-EXEMPLO",
                 payload={"path": "arquivo.py"}, sequence=3)
    )
    expect_raises(UEPError, after_terminal.validate, "T21 event after the terminal is rejected")

    two_terminals = UEP(block_id="BLOCO-EXEMPLO")
    two_terminals.emit(EventType.BLOCK_STARTED)
    two_terminals.emit(EventType.BLOCK_FAILED, reason="erro")
    two_terminals.emit(EventType.BLOCK_COMPLETED)
    expect_raises(UEPError, two_terminals.validate, "T21 a second terminal is rejected")

    bad_open = UEP(block_id="BLOCO-EXEMPLO")
    bad_open.append(
        UCPEvent(event_type=EventType.FILE_READ, block_id="BLOCO-EXEMPLO",
                 payload={"path": "arquivo.py"})
    )
    expect_raises(UEPError, bad_open.validate, "T21 stream not opening with block_started")

    expect_raises(ValueError, lambda: UEP(block_id="  "), "T21 blank block_id is rejected")
    expect_raises(
        ValueError, lambda: UEP.from_dict({"run_id": "R"}), "T21 UEP without block_id"
    )


def t22_digest_is_deterministic():
    a = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, conventions={"language": "python"})
    b = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, conventions={"language": "python"})
    check(a.digest() == b.digest(), "T22 same content yields the same digest")
    check(a.ucp_id != b.ucp_id, "T22 identity differs even when content matches")

    c = UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, conventions={"language": "rust"})
    check(a.digest() != c.digest(), "T22 different content yields a different digest")
    check(len(a.digest()) == 64, "T22 digest is a sha256 hex string")
    check(
        UCP.from_dict(a.to_dict()).digest() == a.digest(),
        "T22 digest survives a round-trip",
    )


def t23_negative_budget_is_rejected():
    expect_raises(
        ValueError,
        lambda: UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, budget={"max_turns": -1}),
        "T23 negative max_turns",
    )
    expect_raises(
        ValueError,
        lambda: Budget(max_tokens=-5),
        "T23 negative max_tokens",
    )
    expect_raises(
        ValueError,
        lambda: Budget(max_cost_usd=-0.01),
        "T23 negative max_cost_usd",
    )
    expect_raises(
        ValueError,
        lambda: Budget.from_dict({"max_turns": "muitos"}),
        "T23 non-numeric budget value",
    )
    expect_raises(
        ValueError,
        lambda: ContextFile(path="   "),
        "T23 context file without a path",
    )
    expect_raises(
        ValueError,
        lambda: UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, context_files="arquivo.py"),
        "T23 context_files must be a list",
    )
    entry = MemoryEntry.from_dict("uma lembranca")
    check(entry.text == "uma lembranca", "T23 a bare string is accepted as a memory entry")


def t24_unscannable_payload_is_rejected():
    """Found in red-team: a payload the scanner cannot finish must be refused,
    with a typed error -- never waved through and never a bare RecursionError."""
    cyclic = {"block_id": "BLOCO-EXEMPLO"}
    cyclic["self"] = cyclic
    expect_raises(
        ValueError,
        lambda: UCP(block_spec=cyclic),
        "T24 reference cycle is rejected with ValueError",
    )
    expect_raises(
        ValueError, lambda: scan_for_secrets(cyclic), "T24 scanner rejects a cycle"
    )
    expect_raises(ValueError, lambda: redact(cyclic), "T24 redact rejects a cycle")

    deep = current = {}
    for _ in range(200):
        current["n"] = {}
        current = current["n"]
    expect_raises(
        ValueError,
        lambda: UCP(block_spec={"block_id": "BLOCO-EXEMPLO"}, conventions=deep),
        "T24 excessive nesting is rejected",
    )

    shallow = {"a": {"b": {"c": [{"d": "valor"}]}}}
    check(scan_for_secrets(shallow) == [], "T24 ordinary nesting still scans clean")

    # Extensions must never be able to shadow a field of the contract.
    hijack = UCP.from_dict(
        {
            "block_spec": {"block_id": "BLOCO-EXEMPLO"},
            "extensions": {"block_spec": "SEQUESTRADO", "extra": 1},
        }
    )
    check(
        hijack.to_dict()["block_spec"]["block_id"] == "BLOCO-EXEMPLO",
        "T24 an extension cannot shadow a known field",
    )
    check(hijack.extensions.get("extra") == 1, "T24 genuine extension preserved")


TESTS = (
    ("T01", t01_required_fields),
    ("T02", t02_unknown_field_is_forward_compatible),
    ("T03", t03_missing_block_spec),
    ("T04", t04_round_trip),
    ("T05", t05_event_types),
    ("T06", t06_event_of_each_type),
    ("T07", t07_event_unknown_field),
    ("T08", t08_builder_is_harness_agnostic),
    ("T09", t09_handoff_is_optional),
    ("T10", t10_schema_version_paths),
    ("T11", t11_no_harness_imports),
    ("T12", t12_budget_is_all_optional),
    ("T13", t13_json_schema_matches_dataclasses),
    ("T14", t14_secret_in_conventions),
    ("T15", t15_env_file_in_context),
    ("T16", t16_no_false_positives),
    ("T17", t17_incomplete_stream_is_not_success),
    ("T18", t18_emit_requires_payload_keys),
    ("T19", t19_reader_accepts_unknown_event_type),
    ("T20", t20_ndjson_round_trip),
    ("T21", t21_sequence_and_validate),
    ("T22", t22_digest_is_deterministic),
    ("T23", t23_negative_budget_is_rejected),
    ("T24", t24_unscannable_payload_is_rejected),
)


def main() -> int:
    for name, fn in TESTS:
        print(f"{name} {fn.__name__}")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            _FAILURES.append(f"{name} raised {type(exc).__name__}: {exc}")
            print(f"  ERROR {type(exc).__name__}: {exc}")
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILURE(S):")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
