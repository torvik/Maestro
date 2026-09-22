"""HandoffManager -- create, claim, accept, cancel, load and list handoffs.

The state machine is the contract::

    open ---claim()---> claimed ---accept()---> accepted
    open ---cancel()--> cancelled
    open ---sweep_expired()--> expired

Nothing else is allowed. In particular ``cancel()`` on a *claimed* handoff
fails: cancelling work another agent already started is the exact failure this
module exists to prevent.

No I/O at import time. Stdlib only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from packages.core.handoff.schema import (
    ClaimError,
    Handoff,
    HandoffExistsError,
    HandoffNotFoundError,
    HandoffStatus,
    InvalidTransitionError,
    ResumePacket,
    StateSnapshot,
    check_transition,
    generate_handoff_id,
    is_past,
    utc_now,
    validate_handoff,
    validate_id,
)
from packages.core.handoff.storage import HandoffStorage


class HandoffManager:
    """Typed handoff lifecycle backed by ``.maestro/handoffs/``."""

    def __init__(self, root: Optional[Path] = None) -> None:
        # No I/O here; the storage layer creates directories on demand.
        self._storage = HandoffStorage(root)

    @property
    def storage(self) -> HandoffStorage:
        return self._storage

    @property
    def base_dir(self) -> Path:
        return self._storage.base_dir

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        from_agent: str,
        to_agent: str,
        block_id: str,
        context_summary: str,
        state_snapshot: Optional[Union[StateSnapshot, Dict[str, Any]]] = None,
        open_questions: Optional[List[str]] = None,
        project: str = "",
        workstream: Optional[str] = None,
        summary: str = "",
        expires_at: Optional[str] = None,
        handoff_id: Optional[str] = None,
    ) -> Handoff:
        """Validate and persist a new handoff with status ``open``.

        Raises ValueError when a required field is missing/blank or the id is
        malformed, and HandoffExistsError when the id is already taken --
        create() never overwrites an existing record.
        """
        new_id = validate_id(handoff_id, "id") if handoff_id else generate_handoff_id()
        now = utc_now()

        payload: Dict[str, Any] = {
            "id": new_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "block_id": block_id,
            "context_summary": context_summary,
            "state_snapshot": StateSnapshot.from_dict(state_snapshot).to_dict(),
            "open_questions": list(open_questions or []),
            "project": project,
            "workstream": workstream,
            "summary": summary,
            "status": HandoffStatus.OPEN.value,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }

        # Validate before touching the filesystem: an invalid handoff is never
        # written (acceptance criterion 6).
        handoff = validate_handoff(Handoff.from_dict(payload))

        path = self._storage.handoff_path(handoff.id)
        if path.exists():
            raise HandoffExistsError(f"handoff '{handoff.id}' already exists at {path}")

        self._storage.write_json(path, handoff.to_dict())
        return handoff

    # ------------------------------------------------------------------
    # read
    # ------------------------------------------------------------------

    def load(self, handoff_id: str) -> Handoff:
        """Read a handoff from disk.

        HandoffNotFoundError when absent; ValueError when the file exists but
        violates the schema (a corrupt record is never silently repaired).
        """
        safe_id = validate_id(handoff_id, "handoff_id")
        path = self._storage.handoff_path(safe_id)
        if not path.is_file():
            raise HandoffNotFoundError(f"handoff '{safe_id}' not found at {path}")
        data = self._storage.read_json(path)
        if data is None:
            raise ValueError(f"handoff '{safe_id}' is not readable JSON: {path}")
        return validate_handoff(Handoff.from_dict(data))

    def list_open(
        self,
        for_agent: Optional[str] = None,
        workstream: Optional[str] = None,
    ) -> List[Handoff]:
        """Open handoffs, oldest first.

        `for_agent` keeps only handoffs addressed to that agent or to "any".
        `workstream` filters by workstream_id.
        A corrupt file is skipped, never raised -- one bad record must not
        blind an agent to every other pending handoff.
        """
        results: List[Handoff] = []
        for handoff_id in self._storage.list_handoff_ids():
            data = self._storage.read_json(self._storage.handoff_path(handoff_id))
            if data is None:
                continue
            try:
                handoff = Handoff.from_dict(data)
            except ValueError:
                continue
            if handoff.status != HandoffStatus.OPEN:
                continue
            if for_agent is not None and not handoff.claimable_by(for_agent):
                continue
            if workstream is not None and handoff.workstream != workstream:
                continue
            results.append(handoff)
        results.sort(key=lambda item: (item.created_at, item.id))
        return results

    # ------------------------------------------------------------------
    # claim -- exactly-once
    # ------------------------------------------------------------------

    def claim(self, handoff_id: str, agent: str) -> ResumePacket:
        """Claim a handoff exactly once and return the resume packet.

        Three phases:

        1. **reserve** -- create ``.claims/<ID>.claim`` with O_EXCL. Exactly
           one caller wins; every other caller gets ClaimError.
        2. **assemble** -- load, validate and build the ResumePacket in memory.
        3. **commit** -- atomically write status=claimed.

        Fail-closed: if phase 2 or 3 raises, the reservation marker is removed
        and the handoff stays ``open``. A failed delivery never strands work.

        On success the marker is kept on purpose -- it is the durable proof
        that this handoff was already delivered.
        """
        safe_id = validate_id(handoff_id, "handoff_id")
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("agent is required and must be a non-empty string")
        agent = agent.strip()

        claimed_at = utc_now()
        claim_file = self._storage.claim_path(safe_id)

        # Phase 1 -- reserve.
        won = self._storage.create_exclusive(
            claim_file,
            {
                "handoff_id": safe_id,
                "agent": agent,
                "claimed_at": claimed_at,
                "pid": os.getpid(),
            },
        )
        if not won:
            raise ClaimError(
                f"handoff '{safe_id}' was already claimed; "
                "claims are exactly-once and are never re-delivered"
            )

        try:
            # Phase 2 -- assemble. Every check happens before any write.
            handoff = self.load(safe_id)

            if handoff.status != HandoffStatus.OPEN:
                raise InvalidTransitionError(
                    f"handoff '{safe_id}' is '{handoff.status.value}', "
                    "only 'open' handoffs can be claimed"
                )
            if not handoff.claimable_by(agent):
                raise ClaimError(
                    f"handoff '{safe_id}' is addressed to '{handoff.to_agent}', "
                    f"not to '{agent}'"
                )
            if is_past(handoff.expires_at, claimed_at):
                raise InvalidTransitionError(
                    f"handoff '{safe_id}' expired at {handoff.expires_at}"
                )

            check_transition(handoff.status, HandoffStatus.CLAIMED)
            packet = ResumePacket.assemble(handoff, agent, claimed_at)

            # Phase 3 -- commit.
            handoff.status = HandoffStatus.CLAIMED
            handoff.claimed_by = agent
            handoff.claimed_at = claimed_at
            handoff.updated_at = claimed_at
            self._storage.write_json(
                self._storage.handoff_path(safe_id), handoff.to_dict()
            )
        except BaseException:
            # Fail-closed rollback: drop the reservation so the handoff stays
            # open and claimable by someone else.
            self._storage.delete(claim_file)
            raise

        packet.handoff = handoff
        return packet

    # ------------------------------------------------------------------
    # accept / cancel / expire
    # ------------------------------------------------------------------

    def accept(self, handoff_id: str, agent: str) -> Handoff:
        """Transition claimed -> accepted. Only the claiming agent may accept."""
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("agent is required and must be a non-empty string")
        agent = agent.strip()

        handoff = self.load(handoff_id)
        check_transition(handoff.status, HandoffStatus.ACCEPTED)
        if handoff.claimed_by != agent:
            raise ClaimError(
                f"handoff '{handoff.id}' was claimed by '{handoff.claimed_by}', "
                f"'{agent}' cannot accept it"
            )

        now = utc_now()
        handoff.status = HandoffStatus.ACCEPTED
        handoff.accepted_by = agent
        handoff.accepted_at = now
        handoff.updated_at = now
        self._storage.write_json(
            self._storage.handoff_path(handoff.id), handoff.to_dict()
        )
        return handoff

    def cancel(self, handoff_id: str, reason: str = "") -> Handoff:
        """Transition open -> cancelled.

        A claimed handoff cannot be cancelled: another agent may already be
        executing it. Abandoned claims are released by the workstream lease TTL.
        """
        handoff = self.load(handoff_id)
        check_transition(handoff.status, HandoffStatus.CANCELLED)

        now = utc_now()
        handoff.status = HandoffStatus.CANCELLED
        handoff.cancel_reason = reason or ""
        handoff.updated_at = now
        self._storage.write_json(
            self._storage.handoff_path(handoff.id), handoff.to_dict()
        )
        return handoff

    def sweep_expired(self, now: Optional[str] = None) -> List[str]:
        """Move every open handoff past its expires_at to ``expired``.

        Returns the ids that were transitioned.
        """
        reference = now or utc_now()
        transitioned: List[str] = []
        for handoff in self.list_open():
            if not is_past(handoff.expires_at, reference):
                continue
            check_transition(handoff.status, HandoffStatus.EXPIRED)
            handoff.status = HandoffStatus.EXPIRED
            handoff.updated_at = reference
            self._storage.write_json(
                self._storage.handoff_path(handoff.id), handoff.to_dict()
            )
            transitioned.append(handoff.id)
        return transitioned
