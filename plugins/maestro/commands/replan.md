---
description: Revisa o plano quando a realidade mudou — bloco maior que a spec, dependência nova, decisão tomada.
argument-hint: [o que mudou]
---

Delegue ao agente `arquiteto`.

Mudança: $ARGUMENTS

Se `$ARGUMENTS` contiver `--fase <nome>`: use `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Encerre com erro se o arquivo não existir. Passe `--fase <nome>` a qualquer script invocado.

Leia `plano/blocos.json` (ou o caminho resolvido acima) e as specs afetadas. Proponha as alterações **antes** de aplicar: quais blocos mudam de escopo, complexidade, modelo ou dependência, e se algum precisa ser quebrado em partes menores.

Regra: se um bloco falhou 2 vezes, a hipótese principal é que **a spec está ambígua**, não que o modelo é fraco. Corrija a spec antes de escalar o modelo.

Ao terminar, encontre e rode `validar-plano.py` (mesma estratégia de caminhos do `/maestro:status`) e resolva qualquer ERRO antes de devolver ao usuário.
