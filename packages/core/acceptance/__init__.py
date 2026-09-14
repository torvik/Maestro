"""Motor de aceite do Maestro: roda o comando_teste de um bloco e apura o resultado.

Nao interpreta criterios de aceite em linguagem natural — apenas executa o
comando_teste do bloco e reporta passed/failed com base no exit code.

    from packages.core.acceptance import run_acceptance
    resultado = run_acceptance(block)

Biblioteca pura: so stdlib. A falha do comando_teste NUNCA levanta excecao —
resulta em AcceptanceResult(passed=False). AcceptanceError so ocorre por erro
de configuracao (comando ausente/vazio, timeout, falha de subprocess).
"""

from .runner import AcceptanceError, AcceptanceResult, run_acceptance

__all__ = [
    "AcceptanceError",
    "AcceptanceResult",
    "run_acceptance",
]
