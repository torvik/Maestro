---
description: Desfaz um bloco aprovado usando git revert (nunca git reset). Exige confirmação explícita. Só opera quando a árvore está limpa.
argument-hint: <ID>
---

Se `$ARGUMENTS` contiver `--fase <nome>`: use `plano/<nome>/blocos.json` e `plano/<nome>/metricas.json` em vez dos caminhos legados. Encerre com erro se `blocos.json` não existir.

Leia `plano/blocos.json` (ou o caminho resolvido acima) e o `metricas.json` correspondente.

Se `$ARGUMENTS` estiver vazio: informe que o ID é obrigatório e liste os blocos com estado `concluido`. Pare.

## Pré-condições (verificar nesta ordem, antes de qualquer escrita)

1. O ID existe em `plano/blocos.json`.
2. Existe registro com `veredito: "aprovado"` e `commit_sha` não nulo para esse ID em `plano/metricas.json`. Se não existir: recuse e diga ao dono para reverter manualmente. **Não tente descobrir o commit por mensagem, data ou heurística.**
3. `git status --porcelain` retorna vazio. Se houver alterações não commitadas: recuse sem tocar no git.
4. Não há revert, merge ou rebase em andamento.
5. O SHA existe no repositório: `git cat-file -e <sha>^{commit}`.

Se qualquer pré-condição falhar: encerre sem gravar nada.

## Fase 1 — inspeção (sem escrita)

Exiba:
```
bloco   <id> — <titulo>   estado atual: <estado>
commit  <sha>  <assunto da mensagem>
```
Rode `git show --stat <sha>` e exiba a saída.

Se o commit alvo for um merge commit (`git cat-file -p <sha>` mostrar dois pais): **pare e pergunte** antes de continuar — `git revert -m` exige escolher o mainline e essa escolha é do dono.

## Fase 2 — commits posteriores

Rode: `git log --oneline <sha>..HEAD -- <arquivos do commit alvo>`

- Se a lista **não estiver vazia**: exiba-a e avise que o revert pode desfazer trabalho posterior. Exija confirmação explícita adicional antes de prosseguir.
- Se a lista **estiver vazia**: prossiga para a confirmação padrão.

## Fase 3 — confirmação e revert

Peça confirmação explícita. Silêncio ou ambiguidade encerra sem gravar.

Se confirmado: execute `git revert --no-edit <sha>`.

**Se o revert terminar em conflito:**
1. Execute `git revert --abort`.
2. Confirme com `git status --porcelain` que a árvore voltou limpa.
3. Reporte os arquivos em conflito.
4. **Não altere `plano/blocos.json`.**

## Fase 4 — sucesso (só após revert sem conflito)

Atualize `plano/blocos.json`:
- `estado` → `"pendente"`
- `notas` → acrescente `"<AAAA-MM-DD> rollback do commit <sha>"` (data do sistema)
- **Não altere** `tentativas`.

Não faça commit adicional — a mudança em `blocos.json` fica na árvore de trabalho.

## Nunca
- Nunca use `git reset`, `git checkout --`, `git restore`, `git clean` nem `git push --force`.
- Nunca faça rollback de mais de um bloco por invocação.
- Nunca decremente `tentativas`.
- Nunca remova registros de `plano/metricas.json`.
- Nunca resolva conflito de revert automaticamente.
- Nunca opere com árvore suja.
