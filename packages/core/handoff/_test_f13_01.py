"""Tests for F13-01 -- typed handoff, claim, workstreams, cross-agent resume.

Stdlib only, no pytest. Real filesystem I/O under tempfile.mkdtemp(); no
filesystem mocking. Every file handle goes through a context manager so
Windows never holds an open descriptor at teardown.

Run::

    python packages/core/handoff/_test_f13_01.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running the file directly from anywhere in the repo.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.core.handoff import (  # noqa: E402
    ANY_AGENT,
    Checkpoint,
    ClaimError,
    Handoff,
    HandoffExistsError,
    HandoffManager,
    HandoffNotFoundError,
    HandoffStatus,
    InvalidTransitionError,
    LeaseError,
    ResumePacket,
    StateSnapshot,
    Workstream,
    WorkstreamNotFoundError,
    WorkstreamRegistry,
)

# ---------------------------------------------------------------------------
# tiny harness
# ---------------------------------------------------------------------------

_FAILURES = []
_PASSED = 0


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_eq(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


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


def run(label, fn):
    global _PASSED
    tmp = tempfile.mkdtemp(prefix="maestro-f13-")
    try:
        fn(Path(tmp))
        _PASSED += 1
        print(f"  PASS  {label}")
    except Exception as err:  # noqa: BLE001
        _FAILURES.append((label, err, traceback.format_exc()))
        print(f"  FAIL  {label}: {type(err).__name__}: {err}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def iso_offset(seconds):
    moment = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_snapshot():
    return StateSnapshot(
        completed=["wired the parser", "added the fixture"],
        remaining=["hook the CLI flag"],
        failed_approaches=["regex over the AST -- too brittle"],
        files_touched=["packages/core/handoff/manager.py"],
        next_steps=["run the acceptance suite"],
        checkpoint=Checkpoint(branch="feat/x", commit="deadbeef", checkpoint_id="CK-1"),
    )


def make_handoff(manager, **overrides):
    kwargs = dict(
        from_agent="claude-code",
        to_agent=ANY_AGENT,
        block_id="B17",
        context_summary="Parser is done; the CLI flag is still unwired.",
        state_snapshot=sample_snapshot(),
        open_questions=["Should the flag default to on?"],
        project="relay",
        workstream="WS-01",
        summary="Handoff mid-block",
    )
    kwargs.update(overrides)
    return manager.create(**kwargs)


# ---------------------------------------------------------------------------
# T01 -- create with required fields -> open
# ---------------------------------------------------------------------------


def t01_create(root):
    manager = HandoffManager(root)
    handoff = make_handoff(manager)

    check_eq(handoff.status, HandoffStatus.OPEN, "T01 status")
    check(handoff.id.startswith("H-"), "T01 generated id should start with H-")
    check_eq(handoff.from_agent, "claude-code", "T01 from_agent")
    check_eq(handoff.to_agent, ANY_AGENT, "T01 to_agent")
    check_eq(handoff.block_id, "B17", "T01 block_id")
    check(handoff.created_at.endswith("Z"), "T01 created_at must be UTC with Z")
    check_eq(handoff.updated_at, handoff.created_at, "T01 updated_at == created_at")

    path = root / ".maestro" / "handoffs" / f"{handoff.id}.json"
    check(path.is_file(), f"T01 record must exist at {path}")

    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    check_eq(raw["status"], "open", "T01 persisted status")
    # Acceptance criterion 1 -- the six typed fields are on the record.
    for field_name in (
        "from_agent",
        "to_agent",
        "block_id",
        "state_snapshot",
        "context_summary",
        "open_questions",
    ):
        check(field_name in raw, f"T01 persisted record must carry '{field_name}'")

    # create() never overwrites.
    expect_raises(
        HandoffExistsError,
        lambda: make_handoff(manager, handoff_id=handoff.id),
        "T01 duplicate id",
    )


# ---------------------------------------------------------------------------
# T02 -- claim once, second claim fails
# ---------------------------------------------------------------------------


def t02_claim_exactly_once(root):
    manager = HandoffManager(root)
    handoff = make_handoff(manager, handoff_id="H-100")

    packet = manager.claim("H-100", "codex")
    check(isinstance(packet, ResumePacket), "T02 claim returns a ResumePacket")
    check_eq(packet.agent, "codex", "T02 packet agent")

    reloaded = manager.load("H-100")
    check_eq(reloaded.status, HandoffStatus.CLAIMED, "T02 status after claim")
    check_eq(reloaded.claimed_by, "codex", "T02 claimed_by")
    check(reloaded.claimed_at, "T02 claimed_at must be set")

    # Second claim -- by anyone -- must fail. Exactly-once delivery.
    expect_raises(
        ClaimError, lambda: manager.claim("H-100", "codex"), "T02 same agent re-claim"
    )
    expect_raises(
        ClaimError,
        lambda: manager.claim("H-100", "claude-code"),
        "T02 other agent re-claim",
    )

    # The marker is the durable proof of delivery and must survive.
    marker = root / ".maestro" / "handoffs" / ".claims" / "H-100.claim"
    check(marker.is_file(), "T02 claim marker must be kept after a successful claim")

    # Status did not drift after the failed attempts.
    check_eq(manager.load("H-100").status, HandoffStatus.CLAIMED, "T02 status stable")
    check(handoff.id == "H-100", "T02 explicit id honoured")


# ---------------------------------------------------------------------------
# T03 -- accept
# ---------------------------------------------------------------------------


def t03_accept(root):
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-200")
    manager.claim("H-200", "codex")

    accepted = manager.accept("H-200", "codex")
    check_eq(accepted.status, HandoffStatus.ACCEPTED, "T03 status")
    check_eq(accepted.accepted_by, "codex", "T03 accepted_by")
    check(accepted.is_terminal, "T03 accepted is terminal")
    check_eq(manager.load("H-200").status, HandoffStatus.ACCEPTED, "T03 persisted")

    # accepted is terminal: no further transition.
    expect_raises(
        InvalidTransitionError,
        lambda: manager.accept("H-200", "codex"),
        "T03 double accept",
    )
    expect_raises(
        InvalidTransitionError, lambda: manager.cancel("H-200"), "T03 cancel accepted"
    )


def t03b_accept_wrong_agent(root):
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-201")
    manager.claim("H-201", "codex")

    expect_raises(
        ClaimError,
        lambda: manager.accept("H-201", "claude-code"),
        "T03b non-claimer cannot accept",
    )
    check_eq(manager.load("H-201").status, HandoffStatus.CLAIMED, "T03b state intact")


# ---------------------------------------------------------------------------
# T04 -- cancel
# ---------------------------------------------------------------------------


def t04_cancel(root):
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-300")

    cancelled = manager.cancel("H-300", reason="block was descoped")
    check_eq(cancelled.status, HandoffStatus.CANCELLED, "T04 status")
    check_eq(cancelled.cancel_reason, "block was descoped", "T04 reason")
    check_eq(manager.load("H-300").status, HandoffStatus.CANCELLED, "T04 persisted")

    # A cancelled handoff is terminal and cannot be claimed.
    expect_raises(
        InvalidTransitionError,
        lambda: manager.claim("H-300", "codex"),
        "T04 claim cancelled",
    )
    # The rollback left no reservation behind, so it stays cancellable-state clean.
    marker = root / ".maestro" / "handoffs" / ".claims" / "H-300.claim"
    check(not marker.exists(), "T04 failed claim must not leave a marker")


def t04b_cannot_cancel_claimed(root):
    """Cancelling work another agent already started is the failure we prevent."""
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-301")
    manager.claim("H-301", "codex")

    expect_raises(
        InvalidTransitionError,
        lambda: manager.cancel("H-301", reason="oops"),
        "T04b cancel of claimed must fail",
    )
    check_eq(manager.load("H-301").status, HandoffStatus.CLAIMED, "T04b state intact")


# ---------------------------------------------------------------------------
# T05 -- load from disk (round-trip)
# ---------------------------------------------------------------------------


def t05_load(root):
    manager = HandoffManager(root)
    original = make_handoff(manager, handoff_id="H-400")

    # A fresh manager -- nothing cached in memory.
    loaded = HandoffManager(root).load("H-400")

    check_eq(loaded.to_dict(), original.to_dict(), "T05 round-trip must be faithful")
    check_eq(loaded.state_snapshot.completed, original.state_snapshot.completed, "T05 completed")
    check_eq(
        loaded.state_snapshot.failed_approaches,
        ["regex over the AST -- too brittle"],
        "T05 failed_approaches survives",
    )
    check_eq(loaded.state_snapshot.checkpoint.commit, "deadbeef", "T05 checkpoint commit")
    check_eq(loaded.state_snapshot.checkpoint.branch, "feat/x", "T05 checkpoint branch")
    check_eq(loaded.open_questions, ["Should the flag default to on?"], "T05 open_questions")
    check_eq(loaded.workstream, "WS-01", "T05 workstream")

    expect_raises(
        HandoffNotFoundError, lambda: manager.load("H-nope"), "T05 missing handoff"
    )


# ---------------------------------------------------------------------------
# T06 -- list_open returns only open handoffs
# ---------------------------------------------------------------------------


def t06_list_open(root):
    manager = HandoffManager(root)
    check_eq(manager.list_open(), [], "T06 empty directory -> []")

    for index in range(4):
        make_handoff(
            manager,
            handoff_id=f"H-50{index}",
            block_id=f"B{index}",
            workstream="WS-A" if index < 2 else "WS-B",
        )

    check_eq(len(manager.list_open()), 4, "T06 all open")

    manager.claim("H-500", "codex")
    manager.cancel("H-501")

    open_ids = [item.id for item in manager.list_open()]
    check_eq(sorted(open_ids), ["H-502", "H-503"], "T06 only open remain")
    check(
        all(item.status == HandoffStatus.OPEN for item in manager.list_open()),
        "T06 every result is open",
    )

    check_eq(
        [item.id for item in manager.list_open(workstream="WS-B")],
        ["H-502", "H-503"],
        "T06 workstream filter",
    )
    check_eq(manager.list_open(workstream="WS-A"), [], "T06 no open in WS-A")

    # A corrupt record must not blind the agent to the rest.
    bad = root / ".maestro" / "handoffs" / "H-broken.json"
    with open(bad, "w", encoding="utf-8") as handle:
        handle.write("{ not json at all")
    check_eq(len(manager.list_open()), 2, "T06 corrupt file is skipped, not raised")

    # Schema-valid JSON but missing a required field: also skipped.
    incomplete = root / ".maestro" / "handoffs" / "H-partial.json"
    with open(incomplete, "w", encoding="utf-8") as handle:
        json.dump({"id": "H-partial", "status": "open"}, handle)
    check_eq(len(manager.list_open()), 2, "T06 invalid schema is skipped")


# ---------------------------------------------------------------------------
# T07 -- missing required field -> ValueError
# ---------------------------------------------------------------------------


def t07_validation(root):
    manager = HandoffManager(root)

    required = {
        "from_agent": "claude-code",
        "to_agent": "codex",
        "block_id": "B17",
        "context_summary": "some context",
    }

    for missing in required:
        kwargs = dict(required)
        kwargs[missing] = ""
        expect_raises(
            ValueError,
            lambda k=kwargs: manager.create(**k),
            f"T07 blank '{missing}' must raise ValueError",
        )

        kwargs_blank = dict(required)
        kwargs_blank[missing] = "   "
        expect_raises(
            ValueError,
            lambda k=kwargs_blank: manager.create(**k),
            f"T07 whitespace-only '{missing}' must raise ValueError",
        )

    # None is rejected too.
    expect_raises(
        ValueError,
        lambda: manager.create(
            from_agent=None, to_agent="codex", block_id="B1", context_summary="x"
        ),
        "T07 None from_agent",
    )

    # Nothing was written by any failed create().
    check_eq(manager.list_open(), [], "T07 invalid handoffs are never persisted")

    # An absent or empty handoff_id means "generate one" -- it is not an error.
    for absent in (None, ""):
        generated = manager.create(handoff_id=absent, **required)
        check(generated.id.startswith("H-"), "T07 absent id is generated")

    # Ids that would escape the directory are rejected.
    # ("" and None mean "no id given" -- one is generated; see spec 6.4.)
    for bad_id in ("../escape", "a/b", "..", "with space", "x\\y", "  ../x  "):
        expect_raises(
            ValueError,
            lambda b=bad_id: manager.create(handoff_id=b, **required),
            f"T07 malformed id {bad_id!r}",
        )

    # Surrounding whitespace is normalized away, not rejected.
    check_eq(
        manager.create(handoff_id="  H-trim\n", **required).id,
        "H-trim",
        "T07 id is stripped",
    )

    # Direct schema validation surfaces the field name.
    try:
        Handoff.from_dict({"id": "H-1", "from_agent": "a", "to_agent": "b"})
        raise AssertionError("T07 from_dict should reject an incomplete payload")
    except ValueError as err:
        check("block_id" in str(err), "T07 error message names the missing field")
        check("context_summary" in str(err), "T07 error message names every missing field")


# ---------------------------------------------------------------------------
# T08 -- cross-agent resume
# ---------------------------------------------------------------------------


def t08_cross_agent_resume(root):
    """Claude ends a session; Codex picks the work up from the handoff alone."""
    claude_side = HandoffManager(root)
    summary = (
        "Provider routing is wired for two adapters. The retry budget is still "
        "hardcoded and must move into config before the block closes."
    )
    claude_side.create(
        from_agent="claude-code",
        to_agent="codex",
        block_id="B21",
        context_summary=summary,
        state_snapshot=StateSnapshot(
            completed=["adapter registry", "two adapters wired"],
            remaining=["move retry budget into config"],
            files_touched=["packages/core/routing/registry.py"],
            next_steps=["extract the retry budget", "add a regression test"],
            checkpoint=Checkpoint(branch="feat/routing", commit="c0ffee"),
        ),
        open_questions=["Which config layer owns the retry budget?"],
        project="relay",
        workstream="WS-provider-routing",
        handoff_id="H-600",
    )

    # A different process, a different agent.
    codex_side = HandoffManager(root)

    pending = codex_side.list_open(for_agent="codex")
    check_eq([item.id for item in pending], ["H-600"], "T08 codex sees the handoff")

    packet = codex_side.claim("H-600", "codex")

    # Criterion 3: context_summary is the initial context for the resuming agent.
    check_eq(packet.context_summary, summary, "T08 context_summary is delivered")
    check_eq(
        packet.next_steps,
        ["extract the retry budget", "add a regression test"],
        "T08 next_steps",
    )
    check_eq(
        packet.open_questions,
        ["Which config layer owns the retry budget?"],
        "T08 open_questions",
    )
    check_eq(packet.checkpoint.commit, "c0ffee", "T08 checkpoint commit")
    check_eq(packet.checkpoint.branch, "feat/routing", "T08 checkpoint branch")
    check_eq(
        packet.files_touched,
        ["packages/core/routing/registry.py"],
        "T08 files_touched",
    )
    check_eq(packet.handoff.from_agent, "claude-code", "T08 origin preserved")
    check_eq(packet.handoff.status, HandoffStatus.CLAIMED, "T08 packet handoff status")

    # Criterion 5: state is enough to resume without re-deriving anything.
    check(packet.to_dict()["context_summary"], "T08 packet serializes")

    accepted = codex_side.accept("H-600", "codex")
    check_eq(accepted.status, HandoffStatus.ACCEPTED, "T08 accepted")


def t08b_addressed_handoff_is_private(root):
    manager = HandoffManager(root)
    make_handoff(manager, to_agent="codex", handoff_id="H-601")

    # A handoff addressed to codex is invisible and unclaimable to others.
    check_eq(manager.list_open(for_agent="gemini"), [], "T08b not listed for others")
    expect_raises(
        ClaimError,
        lambda: manager.claim("H-601", "gemini"),
        "T08b wrong recipient cannot claim",
    )

    # Fail-closed rollback: still open, no marker left behind.
    check_eq(manager.load("H-601").status, HandoffStatus.OPEN, "T08b stays open")
    marker = root / ".maestro" / "handoffs" / ".claims" / "H-601.claim"
    check(not marker.exists(), "T08b rejected claim leaves no marker")

    # And the rightful recipient can still claim it afterwards.
    packet = manager.claim("H-601", "codex")
    check_eq(packet.agent, "codex", "T08b rightful claim succeeds after a rejection")

    # "any" is open to everyone.
    make_handoff(manager, to_agent=ANY_AGENT, handoff_id="H-602")
    check_eq(
        [i.id for i in manager.list_open(for_agent="gemini")],
        ["H-602"],
        "T08b 'any' is visible to all",
    )


# ---------------------------------------------------------------------------
# T09 -- lease is exclusive
# ---------------------------------------------------------------------------


def t09_lease_exclusive(root):
    registry = WorkstreamRegistry(root)
    registry.register("WS-auth-refactor", name="Auth refactor", project="relay")

    lease = registry.acquire_lease("WS-auth-refactor", "claude-code")
    check_eq(lease.workstream_id, "WS-auth-refactor", "T09 lease workstream")
    check_eq(lease.agent, "claude-code", "T09 lease agent")
    check(lease.token, "T09 lease carries a token")
    check(not lease.is_expired, "T09 fresh lease is not expired")

    # Second acquire fails -- for any agent, including the holder.
    expect_raises(
        LeaseError,
        lambda: registry.acquire_lease("WS-auth-refactor", "codex"),
        "T09 second agent cannot acquire",
    )
    expect_raises(
        LeaseError,
        lambda: registry.acquire_lease("WS-auth-refactor", "claude-code"),
        "T09 lease is not reentrant",
    )

    holder = registry.lease_holder("WS-auth-refactor")
    check_eq(holder.agent, "claude-code", "T09 holder unchanged")
    check_eq(holder.token, lease.token, "T09 token unchanged")
    check(registry.is_leased("WS-auth-refactor"), "T09 is_leased")

    # An unregistered workstream cannot be leased -- fail closed.
    expect_raises(
        WorkstreamNotFoundError,
        lambda: registry.acquire_lease("WS-ghost", "codex"),
        "T09 unregistered workstream",
    )
    expect_raises(
        WorkstreamNotFoundError, lambda: registry.get("WS-ghost"), "T09 get unregistered"
    )


# ---------------------------------------------------------------------------
# T10 -- release allows a new acquire
# ---------------------------------------------------------------------------


def t10_lease_release(root):
    registry = WorkstreamRegistry(root)
    registry.register("WS-01", name="First", project="relay")

    first = registry.acquire_lease("WS-01", "claude-code")

    # Wrong token cannot release someone else's lease.
    expect_raises(
        LeaseError,
        lambda: registry.release_lease("WS-01", "not-the-token"),
        "T10 wrong token cannot release",
    )
    check(registry.is_leased("WS-01"), "T10 lease survives a bad release")

    registry.release_lease("WS-01", first.token)
    check(not registry.is_leased("WS-01"), "T10 released")
    check_eq(registry.lease_holder("WS-01"), None, "T10 no holder after release")

    second = registry.acquire_lease("WS-01", "codex")
    check_eq(second.agent, "codex", "T10 new agent acquires after release")
    check(second.token != first.token, "T10 new lease has a new token")

    # Release is idempotent once the lease is gone.
    registry.release_lease("WS-01", second.token)
    registry.release_lease("WS-01", second.token)
    check(not registry.is_leased("WS-01"), "T10 release is idempotent")


def t10b_expired_lease_is_reclaimable(root):
    registry = WorkstreamRegistry(root)
    registry.register("WS-02")
    lease = registry.acquire_lease("WS-02", "claude-code", ttl_seconds=1)

    # Force expiry by rewriting the lease file in the past -- no sleeping.
    lease_path = registry.storage.lease_path("WS-02")
    with open(lease_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["expires_at"] = iso_offset(-60)
    with open(lease_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

    check_eq(registry.lease_holder("WS-02"), None, "T10b expired lease has no holder")
    taken = registry.acquire_lease("WS-02", "codex")
    check_eq(taken.agent, "codex", "T10b expired lease is reclaimable")
    check(taken.token != lease.token, "T10b new token after takeover")

    renewed = registry.renew_lease("WS-02", taken.token, ttl_seconds=7200)
    check(renewed.expires_at > taken.expires_at, "T10b renew extends expiry")
    expect_raises(
        LeaseError,
        lambda: registry.renew_lease("WS-02", "bogus"),
        "T10b renew needs the holder token",
    )


# ---------------------------------------------------------------------------
# workstream independence + registry metadata
# ---------------------------------------------------------------------------


def t11_workstream_independence(root):
    """Criterion 4: several workstreams run at once with independent state."""
    registry = WorkstreamRegistry(root)
    manager = HandoffManager(root)

    registry.register("WS-auth-refactor", name="Auth refactor", project="relay")
    registry.register("WS-provider-routing", name="Provider routing", project="relay")

    lease_auth = registry.acquire_lease("WS-auth-refactor", "claude-code")
    lease_routing = registry.acquire_lease("WS-provider-routing", "codex")
    check(lease_auth.token != lease_routing.token, "T11 independent leases")

    make_handoff(manager, workstream="WS-auth-refactor", handoff_id="H-700")
    make_handoff(manager, workstream="WS-provider-routing", handoff_id="H-701")
    make_handoff(manager, workstream="WS-provider-routing", handoff_id="H-702")

    check_eq(
        [i.id for i in manager.list_open(workstream="WS-auth-refactor")],
        ["H-700"],
        "T11 auth workstream handoffs",
    )
    check_eq(
        [i.id for i in manager.list_open(workstream="WS-provider-routing")],
        ["H-701", "H-702"],
        "T11 routing workstream handoffs",
    )

    # Claiming in one workstream does not disturb the other.
    manager.claim("H-701", "codex")
    check_eq(
        [i.id for i in manager.list_open(workstream="WS-auth-refactor")],
        ["H-700"],
        "T11 other workstream untouched",
    )

    # Releasing one lease does not release the other.
    registry.release_lease("WS-auth-refactor", lease_auth.token)
    check(not registry.is_leased("WS-auth-refactor"), "T11 auth released")
    check(registry.is_leased("WS-provider-routing"), "T11 routing still leased")

    active = [ws.id for ws in registry.list_active()]
    check_eq(active, ["WS-auth-refactor", "WS-provider-routing"], "T11 list_active")

    registry.close("WS-auth-refactor")
    check_eq(
        [ws.id for ws in registry.list_active()],
        ["WS-provider-routing"],
        "T11 closed workstream drops out of list_active",
    )


def t12_rename_does_not_break_identity(root):
    """Identity is workstream_id; name is metadata."""
    registry = WorkstreamRegistry(root)
    manager = HandoffManager(root)

    registry.register("WS-01", name="Old name", project="relay", blocks=["B1"])
    created_at = registry.get("WS-01").created_at
    lease = registry.acquire_lease("WS-01", "claude-code")
    make_handoff(manager, workstream="WS-01", handoff_id="H-800")

    registry.register("WS-01", name="Brand new name", project="relay", blocks=["B1", "B2"])

    renamed = registry.get("WS-01")
    check_eq(renamed.name, "Brand new name", "T12 name updated")
    check_eq(renamed.id, "WS-01", "T12 id unchanged")
    check_eq(renamed.created_at, created_at, "T12 created_at preserved")
    check_eq(renamed.blocks, ["B1", "B2"], "T12 blocks updated")

    holder = registry.lease_holder("WS-01")
    check_eq(holder.token, lease.token, "T12 re-register does not disturb the lease")
    check_eq(
        [i.id for i in manager.list_open(workstream="WS-01")],
        ["H-800"],
        "T12 handoffs still resolve by id",
    )


# ---------------------------------------------------------------------------
# expiry sweep
# ---------------------------------------------------------------------------


def t13_sweep_expired(root):
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-900", expires_at=iso_offset(-120))
    make_handoff(manager, handoff_id="H-901", expires_at=iso_offset(3600))
    make_handoff(manager, handoff_id="H-902")  # never expires

    swept = manager.sweep_expired()
    check_eq(swept, ["H-900"], "T13 only the past-due handoff is swept")
    check_eq(manager.load("H-900").status, HandoffStatus.EXPIRED, "T13 status expired")
    check_eq(manager.load("H-901").status, HandoffStatus.OPEN, "T13 future stays open")
    check_eq(manager.load("H-902").status, HandoffStatus.OPEN, "T13 no expiry stays open")

    check_eq(sorted(i.id for i in manager.list_open()), ["H-901", "H-902"], "T13 listing")

    # An expired handoff cannot be claimed, and a claim on an already-past one fails.
    expect_raises(
        InvalidTransitionError,
        lambda: manager.claim("H-900", "codex"),
        "T13 expired cannot be claimed",
    )

    # Even before a sweep, a past-due open handoff is not claimable.
    make_handoff(manager, handoff_id="H-903", expires_at=iso_offset(-5))
    expect_raises(
        InvalidTransitionError,
        lambda: manager.claim("H-903", "codex"),
        "T13 past-due claim is refused",
    )
    check_eq(manager.load("H-903").status, HandoffStatus.OPEN, "T13 refused claim rolls back")

    check_eq(manager.sweep_expired(), ["H-903"], "T13 second sweep")
    check_eq(manager.sweep_expired(), [], "T13 sweep is idempotent")

    expect_raises(
        ValueError,
        lambda: make_handoff(manager, handoff_id="H-904", expires_at="not-a-date"),
        "T13 malformed expires_at",
    )


# ---------------------------------------------------------------------------
# atomicity / durability details
# ---------------------------------------------------------------------------


def t14_atomic_writes(root):
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-950")
    manager.claim("H-950", "codex")
    manager.accept("H-950", "codex")

    base = root / ".maestro" / "handoffs"
    leftovers = [p.name for p in base.iterdir() if ".tmp-" in p.name]
    check_eq(leftovers, [], "T14 no temp files left behind")

    # The record is valid JSON with a trailing newline.
    with open(base / "H-950.json", "r", encoding="utf-8") as handle:
        text = handle.read()
    check(text.endswith("\n"), "T14 record ends with a newline")
    json.loads(text)

    # Storage paths live entirely under .maestro/handoffs/.
    check(manager.storage.claims_dir.is_dir(), "T14 claims dir under base")
    check_eq(
        manager.storage.claims_dir.parent, base, "T14 claims dir is inside the base dir"
    )
    check_eq(
        manager.storage.workstreams_dir.parent,
        base,
        "T14 workstreams dir is inside the base dir",
    )


def t15_no_io_on_construction(root):
    """Constructors must not touch the filesystem."""
    empty = root / "untouched"
    empty.mkdir()
    HandoffManager(empty)
    WorkstreamRegistry(empty)
    check_eq(
        sorted(os.listdir(empty)), [], "T15 constructors must not create directories"
    )

    # Reading from a repo with no .maestro at all degrades gracefully.
    check_eq(HandoffManager(empty).list_open(), [], "T15 list_open on empty tree")
    check_eq(WorkstreamRegistry(empty).list_active(), [], "T15 list_active on empty tree")
    check_eq(WorkstreamRegistry(empty).lease_holder("WS-x"), None, "T15 no lease holder")


def t16_state_machine_table(root):
    """Only the four documented transitions exist."""
    from packages.core.handoff import ALLOWED_TRANSITIONS, TERMINAL_STATES

    expected = {
        (HandoffStatus.OPEN, HandoffStatus.CLAIMED),
        (HandoffStatus.OPEN, HandoffStatus.EXPIRED),
        (HandoffStatus.OPEN, HandoffStatus.CANCELLED),
        (HandoffStatus.CLAIMED, HandoffStatus.ACCEPTED),
    }
    check_eq(set(ALLOWED_TRANSITIONS), expected, "T16 transition table")
    check_eq(
        set(TERMINAL_STATES),
        {HandoffStatus.ACCEPTED, HandoffStatus.EXPIRED, HandoffStatus.CANCELLED},
        "T16 terminal states",
    )

    # A handoff carried through the full happy path.
    manager = HandoffManager(root)
    make_handoff(manager, handoff_id="H-960")
    check_eq(manager.load("H-960").status, HandoffStatus.OPEN, "T16 open")
    manager.claim("H-960", "codex")
    check_eq(manager.load("H-960").status, HandoffStatus.CLAIMED, "T16 claimed")
    manager.accept("H-960", "codex")
    check_eq(manager.load("H-960").status, HandoffStatus.ACCEPTED, "T16 accepted")


def t17_dataclass_shapes(root):
    """Sanity on the typed surface exported by the package."""
    snapshot = StateSnapshot()
    check_eq(snapshot.completed, [], "T17 snapshot defaults to empty lists")
    check_eq(snapshot.checkpoint.branch, "", "T17 checkpoint default")

    round_tripped = StateSnapshot.from_dict(sample_snapshot().to_dict())
    check_eq(round_tripped.to_dict(), sample_snapshot().to_dict(), "T17 snapshot round-trip")

    workstream = Workstream.from_dict({"id": "WS-9", "name": "x"})
    check_eq(workstream.id, "WS-9", "T17 workstream from_dict")
    expect_raises(
        ValueError, lambda: Workstream.from_dict({"name": "no id"}), "T17 workstream needs id"
    )

    # A bare string where a list is expected is a mistake, not a one-element list.
    expect_raises(
        ValueError,
        lambda: StateSnapshot.from_dict({"completed": "just one"}),
        "T17 string is not a list",
    )

    manager = HandoffManager(root)
    handoff = make_handoff(manager, handoff_id="H-970")
    check(isinstance(handoff.status, HandoffStatus), "T17 status is an enum")
    check_eq(handoff.status.value, "open", "T17 enum serializes to its value")
    check(handoff.claimable_by("anyone"), "T17 'any' is claimable by anyone")
    check(not handoff.is_terminal, "T17 open is not terminal")


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------


def main():
    print("F13-01 -- handoff, claim, workstreams, cross-agent resume")
    print("-" * 62)

    tests = [
        ("T01 create -> open", t01_create),
        ("T02 claim exactly-once", t02_claim_exactly_once),
        ("T03 accept", t03_accept),
        ("T03b accept requires the claimer", t03b_accept_wrong_agent),
        ("T04 cancel", t04_cancel),
        ("T04b cannot cancel a claimed handoff", t04b_cannot_cancel_claimed),
        ("T05 load round-trip", t05_load),
        ("T06 list_open", t06_list_open),
        ("T07 schema validation", t07_validation),
        ("T08 cross-agent resume", t08_cross_agent_resume),
        ("T08b addressed handoff is private", t08b_addressed_handoff_is_private),
        ("T09 lease is exclusive", t09_lease_exclusive),
        ("T10 lease release", t10_lease_release),
        ("T10b expired lease reclaim", t10b_expired_lease_is_reclaimable),
        ("T11 workstream independence", t11_workstream_independence),
        ("T12 rename keeps identity", t12_rename_does_not_break_identity),
        ("T13 sweep_expired", t13_sweep_expired),
        ("T14 atomic writes", t14_atomic_writes),
        ("T15 no I/O on construction", t15_no_io_on_construction),
        ("T16 state machine table", t16_state_machine_table),
        ("T17 dataclass shapes", t17_dataclass_shapes),
    ]

    for label, fn in tests:
        run(label, fn)

    print("-" * 62)
    total = _PASSED + len(_FAILURES)
    if _FAILURES:
        print(f"{len(_FAILURES)} of {total} tests FAILED\n")
        for label, _err, tb in _FAILURES:
            print(f"--- {label} ---")
            print(tb)
        return 1

    print(f"{_PASSED} of {total} tests passed")
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
