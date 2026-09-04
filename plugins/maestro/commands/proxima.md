---
description: Executa o próximo bloco liberado do plano, no modelo que a complexidade exige.
argument-hint: [opcional: ID de um bloco específico]
---

Delegue ao agente `maestro`, usando a skill `executar-bloco`.

Alvo: $ARGUMENTS (se vazio, o maestro escolhe o próximo bloco liberado)

Lembre o maestro das regras invioláveis: um bloco por sessão; bloco com `bloqueado_por` preenchido não é despachado; nenhum C5 vai para Haiku; o revisor é sempre igual ou superior ao executor; e nada é marcado como concluído sem o veredito do revisor.
