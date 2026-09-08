---
name: Maestro fase 2 (v1.3.0) — plano de 17 blocos
description: Contexto e decisões arquiteturais por trás do plano F2-01..F2-17 criado em 2026-09-08
type: project
---

A fase 2 do Maestro (v1.3.0) foi planejada em 2026-09-08 como 17 blocos `F2-*` em `plano/blocos.json`. O `plano/` **não existia** antes disso — o repositório do plugin nunca foi gerenciado pelo próprio Maestro, apesar de o pedido supor que já havia blocos concluídos da v1.0→1.2. Não há blocos históricos registrados.

**Why:** o dono pediu para planejar bugs, comandos novos, observabilidade, execução paralela e distribuição de uma vez. Três decisões moldaram o plano e não são óbvias lendo só o JSON:

1. **F2-01 (`scripts/verificar-repo.py`) é fundacional e veio antes de tudo.** O repositório não tinha suíte de teste, então nenhum bloco teria `comando_teste` verificável. As 5 verificações (`paridade`, `portabilidade`, `comandos-documentados`, `versao`, `plano`) são o harness do resto da fase.
2. **F2-07 (métricas) grava `commit_sha`** porque F2-10 (rollback) precisa saber qual commit reverter, e nada no Maestro registrava isso. Sem F2-07, F2-10 teria de adivinhar o commit — o que a spec proíbe explicitamente.
3. **F-MULTIFASE e F-PARALELO foram quebrados em desenho + implementação** (F2-12/F2-13 e F2-14/F2-15). F2-14 tem permissão explícita de concluir que F-PARALELO deve ser **descartado**; recomendar o descarte é uma saída legítima daquele bloco.

**How to apply:** ao retomar a fase 2, comece por F2-01 e F2-05 (únicos liberados). Não trate o aviso do validador sobre "F2-12: C4 inteiro no modelo forte" como erro — é falso positivo, o C4 já está quebrado em dois e a justificativa está em `notas`. O mesmo vale para o alerta de 35% de custo em Opus: os dois blocos Opus são justamente os blocos de desenho dos splits.
