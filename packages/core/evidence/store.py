"""Evidence store: grava evidencia de execucao de blocos em disco.

Escreve runs (resultado de execucao), diffs e saidas de teste em
``.maestro/runs/<block_id>/`` e ``.maestro/evidence/<block_id>/``.

Biblioteca pura: so stdlib. Append-only — nunca sobrescreve um arquivo
existente; colisao de timestamp gera sufixo numerico (``-2``, ``-3``, ...).
Escrita atomica via ``os.replace()``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class EvidenceError(Exception):
    """Erro de configuracao ao gravar evidencia (ex.: block_id ausente/vazio)."""


def _default_root() -> Path:
    """Resolve a raiz do projeto: maestro_runtime.get_root() ou Path.cwd()."""
    root = None
    try:
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import maestro_runtime  # type: ignore

        root = maestro_runtime.get_root()
    except Exception:
        root = None
    return root if root is not None else Path.cwd()


class EvidenceStore:
    """Grava evidencia de execucao de blocos (runs, diffs, saidas de teste)."""

    def __init__(self, root: "Path | str | None" = None):
        self.root = Path(root) if root is not None else _default_root()

    # -- helpers internos --------------------------------------------------

    @staticmethod
    def _validate_block_id(block_id: "str | None") -> None:
        if not block_id:
            raise EvidenceError("block_id ausente ou vazio")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _runs_dir(self, block_id: str) -> Path:
        return self.root / ".maestro" / "runs" / block_id

    def _evidence_dir(self, block_id: str) -> Path:
        return self.root / ".maestro" / "evidence" / block_id

    @staticmethod
    def _unique_path(directory: Path, filename_fn: Callable[[str], str]) -> Path:
        """Retorna um caminho ainda inexistente em ``directory``.

        Tenta ``filename_fn("")`` primeiro; em caso de colisao, tenta
        ``filename_fn("-2")``, ``filename_fn("-3")``, etc. (I1: append-only).
        """
        suffix = ""
        n = 1
        while True:
            candidate = directory / filename_fn(suffix)
            if not candidate.exists():
                return candidate
            n += 1
            suffix = f"-{n}"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)  # I2
        tmp_path = path.with_name(path.name + f".tmp-{os.getpid()}")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, path)  # I3: escrita atomica

    # -- API publica ---------------------------------------------------------

    def record_run(
        self,
        block_id: str,
        result: str,
        provider: "str | None" = None,
        duration_seconds: "float | None" = None,
        files_changed: "list[str] | None" = None,
        commands_executed: "list[str] | None" = None,
        test_result: "Any | None" = None,
        tentativas: int = 0,
    ) -> Path:
        self._validate_block_id(block_id)
        directory = self._runs_dir(block_id)
        ts = self._timestamp()
        path = self._unique_path(directory, lambda suffix: f"{ts}{suffix}.json")

        data = {
            "schema": 1,
            "block_id": block_id,
            "timestamp": ts,
            "result": result,
            "provider": provider,
            "duration_seconds": duration_seconds,
            "files_changed": files_changed,
            "commands_executed": commands_executed,
            "test_result": test_result,
            "tentativas": tentativas,
        }
        self._atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return path

    def record_diff(self, block_id: str, diff_content: str) -> Path:
        self._validate_block_id(block_id)
        directory = self._evidence_dir(block_id)
        ts = self._timestamp()
        path = self._unique_path(directory, lambda suffix: f"diff-{ts}{suffix}.patch")
        self._atomic_write(path, diff_content)
        return path

    def record_test_output(self, block_id: str, output: str) -> Path:
        self._validate_block_id(block_id)
        directory = self._evidence_dir(block_id)
        ts = self._timestamp()
        path = self._unique_path(directory, lambda suffix: f"test-{ts}{suffix}.txt")
        self._atomic_write(path, output)
        return path

    def evidence_exists(self, block_id: str) -> bool:
        self._validate_block_id(block_id)
        return self._evidence_dir(block_id).exists()

    def list_runs(self, block_id: str) -> "list[Path]":
        self._validate_block_id(block_id)
        directory = self._runs_dir(block_id)
        if not directory.exists():
            return []
        return sorted(directory.glob("*.json"))

    def validate_for_review(self, block_id: str, complexity: str) -> None:
        """Garante que evidencia existe antes de despachar reviewer em C4/C5.

        Levanta EvidenceError se complexity for C4 ou C5 e nao existir
        nenhum arquivo em .maestro/evidence/<block_id>/.

        Para C1/C2/C3 ou complexidade desconhecida: no-op.
        """
        self._validate_block_id(block_id)
        if (complexity or "").upper() not in ("C4", "C5"):
            return
        if not self.evidence_exists(block_id):
            raise EvidenceError(
                "bloco {!r} e {} mas nao possui evidencia registrada; "
                "grave evidencia antes de despachar o reviewer".format(
                    block_id, complexity
                )
            )
