"""MemoryCore -- single entry point for all memory operations.

Markdown is source of truth, SQLite is a reconstructible index.
No external dependencies -- stdlib only (Python 3.9+).
No I/O at module level.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from packages.core.memory.schema import (
    AUTHORITY_RANK,
    DECAY_DEFAULTS,
    VALID_TYPES,
    extract_title,
    now_iso,
    parse_frontmatter,
    parse_iso,
    serialize_frontmatter,
    validate_frontmatter,
)
from packages.core.memory.index import MemoryIndex
from packages.core.memory.lock import MemoryLock


class MemoryError(Exception):
    """Single exception raised by the memory module."""


class MemoryCore:
    """The single gateway for reading and writing memories in .maestro/memory/.

    All interactions with memory files and the SQLite index go through this class.
    """

    def __init__(self, root=None):
        if root is not None:
            self._root = Path(root)
        else:
            # Import lazily to avoid I/O at import time
            from scripts.maestro_state import state_dir
            self._root = state_dir() / "memory"

        self._index = MemoryIndex(self._root / "index.db")
        self._lock = MemoryLock(self._root / "index.lock")
        # Throttle tracking: {memory_id: last_reinforcement_monotonic_time}
        self._last_reinforcement = {}

    # --- Lifecycle ---

    def ensure_dirs(self) -> Path:
        """Create .maestro/memory/ and subdirectories if absent. Idempotent."""
        self._root.mkdir(parents=True, exist_ok=True)
        for subdir in VALID_TYPES:
            (self._root / subdir).mkdir(exist_ok=True)
        return self._root

    # --- Write ---

    def write(self, frontmatter: dict, body: str) -> Path:
        """Write a new memory file.

        Validates frontmatter, generates id/timestamps if absent,
        applies decay defaults, writes atomically, updates index.
        Returns path to created file.
        Raises MemoryError if frontmatter is invalid.
        """
        fm = dict(frontmatter)  # shallow copy

        # Generate id if absent
        if "id" not in fm:
            fm["id"] = str(uuid.uuid4())

        # Fill timestamps if absent
        ts_now = now_iso()
        if "created_at" not in fm:
            fm["created_at"] = ts_now
        if "updated_at" not in fm:
            fm["updated_at"] = ts_now

        # Default pinned
        if "pinned" not in fm:
            fm["pinned"] = False

        # Default tags
        if "tags" not in fm:
            fm["tags"] = ""

        # Apply decay default if not explicitly set
        if "decay_at" not in fm:
            mem_type = fm.get("type")
            if mem_type in DECAY_DEFAULTS:
                delta = DECAY_DEFAULTS[mem_type]
                if delta is not None:
                    created = parse_iso(fm["created_at"])
                    decay = created + delta
                    fm["decay_at"] = decay.strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    fm["decay_at"] = None
            else:
                fm["decay_at"] = None

        # Validate
        errors, warnings = validate_frontmatter(fm)
        if errors:
            raise MemoryError(
                "Invalid frontmatter: " + "; ".join(errors)
            )

        for w in warnings:
            print(f"Warning: {w}", file=sys.stderr)

        # Ensure dirs
        self.ensure_dirs()

        # Build file content
        content = serialize_frontmatter(fm) + "\n\n" + body
        if not content.endswith("\n"):
            content += "\n"

        # Determine path
        mem_type = fm["type"]
        mem_id = fm["id"]
        target = self._root / mem_type / f"{mem_id}.md"

        # Atomic write: tmp + os.replace
        tmp_path = target.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(str(tmp_path), str(target))

        # Update index under lock
        entry = self._build_index_entry(fm, body, target)
        with self._lock:
            self._index.upsert(entry)

        return target

    def patch(self, memory_id: str, updates: dict) -> Path:
        """Patch an existing memory's frontmatter.

        Reads the file, applies updates (shallow merge), revalidates,
        updates updated_at, writes atomically, updates index.
        Raises MemoryError if id not found or updates invalid.
        """
        result = self.read_raw(memory_id)
        if result is None:
            raise MemoryError(f"Memory '{memory_id}' not found")

        fm, body = result

        # Apply updates
        for k, v in updates.items():
            fm[k] = v

        # Always update timestamp
        fm["updated_at"] = now_iso()

        # Revalidate
        errors, warnings = validate_frontmatter(fm)
        if errors:
            raise MemoryError(
                "Invalid frontmatter after patch: " + "; ".join(errors)
            )

        for w in warnings:
            print(f"Warning: {w}", file=sys.stderr)

        # Determine path
        target = self._root / fm["type"] / f"{memory_id}.md"

        # Build content
        content = serialize_frontmatter(fm) + "\n\n" + body
        if not content.endswith("\n"):
            content += "\n"

        # Atomic write
        tmp_path = target.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(str(tmp_path), str(target))

        # Update index
        entry = self._build_index_entry(fm, body, target)
        with self._lock:
            self._index.upsert(entry)

        return target

    def supersede(self, old_id: str, new_frontmatter: dict, new_body: str) -> Path:
        """Create a new memory that supersedes an old one.

        Validates authority: new must be >= old.
        Creates new memory with supersedes=old_id.
        Marks old as is_superseded in the index.
        Returns path to new memory.
        """
        old_result = self.read_raw(old_id)
        if old_result is None:
            raise MemoryError(f"Memory '{old_id}' not found for supersession")

        old_fm, _ = old_result
        old_authority = old_fm.get("authority", "inferred")
        new_authority = new_frontmatter.get("authority", "inferred")

        if AUTHORITY_RANK.get(new_authority, -1) < AUTHORITY_RANK.get(old_authority, -1):
            raise MemoryError(
                f"Cannot supersede memory with authority '{old_authority}' "
                f"by memory with authority '{new_authority}' "
                f"(equal or higher authority required)"
            )

        # Set supersedes field
        fm = dict(new_frontmatter)
        fm["supersedes"] = old_id

        # Write the new memory
        new_path = self.write(fm, new_body)

        # Mark old as superseded in the index
        with self._lock:
            self._index.mark_superseded(old_id)

        return new_path

    def delete(self, memory_id: str) -> bool:
        """Delete a memory file and its index entry.

        Returns True if deleted, False if not found.
        Raises MemoryError if memory is pinned.
        """
        result = self.read_raw(memory_id)
        if result is None:
            return False

        fm, _ = result
        if fm.get("pinned") is True:
            raise MemoryError(
                f"Cannot delete pinned memory '{memory_id}'"
            )

        # Remove file
        file_path = self._root / fm["type"] / f"{memory_id}.md"
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass

        # Remove from index
        with self._lock:
            self._index.remove(memory_id)

        return True

    # --- Read ---

    def read(self, memory_id: str):
        """Read a memory by id. Returns (frontmatter, body) or None.

        Increments access_count in the index if pinned=false (reinforcement).
        Throttle: max 1 reinforcement per memory per 60 seconds.
        """
        result = self.read_raw(memory_id)
        if result is None:
            return None

        fm, body = result

        # Reinforcement: only for non-pinned memories
        if not fm.get("pinned", False):
            now = time.monotonic()
            last = self._last_reinforcement.get(memory_id, 0)
            if now - last >= 60.0:
                self._last_reinforcement[memory_id] = now
                with self._lock:
                    self._index.increment_access(memory_id)

        return fm, body

    def read_raw(self, memory_id: str):
        """Read a memory without reinforcement. Returns (frontmatter, body) or None."""
        # Find the file on disk
        for mem_type in VALID_TYPES:
            path = self._root / mem_type / f"{memory_id}.md"
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    fm, body = parse_frontmatter(text)
                    return fm, body
                except (ValueError, OSError):
                    return None
        return None

    def exists(self, memory_id: str) -> bool:
        """True if the .md file exists on disk."""
        for mem_type in VALID_TYPES:
            path = self._root / mem_type / f"{memory_id}.md"
            if path.exists():
                return True
        return False

    def list_memories(
        self,
        type: str | None = None,
        authority: str | None = None,
        include_expired: bool = False,
        include_superseded: bool = False,
    ) -> list[dict]:
        """Query the SQLite index with optional filters.

        Returns list of dicts (frontmatter + access_count + last_accessed_at).
        Excludes expired and superseded by default.
        Ordered by updated_at DESC.
        """
        return self._index.query(
            type_filter=type,
            authority_filter=authority,
            include_expired=include_expired,
            include_superseded=include_superseded,
        )

    # --- Decay ---

    def is_expired(self, memory_id: str) -> bool:
        """True if decay_at is in the past. Pinned memories never expire."""
        result = self.read_raw(memory_id)
        if result is None:
            return False

        fm, _ = result
        if fm.get("pinned") is True:
            return False

        decay_at = fm.get("decay_at")
        if decay_at is None:
            return False

        try:
            decay_dt = parse_iso(decay_at)
            return datetime.now(timezone.utc) > decay_dt
        except (ValueError, TypeError):
            return False

    def list_expired(self) -> list[dict]:
        """Return all memories with decay_at in the past (excluding pinned)."""
        all_entries = self._index.query(
            include_expired=True, include_superseded=True
        )
        now = now_iso()
        expired = []
        for entry in all_entries:
            if entry.get("pinned") == 1:
                continue
            decay_at = entry.get("decay_at")
            if decay_at is not None and decay_at < now:
                expired.append(entry)
        return expired

    # --- Index ---

    def rebuild_index(self):
        """Rebuild index.db from scratch by scanning all .md files.

        Returns (total_files, total_errors).
        Errors are printed to stderr but don't stop the rebuild.
        """
        start_ms = time.monotonic()

        with self._lock:
            self._index.drop_all()

        total_files = 0
        total_errors = 0

        for mem_type in VALID_TYPES:
            type_dir = self._root / mem_type
            if not type_dir.exists():
                continue
            for md_file in sorted(type_dir.glob("*.md")):
                total_files += 1
                try:
                    text = md_file.read_text(encoding="utf-8")
                    fm, body = parse_frontmatter(text)
                    errors, _ = validate_frontmatter(fm)
                    if errors:
                        total_errors += 1
                        print(
                            f"rebuild: skipping {md_file}: {'; '.join(errors)}",
                            file=sys.stderr,
                        )
                        continue

                    # Verify id matches filename
                    file_id = md_file.stem
                    if fm.get("id") != file_id:
                        total_errors += 1
                        print(
                            f"rebuild: skipping {md_file}: id mismatch "
                            f"(frontmatter={fm.get('id')!r}, filename={file_id!r})",
                            file=sys.stderr,
                        )
                        continue

                    entry = self._build_index_entry(fm, body, md_file)
                    # Reset reinforcement data on rebuild
                    entry["access_count"] = 0
                    entry["last_accessed_at"] = None

                    with self._lock:
                        self._index.upsert(entry)

                except Exception as exc:
                    total_errors += 1
                    print(
                        f"rebuild: error processing {md_file}: {exc}",
                        file=sys.stderr,
                    )

        duration_ms = int((time.monotonic() - start_ms) * 1000)
        with self._lock:
            self._index.log_rebuild(total_files, total_errors, duration_ms)

        # Handle supersession chains: mark entries that are superseded
        with self._lock:
            all_entries = self._index.all_entries()
            superseded_ids = set()
            for e in all_entries:
                if e.get("supersedes"):
                    superseded_ids.add(e["supersedes"])
            for sid in superseded_ids:
                self._index.mark_superseded(sid)

        return total_files, total_errors

    def verify_index(self) -> list[str]:
        """Compare index with files on disk.

        Returns list of divergences. Empty list = index is consistent.
        """
        divergences = []

        # Files on disk
        disk_ids = {}
        for mem_type in VALID_TYPES:
            type_dir = self._root / mem_type
            if not type_dir.exists():
                continue
            for md_file in type_dir.glob("*.md"):
                file_id = md_file.stem
                disk_ids[file_id] = md_file

        # IDs in index
        index_entries = {e["id"]: e for e in self._index.all_entries()}

        # Files without index entry
        for fid in disk_ids:
            if fid not in index_entries:
                divergences.append(f"File without index entry: {disk_ids[fid]}")

        # Index entries without file
        for iid in index_entries:
            if iid not in disk_ids:
                divergences.append(f"Index entry without file: {iid}")

        # Hash divergences
        for fid in disk_ids:
            if fid in index_entries:
                file_content = disk_ids[fid].read_text(encoding="utf-8")
                file_hash = hashlib.sha256(
                    file_content.encode("utf-8")
                ).hexdigest()
                if file_hash != index_entries[fid]["file_hash"]:
                    divergences.append(
                        f"Hash mismatch for {fid}: "
                        f"disk={file_hash}, index={index_entries[fid]['file_hash']}"
                    )

        return divergences

    # --- Validation ---

    def validate_file(self, path: Path):
        """Validate a memory Markdown file. Returns (errors, warnings)."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, IOError) as exc:
            return [f"Cannot read file: {exc}"], []

        try:
            fm, body = parse_frontmatter(text)
        except ValueError as exc:
            return [str(exc)], []

        errors, warnings = validate_frontmatter(fm)

        # Check id matches filename
        file_id = path.stem
        fm_id = fm.get("id")
        if fm_id is not None and fm_id != file_id:
            errors.append(
                f"id mismatch: frontmatter says '{fm_id}', "
                f"filename says '{file_id}'"
            )

        return errors, warnings

    def validate_all(self):
        """Validate all .md files. Returns dict[path_str -> (errors, warnings)]."""
        results = {}
        for mem_type in VALID_TYPES:
            type_dir = self._root / mem_type
            if not type_dir.exists():
                continue
            for md_file in sorted(type_dir.glob("*.md")):
                results[str(md_file)] = self.validate_file(md_file)
        return results

    # --- Internal helpers ---

    def _build_index_entry(self, fm: dict, body: str, file_path: Path) -> dict:
        """Build an index entry dict from frontmatter, body, and file path."""
        content = file_path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        stat = file_path.stat()

        rel_path = str(file_path.relative_to(self._root))

        return {
            "id": fm["id"],
            "type": fm["type"],
            "authority": fm["authority"],
            "created_at": fm["created_at"],
            "updated_at": fm["updated_at"],
            "decay_at": fm.get("decay_at"),
            "pinned": fm.get("pinned", False),
            "supersedes": fm.get("supersedes"),
            "is_superseded": False,
            "tags": fm.get("tags", ""),
            "source_block": fm.get("source_block"),
            "source_agent": fm.get("source_agent"),
            "file_path": rel_path,
            "file_hash": file_hash,
            "file_size": stat.st_size,
            "file_mtime": stat.st_mtime,
            "indexed_at": now_iso(),
            "access_count": 0,
            "last_accessed_at": None,
            "title": extract_title(body),
            "module": fm.get("modulo"),
            "resultado": fm.get("resultado"),
        }
