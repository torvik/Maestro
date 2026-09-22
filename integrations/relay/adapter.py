"""RelayAdapter -- STUB. API do Relay ainda nao definida (F15-01).

Ver docs/integrations/relay.md e a nota de bloqueio do bloco em
plano/blocos.json:

    "Bloqueado por decisao: a API do Relay ainda nao esta definida. Executar
    a parte CI/CD (GitHub Actions) independentemente da integracao Relay."
    "bloqueado_por sera limpo quando a API do Relay for documentada."

Este modulo define a INTERFACE que a integracao real implementara quando a
API for documentada (mesmo padrao de "reformular como API" usado em
F12-02/F13-01/F13-02). O backend aqui e vazio por design: nenhuma chamada de
rede, nenhuma credencial, nenhum efeito colateral fora do processo. Chamar os
metodos e sempre seguro (nunca levanta), para que o modo headless (que
depende deste modulo poder ser chamado em CI sem quebrar) possa ser
desenvolvido e testado sem depender do Relay real.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from packages.core.protocol import UCPEvent  # noqa: E402

__all__ = ["RelayTrigger", "RelayAdapter"]


@dataclass
class RelayTrigger:
    """Payload minimo de um trigger recebido do Relay.

    Schema:
      trigger_id: identificador do trigger no Relay (opaco para o Maestro).
      block_id:   bloco do plano a executar.
      source:     origem do trigger (ex.: "github_actions", "manual", "relay").
      payload:    dados adicionais especificos do Relay -- nunca interpretados
                  aqui, so preservados.

    `from_dict` e tolerante (mesmo principio de "consumidor tolerante" do
    UEP, ver docs/architecture/uep.md): entrada ausente, `None`, tipo errado
    ou chave faltando nunca levanta -- vira valor default.
    """

    trigger_id: str = ""
    block_id: str = ""
    source: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Any]) -> "RelayTrigger":
        if not isinstance(data, dict):
            data = {}
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            trigger_id=_as_text(data.get("trigger_id")),
            block_id=_as_text(data.get("block_id")),
            source=_as_text(data.get("source")),
            payload=dict(payload),
        )


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


class RelayAdapter:
    """Stub do adapter de integracao com o Relay.

    Quando a API do Relay for documentada, um bloco posterior substitui o
    corpo destes dois metodos por chamadas reais (HTTP/gRPC/o que a API
    definir); a assinatura publica nao muda, entao quem ja chama
    `RelayAdapter` hoje nao precisa mudar nada.
    """

    def __init__(self) -> None:
        #: Eventos "publicados" ficam aqui, em memoria -- util para testes e
        #: para inspecao manual. Nunca sai do processo.
        self.published: List[UCPEvent] = []
        #: Triggers recebidos, em memoria, na mesma logica.
        self.received: List[RelayTrigger] = []

    def receive_trigger(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Recebe um trigger (ex.: webhook do Relay) e devolve um ack.

        STUB: nao autentica, nao valida contra um servidor real, nao faz
        I/O de rede. Payload invalido vira um `RelayTrigger` vazio, nunca
        uma excecao.
        """
        try:
            trigger = RelayTrigger.from_dict(payload)
        except Exception:
            trigger = RelayTrigger()
        self.received.append(trigger)
        return {
            "ack": True,
            "trigger_id": trigger.trigger_id,
            "block_id": trigger.block_id,
            "stub": True,
        }

    def publish_event(self, event: Any) -> None:
        """Publicaria um evento UEP via Relay.

        STUB: nenhum I/O de rede. Aceita `UCPEvent` ou `dict` (convertido via
        `UCPEvent.from_dict`, tolerante). Qualquer falha de conversao e
        silenciosamente ignorada -- publicar para um Relay que nao existe
        ainda nunca pode derrubar um pipeline headless.
        """
        try:
            parsed = event if isinstance(event, UCPEvent) else UCPEvent.from_dict(event)
        except Exception:
            return
        self.published.append(parsed)
