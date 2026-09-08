# F2-02 — B-WIN: localização de scripts cross-platform

## 1. Identificação
- Complexidade: C3
- Modelo: claude-sonnet-5
- Revisor: claude-opus-5
- Depende de: F2-01
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco, nenhum comando ou skill do Maestro depende de `find` ou de `python3`, e a sequência de localização de script existe em um único lugar. Hoje o Maestro quebra no PowerShell e em qualquer máquina onde o executável se chame `python`.

## 3. Escopo
- Criar `skills/maestro-runtime/SKILL.md` com a sequência canônica de detecção de interpretador e localização de script.
- Substituir, nos 6 arquivos que hoje trazem `find ~/...`, a instrução inline por uma referência à skill `maestro-runtime`.
- Substituir toda ocorrência de `python3 <script>` por `python <script>` com fallback documentado.
- Replicar cada alteração em `plugins/maestro/`.

## 4. Não faça
- Não escreva um script Python que localize outro script Python. O problema é circular: se o interpretador ainda não foi detectado, um localizador em Python não roda. A detecção é uma instrução em linguagem natural para o agente, não código.
- Não use `where`, `which`, `Get-ChildItem`, `dir /s` nem qualquer variante de busca dependente de shell. A sequência é uma lista de caminhos candidatos testados um a um.
- Não altere a lógica de nenhum comando além da localização do script e do nome do interpretador.
- Não crie um `maestro-runtime` que repita conselho genérico. Ele contém a sequência de caminhos e nada mais.
- Não toque em `agents/*.md` — eles não contêm `find ~/`.

## 5. Contrato

`skills/maestro-runtime/SKILL.md` expõe dois procedimentos nomeados, citáveis pelos outros arquivos:

**`interpretador`** — ordem de tentativa, parar na primeira que responder:
1. `python --version`
2. `python3 --version`
3. `py -3 --version`

Se nenhuma responder: não há interpretador. O agente lê `plano/blocos.json` diretamente e monta o quadro à mão.

**`localizar <nome-do-script>`** — ordem de tentativa, parar no primeiro caminho que existir:
1. `scripts/<nome>`
2. `.claude/plugins/maestro/scripts/<nome>`
3. `.claude/skills/../scripts/<nome>`
4. `${CLAUDE_PLUGIN_ROOT}/scripts/<nome>` se a variável estiver definida
5. Caminho informado pelo usuário

Se nenhum existir: reporte quais caminhos foram tentados e siga o fallback declarado no comando que chamou.

## 6. Regras
**R1.** Todo arquivo que hoje contém `find ~/.claude/plugins/cache/maestro ...` passa a dizer, em uma linha: *"Use a skill `maestro-runtime`, procedimento `localizar`, para encontrar `<nome>.py`, e o procedimento `interpretador` para saber como invocá-lo."*

**R2.** Os 6 arquivos afetados na raiz, confirmados por inspeção em 2026-09-08:
`commands/custos.md`, `commands/status.md`, `skills/maestro-setup/SKILL.md`, `skills/migrar-plano/SKILL.md`, `skills/planejar-projeto/SKILL.md`. Antes de editar, rode `python scripts/verificar-repo.py --check portabilidade` e trate a lista que ele imprimir como autoritativa — ela pode incluir arquivos além destes.

**R3.** Cada edição na raiz é replicada byte-a-byte em `plugins/maestro/`. A verificação `paridade` prova isso.

**R4.** O fallback "leia `plano/blocos.json` diretamente" já existe em `commands/status.md` e `commands/custos.md` e deve ser preservado, com o acréscimo explícito: *nunca invente números que o script não retornou*.

**R5.** Ao substituir `python3` por `python`, mantenha uma menção ao fallback na forma `python <script>` (ou `python3` se `python` não existir) — a verificação `portabilidade` aceita essa forma exata.

## 7. Arquivos
- `skills/maestro-runtime/SKILL.md` (criar) e cópia em `plugins/maestro/`
- `commands/*.md` (editar apenas as linhas de localização/interpretador) e cópias
- `skills/maestro-setup/SKILL.md`, `skills/migrar-plano/SKILL.md`, `skills/planejar-projeto/SKILL.md`, `skills/executar-bloco/SKILL.md` e cópias

## 8. Dados
Nenhum valor de negócio. Os caminhos candidatos estão fixados na seção 5 desta spec.

## 9. Critérios de aceite (EARS)
1. QUANDO a verificação `portabilidade` roda O SISTEMA DEVE reportar zero ocorrências da string `find ~/` em `commands/`, `agents/` e `skills/`, nas duas cópias.
2. QUANDO a verificação `portabilidade` roda O SISTEMA DEVE reportar zero ocorrências de `python3 ` como comando literal, nas duas cópias.
3. O SISTEMA DEVE conter `skills/maestro-runtime/SKILL.md` com os procedimentos `interpretador` e `localizar`.
4. QUANDO um comando precisa localizar um script O SISTEMA DEVE referenciar a skill `maestro-runtime` em vez de repetir a sequência de busca.
5. SE nenhum interpretador Python for encontrado ENTÃO O SISTEMA DEVE instruir o agente a ler `plano/blocos.json` diretamente e nunca a inventar os números do quadro.
6. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1/T2 — `python scripts/verificar-repo.py --check portabilidade` sai com 0.
- T3 — `skills/maestro-runtime/SKILL.md` existe e contém as duas palavras `interpretador` e `localizar` como cabeçalhos.
- T4 — cada um dos arquivos listados por R2 contém a string `maestro-runtime`.
- T5 — `commands/status.md` ainda contém a instrução de não inventar números.
- T6 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T7 — borda: `/maestro:status` executado a partir do PowerShell não emite nenhum comando que contenha `find`.

## 11. Pare e pergunte
- Se `verificar-repo.py --check portabilidade` listar um arquivo fora dos 6 previstos em R2 e a correção exigir mudar a lógica do comando, e não só a linha de localização → pare e pergunte.
- Se algum comando depender de `find` para algo que não seja localizar um script do Maestro → pare e pergunte; isso é outro problema.
- Se a variável `CLAUDE_PLUGIN_ROOT` não existir neste runtime → pare e pergunte antes de remover o item 4 do procedimento `localizar`.
