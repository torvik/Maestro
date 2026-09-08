---
description: Configura o Maestro neste projeto por conversa — detecta specs, faz poucas perguntas e gera o plano.
---

Se `$ARGUMENTS` contiver `--fase <nome>`: crie o plano em `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Informe o arquiteto que este é um plano multifase.

Use a skill `maestro-setup` para configurar o Maestro neste projeto.

Detecte o que já existe antes de perguntar qualquer coisa. Faça no máximo 6 perguntas, uma por vez, sempre com um padrão sugerido que o usuário possa aceitar com um "pode ser". Ao final, gere `maestro.config.json` e `plano/blocos.json`, valide, e mostre o quadro de status com o próximo bloco liberado.
