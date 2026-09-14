"""Roteamento por capacidades: requisitos -> (provider, tier).

Este modulo nao conhece nomes de modelo, nao le configuracao externa e nao
executa IO. A escolha e feita apenas sobre capacidades declaradas pelos
providers registrados.

Contrato de capacidades
-----------------------
Capacidades ordinais (``low`` < ``medium`` < ``high``):
    reasoning, context, coding, autonomy, risk
Capacidades booleanas:
    review_required, isolation_recommended

Regra de satisfacao de um tier:
    - ordinal:  valor_do_tier >= valor_requerido
    - booleana: se o requisito e True, o tier precisa ser True;
                se o requisito e False, qualquer tier serve.
"""

from collections.abc import Mapping as _MappingABC
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:  # Protocol existe em typing a partir do 3.8
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover - defensivo para runtimes antigos
    Protocol = object  # type: ignore[assignment]

    def runtime_checkable(cls):  # type: ignore[misc]
        return cls


__all__ = [
    "ORDINAL_CAPABILITIES",
    "BOOLEAN_CAPABILITIES",
    "ORDINAL_LEVELS",
    "Provider",
    "ProviderRegistry",
    "RoutingError",
    "normalize_requirements",
    "resolve",
    "tier_satisfies",
]


ORDINAL_LEVELS = {"low": 0, "medium": 1, "high": 2}

ORDINAL_CAPABILITIES = ("reasoning", "context", "coding", "autonomy", "risk")
BOOLEAN_CAPABILITIES = ("review_required", "isolation_recommended")

_KNOWN_CAPABILITIES = ORDINAL_CAPABILITIES + BOOLEAN_CAPABILITIES

# Default aplicado quando o requisito nao e informado: o menos exigente
# possivel, para que a ausencia de requisito nunca encareca a escolha.
_DEFAULT_ORDINAL = "low"
_DEFAULT_BOOLEAN = False


class RoutingError(Exception):
    """Nenhum provider registrado consegue satisfazer os requisitos.

    Atributos
    ---------
    requirements : dict
        Requisitos normalizados que originaram a falha.
    missing : list[str]
        Capacidades que nenhum provider conseguiu atender.
    per_provider : dict[str, list[str]]
        Capacidades faltantes por provider avaliado. Vazio quando o registry
        nao possui providers.
    """

    def __init__(self, message, requirements=None, missing=None, per_provider=None):
        # type: (str, Optional[Mapping[str, Any]], Optional[Sequence[str]], Optional[Mapping[str, Sequence[str]]]) -> None
        super(RoutingError, self).__init__(message)
        self.requirements = dict(requirements or {})
        self.missing = list(missing or [])
        self.per_provider = {k: list(v) for k, v in dict(per_provider or {}).items()}


@runtime_checkable
class Provider(Protocol):
    """Protocolo que todo provider de roteamento precisa implementar."""

    name = ""  # type: str

    def can_satisfy(self, requirements):
        # type: (Mapping[str, Any]) -> bool
        """True se algum tier do provider atende a todos os requisitos."""

    def select_tier(self, requirements):
        # type: (Mapping[str, Any]) -> Optional[str]
        """Tier mais barato que atende aos requisitos, ou None."""

    def capabilities(self, tier):
        # type: (str) -> Dict[str, Any]
        """Capacidades declaradas do tier informado."""

    def cost_weight(self, tier):
        # type: (str) -> int
        """Peso relativo de custo do tier informado (menor e mais barato)."""


def _is_provider(candidate):
    # type: (Any) -> bool
    required = ("name", "can_satisfy", "select_tier", "capabilities", "cost_weight")
    return all(hasattr(candidate, attr) for attr in required)


def normalize_requirements(requirements):
    # type: (Optional[Mapping[str, Any]]) -> Dict[str, Any]
    """Valida e completa os requisitos com os defaults menos exigentes.

    Falha fechada: chave desconhecida ou valor invalido levanta ValueError em
    vez de ser silenciosamente ignorado, para que um requisito digitado errado
    nunca resulte em roteamento sub-dimensionado.
    """
    if requirements is None:
        requirements = {}
    if not isinstance(requirements, _MappingABC):
        raise ValueError("requirements deve ser um mapping, recebido %s" % type(requirements).__name__)

    unknown = sorted(set(requirements) - set(_KNOWN_CAPABILITIES))
    if unknown:
        raise ValueError(
            "capacidade desconhecida em requirements: %s (conhecidas: %s)"
            % (", ".join(unknown), ", ".join(_KNOWN_CAPABILITIES))
        )

    normalized = {}  # type: Dict[str, Any]
    for cap in ORDINAL_CAPABILITIES:
        value = requirements.get(cap, _DEFAULT_ORDINAL)
        if value is None:
            value = _DEFAULT_ORDINAL
        if value not in ORDINAL_LEVELS:
            raise ValueError(
                "valor invalido para %s: %r (esperado low, medium ou high)" % (cap, value)
            )
        normalized[cap] = value
    for cap in BOOLEAN_CAPABILITIES:
        value = requirements.get(cap, _DEFAULT_BOOLEAN)
        if value is None:
            value = _DEFAULT_BOOLEAN
        if not isinstance(value, bool):
            raise ValueError("valor invalido para %s: %r (esperado True ou False)" % (cap, value))
        normalized[cap] = value
    return normalized


def unmet_capabilities(tier_capabilities, requirements):
    # type: (Mapping[str, Any], Mapping[str, Any]) -> List[str]
    """Capacidades do requisito que o tier nao atende."""
    unmet = []  # type: List[str]
    for cap in ORDINAL_CAPABILITIES:
        required = requirements.get(cap, _DEFAULT_ORDINAL)
        offered = tier_capabilities.get(cap, _DEFAULT_ORDINAL)
        if ORDINAL_LEVELS.get(offered, -1) < ORDINAL_LEVELS[required]:
            unmet.append(cap)
    for cap in BOOLEAN_CAPABILITIES:
        if requirements.get(cap, _DEFAULT_BOOLEAN) and not tier_capabilities.get(cap, False):
            unmet.append(cap)
    return unmet


def tier_satisfies(tier_capabilities, requirements):
    # type: (Mapping[str, Any], Mapping[str, Any]) -> bool
    """True se o tier atende a todos os requisitos informados."""
    return not unmet_capabilities(tier_capabilities, requirements)


class ProviderRegistry(object):
    """Colecao ordenada de providers usada para resolver requisitos."""

    def __init__(self, providers=None):
        # type: (Optional[Sequence[Any]]) -> None
        self._providers = []  # type: List[Any]
        for provider in providers or ():
            self.register(provider)

    def register(self, provider):
        # type: (Any) -> Any
        """Registra um provider. Nome duplicado e rejeitado."""
        if not _is_provider(provider):
            raise ValueError(
                "provider invalido: precisa expor name, can_satisfy, select_tier, "
                "capabilities e cost_weight"
            )
        name = getattr(provider, "name", "")
        if not isinstance(name, str) or not name:
            raise ValueError("provider precisa de um atributo name nao vazio")
        if any(getattr(p, "name") == name for p in self._providers):
            raise ValueError("provider ja registrado: %s" % name)
        self._providers.append(provider)
        return provider

    def list_providers(self):
        # type: () -> List[Any]
        """Providers na ordem de registro (copia defensiva)."""
        return list(self._providers)

    def resolve(self, requirements):
        # type: (Optional[Mapping[str, Any]]) -> Dict[str, Any]
        """Resolve requisitos para o provider/tier de menor cost_weight."""
        normalized = normalize_requirements(requirements)

        candidates = []  # type: List[Tuple[int, int, Any, str, Dict[str, Any]]]
        per_provider = {}  # type: Dict[str, List[str]]

        for index, provider in enumerate(self._providers):
            name = getattr(provider, "name")
            if not provider.can_satisfy(normalized):
                per_provider[name] = self._diagnose(provider, normalized)
                continue
            tier = provider.select_tier(normalized)
            if tier is None:
                per_provider[name] = self._diagnose(provider, normalized)
                continue
            capabilities = dict(provider.capabilities(tier))
            unmet = unmet_capabilities(capabilities, normalized)
            if unmet:
                # can_satisfy mentiu ou o tier nao confere: falha fechada,
                # o provider e descartado em vez de aceito.
                per_provider[name] = unmet
                continue
            cost = int(provider.cost_weight(tier))
            candidates.append((cost, index, provider, tier, capabilities))

        if not candidates:
            missing = self._aggregate_missing(per_provider, normalized)
            raise RoutingError(
                self._build_message(normalized, missing, per_provider),
                requirements=normalized,
                missing=missing,
                per_provider=per_provider,
            )

        # Menor cost_weight vence. Empate resolvido pela ordem de registro:
        # registrar um provider antes e a forma de declarar preferencia. Como
        # o registry faz parte da entrada, o resultado segue deterministico.
        cost, _index, provider, tier, capabilities = min(
            candidates, key=lambda item: (item[0], item[1])
        )

        return {
            "provider": getattr(provider, "name"),
            "tier": tier,
            "capabilities": capabilities,
            "cost_weight": cost,
            "metadata": {
                "requirements": dict(normalized),
                "selection": "lowest_cost_weight",
                "candidates": sorted(
                    (
                        {
                            "provider": getattr(item[2], "name"),
                            "tier": item[3],
                            "cost_weight": item[0],
                        }
                        for item in candidates
                    ),
                    key=lambda entry: (entry["cost_weight"], entry["provider"], entry["tier"]),
                ),
                "rejected": {k: list(v) for k, v in sorted(per_provider.items())},
            },
        }

    @staticmethod
    def _diagnose(provider, normalized):
        # type: (Any, Mapping[str, Any]) -> List[str]
        """Capacidades faltantes quando nenhum tier satisfaz os requisitos.

        Usa a uniao dos gaps de todos os tiers: se requisitos conflitam
        (ex: reasoning:high E autonomy:high, sem tier que tenha ambos),
        a intersecao seria vazia mas a uniao mostra o que contribuiu
        para a impossibilidade. Se o provider nao expoe seus tiers,
        reporta os requisitos exigentes.
        """
        tiers = getattr(provider, "tier_names", None)
        if not callable(tiers):
            return _demanding_capabilities(normalized)
        union = set()  # type: set
        found_any = False
        for tier in tiers():
            try:
                capabilities = dict(provider.capabilities(tier))
            except Exception:  # noqa: BLE001 - provider externo nao confiavel
                continue
            found_any = True
            unmet = set(unmet_capabilities(capabilities, normalized))
            union |= unmet
        if not found_any:
            return _demanding_capabilities(normalized)
        return sorted(union) if union else _demanding_capabilities(normalized)

    @staticmethod
    def _aggregate_missing(per_provider, normalized):
        # type: (Mapping[str, Sequence[str]], Mapping[str, Any]) -> List[str]
        if not per_provider:
            # Registry vazio: nada atende a nenhum requisito exigente.
            return _demanding_capabilities(normalized)
        common = None  # type: Optional[set]
        for gaps in per_provider.values():
            gaps_set = set(gaps)
            common = gaps_set if common is None else (common & gaps_set)
        union = set()  # type: set
        for gaps in per_provider.values():
            union |= set(gaps)
        return sorted(common or union)

    @staticmethod
    def _build_message(normalized, missing, per_provider):
        # type: (Mapping[str, Any], Sequence[str], Mapping[str, Sequence[str]]) -> str
        if not per_provider:
            return (
                "nenhum provider registrado; capacidades nao atendidas: %s"
                % (", ".join(missing) or "nenhuma")
            )
        detail = "; ".join(
            "%s: %s" % (name, ", ".join(gaps) or "nenhum tier elegivel")
            for name, gaps in sorted(per_provider.items())
        )
        return "nenhum provider satisfaz os requisitos. Faltantes: %s (%s)" % (
            ", ".join(missing) or "nenhuma",
            detail,
        )


def _demanding_capabilities(normalized):
    # type: (Mapping[str, Any]) -> List[str]
    """Requisitos acima do piso (que efetivamente exigem algo do provider)."""
    demanding = [
        cap
        for cap in ORDINAL_CAPABILITIES
        if ORDINAL_LEVELS[normalized.get(cap, _DEFAULT_ORDINAL)] > 0
    ]
    demanding += [cap for cap in BOOLEAN_CAPABILITIES if normalized.get(cap, False)]
    return sorted(demanding) or sorted(ORDINAL_CAPABILITIES)


def resolve(requirements, registry=None):
    # type: (Optional[Mapping[str, Any]], Optional[ProviderRegistry]) -> Dict[str, Any]
    """Resolve requisitos de capacidade para um par provider/tier.

    Parametros
    ----------
    requirements : dict
        Capacidades exigidas. Chaves ausentes assumem o piso (low / False).
    registry : ProviderRegistry, opcional
        Registry a consultar. Quando omitido, usa o registry padrao do
        pacote. Injetar um registry torna a chamada independente de
        configuracao e de ambiente.

    Levanta
    -------
    RoutingError
        Quando nenhum provider registrado atende aos requisitos.
    ValueError
        Quando os requisitos contem chave desconhecida ou valor invalido.
    """
    if registry is None:
        from .providers import default_registry  # import tardio: evita ciclo

        registry = default_registry()
    return registry.resolve(requirements)
