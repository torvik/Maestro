---
name: Toda alteração precisa ir para as duas cópias do plugin
description: `commands/`, `agents/`, `skills/` e `scripts/` existem duplicados na raiz e em `plugins/maestro/`, hoje byte-a-byte idênticos
type: project
---

O repositório mantém duas cópias idênticas de `commands/`, `agents/`, `skills/` e `scripts/`: uma na raiz e outra sob `plugins/maestro/`. Verificado por `diff -rq` em 2026-09-08: nenhuma divergência entre elas.

**Why:** a raiz serve à instalação manual (o usuário copia para `.claude/`), e `plugins/maestro/` serve ao marketplace. Editar só uma das cópias produz um bug que não aparece no ambiente de quem editou — só no do usuário que instalou pelo outro caminho.

**How to apply:** todo bloco que toca esses quatro diretórios declara ambos os caminhos em `arquivos_permitidos`, e o `comando_teste` inclui `python scripts/verificar-repo.py --check paridade` (verificação criada pelo bloco F2-01). Se `verificar-repo.py` ainda não existir, use `diff -rq` manualmente antes de dar o trabalho por pronto.

Divergência real encontrada em 2026-09-08 e registrada como bloco F2-03: `.claude-plugin/plugin.json` declara `1.1.0` enquanto `CHANGELOG.md` e `VERSAO.md` já estão em `1.2.0`.
