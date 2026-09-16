"""SemanticMemory -- busca FTS5, extracao de entidades, links e vectors opcionais.

Todas as tabelas criadas por este modulo usam o prefixo `ext_` e nunca tocam
nas tabelas do schema base (`memories`, `rebuild_log`, `schema_version`).

Sem dependencias externas obrigatorias. Sem I/O no import nem no __init__.
"""

from __future__ import annotations

import re
import struct
import uuid

from packages.core.memory.core import MemoryCore
from packages.core.memory.schema import VALID_TYPES, now_iso, parse_frontmatter

# --- SQL: schema ---

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS ext_fts USING fts5(
    memory_id UNINDEXED,
    content,
    tokenize = 'unicode61'
)
"""

_CREATE_ENTITIES = """
CREATE TABLE IF NOT EXISTS ext_entities (
    id          TEXT PRIMARY KEY,
    memory_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    context     TEXT DEFAULT '',
    created_at  TEXT NOT NULL
)
"""

_CREATE_ENTITIES_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ext_entities_memory ON ext_entities(memory_id)",
    "CREATE INDEX IF NOT EXISTS idx_ext_entities_kind ON ext_entities(kind)",
]

_CREATE_LINKS = """
CREATE TABLE IF NOT EXISTS ext_entity_links (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    rel         TEXT NOT NULL,
    created_at  TEXT NOT NULL
)
"""

_CREATE_LINKS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ext_links_source ON ext_entity_links(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_ext_links_target ON ext_entity_links(target_id)",
]

_CREATE_VECTORS = """
CREATE TABLE IF NOT EXISTS ext_vectors (
    memory_id   TEXT PRIMARY KEY,
    embedding   BLOB NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL
)
"""

# --- Regex de extracao de entidades (heuristica simples, sem AST) ---

_FUNCTION_RE = re.compile(r"\b(?:def|function)\s+(\w+)")
_CLASS_RE = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)
_FILE_RE = re.compile(r"`([\w./\\\-]+\.\w+)`")
_DECISION_LINE_RE = re.compile(r"^-\s*DECIS[ÃA]O:\s*(.+)$", re.MULTILINE)
_DECISION_HEADER_RE = re.compile(r"^##\s*Decis[ãa]o\b\s*(.*)$", re.MULTILINE)

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def _pack_embedding(vector) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _unpack_embedding(blob: bytes):
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _cosine_similarity(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticMemory:
    """API especializada para busca semantica (FTS5 + entidades + links)."""

    def __init__(self, core: MemoryCore):
        self._core = core

    # --- Schema ---

    def ensure_schema(self) -> None:
        """Cria tabelas ext_* se ausentes. Idempotente."""
        conn = self._core._index.connection()
        conn.execute(_CREATE_FTS)
        conn.execute(_CREATE_ENTITIES)
        for sql in _CREATE_ENTITIES_INDICES:
            conn.execute(sql)
        conn.execute(_CREATE_LINKS)
        for sql in _CREATE_LINKS_INDICES:
            conn.execute(sql)
        if self.vectors_available():
            conn.execute(_CREATE_VECTORS)
        conn.commit()

    # --- FTS5 ---

    def index_memory(self, memory_id: str, content: str) -> None:
        """Indexa conteudo de uma memoria no FTS5. Upsert (DELETE + INSERT)."""
        conn = self._core._index.connection()
        conn.execute("DELETE FROM ext_fts WHERE memory_id = ?", (memory_id,))
        conn.execute(
            "INSERT INTO ext_fts (memory_id, content) VALUES (?, ?)",
            (memory_id, content),
        )
        conn.commit()

        # Extracao automatica de entidades a partir do conteudo indexado
        self._sync_entities(memory_id, content)

    def index_all(self) -> int:
        """Varre todos os arquivos Markdown em .maestro/memory/ e indexa.

        Retorna numero de arquivos indexados. Nao falha se o diretorio
        raiz nao existir.
        """
        root = self._core._root
        if not root.exists():
            return 0

        count = 0
        for mem_type in VALID_TYPES:
            type_dir = root / mem_type
            if not type_dir.exists():
                continue
            for md_file in sorted(type_dir.glob("*.md")):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    _fm, body = parse_frontmatter(text)
                except (ValueError, OSError):
                    continue
                memory_id = md_file.stem
                self.index_memory(memory_id, body)
                count += 1
        return count

    def search(self, query: str, limit: int = 10) -> list:
        """Busca FTS5. Retorna lista de dicts com memory_id, snippet, rank.

        Re-ranking por similaridade coseno quando vectors estiverem
        disponiveis e houver embeddings armazenados.
        """
        if not query or not query.strip():
            return []

        conn = self._core._index.connection()
        try:
            rows = conn.execute(
                """
                SELECT memory_id,
                       snippet(ext_fts, 1, '[', ']', '...', 8) AS snippet,
                       rank
                FROM ext_fts
                WHERE ext_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except Exception:
            return []

        results = [
            {"memory_id": r["memory_id"], "snippet": r["snippet"], "rank": r["rank"]}
            for r in rows
        ]

        if not results or not self.vectors_available():
            return results

        # Re-ranking opcional por similaridade coseno, se houver embeddings
        try:
            query_vector = self._embed_text(query)
        except Exception:
            query_vector = None

        if query_vector is None:
            return results

        try:
            table_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ext_vectors'"
            ).fetchone()
        except Exception:
            table_check = None

        if not table_check:
            return results

        scored = []
        for r in results:
            row = conn.execute(
                "SELECT embedding FROM ext_vectors WHERE memory_id = ?",
                (r["memory_id"],),
            ).fetchone()
            if row is None:
                scored.append((0.0, r))
                continue
            try:
                vec = _unpack_embedding(row["embedding"])
                sim = _cosine_similarity(query_vector, vec)
            except Exception:
                sim = 0.0
            scored.append((sim, r))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored]

    # --- Entidades ---

    def add_entity(self, memory_id: str, kind: str, name: str, context: str = "") -> str:
        """Adiciona entidade. Retorna entity_id."""
        conn = self._core._index.connection()
        entity_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO ext_entities (id, memory_id, kind, name, context, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entity_id, memory_id, kind, name, context, now_iso()),
        )
        conn.commit()
        return entity_id

    def add_link(self, source_id: str, target_id: str, rel: str) -> str:
        """Adiciona link entre entidades. Retorna link_id."""
        conn = self._core._index.connection()
        link_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO ext_entity_links (id, source_id, target_id, rel, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (link_id, source_id, target_id, rel, now_iso()),
        )
        conn.commit()
        return link_id

    def entities_for_memory(self, memory_id: str) -> list:
        """Retorna entidades de uma memoria."""
        conn = self._core._index.connection()
        rows = conn.execute(
            "SELECT * FROM ext_entities WHERE memory_id = ?", (memory_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def links_for_entity(self, entity_id: str) -> list:
        """Retorna links de uma entidade (source ou target)."""
        conn = self._core._index.connection()
        rows = conn.execute(
            "SELECT * FROM ext_entity_links WHERE source_id = ? OR target_id = ?",
            (entity_id, entity_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def _sync_entities(self, memory_id: str, content: str) -> None:
        """Re-extrai entidades regex-based para uma memoria (idempotente).

        Remove as entidades previamente auto-extraidas para este memory_id
        (kinds conhecidos) e insere as encontradas no conteudo atual.
        """
        extracted = self._extract_entities(content)

        conn = self._core._index.connection()
        conn.execute(
            "DELETE FROM ext_entities WHERE memory_id = ? "
            "AND kind IN ('function','class','file','decision')",
            (memory_id,),
        )
        for kind, name, context in extracted:
            entity_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO ext_entities (id, memory_id, kind, name, context, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entity_id, memory_id, kind, name, context, now_iso()),
            )
        conn.commit()

    @staticmethod
    def _extract_entities(content: str) -> list:
        """Extrai entidades via regex (heuristica simples, sem AST).

        Retorna lista de tuplas (kind, name, context).
        """
        found = []

        for m in _FUNCTION_RE.finditer(content):
            found.append(("function", m.group(1), m.group(0)))

        for m in _CLASS_RE.finditer(content):
            found.append(("class", m.group(1), m.group(0).strip()))

        for m in _FILE_RE.finditer(content):
            found.append(("file", m.group(1), m.group(0)))

        for m in _DECISION_LINE_RE.finditer(content):
            found.append(("decision", m.group(1).strip(), m.group(0)))

        for m in _DECISION_HEADER_RE.finditer(content):
            name = m.group(1).strip() or "Decisão"
            found.append(("decision", name, m.group(0)))

        return found

    # --- Vectors opcionais ---

    def vectors_available(self) -> bool:
        """True se biblioteca de embeddings esta disponivel."""
        try:
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            pass
        try:
            import numpy  # noqa: F401

            return True
        except ImportError:
            return False

    def index_embedding(self, memory_id: str, text: str) -> bool:
        """Gera e armazena embedding se biblioteca disponivel.

        Retorna True se indexado, False caso contrario. Nunca levanta
        excecao mesmo se a biblioteca de embeddings estiver ausente.
        """
        try:
            vector = self._embed_text(text)
        except Exception:
            return False

        if vector is None:
            return False

        try:
            conn = self._core._index.connection()
            conn.execute(_CREATE_VECTORS)
            conn.execute(
                "DELETE FROM ext_vectors WHERE memory_id = ?", (memory_id,)
            )
            conn.execute(
                """INSERT INTO ext_vectors (memory_id, embedding, model, created_at)
                   VALUES (?, ?, ?, ?)""",
                (memory_id, _pack_embedding(vector), _EMBEDDING_MODEL_NAME, now_iso()),
            )
            conn.commit()
            return True
        except Exception:
            return False

    def _embed_text(self, text: str):
        """Gera um vetor de embedding para `text`, ou None se indisponivel.

        Usa sentence_transformers quando disponivel. Sem essa biblioteca,
        nao ha embedding semantico real disponivel e retorna None.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return None

        model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
        vector = model.encode(text)
        return [float(x) for x in vector]
