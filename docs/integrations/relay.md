# Integração com Relay (placeholder)

> **Status: API do Relay ainda não definida.** Este documento descreve a
> interface stub implementada em `integrations/relay/adapter.py` pelo bloco
> F15-01. Nenhum dos métodos abaixo faz I/O de rede.

## Por que é um stub

Nota de bloqueio registrada em `plano/blocos.json` para o bloco F15-01:

> "Bloqueado por decisão: a API do Relay ainda não está definida. Executar a
> parte CI/CD (GitHub Actions) independentemente da integração Relay.
> `bloqueado_por` será limpo quando a API do Relay for documentada."

Sem uma API documentada não há URL, esquema de autenticação, nem contrato de
request/response para implementar de verdade — implementar contra uma API
inexistente significaria inventar valores de negócio (URL, credencial,
formato de payload), o que este projeto não faz sem que o dado venha de uma
fonte real.

O que existe hoje, em vez disso, é a **interface** que o Relay real vai
preencher, para que:

- o modo headless (F15-01, critérios 1/2/3/6) possa ser desenvolvido,
  testado e revisado sem depender do Relay;
- quando a API for documentada, um bloco posterior troque o corpo dos
  métodos sem quebrar quem já chama `RelayAdapter`.

## Interface atual (stub)

```python
from integrations.relay import RelayAdapter, RelayTrigger

adapter = RelayAdapter()

# Recebe um trigger (ex.: webhook do Relay). STUB: sem autenticação, sem
# rede. Nunca levanta.
ack = adapter.receive_trigger({
    "trigger_id": "T-123",
    "block_id": "F15-01",
    "source": "github_actions",
    "payload": {},
})
# ack == {"ack": True, "trigger_id": "T-123", "block_id": "F15-01", "stub": True}

# Publicaria um evento UEP via Relay. STUB: sem rede; só guarda em memória
# (adapter.published). Nunca levanta.
from packages.core.protocol import UEP, EventType
stream = UEP(block_id="F15-01")
event = stream.emit(EventType.BLOCK_STARTED)
adapter.publish_event(event)
```

### Schema de `RelayTrigger`

| Campo | Tipo | Nota |
|-------|------|------|
| `trigger_id` | string | id opaco atribuído pelo Relay |
| `block_id` | string | bloco do plano a executar |
| `source` | string | origem do trigger (ex.: `"github_actions"`, `"manual"`, `"relay"`) |
| `payload` | objeto | dados específicos do Relay, nunca interpretados pelo Maestro |

`RelayTrigger.from_dict` é tolerante: entrada `None`, `{}`, dict parcial ou
tipo errado nunca levanta — vira trigger com campos vazios.

### Eventos publicados

`publish_event` aceita `UCPEvent` (de `packages.core.protocol`, protocolo
UEP — ver [`docs/architecture/uep.md`](../architecture/uep.md)) ou um `dict`
equivalente. Nenhum formato novo foi inventado para o Relay: o Maestro já
tem um contrato de evento (UEP) e a integração o reaproveita.

## O que muda quando a API do Relay for documentada

1. `bloqueado_por` é limpo em `plano/blocos.json` para o bloco que
   implementa o backend real.
2. Um novo bloco (fora de F15-01) substitui o corpo de `receive_trigger` e
   `publish_event` por chamadas HTTP/gRPC/o que a API definir — sem mudar a
   assinatura pública.
3. Credenciais/URL do Relay entram via configuração (variável de ambiente
   ou arquivo de config), nunca hardcoded no código — mesma regra do resto
   do projeto.
4. Este documento é atualizado com o schema real de request/response.

## Ver também

- [`docs/integrations/cicd.md`](cicd.md) — modo headless e GitHub Actions
  (não depende do Relay).
- [`docs/architecture/uep.md`](../architecture/uep.md) — contrato de evento
  reaproveitado por `publish_event`.
- `plano/specs/F15-01-cicd-relay.md` — spec completa deste bloco.
