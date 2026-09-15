"""SQLite index manager for memory files.

Manages .maestro/memory/index.db with WAL mode.
No external dependencies -- stdlib only (Python 3.9+).
No I/O at module level.
"""

import sqlite3
from pathlib import Path

from packages.core.memory.schema import now_iso

# --- SQL Statements ---

_CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    authority       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    decay_at        TEXT,
    pinned          INTEGER NOT NULL DEFAULT 0,
    supersedes      TEXT,
    is_superseded   INTEGER NOT NULL DEFAULT 0,
    tags            TEXT DEFAULT '',
    source_block    TEXT,
    source_agent    TEXT,
    file_path       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    file_size       INTEGER NOT NULL,
    file_mtime      REAL NOT NULL,
    indexed_at      TEXT NOT NULL,
    access_count    INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT,
    title           TEXT DEFAULT ''
)
"""

_CREATE_REBUILD_LOG = """
CREATE TABLE IF NOT EXISTS rebuild_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rebuilt_at  TEXT NOT NULL,
    total_files INTEGER NOT NULL,
    total_errors INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
)
"""

_CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
)
"""

_CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)",
    "CREATE INDEX IF NOT EXISTS idx_memories_authority ON memories(authority)",
    "CREATE INDEX IF NOT EXISTS idx_memories_decay ON memories(decay_at) WHERE decay_at IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memories_supersedes ON memories(supersedes) WHERE supersedes IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memories_is_superseded ON memories(is_superseded) WHERE is_superseded = 1",
    "CREATE INDEX IF NOT EXISTS idx_memories_source_block ON memories(source_block) WHERE source_block IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memories_access_count ON memories(access_count)",
]


class MemoryIndex:
    """Manages the SQLite index for memory files."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn = None

    def _ensure_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._init_schema()
        return self._conn

    def connection(self) -> sqlite3.Connection:
        """Return the underlying SQLite connection (for extensions like F11-03)."""
        return self._ensure_connection()

    def _init_schema(self):
        conn = self._conn
        conn.execute(_CREATE_MEMORIES)
        conn.execute(_CREATE_REBUILD_LOG)
        conn.execute(_CREATE_SCHEMA_VERSION)
        for idx_sql in _CREATE_INDICES:
            conn.execute(idx_sql)
        # Insert schema version if not present
        existing = conn.execute(
            "SELECT version FROM schema_version WHERE version = 1"
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO schema_version VALUES (1, ?)", (now_iso(),)
            )
        conn.commit()

    def upsert(self, entry: dict):
        """Insert or replace a memory entry in the index."""
        conn = self._ensure_connection()
        conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, type, authority, created_at, updated_at, decay_at,
                pinned, supersedes, is_superseded, tags, source_block,
                source_agent, file_path, file_hash, file_size, file_mtime,
                indexed_at, access_count, last_accessed_at, title)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry["id"],
                entry["type"],
                entry["authority"],
                entry["created_at"],
                entry["updated_at"],
                entry.get("decay_at"),
                1 if entry.get("pinned") else 0,
                entry.get("supersedes"),
                1 if entry.get("is_superseded") else 0,
                entry.get("tags", ""),
                entry.get("source_block"),
                entry.get("source_agent"),
                entry["file_path"],
                entry["file_hash"],
                entry["file_size"],
                entry["file_mtime"],
                entry["indexed_at"],
                entry.get("access_count", 0),
                entry.get("last_accessed_at"),
                entry.get("title", ""),
            ),
        )
        conn.commit()

    def remove(self, memory_id: str):
        """Remove a memory entry from the index."""
        conn = self._ensure_connection()
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()

    def get(self, memory_id: str) -> dict | None:
        """Get a single memory entry by id."""
        conn = self._ensure_connection()
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def mark_superseded(self, memory_id: str):
        """Mark a memory as superseded in the index."""
        conn = self._ensure_connection()
        conn.execute(
            "UPDATE memories SET is_superseded = 1 WHERE id = ?", (memory_id,)
        )
        conn.commit()

    def increment_access(self, memory_id: str):
        """Increment access_count and update last_accessed_at."""
        conn = self._ensure_connection()
        conn.execute(
            """UPDATE memories
               SET access_count = access_count + 1,
                   last_accessed_at = ?
               WHERE id = ?""",
            (now_iso(), memory_id),
        )
        conn.commit()

    def query(
        self,
        type_filter: str | None = None,
        authority_filter: str | None = None,
        include_expired: bool = False,
        include_superseded: bool = False,
    ) -> list[dict]:
        """Query the index with optional filters."""
        conn = self._ensure_connection()
        conditions = []
        params = []

        if type_filter:
            conditions.append("type = ?")
            params.append(type_filter)

        if authority_filter:
            conditions.append("authority = ?")
            params.append(authority_filter)

        if not include_expired:
            conditions.append(
                "(decay_at IS NULL OR decay_at > ? OR pinned = 1)"
            )
            params.append(now_iso())

        if not include_superseded:
            conditions.append("is_superseded = 0")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = f"SELECT * FROM memories {where} ORDER BY updated_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def all_ids(self) -> set[str]:
        """Return set of all memory IDs in the index."""
        conn = self._ensure_connection()
        rows = conn.execute("SELECT id FROM memories").fetchall()
        return {r["id"] for r in rows}

    def all_entries(self) -> list[dict]:
        """Return all entries in the index."""
        conn = self._ensure_connection()
        rows = conn.execute("SELECT * FROM memories").fetchall()
        return [dict(r) for r in rows]

    def drop_all(self):
        """Drop and recreate the memories table (for rebuild)."""
        conn = self._ensure_connection()
        conn.execute("DROP TABLE IF EXISTS memories")
        conn.execute(_CREATE_MEMORIES)
        for idx_sql in _CREATE_INDICES:
            conn.execute(idx_sql)
        conn.commit()

    def log_rebuild(self, total_files: int, total_errors: int, duration_ms: int):
        """Log a rebuild operation."""
        conn = self._ensure_connection()
        conn.execute(
            "INSERT INTO rebuild_log (rebuilt_at, total_files, total_errors, duration_ms) "
            "VALUES (?, ?, ?, ?)",
            (now_iso(), total_files, total_errors, duration_ms),
        )
        conn.commit()

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
