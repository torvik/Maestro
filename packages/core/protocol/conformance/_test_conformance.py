"""Stdlib tests for the Adapter SDK (F14-02). No pytest.

Run: python packages/core/protocol/conformance/_test_conformance.py
Prints ALL TESTS PASSED and exits 0 on success.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from packages.core.protocol.conformance import (  # noqa: E402
    AdapterManifest,
    AdapterRegistry,
    ConformanceSuite,
    GenericCLIAdapter,
    ValidationError,
)

_FAILURES = []


def check(condition, message):
    if not condition:
        _FAILURES.append(message)


def _valid_manifest_dict():
    return {
        "name": "adapter-exemplo",
        "version": "1.0.0",
        "harness": "cli-exemplo",
        "supported_events": [
            "block_started",
            "file_read",
            "file_written",
            "test_run",
            "block_completed",
            "block_failed",
        ],
        "capabilities": {"shell_execution": True},
    }


def test_T01_valid_manifest_passes():
    manifest = AdapterManifest.from_dict(_valid_manifest_dict())
    check(manifest.name == "adapter-exemplo", "T01: name preserved")
    check(manifest.harness == "cli-exemplo", "T01: harness preserved")
    check(len(manifest.supported_events) == 6, "T01: all 6 events accepted")


def test_T02_missing_required_field_raises():
    data = _valid_manifest_dict()
    del data["harness"]
    try:
        AdapterManifest.from_dict(data)
        _FAILURES.append("T02: expected ValidationError for missing 'harness'")
    except ValidationError:
        pass


def test_T03_registry_register_valid_activates():
    registry = AdapterRegistry()
    registry.register(_valid_manifest_dict())
    check(registry.is_registered("adapter-exemplo"), "T03: adapter is registered")
    check(registry.get("adapter-exemplo") is not None, "T03: get() returns entry")


def test_T04_registry_register_invalid_raises_and_stays_unregistered():
    registry = AdapterRegistry()
    bad = _valid_manifest_dict()
    del bad["capabilities"]
    try:
        registry.register(bad)
        _FAILURES.append("T04: expected ValidationError for missing 'capabilities'")
    except ValidationError:
        pass
    check(
        not registry.is_registered("adapter-exemplo"),
        "T04: invalid manifest must not register anything",
    )
    check(registry.names() == [], "T04: registry stays empty after failed register")


def test_T05_generic_cli_manifest_is_valid():
    adapter = GenericCLIAdapter(name="minha-ferramenta", command=["minha-ferramenta", "run"])
    check(adapter.manifest.harness == "generic-cli", "T05: harness == generic-cli")
    check(adapter.manifest.name == "minha-ferramenta", "T05: name preserved")
    check(len(adapter.manifest.supported_events) == 6, "T05: all 6 events declared")


def test_T06_generic_cli_passes_conformance_suite():
    adapter = GenericCLIAdapter(name="minha-ferramenta", command=["minha-ferramenta", "run"])
    suite = ConformanceSuite(adapter.manifest, adapter)
    results = suite.run()
    check(suite.ok, f"T06: expected ok, got failures: {suite.failures()}")
    check(len(results) == 5, f"T06: expected 5 checks to run, got {len(results)}")


def _integration_manifest_path(name):
    return os.path.join(_REPO_ROOT, "integrations", name, "adapter.manifest.json")


def test_T07_claude_code_manifest_passes_conformance():
    path = _integration_manifest_path("claude-code")
    check(os.path.exists(path), f"T07: manifest file must exist at {path}")
    suite = ConformanceSuite(path)
    suite.run()
    check(suite.ok, f"T07: claude-code manifest failed: {suite.failures()}")


def test_T08_codex_manifest_passes_conformance():
    path = _integration_manifest_path("codex")
    check(os.path.exists(path), f"T08: manifest file must exist at {path}")
    suite = ConformanceSuite(path)
    suite.run()
    check(suite.ok, f"T08: codex manifest failed: {suite.failures()}")


def test_T09_suite_rejects_manifest_without_supported_events():
    data = _valid_manifest_dict()
    data["supported_events"] = []
    suite = ConformanceSuite(data)
    suite.run()
    check(not suite.ok, "T09: manifest with empty supported_events must not be ok")


def test_T10_manifest_from_file_loads_json_from_disk():
    data = _valid_manifest_dict()
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, "adapter.manifest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        manifest = AdapterManifest.from_file(path)
    check(manifest.name == data["name"], "T10: name loaded from disk matches")
    check(
        manifest.supported_events == data["supported_events"],
        "T10: supported_events loaded from disk matches",
    )
    check(
        manifest.capabilities == data["capabilities"],
        "T10: capabilities loaded from disk matches",
    )


# -- extra robustness, following repo convention (see F14-01 T13+) ---------


def test_T11_manifest_direct_construction_missing_field_raises():
    try:
        AdapterManifest(name="x", version="1.0.0", harness="", supported_events=["block_started"])
        _FAILURES.append("T11: expected ValidationError for blank harness")
    except ValidationError:
        pass


def test_T12_manifest_unknown_event_type_raises():
    data = _valid_manifest_dict()
    data["supported_events"] = ["block_started", "not_a_real_event"]
    try:
        AdapterManifest.from_dict(data)
        _FAILURES.append("T12: expected ValidationError for unknown event type")
    except ValidationError:
        pass


def test_T13_generic_cli_build_invocation_uses_test_command():
    from packages.core.protocol import UCPBuilder

    adapter = GenericCLIAdapter(name="minha-ferramenta", command=["minha-ferramenta"])
    ucp = UCPBuilder().for_block("BLOCO-EXEMPLO", test_command="pytest -q").build()
    invocation = adapter.build_invocation(ucp)
    check(invocation[0] == "minha-ferramenta", "T13: base command preserved")
    check("pytest -q" in invocation, "T13: test_command appended")


def test_T14_generic_cli_parse_event_line_tolerant():
    adapter = GenericCLIAdapter(name="minha-ferramenta", command=["minha-ferramenta"])
    check(
        adapter.parse_event_line("not json at all") is None,
        "T14: unrecognizable line returns None, does not raise",
    )
    check(adapter.parse_event_line("") is None, "T14: empty line returns None")
    event = adapter.parse_event_line(
        json.dumps({"event_type": "file_read", "block_id": "BLOCO-EXEMPLO", "payload": {"path": "a.py"}})
    )
    check(event is not None, "T14: valid event line parses")
    check(event.event_type == "file_read", "T14: parsed event_type correct")


def test_T15_validation_error_is_value_error():
    check(issubclass(ValidationError, ValueError), "T15: ValidationError subclasses ValueError")


def main():
    tests = [
        test_T01_valid_manifest_passes,
        test_T02_missing_required_field_raises,
        test_T03_registry_register_valid_activates,
        test_T04_registry_register_invalid_raises_and_stays_unregistered,
        test_T05_generic_cli_manifest_is_valid,
        test_T06_generic_cli_passes_conformance_suite,
        test_T07_claude_code_manifest_passes_conformance,
        test_T08_codex_manifest_passes_conformance,
        test_T09_suite_rejects_manifest_without_supported_events,
        test_T10_manifest_from_file_loads_json_from_disk,
        test_T11_manifest_direct_construction_missing_field_raises,
        test_T12_manifest_unknown_event_type_raises,
        test_T13_generic_cli_build_invocation_uses_test_command,
        test_T14_generic_cli_parse_event_line_tolerant,
        test_T15_validation_error_is_value_error,
    ]
    for test in tests:
        test()

    if _FAILURES:
        print("FAILURES:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        print(f"\n{len(_FAILURES)} check(s) failed.")
        sys.exit(1)

    print("ALL TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
