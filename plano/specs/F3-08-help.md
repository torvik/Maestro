# F3-08 — F-HELP: comando `/maestro:help`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Agente: operario · Revisor: claude-sonnet-5
- Depende de: F3-04, F3-07 · Orçamento: 15 turnos
- Comando de teste: `python scripts/verificar-repo.py --check comandos-documentados && python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check portabilidade`

## 2. Objetivo
Depois deste bloco existe um ponto único de entrada que responde "o que eu rodo agora" sem o dono precisar abrir treze arquivos de comando ou o `INSTALACAO-USUARIO.md`. O comando cobre início rápido em três passos e referência completa de comandos, skills e scripts.

## 3. Escopo
- Criação de `commands/help.md`, com as quatro seções definidas no contrato.
- Menção de `/maestro:help` em `INSTALACAO-USUARIO.md` e em `skills/maestro-setup/SKILL.md`, sem a qual a verificação `comandos-documentados` passa a falhar.
- Atualização da contagem de comandos por extenso em `INSTALACAO-USUARIO.md`, que hoje declara o total anterior à criação deste comando.
- Réplica byte-a-byte dos três arquivos em `plugins/maestro/`.

## 4. Não faça
- Não liste comando que não exista em `commands/`. A verificação `comandos-documentados` recusa comando fantasma nos dois documentos, e um comando inventado no `help` é o erro mais provável deste bloco.
- Não invente exemplo com valor de negócio: nada de preço, link, nome de cliente, chave ou caminho de máquina de outra pessoa. Os exemplos usam apenas IDs de bloco genéricos e nomes de fase genéricos.
- Não duplique o conteúdo dos comandos. O `help` dá uma linha por comando e diz quando usar; a descrição longa mora no próprio arquivo do comando.
- Não crie um segundo comando, um alias ou um atalho. Este bloco cria exatamente um arquivo novo em `commands/`.
- Não altere nenhum outro arquivo de `commands/`. A descrição de cada comando é lida do frontmatter existente, não reescrita.
- Não introduza `python3` literal sem fallback nem `find ~/`, porque a verificação `portabilidade` está no comando de teste deste bloco.

## 5. Contrato

**Arquivo:** `commands/help.md`, com frontmatter contendo `description` de uma linha e `argument-hint: [comando]`.

**Comportamento com argumento:** se `$ARGUMENTS` contém o nome de um comando existente, exibe apenas a entrada daquele comando, com a descrição, quando usar e um exemplo. Se contém um nome que não existe em `commands/`, lista os nomes válidos. Se está vazio, exibe o documento inteiro.

**Quatro seções obrigatórias, nesta ordem:**

1. **Início rápido** — exatamente três passos numerados, cada um com o comando a rodar e uma linha do que ele produz. A sequência é: preparar o repositório, gerar o plano, executar o próximo bloco.
2. **Referência completa** — uma entrada por arquivo existente em `commands/`, cada uma com o nome no formato `/maestro:<nome>`, uma linha de descrição e uma linha de quando usar. As entradas são separadas em dois grupos: dia a dia e correção.
3. **Exemplos de uso** — de quatro a seis linhas de comando reais, cada uma com um comentário de uma linha dizendo o que acontece.
4. **Skills de suporte e scripts** — as skills de `skills/` com uma linha cada, e os scripts de `scripts/` com uma linha cada, dizendo quando o Maestro os invoca.

**Fonte de verdade da lista:** o conteúdo de `commands/`, `skills/` e `scripts/` no momento da escrita, lido diretamente. A contagem por extenso em `INSTALACAO-USUARIO.md` é derivada do número de arquivos em `commands/`.

## 6. Regras
**R1.** Toda entrada da seção 2 usa a `description` do frontmatter do comando correspondente como base da linha de descrição. Descrição inventada reprova na revisão.
**R2.** O grupo "dia a dia" da seção 2 tem no máximo quatro entradas. Todo o resto vai para "correção". A regra espelha o critério já usado no passo de fechamento da skill `maestro-setup`.
**R3.** A menção de `/maestro:help` em `INSTALACAO-USUARIO.md` e em `skills/maestro-setup/SKILL.md` usa exatamente essa grafia, porque a verificação `comandos-documentados` procura a subcadeia literal.
**R4.** O número por extenso em `INSTALACAO-USUARIO.md` é conferido contando os arquivos `.md` de `commands/` depois da criação de `help.md`, e não copiado desta spec.
**R5.** Os exemplos da seção 3 usam IDs de bloco no formato da convenção do projeto e nenhum dado real de nenhum projeto do dono.
**R6.** O arquivo é escrito em português, como os demais comandos, e não excede duzentas linhas.

## 7. Arquivos
`commands/help.md`, `INSTALACAO-USUARIO.md`, `skills/maestro-setup/SKILL.md` e as três cópias correspondentes em `plugins/maestro/`.

## 8. Dados
A lista de comandos vem de `commands/`, as descrições vêm do frontmatter de cada comando, a lista de skills vem de `skills/`, a lista de scripts vem de `scripts/` e a contagem por extenso é derivada por contagem de arquivos. Nenhum item da lista vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE conter o arquivo `commands/help.md` com frontmatter contendo `description` e `argument-hint`.
2. O SISTEMA DEVE conter em `commands/help.md` as quatro seções do contrato, na ordem, com os títulos "Início rápido", "Referência completa", "Exemplos de uso" e "Skills de suporte e scripts".
3. QUANDO a seção "Início rápido" é lida O SISTEMA DEVE apresentar exatamente três passos numerados, cada um com o comando a rodar.
4. O SISTEMA DEVE listar na seção "Referência completa" uma entrada por arquivo existente em `commands/`, sem omissão e sem entrada extra.
5. O SISTEMA DEVE limitar o grupo de dia a dia da seção "Referência completa" a no máximo quatro entradas.
6. SE `$ARGUMENTS` contém o nome de um comando existente ENTÃO O SISTEMA DEVE exibir apenas a entrada daquele comando.
7. SE `$ARGUMENTS` contém um nome que não existe em `commands/` ENTÃO O SISTEMA DEVE listar os nomes válidos.
8. O SISTEMA DEVE mencionar `/maestro:help` em `INSTALACAO-USUARIO.md` e em `skills/maestro-setup/SKILL.md`.
9. O SISTEMA DEVE declarar em `INSTALACAO-USUARIO.md` a quantidade de comandos por extenso, e essa quantidade DEVE ser igual ao número de arquivos `.md` em `commands/`.
10. QUANDO a verificação `comandos-documentados` roda após a alteração O SISTEMA DEVE reportar zero divergências.
11. QUANDO as verificações `paridade` e `portabilidade` rodam após a alteração O SISTEMA DEVE reportar zero falhas.
12. O SISTEMA DEVE listar na seção de skills e scripts uma linha por diretório de `skills/` e uma linha por arquivo de `scripts/`.

## 10. Casos de teste obrigatórios
- T1 — `commands/help.md` existe e tem frontmatter com `description` e `argument-hint`.
- T2 — os quatro títulos de seção do contrato aparecem no arquivo, na ordem.
- T3 — a seção "Início rápido" tem três passos numerados e nenhum a mais.
- T4 — o número de ocorrências de `/maestro:` na seção "Referência completa" é igual ao número de arquivos `.md` em `commands/`.
- T5 — todo nome mencionado no formato `/maestro:<nome>` corresponde a um arquivo existente em `commands/`.
- T6 — o grupo de dia a dia tem no máximo quatro entradas, contadas uma a uma.
- T7 — a seção "Exemplos de uso" tem entre quatro e seis linhas de comando.
- T8 — `INSTALACAO-USUARIO.md` contém `/maestro:help` e o número por extenso corresponde à contagem de arquivos em `commands/`.
- T9 — `skills/maestro-setup/SKILL.md` contém `/maestro:help`.
- T10 — `python scripts/verificar-repo.py --check comandos-documentados` sai com 0.
- T11 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T12 — `python scripts/verificar-repo.py --check portabilidade` sai com 0.
- T13 — busca textual em `commands/help.md`: nenhum caminho absoluto de máquina, nenhum link externo e nenhum valor numérico de negócio.

## 11. Pare e pergunte
- Se o número de arquivos em `commands/` não bater com o esperado ao contar → pare e reporte a contagem encontrada antes de escrever o número por extenso.
- Se algum comando não tiver `description` no frontmatter → pare e pergunte, em vez de escrever uma descrição sua para ele.
- Se a verificação `comandos-documentados` continuar falhando depois das duas menções → pare e mostre a saída completa, porque pode haver um terceiro documento no contrato dessa verificação.
