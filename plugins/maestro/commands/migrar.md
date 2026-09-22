---
description: Migra a estrutura legada do plano (plano/blocos.json monolítico) para .maestro/blocks/ (um arquivo por bloco), com backup automático e relatório.
argument-hint: [--dry-run] [--force] [--plano <caminho>]
---

Use a skill `maestro-runtime` para localizar `maestro_migrate.py` (em `scripts/` ou na cópia do plugin) e invoque com o interpretador detectado, repassando `$ARGUMENTS` como estão (`--dry-run`, `--force`, `--plano <caminho>`).

## O que o comando faz

1. Detecta se o projeto está em estrutura legada:
   - `.maestro/blocks/` ausente ou vazio;
   - `plano/blocos.json` em array flat (sem chave `"blocos"`);
   - `maestro.config.json` com `maestro_versao` de major `< 2`.
2. Se já estiver migrado (`.maestro/blocks/` populado) e `--force` não foi passado: informa o estado atual e não altera nada.
3. Cria backup completo em `.maestro/migration-backup/<timestamp>/` **antes** de qualquer escrita.
4. Converte cada bloco de `plano/blocos.json` para `.maestro/blocks/<bloco-id>.json`, preservando todos os campos, estados e IDs.
5. Normaliza `plano/blocos.json` para o formato `{"blocos": [...]}` quando necessário — `scripts/status.py` e `scripts/maestro_next.py` continuam funcionando sem alteração.
6. Gera `migration-report.json` dentro do diretório de backup, com o que foi convertido, preservado e o que não pôde ser migrado automaticamente (ex.: blocos sem `id` válido ou com `id` duplicado).
7. Verifica, ao final, que `status.py` e `maestro_next.py` (quando presentes) rodam com código de saída 0 sobre o novo estado.

## Flags

- `--dry-run` — mostra exatamente o que seria feito (blocos a converter, se o plano seria normalizado, onde o backup ficaria) sem escrever nenhum arquivo.
- `--force` — migra novamente mesmo que `.maestro/blocks/` já exista e não esteja vazio. Cria um novo backup, incluindo cópia do `.maestro/blocks/` anterior.
- `--plano <caminho>` — usa um `plano/blocos.json` alternativo em vez do caminho padrão.

## Exemplos

```
/maestro:migrar --dry-run
/maestro:migrar
/maestro:migrar --force
/maestro:migrar --plano plano/fase-1/blocos.json
```

## Se a migração falhar

O comando é fail-safe: se qualquer etapa falhar depois que o backup foi criado, `plano/blocos.json` e `.maestro/blocks/` são restaurados automaticamente ao estado anterior — nenhum estado parcial fica no lugar. O diretório de backup nunca é apagado, mesmo em caso de falha, e fica em `.maestro/migration-backup/<timestamp>/` como evidência para investigação manual.

Se o comando reportar `ERRO: migracao falhou`:
1. Confirme que `plano/blocos.json` voltou ao conteúdo original (o comando já faz isso sozinho).
2. Inspecione `.maestro/migration-backup/<timestamp>/` para entender em qual etapa a falha ocorreu (o backup de `blocos.json.bak`, `blocks.bak/` e `maestro.config.json.bak` estará lá, mesmo sem `migration-report.json`, que só é escrito em caso de sucesso).
3. Rode `/maestro:migrar --dry-run` de novo para confirmar que o projeto voltou ao estado legado antes de tentar de novo.
4. Não edite `.maestro/blocks/` nem `plano/blocos.json` manualmente para "consertar" — corrija a causa raiz (ex.: JSON inválido, permissão de escrita) e rode o comando de novo.
