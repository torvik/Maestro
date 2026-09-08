---
description: Mostra o quadro do plano — concluído, em andamento, liberado, travado.
---

Se `$ARGUMENTS` contiver `--fase <nome>`: passe `--fase <nome>` ao script invocado. O script resolve o caminho do plano pelas 4 regras de precedência.

Use a skill `maestro-runtime` para localizar `status.py` e invoque com o interpretador detectado.

- Sem argumentos: exibe o quadro geral do plano (estado, próximo bloco, bloqueados, distribuição por modelo e métricas se disponíveis).
- Com `--bloco <ID>`: exibe todos os detalhes do bloco (spec, critérios, dependências, notas, métricas).

Se nenhum interpretador ou caminho existir: leia `plano/blocos.json` diretamente e exiba o quadro de estado, próximo bloco liberado e bloqueados. Nunca invente informação que o script não retornou.

Depois do quadro, acrescente em no máximo 4 linhas: qual é o próximo bloco liberado, o que está travando os bloqueados, e se algum bloco chegou a 2 tentativas e precisa de decisão. Se `plano/metricas.json` existir, o script já exibe um resumo de métricas (turnos usados vs orçados, reprovações). Não invente informação que o script não retornou.
