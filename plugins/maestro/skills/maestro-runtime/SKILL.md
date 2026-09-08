---
name: maestro-runtime
description: Procedimentos canônicos de detecção de interpretador Python e localização de scripts do Maestro. Cross-platform (Windows e Linux). Use sempre que um comando ou skill precisar rodar um script Python do Maestro.
---

# Maestro Runtime

## interpretador

Detecte o interpretador Python testando nesta ordem. Pare na primeira que responder:

1. `python --version`
2. `python3 --version` — se `python` não responder
3. `py -3 --version`

Se nenhuma responder: não há interpretador disponível. Siga o fallback declarado no comando que chamou — nunca invente os dados que o script retornaria.

## localizar `<nome-do-script>`

Teste os caminhos nesta ordem. Pare no primeiro que existir:

1. `scripts/<nome>`
2. `.claude/plugins/maestro/scripts/<nome>`
3. `.claude/skills/../scripts/<nome>`
4. `${CLAUDE_PLUGIN_ROOT}/scripts/<nome>` — se a variável estiver definida
5. Caminho informado pelo usuário

Se nenhum existir: reporte os caminhos tentados e siga o fallback declarado no comando que chamou.
