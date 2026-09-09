---
name: Maestro fase 3 (v1.4.0)
description: Plano F3 — 9 blocos, decisões de arquitetura do lock e do linter que não são deriváveis do código
type: project
---

Fase F3 planejada em 2026-09-08 (9 blocos F3-01..F3-09, alvo v1.4.0), substituindo o plano da F2 (concluída).

**Why:** o dono pediu 6 funcionalidades (órfãos, fallback de métricas, lock multissessão, template de spec, linter de spec, comando help). Virou 9 blocos porque lock e linter foram quebrados em script + integração, e porque a fase precisa de um bloco de fechamento de versão.

**How to apply:** três decisões de arquitetura valem para qualquer retrabalho nesses blocos e não estão no código:

1. **Lock**: `os.kill(pid, 0)` é proibido — no Windows o CPython encaminha para `TerminateProcess` e mata o processo alvo. Por isso não há sondagem de PID; a detecção de lock órfão é só por idade, e a recuperação exige `--forcar` explícito (fail-closed). O PID gravado é diagnóstico, nunca token de posse: cada invocação de `lock.py` é um processo novo e de vida curta. A posse é o conjunto de IDs de bloco. O lock é do **plano**, não do bloco, porque o que ele protege é a escrita em `blocos.json`.
2. **Órfãos**: `validar-plano.py` já detecta dependência inexistente e sai 1 — não duplicar lá. O furo é o `status.py`, onde o bloco órfão aparece como `(espera XX-99)` e fica invisível. Regra do projeto: `status.py` é relatório e sai 0 sempre; o portão binário é `verificar-repo.py`.
3. **Linter de spec**: a definição de "seção genérica" é duas listas literais fixadas na spec F3-06 (recusa por igualdade e recusa por frase). Sem elas o executor inventa o critério e o linter recusa spec legítima.

Armadilha conhecida: criar `commands/help.md` quebra `verificar-repo.py --check comandos-documentados` a menos que `INSTALACAO-USUARIO.md` e `skills/maestro-setup/SKILL.md` mencionem `/maestro:help` no mesmo bloco.

Falso positivo do validador: o termo "rápido" na lista VAGO faz qualquer critério que cite a seção "Início rápido" do help virar aviso. Contornado referenciando a seção 5 da spec em vez do título literal.
