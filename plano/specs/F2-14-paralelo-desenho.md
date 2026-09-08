# F2-14 — F-PARALELO (desenho): despacho simultâneo e detecção de conflito

## 1. Identificação
- Complexidade: **C5**
- Modelo: claude-opus-5 · Agente: `arquiteto` · Revisor: claude-opus-5
- Depende de: F2-07, F2-13
- Orçamento de turnos: 40

## 2. Objetivo
Depois deste bloco existe a spec `F2-15-paralelo-impl.md`, fechando quando dois blocos podem rodar ao mesmo tempo e o que acontece em cada corrida possível. Nenhum código é escrito aqui.

**Por que C5:** dois agentes escrevendo o mesmo arquivo destroem trabalho já aprovado, e o dono só descobre depois do commit. O dano é irreversível na prática — a sessão do agente que perdeu a escrita não existe mais. Erro de desenho aqui não aparece em teste; aparece em produção, uma vez, tarde.

## 3. Escopo
- Escrever `plano/specs/F2-15-paralelo-impl.md` completa, nas 11 seções do gabarito.
- Incluir a seção de red-team com no mínimo 8 cenários de corrida e a resposta do sistema a cada um.

## 4. Não faça
- Não escreva código. O produto é uma spec.
- Não proponha git worktree, branch por bloco nem qualquer isolamento que exija merge posterior sem que o dono tenha decidido. Merge automático de trabalho de dois agentes é exatamente a classe de erro que este bloco existe para evitar.
- Não proponha locking por arquivo em disco como mecanismo primário. Sessão interrompida deixa lock órfão e trava o plano inteiro.
- Não permita paralelismo "quando parecer seguro". O predicado é uma conjunção de condições verificáveis; ausência de prova é conflito.
- Não deixe nenhum caminho de falha em que um bloco fique `em_andamento` sem que o dono seja avisado.
- Não trate a fase de commit como paralelizável.

## 5. Contrato
Produto: `plano/specs/F2-15-paralelo-impl.md`, 11 seções, critérios EARS, seções "Não faça" e "Pare e pergunte" com casos concretos, mais a seção de red-team.

O predicado de elegibilidade tem a forma de conjunção numerada:
```
paralelizavel(A, B) :=
  C1 ^ C2 ^ C3 ^ ... ^ Cn
```
Cada `Ci` é verificável isoladamente por `scripts/paralelo.py`. Falha em provar qualquer `Ci` resulta em serialização, não em execução.

## 6. Regras — decisões que a spec produzida tem de fechar

**R1 — condições mínimas do predicado.** No mínimo: (a) nenhum depende do outro, direta ou transitivamente; (b) ambos `pendente` com todas as dependências `concluido`; (c) nenhum tem `bloqueado_por` preenchido; (d) nenhum é C5; (e) os conjuntos de `arquivos_permitidos` são **provadamente** disjuntos. A spec pode acrescentar condições; não pode remover nenhuma destas.

**R2 — disjunção de globs.** Especifique o algoritmo. Trate explicitamente: `**` no meio e no fim; globs idênticos; prefixo comum (`src/a/**` versus `src/**`); caminho literal contra glob; caminho de arquivo único repetido. **Se a disjunção não puder ser provada, o resultado é conflito.** Nunca o contrário.

**R3 — arquivos fora dos globs.** Todo bloco toca `plano/blocos.json` e, após F2-07, `plano/metricas.json`, mesmo sem declará-los. A spec tem de definir quem escreve nesses arquivos durante um lote paralelo. Ignorar isso é o furo mais provável do desenho.

**R4 — commit serializado.** No máximo um bloco commitando por vez. Defina a ordem e o que acontece se o commit de um bloco falhar enquanto outros esperam.

**R5 — teto de paralelismo.** Valor padrão numérico e o campo de `maestro.config.json` que o altera. Justifique o padrão em uma linha.

**R6 — falha parcial.** Se um bloco do lote for reprovado ou falhar, defina o destino dos demais. Nenhum caminho pode terminar com bloco em `em_andamento` sem aviso ao dono.

**R7 — interrupção de sessão.** Defina o que `/maestro:retomar` encontra e como reconstrói o estado quando a sessão morre no meio de um lote. Hoje `retomar` assume um bloco por vez.

**R8 — red-team, mínimo 8 cenários**, cada um com a resposta do sistema. Cubra ao menos: dois blocos com globs sobrepostos que a análise estática não pegou; agente escrevendo fora dos `arquivos_permitidos`; dois blocos escrevendo `plano/blocos.json` ao mesmo tempo; revisor de A reprovando enquanto B commita; sessão interrompida no meio do lote; bloco que ganha `bloqueado_por` depois de o lote iniciar; dependência descoberta em tempo de execução; lote com um bloco muito mais lento que o outro.

**R9 — fail-closed é a regra do bloco.** Em toda ambiguidade, a resposta é serializar. Registre isso na seção 6 da spec produzida como regra numerada, não como comentário.

**R10 — reversibilidade.** A spec define como o dono desliga o paralelismo por completo, e o comportamento com paralelismo desligado é idêntico ao de hoje.

## 7. Arquivos
`plano/specs/F2-15-paralelo-impl.md` (criar; substitui o placeholder). Nada mais.

## 8. Dados
O comportamento atual do ciclo de despacho vem de `agents/maestro.md`. O formato de `arquivos_permitidos` vem de `plano/blocos.json`. O teto de paralelismo padrão é decisão a ser proposta e confirmada com o dono. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE produzir `plano/specs/F2-15-paralelo-impl.md` com as 11 seções do gabarito preenchidas.
2. O SISTEMA DEVE definir o predicado de elegibilidade como conjunção de condições numeradas e verificáveis uma a uma.
3. O SISTEMA DEVE especificar o algoritmo de disjunção de `arquivos_permitidos`, incluindo o tratamento de `**` e de globs parcialmente sobrepostos.
4. SE a disjunção entre dois conjuntos de globs não puder ser provada ENTÃO a spec DEVE determinar serialização, nunca execução simultânea.
5. A spec DEVE proibir execução simultânea de qualquer bloco C5.
6. A spec DEVE definir a fase de commit como serializada, com no máximo um bloco commitando por vez.
7. A spec DEVE definir um teto de paralelismo com valor padrão numérico e o campo de configuração que o altera.
8. SE qualquer bloco do lote falhar ENTÃO a spec DEVE definir o destino dos restantes sem deixar nenhum em `em_andamento` órfão.
9. A spec DEVE conter uma seção de red-team com no mínimo 8 cenários de corrida ou conflito e a resposta do sistema a cada um.
10. A spec DEVE definir o comportamento em caso de interrupção da sessão no meio de um lote, de forma que `/maestro:retomar` reconstrua o estado.

## 10. Casos de teste obrigatórios
- T1 — o arquivo produzido contém os 11 cabeçalhos numerados.
- T2 — a seção 6 contém o predicado como lista numerada com as 5 condições mínimas de R1.
- T3 — o algoritmo de disjunção cobre nominalmente os 5 casos de glob de R2.
- T4 — existe critério EARS afirmando serialização quando a disjunção não é provável.
- T5 — existe critério EARS proibindo C5 em paralelo.
- T6 — existe critério EARS de commit serializado.
- T7 — o teto de paralelismo aparece com valor numérico e nome de campo de configuração.
- T8 — existe critério EARS cobrindo falha parcial sem `em_andamento` órfão.
- T9 — a seção de red-team tem no mínimo 8 cenários numerados, cada um com resposta.
- T10 — existe critério EARS cobrindo interrupção de sessão e `/maestro:retomar`.
- T11 — a spec responde nominalmente a R3 (quem escreve `plano/blocos.json` durante o lote).
- T12 — `python scripts/validar-plano.py` sai com 0.

## 11. Pare e pergunte
- Se você concluir que a disjunção de globs não é decidível de forma confiável para os padrões usados nos planos reais → **pare e proponha ao dono descartar F-PARALELO**. Um recurso que corrompe trabalho uma vez a cada vinte execuções tem valor esperado negativo. Recomendar o descarte é uma saída legítima deste bloco.
- Se o teto de paralelismo padrão precisar ser maior que 2 para haver ganho perceptível → pare e pergunte; acima de 2 a superfície de corrida cresce mais rápido que o ganho.
- Se a implementação exigir mudança no contrato de `arquivos_permitidos` (por exemplo, exigir globs sem `**`) → pare e pergunte; isso invalida planos existentes.
- Se `/maestro:retomar` não puder reconstruir o estado de um lote interrompido sem um arquivo de estado novo → pare e pergunte antes de introduzir esse arquivo.
