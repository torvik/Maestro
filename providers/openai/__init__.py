"""OpenAI provider concreto: tier -> modelo, quota, health, cooldown de 429.

    from providers.openai import OpenAIProvider
    provider = OpenAIProvider()
    provider.resolve_model({"reasoning": "high"})

Importar este pacote nao produz output nem executa IO.
"""

from .provider import OpenAIProvider

__all__ = ["OpenAIProvider"]
