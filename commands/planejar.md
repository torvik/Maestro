---
description: Escreve a spec de um bloco (ou planeja um projeto novo) com o arquiteto no Opus.
argument-hint: [ID do bloco ou descrição do que planejar]
---

Se `$ARGUMENTS` contiver `--fase <nome>`: registre o plano em `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Passe `--fase <nome>` ao `validar-plano.py` ao final.

Use a skill `planejar-projeto` e delegue ao agente `arquiteto`.

Alvo: $ARGUMENTS

Se for um bloco existente sem spec, escreva a spec no padrão de 11 seções. Se for um projeto ou fase nova, quebre em blocos, atribua complexidade C1–C5 e modelo a cada um, e registre em `plano/blocos.json`.

Antes de escrever, confirme as suposições que mudariam a arquitetura. Ao terminar, encontre e rode `validar-plano.py` (mesma estratégia de caminhos do `/maestro:status`) e resolva qualquer ERRO.
