# Convenções do projeto Maestro

## Estrutura de arquivos

Toda mudança em agents, commands ou skills deve ser aplicada em **duas cópias**:
1. `maestro-repo/<tipo>/arquivo.md` (cópia raiz)
2. `maestro-repo/plugins/maestro/<tipo>/arquivo.md` (cópia do plugin)

Ambas devem ficar idênticas após qualquer edição.

## Scripts Python

- Compatíveis com Python 3.8+
- Sem dependências externas (só stdlib)
- Cross-platform: sem `find`, sem `~`, sem separadores Unix hardcoded — usar `pathlib.Path`
- Saída em texto simples, sem cores ANSI obrigatórias

## Arquivos de instrução (agents, commands, skills)

- Markdown puro, sem frontmatter exceto nos agents
- Sem conselhos genéricos ("use código limpo", "siga boas práticas")
- Cada instrução deve ser verificável ou executável

## Versionamento

- Bugs e correções de texto: CORREÇÃO (patch)
- Recurso novo compatível: MENOR (minor)
- Mudança no formato de `plano/blocos.json` ou `maestro.config.json`: MAIOR
- Atualizar sempre: `plugin.json`, `CHANGELOG.md`, `VERSAO.md`
