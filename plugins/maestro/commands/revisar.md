---
description: Dispara revisão de auditoria de um bloco específico, independente do fluxo de execução.
argument-hint: <ID do bloco>
---

Leia `plano/blocos.json` e encontre o bloco com id igual a $ARGUMENTS.

Se $ARGUMENTS estiver vazio, liste os blocos concluídos ou em_andamento e peça ao usuário qual revisar.

Usando a skill `executar-bloco` (seção 4 — Prompt de revisão), despache o agente `revisor` contra a spec do bloco. Passe o `revisor_modelo` declarado no bloco como `model` da invocação.

Ao receber o veredito:
- **APROVADO**: reporte ao usuário com a evidência.
- **REPROVADO**: reporte o que falta. Ofereça abrir `/maestro:replanejar` para corrigir a spec ou `/maestro:proxima <ID>` para re-executar.

Não altere o `estado` do bloco — esta revisão é de auditoria, não de execução.
