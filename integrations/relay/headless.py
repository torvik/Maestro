"""Modo headless: executa blocos do plano sem interacao humana (F15-01).

Ver plano/specs/F15-01-cicd-relay.md, secoes 4-6.

RESTRICAO DE ESCOPO: `scripts/maestro_run.py` (bloco F4-03) nao esta em
`arquivos_permitidos` deste bloco e NUNCA e editado ou importado aqui. Este
modulo apenas o invoca via `subprocess` -- a mesma regra I5 que o proprio
`maestro_run.py` usa para `lock.py`. Isso preserva o contrato publico do
bloco F4-03 e evita tocar em arquivo de outro bloco.

Definicao de modo headless (spec, secao 5):

1. Autonomia forcada em memoria: `effective_autonomia()` sempre devolve
   "auto", independente do que estiver em `maestro.config.json` no disco.
   O arquivo nunca e escrito por este modulo.
2. Pendencia vira bloqueio, nunca pergunta: `block_pending_question()`
   registra a falha via `maestro_run.py finish <ID> --fail --motivo <texto>`
   em vez de chamar `input()`. Nenhuma funcao deste modulo chama `input()`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
MAESTRO_RUN_PATH = os.path.join(ROOT, "scripts", "maestro_run.py")

#: Autonomia efetiva em modo headless. Constante, nao configuravel -- o
#: proposito do modo headless e justamente nao parar. Nunca gravado em disco.
AUTONOMIA_HEADLESS = "auto"

__all__ = [
    "AUTONOMIA_HEADLESS",
    "MAESTRO_RUN_PATH",
    "HeadlessResult",
    "HeadlessRunner",
]


@dataclass
class HeadlessResult:
    """Resultado de uma operacao headless. `blocked_reason`so e preenchido
    por `block_pending_question`."""

    block_id: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    blocked_reason: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class HeadlessRunner:
    """Executa `scripts/maestro_run.py` sem interacao humana.

    `runner` e injetavel: um callable `(args: list[str]) -> CompletedProcess`
    usado pelos testes para inspecionar os argumentos construidos sem
    disparar um subprocess real nem tocar arquivos do repositorio.
    """

    def __init__(
        self,
        root: Optional[str] = None,
        maestro_run_path: Optional[str] = None,
        runner: Optional[Callable[[List[str]], Any]] = None,
    ) -> None:
        self.root = root or ROOT
        self.maestro_run_path = maestro_run_path or MAESTRO_RUN_PATH
        self._runner = runner or self._default_subprocess_runner

    # -- autonomia ----------------------------------------------------

    def effective_autonomia(self) -> str:
        """Autonomia usada em modo headless. Sempre "auto".

        Override em memoria: nao le nem escreve `maestro.config.json`. O
        valor persistido no disco (tipicamente "parar_a_cada_bloco") e de
        outro bloco e nunca e alterado por este metodo.
        """
        return AUTONOMIA_HEADLESS

    # -- subprocess -----------------------------------------------------

    def _default_subprocess_runner(self, args: List[str]):
        cmd = [sys.executable, self.maestro_run_path] + list(args)
        return subprocess.run(
            cmd,
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
        )

    def _run(self, block_id: str, args: List[str]) -> HeadlessResult:
        proc = self._runner(args)
        return HeadlessResult(
            block_id=block_id,
            exit_code=getattr(proc, "returncode", 1),
            stdout=getattr(proc, "stdout", "") or "",
            stderr=getattr(proc, "stderr", "") or "",
        )

    # -- operacoes --------------------------------------------------------

    def dry_run(self, block_id: str, fase: Optional[str] = None) -> HeadlessResult:
        """`maestro_run.py --dry-run <ID> [--fase <fase>]`.

        Somente leitura (invariante I1 de maestro_run.py): nunca adquire
        lock, nunca escreve. Seguro contra o plano real do repositorio.
        """
        args = ["--dry-run", block_id]
        if fase:
            args += ["--fase", fase]
        return self._run(block_id, args)

    def block_pending_question(
        self,
        block_id: str,
        motivo: str,
        fase: Optional[str] = None,
    ) -> HeadlessResult:
        """Registra bloqueio no lugar de perguntar algo a um humano.

        `motivo` e obrigatorio e nao pode ser vazio -- e o texto que fica
        registrado nas notas do bloco (`maestro_run.py finish --fail
        --motivo`). Esta funcao nunca chama `input()`.
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValueError("block_pending_question requer 'motivo' nao vazio")
        args = ["finish", block_id, "--fail", "--motivo", motivo]
        if fase:
            args += ["--fase", fase]
        resultado = self._run(block_id, args)
        resultado.blocked_reason = motivo
        return resultado
