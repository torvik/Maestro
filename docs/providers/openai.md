# Provider OpenAI

`providers/openai/provider.py` implementa `OpenAIProvider`, a camada
concreta que traduz o roteamento abstrato de `packages/core/routing/`
(requisitos -> tier) em um nome de modelo OpenAI real, e gerencia saude,
quota e cooldown de 429 do provider.

Este bloco **nao faz chamadas de rede**. Nenhuma dependencia externa e
importada (`import openai` esta fora de escopo).

## Mapeamento tier -> modelo

| Tier | Modelo | Context tokens |
|---|---|---|
| low | `gpt-4o-mini` | 128 000 |
| medium | `gpt-4o` | 128 000 |
| high | `o1` | 128 000 |

Requirements vazios (`{}`) ou `None` **nao** sao fallback de erro: eles
satisfazem o piso de capacidades, entao `resolve()` (de `packages.core.routing`)
resolve normalmente para o tier `low` -> `gpt-4o-mini`.

Fallback (`medium` -> `gpt-4o`) so ocorre quando `resolve()` levanta uma
excecao (ex: campo invalido como `{'campo_invalido': 'x'}`, routing
indisponivel) -- o `except Exception` em `resolve_model` captura e forca
`tier = "medium"`.

## `resolve_model`

```python
from providers.openai.provider import OpenAIProvider

provider = OpenAIProvider()
provider.resolve_model({"review_required": True, "isolation_recommended": True})
# -> "o1"
```

Internamente, `resolve_model` usa um `ProviderRegistry` do
`packages.core.routing` registrado apenas com o `OpenAIProvider` de
roteamento (`packages.core.routing.providers.OpenAIProvider`), garantindo
que o tier retornado seja sempre um dos 3 tiers OpenAI (`low`, `medium`,
`high`). Qualquer excecao durante a resolucao (routing indisponivel,
requirements malformados) cai no fallback `medium`.

## `resolve_context`

Retorna o tamanho do context window (em tokens) do modelo resolvido por
`resolve_model`, usando a tabela `MODEL_CONTEXT`.

## `check_quota` / `check_health`

`check_quota` opera **offline** neste bloco:

```python
provider.check_quota()
# -> {"available": True, "reason": None}
```

`check_health` verifica apenas a presenca de uma API key (parametro
`api_key` no construtor ou variavel de ambiente `OPENAI_API_KEY`) --
nenhuma chamada de rede e feita:

```python
provider.check_health()
# sem API key configurada:
# -> {"healthy": False, "latency_ms": None, "error": "OPENAI_API_KEY ausente"}

provider = OpenAIProvider(api_key="sk-...")
provider.check_health()
# -> {"healthy": True, "latency_ms": None, "error": None}
```

A implementacao de verificacao real via API (latencia, chamada de rede)
fica para um bloco futuro.

## Cooldown de 429

`record_429(tentativa)` grava um cooldown em disco, com backoff exponencial:

```
backoff_seconds = min(2**tentativa * 5, 300)   # maximo 5 minutos
```

Arquivo: `.maestro/providers/openai/cooldown.json`

```json
{
  "until": "2026-09-14T12:30:00Z",
  "backoff_seconds": 60
}
```

Escrita atomica via `os.replace(tmp, path)`. `is_in_cooldown()` le o arquivo
e retorna `True` enquanto `until` estiver no futuro ou se o arquivo estiver
corrompido (fail-safe: duvida = assume em cooldown); retorna `False` se o
arquivo nao existir ou o cooldown ja tiver expirado.

## Registro de uso

`record_usage(block_id, model, tokens_in=0, tokens_out=0, cost_usd=0.0)`
appenda uma linha JSON (JSON Lines, append-only) em
`.maestro/providers/openai/usage.jsonl`:

```json
{"timestamp": "2026-09-14T12:00:00Z", "block_id": "F6-02", "model": "gpt-4o", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
```

O diretorio e criado automaticamente se nao existir. A escrita e atomica via
`os.replace(tmp, path)`.
