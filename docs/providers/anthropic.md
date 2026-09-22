# Provider Anthropic

`providers/anthropic/provider.py` implementa `AnthropicProvider`, a camada
concreta que traduz o roteamento abstrato de `packages/core/routing/`
(requisitos -> tier) em um nome de modelo Anthropic real, e gerencia saude,
quota e cooldown de 429 do provider.

Este bloco **nao faz chamadas de rede**. Nenhuma dependencia externa e
importada (`import anthropic` esta fora de escopo -- ver F7-01).

## Mapeamento tier -> modelo

| Tier | Modelo | Context tokens |
|---|---|---|
| fast | `claude-haiku-4-5-20251001` | 200 000 |
| balanced | `claude-sonnet-4-6` | 200 000 |
| advanced | `claude-sonnet-4-6` | 200 000 |
| maximum | `claude-opus-4-6` | 200 000 |

Requirements vazios (`{}`) ou `None` **nao** sao fallback de erro: eles
satisfazem o piso de capacidades, entao `resolve()` (de `packages.core.routing`)
resolve normalmente para o tier `fast` -> `claude-haiku-4-5-20251001`.

Fallback (`balanced` -> `claude-sonnet-4-6`) so ocorre quando `resolve()`
levanta uma excecao (ex: campo invalido como `{'campo_invalido': 'x'}`,
routing indisponivel) -- o `except Exception` em `resolve_model` captura e
forca `tier = "balanced"`.

## `resolve_model`

```python
from providers.anthropic.provider import AnthropicProvider

provider = AnthropicProvider()
provider.resolve_model({"reasoning": "high"})
# -> "claude-sonnet-4-6" (ou outro modelo, dependendo do tier resolvido)
```

Internamente, `resolve_model` usa um `ProviderRegistry` do
`packages.core.routing` registrado apenas com o `AnthropicProvider` de
roteamento (`packages.core.routing.providers.AnthropicProvider`), garantindo
que o tier retornado seja sempre um dos 4 tiers Anthropic (`fast`, `balanced`,
`advanced`, `maximum`). Qualquer excecao durante a resolucao (routing
indisponivel, requirements malformados) cai no fallback `balanced`.

## `resolve_context`

Retorna o tamanho do context window (em tokens) do modelo resolvido por
`resolve_model`, usando a tabela `MODEL_CONTEXT`.

## `check_quota` / `check_health`

Ambos operam **offline** neste bloco (sem API key configurada nao ha
diferenca de comportamento, pois nenhuma chamada de rede e feita):

```python
provider.check_quota()
# -> {"available": True, "reason": None}

provider.check_health()
# -> {"healthy": True, "latency_ms": None, "error": None}
```

A implementacao de verificacao real via API fica para F7-01.

## Cooldown de 429

`record_429(tentativa)` grava um cooldown em disco, com backoff exponencial:

```
backoff_seconds = min(2**tentativa * 5, 300)   # maximo 5 minutos
```

Arquivo: `.maestro/providers/anthropic/cooldown.json`

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
`.maestro/providers/anthropic/usage.jsonl`:

```json
{"timestamp": "2026-09-14T12:00:00Z", "block_id": "F6-01", "model": "claude-sonnet-4-6", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
```

O diretorio e criado automaticamente se nao existir. A escrita e atomica via
`os.replace(tmp, path)`.

## `ProviderManager` (`packages/core/providers/`)

`ProviderManager` gerencia o ciclo de vida de providers concretos
registrados (nao apenas Anthropic): registro, consulta (`get`/`list`), health
check com cache TTL em memoria, e cooldown em memoria por nome de provider.
E independente da logica especifica de cada provider -- so exige o atributo
`name` e o metodo `check_health()`.

```python
from packages.core.providers import ProviderManager
from providers.anthropic.provider import AnthropicProvider

manager = ProviderManager()
manager.register(AnthropicProvider())
manager.list()                       # -> ["anthropic"]
manager.health_check("anthropic")    # -> ProviderInfo(...), cacheado por ttl_seconds
```
