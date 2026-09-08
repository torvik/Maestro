---
name: migrar-plano
description: Migra um plano/blocos.json criado com versão MAIOR mais antiga para o formato atual. Use quando /maestro:status detectar divergência de versão MAIOR entre plugin.json e maestro_versao do config.
---

# Migrar plano

Use quando o `status.py` exibir "ATENCAO: o plano foi criado na versao X.y.z e o plugin é A.b.c" com MAIOR diferente.

## Antes de migrar

1. Faça um commit do estado atual: `git add plano/ && git commit -m "backup: plano antes da migração para vX"`.
2. Leia `plano/blocos.json` e `maestro.config.json` completos.
3. Leia o `CHANGELOG.md` do Maestro para identificar as mudanças de formato entre as versões.

## O que preservar sempre

- `estado` de cada bloco (concluído deve permanecer concluído)
- `tentativas` e `notas` (histórico de falhas é informação valiosa)
- `depende_de` (grafo de dependências define a ordem de execução)
- `bloqueado_por` (bloqueios explícitos do usuário não devem ser perdidos)

## O que atualizar

Para cada campo adicionado na nova versão MAIOR que não existe no bloco:
- Se tem valor padrão documentado no schema: aplique o padrão
- Se não tem padrão e é obrigatório: preencha com `null` e sinalize como "requer revisão humana" em `notas`
- Nunca invente valores de negócio ou complexidade

## Ao terminar

1. Atualize `maestro_versao` em `maestro.config.json` para a versão instalada (leia de `.claude-plugin/plugin.json` — use a skill `maestro-runtime` procedimento `localizar` se necessário).
2. Use a skill `maestro-runtime` para localizar e rodar `validar-plano.py`.
3. Se houver ERROs: mostre ao usuário e aguarde correção antes de continuar.
4. Se houver só AVISOs: mostre e pergunte se o usuário quer continuar.
5. Faça um commit: `git commit -m "migração: plano atualizado para vX"`.

## Nunca

- Nunca migre silenciosamente. O usuário precisa saber que o formato mudou.
- Nunca altere `estado: "concluido"` de um bloco já concluído.
- Nunca descarte `notas` — é o histórico de decisões do projeto.
