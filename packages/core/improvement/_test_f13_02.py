"""Tests for F13-02 -- ProposalEngine, approval/eval gate and audit trail.

Stdlib only, no pytest. Real filesystem via tempfile.mkdtemp(), no mocks of
the filesystem. Every open() uses a context manager: on Windows an unclosed
handle blocks the cleanup of the temp directory.

Run:  python packages/core/improvement/_test_f13_02.py
"""

from __future__ import annotations

import ast
import builtins
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from packages.core.improvement import (  # noqa: E402
    ApprovalPolicy,
    AuditTrail,
    EvalGateError,
    EvalResult,
    Evidence,
    InvalidTransitionError,
    Proposal,
    ProposalEngine,
    ProposalNotFoundError,
    ProposalStatus,
    TargetType,
)

# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------

_FAILURES = []
_RUN = 0


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_raises(exc_type, fn, message):
    try:
        fn()
    except exc_type:
        return
    except Exception as err:  # noqa: BLE001
        raise AssertionError(
            f"{message}: expected {exc_type.__name__}, got "
            f"{type(err).__name__}: {err}"
        )
    raise AssertionError(f"{message}: expected {exc_type.__name__}, nothing raised")


def run(name, fn):
    global _RUN
    _RUN += 1
    workdir = tempfile.mkdtemp(prefix="f13_02_")
    try:
        fn(Path(workdir))
        print(f"  ok   {name}")
    except Exception:  # noqa: BLE001
        _FAILURES.append(name)
        print(f"  FAIL {name}")
        traceback.print_exc()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

BASE = dict(
    problem="Blocos falham por spec ausente antes da execucao.",
    improvement="Validar a existencia da spec no preflight do bloco.",
    estimated_impact="Elimina o modo de falha mais comum da fila atual.",
)


def make_proposal(engine, **overrides):
    fields = dict(BASE)
    fields["evidence"] = [
        Evidence(block_id="X1-01", error_type="spec_ausente"),
        Evidence(block_id="X1-02", error_type="spec_ausente"),
    ]
    fields["target_type"] = TargetType.GOTCHA
    fields.update(overrides)
    return engine.create(**fields)


def history(*pairs):
    return [
        {"block_id": bid, "error_type": etype, "detail": "", "timestamp": ""}
        for bid, etype in pairs
    ]


def audit_events(engine, proposal_id):
    return [e.get("event") for e in engine.audit.for_proposal(proposal_id)]


# --------------------------------------------------------------------------
# T01 -- create() persists a pending proposal plus sidecar
# --------------------------------------------------------------------------


def t01_create(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)

    check(proposal.status is ProposalStatus.PENDING, "new proposal must be pending")
    check(proposal.created_at.endswith("Z"), "created_at must be ISO-8601 UTC with Z")

    json_path = root / ".maestro" / "proposals" / f"{proposal.id}.json"
    md_path = root / ".maestro" / "proposals" / f"{proposal.id}.md"
    check(json_path.is_file(), f"canonical json missing: {json_path}")
    check(md_path.is_file(), f"sidecar markdown missing: {md_path}")

    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    check(data["status"] == "pending", "persisted status must be pending")
    check(data["problem"] == BASE["problem"], "problem must round-trip")
    check(
        [e["block_id"] for e in data["evidence"]] == ["X1-01", "X1-02"],
        "evidence block ids must round-trip",
    )
    check(data["estimated_impact"] == BASE["estimated_impact"], "impact must persist")

    with open(md_path, "r", encoding="utf-8") as handle:
        sidecar = handle.read()
    check(proposal.id in sidecar, "sidecar must name the proposal")
    check("X1-01" in sidecar, "sidecar must list the evidence")

    # No temp leftovers from the atomic write.
    leftovers = [p.name for p in (root / ".maestro" / "proposals").iterdir() if ".tmp-" in p.name]
    check(not leftovers, f"atomic write left temp files behind: {leftovers}")

    # Timestamped id satisfies the "<timestamp>.md" requirement.
    check(proposal.id.startswith("P-"), "proposal id must start with P-")
    check(len(proposal.id.split("-")) == 3, "id must be P-<timestamp>-<hex>")


# --------------------------------------------------------------------------
# T02 -- create() rejects a missing required field
# --------------------------------------------------------------------------


def t02_missing_field(root):
    engine = ProposalEngine(root)
    ev = [Evidence(block_id="X1-01")]

    for omitted in ("problem", "improvement", "estimated_impact"):
        fields = dict(BASE)
        fields[omitted] = ""
        fields["evidence"] = ev
        try:
            engine.create(**fields)
        except ValueError as err:
            check(omitted in str(err), f"ValueError must name the field '{omitted}': {err}")
        else:
            raise AssertionError(f"missing '{omitted}' must raise ValueError")

    # Nothing was written for any of the rejected attempts.
    check(engine.list_all() == [], "rejected proposals must never reach disk")
    check(engine.audit.read_all() == [], "rejected proposals must not be audited")


# --------------------------------------------------------------------------
# T03 -- approve()
# --------------------------------------------------------------------------


def t03_approve(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)

    approved = engine.approve(proposal.id, "owner")
    check(approved.status is ProposalStatus.APPROVED, "approve() must set approved")
    check(approved.approved_by == "owner", "approved_by must be recorded")
    check(approved.approved_at.endswith("Z"), "approved_at must be ISO-8601 UTC")

    check(
        engine.get(proposal.id).status is ProposalStatus.APPROVED,
        "approval must be durable on disk",
    )

    audit_path = root / ".maestro" / "proposals" / "audit.jsonl"
    check(audit_path.is_file(), "audit.jsonl must exist after approve()")
    check(
        audit_events(engine, proposal.id) == ["created", "approved"],
        f"audit must record created then approved, got {audit_events(engine, proposal.id)}",
    )
    entry = engine.audit.for_proposal(proposal.id)[-1]
    check(entry["actor"] == "owner", "audit entry must carry the actor")

    expect_raises(
        ValueError,
        lambda: engine.approve(proposal.id, "   "),
        "approve() with a blank author",
    )


# --------------------------------------------------------------------------
# T04 -- reject()
# --------------------------------------------------------------------------


def t04_reject(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)

    rejected = engine.reject(proposal.id, "owner", reason="fora do escopo atual")
    check(rejected.status is ProposalStatus.REJECTED, "reject() must set rejected")
    check(rejected.reject_reason == "fora do escopo atual", "reason must be recorded")
    check(
        audit_events(engine, proposal.id) == ["created", "rejected"],
        "audit must record the rejection",
    )
    # Terminal: no reopening.
    expect_raises(
        InvalidTransitionError,
        lambda: engine.approve(proposal.id, "owner"),
        "approving a rejected proposal",
    )


# --------------------------------------------------------------------------
# T05 -- mark_implemented() only from approved
# --------------------------------------------------------------------------


def t05_mark_implemented(root):
    engine = ProposalEngine(root)
    pending = make_proposal(engine)

    # The gate of acceptance criterion 3.
    expect_raises(
        InvalidTransitionError,
        lambda: engine.mark_implemented(pending.id),
        "implementing a pending proposal",
    )
    check(
        engine.get(pending.id).status is ProposalStatus.PENDING,
        "a refused implementation must not change state",
    )

    engine.approve(pending.id, "owner")
    done = engine.mark_implemented(pending.id, ref="commit-abc123")
    check(done.status is ProposalStatus.IMPLEMENTED, "approved -> implemented")
    check(done.implemented_ref == "commit-abc123", "implemented_ref must be recorded")
    check(done.implemented_at.endswith("Z"), "implemented_at must be ISO-8601 UTC")

    # Terminal.
    expect_raises(
        InvalidTransitionError,
        lambda: engine.mark_implemented(pending.id),
        "implementing twice",
    )

    rejected = make_proposal(engine)
    engine.reject(rejected.id, "owner")
    expect_raises(
        InvalidTransitionError,
        lambda: engine.mark_implemented(rejected.id),
        "implementing a rejected proposal",
    )


# --------------------------------------------------------------------------
# T06 -- list_pending()
# --------------------------------------------------------------------------


def t06_list_pending(root):
    engine = ProposalEngine(root)
    check(engine.list_pending() == [], "empty directory must list as []")

    keep = make_proposal(engine)
    approved = make_proposal(engine)
    rejected = make_proposal(engine)
    engine.approve(approved.id, "owner")
    engine.reject(rejected.id, "owner")

    pending = engine.list_pending()
    check(len(pending) == 1, f"expected 1 pending, got {len(pending)}")
    check(pending[0].id == keep.id, "list_pending must return only the pending one")
    check(
        all(p.status is ProposalStatus.PENDING for p in pending),
        "list_pending must never return a non-pending proposal",
    )
    check(len(engine.list_all()) == 3, "list_all must return every proposal")
    check(
        len(engine.list_all(status=ProposalStatus.APPROVED)) == 1,
        "list_all must filter by status",
    )


# --------------------------------------------------------------------------
# T07 -- detect_patterns() at and above threshold
# --------------------------------------------------------------------------


def t07_detect_pattern(root):
    engine = ProposalEngine(root)
    entries = history(
        ("X1-01", "spec_ausente"),
        ("X1-02", "spec_ausente"),
        ("X1-03", "spec_ausente"),
        ("X1-04", "timeout"),
    )

    found = engine.detect_patterns(entries)
    check(len(found) == 1, f"expected 1 proposal, got {len(found)}")

    proposal = found[0]
    check(proposal.status is ProposalStatus.PENDING, "draft must be pending")
    check(
        proposal.block_ids == ["X1-01", "X1-02", "X1-03"],
        f"evidence must cite the 3 blocks, got {proposal.block_ids}",
    )
    check("spec_ausente" in proposal.problem, "problem must name the error type")
    check(proposal.improvement.strip() != "", "improvement must be filled")
    check(proposal.estimated_impact.strip() != "", "estimated_impact must be filled")
    check(proposal.target_type is TargetType.PLAN, "detected proposals target the plan")
    check(0.0 <= proposal.confidence <= 1.0, "confidence must be within [0,1]")

    # Detection is pure: nothing on disk unless asked.
    check(engine.list_all() == [], "detect_patterns must not persist by default")
    check(
        not (root / ".maestro" / "proposals" / "audit.jsonl").exists(),
        "detect_patterns must not write the audit trail by default",
    )

    persisted = engine.detect_patterns(entries, persist=True)
    check(len(persisted) == 1, "persist=True must still produce 1 proposal")
    check(len(engine.list_pending()) == 1, "persist=True must write the proposal")
    check(
        audit_events(engine, persisted[0].id) == ["created"],
        "persist=True must audit the creation",
    )


# --------------------------------------------------------------------------
# T08 -- detect_patterns() below threshold
# --------------------------------------------------------------------------


def t08_detect_below_threshold(root):
    engine = ProposalEngine(root)
    check(
        engine.detect_patterns(history(("X1-01", "spec_ausente"), ("X1-02", "spec_ausente")))
        == [],
        "2 distinct blocks must not trigger a proposal",
    )
    check(engine.detect_patterns([]) == [], "empty history must return []")
    check(engine.detect_patterns(None) == [], "None history must return []")

    # Three occurrences inside ONE block is a troubled block, not a pattern.
    same_block = history(
        ("X1-01", "spec_ausente"),
        ("X1-01", "spec_ausente"),
        ("X1-01", "spec_ausente"),
    )
    check(
        engine.detect_patterns(same_block) == [],
        "repeats within a single block must not count as a recurring pattern",
    )

    # Malformed entries are ignored, not fatal.
    noisy = [
        {"block_id": "", "error_type": "spec_ausente"},
        {"error_type": "spec_ausente"},
        "not a dict",
        {"block_id": "X1-09"},
    ]
    check(engine.detect_patterns(noisy) == [], "malformed entries must be ignored")


# --------------------------------------------------------------------------
# T09 -- to_block_spec()
# --------------------------------------------------------------------------


def t09_to_block_spec(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)

    expect_raises(
        ValueError,
        lambda: engine.to_block_spec(proposal),
        "deriving a block from a pending proposal",
    )

    approved = engine.approve(proposal.id, "owner")
    block = engine.to_block_spec(approved)

    for key in (
        "id",
        "titulo",
        "spec",
        "complexidade",
        "modelo",
        "agente",
        "depende_de",
        "arquivos_permitidos",
        "criterio_aceite",
        "estado",
        "origem_proposal",
    ):
        check(key in block, f"block dict is missing '{key}'")

    check(block["origem_proposal"] == proposal.id, "block must trace back to the proposal")
    check(block["estado"] == "pendente", "derived block starts pendente")
    check(block["spec"].startswith("plano/specs/"), "spec path must live under plano/specs")
    check(block["spec"].endswith(".md"), "spec path must be a markdown file")
    check(isinstance(block["criterio_aceite"], list), "criterio_aceite must be a list")
    check(len(block["criterio_aceite"]) >= 1, "criterio_aceite must not be empty")
    check(
        block["arquivos_permitidos"] == [],
        "arquivos_permitidos must be empty: a guessed list grants false authorization",
    )
    check(block["titulo"].strip() != "", "titulo must not be blank")

    # The dict must be JSON-serializable so the operator can paste it.
    json.dumps(block, ensure_ascii=False)

    # Accepts an id as well as an object.
    check(engine.to_block_spec(proposal.id)["id"] == block["id"], "id form must match")

    # Still derivable after implementation.
    engine.mark_implemented(proposal.id)
    check(engine.to_block_spec(proposal.id)["id"] == block["id"], "implemented is derivable")


# --------------------------------------------------------------------------
# T10 -- the engine never touches plano/blocos.json
# --------------------------------------------------------------------------


def t10_never_touches_plan(root):
    """Instrument every write primitive and run the full lifecycle."""
    touched = []

    real_open = builtins.open
    real_replace = os.replace
    real_os_open = os.open

    def _record(path, tag):
        try:
            text = str(path).replace("\\", "/")
        except Exception:  # noqa: BLE001
            return
        if "plano/" in text or text.endswith("blocos.json"):
            touched.append(f"{tag}:{text}")

    def spy_open(file, *args, **kwargs):
        _record(file, "open")
        return real_open(file, *args, **kwargs)

    def spy_replace(src, dst, *args, **kwargs):
        _record(src, "replace-src")
        _record(dst, "replace-dst")
        return real_replace(src, dst, *args, **kwargs)

    def spy_os_open(path, *args, **kwargs):
        _record(path, "os.open")
        return real_os_open(path, *args, **kwargs)

    builtins.open = spy_open
    os.replace = spy_replace
    os.open = spy_os_open
    try:
        engine = ProposalEngine(root)
        entries = history(
            ("X1-01", "spec_ausente"),
            ("X1-02", "spec_ausente"),
            ("X1-03", "spec_ausente"),
        )
        drafts = engine.detect_patterns(entries)
        proposal = engine.create(
            problem=drafts[0].problem,
            improvement=drafts[0].improvement,
            estimated_impact=drafts[0].estimated_impact,
            evidence=drafts[0].evidence,
            target_type=TargetType.PLAN,
        )
        engine.approve(
            proposal.id,
            "owner",
            eval_result={"score_before": 0.72, "score_after": 0.81, "passed": True},
        )
        block = engine.to_block_spec(proposal.id)
        engine.mark_implemented(proposal.id, ref=block["id"])
        engine.list_pending()
        engine.audit.read_all()
    finally:
        builtins.open = real_open
        os.replace = real_replace
        os.open = real_os_open

    check(not touched, f"engine touched the plan: {touched}")

    # Belt and braces: no module carries "blocos.json" as a live string
    # constant. Two deliberate exclusions:
    #   - docstrings, which are prose and cannot be opened;
    #   - "plano/specs/...", which to_block_spec() returns as *data* for the
    #     operator to place; the instrumented check above already proves no
    #     path under plano/ is ever opened.
    pkg_dir = Path(__file__).resolve().parent
    for module in sorted(pkg_dir.glob("*.py")):
        if module.name == Path(__file__).name:
            continue
        with open(module, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=str(module))

        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.value in docstrings:
                continue
            check(
                "blocos.json" not in node.value,
                f"{module.name}:{node.lineno} carries blocos.json as a live "
                f"string constant: {node.value!r}",
            )


# --------------------------------------------------------------------------
# T11 -- audit trail preserves the full history
# --------------------------------------------------------------------------


def t11_audit_history(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)
    engine.approve(proposal.id, "owner")
    engine.mark_implemented(proposal.id, ref="commit-abc123")

    events = engine.audit.for_proposal(proposal.id)
    check(
        [e["event"] for e in events] == ["created", "approved", "implemented"],
        f"full history expected, got {[e['event'] for e in events]}",
    )
    check(
        [e["status"] for e in events] == ["pending", "approved", "implemented"],
        "each entry must carry the resulting status",
    )
    for event in events:
        check(event["ts"].endswith("Z"), "every audit ts must be ISO-8601 UTC")
        check(event["proposal_id"] == proposal.id, "every entry must name the proposal")

    # Other proposals do not pollute the filtered view.
    other = make_proposal(engine)
    check(len(engine.audit.for_proposal(proposal.id)) == 3, "filter must be per proposal")
    check(len(engine.audit.read_all()) == 4, "read_all must return every event")
    check(engine.audit.for_proposal(other.id)[0]["event"] == "created", "other proposal logged")

    # Append-only: the trail only ever grows, and no API can shorten it.
    audit_path = root / ".maestro" / "proposals" / "audit.jsonl"
    with open(audit_path, "r", encoding="utf-8") as handle:
        before = handle.read()
    engine.list_pending()
    engine.get(proposal.id)
    with open(audit_path, "r", encoding="utf-8") as handle:
        after = handle.read()
    check(after == before, "reads must not mutate the audit trail")
    check(after.startswith(before[: len(before)]), "audit trail must be append-only")

    for forbidden in ("delete", "clear", "truncate", "rewrite", "remove"):
        check(
            not hasattr(AuditTrail, forbidden),
            f"AuditTrail must not expose '{forbidden}'",
        )

    # One corrupt line does not erase the readable history.
    with open(audit_path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write("{not json at all\n")
    check(len(engine.audit.read_all()) == 4, "corrupt line must be skipped, not fatal")


# --------------------------------------------------------------------------
# T12 -- a second approve() is refused, and does not pollute the trail
# --------------------------------------------------------------------------


def t12_double_approve(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine)
    engine.approve(proposal.id, "owner")

    expect_raises(
        InvalidTransitionError,
        lambda: engine.approve(proposal.id, "other-owner"),
        "approving an already approved proposal",
    )

    events = audit_events(engine, proposal.id)
    check(
        events.count("approved") == 1,
        f"a refused second approval must not be audited, got {events}",
    )
    stored = engine.get(proposal.id)
    check(stored.approved_by == "owner", "the original approver must be preserved")


# --------------------------------------------------------------------------
# Robustness
# --------------------------------------------------------------------------


def t13_evidence_required(root):
    engine = ProposalEngine(root)
    for bad in ([], None, "X1-01", {"block_id": "X1-01"}):
        expect_raises(
            ValueError,
            lambda bad=bad: engine.create(**BASE, evidence=bad),
            f"evidence={bad!r}",
        )
    expect_raises(
        ValueError,
        lambda: engine.create(**BASE, evidence=[{"block_id": "  "}]),
        "evidence entry with a blank block_id",
    )
    check(engine.list_all() == [], "no invalid proposal may reach disk")


def t14_confidence_bounds(root):
    engine = ProposalEngine(root)
    ev = [Evidence(block_id="X1-01")]
    for bad in (-0.1, 1.5, "muito"):
        expect_raises(
            ValueError,
            lambda bad=bad: engine.create(**BASE, evidence=ev, confidence=bad),
            f"confidence={bad!r}",
        )
    ok = engine.create(**BASE, evidence=ev, confidence=0.88, target_type=TargetType.GOTCHA)
    check(ok.confidence == 0.88, "valid confidence must be stored")
    check(engine.get(ok.id).confidence == 0.88, "confidence must round-trip")


def t15_malformed_id(root):
    engine = ProposalEngine(root)
    ev = [Evidence(block_id="X1-01")]
    for bad in ("../escape", "a/b", "..", ".", "with space", "x\\y", "a:b"):
        expect_raises(
            ValueError,
            lambda bad=bad: engine.create(**BASE, evidence=ev, proposal_id=bad),
            f"proposal_id={bad!r}",
        )
    check(engine.list_all() == [], "a malformed id must never reach disk")

    # None and "" both mean "generate one" -- same convention as F13-01.
    for blank in (None, ""):
        generated = engine.create(**BASE, evidence=ev, proposal_id=blank)
        check(
            generated.id.startswith("P-"),
            f"proposal_id={blank!r} must generate an id, got {generated.id!r}",
        )


def t16_not_found(root):
    engine = ProposalEngine(root)
    expect_raises(
        ProposalNotFoundError, lambda: engine.get("P-20260101T000000-deadbeef"), "get()"
    )
    expect_raises(
        ProposalNotFoundError,
        lambda: engine.approve("P-20260101T000000-deadbeef", "owner"),
        "approve() of a missing proposal",
    )


def t17_eval_gate_required(root):
    engine = ProposalEngine(root)
    for high in (TargetType.RULE, TargetType.PROCEDURE, TargetType.DECISION, TargetType.PLAN):
        proposal = make_proposal(engine, target_type=high)
        expect_raises(
            EvalGateError,
            lambda pid=proposal.id: engine.approve(pid, "owner"),
            f"approving {high.value} without an eval",
        )
        check(
            engine.get(proposal.id).status is ProposalStatus.PENDING,
            "a refused approval must leave the proposal pending",
        )
        approved = engine.approve(
            proposal.id,
            "owner",
            eval_result={"score_before": 0.72, "score_after": 0.81, "passed": True},
        )
        check(approved.status is ProposalStatus.APPROVED, "passing eval must approve")
        check(approved.eval_result.passed is True, "eval_result must be stored")
        check(
            engine.get(proposal.id).eval_result.score_after == 0.81,
            "eval scores must round-trip",
        )

    # Low-impact targets need no eval.
    for low in (TargetType.GOTCHA, TargetType.CONCEPT):
        proposal = make_proposal(engine, target_type=low)
        check(
            engine.approve(proposal.id, "owner").status is ProposalStatus.APPROVED,
            f"{low.value} must approve without an eval",
        )


def t18_eval_failure_rejects(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine, target_type=TargetType.RULE)

    expect_raises(
        EvalGateError,
        lambda: engine.approve(
            proposal.id,
            "owner",
            eval_result={"score_before": 0.81, "score_after": 0.60, "passed": False},
        ),
        "approving with a failing eval",
    )

    stored = engine.get(proposal.id)
    check(
        stored.status is ProposalStatus.REJECTED,
        "a failing eval must leave the proposal rejected on disk",
    )
    check(stored.eval_result.passed is False, "the failing eval must be recorded")
    check("eval gate failed" in stored.reject_reason, "reject_reason must cite the eval")
    check(
        audit_events(engine, proposal.id) == ["created", "eval_failed", "rejected"],
        f"audit must record the failure, got {audit_events(engine, proposal.id)}",
    )

    # `passed` is read as given, never recomputed from the scores.
    other = make_proposal(engine, target_type=TargetType.RULE)
    approved = engine.approve(
        other.id,
        "owner",
        eval_result={"score_before": 0.90, "score_after": 0.10, "passed": True},
    )
    check(
        approved.status is ProposalStatus.APPROVED,
        "engine must trust 'passed' rather than recompute it from the scores",
    )


def t19_corrupt_file_survives_listing(root):
    engine = ProposalEngine(root)
    good = make_proposal(engine)

    corrupt = root / ".maestro" / "proposals" / "P-20260101T000000-badbad00.json"
    with open(corrupt, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{ this is not json")
    incomplete = root / ".maestro" / "proposals" / "P-20260101T000000-badbad01.json"
    with open(incomplete, "w", encoding="utf-8", newline="\n") as handle:
        handle.write('{"id": "P-20260101T000000-badbad01"}')

    pending = engine.list_pending()
    check(len(pending) == 1, f"corrupt files must be skipped, got {len(pending)}")
    check(pending[0].id == good.id, "the readable proposal must still be listed")


def t20_round_trip(root):
    engine = ProposalEngine(root)
    original = engine.create(
        problem=BASE["problem"],
        improvement=BASE["improvement"],
        estimated_impact=BASE["estimated_impact"],
        evidence=[
            {"block_id": "X1-01", "error_type": "spec_ausente", "detail": "d1"},
            Evidence(block_id="X1-02", error_type="spec_ausente", occurred_at="2026-01-01T00:00:00Z"),
        ],
        block_id_origem="X1-01",
        target_type="gotcha",
        target_path="gotchas/exemplo.md",
        confidence=0.5,
        rationale="racional de teste",
    )
    loaded = engine.get(original.id)
    check(loaded.to_dict() == original.to_dict(), "get() must round-trip faithfully")
    check(loaded.target_type is TargetType.GOTCHA, "string target_type must coerce")
    check(loaded.evidence[0].detail == "d1", "evidence detail must survive")
    check(loaded.block_id_origem == "X1-01", "block_id_origem must survive")

    # Proposal.from_dict on the raw JSON gives the same object.
    with open(root / ".maestro" / "proposals" / f"{original.id}.json", "r", encoding="utf-8") as h:
        raw = json.load(h)
    check(Proposal.from_dict(raw).to_dict() == original.to_dict(), "from_dict must round-trip")


def t21_no_overwrite(root):
    engine = ProposalEngine(root)
    ev = [Evidence(block_id="X1-01")]
    first = engine.create(**BASE, evidence=ev, proposal_id="P-fixed-id")
    check(first.id == "P-fixed-id", "explicit id must be honoured")
    try:
        engine.create(**BASE, evidence=ev, proposal_id="P-fixed-id")
    except Exception as err:  # noqa: BLE001
        check(type(err).__name__ == "ProposalExistsError", f"expected ProposalExistsError, got {err!r}")
    else:
        raise AssertionError("create() must never overwrite an existing proposal")


def t22_policy_cannot_waive_approval(root):
    """No policy value may let a proposal skip approve()."""
    permissive = ApprovalPolicy(require_eval=frozenset())
    engine = ProposalEngine(root, policy=permissive)
    proposal = make_proposal(engine, target_type=TargetType.RULE)

    # The permissive policy waives the eval...
    expect_raises(
        InvalidTransitionError,
        lambda: engine.mark_implemented(proposal.id),
        "implementing without approval under a permissive policy",
    )
    # ...but never the approval itself.
    engine.approve(proposal.id, "owner")
    check(
        engine.mark_implemented(proposal.id).status is ProposalStatus.IMPLEMENTED,
        "explicit approval must still be the only path to implemented",
    )

    for forbidden in ("auto_approve", "force", "skip_eval", "bypass"):
        check(
            not hasattr(ProposalEngine, forbidden),
            f"ProposalEngine must not expose '{forbidden}'",
        )
        check(
            not hasattr(permissive, forbidden),
            f"ApprovalPolicy must not expose '{forbidden}'",
        )


def t23_no_io_on_construction(root):
    """__init__ must not create directories or files."""
    engine = ProposalEngine(root)
    check(
        not (root / ".maestro").exists(),
        "constructing the engine must not create .maestro",
    )
    check(engine.list_pending() == [], "listing a missing directory must return []")
    check(engine.audit.read_all() == [], "reading a missing audit file must return []")
    check(
        not (root / ".maestro").exists(),
        "read-only calls must not create directories",
    )


def t24_eval_result_validation(root):
    engine = ProposalEngine(root)
    proposal = make_proposal(engine, target_type=TargetType.RULE)
    for bad in ({"score_before": 0.1, "score_after": 0.2}, "passed", 42):
        expect_raises(
            ValueError,
            lambda bad=bad: engine.approve(proposal.id, "owner", eval_result=bad),
            f"eval_result={bad!r}",
        )
    check(
        engine.get(proposal.id).status is ProposalStatus.PENDING,
        "an invalid eval must leave the proposal untouched",
    )
    typed = EvalResult(score_before=0.72, score_after=0.81, passed=True)
    check(
        engine.approve(proposal.id, "owner", eval_result=typed).status
        is ProposalStatus.APPROVED,
        "a typed EvalResult must be accepted",
    )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

TESTS = [
    ("T01 create persists pending proposal + sidecar", t01_create),
    ("T02 create rejects missing required field", t02_missing_field),
    ("T03 approve sets approved and audits", t03_approve),
    ("T04 reject sets rejected and audits", t04_reject),
    ("T05 mark_implemented requires approved", t05_mark_implemented),
    ("T06 list_pending returns only pending", t06_list_pending),
    ("T07 detect_patterns at threshold", t07_detect_pattern),
    ("T08 detect_patterns below threshold", t08_detect_below_threshold),
    ("T09 to_block_spec derives plan block", t09_to_block_spec),
    ("T10 engine never touches plano/blocos.json", t10_never_touches_plan),
    ("T11 audit trail preserves full history", t11_audit_history),
    ("T12 second approve is refused", t12_double_approve),
    ("T13 evidence is required", t13_evidence_required),
    ("T14 confidence bounds", t14_confidence_bounds),
    ("T15 malformed proposal id", t15_malformed_id),
    ("T16 missing proposal", t16_not_found),
    ("T17 eval gate for high impact", t17_eval_gate_required),
    ("T18 failing eval rejects the proposal", t18_eval_failure_rejects),
    ("T19 corrupt file does not break listing", t19_corrupt_file_survives_listing),
    ("T20 round-trip fidelity", t20_round_trip),
    ("T21 create never overwrites", t21_no_overwrite),
    ("T22 policy cannot waive approval", t22_policy_cannot_waive_approval),
    ("T23 no I/O on construction", t23_no_io_on_construction),
    ("T24 eval_result validation", t24_eval_result_validation),
]


def main() -> int:
    print("F13-02 -- ProposalEngine")
    for name, fn in TESTS:
        run(name, fn)
    print("")
    if _FAILURES:
        print(f"{len(_FAILURES)} of {_RUN} tests FAILED:")
        for name in _FAILURES:
            print(f"  - {name}")
        return 1
    print(f"{_RUN} tests")
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
