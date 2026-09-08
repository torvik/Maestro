# F2-13 — F-MULTIFASE (implementação): `--fase` em todos os comandos

## 1. Identificação
- Complexidade: C4
- Modelo: claude-sonnet-5 · Agente: `implementador` · Revisor: claude-opus-5
- Depende de: F2-12
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco, todos os comandos e scripts do Maestro aceitam `--fase <nome>` para operar sobre `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Planos existentes continuam funcionando sem argumento e sem migração.

## 3. Escopo
- Alterar `scripts/status.py` para aceitar `--fase` e resolver o caminho do plano.
- Alterar `scripts/validar-plano.py` para aceitar `--fase`.
- Alterar `scripts/exportar-relatorio.py` para aceitar `--fase`.
- Alterar todos os 12 arquivos em `commands/` para passar `--fase` ao script quando o argumento for fornecido.
- Replicar cada alteração em `plugins/maestro/`.
- Acrescentar campo `fase_padrao` opcional a `maestro.config.json` (sem torná-lo obrigatório).

## 4. Não faça
- Não migre `plano/blocos.json` para `plano/<fase>/blocos.json`. Planos legados devem funcionar sem alteração.
- Não quebre o comportamento atual de nenhum comando quando `--fase` não é passado.
- Não crie um arquivo de índice de fases (`plano/fases.json`). A descoberta de fases é por `glob("plano/*/blocos.json")`.
- Não permita dependência entre blocos de fases diferentes — `validar-plano.py` reporta ERRO se `depende_de` contém `"fase:id"`.
- Não altere o formato de `blocos.json`. Nenhum campo novo é adicionado ao bloco.

## 5. Contrato

### Regras de precedência (4 regras, mutuamente exclusivas)

1. **`--fase <nome>` presente** → usa `plano/<nome>/blocos.json`. Erro se o arquivo não existir.
2. **`--fase` ausente e `plano/blocos.json` existe** → usa `plano/blocos.json` (modo legado, sem aviso).
3. **`--fase` ausente, sem `plano/blocos.json`, exatamente uma subpasta `plano/*/blocos.json`** → usa essa subpasta, imprimindo o caminho resolvido.
4. **`--fase` ausente, sem `plano/blocos.json`, duas ou mais subpastas** → erro com lista das fases disponíveis e instrução para passar `--fase`.

### Coexistência
Se `plano/blocos.json` e `plano/<fase>/blocos.json` coexistem sem `--fase`: a regra 2 vence (legado tem precedência). Justificativa: retrocompatibilidade é requisito duro.

### Dependência entre fases
`depende_de: ["outra_fase:F1-01"]` → ERRO de validação. Blocos de fases diferentes são planos independentes; a ordem entre eles é responsabilidade do dono.

### Colisão de ID
O mesmo `id` em duas fases é ERRO de validação se ambas forem carregadas na mesma invocação.

### Métricas por fase
`plano/<fase>/metricas.json` no layout multifase. `plano/metricas.json` é o caminho legado.

### `--fase` e `MAESTRO_PLANO`
`--fase` vence. Se `MAESTRO_PLANO` estiver definido e `--fase` for passado, o script imprime aviso e usa `--fase`.

### Arquivos a alterar (lista nominal)
`commands/setup.md`, `commands/status.md`, `commands/proxima.md`, `commands/planejar.md`, `commands/replanejar.md`, `commands/custos.md`, `commands/retomar.md`, `commands/revisar.md`, `commands/destravar.md`, `commands/editar.md`, `commands/rollback.md`, `commands/exportar.md` + cópias em `plugins/maestro/commands/`.
`scripts/status.py`, `scripts/validar-plano.py`, `scripts/exportar-relatorio.py` + cópias em `plugins/maestro/scripts/`.

## 6. Regras
**R1.** Todo script Python que lê `plano/blocos.json` deve aceitar `--fase <nome>` como argumento, resolvendo o caminho pelas 4 regras da seção 5.
**R2.** Em erro de resolução, o script sai com código 1 e imprime os caminhos tentados.
**R3.** `maestro.config.json` pode declarar `fase_padrao: "nome"` que equivale a `--fase nome` quando `--fase` não é passado. Não é obrigatório.
**R4.** `verificar-repo.py --check paridade` sai com 0 ao final.

## 7. Arquivos
12 arquivos de `commands/` + cópias, e 3 scripts Python + cópias (total: 30 arquivos). Nada mais.

## 8. Dados
O nome da fase vem de `$ARGUMENTS` do comando ou de `maestro.config.json`. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `--fase <nome>` é passado O SISTEMA DEVE usar `plano/<nome>/blocos.json` e reportar erro se não existir.
2. QUANDO `--fase` está ausente e `plano/blocos.json` existe O SISTEMA DEVE usá-lo sem aviso.
3. QUANDO `--fase` está ausente e existe exatamente uma fase em `plano/` O SISTEMA DEVE usá-la e imprimir o caminho resolvido.
4. QUANDO `--fase` está ausente e existem duas ou mais fases sem `plano/blocos.json` O SISTEMA DEVE exibir a lista e encerrar com código 1.
5. SE `depende_de` contém ID com prefixo de fase ENTÃO O SISTEMA DEVE reportar ERRO no `validar-plano.py`.
6. SE o mesmo ID aparecer em duas fases carregadas na mesma invocação ENTÃO O SISTEMA DEVE reportar ERRO de colisão.
7. O SISTEMA DEVE manter o comportamento atual de todos os comandos quando `--fase` não é passado.
8. QUANDO a verificação `paridade` roda O SISTEMA DEVE reportar zero divergências.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/status.py --fase principal` com arquivo existente: exibe quadro da fase.
- T2 — `python scripts/status.py` sem argumento com `plano/blocos.json` existente: comportamento idêntico ao atual.
- T3 — `python scripts/status.py --fase inexistente`: sai com 1, lista fases disponíveis.
- T4 — duas fases em `plano/` sem `plano/blocos.json` e sem `--fase`: sai com 1 e lista as fases.
- T5 — `validar-plano.py` com bloco contendo `"depende_de": ["outra:F1-01"]`: reporta ERRO.
- T6 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T7 — borda: `MAESTRO_PLANO` definido e `--fase` passado: usa `--fase` e imprime aviso.
- T8 — borda: `maestro.config.json` com `fase_padrao`: equivale a `--fase <valor>` sem argumento.

## 11. Pare e pergunte
- Se o parsing posicional de `status.py --bloco` (F2-08) conflitar com `--fase` → pare e pergunte antes de converter para `argparse`; mudar o parser afeta todos os scripts.
- Se o número de arquivos de `commands/` divergir de 12 → pare e reporte.
- Se a resolução automática de fase única (regra 3) causar confusão em projetos com outras pastas em `plano/` → pare e proponha restringir a `glob("plano/*/blocos.json")` com verificação de JSON válido.
