"""WorkingMemory -- sessão ativa de execução de bloco.

Sem dependências externas. Sem I/O no import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from packages.core.memory.core import MemoryCore, MemoryError
from packages.core.memory.schema import now_iso


# --- Campos protegidos que não podem ser sobrescritos via extra_frontmatter ---
_PROTECTED_CREATE = {"type", "authority", "session_id", "bloco_id", "modelo_usado", "status", "pinned"}

# Campos que update() não pode alterar
_PROTECTED_UPDATE = {"type", "authority", "session_id", "bloco_id"}


def extract_module(bloco_id: str) -> str:
    """Extrai o módulo de um bloco_id.

    extract_module("F11-02") -> "F11"
    extract_module("F3-02a") -> "F3"
    extract_module("F11")    -> "F11"
    extract_module("")       -> ""

    Nunca levanta exceção.
    """
    if not bloco_id:
        return ""
    idx = bloco_id.find("-")
    if idx == -1:
        return bloco_id
    return bloco_id[:idx]


def _validate_session_id(session_id: str) -> None:
    """Valida session_id: não-vazio, sem /, <= 128 chars."""
    if not session_id:
        raise MemoryError("session_id must be non-empty")
    if "/" in session_id:
        raise MemoryError("session_id must not contain '/'")
    if len(session_id) > 128:
        raise MemoryError("session_id must be <= 128 characters")


class WorkingMemory:
    """API especializada para working memory (tipo 'working')."""

    def __init__(self, core: MemoryCore):
        self._core = core

    def create(
        self,
        session_id: str,
        bloco_id: str,
        modelo_usado: str,
        extra_frontmatter: dict | None = None,
        body: str = "",
    ) -> str:
        """Cria uma nova entrada de working memory para a sessão.

        Retorna o memory_id (UUID4) da entrada criada.
        Levanta MemoryError se:
          - session_id inválido
          - já existe working ativa para session_id
          - extra_frontmatter tenta sobrescrever campos protegidos
        """
        _validate_session_id(session_id)

        # Verifica se já existe working ativa para session_id (I-W1)
        existing = self.get(session_id)
        if existing is not None:
            raise MemoryError(
                f"Working memory already exists for session_id '{session_id}'. "
                "Use update() or delete() first."
            )

        # Valida extra_frontmatter
        if extra_frontmatter:
            for key in extra_frontmatter:
                if key in _PROTECTED_CREATE:
                    raise MemoryError(
                        f"extra_frontmatter cannot override protected field '{key}'"
                    )

        fm: dict = {}

        # Campos extras primeiro (não-protegidos)
        if extra_frontmatter:
            fm.update(extra_frontmatter)

        # Campos obrigatórios (sobrescrevem qualquer extra)
        fm["type"] = "working"
        fm["authority"] = "session"
        fm["session_id"] = session_id
        fm["bloco_id"] = bloco_id
        fm["modelo_usado"] = modelo_usado
        fm["status"] = "running"
        fm["pinned"] = False

        path = self._core.write(fm, body)
        # Extrai o UUID4 do nome do arquivo
        return path.stem

    def get(self, session_id: str) -> tuple[dict, str] | None:
        """Retorna (frontmatter, body) da working memory ativa para session_id.

        Retorna None se não existe ou está expirada.
        """
        entries = self._core.list_memories(
            type="working",
            include_expired=False,
            include_superseded=False,
        )
        for entry in entries:
            # Lê o arquivo para obter o frontmatter completo (incluindo campos extras)
            mid = entry["id"]
            result = self._core.read_raw(mid)
            if result is None:
                continue
            fm, body = result
            if fm.get("session_id") == session_id:
                # Verifica expiração manualmente (list_memories já filtra, mas confirma)
                decay_at = fm.get("decay_at")
                if decay_at is not None:
                    from packages.core.memory.schema import parse_iso
                    try:
                        decay_dt = parse_iso(decay_at)
                        if datetime.now(timezone.utc) > decay_dt:
                            continue
                    except (ValueError, TypeError):
                        pass
                return fm, body
        return None

    def update(
        self,
        session_id: str,
        updates: dict | None = None,
        body: str | None = None,
    ) -> str:
        """Atualiza a working memory existente para session_id.

        Retorna o memory_id da entrada atualizada.
        Levanta MemoryError se session_id não encontrado ou campo protegido alterado.
        """
        result = self.get(session_id)
        if result is None:
            raise MemoryError(f"No active working memory for session_id '{session_id}'")

        fm, current_body = result
        mid = fm["id"]

        # Valida updates
        if updates:
            for key in updates:
                if key in _PROTECTED_UPDATE:
                    raise MemoryError(
                        f"Cannot update protected field '{key}' in working memory"
                    )

        # Aplica updates ao frontmatter
        patch: dict = {}
        if updates:
            patch.update(updates)

        # Se body fornecido, reescreve o arquivo inteiro via patch + body
        if body is not None or updates:
            # Usa patch para frontmatter
            if patch:
                self._core.patch(mid, patch)
            # Se body foi fornecido, precisa reescrever o arquivo com novo body
            if body is not None:
                # Lê estado atual após patch
                result2 = self._core.read_raw(mid)
                if result2 is None:
                    raise MemoryError(f"Memory '{mid}' disappeared after patch")
                fm2, _ = result2
                # Reescreve com novo body (patch não aceita body, então usamos write direto)
                import os
                from pathlib import Path
                content_fm = __import__(
                    "packages.core.memory.schema",
                    fromlist=["serialize_frontmatter"]
                ).serialize_frontmatter(fm2)
                content = content_fm + "\n\n" + body
                if not content.endswith("\n"):
                    content += "\n"
                target = Path(self._core._root) / "working" / f"{mid}.md"
                tmp_path = target.with_suffix(".md.tmp")
                tmp_path.write_text(content, encoding="utf-8")
                os.replace(str(tmp_path), str(target))
                # Atualiza índice
                entry = self._core._build_index_entry(fm2, body, target)
                with self._core._lock:
                    self._core._index.upsert(entry)

        return mid

    def delete(self, session_id: str) -> bool:
        """Remove a working memory para session_id do disco e do índice.

        Retorna True se removida, False se não existia.
        """
        result = self.get(session_id)
        if result is None:
            return False
        fm, _ = result
        mid = fm["id"]
        return self._core.delete(mid)

    def list_active(self) -> list[dict]:
        """Retorna frontmatters de todas as working memories ativas, ordenadas por updated_at DESC."""
        entries = self._core.list_memories(
            type="working",
            include_expired=False,
            include_superseded=False,
        )
        # Enriquece com campos extras do arquivo
        result = []
        for entry in entries:
            mid = entry["id"]
            raw = self._core.read_raw(mid)
            if raw is None:
                continue
            fm, _ = raw
            # Verifica expiração (list_memories já filtra, mas confirma para campos extras)
            decay_at = fm.get("decay_at")
            if decay_at is not None:
                from packages.core.memory.schema import parse_iso
                try:
                    decay_dt = parse_iso(decay_at)
                    if datetime.now(timezone.utc) > decay_dt:
                        continue
                except (ValueError, TypeError):
                    pass
            result.append(fm)
        return result
