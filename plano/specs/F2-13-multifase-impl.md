# F2-13 — F-MULTIFASE (implementação): `--fase` em todos os comandos

> **PLACEHOLDER.** Este arquivo é substituído integralmente pelo bloco de desenho **F2-12**, executado pelo `arquiteto` em Opus. Não execute F2-13 enquanto este aviso estiver aqui — a spec ainda não existe.
>
> O conteúdo abaixo registra apenas as restrições já fixadas, que o desenho tem de respeitar.

## Restrições já fixadas (entrada para F2-12)

**Compatibilidade — requisito duro.** `plano/blocos.json` de um projeto v1.2 continua funcionando sem `--fase` e sem migração de arquivo.

**Colisão de id entre fases é erro de validação**, com código de saída 1. Nunca resolução silenciosa por ordem de leitura.

**Fail-closed na ambiguidade.** `--fase` ausente com mais de uma fase e sem `plano/blocos.json` não escolhe uma fase por conta própria: lista as fases e sai com 1, sem escrever.

**Superfície.** Todos os arquivos de `commands/`, `scripts/*.py`, `agents/maestro.md` e `skills/maestro-setup/SKILL.md`, nas duas cópias. A lista nominal é derivada de `commands/` no momento da execução de F2-12, não deste arquivo.

**Paridade.** Toda alteração na raiz é replicada byte-a-byte em `plugins/maestro/`. Verificado por `python scripts/verificar-repo.py --check paridade`.

**Regressão.** `python scripts/validar-plano.py` sem `--fase` sobre um plano legado produz o mesmo resultado que produzia antes da alteração. Capture a saída atual antes de começar.

**Orçamento.** 30 turnos. Se o desenho concluir que não cabe, F2-12 quebra em dois blocos em vez de inflar o orçamento.
