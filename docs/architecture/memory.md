# Memory Architecture

## Overview

The Maestro memory system uses **Markdown as source of truth** and **SQLite as a reconstructible index**. Memory belongs to the project, not to any specific agent.

## Directory Structure

```
.maestro/memory/
  working/          # Short-lived context (default decay: 24h)
  episodic/         # Session records (default decay: 30 days)
  semantic/         # Concepts, decisions, patterns (no decay)
  procedural/       # How-to knowledge (no decay)
  index.db          # SQLite index (WAL mode)
  index.lock        # Interprocess lock file
```

## File Format

Each memory is a Markdown file with YAML frontmatter:

```
.maestro/memory/<type>/<uuid4>.md
```

### Frontmatter Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID4 string | Yes | Globally unique identifier |
| `type` | enum | Yes | working, episodic, semantic, procedural |
| `authority` | enum | Yes | project, session, inferred |
| `created_at` | ISO-8601 UTC | Yes | Creation timestamp |
| `updated_at` | ISO-8601 UTC | Yes | Last update timestamp |
| `decay_at` | ISO-8601 UTC or null | Yes | Expiration timestamp |
| `pinned` | boolean | Yes | If true, never expires and not deleted |
| `supersedes` | UUID4 or null | No | ID of superseded memory |
| `tags` | comma-separated string | No | Categorization tags |
| `source_block` | string or null | No | Originating block ID |
| `source_agent` | string or null | No | Originating agent name |

## SQLite Index

File: `.maestro/memory/index.db` (WAL mode for concurrent reads).

### Table: memories

All frontmatter fields plus derived fields:

- `is_superseded` (0/1) -- set when another memory supersedes this one
- `file_path` -- relative path from memory root
- `file_hash` -- SHA-256 of file content
- `file_size`, `file_mtime` -- filesystem metadata
- `indexed_at` -- timestamp of indexing
- `access_count` -- reinforcement counter (index-only, lost on rebuild)
- `last_accessed_at` -- last read timestamp (index-only, lost on rebuild)
- `title` -- extracted from first `# Heading` in body

### Table: rebuild_log

Records each `rebuild_index()` invocation with timestamp, file/error counts, and duration.

### Table: schema_version

Single row with version=1. Used for future migrations.

## Invariants

1. **Markdown is source of truth.** SQLite is derived and reconstructible.
2. **Atomic writes.** All file writes use tmp + `os.replace()`.
3. **Validation before write.** Invalid frontmatter is never persisted.
4. **Non-destructive reads.** `read()` and `read_raw()` return None for missing files.
5. **Frontmatter/body separation.** Parser never interprets body as YAML.
6. **Agent-agnostic.** No agent name is a functional requirement.
7. **Idempotent rebuild.** Same files produce same index (except timestamps and reinforcement).
8. **Fail-closed.** Ambiguous input is always an error.
9. **No external deps.** stdlib Python 3.9+ only.
10. **No I/O on import.** All I/O happens in instance methods.

## Authority Levels

```
project   (highest)  -- project owner decisions
session   (medium)   -- session-specific context
inferred  (lowest)   -- automatically learned
```

Supersession rule: a memory can only be superseded by one with equal or higher authority.

## Decay and Reinforcement

- `working` memories decay after 24 hours by default
- `episodic` memories decay after 30 days by default
- `semantic` and `procedural` memories have no default decay
- Pinned memories never expire regardless of `decay_at`
- Expired memories stay on disk but are excluded from default queries
- Each `read()` increments `access_count` (throttled: max 1 per 60s per memory)
- Pinned memories do not receive reinforcement
- `access_count` and `last_accessed_at` live only in the index

## Concurrency

- `MemoryLock` provides interprocess file locking for SQLite writes
- Uses `msvcrt.locking` on Windows, `fcntl.flock` on Unix
- Reads do not acquire the lock (WAL mode allows concurrent reads)
- Timeout: 10 seconds (raises `MemoryError` on failure)

## Write Sequence

```
1. Validate frontmatter
2. Write .md file atomically (tmp + os.replace)
3. Acquire MemoryLock
4. Update SQLite index
5. Release MemoryLock
```

Crash between steps 2 and 3: file exists but index is stale. `rebuild_index()` corrects this.

## API Entry Point

All access goes through `MemoryCore`:

```python
from packages.core.memory import MemoryCore

mc = MemoryCore(".maestro/memory")
mc.ensure_dirs()
path = mc.write({"type": "semantic", "authority": "project"}, "# My Decision\n\nContent here.")
fm, body = mc.read(memory_id)
```
