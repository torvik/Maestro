# Universal Event Protocol (UEP)

> `event_protocol_version: 1` — implementado em `packages/core/protocol/uep.py`.
> Visão geral e regras comuns aos dois protocolos: [protocol.md](protocol.md).

O UEP é o **contrato de eventos** emitidos durante a execução de um bloco.

```
claude-code | codex | generic-cli | <futuro> ──UEP──► Evidence Store | Telemetry | Reviewer | State
```

## Os seis eventos

| Evento | Quando | Payload obrigatório | Payload usual |
|--------|--------|---------------------|---------------|
| `block_started` | executor começou o bloco | — | `ucp_digest`, `executor`, `budget` |
| `file_read` | leu um arquivo | `path` | `tokens`, `bytes` |
| `file_written` | escreveu/alterou um arquivo | `path` | `bytes`, `created` |
| `test_run` | rodou o comando de teste | `command`, `passed` | `exit_code`, `duration_ms`, `output_tail` |
| `block_completed` | terminou com sucesso | — | `files_written`, `tests_passed`, `summary` |
| `block_failed` | terminou sem sucesso | `reason` | `error_type`, `files_written`, `partial` |

Adicionar um evento é evolução compatível. **Remover ou renomear um deles exige
`event_protocol_version = 2`.**

## Envelope do evento

| Campo | Tipo | Nota |
|-------|------|------|
| `event_type` | string | um dos seis; leitor aceita valor desconhecido |
| `block_id` | string | obrigatório, não vazio |
| `payload` | objeto | específico do tipo |
| `sequence` | inteiro | monotônico dentro do stream, começa em 1 |
| `timestamp` | string | ISO-8601 UTC, sufixo `Z` |
| `agent` | string | id do agente (dado) |
| `run_id` | string | correlaciona com o UCP |
| `event_id` | string | `E-<YYYYMMDDTHHMMSS>-<8 hex>` |
| `schema_version` | inteiro | default 1 |

## Ordenação

**`sequence` é a ordem canônica. `timestamp` não é.** O relógio de um processo
externo não é confiável e pode até retroceder; ordenar por tempo produziria um
stream reordenado silenciosamente. Nenhum consumidor deve ordenar por
`timestamp`.

`UEP.validate()` verifica, e levanta `UEPError` quando violado:

1. `block_id` não vazio;
2. `sequence` estritamente crescente;
3. o primeiro evento é `block_started` (stream que abre em outro evento está truncado);
4. no máximo um evento terminal;
5. nenhum evento **depois** do terminal.

## Outcome — fail-closed

```python
stream.outcome     # "completed" | "failed" | "incomplete"
stream.succeeded   # True apenas para "completed"
```

| Último evento | `outcome` | `succeeded` |
|---------------|-----------|-------------|
| `block_completed` | `completed` | `True` |
| `block_failed` | `failed` | `False` |
| qualquer outro | `incomplete` | `False` |
| stream vazio | `incomplete` | `False` |

**Regra normativa: `incomplete` NUNCA pode ser tratado como sucesso.** Um
executor morto no meio da execução tem que ser indistinguível de um que falhou —
ausência de evidência de sucesso não é evidência de sucesso. Todo consumidor de
UEP herda essa regra.

## Estrito ao emitir, tolerante ao ler

Aplicação deliberada do princípio de Postel:

| | Produtor (`emit`) | Consumidor (`from_dict`, `from_ndjson`) |
|---|---|---|
| tipo de evento desconhecido | `ValueError` | aceito; `is_known_type == False` |
| chave obrigatória do payload ausente | `ValueError` | aceito |
| campo desconhecido no envelope | preservado | preservado em `extensions` |
| `schema_version` futura | preservada | preservada |

Como produtor, o Maestro é estrito porque emitir lixo contamina **todo**
consumidor a jusante. Como consumidor, é tolerante porque recusar um evento de
um produtor mais novo quebra justamente a interoperabilidade que o protocolo
existe para criar.

Para **retransmitir** um evento de outro produtor (inclusive de tipo
desconhecido), use `append()` em vez de `emit()`.

## Uso

```python
from packages.core.protocol import UEP, EventType

stream = UEP(block_id=packet.block_id, run_id=packet.run_id, ucp_id=packet.ucp_id)
stream.emit(EventType.BLOCK_STARTED, ucp_digest=packet.digest())
stream.emit(EventType.FILE_READ, path="arquivo.py", tokens=120)
stream.emit(EventType.FILE_WRITTEN, path="arquivo.py", bytes=340)
stream.emit(EventType.TEST_RUN, command="python -m unittest", passed=True)
stream.emit(EventType.BLOCK_COMPLETED, summary="pronto")

stream.validate()
stream.succeeded        # True
stream.files_written()  # ["arquivo.py"]
stream.tests_passed()   # True
```

## NDJSON

`to_ndjson()` / `from_ndjson()` operam sobre **string**, sem I/O. Uma linha JSON
por evento: formato append-only, resistente a truncamento — se o processo morrer
no meio de uma escrita, as linhas anteriores continuam válidas.

`from_ndjson()` **pula** linha vazia e linha com JSON inválido em vez de abortar:
um registro corrompido não pode cegar o stream inteiro. É a mesma política de
`HandoffManager.list_open()` em [handoff.md](handoff.md).

```
{"schema_version":1,"event_type":"block_started","block_id":"BLOCO-EXEMPLO","sequence":1,...}
{"schema_version":1,"event_type":"file_written","block_id":"BLOCO-EXEMPLO","sequence":2,...}
{"schema_version":1,"event_type":"block_completed","block_id":"BLOCO-EXEMPLO","sequence":3,...}
```

## Trust boundary

Payload de evento vai para log e para o Evidence Store — atravessa a mesma
fronteira que o UCP e passa pelo mesmo scanner, em `emit()` e na construção de
qualquer `UCPEvent`. Detalhes em [protocol.md](protocol.md#trust-boundary).

Recomendação para `file_read` / `file_written`: use caminho **relativo à raiz do
projeto**. Caminho absoluto expõe a árvore de diretórios do usuário em todo log.

## JSON Schema

Fonte de verdade: `packages.core.protocol.schema.UEP_EVENT_JSON_SCHEMA` e
`UEP_JSON_SCHEMA`. O teste T13 falha se este documento divergir das dataclasses.

### Evento

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://maestro.dev/schemas/uep-event-v1.json",
  "title": "Universal Event Protocol event",
  "type": "object",
  "required": ["event_type", "block_id"],
  "additionalProperties": true,
  "properties": {
    "schema_version": { "type": "integer", "minimum": 1 },
    "event_type": {
      "type": "string",
      "description": "One of the six protocol events. Readers must accept unknown values from future producers without failing."
    },
    "block_id": { "type": "string", "minLength": 1 },
    "sequence": { "type": "integer", "minimum": 0 },
    "timestamp": { "type": "string" },
    "agent": { "type": "string" },
    "run_id": { "type": "string" },
    "event_id": { "type": "string" },
    "payload": { "type": "object" }
  }
}
```

### Stream

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://maestro.dev/schemas/uep-v1.json",
  "title": "Universal Event Protocol stream",
  "type": "object",
  "required": ["block_id"],
  "additionalProperties": true,
  "properties": {
    "schema_version": { "type": "integer", "minimum": 1 },
    "block_id": { "type": "string", "minLength": 1 },
    "run_id": { "type": "string" },
    "ucp_id": { "type": "string" },
    "agent": { "type": "string" },
    "events": { "$comment": "array of uep-event-v1.json", "type": "array" }
  }
}
```

### Payload por tipo

O JSON Schema do envelope declara `payload` como objeto livre porque o leitor
precisa aceitar payload de produtor futuro. As chaves obrigatórias da tabela do
topo são aplicadas **só na emissão**, por
`packages.core.protocol.uep.REQUIRED_PAYLOAD_KEYS`.
