"""ProceduralMemory -- sequencias de passos que funcionaram, agrupadas por
tipo de tarefa, para reutilizacao em execucoes futuras.

Toda tabela criada usa o prefixo `ext_`. Sem I/O no import nem no __init__.
"""

from __future__ import annotations

import json
import uuid

from packages.core.memory.core import MemoryCore
from packages.core.memory.schema import now_iso

_CREATE_PROCEDURAL = """
CREATE TABLE IF NOT EXISTS ext_procedural (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL,
    steps       TEXT NOT NULL,
    source_block TEXT,
    outcome     TEXT NOT NULL DEFAULT 'success',
    created_at  TEXT NOT NULL,
    used_count  INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_PROCEDURAL_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ext_proc_task_type ON ext_procedural(task_type)",
    "CREATE INDEX IF NOT EXISTS idx_ext_proc_outcome ON ext_procedural(outcome)",
]


class ProceduralMemory:
    """API especializada para procedural memory (sequencias de passos)."""

    def __init__(self, core: MemoryCore):
        self._core = core

    def ensure_schema(self) -> None:
        """Cria tabela ext_procedural se ausente. Idempotente."""
        conn = self._core._index.connection()
        conn.execute(_CREATE_PROCEDURAL)
        for sql in _CREATE_PROCEDURAL_INDICES:
            conn.execute(sql)
        conn.commit()

    def record(
        self,
        task_type: str,
        steps: list,
        source_block: str | None = None,
        outcome: str = "success",
    ) -> str:
        """Registra sequencia de passos. Retorna id."""
        self.ensure_schema()
        conn = self._core._index.connection()
        proc_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO ext_procedural
               (id, task_type, steps, source_block, outcome, created_at, used_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (
                proc_id,
                task_type,
                json.dumps(steps),
                source_block,
                outcome,
                now_iso(),
            ),
        )
        conn.commit()
        return proc_id

    def get_by_task_type(
        self,
        task_type: str,
        outcome: str = "success",
        limit: int = 5,
    ) -> list:
        """Retorna sequencias ordenadas por used_count desc, created_at desc."""
        self.ensure_schema()
        conn = self._core._index.connection()
        rows = conn.execute(
            """SELECT * FROM ext_procedural
               WHERE task_type = ? AND outcome = ?
               ORDER BY used_count DESC, created_at DESC
               LIMIT ?""",
            (task_type, outcome, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["steps"] = json.loads(d["steps"])
            except (TypeError, ValueError):
                pass
            results.append(d)
        return results

    def increment_used(self, proc_id: str) -> None:
        """Incrementa used_count de uma sequencia."""
        self.ensure_schema()
        conn = self._core._index.connection()
        conn.execute(
            "UPDATE ext_procedural SET used_count = used_count + 1 WHERE id = ?",
            (proc_id,),
        )
        conn.commit()

    def list_task_types(self) -> list:
        """Retorna lista de task_types distintos com pelo menos 1 registro."""
        self.ensure_schema()
        conn = self._core._index.connection()
        rows = conn.execute(
            "SELECT DISTINCT task_type FROM ext_procedural"
        ).fetchall()
        return [r[0] for r in rows]

    def delete(self, proc_id: str) -> None:
        """Remove sequencia pelo id."""
        self.ensure_schema()
        conn = self._core._index.connection()
        conn.execute("DELETE FROM ext_procedural WHERE id = ?", (proc_id,))
        conn.commit()
