"""Filesystem layer for handoffs and workstreams.

Layout under <root>/.maestro/handoffs/::

    <HANDOFF_ID>.json              canonical handoff record
    .claims/<HANDOFF_ID>.claim     reservation marker (O_EXCL) -- exactly-once
    workstreams/<WS_ID>.json       workstream record
    workstreams/<WS_ID>.lease      active lease (O_EXCL + TTL)

Two primitives matter here:

* every ``.json`` write is atomic (temp file in the same directory followed by
  ``os.replace``, which is atomic on both POSIX and Windows), so a crash never
  leaves a half-written record;
* reservations and leases use ``os.open(..., O_CREAT | O_EXCL)``, the only
  cross-platform mutual-exclusion primitive available without a dependency.

No I/O at import time. Stdlib only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

HANDOFF_DIRNAME = os.path.join(".maestro", "handoffs")
CLAIMS_DIRNAME = ".claims"
WORKSTREAMS_DIRNAME = "workstreams"


class HandoffStorage:
    """Path resolution plus atomic read/write for the handoff package."""

    def __init__(self, root: Optional[Path] = None) -> None:
        # No I/O here: directories are created on demand.
        self._root = Path(root) if root is not None else Path.cwd()

    # -- paths ------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def base_dir(self) -> Path:
        return self._root / ".maestro" / "handoffs"

    @property
    def claims_dir(self) -> Path:
        return self.base_dir / CLAIMS_DIRNAME

    @property
    def workstreams_dir(self) -> Path:
        return self.base_dir / WORKSTREAMS_DIRNAME

    def handoff_path(self, handoff_id: str) -> Path:
        return self.base_dir / f"{handoff_id}.json"

    def claim_path(self, handoff_id: str) -> Path:
        return self.claims_dir / f"{handoff_id}.claim"

    def workstream_path(self, workstream_id: str) -> Path:
        return self.workstreams_dir / f"{workstream_id}.json"

    def lease_path(self, workstream_id: str) -> Path:
        return self.workstreams_dir / f"{workstream_id}.lease"

    # -- generic JSON I/O -------------------------------------------------

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        """Atomically write `payload` as UTF-8 JSON to `path`."""
        self._ensure_dir(path.parent)
        tmp = path.parent / f"{path.name}.tmp-{os.getpid()}"
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
                handle.write("\n")
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

    def delete(self, path: Path) -> None:
        """Remove `path` if present. Idempotent."""
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return

    def exists(self, path: Path) -> bool:
        return path.exists()

    # -- exclusive markers (O_EXCL) ---------------------------------------

    def create_exclusive(self, path: Path, payload: Dict[str, Any]) -> bool:
        """Create `path` only if it does not exist yet.

        Returns True when this process won the race, False when the file was
        already there. Never overwrites.
        """
        self._ensure_dir(path.parent)
        body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        except OSError:
            return False
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            # Could not finish writing the marker: do not leave a corpse that
            # would block every future attempt.
            self.delete(path)
            return False
        return True

    # -- listings ---------------------------------------------------------

    def list_handoff_ids(self) -> List[str]:
        """Ids of every handoff record, sorted. Missing directory -> []."""
        if not self.base_dir.is_dir():
            return []
        ids = []
        for entry in self.base_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json":
                ids.append(entry.stem)
        return sorted(ids)

    def list_workstream_ids(self) -> List[str]:
        """Ids of every workstream record, sorted. Missing directory -> []."""
        if not self.workstreams_dir.is_dir():
            return []
        ids = []
        for entry in self.workstreams_dir.iterdir():
            if entry.is_file() and entry.suffix == ".json":
                ids.append(entry.stem)
        return sorted(ids)
