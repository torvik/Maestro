---
description: Executa o próximo bloco liberado do plano, no modelo que a complexidade exige.
argument-hint: [opcional: ID de um bloco específico]
---

Se `$ARGUMENTS` contiver `--fase <nome>`: resolva o plano como `plano/<nome>/blocos.json`. Encerre com erro se o arquivo não existir. Passe `--fase <nome>` a qualquer script invocado.

Se $ARGUMENTS contiver `--dry-run`: leia `plano/blocos.json` e `maestro.config.json`, identifique o próximo bloco liberado e exiba — ID, complexidade, modelo, agente, orçamento de turnos e arquivos_permitidos — sem despachar nada. `--dry-run` não consulta o lock, porque nada é escrito.

Se $ARGUMENTS NÃO contiver `--dry-run`: antes de delegar ao agente `maestro`, rode `lock.py status` — script localizado pela skill `maestro-runtime`, repassando `--fase <nome>` se recebido. Se sair com código 1: exiba ao dono o conteúdo impresso pelo script e ENCERRE sem delegar ao agente `maestro`. Se sair com código 0: prossiga normalmente para o passo abaixo.

Se $ARGUMENTS contiver `--paralelo`: delegue ao agente `maestro` com instrução de rodar `scripts/paralelo.py` para montar o lote. O maestro executa o ciclo de lote paralelo (até `max_paralelo` blocos simultâneos, com commits serializados). Bloco C5 nunca entra em lote.

Caso contrário, delegue ao agente `maestro`, usando a skill `executar-bloco`.

Alvo: $ARGUMENTS (se vazio, o maestro escolhe o próximo bloco liberado; se for um ID de bloco específico, execute aquele bloco)

Lembre o maestro das regras invioláveis: um bloco por sessão; bloco com `bloqueado_por` preenchido não é despachado; nenhum C5 vai para Haiku; o revisor é sempre igual ou superior ao executor; e nada é marcado como concluído sem o veredito do revisor.
