"""Provider Registry: ciclo de vida de providers concretos.

Este modulo gerencia registro, consulta de saude com cache TTL e cooldown de
providers concretos (ex: ``providers.anthropic.AnthropicProvider``). Nao
conhece detalhes de nenhum provider especifico -- apenas o protocolo minimo
(atributo ``name`` e metodo ``check_health()``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["ProviderError", "ProviderInfo", "ProviderManager"]


class ProviderError(Exception):
    """Erro de gerenciamento de provider (registro invalido, nome ausente etc.)."""


@dataclass
class ProviderInfo:
    name: str
    healthy: bool
    last_check: Optional[str]
    cooldown_until: Optional[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProviderManager:
    """Registro de providers com cache de health check (TTL) e cooldown em memoria."""

    def __init__(self) -> None:
        self._providers: Dict[str, Any] = {}
        # name -> (monotonic_checked_at, ProviderInfo)
        self._health_cache: Dict[str, Tuple[float, ProviderInfo]] = {}
        # name -> monotonic deadline
        self._cooldowns: Dict[str, float] = {}

    def register(self, provider: Any) -> None:
        name = getattr(provider, "name", None)
        if not name or not isinstance(name, str):
            raise ProviderError("provider precisa de um atributo 'name' nao vazio")
        self._providers[name] = provider

    def get(self, name: str) -> Any:
        try:
            return self._providers[name]
        except KeyError:
            raise ProviderError("provider nao registrado: %s" % name)

    def list(self) -> List[str]:
        return list(self._providers.keys())

    def health_check(self, name: str, ttl_seconds: int = 300) -> ProviderInfo:
        provider = self.get(name)
        now = time.monotonic()

        cached = self._health_cache.get(name)
        if cached is not None:
            checked_at, info = cached
            if now - checked_at < ttl_seconds:
                return info

        try:
            result = provider.check_health()
            healthy = bool(result.get("healthy", False))
        except Exception:
            healthy = False

        info = ProviderInfo(
            name=name,
            healthy=healthy,
            last_check=_now_iso(),
            cooldown_until=self._cooldown_iso(name),
        )
        self._health_cache[name] = (now, info)
        return info

    def is_in_cooldown(self, name: str) -> bool:
        deadline = self._cooldowns.get(name)
        if deadline is None:
            return False
        return time.monotonic() < deadline

    def set_cooldown(self, name: str, seconds: int) -> None:
        self._cooldowns[name] = time.monotonic() + seconds

    def _cooldown_iso(self, name: str) -> Optional[str]:
        if not self.is_in_cooldown(name):
            return None
        remaining = self._cooldowns[name] - time.monotonic()
        dt = datetime.now(timezone.utc) + timedelta(seconds=max(remaining, 0))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
