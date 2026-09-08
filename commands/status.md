---
description: Mostra o quadro do plano — concluído, em andamento, liberado, travado.
---

Encontre e rode o script `status.py` do Maestro. Use a skill `maestro-runtime`: localize `status.py` com o procedimento `localizar` e invoque com o interpretador do procedimento `interpretador`. Se nenhum interpretador ou caminho existir: leia `plano/blocos.json` diretamente e exiba o quadro de estado, próximo bloco liberado e bloqueados. Nunca invente informação que o script não retornou.

Depois do quadro, acrescente em no máximo 4 linhas: qual é o próximo bloco liberado, o que está travando os bloqueados, e se algum bloco chegou a 2 tentativas e precisa de decisão. Se `plano/metricas.json` existir, o script já exibe um resumo de métricas (turnos usados vs orçados, reprovações). Não invente informação que o script não retornou.
