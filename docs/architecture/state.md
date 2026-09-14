# Estado canônico do Maestro — `.maestro/`

Bloco de origem: **F3-02**. Módulo: `scripts/maestro_state.py`.

Este documento é o contrato de dados do qual dependem `maestro status` (F4-01), o
complexity engine (F5-01), os hooks (F10-03) e o memory core (F11-01).

> **Regra dura:** `maestro_state.py` é a **única** porta de leitura e escrita de
> `.maestro/project.yaml` e `.maestro/state.json`. Nenhum outro módulo abre esses
> arquivos diretamente. Alterar qualquer assinatura da API pública é uma quebra de
> contrato que exige revisão dos quatro blocos acima.

---

## 1. Layout em disco

```
.maestro/
├── project.yaml     identidade do projeto      — VERSIONADO
└── state.json       estado operacional corrente — DERIVADO / EFÊMERO
```

F3-02 cria **apenas** esses dois artefatos. `blocks/`, `runs/`, `memory/` e
`evidence/` pertencem aos blocos que os introduzem; cada um deve chamar
`ensure_state_dir()` antes de criar o próprio subdiretório.

`state.json` é derivado e não deve ser versionado. Quando o repositório do usuário
tiver controle de versão, a entrada esperada é:

```
.maestro/state.json
```

A raiz do projeto vem sempre de `maestro_runtime.get_root()` (F3-01). Quando
`get_root()` retorna `None`, `maestro_state` usa `Path.cwd()` — o mesmo fallback
silencioso já estabelecido em `resolve_path()`. `maestro_state` **não** duplica a
lógica de descoberta de raiz.

---

## 2. API pública

```
StateError(Exception)                         # única exceção lançada pelo módulo

state_dir(root=None)          -> Path         # <root>/.maestro
project_file(root=None)       -> Path         # <root>/.maestro/project.yaml
state_file(root=None)         -> Path         # <root>/.maestro/state.json

ensure_state_dir(root=None)   -> Path         # cria .maestro/ se ausente; nunca sobrescreve
init(root=None)               -> dict         # cria .maestro/ + project.yaml + state.json ausentes

read_project(root=None)       -> dict         # normalizado e validado; levanta StateError se inválido
write_project(doc, root=None) -> Path         # valida antes de escrever; escrita atômica
validate_project(doc)         -> (errors, warnings)   # listas de str; NUNCA levanta

read_state(root=None)         -> dict         # NUNCA levanta; estado vazio se ausente/ilegível
write_state(state, root=None) -> Path         # valida, carimba last_updated, escrita atômica
validate_state(doc)           -> (errors, warnings)   # listas de str; NUNCA levanta

empty_state()                 -> dict         # estado vazio canônico
default_project(root=None)    -> dict         # project.yaml canônico inferido do ambiente
```

`validate_project` aceita um parâmetro opcional adicional `root=None`, usado apenas
para emitir o aviso de "projeto movido". A chamada `validate_project(doc)` do
contrato permanece válida e é a forma preferida.

### Contrato com `lock.py`

O campo `locks` de `state.json` é um **registro declarativo e consultivo**.
`maestro_state` não adquire, não libera e não verifica validade de lock.
`plano/.lock` (lock de arquivo, interprocesso) continua sendo o mecanismo real de
exclusão mútua. Este schema apenas reserva e valida a forma do slot.

---

## 3. Schema — `.maestro/project.yaml`

| Campo | Tipo | Obrigatório | Regra de validação |
|---|---|---|---|
| `schema` | int | não (default `1`) | deve ser exatamente `1`; outro valor = erro `schema desconhecido` |
| `id` | string | **sim** | `^[a-z0-9][a-z0-9._-]{0,63}$` |
| `name` | string | **sim** | 1 a 120 caracteres, não só espaços |
| `version` | string | **sim** | não vazia, sem espaço nas bordas |
| `root` | string | **sim** | caminho absoluto |
| `maestro_version` | string | **sim** | não vazia, sem espaço nas bordas |

- Chave desconhecida no topo: **warning**, não erro (compatibilidade progressiva).
- `root` divergente da raiz corrente: **warning** (`projeto movido`), não erro.

### Forma plana é a canônica

A forma canônica é **plana**: cinco chaves no topo. A forma aninhada do
documento-mestre é aceita **na leitura** e normalizada por `normalize_project()`:

| Forma aninhada | Forma plana |
|---|---|
| `project.id` | `id` |
| `project.name` | `name` |
| `project.version` | `version` |
| `project.root` | `root` |
| `maestro.version` | `maestro_version` |

A escrita **nunca** reproduz a forma aninhada. Blocos a jusante veem uma única forma.

Razões da forma plana: torna os critérios de aceite verificáveis literalmente;
`maestro_version` no topo não colide com `project.version`; e um nível de
aninhamento a menos é um modo de falha a menos no parser restrito.

### Valores default (`default_project()`)

Nenhum valor é inventado. Todos derivam do ambiente:

| Campo | Origem |
|---|---|
| `id` | nome do diretório raiz, minúsculo, caracteres fora do padrão trocados por `-` |
| `name` | nome do diretório raiz, como está |
| `version` | constante `"0.0.0"` |
| `root` | `str(root)` com `/` como separador |
| `maestro_version` | `MAESTRO_VERSION` do ambiente → `<root>/.claude-plugin/plugin.json` campo `version` → `"0.0.0"` |

---

## 4. Subconjunto YAML — por que não há PyYAML

`project.yaml` é YAML por definição do documento-mestre. A biblioteca padrão do
Python não tem parser YAML e `PyYAML` não pode ser assumido como instalado.

| Opção | Decisão |
|---|---|
| Declarar `PyYAML` como dependência | **Rejeitada.** Exigir `pip install` antes do primeiro `maestro status` quebra o requisito de funcionar apenas com CLI. |
| Usar `PyYAML` se disponível, parser interno se não | **Rejeitada.** Produz comportamento não determinístico entre máquinas: o mesmo arquivo seria aceito na máquina A e rejeitado na B. Inaceitável para uma fonte de verdade. |
| Parser interno de subconjunto restrito, sempre | **Aceita.** Determinístico em qualquer máquina, pequeno o bastante para ser correto, e fail-closed. |

**Consequência:** `.maestro/project.yaml` **não é YAML arbitrário**. É o subconjunto
abaixo. Nenhum bloco pode escrever listas, blocos multilinha, âncoras ou aninhamento
além de um nível nesse arquivo.

### Aceito

- linhas em branco;
- comentários: linha iniciada por `#`, ou `#` precedido de espaço após um valor não citado;
- `chave: valor` com indentação 0 ou 2 espaços (profundidade máxima 2);
- chave casando `[A-Za-z_][A-Za-z0-9_-]*`;
- escalares: string sem aspas, string entre `"` ou `'`, inteiro, `true`/`false`, `null`/`~`/vazio.

### Rejeitado — `StateError` com número de linha

| Construção | Exemplo |
|---|---|
| listas | `- item`, `[a, b]` |
| mapas inline | `{a: 1}` |
| blocos multilinha | `\|`, `>` |
| âncoras e aliases | `&ancora`, `*alias` |
| separadores de documento | `---`, `...` |
| tabulação como indentação | `\tchave: v` |
| indentação fora de múltiplo de 2 | `   chave: v` |
| profundidade maior que 2 | terceiro nível de aninhamento |
| chave duplicada no mesmo nível | `id:` duas vezes |

**Fail-closed:** na dúvida, erro. Nunca adivinhar a intenção. Uma construção fora do
subconjunto jamais é interpretada silenciosamente de forma errada.

---

## 5. Schema — `.maestro/state.json`

| Campo | Tipo | Obrigatório | Regra de validação |
|---|---|---|---|
| `schema` | int | não (default `1`) | deve ser exatamente `1` |
| `current_block` | string \| null | **sim** | se string: não vazia |
| `phase` | string \| null | **sim** | se string: não vazia |
| `last_updated` | string \| null | **sim** | se string: ISO-8601 UTC terminando em `Z` |
| `locks` | lista | **sim** | cada item é objeto com `id`, `owner`, `acquired_at` obrigatórios; `scope` e `expires_at` opcionais |
| `blocks` | objeto | não (default `{}`) | chave = id do bloco; valor = objeto com `status` obrigatório |

`blocks[*].status` ∈ `planned`, `ready`, `running`, `review`, `completed`,
`blocked`, `failed`, `cancelled`. Qualquer outro valor é **erro**.

`blocks[*].blocked_by`, quando presente, é lista de ids de bloco.

`last_updated` é carimbado por `write_state()` com `datetime.now(timezone.utc)`.
`datetime.utcnow()` não é usado em nenhum caminho.

### Estado vazio canônico

```json
{"schema": 1, "current_block": null, "phase": null, "last_updated": null, "locks": [], "blocks": {}}
```

Este é exatamente o valor retornado por `empty_state()` e por `read_state()` em
qualquer condição de falha.

---

## 6. Invariantes

| # | Invariante |
|---|---|
| **I1** | **Não destruição.** Nenhum caminho de código sobrescreve um arquivo existente em `.maestro/` sem que o chamador passe um documento completo por `write_project`/`write_state`. `init()` e `ensure_state_dir()` são idempotentes. |
| **I2** | **Leitura de estado não falha.** `read_state()` retorna estado vazio para diretório ausente, arquivo ausente, JSON malformado, erro de permissão e tipo raiz errado. Nunca levanta. |
| **I3** | **Leitura de identidade falha alto.** `read_project()` levanta `StateError` com mensagem descritiva quando o arquivo está ausente ou inválido. |
| **I4** | **Escrita atômica.** Toda escrita usa arquivo temporário no mesmo diretório seguido de `os.replace()`. |
| **I5** | **Validação antes de escrita.** `write_project` e `write_state` validam e levantam `StateError` antes de tocar o disco. |
| **I6** | **Agnóstico a agente.** Nenhum campo, valor ou caminho do schema nomeia Claude Code, Codex ou qualquer harness. Campos `agent`, `model`, `provider` e `harness` são proibidos em `state.json`. |
| **I7** | **Agnóstico a plano.** `maestro_state` não lê `plano/blocos.json` nem `maestro.config.json`. A validação de `current_block` é interna a `state.json` (ver I8), nunca consulta o plano. |
| **I8** | **Coerência de bloco corrente.** Se `blocks` é não vazio e `current_block` é não nulo, `current_block` deve ser chave de `blocks` — caso contrário, erro. |
| **I9** | **`project.yaml` é versionado; `state.json` não.** |
| **I10** | **Escritor único.** O módulo assume um escritor por vez. Exclusão mútua real é responsabilidade de `plano/.lock`. |

---

## 7. CLI

```
python scripts/maestro_state.py --validate
python scripts/maestro_state.py --init
python scripts/maestro_state.py --show [--json]
python scripts/maestro_state.py --validate --root /caminho/do/projeto
```

| Comando | Comportamento | Saída |
|---|---|---|
| `--validate` | Garante `.maestro/`; valida `project.yaml` (cria com defaults se ausente) e `state.json` (se existir). Imprime erros e warnings. | `0` válido, `1` inválido, `2` erro de execução |
| `--init` | Cria `.maestro/`, `project.yaml` e `state.json` ausentes. Não sobrescreve. | `0` sempre que não houver erro de IO |
| `--show` | Imprime identidade e estado corrente em texto legível. | `0` / `2` |
| `--json` | Modifica `--validate` e `--show` para saída JSON em uma linha. | idem |
| `--root PATH` | Sobrepõe a raiz descoberta. | — |

Sem argumento: imprime o docstring do módulo e sai com `0`.

O módulo depende somente da biblioteca padrão do Python 3.9+. Não requer Claude
Code, não requer Codex e não requer instalação de pacote: é por isso que
`maestro status` (F4-01) funciona apenas com CLI.

---

## 8. Como blocos a jusante devem consumir

```python
import maestro_state

# leitura tolerante — nunca quebra a UI
estado = maestro_state.read_state()

# leitura estrita — identidade é pré-requisito
try:
    projeto = maestro_state.read_project()
except maestro_state.StateError as exc:
    ...  # mensagem já é descritiva; não reinterpretar

# escrita — read, modify, write do documento inteiro
estado["current_block"] = "F4-01"
estado["blocks"]["F4-01"] = {"status": "running"}
maestro_state.write_state(estado)   # carimba last_updated automaticamente

# antes de criar subdiretório próprio
raiz_estado = maestro_state.ensure_state_dir()
```

Regras para o consumidor:

1. Sempre passe o documento **inteiro** para `write_state` — o módulo não faz merge parcial.
2. Nunca escreva `last_updated` à mão; `write_state` carimba.
3. Nunca abra `project.yaml` ou `state.json` diretamente.
4. Nunca grave caminho absoluto da máquina em `state.json`.
5. Antes de criar um subdiretório de `.maestro/`, chame `ensure_state_dir()`.
