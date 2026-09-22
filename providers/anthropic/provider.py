"""Anthropic provider concreto.

Traduz tier abstrato (de ``packages.core.routing``) para nome de modelo
Anthropic concreto, e gerencia saude/quota/cooldown de 429 do provider.

Nao importa o SDK ``anthropic`` -- nenhuma chamada de rede e feita aqui. Isso
e responsabilidade de um bloco futuro (F7-01).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

__all__ = ["AnthropicProvider"]


# Mapeamento tier -> modelo Anthropic (identico a tabela de F5-02, com nomes
# de modelo explicitos). Fallback de qualquer tier desconhecido: balanced.
TIER_TO_MODEL: Dict[str, str] = {
    "fast": "claude-haiku-4-5-20251001",
    "balanced": "claude-sonnet-4-6",
    "advanced": "claude-sonnet-4-6",
    "maximum": "claude-opus-4-6",
}

DEFAULT_MODEL = "claude-sonnet-4-6"

# Context window (tokens) por modelo.
MODEL_CONTEXT: Dict[str, int] = {
    "claude-haiku-4-5-20251001": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 200_000,
}
DEFAULT_CONTEXT = 200_000

_STATE_DIR = os.path.join(".maestro", "providers", "anthropic")
_COOLDOWN_FILE = os.path.join(_STATE_DIR, "cooldown.json")
_USAGE_FILE = os.path.join(_STATE_DIR, "usage.jsonl")

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(_ISO_FORMAT)


def _atomic_write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


class AnthropicProvider:
    """Provider concreto Anthropic: resolve_model, quota, health, cooldown."""

    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, config: Optional[dict] = None) -> None:
        # Sem IO aqui -- apenas guarda o estado recebido (invariante I5).
        self.api_key = api_key
        self.config = dict(config or {})

    # ------------------------------------------------------------------
    # Resolucao de modelo / context window
    # ------------------------------------------------------------------

    def resolve_model(self, requirements: Optional[dict]) -> str:
        try:
            from packages.core.routing import resolve, ProviderRegistry
            from packages.core.routing.providers import AnthropicProvider as RoutingAnthropicProvider

            reg = ProviderRegistry()
            reg.register(RoutingAnthropicProvider())
            result = resolve(requirements, registry=reg)
            tier = result["tier"]
        except Exception:
            tier = "balanced"
        return TIER_TO_MODEL.get(tier, DEFAULT_MODEL)

    def resolve_context(self, requirements: Optional[dict]) -> int:
        model = self.resolve_model(requirements)
        return MODEL_CONTEXT.get(model, DEFAULT_CONTEXT)

    # ------------------------------------------------------------------
    # Quota / health (offline -- sem chamada de API neste bloco)
    # ------------------------------------------------------------------

    def check_quota(self) -> Dict[str, Any]:
        return {"available": True, "reason": None}

    def check_health(self) -> Dict[str, Any]:
        return {"healthy": True, "latency_ms": None, "error": None}

    # ------------------------------------------------------------------
    # Cooldown de 429 (arquivo em disco, escrita atomica)
    # ------------------------------------------------------------------

    def record_429(self, tentativa: int) -> None:
        backoff_seconds = min((2 ** int(tentativa)) * 5, 300)
        until = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
        payload = {
            "until": until.strftime(_ISO_FORMAT),
            "backoff_seconds": backoff_seconds,
        }
        _atomic_write(_COOLDOWN_FILE, json.dumps(payload))

    def is_in_cooldown(self) -> bool:
        if not os.path.exists(_COOLDOWN_FILE):
            return False
        try:
            with open(_COOLDOWN_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            until = datetime.strptime(data["until"], _ISO_FORMAT).replace(tzinfo=timezone.utc)
        except Exception:
            return True  # fail-safe: arquivo corrompido → assume em cooldown
        return datetime.now(timezone.utc) < until

    # ------------------------------------------------------------------
    # Registro de uso (JSON Lines, append-only, escrita atomica)
    # ------------------------------------------------------------------

    def record_usage(
        self,
        block_id: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        record = {
            "timestamp": _now_iso(),
            "block_id": block_id,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
        }
        line = json.dumps(record, ensure_ascii=False)

        existing = ""
        if os.path.exists(_USAGE_FILE):
            with open(_USAGE_FILE, "r", encoding="utf-8") as fh:
                existing = fh.read()
        if existing and not existing.endswith("\n"):
            existing += "\n"
        _atomic_write(_USAGE_FILE, existing + line + "\n")
