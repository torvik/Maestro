# F2-03 — B-VERSAO: coerência de versão

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Revisor: claude-sonnet-5
- Depende de: F2-01 · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, a versão declarada no `plugin.json` é a mesma do `CHANGELOG.md` e do `VERSAO.md`. Hoje `plugin.json` diz `1.1.0` enquanto o CHANGELOG já registra `1.2.0` — quem instala pelo marketplace vê a versão errada e o `migrar-plano` compara contra um número falso.

## 3. Escopo
- Corrigir o campo `version` em `.claude-plugin/plugin.json` e na cópia sob `plugins/maestro/`.
- Conferir e, se preciso, corrigir a versão citada em `VERSAO.md` e na cópia.

## 4. Não faça
- Não edite `CHANGELOG.md`. Ele é a fonte de verdade neste bloco.
- Não faça bump para `1.3.0`. A fase 2 ainda não foi entregue; a versão corrente continua sendo a do último release publicado.
- Não altere nenhum outro campo do `plugin.json` (`description`, `keywords`, `author`).

## 5. Contrato
Fonte de verdade: a primeira string no formato `\d+\.\d+\.\d+` que aparece em `CHANGELOG.md`. Destinos: campo `version` de todo `plugin.json`, e a versão citada em `VERSAO.md`.

## 6. Regras
**R1.** Leia a versão do `CHANGELOG.md`; não a digite de memória nem a copie desta spec.
**R2.** Se houver mais de um `plugin.json` no repositório, todos recebem o mesmo valor.
**R3.** `plugin.json` continua sendo JSON válido, com a mesma indentação de 2 espaços.

## 7. Arquivos
`.claude-plugin/plugin.json`, `plugins/maestro/.claude-plugin/plugin.json`, `VERSAO.md`, `plugins/maestro/VERSAO.md`.

## 8. Dados
O número da versão vem exclusivamente do `CHANGELOG.md` do repositório. Não há valor nesta spec para copiar.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE registrar em `.claude-plugin/plugin.json` a mesma versão declarada no topo do `CHANGELOG.md`.
2. QUANDO a verificação `versao` roda O SISTEMA DEVE reportar zero divergências entre `plugin.json`, `VERSAO.md` e o topo do `CHANGELOG.md`.
3. SE existir mais de um `plugin.json` no repositório ENTÃO O SISTEMA DEVE exigir que todos declarem a mesma versão.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/verificar-repo.py --check versao` sai com 0.
- T2 — `python -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])"` imprime a versão do CHANGELOG.
- T3 — borda: `python scripts/verificar-repo.py --check paridade` continua saindo com 0.

## 11. Pare e pergunte
- Se `CHANGELOG.md` e `VERSAO.md` discordarem entre si → pare e pergunte qual é a versão publicada. Não escolha a maior.
- Se o `CHANGELOG.md` tiver uma entrada `Unreleased` no topo → pare e pergunte.
