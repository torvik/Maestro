"""EpisodicMemory -- registro permanente de execuções passadas.

Sem dependências externas. Sem I/O no import.
"""

from __future__ import annotations

from packages.core.memory.core import MemoryCore, MemoryError
from packages.core.memory.schema import now_iso
from packages.core.memory.working import WorkingMemory, extract_module

# Campos protegidos que extra_frontmatter não pode sobrescrever em promote()
_PROTECTED_PROMOTE = {
    "type", "authority", "bloco_id", "modulo", "resultado",
    "duracao_segundos", "modelo_usado", "source_block",
}

_VALID_RESULTADO = {"success", "failure", "partial"}

# SQL para adicionar coluna module e índice (idempotente)
_ADD_MODULE_COLUMN = "ALTER TABLE memories ADD COLUMN module TEXT"
_CREATE_MODULE_INDEX = "CREATE INDEX IF NOT EXISTS idx_memories_module ON memories(module)"


class EpisodicMemory:
    """API especializada para episodic memory (tipo 'episodic')."""

    def __init__(self, core: MemoryCore):
        self._core = core
        self._wm = WorkingMemory(core)
        self._ensure_module_column()

    def _ensure_module_column(self) -> None:
        """Garante que a coluna module e o índice existem. Idempotente."""
        conn = self._core._index.connection()
        # Tenta adicionar coluna; ignora se já existe
        try:
            conn.execute(_ADD_MODULE_COLUMN)
            conn.commit()
        except Exception:
            # Coluna já existe — OK
            pass
        # Cria índice (IF NOT EXISTS é idempotente)
        conn.execute(_CREATE_MODULE_INDEX)
        conn.commit()

    def _set_module_in_db(self, memory_id: str, module: str) -> None:
        """Atualiza a coluna module no SQLite para um memory_id."""
        conn = self._core._index.connection()
        conn.execute(
            "UPDATE memories SET module = ? WHERE id = ?",
            (module, memory_id),
        )
        conn.commit()

    def promote(
        self,
        session_id: str,
        bloco_id: str,
        resultado: str,
        duracao_segundos: float,
        modelo_usado: str,
        findings: str | None = None,
        extra_frontmatter: dict | None = None,
        body: str = "",
    ) -> str:
        """Promove a working memory de session_id para episodic.

        Sequência (seção 8 da spec):
        1. Valida parâmetros
        2. Tenta recuperar working pelo session_id
        3. Cria episodic
        4. Se criação OK: deleta working
        5. Retorna memory_id da episodic

        Levanta MemoryError se:
          - resultado inválido
          - duracao_segundos < 0
          - findings é string vazia
          - extra_frontmatter tenta sobrescrever campos protegidos
        """
        # 1. Valida parâmetros antes de qualquer I/O
        if resultado not in _VALID_RESULTADO:
            raise MemoryError(
                f"resultado must be one of {_VALID_RESULTADO}, got: {resultado!r}"
            )
        if duracao_segundos < 0:
            raise MemoryError(
                f"duracao_segundos must be >= 0, got: {duracao_segundos}"
            )
        if findings is not None and findings == "":
            raise MemoryError(
                "findings must be non-empty string or None, got empty string"
            )
        if bloco_id is None:
            raise MemoryError("bloco_id must not be None")

        if extra_frontmatter:
            for key in extra_frontmatter:
                if key in _PROTECTED_PROMOTE:
                    raise MemoryError(
                        f"extra_frontmatter cannot override protected field '{key}'"
                    )

        # 2. Tenta recuperar working
        working_result = self._wm.get(session_id)
        working_fm = None
        working_body = ""
        source_working_id = None

        if working_result is not None:
            working_fm, working_body = working_result
            source_working_id = working_fm.get("id")

        # 3. Monta frontmatter da episodic
        modulo = extract_module(bloco_id)

        fm: dict = {}

        # Campos copiados da working (regra 4 da spec)
        if working_fm is not None:
            if "session_id" not in fm and "session_id" not in (extra_frontmatter or {}):
                if working_fm.get("session_id"):
                    fm["session_id"] = working_fm["session_id"]
            if working_fm.get("source_agent"):
                fm["source_agent"] = working_fm["source_agent"]
            if working_fm.get("tags"):
                fm["tags"] = working_fm["tags"]

        # Extra frontmatter (campos não-protegidos)
        if extra_frontmatter:
            fm.update(extra_frontmatter)

        # Campos obrigatórios (sobrescrevem tudo)
        fm["type"] = "episodic"
        fm["authority"] = "session"
        fm["bloco_id"] = bloco_id
        fm["modulo"] = modulo
        fm["resultado"] = resultado
        fm["duracao_segundos"] = duracao_segundos
        fm["modelo_usado"] = modelo_usado
        fm["source_block"] = bloco_id
        fm["pinned"] = False

        if source_working_id is not None:
            fm["source_working_id"] = source_working_id
        else:
            fm["source_working_id"] = None

        # Inclui session_id se não foi copiado da working e não está em extra
        if "session_id" not in fm and session_id:
            fm["session_id"] = session_id

        # Monta body da episodic (regra 3 da spec)
        if body:
            base_body = body
        elif working_body:
            base_body = working_body
        else:
            base_body = ""

        if findings is not None:
            final_body = base_body + f"\n\n## Findings\n{findings}"
        else:
            final_body = base_body

        # 3c. Cria episodic (se falhar, working NÃO é deletada)
        path = self._core.write(fm, final_body)
        episodic_id = path.stem

        # Atualiza coluna module no SQLite
        self._set_module_in_db(episodic_id, modulo)

        # 3d. Só deleta working após escrita bem-sucedida
        if working_fm is not None:
            self._wm.delete(session_id)

        return episodic_id

    def get(self, memory_id: str) -> tuple[dict, str] | None:
        """Retorna (frontmatter, body) da episodic pelo seu UUID4.

        Retorna None se não encontrado.
        """
        result = self._core.read_raw(memory_id)
        if result is None:
            return None
        fm, body = result
        if fm.get("type") != "episodic":
            return None
        return fm, body

    def list_by_module(
        self,
        modulo: str,
        limit: int = 10,
        include_expired: bool = False,
    ) -> list[dict]:
        """Retorna as últimas `limit` episodics do módulo, ordenadas por created_at DESC.

        Usa índice SQLite WHERE module = ? para performance < 50ms.
        """
        conn = self._core._index.connection()
        conditions = ["type = 'episodic'", "is_superseded = 0", "module = ?"]
        params: list = [modulo]

        if not include_expired:
            conditions.append("(decay_at IS NULL OR decay_at > ? OR pinned = 1)")
            params.append(now_iso())

        where = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM memories WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]
        for r in result:
            if "modulo" not in r and "module" in r:
                r["modulo"] = r["module"]
        return result

    def list_by_bloco(
        self,
        bloco_id: str,
        include_expired: bool = False,
    ) -> list[dict]:
        """Retorna todas as episodics para um bloco_id específico, ordenadas por created_at DESC.

        Usa índice SQLite source_block.
        """
        conn = self._core._index.connection()
        conditions = ["type = 'episodic'", "is_superseded = 0", "source_block = ?"]
        params: list = [bloco_id]

        if not include_expired:
            conditions.append("(decay_at IS NULL OR decay_at > ? OR pinned = 1)")
            params.append(now_iso())

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC"

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def list_recent(
        self,
        limit: int = 10,
        modulo: str | None = None,
        resultado: str | None = None,
        include_expired: bool = False,
    ) -> list[dict]:
        """Consulta geral: últimas episodics com filtros opcionais.

        Ordenadas por created_at DESC.
        """
        conn = self._core._index.connection()
        conditions = ["type = 'episodic'", "is_superseded = 0"]
        params: list = []

        if modulo is not None:
            conditions.append("module = ?")
            params.append(modulo)

        if not include_expired:
            conditions.append("(decay_at IS NULL OR decay_at > ? OR pinned = 1)")
            params.append(now_iso())

        where = " AND ".join(conditions)
        # Busca mais que limit para compensar filtro Python por resultado
        fetch_limit = limit * 10 + 50 if resultado is not None else limit
        sql = (
            f"SELECT * FROM memories WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ?"
        )
        params.append(fetch_limit)

        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            r = dict(row)
            if "modulo" not in r and "module" in r:
                r["modulo"] = r["module"]
            # Enriquece com frontmatter do arquivo para obter campos não indexados
            raw = self._core.read_raw(r["id"])
            if raw is not None:
                fm_file, _ = raw
                # Propaga resultado do frontmatter para o dict de resultado
                if "resultado" not in r or r.get("resultado") is None:
                    r["resultado"] = fm_file.get("resultado")
            result.append(r)

        # Filtro de resultado em Python (campo no frontmatter, não coluna SQL)
        if resultado is not None:
            result = [r for r in result if r.get("resultado") == resultado]

        return result[:limit]
