"""Roteamento por capacidades do Maestro.

Traduz um conjunto de requisitos de capacidade em um par provider/tier, sem
mencionar modelos concretos e sem ler configuracao externa.

    from packages.core.routing import resolve
    resolve({"reasoning": "high", "coding": "high"})

Importar este pacote nao produz output nem executa IO.
"""

from .registry import resolve, ProviderRegistry, Provider, RoutingError

__all__ = [
    "resolve",
    "ProviderRegistry",
    "Provider",
    "RoutingError",
]
