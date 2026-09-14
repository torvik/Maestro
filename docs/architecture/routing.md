# Roteamento por capacidades

`packages/core/routing` traduz **requisitos de capacidade** em um par
**provider/tier**. É a fronteira entre "que tipo de trabalho é este" e "quem
executa". O módulo é puro: só stdlib, sem IO, sem leitura de configuração e sem
estado global mutável.

## Por que capacidades, e não modelos

Nomes de modelo não aparecem em nenhum ponto deste módulo. O catálogo de
modelos de cada provider muda com frequência; a pergunta "este trabalho exige
raciocínio alto e revisão humana?" não muda. Amarrar o roteamento a nomes de
modelo faria cada troca de catálogo virar uma alteração de lógica de decisão,
com risco de regressão silenciosa em blocos de risco alto.

A tradução `tier -> modelo concreto` pertence à camada de execução, não a esta.

## Vocabulário

Capacidades ordinais (`low` < `medium` < `high`):

| Capacidade | Significado |
|---|---|
| `reasoning` | profundidade de raciocínio exigida |
| `context` | volume de contexto que precisa ser mantido |
| `coding` | exigência de geração/edição de código |
| `autonomy` | quanto o executor pode decidir sozinho |
| `risk` | consequência de um erro |

Capacidades booleanas:

| Capacidade | Significado |
|---|---|
| `review_required` | a saída exige revisão antes de valer |
| `isolation_recommended` | a execução deve ocorrer isolada |

Requisito ausente assume o **piso** (`low` / `False`). Ausência de requisito
nunca encarece a escolha.

## API

```python
from packages.core.routing import resolve, ProviderRegistry, RoutingError

resolve(requirements: dict, registry: ProviderRegistry = None) -> dict
```

Retorno:

| Campo | Conteúdo |
|---|---|
| `provider` | nome do provider vencedor |
| `tier` | tier escolhido dentro do provider |
| `capabilities` | capacidades declaradas do tier (podem superar o pedido) |
| `cost_weight` | peso relativo de custo do tier |
| `metadata` | requisitos normalizados, candidatos e providers descartados |

`metadata.candidates` vem ordenado por `(cost_weight, provider, tier)`, de modo
que o retorno de `resolve` não varia com a ordem de registro quando os custos
diferem.

`registry=None` usa `providers.default_registry()`, que constrói uma instância
nova a cada chamada. Injetar um registry torna a chamada independente de
ambiente — é como testes e chamadores que já resolveram sua própria política de
providers devem usar a função.

## Algoritmo

1. Normaliza e valida os requisitos.
2. Para cada provider, na ordem de registro: se `can_satisfy`, pede o tier mais
   barato que atende (`select_tier`).
3. Reconfere as capacidades do tier devolvido contra os requisitos.
4. Entre os candidatos, vence o de menor `cost_weight`.
5. Nenhum candidato: `RoutingError`.

**Desempate.** Custos iguais são resolvidos pela ordem de registro — registrar
um provider antes é a forma de declarar preferência. Como o registry faz parte
da entrada, o resultado permanece determinístico.

## Postura fail-closed

O módulo erra para o lado restritivo, nunca para o permissivo:

- **Chave desconhecida em `requirements` levanta `ValueError`.** Um requisito
  digitado errado seria silenciosamente ignorado e produziria roteamento
  sub-dimensionado — exatamente o erro que mais custa em blocos de risco alto.
- **Valor inválido levanta `ValueError`** em vez de cair no piso.
- **Tier que não confere é descartado.** Se um provider responde `can_satisfy =
  True` mas devolve um tier cujas capacidades não atendem ao pedido, o provider
  é descartado e registrado em `metadata.rejected`. Um provider mal
  implementado não consegue forçar uma escolha inadequada.
- **Nenhum candidato nunca vira um fallback.** Levanta `RoutingError`; não
  existe "tier padrão" quando a resolução falha.

## `RoutingError`

| Atributo | Conteúdo |
|---|---|
| `requirements` | requisitos normalizados que causaram a falha |
| `missing` | capacidades que nenhum provider atendeu |
| `per_provider` | capacidades faltantes por provider avaliado |

Com o registry vazio, `per_provider` é `{}` e `missing` lista os requisitos
acima do piso. Se nenhum requisito estava acima do piso, `missing` lista as
capacidades ordinais — a falha, nesse caso, é a ausência de providers, e a
mensagem da exceção diz isso explicitamente.

## Providers padrão

Tiers descritos apenas por capacidades e custo relativo. `cost_weight` é
ordinal e comparável **entre providers**; não é preço.

`anthropic`

| Tier | reasoning | context | coding | autonomy | risk | review | isolation | custo |
|---|---|---|---|---|---|---|---|---|
| fast | low | low | low | high | low | não | não | 1 |
| balanced | medium | medium | medium | medium | medium | não | não | 3 |
| advanced | high | medium | high | low | high | sim | não | 5 |
| maximum | high | high | high | low | high | sim | sim | 10 |

`openai`

| Tier | reasoning | context | coding | autonomy | risk | review | isolation | custo |
|---|---|---|---|---|---|---|---|---|
| low | low | low | low | high | low | não | não | 1 |
| medium | medium | medium | medium | medium | medium | não | não | 3 |
| high | high | high | high | low | high | sim | sim | 7 |

## Adicionando um provider

Herde `TieredProvider`, declare `name` e `TIERS` como tuplas
`(nome, capacidades, cost_weight)` do mais barato para o mais caro. Um provider
totalmente próprio só precisa expor `name`, `can_satisfy`, `select_tier`,
`capabilities` e `cost_weight`; `tier_names` é opcional e melhora o diagnóstico
em `RoutingError`.

Regra de calibração: `cost_weight` precisa ser comparável com o dos providers
existentes, senão o desempate por custo perde sentido entre providers.
