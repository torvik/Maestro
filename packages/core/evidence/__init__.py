"""Evidence store do Maestro: grava evidencia de execucao de blocos em disco.

Runs, diffs e saidas de teste sao gravados em ``.maestro/runs/<block_id>/``
e ``.maestro/evidence/<block_id>/``. Biblioteca pura: so stdlib.
Append-only — nunca sobrescreve arquivo existente.

    from packages.core.evidence import EvidenceStore
    store = EvidenceStore()
    store.record_run("F8-01", "concluido")
"""

from .store import EvidenceError, EvidenceStore

__all__ = [
    "EvidenceStore",
    "EvidenceError",
]
