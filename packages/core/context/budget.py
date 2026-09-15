"""BudgetTracker: rastreio de 3 orcamentos independentes por bloco.

Um bloco tem 3 limites separados durante a execucao:

- contexto (tokens): quanto texto de contexto foi entregue ao executor;
- exploracao (arquivos): quantos arquivos distintos foram lidos;
- mudanca (arquivos): quantos arquivos distintos foram escritos/alterados.

``BudgetTracker`` acumula o uso de cada um e levanta ``BudgetError`` apenas
quando o orcamento de mudanca e excedido (leitura/exploracao nunca bloqueia).

    from packages.core.context import BudgetTracker
    tracker = BudgetTracker(change_budget=20)
    tracker.track_read("foo.py", tokens=120)
    tracker.track_write("bar.py")
    usage = tracker.get_usage()

Biblioteca pura: so stdlib.
"""

from dataclasses import dataclass, field


class BudgetError(Exception):
    """Levantado quando um orcamento de mudanca e excedido."""


@dataclass
class BudgetUsage:
    context_tokens_used: int
    context_tokens_limit: int
    exploration_files_used: int
    exploration_files_limit: int
    change_files_used: int
    change_files_limit: int
    files_read: list
    files_changed: list


class BudgetTracker:
    """Rastreia 3 orcamentos independentes: contexto, exploracao e mudanca."""

    def __init__(self, context_budget=8000, exploration_budget=10, change_budget=20):
        self._context_budget = context_budget
        self._exploration_budget = exploration_budget
        self._change_budget = change_budget

        self._context_tokens_used = 0
        self._files_read = []
        self._files_changed = []

    def track_read(self, path: str, tokens: int = 0) -> None:
        """Registra leitura de ``path``. Nunca levanta (I2)."""
        if path not in self._files_read:
            self._files_read.append(path)
        if tokens:
            self._context_tokens_used += tokens

    def track_context_tokens(self, tokens: int) -> None:
        """Acumula tokens de contexto entregues ao executor."""
        self._context_tokens_used += tokens

    def track_write(self, path: str) -> None:
        """Registra escrita de ``path``.

        Levanta ``BudgetError`` ANTES de registrar se o orcamento de mudanca
        ja foi atingido (I1).
        """
        if path not in self._files_changed and len(self._files_changed) >= self._change_budget:
            raise BudgetError(
                f"change_budget excedido: limite={self._change_budget}, "
                f"tentativa de escrever '{path}'"
            )
        if path not in self._files_changed:
            self._files_changed.append(path)

    def get_usage(self) -> BudgetUsage:
        return BudgetUsage(
            context_tokens_used=self._context_tokens_used,
            context_tokens_limit=self._context_budget,
            exploration_files_used=len(self._files_read),
            exploration_files_limit=self._exploration_budget,
            change_files_used=len(self._files_changed),
            change_files_limit=self._change_budget,
            files_read=list(self._files_read),
            files_changed=list(self._files_changed),
        )

    def is_exploration_exhausted(self) -> bool:
        return len(self._files_read) >= self._exploration_budget

    def is_change_exhausted(self) -> bool:
        return len(self._files_changed) >= self._change_budget

    def to_metrics_record(self) -> dict:
        """Retorna um dict serializavel para registro de metricas. Sem IO."""
        return {
            "context_tokens": self._context_tokens_used,
            "exploration_files": len(self._files_read),
            "change_files": len(self._files_changed),
            "files_read": list(self._files_read),
            "files_changed": list(self._files_changed),
        }
