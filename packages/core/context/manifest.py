"""Context Manifest: o pacote de contexto entregue ao executor de um bloco.

Estrutura de dados pura. ``to_prompt()`` apenas serializa o que ja esta em
memoria — nao le arquivos, nao consulta rede, nao toca disco (I3).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextFile:
    """Um arquivo incluido no manifesto, com prioridade e custo em tokens."""

    path: str
    content: str
    priority: int
    tokens: int


@dataclass
class ContextManifest:
    """Contexto minimo suficiente para executar um bloco.

    Contem apenas: spec do bloco, convencoes do projeto, arquivos relevantes,
    gotchas e a lista do que foi omitido. Nunca historico de conversa e nunca
    specs de outros blocos.
    """

    block_id: str
    spec: str = ""
    spec_path: str = ""
    conventions: str = ""
    files: list[ContextFile] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    gotchas: list[str] = field(default_factory=list)
    total_tokens: int = 0
    budget_tokens: int = 0

    def to_prompt(self) -> str:
        """Serializa o manifesto no prompt do executor. Sem nenhum IO."""
        partes: list[str] = [
            f"Implemente o bloco {self.block_id} conforme o contexto abaixo.",
            "N\u00e3o implemente nada fora dos arquivos listados.",
        ]

        if self.spec.strip():
            partes.append("")
            partes.append("=== SPEC ===")
            partes.append(self.spec.rstrip())

        if self.conventions.strip():
            partes.append("")
            partes.append("=== CONVEN\u00c7\u00d5ES ===")
            partes.append(self.conventions.rstrip())

        if self.files:
            partes.append("")
            partes.append("=== ARQUIVOS RELEVANTES ===")
            for arquivo in self.files:
                partes.append(f"--- {arquivo.path} ---")
                partes.append(arquivo.content.rstrip())

        if self.gotchas:
            partes.append("")
            partes.append("=== GOTCHAS / NOTAS ===")
            for gotcha in self.gotchas:
                partes.append(f"- {gotcha}")

        if self.omitted:
            partes.append("")
            partes.append("=== OMITIDOS (budget excedido) ===")
            for caminho in self.omitted:
                partes.append(f"- {caminho}")

        return "\n".join(partes) + "\n"
