# F2-01 — Harness de verificação do repositório (`verificar-repo.py`)

## 1. Identificação
- Complexidade: C3
- Modelo: claude-sonnet-5
- Revisor: claude-sonnet-5
- Depende de: nenhum
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco existe um script que prova, com código de saída, que o repositório do Maestro está internamente coerente. Ele é o `comando_teste` de quase todos os blocos da fase 2 — sem ele os outros blocos não têm verificação binária.

## 3. Escopo
- Criar `scripts/verificar-repo.py`.
- Copiar o arquivo idêntico para `plugins/maestro/scripts/verificar-repo.py`.
- Implementar exatamente 5 verificações: `paridade`, `portabilidade`, `comandos-documentados`, `versao`, `plano`.

## 4. Não faça
- Não corrija nenhum problema que o script encontrar. Este bloco só cria o detector. As correções são F2-02, F2-03, F2-04, F2-16 e F2-17. É esperado que a primeira execução do script **falhe** — isso não é motivo para alterar outros arquivos.
- Não altere `validar-plano.py` nem `status.py`.
- Não use `subprocess`, `os.system`, `git`, `find`, `diff` nem qualquer binário externo. O script roda em Windows e em Linux com o mesmo código.
- Não use dependências fora da biblioteca padrão.
- Não invente uma sexta verificação.

## 5. Contrato

Invocação:
```
python scripts/verificar-repo.py                 # roda as 5
python scripts/verificar-repo.py --check paridade
python scripts/verificar-repo.py --raiz <caminho>  # default: diretorio do script/..
```

Saída, uma linha por falha, em stdout:
```
FALHA <check> <caminho relativo>: <motivo em uma frase>
```
Última linha, sempre:
```
<n> verificacao(oes) executada(s), <m> falha(s)
```

Códigos de saída: `0` = nenhuma falha. `1` = ao menos uma falha. `2` = uso inválido (`--check` com nome desconhecido).

## 6. Regras

**R1 — `paridade`.** Para cada arquivo sob `commands/`, `agents/`, `skills/`, `scripts/` (recursivo), deve existir o gêmeo em `plugins/maestro/<mesmo caminho relativo>` com conteúdo byte-a-byte idêntico. Falha se ausente ou divergente. Também falha no sentido inverso: arquivo em `plugins/maestro/<dir>/` sem gêmeo na raiz. Exclua `__pycache__` e `*.pyc`. `verificar-repo.py` verifica a si próprio como qualquer outro arquivo.

**R2 — `portabilidade`.** Nenhum arquivo `.md` sob `commands/`, `agents/`, `skills/` (nas duas cópias) pode conter:
- a substring `find ~/`
- a substring `python3 ` (com espaço) — exceto quando precedida imediatamente por `ou ` dentro de uma linha que também contenha `python ` (fallback documentado é permitido)

Reporte uma falha por arquivo, citando a linha.

**R3 — `comandos-documentados`.** Seja `C` o conjunto de nomes derivados de `commands/*.md` (nome do arquivo sem extensão). O script verifica que:
- `INSTALACAO-USUARIO.md` menciona a string `/maestro:<nome>` para todo nome em `C`;
- `skills/maestro-setup/SKILL.md` menciona a string `/maestro:<nome>` para todo nome em `C`;
- nenhum dos dois arquivos menciona `/maestro:<x>` para um `x` que não esteja em `C`.

**R4 — `versao`.** A versão declarada em todo arquivo `.claude-plugin/plugin.json` do repositório, a primeira versão que aparece em `VERSAO.md` no formato `\d+\.\d+\.\d+`, e a primeira que aparece em `CHANGELOG.md` no mesmo formato, devem ser todas iguais. Falha lista os valores encontrados e sua origem.

**R5 — `plano`.** `plano/blocos.json` deve existir e ser JSON válido, e todo caminho no campo `spec` de cada bloco deve existir no disco. Esta verificação **não** duplica `validar-plano.py`; ela só checa existência de arquivo.

**R6.** Nenhuma verificação lança exceção não tratada. Erro de leitura de arquivo vira uma linha `FALHA`.

**R7.** O script funciona quando invocado de qualquer diretório de trabalho: resolva a raiz a partir de `Path(__file__).resolve().parent.parent`, salvo se `--raiz` for passado.

## 7. Arquivos
- `scripts/verificar-repo.py` (criar)
- `plugins/maestro/scripts/verificar-repo.py` (criar, idêntico)

Escrita fora destes dois caminhos reprova o bloco.

## 8. Dados
Nenhum valor de negócio. Os únicos literais são os nomes das 5 verificações e os diretórios listados em R1/R2, todos fixados nesta spec.

## 9. Critérios de aceite (EARS)
1. QUANDO o script roda sem argumentos O SISTEMA DEVE executar as 5 verificações e sair com código 0 se todas passarem.
2. SE qualquer verificação falhar ENTÃO O SISTEMA DEVE imprimir uma linha por falha no formato `FALHA <check> <caminho>: <motivo>` e sair com código 1.
3. QUANDO invocado com `--check <nome>` O SISTEMA DEVE executar apenas a verificação de nome informado.
4. SE `--check` receber um nome inexistente ENTÃO O SISTEMA DEVE listar os nomes válidos e sair com código 2.
5. O SISTEMA DEVE usar apenas a biblioteca padrão do Python 3.9+ e não invocar nenhum binário externo.
6. QUANDO um arquivo existe em `commands/`, `agents/`, `skills/` ou `scripts/` sem gêmeo byte-a-byte em `plugins/maestro/` O SISTEMA DEVE reportar falha na verificação `paridade`.

## 10. Casos de teste obrigatórios
- T1 — deriva do critério 1: rodar `python scripts/verificar-repo.py` e conferir que a última linha diz `5 verificacao(oes) executada(s)`.
- T2 — deriva do critério 2: rodar antes de F2-02 e conferir que `portabilidade` reporta as 5 ocorrências de `find ~/` já conhecidas.
- T3 — deriva do critério 3: `--check paridade` imprime só resultados de paridade.
- T4 — deriva do critério 4: `--check inexistente` sai com 2.
- T5 — deriva do critério 5: `grep` no fonte não encontra `subprocess`, `os.system`, nem `import` fora da stdlib.
- T6 — deriva do critério 6: apagar temporariamente `plugins/maestro/commands/status.md`, rodar, confirmar 1 falha de paridade, restaurar.
- T7 — borda: rodar de dentro de `scripts/` (`cd scripts && python verificar-repo.py`) e obter o mesmo resultado.
- T8 — borda: `versao` deve falhar hoje, porque `plugin.json` diz 1.1.0 e `CHANGELOG.md` diz 1.2.0. Falhar aqui é o comportamento correto.

## 11. Pare e pergunte
- Se `plugins/maestro/` contiver arquivo que **deveria** divergir da raiz por desenho → pare e pergunte antes de reportar como falha de paridade.
- Se `CHANGELOG.md` não tiver versão em formato `\d+\.\d+\.\d+` na primeira ocorrência → pare e pergunte qual é a fonte de verdade da versão.
- Se você concluir que alguma das 5 verificações é impossível sem binário externo → pare e pergunte, não relaxe a regra R6/R7 por conta própria.
