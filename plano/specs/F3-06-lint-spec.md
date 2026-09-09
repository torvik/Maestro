# F3-06 — F-LINT-SPEC: `scripts/lint-spec.py`

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Agente: implementador · Revisor: claude-sonnet-5
- Depende de: F3-05 · Orçamento: 30 turnos
- Comando de teste: `python scripts/lint-spec.py plano/specs/F3-06-lint-spec.md && python scripts/verificar-repo.py --check paridade`

## 2. Objetivo
Depois deste bloco existe um portão binário sobre a qualidade estrutural de uma spec: onze seções presentes, três ou mais critérios em notação EARS, e as seções "Não faça" e "Pare e pergunte" com conteúdo específico em vez de vazio ou frase de efeito. Hoje uma spec incompleta só é descoberta quando o executor já queimou meia sessão.

## 3. Escopo
- Criação de `scripts/lint-spec.py`, que valida um ou mais arquivos de spec contra seis regras numeradas.
- Definição da lista de itens genéricos recusados, que é o coração do bloco e está fixada na seção 5.
- Réplica byte-a-byte em `plugins/maestro/scripts/lint-spec.py`.

## 4. Não faça
- Não invente critério de qualidade além das seis regras da seção 5. Linter que opina reprova spec boa, e o dono para de rodá-lo.
- Não altere nenhuma spec. O script é somente leitura em todos os caminhos, inclusive nos de erro.
- Não use modelo de linguagem, chamada de rede nem dependência externa. A verificação é textual, determinística e roda sem internet.
- Não avalie conteúdo semântico. Um critério em EARS que diz algo errado passa neste linter; julgar conteúdo é trabalho do revisor humano e do agente revisor.
- Não considere ausência de acento como equivalente ao título canônico. Os títulos são comparados literalmente, incluindo acentuação, porque `novo-bloco.py` os emite assim.
- Não emita aviso, apenas erro ou sucesso. Aviso em linter vira ruído que ninguém lê, e este script é usado como portão.

## 5. Contrato

**Invocação:** `python scripts/lint-spec.py <arquivo.md> [<arquivo.md> ...]`

**Seis regras, citadas por número na mensagem de erro:**

- **L1** — as onze seções estão presentes, na ordem, com os títulos literais definidos no contrato do bloco F3-05.
- **L2** — o arquivo não contém a subcadeia `<<PREENCHER:`.
- **L3** — a seção 9 tem três ou mais itens, e cada item contém pelo menos um dos marcadores EARS: `QUANDO`, `SE `, `ENQUANTO`, `ONDE`, `DEVE`.
- **L4** — a seção 4 tem dois ou mais itens de lista, cada um com vinte caracteres ou mais, e nenhum item recusado pela lista de genéricos.
- **L5** — a seção 11 tem dois ou mais itens de lista, cada um com vinte caracteres ou mais, nenhum item recusado pela lista de genéricos, e cada item contendo `→` ou começando com `Se `.
- **L6** — nenhuma das onze seções está vazia, isto é, todas têm pelo menos uma linha não vazia depois do título e antes do título seguinte.

**Lista de genéricos, parte A — item recusado por igualdade.** Depois de remover o marcador de lista, converter para minúsculas e retirar pontuação das pontas, o item é recusado se for exatamente igual a: `n/a`, `na`, `nenhum`, `nenhuma`, `nada`, `tbd`, `todo`, `a definir`, `a preencher`, `-`.

**Lista de genéricos, parte B — item recusado por conter a frase.** Comparação em minúsculas, com e sem acento: `boas praticas`, `boas práticas`, `codigo limpo`, `código limpo`, `adicione testes`, `trate erros`, `seja cuidadoso`, `use bom senso`, `faca direito`, `faça direito`, `nao faca besteira`, `não faça besteira`, `siga o padrao`, `siga o padrão`.

**Formato de erro, uma linha por violação:**

```
<caminho>:<numero da secao ou 0>: L<n> <mensagem>
```

**Formato de sucesso, uma linha por arquivo:** `OK <caminho>`

**Códigos de saída:** `0` todos os arquivos passaram; `1` pelo menos um arquivo tem violação, com todas as violações de todos os arquivos listadas antes da saída; `2` arquivo não encontrado ou sem extensão `.md`.

## 6. Regras
**R1.** Item de lista é uma linha que começa, após espaços opcionais, com `- `, `* ` ou com um número seguido de ponto e espaço.
**R2.** Uma seção vai do seu título até o próximo título de nível dois ou até o fim do arquivo.
**R3.** A contagem de caracteres de L4 e L5 exclui o marcador de lista e os espaços das pontas.
**R4.** A comparação sem acento da parte B é feita normalizando o texto com `unicodedata`, não com uma tabela de substituição escrita à mão.
**R5.** Se L1 falhar por seção ausente, as demais regras ainda são avaliadas nas seções que existem. O relatório é completo numa passada, porque rodar o linter cinco vezes seguidas custa mais que ler cinco erros de uma vez.
**R6.** Com vários arquivos, cada um é avaliado por inteiro e o código de saída é 1 se qualquer um falhar.
**R7.** Só biblioteca padrão do Python 3.9 ou superior.

## 7. Arquivos
`scripts/lint-spec.py` e `plugins/maestro/scripts/lint-spec.py`. Nenhuma spec e nenhum outro arquivo é alterado por este bloco.

## 8. Dados
Todo valor vem do arquivo de spec passado como argumento e das listas literais da seção 5. Nenhuma regra e nenhuma frase da lista de genéricos vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `lint-spec.py` recebe uma spec com as onze seções, três ou mais critérios EARS e as seções 4 e 11 preenchidas O SISTEMA DEVE imprimir `OK <caminho>` e sair com código 0.
2. SE a spec não tem alguma das onze seções ENTÃO O SISTEMA DEVE imprimir uma violação `L1` por seção ausente e sair com código 1.
3. SE as onze seções estão presentes mas fora da ordem ENTÃO O SISTEMA DEVE imprimir violação `L1` e sair com código 1.
4. SE a spec contém a subcadeia `<<PREENCHER:` ENTÃO O SISTEMA DEVE imprimir violação `L2` e sair com código 1.
5. SE a seção 9 tem menos de três itens ENTÃO O SISTEMA DEVE imprimir violação `L3` e sair com código 1.
6. SE algum item da seção 9 não contém nenhum marcador EARS ENTÃO O SISTEMA DEVE imprimir violação `L3` identificando o item.
7. SE a seção 4 tem menos de dois itens, ou item com menos de vinte caracteres, ou item da lista de genéricos ENTÃO O SISTEMA DEVE imprimir violação `L4` e sair com código 1.
8. SE a seção 11 tem item sem `→` e que não começa com `Se ` ENTÃO O SISTEMA DEVE imprimir violação `L5` e sair com código 1.
9. SE alguma das onze seções não tem nenhuma linha de conteúdo ENTÃO O SISTEMA DEVE imprimir violação `L6` e sair com código 1.
10. QUANDO o arquivo passado não existe O SISTEMA DEVE sair com código 2.
11. QUANDO `lint-spec.py` roda sobre o esqueleto recém-gerado por `novo-bloco.py` O SISTEMA DEVE sair com código 1, reportando ao menos a violação `L2`.
12. QUANDO `lint-spec.py` roda sobre as nove specs de `plano/specs/F3-*.md` O SISTEMA DEVE sair com código 0.
13. O SISTEMA DEVE deixar todos os arquivos de entrada inalterados.
14. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `lint-spec.py plano/specs/F3-06-lint-spec.md` imprime `OK` e sai 0.
- T2 — `lint-spec.py plano/specs/F3-01-orphan-check.md plano/specs/F3-03-lock-script.md` sai 0.
- T3 — todas as nove specs `plano/specs/F3-*.md` numa única invocação: sai 0.
- T4 — cópia de uma spec com a seção 7 removida: sai 1 com violação `L1`.
- T5 — esqueleto gerado por `novo-bloco.py`: sai 1 e a saída contém `L2`.
- T6 — cópia com a seção 9 reduzida a dois itens: sai 1 com `L3`.
- T7 — cópia com um item da seção 9 sem marcador EARS: sai 1 com `L3`.
- T8 — cópia com a seção 4 contendo apenas `- nenhum`: sai 1 com `L4`.
- T9 — cópia com a seção 4 contendo `- Use boas práticas ao escrever o código`: sai 1 com `L4`.
- T10 — cópia com item da seção 11 sem `→` e começando com `Consulte`: sai 1 com `L5`.
- T11 — cópia com a seção 8 vazia: sai 1 com `L6`.
- T12 — `lint-spec.py arquivo-que-nao-existe.md` sai 2.
- T13 — `lint-spec.py README.txt` sai 2.
- T14 — hash de cada arquivo de entrada antes e depois de todos os testes é idêntico.
- T15 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se alguma das nove specs `F3-*.md` reprovar no linter → pare e reporte qual regra e qual spec, porque isso significa que a regra está errada ou a spec está errada e a decisão é do arquiteto.
- Se você achar que a lista de genéricos deveria crescer → pare e proponha a adição ao dono, porque cada frase nova recusa specs legítimas.
- Se a normalização sem acento se comportar de forma diferente no Windows → pare e reporte o comportamento observado antes de trocar a abordagem.
