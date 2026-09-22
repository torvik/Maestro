# Context Builder (F9-01)

Módulo: `packages/core/context/` (`__init__.py` + `builder.py` + `manifest.py`).

## Propósito

Monta o **Context Manifest**: o contexto mínimo suficiente para um executor
implementar um bloco. O executor recebe **apenas** esse manifesto — sem
histórico de conversa e sem specs de outros blocos.

O módulo apenas coleta, prioriza e corta. Não interpreta a spec, não decide
nada sobre o bloco e não chama provider.

## API pública

```python
ContextError(Exception)

class ContextBuilder:
    def __init__(self, root=None, budget_tokens=8000, config_path=None)
    # root=None -> maestro_runtime.get_root() ou Path.cwd()
    # config_path=None -> <root>/maestro.config.json

    def build(self, block: dict) -> ContextManifest
    def estimate_tokens(self, text: str) -> int   # len(text) // 4
```

```python
@dataclass
class ContextFile:
    path: str        # relativo à raiz, sempre com barra normal
    content: str
    priority: int    # 1 = maior
    tokens: int

@dataclass
class ContextManifest:
    block_id: str
    spec: str            # conteúdo do arquivo de spec
    spec_path: str       # caminho relativo do arquivo de spec
    conventions: str
    files: list[ContextFile]
    omitted: list[str]
    gotchas: list[str]
    total_tokens: int
    budget_tokens: int

    def to_prompt(self) -> str
```

## Taxonomia de fontes de contexto

| Fonte | Origem | Prioridade | Disputa budget |
|---|---|---|---|
| Spec do bloco | `block["spec"]` | 1 | Não — sempre incluída |
| Convenções do projeto | `maestro.config.json["convencoes"]` | 2 | Não — sempre incluídas |
| Documentos e ADRs | `arquivos_permitidos` (`.md`, `adr*`, `*/adr*`) | 3 | Sim |
| Código | `arquivos_permitidos` (`.py`) | 4 | Sim |
| Demais arquivos | `arquivos_permitidos` (resto) | 5 | Sim |
| Gotchas / notas | `block["gotchas"]`, senão `block["notas"]` | — | Não |

Fontes **fora** da taxonomia nunca entram: histórico de conversa, specs de
outros blocos, saída de execuções anteriores.

## Regras de prioridade e budget

1. Spec e convenções entram sempre (invariante I1) e contam em
   `total_tokens`, mesmo que sozinhas já estourem o budget.
2. Os demais arquivos são ordenados por `(prioridade, tokens, caminho)` —
   prioridade mais alta primeiro e, dentro da mesma prioridade, o arquivo mais
   barato primeiro (mais arquivos cabem no mesmo budget).
3. Cada arquivo é incluído enquanto `total + tokens <= budget_tokens`. O que
   não couber vai para `omitted` — o corte é por arquivo inteiro, nunca por
   metade de arquivo.
4. Arquivo ilegível (erro de IO ou não-UTF-8) vai para `omitted` com o sufixo
   `(ilegível)` e não derruba o build.
5. A ordenação é totalmente determinística: duas chamadas com o mesmo disco
   produzem o mesmo manifesto (invariante I2).

Diretórios ignorados na expansão de globs: `__pycache__`, `.git`, `.maestro`,
`node_modules`.

## Formato de `to_prompt()`

```
Implemente o bloco <block_id> conforme o contexto abaixo.
Não implemente nada fora dos arquivos listados.

=== SPEC ===
<spec>

=== CONVENÇÕES ===
<conventions>

=== ARQUIVOS RELEVANTES ===
--- <path> ---
<content>

=== GOTCHAS / NOTAS ===
- <gotcha>

=== OMITIDOS (budget excedido) ===
- <path>
```

Seções vazias são omitidas. `to_prompt()` não faz nenhum IO (invariante I3) —
serializa apenas o que já está no manifesto.

## Invariantes

- **I1** — spec e convenções sempre incluídas no manifesto.
- **I2** — `build()` é determinístico para o mesmo estado de disco.
- **I3** — `to_prompt()` não lê arquivos nem acessa rede.
- **I4** — arquivo ilegível vai para `omitted`, sem crash.
- **I5** — só stdlib.
- **I6** — `__all__` tem exatamente 3 nomes:
  `ContextBuilder`, `ContextManifest`, `ContextError`.

## Erros

`ContextError` é levantado apenas por erro de configuração do chamador:
`block` que não é `dict` ou bloco sem `id`. Falhas de leitura de arquivo
nunca levantam exceção — viram `omitted`.
