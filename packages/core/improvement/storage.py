"""Filesystem layer for improvement proposals.

Layout under <root>/.maestro/proposals/::

    <PROPOSAL_ID>.json     canonical record (source of truth)
    <PROPOSAL_ID>.md       human-readable sidecar (derived, never read back)
    audit.jsonl            append-only trail of every transition

Every ``.json`` and ``.md`` write is atomic: a temp file in the same directory
followed by ``os.replace``, which is atomic on POSIX and on Windows. A crash
never leaves a half-written proposal.

This module resolves paths under ``.maestro/proposals`` only. It has no notion
of ``plano/`` and must never gain one -- see acceptance criterion 6.

No I/O at import time. Stdlib only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

PROPOSALS_DIRNAME = "proposals"
AUDIT_FILENAME = "audit.jsonl"


class ProposalStorage:
    """Path resolution plus atomic read/write for the improvement package."""

    def __init__(self, root: Optional[Path] = None) -> None:
        # No I/O here: directories are created on demand.
        self._root = Path(root) if root is not None else Path.cwd()

    # -- paths ------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def base_dir(self) -> Path:
        return self._root / ".maestro" / PROPOSALS_DIRNAME

    def proposal_path(self, proposal_id: str) -> Path:
        return self.base_dir / f"{proposal_id}.json"

    def sidecar_path(self, proposal_id: str) -> Path:
        return self.base_dir / f"{proposal_id}.md"

    @property
    def audit_path(self) -> Path:
        return self.base_dir / AUDIT_FILENAME

    # -- generic I/O ------------------------------------------------------

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, body: str) -> None:
        self._ensure_dir(path.parent)
        tmp = path.parent / f"{path.name}.tmp-{os.getpid()}"
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            # Nothing is left behind if os.replace never ran.
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        """Atomically write `payload` as UTF-8 JSON to `path`."""
        body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        self._atomic_write(path, body)

    def write_text(self, path: Path, body: str) -> None:
        """Atomically write UTF-8 text to `path`."""
        self._atomic_write(path, body)

    def read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Read JSON from `path`. Returns None when absent or unreadable."""
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def exists(self, path: Path) -> bool:
        return path.exists()

    # -- append-only ------------------------------------------------------

    def append_line(self, path: Path, line: str) -> None:
        """Append one line to `path`, creating it on demand.

        Mode "a" only. There is deliberately no counterpart that opens the
        audit file for truncating writes.
        """
        self._ensure_dir(path.parent)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line.rstrip("\n") + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_lines(self, path: Path) -> List[str]:
        """Every line of `path`, in write order. Missing file -> []."""
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return [line for line in handle.read().splitlines() if line.strip()]
        except OSError:
            return []

    # -- listings ---------------------------------------------------------

    def list_proposal_ids(self) -> List[str]:
        """Ids of every proposal record, sorted. Missing directory -> []."""
        if not self.base_dir.is_dir():
            return []
        ids = []
        for entry in self.base_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json":
                ids.append(entry.stem)
        return sorted(ids)
