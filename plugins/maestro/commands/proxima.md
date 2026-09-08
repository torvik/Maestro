---
description: Executa o próximo bloco liberado do plano, no modelo que a complexidade exige.
argument-hint: [opcional: ID de um bloco específico]
---

Se `$ARGUMENTS` contiver `--fase <nome>`: resolva o plano como `plano/<nome>/blocos.json`. Encerre com erro se o arquivo não existir. Passe `--fase <nome>` a qualquer script invocado.

Se $ARGUMENTS contiver `--dry-run`: leia `plano/blocos.json` e `maestro.config.json`, identifique o próximo bloco liberado e exiba — ID, complexidade, modelo, agente, orçamento de turnos e arquivos_permitidos — sem despachar nada.

Caso contrário, delegue ao agente `maestro`, usando a skill `executar-bloco`.

Alvo: $ARGUMENTS (se vazio, o maestro escolhe o próximo bloco liberado; se for um ID de bloco específico, execute aquele bloco)

Lembre o maestro das regras invioláveis: um bloco por sessão; bloco com `bloqueado_por` preenchido não é despachado; nenhum C5 vai para Haiku; o revisor é sempre igual ou superior ao executor; e nada é marcado como concluído sem o veredito do revisor.
