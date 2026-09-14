# Maestro

## Como usar

1. `python scripts/status.py` — veja o quadro do plano.
2. `python scripts/maestro_next.py` — identifique o próximo bloco liberado.

## Regra de paridade

Qualquer mudança em `scripts/` deve ser espelhada em `plugins/maestro/scripts/`
(conteúdo byte a byte idêntico). O mesmo vale para `commands/`, `agents/` e
`skills/` em relação às suas cópias em `plugins/maestro/`.

## Verificação

`python scripts/verificar-repo.py`

## Nota

O template de `CLAUDE.md` para projetos externos que adotam o Maestro está em
`integrations/claude-code/CLAUDE.md.template`.
