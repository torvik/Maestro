---
description: Recupera blocos em_andamento após sessão interrompida — analisa o que foi feito e oferece opções de continuação.
argument-hint: [opcional: ID do bloco]
---

Se `$ARGUMENTS` contiver `--fase <nome>`: use `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Encerre com erro se o arquivo não existir.

Leia `plano/blocos.json` (ou o caminho resolvido acima) e identifique todos os blocos com `estado: "em_andamento"`.

Se $ARGUMENTS especifica um ID, foque nesse bloco. Caso contrário, liste todos os blocos em limbo.

Para cada bloco `em_andamento`:
0. Rode `lock.py status` — script localizado pela skill `maestro-runtime`, repassando `--fase <nome>` se recebido — e apresente ao dono a situação encontrada antes de qualquer outra ação:
   - **Lock ausente** (`LOCK LIVRE`, saída 0): a sessão morreu antes de adquirir o lock. Siga o fluxo normal abaixo (passos 1-4).
   - **Lock com os mesmos IDs do bloco em limbo**: é o lock da própria sessão morta. Ofereça `lock.py liberar --blocos <IDs>` ao dono antes de aplicar qualquer uma das três opções abaixo.
   - **Lock com IDs diferentes dos do bloco em limbo**: pode haver outra sessão viva executando o plano. NÃO libere o lock. Avise o dono e pare — não prossiga com as opções abaixo sem confirmação explícita dele. O uso de `--forcar` só ocorre depois dessa confirmação explícita, com o conteúdo do lock atual exibido na tela.
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

Execute a opção escolhida pelo usuário e atualize `plano/blocos.json`. Se o passo 0 identificou lock da própria sessão morta e o dono autorizou a liberação, libere-o (`lock.py liberar --blocos <IDs>`) como parte da execução da opção escolhida.
