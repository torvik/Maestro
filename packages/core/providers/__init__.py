"""Provider Registry: ciclo de vida de providers concretos (health, TTL cache, cooldown).

    from packages.core.providers import ProviderManager
    manager = ProviderManager()
    manager.register(algum_provider)

Importar este pacote nao produz output nem executa IO.
"""

from .manager import ProviderError, ProviderInfo, ProviderManager
from .registry import ProviderRegistry

__all__ = ["ProviderError", "ProviderInfo", "ProviderManager", "ProviderRegistry"]
