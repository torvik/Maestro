"""WorkstreamRegistry -- logical lines of work plus exclusive execution leases.

A workstream groups blocks that belong to the same line of work inside a
project (``WS-auth-refactor``, ``WS-provider-routing``). Each workstream has
independent handoffs, so several can run at once.

Identity is ``workstream_id``. ``name`` is metadata: renaming it must never
break handoffs, leases or history, so nothing here indexes by name.

The lease gives one agent exclusive execution rights over a workstream, which
is what stops two agents from editing the same files at the same time. It is
fail-closed by design: releasing requires the owner token and there is no
force-release -- only the TTL can take a lease away from its holder.

No I/O at import time. Stdlib only.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from packages.core.handoff.schema import (
    Lease,
    LeaseError,
    Workstream,
    WorkstreamNotFoundError,
    is_past,
    parse_ts,
    utc_now,
    validate_id,
)
from packages.core.handoff.storage import HandoffStorage

DEFAULT_LEASE_TTL_SECONDS = 3600


class WorkstreamRegistry:
    """Registry of workstreams and their exclusive leases."""

    def __init__(self, root: Optional[Path] = None) -> None:
        # No I/O here; directories are created on demand.
        self._storage = HandoffStorage(root)

    @property
    def storage(self) -> HandoffStorage:
        return self._storage

    # ------------------------------------------------------------------
    # registry
    # ------------------------------------------------------------------

    def register(
        self,
        workstream_id: str,
        name: str = "",
        project: str = "",
        blocks: Optional[List[str]] = None,
    ) -> Workstream:
        """Create or update workstream metadata.

        Idempotent: re-registering preserves ``created_at`` and does not touch
        an active lease.
        """
        safe_id = validate_id(workstream_id, "workstream_id")
        now = utc_now()
        path = self._storage.workstream_path(safe_id)

        existing = self._storage.read_json(path)
        created_at = now
        status = "active"
        if existing is not None:
            created_at = str(existing.get("created_at") or now)
            status = str(existing.get("status") or "active")

        workstream = Workstream(
            id=safe_id,
            name=name,
            project=project,
            blocks=list(blocks or []),
            status=status,
            created_at=created_at,
            updated_at=now,
        )
        self._storage.write_json(path, workstream.to_dict())
        return workstream

    def get(self, workstream_id: str) -> Workstream:
        """Load a workstream. WorkstreamNotFoundError when unregistered."""
        safe_id = validate_id(workstream_id, "workstream_id")
        data = self._storage.read_json(self._storage.workstream_path(safe_id))
        if data is None:
            raise WorkstreamNotFoundError(f"workstream '{safe_id}' is not registered")
        return Workstream.from_dict(data)

    def list_active(self) -> List[Workstream]:
        """Every workstream with status 'active', ordered by id."""
        results: List[Workstream] = []
        for workstream_id in self._storage.list_workstream_ids():
            data = self._storage.read_json(
                self._storage.workstream_path(workstream_id)
            )
            if data is None:
                continue
            try:
                workstream = Workstream.from_dict(data)
            except ValueError:
                continue
            if workstream.status == "active":
                results.append(workstream)
        results.sort(key=lambda item: item.id)
        return results

    def close(self, workstream_id: str) -> Workstream:
        """Mark a workstream as closed. It stops showing up in list_active()."""
        workstream = self.get(workstream_id)
        workstream.status = "closed"
        workstream.updated_at = utc_now()
        self._storage.write_json(
            self._storage.workstream_path(workstream.id), workstream.to_dict()
        )
        return workstream

    # ------------------------------------------------------------------
    # leases
    # ------------------------------------------------------------------

    def lease_holder(self, workstream_id: str) -> Optional[Lease]:
        """The lease currently in force, or None when absent or expired.

        Read-only: never removes an expired lease.
        """
        safe_id = validate_id(workstream_id, "workstream_id")
        data = self._storage.read_json(self._storage.lease_path(safe_id))
        if data is None:
            return None
        lease = Lease.from_dict(data)
        if lease.is_expired:
            return None
        return lease

    def acquire_lease(
        self,
        workstream_id: str,
        agent: str,
        ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    ) -> Lease:
        """Acquire exclusive execution rights over a workstream.

        Returns a Lease carrying the token required to release it.

        LeaseError when a lease is already in force -- including one held by
        the same agent. Leases are not reentrant on purpose: a second acquire
        signals a coordination bug upstream and must not be masked.

        An expired lease is swept and replaced.
        """
        safe_id = validate_id(workstream_id, "workstream_id")
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("agent is required and must be a non-empty string")
        agent = agent.strip()
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")

        # Fail-closed: never lease a workstream that was never registered.
        if not self._storage.workstream_path(safe_id).is_file():
            raise WorkstreamNotFoundError(
                f"workstream '{safe_id}' is not registered; call register() first"
            )

        lease_file = self._storage.lease_path(safe_id)
        existing = self._storage.read_json(lease_file)
        if existing is not None:
            current = Lease.from_dict(existing)
            if not current.is_expired:
                raise LeaseError(
                    f"workstream '{safe_id}' is leased by '{current.agent}' "
                    f"until {current.expires_at}"
                )
            # Expired: sweep it so the slot can be taken again.
            self._storage.delete(lease_file)

        acquired_at = utc_now()
        started = parse_ts(acquired_at)
        expires_at = (started + timedelta(seconds=ttl_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        lease = Lease(
            workstream_id=safe_id,
            agent=agent,
            token=uuid.uuid4().hex,
            acquired_at=acquired_at,
            expires_at=expires_at,
        )

        # O_EXCL decides the race: exactly one caller creates the file.
        if not self._storage.create_exclusive(lease_file, lease.to_dict()):
            raise LeaseError(
                f"workstream '{safe_id}' was leased by another agent concurrently"
            )
        return lease

    def release_lease(self, workstream_id: str, token: str) -> None:
        """Release a lease using the owner token.

        No-op when no lease is present (release is idempotent).
        LeaseError when the token does not match -- an agent never drops
        someone else's lease, and there is no force-release.
        """
        safe_id = validate_id(workstream_id, "workstream_id")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token is required and must be a non-empty string")

        lease_file = self._storage.lease_path(safe_id)
        data = self._storage.read_json(lease_file)
        if data is None:
            return

        lease = Lease.from_dict(data)
        if lease.token != token.strip():
            raise LeaseError(
                f"token does not match the lease on workstream '{safe_id}'; "
                "only the holder can release it"
            )
        self._storage.delete(lease_file)

    def is_leased(self, workstream_id: str) -> bool:
        """True when a non-expired lease is in force."""
        return self.lease_holder(workstream_id) is not None

    def renew_lease(
        self,
        workstream_id: str,
        token: str,
        ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    ) -> Lease:
        """Extend an in-force lease. Only the holder token may renew."""
        safe_id = validate_id(workstream_id, "workstream_id")
        lease_file = self._storage.lease_path(safe_id)
        data = self._storage.read_json(lease_file)
        if data is None:
            raise LeaseError(f"workstream '{safe_id}' has no lease to renew")
        lease = Lease.from_dict(data)
        if lease.token != (token or "").strip():
            raise LeaseError(
                f"token does not match the lease on workstream '{safe_id}'"
            )
        if is_past(lease.expires_at):
            raise LeaseError(
                f"lease on workstream '{safe_id}' expired at {lease.expires_at}; "
                "acquire a new one"
            )
        now = parse_ts(utc_now())
        lease.expires_at = (now + timedelta(seconds=ttl_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self._storage.write_json(lease_file, lease.to_dict())
        return lease
