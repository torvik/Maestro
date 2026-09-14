"""Providers padrao do roteamento por capacidades.

Os tiers sao descritos apenas por capacidades e por um peso relativo de custo.
Nenhum nome de modelo aparece aqui por design: a traducao tier -> modelo
concreto pertence a camada de execucao, nao ao roteamento. Assim o catalogo de
modelos pode mudar sem alterar a logica de selecao.
"""

from typing import Any, Dict, List, Mapping, Optional, Tuple

from .registry import ProviderRegistry, tier_satisfies

__all__ = [
    "TieredProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "default_registry",
]


def _tier(reasoning, context, coding, autonomy, risk, review_required, isolation_recommended):
    # type: (str, str, str, str, str, bool, bool) -> Dict[str, Any]
    return {
        "reasoning": reasoning,
        "context": context,
        "coding": coding,
        "autonomy": autonomy,
        "risk": risk,
        "review_required": review_required,
        "isolation_recommended": isolation_recommended,
    }


class TieredProvider(object):
    """Provider generico definido por uma tabela ordenada de tiers.

    Subclasses declaram ``name`` e ``TIERS``: uma sequencia de
    ``(nome_do_tier, capacidades, cost_weight)`` ordenada do mais barato para o
    mais caro. A ordem da tabela e o criterio de desempate, o que mantem a
    selecao deterministica.
    """

    name = ""  # type: str
    TIERS = ()  # type: Tuple[Tuple[str, Dict[str, Any], int], ...]

    def tier_names(self):
        # type: () -> List[str]
        """Nomes dos tiers, do mais barato para o mais caro."""
        return [tier_name for tier_name, _caps, _cost in self._ordered_tiers()]

    def capabilities(self, tier):
        # type: (str) -> Dict[str, Any]
        for tier_name, caps, _cost in self.TIERS:
            if tier_name == tier:
                return dict(caps)
        raise KeyError("tier desconhecido em %s: %r" % (self.name, tier))

    def cost_weight(self, tier):
        # type: (str) -> int
        for tier_name, _caps, cost in self.TIERS:
            if tier_name == tier:
                return int(cost)
        raise KeyError("tier desconhecido em %s: %r" % (self.name, tier))

    def can_satisfy(self, requirements):
        # type: (Mapping[str, Any]) -> bool
        return self.select_tier(requirements) is not None

    def select_tier(self, requirements):
        # type: (Mapping[str, Any]) -> Optional[str]
        """Tier mais barato que atende aos requisitos, ou None."""
        for tier_name, caps, _cost in self._ordered_tiers():
            if tier_satisfies(caps, requirements):
                return tier_name
        return None

    def _ordered_tiers(self):
        # type: () -> List[Tuple[str, Dict[str, Any], int]]
        # Ordena por custo; empates preservam a ordem de declaracao (sort estavel).
        return sorted(self.TIERS, key=lambda item: int(item[2]))

    def __repr__(self):  # pragma: no cover - conveniencia de debug
        # type: () -> str
        return "<%s name=%r tiers=%d>" % (type(self).__name__, self.name, len(self.TIERS))


class AnthropicProvider(TieredProvider):
    """Tiers do provider ``anthropic``."""

    name = "anthropic"
    TIERS = (
        ("fast", _tier("low", "low", "low", "high", "low", False, False), 1),
        ("balanced", _tier("medium", "medium", "medium", "medium", "medium", False, False), 3),
        ("advanced", _tier("high", "medium", "high", "low", "high", True, False), 5),
        ("maximum", _tier("high", "high", "high", "low", "high", True, True), 10),
    )


class OpenAIProvider(TieredProvider):
    """Tiers do provider ``openai``."""

    name = "openai"
    TIERS = (
        ("low", _tier("low", "low", "low", "high", "low", False, False), 1),
        ("medium", _tier("medium", "medium", "medium", "medium", "medium", False, False), 3),
        ("high", _tier("high", "high", "high", "low", "high", True, True), 7),
    )


DEFAULT_PROVIDER_CLASSES = (AnthropicProvider, OpenAIProvider)


def default_registry():
    # type: () -> ProviderRegistry
    """Novo registry com os providers padrao, na ordem de declaracao.

    Retorna uma instancia nova a cada chamada: nao ha estado global mutavel,
    entao um teste que registre providers extras nunca contamina outro.
    """
    registry = ProviderRegistry()
    for provider_class in DEFAULT_PROVIDER_CLASSES:
        registry.register(provider_class())
    return registry
