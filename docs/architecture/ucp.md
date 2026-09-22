# Universal Context Packet (UCP)

> `context_packet_version: 1` — implementado em `packages/core/protocol/ucp.py`.
> Visão geral e regras comuns aos dois protocolos: [protocol.md](protocol.md).

O UCP é o **contrato de dados** entregue de qualquer agente para qualquer
executor. Contém tudo que é necessário para executar um bloco e nada além disso.

```
Planner + Context Builder + Memory Engine ──UCP──► claude-code | codex | generic-cli | <futuro>
```

Nenhum tipo, campo ou chave do UCP nomeia um harness. Identificadores de agente
aparecem apenas como **dado** (`producer_agent`, `handoff.from_agent`).

## Campos

| Campo | Tipo | Obrigatório | Nota |
|-------|------|-------------|------|
| `block_spec` | objeto | **sim** | o que executar; `block_id` não pode ser vazio |
| `conventions` | objeto | sim (pode ser `{}`) | convenções do projeto |
| `context_files` | array | sim (pode ser `[]`) | arquivos do repositório |
| `memory_entries` | array | sim (pode ser `[]`) | memória recuperada |
| `budget` | objeto | sim (pode ser `{}`) | limites; todo limite é opcional |
| `handoff` | objeto ou `null` | **não** | contexto de retomada |
| `ucp_id` | string | gerado | `U-<YYYYMMDDTHHMMSS>-<8 hex>` |
| `run_id` | string | não | correlaciona com o UEP |
| `producer_agent` | string | não | id do agente produtor (dado) |
| `created_at` | string | gerado | ISO-8601 UTC, sufixo `Z` |
| `schema_version` | inteiro | default 1 | ver [versionamento](protocol.md#versionamento) |

Obrigatório **como contêiner** significa que vazio é válido: "nenhuma entrada de
memória relevante" é informação legítima. Exigir conteúdo faria o produtor
preencher lixo só para passar na validação.

### Normalizações

- `conventions` recebido como string vira `{"notes": "<string>"}`. Na rede é
  sempre objeto — adapters nunca enfrentam dois formatos.
- `budget` recebido como dict vira `Budget`; chaves desconhecidas são
  preservadas em `budget.extensions`.
- Limite negativo em `budget` → `ValueError`. A jusante um número negativo seria
  lido como "sem limite", e essa falha silenciosa é exatamente o que não se
  aceita num contrato.

## Uso

```python
from packages.core.protocol import UCPBuilder

packet = (UCPBuilder()
          .for_block("BLOCO-EXEMPLO",
                     spec_text="...",
                     allowed_paths=["pacote/**"],
                     test_command="python -m unittest")
          .with_conventions({"language": "python"})
          .add_context_file("arquivo.py", conteudo, tokens=120)
          .add_memory_entry("Evite reescrever o arquivo inteiro.", kind="procedural")
          .with_budget(max_turns=20, max_tokens=8000)
          .build())

wire = packet.to_json()
same = UCP.from_json(wire)          # round-trip fiel
packet.digest()                     # prova de qual pacote foi executado
```

`UCP.digest()` é o sha256 do conteúdo canônico **excluindo** `ucp_id` e
`created_at`, para que dois pacotes com as mesmas instruções tenham o mesmo
digest. É o valor que o evento `block_started` carrega em `ucp_digest`.

## Trust boundary

O UCP atravessa a fronteira de confiança do Maestro. Ele **nunca** pode conter
credencial, chave privada, token de provedor, dump de ambiente, `.env` ou PII.
A regra completa, o scanner e o remédio (`redact()`) estão em
[protocol.md](protocol.md#trust-boundary).

Consequência prática: **não existe instância de `UCP` em memória carregando
segredo** — a validação roda na construção e não tem flag para desligar.

### Obrigações do adapter

O protocolo não faz I/O, então ele não pode violar o sistema de arquivos — mas o
adapter que consome o UCP pode. Duas obrigações que **não** são verificáveis aqui:

1. `context_files[].path` é dado vindo do produtor e pode conter `../`. O adapter
   que escrever em disco a partir desse campo DEVE resolver o caminho contra a
   raiz do projeto e recusar o que escapar dela.
2. `block_spec.allowed_paths` é o limite de escrita do bloco. O adapter DEVE
   aplicá-lo; o UCP apenas o declara.

## JSON Schema

Fonte de verdade: `packages.core.protocol.schema.UCP_JSON_SCHEMA`. O teste T13
falha se este documento divergir das dataclasses.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://maestro.dev/schemas/ucp-v1.json",
  "title": "Universal Context Packet",
  "description": "Data contract handed from any agent to any executor. Carries no credentials, no raw environment and no user PII.",
  "type": "object",
  "required": ["block_spec"],
  "additionalProperties": true,
  "properties": {
    "schema_version": { "type": "integer", "minimum": 1 },
    "ucp_id": { "type": "string" },
    "run_id": { "type": "string" },
    "producer_agent": { "type": "string" },
    "created_at": { "type": "string", "description": "ISO-8601 UTC with a trailing Z." },
    "block_spec": {
      "type": "object",
      "required": ["block_id"],
      "additionalProperties": true,
      "properties": {
        "block_id": { "type": "string", "minLength": 1 },
        "title": { "type": "string" },
        "spec_text": { "type": "string" },
        "spec_path": { "type": "string" },
        "complexity": { "type": "string" },
        "acceptance_criteria": { "type": "array", "items": { "type": "string" } },
        "allowed_paths": { "type": "array", "items": { "type": "string" } },
        "forbidden_actions": { "type": "array", "items": { "type": "string" } },
        "stop_and_ask": { "type": "array", "items": { "type": "string" } },
        "test_command": { "type": "string" }
      }
    },
    "conventions": { "type": "object" },
    "context_files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path"],
        "additionalProperties": true,
        "properties": {
          "path": { "type": "string", "minLength": 1 },
          "content": { "type": "string" },
          "priority": { "type": "integer" },
          "tokens": { "type": "integer", "minimum": 0 },
          "truncated": { "type": "boolean" }
        }
      }
    },
    "memory_entries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [],
        "additionalProperties": true,
        "properties": {
          "id": { "type": "string" },
          "kind": { "type": "string" },
          "text": { "type": "string" },
          "source": { "type": "string" },
          "score": { "type": "number" }
        }
      }
    },
    "budget": {
      "type": "object",
      "required": [],
      "additionalProperties": true,
      "description": "Every limit is optional; null means 'no limit'.",
      "properties": {
        "max_turns": { "type": ["integer", "null"], "minimum": 0 },
        "max_tokens": { "type": ["integer", "null"], "minimum": 0 },
        "max_cost_usd": { "type": ["number", "null"], "minimum": 0 },
        "context_tokens": { "type": ["integer", "null"], "minimum": 0 },
        "exploration_files": { "type": ["integer", "null"], "minimum": 0 },
        "change_files": { "type": ["integer", "null"], "minimum": 0 }
      }
    },
    "handoff": {
      "description": "Optional: null when the block is not a resume.",
      "oneOf": [
        {
          "type": "object",
          "required": [],
          "additionalProperties": true,
          "properties": {
            "handoff_id": { "type": "string" },
            "from_agent": { "type": "string" },
            "to_agent": { "type": "string", "description": "An agent id, or the sentinel 'any'." },
            "context_summary": { "type": "string" },
            "next_steps": { "type": "array", "items": { "type": "string" } },
            "open_questions": { "type": "array", "items": { "type": "string" } },
            "files_touched": { "type": "array", "items": { "type": "string" } },
            "checkpoint": { "type": "object" }
          }
        },
        { "type": "null" }
      ]
    }
  }
}
```

`additionalProperties: true` em todo nível é intencional: é o que torna a
degradação graceful possível (ver [protocol.md](protocol.md)).

## Exemplo

```json
{
  "schema_version": 1,
  "ucp_id": "U-20260922T101530-a1b2c3d4",
  "run_id": "R-EXEMPLO",
  "producer_agent": "agent-a",
  "created_at": "2026-09-22T10:15:30Z",
  "block_spec": {
    "block_id": "BLOCO-EXEMPLO",
    "title": "Bloco de exemplo",
    "complexity": "C2",
    "acceptance_criteria": ["O SISTEMA DEVE expor exemplo()."],
    "allowed_paths": ["pacote/**"],
    "forbidden_actions": ["Nao escreva fora de pacote/."],
    "test_command": "python -m unittest"
  },
  "conventions": { "language": "python", "style": "stdlib only" },
  "context_files": [
    { "path": "arquivo.py", "content": "def exemplo():\n    return 1\n", "tokens": 12 }
  ],
  "memory_entries": [
    { "kind": "procedural", "text": "Evite reescrever arquivo.py inteiro." }
  ],
  "budget": { "max_turns": 20, "max_tokens": 8000, "max_cost_usd": 1.5 },
  "handoff": null
}
```

## Relação com o Context Builder

`ContextManifest` (`packages/core/context`) e `ContextFile` do UCP são
estruturalmente parecidos, mas o protocolo **não importa** o context builder —
ver a [regra da folha](protocol.md#a-regra-da-folha). A tradução
`ContextManifest → UCP` é trabalho do adapter (F14-02), não do protocolo.
