# Planner Core

`packages/core/planner/` é a biblioteca de análise de plano do Maestro. Ela responde
às perguntas estruturais que o scheduler precisa fazer **antes** de iniciar qualquer
execução: o plano é válido? há ciclo? em que ordem posso rodar? o que desbloqueia mais?

É uma biblioteca pura: só stdlib (Python 3.9+), sem estado global, sem chamada de
modelo, sem dependência de `maestro_state`, `maestro_runtime` ou `maestro_complexity`.
Importar o pacote não produz output nem executa IO.

## Os três níveis

| Nível | Entidade | O que representa |
| --- | --- | --- |
| L0 | `Plan` | objetivo global: `projeto`, `objetivo` |
| L1 | `Phase` | agrupamento de blocos por prefixo do id (`F0`, `F2`, ..., `F15`) |
| L2 | `Block` | unidade executável e atômica do grafo |

L2 é acessível por `plan.phases[i].blocks` ou, achatado, por `plan.all_blocks()`.

## API pública

`__all__` tem exatamente 8 símbolos:

```python
from packages.core.planner import (
    PlannerError,      # Exception
    load_plan,         # (path) -> Plan
    validate_plan,     # (path) -> None, levanta PlannerError se inválido
    detect_cycles,     # (blocks: list[dict]) -> list[list[str]]
    critical_path,     # (blocks: list[dict]) -> list[str]
    topo_sort,         # (blocks: list[dict]) -> list[str]
    Plan,              # dataclass L0
    Phase,             # dataclass L1
)
```

`Block` não é exportado no `__all__` — chega até quem chama através de
`Plan.all_blocks()` e `Plan.block_by_id()`.

## Modelo de dados

```python
@dataclass
class Block:
    id: str
    titulo: str
    fase: str            # campo "fase" se existir, senão prefixo do id
    complexidade: str
    estado: str
    depende_de: list[str]
    raw: dict            # cópia dos campos originais do bloco

@dataclass
class Phase:
    id: str
    blocks: list[Block]

@dataclass
class Plan:
    projeto: str
    objetivo: str
    phases: list[Phase]

    def all_blocks(self) -> list[Block]
    def block_by_id(self, id: str) -> Block | None
    def to_blocks(self) -> list[dict]     # reexporta no schema-blocos.md
```

### Derivação da fase

`fase` vem do campo `"fase"` do bloco quando ele existe. Quando não existe (o caso do
`plano/blocos.json` atual), é o prefixo do id: tudo antes do **último** `-`.
`"F0-01"` → `"F0"`, `"F10-03"` → `"F10"`. Id sem `-` vira a própria fase.

### Ordenação das fases

Ordenação natural, não lexicográfica: `F0 < F2 < F9 < F10 < F15`. A parte numérica do
id da fase é comparada como inteiro. Fases sem dígitos vão para o fim, em ordem
alfabética. Dentro de cada fase, os blocos mantêm a ordem do arquivo.

### Reexportação

`Plan.to_blocks()` devolve os dicts originais (cópias rasas), compatíveis com
`schema-blocos.md`. Um round-trip `load_plan(p).to_blocks()` preserva todos os campos
do arquivo, inclusive os que o `Block` não modela (`modelo`, `agente`,
`criterio_aceite`, `comando_teste`, `orcamento_turnos`, `tentativas`, `notas`, ...).
A ordem pode mudar: a saída sai agrupada e ordenada por fase.

## Validação

`validate_plan(path)` é **fail-closed**: nunca devolve `False` nem `None`
silenciosamente para um plano ruim. Ou retorna `None` (plano válido) ou levanta
`PlannerError`. As checagens rodam nesta ordem, e a primeira que falha aborta:

1. **Arquivo legível** — existe e é JSON válido → `arquivo inválido: ...`
2. **Formato** — lista raiz OU `{"blocos": [...]}`, todo item objeto com `id` não
   vazio → `formato desconhecido: ...`
3. **Ids únicos** → `ids duplicados: [...]`
4. **Dependências existem** — todo `depende_de` referencia um id do mesmo plano →
   `dependências ausentes: {id: [deps_faltantes]}`
5. **Sem ciclos** → `ciclo detectado: [ids do ciclo]`

A ordem importa: sem (3) o mapa de ids é ambíguo, e sem (4) uma dependência quebrada
seria confundida com um nó ausente do grafo.

### Advertências

Vão para **stderr** e não invalidam o plano — são sinais para quem opera, não erros:

- bloco sem `spec`, ou com `spec` apontando para arquivo inexistente;
- bloco com `estado: "em_andamento"` (sessão possivelmente interrompida).

O plano real do repositório emite advertências de spec inexistente para fases ainda
não especificadas. Isso é esperado e `validate_plan('plano/blocos.json')` passa.

## Algoritmos

Todos operam sobre `list[dict]` com as chaves `id` e `depende_de`. A aresta do grafo é
`bloco -> dependência`. Dependências que apontam para ids fora da lista são
**ignoradas** pelos algoritmos — reportá-las é responsabilidade da etapa 4 de
`validate_plan`, e assim as três funções continuam utilizáveis sobre subconjuntos do
plano (uma fase isolada, por exemplo).

### `detect_cycles(blocks) -> list[list[str]]`

DFS iterativa com coloração branco/cinza/preto. Ao encontrar uma aresta para um nó
cinza (já na pilha atual), recorta do caminho corrente o trecho mínimo que fecha o
loop. Ciclos são canonicalizados por rotação (rotacionados para começar no menor id),
o que evita reportar o mesmo ciclo duas vezes por caminhos diferentes. Retorna `[]`
num DAG. Complexidade O(V+E). Iterativa de propósito: um plano profundo não deve
estourar a pilha do interpretador.

### `topo_sort(blocks) -> list[str]`

Kahn. O grau de entrada de um bloco é o número de dependências distintas que ele tem
dentro do plano; um bloco entra na fila quando o grau chega a zero. O desempate é
determinístico pela ordem de aparição no arquivo — duas execuções sobre o mesmo
arquivo produzem a mesma lista. Se sobrar nó ao fim da fila, há ciclo e a função
levanta `PlannerError` já com os ids do ciclo.

Garantia: para todo bloco, todas as suas dependências aparecem antes dele.

### `critical_path(blocks) -> list[str]`

Longest path em DAG, por programação dinâmica sobre a ordem topológica:

```
comprimento[v] = 1 + max(comprimento[d] for d in deps(v))   # 1 se não tem deps
```

Guarda o predecessor que deu o máximo e reconstrói a cadeia de trás para frente.
Retorna os ids **em ordem de execução** (dependência primeiro). Levanta `PlannerError`
se houver ciclo (via `topo_sort`).

O peso é **contagem de blocos**, não complexidade nem tempo estimado. Um C5 pesa o
mesmo que um C1. Introduzir peso por complexidade mudaria a semântica do caminho
crítico e é decisão de outro bloco.

Interpretação prática: o caminho crítico é a cadeia mais longa de trabalho
estritamente sequencial. Nenhum paralelismo encurta o plano abaixo desse comprimento,
e atrasar qualquer bloco dele atrasa o plano inteiro.

## Invariantes

- **I1 — Puro.** Só `load_plan` e `validate_plan` fazem IO. `detect_cycles`,
  `topo_sort` e `critical_path` não tocam disco nem stderr.
- **I2 — Sem modificação.** Nenhuma função altera `blocos.json` nem os dicts de
  entrada. `Block.raw` é uma cópia; `Block.depende_de` é uma lista nova.
- **I3 — Fail-closed.** Plano inválido sempre vira exceção, nunca um retorno mudo.
- **I4 — Só stdlib** Python 3.9+.
- **I5 — `__all__` = 8 símbolos.**
- **I6 — Compatível com o plano real.** `validate_plan('plano/blocos.json')` passa.

## Exemplo

```python
from packages.core.planner import load_plan, critical_path, topo_sort

plano = load_plan("plano/blocos.json")
print(plano.projeto, len(plano.phases), len(plano.all_blocks()))

brutos = plano.to_blocks()
print(topo_sort(brutos)[:5])
print(critical_path(brutos))

bloco = plano.block_by_id("F0-01")
print(bloco.fase, bloco.complexidade, bloco.depende_de)
```
