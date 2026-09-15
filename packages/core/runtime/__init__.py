"""Retry classificado e escalation de modelo do Maestro.

Classifica falhas de execucao de bloco em 5 tipos conhecidos e retorna a
decisao de retry (mesmo modelo, modelo superior, aguardar cooldown ou
parar). Nao executa a decisao: apenas classifica.

    from packages.core.runtime import RetryClassifier
    RetryClassifier().classify("teste_falhou", block, tentativas=0)

Importar este pacote nao produz output nem executa IO.
"""

from .retry import RetryClassifier, RetryDecision, RetryError

__all__ = [
    "RetryClassifier",
    "RetryDecision",
    "RetryError",
]
