"""Anthropic provider concreto: tier -> modelo, quota, health, cooldown de 429.

    from providers.anthropic import AnthropicProvider
    provider = AnthropicProvider()
    provider.resolve_model({"reasoning": "high"})

Importar este pacote nao produz output nem executa IO.
"""

from .provider import AnthropicProvider

__all__ = ["AnthropicProvider"]
