---
description: Recupera blocos em_andamento após sessão interrompida — analisa o que foi feito e oferece opções de continuação.
argument-hint: [opcional: ID do bloco]
---

Leia `plano/blocos.json` e identifique todos os blocos com `estado: "em_andamento"`.

Se $ARGUMENTS especifica um ID, foque nesse bloco. Caso contrário, liste todos os blocos em limbo.

Para cada bloco `em_andamento`:
1. Rode `git log --oneline -10` e `git diff HEAD~1..HEAD --stat` para entender o que foi feito desde que o bloco iniciou.
2. Verifique se os arquivos em `arquivos_permitidos` foram modificados.
3. Rode `comando_teste` do bloco — reporte se passa ou falha.
4. Apresente ao usuário:
   - O que foi feito (evidência do git)
   - Se os critérios de aceite parecem cobertos ou não
   - Três opções:
     - **(a) Retomar**: acione o agente `revisor` contra o código atual — se aprovado, marque como `concluido` e faça commit
     - **(b) Resetar**: volte o bloco para `pendente`, incremente `tentativas`, anote em `notas` o que travou
     - **(c) Descartar e refazer**: volte para `pendente` com `tentativas` inalterado, anote que foi descartado por sessão perdida

Execute a opção escolhida pelo usuário e atualize `plano/blocos.json`.
