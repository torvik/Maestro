# F2-17 — D-SETUP-STEP5: passo de fechamento da skill `maestro-setup`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Revisor: claude-sonnet-5
- Depende de: F2-06, F2-08, F2-09, F2-10, F2-11 · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, quem acabou de rodar `/maestro:setup` vê todos os comandos disponíveis, agrupados por uso. Hoje o Passo 5 se chama "Fechar com as três ações" e lista apenas `status`, `proxima` e `planejar` — o usuário novo nunca descobre o resto.

## 3. Escopo
- Reescrever o passo de fechamento de `skills/maestro-setup/SKILL.md`.
- Replicar em `plugins/maestro/skills/maestro-setup/SKILL.md`.

## 4. Não faça
- Não altere os Passos 1 a 4 nem a seção "Nunca".
- Não deixe o título dizendo "as três ações". O título muda junto com a lista.
- Não derive a lista deste documento. Derive de `commands/` no momento da execução.
- Não descreva comando que você não leu.
- Não transforme o passo em tutorial. Uma linha por comando.

## 5. Contrato
Duas listas, nesta ordem:
```
**No dia a dia**            (no maximo 4 itens)
- `/maestro:<nome>` — <uma linha>

**Quando algo sai do trilho**
- `/maestro:<nome>` — <uma linha>
```
A união das duas listas é exatamente o conjunto de arquivos em `commands/`.

## 6. Regras
**R1.** Primeiro grupo com no máximo 4 itens. Uma lista de doze itens iguais não é lida.
**R2.** Todo arquivo de `commands/` aparece em exatamente um dos dois grupos.
**R3.** As descrições saem do conteúdo de cada arquivo de comando.
**R4.** O título do passo é reescrito para não citar um número que vai mudar de novo.
**R5.** Alteração replicada byte-a-byte em `plugins/maestro/`.

## 7. Arquivos
`skills/maestro-setup/SKILL.md` e `plugins/maestro/skills/maestro-setup/SKILL.md`.

## 8. Dados
A lista vem de `commands/`. As descrições vêm de cada arquivo de comando. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE listar no passo de fechamento um item por arquivo existente em `commands/`.
2. O SISTEMA DEVE separar a lista em ações do dia a dia e ações de correção, com no máximo 4 itens no primeiro grupo.
3. QUANDO a verificação `comandos-documentados` roda O SISTEMA DEVE reportar zero divergências entre a lista e o conteúdo de `commands/`.
4. QUANDO a verificação `paridade` roda O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/verificar-repo.py --check comandos-documentados` sai com 0.
- T2 — o primeiro grupo tem no máximo 4 itens.
- T3 — a união dos dois grupos é igual ao conjunto de `commands/*.md`, sem repetição.
- T4 — o título do passo não contém "três".
- T5 — os Passos 1 a 4 estão byte-a-byte iguais (capturar antes de começar).
- T6 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se não for óbvio em qual grupo um comando entra → pare e pergunte. `/maestro:custos` e `/maestro:exportar` são os casos de fronteira previstos.
- Se `commands/` tiver um número de arquivos diferente de 12 → pare e reporte antes de escrever.
