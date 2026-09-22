# Evidence Store (F8-01)

Módulo: `packages/core/evidence/` (`__init__.py` + `store.py`).

## Propósito

Grava em disco a evidência de execução de um bloco: o resultado da rodada
(`record_run`), o diff aplicado (`record_diff`) e a saída do teste de aceite
(`record_test_output`). O módulo apenas persiste dados — não interpreta,
não julga e não decide nada sobre o resultado do bloco.

## API pública

```python
EvidenceError(Exception)

class EvidenceStore:
    def __init__(self, root=None)
    # root=None -> maestro_runtime.get_root() ou Path.cwd()

    def record_run(self, block_id, result, provider=None, duration_seconds=None,
                    files_changed=None, commands_executed=None, test_result=None,
                    tentativas=0) -> Path

    def record_diff(self, block_id, diff_content) -> Path
    def record_test_output(self, block_id, output) -> Path
    def evidence_exists(self, block_id) -> bool
    def list_runs(self, block_id) -> list[Path]
```

## Layout em disco

```
.maestro/runs/<block_id>/<timestamp>.json
.maestro/evidence/<block_id>/diff-<timestamp>.patch
.maestro/evidence/<block_id>/test-<timestamp>.txt
```

`<timestamp>` = `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")`.

## Schema do run JSON

```json
{
  "schema": 1,
  "block_id": "...",
  "timestamp": "...",
  "result": "...",
  "provider": null,
  "duration_seconds": null,
  "files_changed": null,
  "commands_executed": null,
  "test_result": null,
  "tentativas": 0
}
```

## Resolução da raiz (`root=None`)

Quando `root` não é informado, o construtor tenta importar `maestro_runtime`
(adicionando `scripts/` ao `sys.path` a partir da localização do próprio
arquivo `store.py`) e chamar `maestro_runtime.get_root()`. Se o import falhar
ou `get_root()` retornar `None`, usa `Path.cwd()`.

## Invariantes

- **I1** — Append-only: nenhuma gravação sobrescreve um arquivo existente.
  Colisão de timestamp (duas chamadas no mesmo segundo) gera sufixo
  numérico incremental no nome do arquivo (`-2`, `-3`, ...).
- **I2** — Os diretórios `.maestro/runs/<block_id>/` e
  `.maestro/evidence/<block_id>/` são criados automaticamente se não
  existirem.
- **I3** — Escrita atômica: o conteúdo é gravado primeiro em um arquivo
  temporário no mesmo diretório e depois promovido com `os.replace()`,
  evitando arquivos truncados/parciais em caso de falha no meio da escrita.
- **I4** — `EvidenceError` é levantado se `block_id` for `None` ou string
  vazia, em qualquer método público.
- **I5** — Somente stdlib Python (`json`, `os`, `sys`, `datetime`, `pathlib`).
  Nenhuma dependência externa.
- **I6** — `__all__` do pacote tem exatamente 2 símbolos: `EvidenceStore` e
  `EvidenceError`.

## Erros

- `EvidenceStore().record_run("", "concluido")` → `EvidenceError("block_id ausente ou vazio")`
- Todo método público (`record_run`, `record_diff`, `record_test_output`,
  `evidence_exists`, `list_runs`) valida `block_id` da mesma forma.

## `evidence_exists(block_id)`

Retorna `True` se o diretório `.maestro/evidence/<block_id>/` existir
(ou seja, se já houve ao menos um `record_diff` ou `record_test_output`
para esse bloco), `False` caso contrário. Não considera `.maestro/runs/`.

## `list_runs(block_id)`

Retorna a lista ordenada (por nome de arquivo, portanto por timestamp) de
caminhos `.json` em `.maestro/runs/<block_id>/`. Lista vazia se o diretório
não existir.

## `validate_for_review(block_id, complexity)`

Gate de segurança para blocos C4 e C5: levanta `EvidenceError` se não existir
nenhum arquivo em `.maestro/evidence/<block_id>/`. Para C1/C2/C3 (ou
complexidade desconhecida), é no-op.

**Deve ser chamado pelo orquestrador antes de despachar o reviewer** em blocos
C4/C5. Padrão de uso:

```python
store.record_diff(block_id, git_diff)
store.record_test_output(block_id, test_output)
store.validate_for_review(block_id, "C4")  # levanta EvidenceError se sem evidência
# só então: despachar reviewer
```

## Uso

```python
from packages.core.evidence import EvidenceStore, EvidenceError

store = EvidenceStore()  # raiz resolvida via maestro_runtime.get_root()
store.record_run("F8-01", "concluido", provider="anthropic", tentativas=1)
store.record_diff("F8-01", diff_text)
store.record_test_output("F8-01", pytest_output)

if store.evidence_exists("F8-01"):
    runs = store.list_runs("F8-01")

# Para blocos C4/C5 — gate antes de despachar reviewer:
store.validate_for_review("F8-01", "C4")
```
