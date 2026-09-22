"""Append-only audit trail for improvement proposals.

Every creation and every state transition is recorded as one JSON object per
line in ``.maestro/proposals/audit.jsonl``.

Append-only is enforced by construction, not by convention: this class exposes
no delete, clear, truncate or rewrite, and never opens the file in a mode that
can shorten it. An audit trail you can edit is not an audit trail.

No I/O at import time. Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import SCHEMA_VERSION, utc_now
from .storage import ProposalStorage

#: Events written by ProposalEngine.
EVENT_CREATED = "created"
EVENT_APPROVED = "approved"
EVENT_REJECTED = "rejected"
EVENT_IMPLEMENTED = "implemented"
EVENT_EVAL_FAILED = "eval_failed"


class AuditTrail:
    """Append-only JSONL trail over `.maestro/proposals/audit.jsonl`."""

    def __init__(
        self,
        root: Optional[Path] = None,
        storage: Optional[ProposalStorage] = None,
    ) -> None:
        # No I/O here: the file is created on the first append.
        self._storage = storage if storage is not None else ProposalStorage(root)

    @property
    def path(self) -> Path:
        return self._storage.audit_path

    def append(
        self,
        event: str,
        proposal_id: str,
        *,
        actor: str = "",
        status: Optional[str] = None,
        detail: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append one event. Returns the record as written."""
        record: Dict[str, Any] = {
            "ts": utc_now(),
            "event": str(event),
            "proposal_id": str(proposal_id),
            "actor": str(actor or ""),
            "status": status,
            "detail": str(detail or ""),
            "schema_version": SCHEMA_VERSION,
        }
        if extra:
            for key, value in extra.items():
                if key not in record:
                    record[key] = value
        self._storage.append_line(
            self.path, json.dumps(record, ensure_ascii=False, sort_keys=False)
        )
        return record

    def read_all(self) -> List[Dict[str, Any]]:
        """Every event, in write order.

        A corrupt line is skipped rather than raised: one bad line must not
        erase the readable history around it.
        """
        events: List[Dict[str, Any]] = []
        for line in self._storage.read_lines(self.path):
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return events

    def for_proposal(self, proposal_id: str) -> List[Dict[str, Any]]:
        """Events for one proposal, in chronological (write) order."""
        target = str(proposal_id)
        return [
            event for event in self.read_all() if event.get("proposal_id") == target
        ]
