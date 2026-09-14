"""Execucao do comando_teste de um bloco e apuracao de passed/failed."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


class AcceptanceError(Exception):
    """Erro de configuracao ao rodar o teste de aceite (nao e falha do teste)."""


@dataclass
class AcceptanceResult:
    passed: bool
    exit_code: int
    command_output: str
    stdout: str
    stderr: str
    criteria: list[str]
    failed_criteria: list[str]


def run_acceptance(
    block: dict,
    cwd=None,
    timeout: int = 120,
) -> AcceptanceResult:
    comando = block.get("comando_teste")
    if not comando:
        raise AcceptanceError("campo 'comando_teste' ausente ou vazio")

    criteria = list(block.get("criterio_aceite", []))

    try:
        proc = subprocess.run(
            comando,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        raise AcceptanceError(f"timeout: {timeout}s excedido")
    except (OSError, subprocess.SubprocessError) as e:
        raise AcceptanceError(str(e))

    stdout = proc.stdout
    stderr = proc.stderr
    command_output = stdout + ("\n" + stderr if stderr else "")
    passed = proc.returncode == 0
    failed_criteria = [] if passed else list(criteria)

    return AcceptanceResult(
        passed=passed,
        exit_code=proc.returncode,
        command_output=command_output,
        stdout=stdout,
        stderr=stderr,
        criteria=criteria,
        failed_criteria=failed_criteria,
    )
