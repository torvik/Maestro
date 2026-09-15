"""ProviderRegistry: estende ProviderManager com rastreamento de uso, quota e routing.

Usage::

    from packages.core.providers import ProviderRegistry
    r = ProviderRegistry()
    r.register(algum_provider)
    r.set_quota("algum", daily_tokens=1_000_000)
    r.track_usage("algum", tokens=500, cost_usd=0.01)
    disponiveis = r.list_available()
    escolhido = r.capacity_aware_select()
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .manager import ProviderManager

__all__ = ["ProviderRegistry"]

_HEALTH_TTL = 60  # segundos


class ProviderRegistry(ProviderManager):
    """Estende ProviderManager com rastreamento de uso e quota por sessao.

    Invariantes:
    - Uso e' em memoria; reseta quando o processo reinicia.
    - Sem quota definida, o provider nunca fica over_quota.
    - list_available nao levanta — retorna lista (pode ser vazia).
    """

    def __init__(self) -> None:
        super().__init__()
        # name -> {"tokens": int, "requests": int, "cost_usd": float}
        self._usage: Dict[str, Dict[str, float]] = {}
        # name -> {"daily_tokens": int|None, "daily_requests": int|None, "daily_cost_usd": float|None}
        self._quotas: Dict[str, Dict[str, Optional[float]]] = {}

    # ------------------------------------------------------------------
    # Rastreamento de uso
    # ------------------------------------------------------------------

    def track_usage(
        self,
        name: str,
        tokens: int = 0,
        requests: int = 1,
        cost_usd: float = 0.0,
    ) -> None:
        """Registra uso acumulado na sessao atual (em memoria, nao persiste)."""
        if name not in self._usage:
            self._usage[name] = {"tokens": 0, "requests": 0, "cost_usd": 0.0}
        self._usage[name]["tokens"] += tokens
        self._usage[name]["requests"] += requests
        self._usage[name]["cost_usd"] += cost_usd

    def get_usage(self, name: str) -> Dict[str, float]:
        """Retorna uso acumulado: {tokens, requests, cost_usd}."""
        return dict(self._usage.get(name, {"tokens": 0, "requests": 0, "cost_usd": 0.0}))

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    def set_quota(
        self,
        name: str,
        daily_tokens: Optional[int] = None,
        daily_requests: Optional[int] = None,
        daily_cost_usd: Optional[float] = None,
    ) -> None:
        """Define quota diaria para o provider. None = sem limite."""
        self._quotas[name] = {
            "daily_tokens": daily_tokens,
            "daily_requests": daily_requests,
            "daily_cost_usd": daily_cost_usd,
        }

    def is_over_quota(self, name: str) -> bool:
        """True se qualquer dimensao de uso excedeu a quota definida."""
        quota = self._quotas.get(name, {})
        if not quota:
            return False
        usage = self.get_usage(name)
        if quota.get("daily_tokens") is not None and usage["tokens"] > quota["daily_tokens"]:
            return True
        if quota.get("daily_requests") is not None and usage["requests"] > quota["daily_requests"]:
            return True
        if quota.get("daily_cost_usd") is not None and usage["cost_usd"] > quota["daily_cost_usd"]:
            return True
        return False

    # ------------------------------------------------------------------
    # Disponibilidade e routing
    # ------------------------------------------------------------------

    def list_available(self) -> List[str]:
        """Providers registrados que nao estao em cooldown, nao estao sobre quota
        e cujo health check retorna healthy (TTL 60s).

        Nao levanta — retorna lista vazia se nenhum disponivel.
        """
        result = []
        for name in self.list():
            if self.is_in_cooldown(name):
                continue
            if self.is_over_quota(name):
                continue
            try:
                info = self.health_check(name, ttl_seconds=_HEALTH_TTL)
                if not info.healthy:
                    continue
            except Exception:
                continue
            result.append(name)
        return result

    def capacity_aware_select(self) -> Optional[str]:
        """Entre os disponiveis, seleciona o de menor uso relativo a quota.

        Se nenhuma quota definida, seleciona o primeiro disponivel.
        Retorna None se list_available() for vazia.
        """
        available = self.list_available()
        if not available:
            return None
        return min(available, key=self._relative_load)

    def _relative_load(self, name: str) -> float:
        """0.0 = sem uso; 1.0 = quota atingida; >1.0 = sobre quota."""
        usage = self.get_usage(name)
        quota = self._quotas.get(name, {})
        loads = []
        for dim in ("tokens", "requests"):
            limit = quota.get(f"daily_{dim}")
            if limit and limit > 0:
                loads.append(usage[dim] / limit)
        cost_limit = quota.get("daily_cost_usd")
        if cost_limit and cost_limit > 0:
            loads.append(usage["cost_usd"] / cost_limit)
        return sum(loads) / len(loads) if loads else 0.0

    # ------------------------------------------------------------------
    # Resumo de uso (para maestro status --custos)
    # ------------------------------------------------------------------

    def usage_summary(self) -> List[Dict]:
        """Lista de {name, tokens, requests, cost_usd, over_quota} para todos os registrados."""
        result = []
        for name in self.list():
            usage = self.get_usage(name)
            result.append(
                {
                    "name": name,
                    "tokens": int(usage["tokens"]),
                    "requests": int(usage["requests"]),
                    "cost_usd": round(usage["cost_usd"], 6),
                    "over_quota": self.is_over_quota(name),
                }
            )
        return result
