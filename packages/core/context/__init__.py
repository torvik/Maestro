"""Context Builder do Maestro: contexto minimo suficiente por bloco.

Monta o Context Manifest que o executor recebe — spec do bloco, convencoes,
arquivos relevantes de ``arquivos_permitidos``, gotchas e o registro do que
foi omitido por budget. Sem historico de conversa, sem specs de outros blocos.

    from packages.core.context import ContextBuilder
    manifest = ContextBuilder(budget_tokens=8000).build(block)
    prompt = manifest.to_prompt()

Biblioteca pura: so stdlib. Arquivo ilegivel vai para ``omitted`` em vez de
derrubar o build.
"""

from .builder import ContextBuilder, ContextError
from .manifest import ContextFile, ContextManifest  # noqa: F401  (ContextFile e reexport)

__all__ = [
    "ContextBuilder",
    "ContextManifest",
    "ContextError",
]
