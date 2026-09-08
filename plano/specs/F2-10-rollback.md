# F2-10 — F-ROLLBACK: `/maestro:rollback <ID>`

## 1. Identificação
- Complexidade: C4
- Modelo: claude-sonnet-5 · Revisor: claude-opus-5
- Depende de: F2-07
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco o dono desfaz um bloco aprovado por engano, com um comando, sem tocar no git à mão. O desenho está fechado nesta spec; a incerteza de design que classificava o bloco como C4 — o que fazer quando existem commits posteriores — está resolvida na regra R4.

## 3. Escopo
- Criar `commands/rollback.md` e a cópia em `plugins/maestro/commands/rollback.md`.

## 4. Não faça
- **Nunca** use `git reset`, `git checkout --`, `git restore`, `git clean` nem `git push --force`. A única operação permitida é `git revert`. Reverter cria um commit novo; resetar apaga história e é irrecuperável para quem já puxou.
- Não faça rollback de mais de um bloco por invocação. Reversão em cadeia é decisão do dono, um passo por vez.
- Não decremente `tentativas`. Rollback não apaga o fato de que a tentativa aconteceu.
- Não remova registros de `plano/metricas.json`. O arquivo é append-only (F2-07, R9).
- Não faça `git stash` para contornar uma árvore suja. Recuse e devolva ao dono.
- Não resolva conflito de revert automaticamente.

## 5. Contrato

Entrada: `$ARGUMENTS` = um ID de bloco.

Fonte do SHA: o registro **mais recente** com `veredito: "aprovado"` e `commit_sha` não nulo, para aquele `id`, em `plano/metricas.json`.

Fase 1 — inspeção, sem escrita:
```
bloco   <id> — <titulo>   estado atual: <estado>
commit  <sha>  <assunto>
git show --stat <sha>
posteriores que tocam os mesmos arquivos: <lista ou "nenhum">
```

Fase 2 — só após confirmação explícita: `git revert --no-edit <sha>`.

Fase 3 — sucesso:
```
blocos.json: estado -> "pendente";
             notas  += "<AAAA-MM-DD> rollback do commit <sha>"
tentativas: inalterado
```

## 6. Regras
**R1 — pré-condições, verificadas nesta ordem, todas antes de qualquer escrita.** Falha em qualquer uma encerra sem tocar em git nem em JSON:
1. o ID existe em `plano/blocos.json`;
2. existe registro aprovado com `commit_sha` para esse ID em `plano/metricas.json`;
3. `git status --porcelain` retorna vazio;
4. não há revert, merge ou rebase em andamento;
5. o SHA existe no repositório (`git cat-file -e <sha>^{commit}`).

**R2.** Se a pré-condição 2 falhar, recuse e diga ao dono para reverter à mão. Não tente descobrir o commit por mensagem, por data nem por heurística — adivinhar qual commit reverter é a forma de destruir trabalho alheio.

**R3.** Confirmação explícita é obrigatória em todos os casos, inclusive quando não há commits posteriores. Não existe modo `--sim`, `--force` nem equivalente.

**R4 — commits posteriores.** Antes de confirmar, rode `git log --oneline <sha>..HEAD -- <arquivos do commit alvo>`. Se a lista não estiver vazia, exiba-a e exija uma segunda confirmação, avisando que o revert pode desfazer trabalho posterior nesses arquivos. Lista vazia dispensa a segunda confirmação.

**R5 — conflito.** Se `git revert` terminar em conflito: rode `git revert --abort`, confirme com `git status --porcelain` que a árvore voltou a ficar limpa, reporte os arquivos em conflito e **não** altere `plano/blocos.json`. Fail-closed: o repositório volta ao estado de antes do comando.

**R6.** A alteração de `plano/blocos.json` só acontece depois de o revert concluir sem conflito.

**R7.** O commit do revert não é feito por este comando além do que o próprio `git revert --no-edit` faz. Não faça um commit adicional para a mudança em `blocos.json` — deixe-a na árvore e diga ao dono.

**R8.** A data da nota vem do sistema.

**R9.** Front-matter com `argument-hint: <ID>`.

## 7. Arquivos
`commands/rollback.md` e `plugins/maestro/commands/rollback.md`. Nada mais é criado ou editado por este bloco.

## 8. Dados
O SHA vem de `plano/metricas.json`. A lista de arquivos e de commits posteriores vem do git. A data vem do sistema. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO o comando recebe um ID O SISTEMA DEVE localizar o `commit_sha` em `plano/metricas.json` e exibir `git show --stat` antes de qualquer alteração.
2. O SISTEMA DEVE usar `git revert` e nunca `git reset`, `git checkout --` nem `git clean`.
3. SE o bloco não tiver `commit_sha` em `plano/metricas.json` ENTÃO O SISTEMA DEVE recusar e instruir o usuário a reverter manualmente.
4. SE a árvore de trabalho tiver alterações não commitadas ENTÃO O SISTEMA DEVE recusar e não tocar no git.
5. SE existirem commits posteriores que alteram os mesmos arquivos ENTÃO O SISTEMA DEVE listá-los e pedir confirmação explícita adicional antes de reverter.
6. SE `git revert` terminar em conflito ENTÃO O SISTEMA DEVE rodar `git revert --abort`, deixar o repositório no estado anterior e não alterar `plano/blocos.json`.
7. QUANDO o revert conclui sem conflito O SISTEMA DEVE gravar `estado: "pendente"`, deixar `tentativas` inalterado e acrescentar uma nota com o SHA revertido e a data.
8. O SISTEMA DEVE pedir confirmação explícita antes de executar o `git revert` em todos os casos.

## 10. Casos de teste obrigatórios
- T1 — bloco com `commit_sha` válido: o comando imprime o `--stat` e para para confirmar.
- T2 — o texto do comando não contém as strings `git reset`, `git checkout --`, `git clean` nem `--force`.
- T3 — bloco sem `commit_sha`: recusa; `git log` inalterado.
- T4 — com um arquivo modificado não commitado: recusa; `git status` inalterado.
- T5 — commit posterior tocando o mesmo arquivo: a lista aparece e há segunda confirmação.
- T6 — cenário de conflito forçado: após o comando, `git status --porcelain` volta vazio e `blocos.json` fica intacto (comparar hash).
- T7 — sucesso: `estado` vira `pendente`, `notas` cresce em 1 item com o SHA, `tentativas` igual ao valor anterior.
- T8 — usuário não confirma: nenhum commit novo em `git log`.
- T9 — borda: dois registros aprovados do mesmo bloco → o comando usa o `timestamp_fim` mais recente.
- T10 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se o commit alvo for um merge commit → pare e pergunte. `git revert -m` exige escolher o mainline, e essa escolha é do dono.
- Se o commit alvo já tiver sido enviado para um remoto com outros colaboradores → pare e avise antes de reverter.
- Se o commit do bloco contiver alterações fora dos `arquivos_permitidos` daquele bloco → pare e liste; reverter vai desfazer coisas que não pertencem ao bloco.
- Se houver mais de um registro aprovado e os `timestamp_fim` forem iguais → pare e pergunte qual SHA reverter.
