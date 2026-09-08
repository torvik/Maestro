# F2-15 — F-PARALELO (implementação): despacho simultâneo no `maestro.md`

## 1. Identificação
- Complexidade: **C4**
- Modelo: claude-sonnet-5 · Agente: `implementador` · Revisor: claude-opus-5
- Depende de: F2-14
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco, `/maestro:proxima --paralelo` despacha um lote de até N blocos simultaneamente quando o predicado de elegibilidade provar que não há conflito. Com paralelismo desligado ou `--paralelo` ausente, o comportamento é idêntico ao da v1.2.

## 3. Escopo
- Criar `scripts/paralelo.py`: analisador e planejador de lotes. Não despacha agente. Não escreve em `plano/blocos.json`.
- Alterar `agents/maestro.md` para suportar despacho de lote quando `--paralelo` for passado.
- Alterar `commands/proxima.md` para aceitar `--paralelo`.
- Replicar cada alteração em `plugins/maestro/`.

## 4. Não faça
- Não use `git worktree`, branch por bloco nem qualquer isolamento que exija merge automático de trabalho de dois agentes. Merge automático de dois agentes é exatamente a classe de erro que este bloco existe para evitar.
- Não use locking por arquivo em disco como mecanismo primário. Sessão interrompida deixa lock órfão e trava o plano inteiro.
- Não permita execução simultânea quando a disjunção de globs não puder ser provada. Ausência de prova é conflito.
- Não torne o commit paralelo. No máximo um bloco commitando por vez.
- Não deixe nenhum bloco em `em_andamento` sem aviso ao dono ao final de qualquer caminho de falha.
- Não modifique o formato de `blocos.json`. Nenhum campo novo nos blocos.

## 5. Contrato

### Regra 0 — Fail-closed (inviolável)
Em toda ambiguidade, o resultado é serialização. Ausência de prova de disjunção é conflito. Esta regra prevalece sobre todas as outras.

### Predicado de elegibilidade

```
paralelizavel(A, B) :=
  C1 ^ C2 ^ C3 ^ C4 ^ C5 ^ C6
```

| Cond | Verificação |
|------|-------------|
| C1 | Nenhum bloco depende do outro, direta ou transitivamente |
| C2 | Ambos `pendente` com todas as dependências `concluido` |
| C3 | Nenhum tem `bloqueado_por` preenchido |
| C4 | Nenhum é `C5` (complexidade) |
| C5 | `arquivos_permitidos` dos dois blocos são provadamente disjuntos (algoritmo abaixo) |
| C6 | Nenhum bloco está atualmente `em_andamento` |

A ausência de prova de qualquer `Ci` resulta em serialização, nunca em execução.

### Algoritmo de disjunção de globs (C5)

`scripts/paralelo.py` implementa `disjoint(Ga, Gb)`:

```
disjoint(Ga, Gb):
  para cada Pa em Ga:
    para cada Pb em Gb:
      se globs_podem_sobrepor(Pa, Pb):
        retorna FALSE   ← conflito → serializar
  retorna TRUE

globs_podem_sobrepor(Pa, Pb):
  pa = Pa.split('/')
  pb = Pb.split('/')
  retorna segmentos_sobrepoem(pa, pb, memo={})

segmentos_sobrepoem(pa, pb, memo):
  chave = (tuple(pa), tuple(pb))
  se chave em memo: retorna memo[chave]

  se pa == [] e pb == []:
    resultado = True
  senão se pa == []:
    resultado = todos(s == '**' para s em pb)
  senão se pb == []:
    resultado = todos(s == '**' para s em pa)
  senão se pa[0] == '**':
    resultado = (segmentos_sobrepoem(pa[1:], pb, memo) ou   # ** = 0 segmentos
                 segmentos_sobrepoem(pa, pb[1:], memo))     # ** consome pb[0]
  senão se pb[0] == '**':
    resultado = (segmentos_sobrepoem(pa, pb[1:], memo) ou
                 segmentos_sobrepoem(pa[1:], pb, memo))
  senão:
    # ambos segmentos concretos (sem **)
    resultado = (segmento_pode_coincidir(pa[0], pb[0]) e
                 segmentos_sobrepoem(pa[1:], pb[1:], memo))

  memo[chave] = resultado
  retorna resultado

segmento_pode_coincidir(a, b):
  se a == '*' ou b == '*': retorna True          # * bate com qualquer segmento
  se '*' nao em a e '*' nao em b: retorna a == b # dois literais
  retorna True                                    # fail-closed: ambiguidade = True
```

**Casos de glob cobertos:**
1. `**` no fim: `src/a/**` vs `src/b/**` → disjoint (prefixos distintos)
2. `**` no meio: `src/a/**/x` vs `src/b/**/x` → disjoint
3. Globs idênticos: `src/**` vs `src/**` → overlap (retorna False imediatamente)
4. Prefixo comum: `src/a/**` vs `src/**` → NOT disjoint (src/a/ ⊂ src/)
5. Literal vs glob: `src/a/foo.ts` vs `src/**` → NOT disjoint

**Observação crítica:** `plano/blocos.json` e `plano/metricas.json` nunca aparecem em `arquivos_permitidos`, mas todo bloco os escreve. Ver R3 abaixo.

### R3 — blocos.json e metricas.json durante o lote

`plano/blocos.json` e `plano/metricas.json` são escritos pelo ciclo do maestro, não pelo agente executor. Durante um lote paralelo:

- O agente executor **não** escreve em `blocos.json` nem em `metricas.json`. Ele executa, roda testes, solicita revisão — e retorna resultado ao maestro.
- O maestro serializa **todos** os writes em `blocos.json` e `metricas.json` após receber os resultados do lote.
- Ordem de escrita: mesma ordem topológica dos blocos no plano.

### R4 — Commit serializado

Após todos os blocos do lote terminarem execução e revisão:

1. Maestro ordena o lote por ID crescente.
2. Para cada bloco (em ordem): verifica `comando_teste` → se passa, commita; se falha, marca `pendente` e continua com próximo.
3. Um bloco não commita enquanto o anterior não terminou de commitar.
4. Se o commit de um bloco falhar: o bloco fica `pendente` (não `em_andamento`), `tentativas++`, nota registrada. Os demais blocos aprovados continuam o ciclo.

### R5 — Teto de paralelismo

- Padrão: **2** (dois blocos simultâneos por lote).
- Campo de configuração: `max_paralelo` em `maestro.config.json`.
- Justificativa do padrão: acima de 2, a superfície de corrida cresce mais rápido que o ganho real, pois commits e writes a blocos.json são serializados de qualquer forma.
- `max_paralelo: 1` ou ausência de `--paralelo` em proxima.md = comportamento idêntico à v1.2.

### R6 — Falha parcial

| Situação | Destino dos demais |
|----------|-------------------|
| Bloco A reprovado pelo revisor | A → `pendente`, `tentativas++`. B commita normalmente se aprovado. |
| Bloco A trava / crash | Maestro detecta ausência de resposta. A → `pendente`. B segue. |
| Commit de A falha | A → `pendente`. B commita na sequência. |
| Ambos reprovados | Ambos → `pendente`. Nenhum em `em_andamento`. |

**Invariante:** ao final do lote, nenhum bloco está em `em_andamento` sem aviso ao dono.

### R7 — Interrupção de sessão

Quando a sessão morre durante um lote paralelo:
- Múltiplos blocos ficam com `estado: "em_andamento"`.
- `/maestro:retomar` detecta N blocos `em_andamento` → modo lote.
- Para cada bloco `em_andamento`: roda `comando_teste`, exibe resultado, oferece:
  - (a) Rodar revisor e commitar se aprovado
  - (b) Resetar para `pendente` com `tentativas++`
  - (c) Descartar (pendente sem incrementar tentativas)
- Sem arquivo de estado adicional. O `estado: "em_andamento"` em `blocos.json` é o único sinal necessário.

### Desligando o paralelismo

`max_paralelo: 1` em `maestro.config.json` → `scripts/paralelo.py` retorna lote de tamanho 1 → comportamento idêntico à v1.2. Nenhuma outra alteração necessária.

## 6. Regras

**R0 (inviolável).** Fail-closed: em toda ambiguidade, serializar.
**R1.** O predicado tem exatamente 6 condições (C1–C6). Nenhuma pode ser removida; a implementação pode adicionar.
**R2.** `scripts/paralelo.py` implementa `disjoint()` com memoização. Falha em provar disjunção → conflito.
**R3.** Somente o maestro escreve em `blocos.json` e `metricas.json`, de forma serializada, após o lote.
**R4.** Commits são serializados, um por vez, em ordem de ID crescente.
**R5.** Padrão de lote: 2. Campo `max_paralelo` em config. Acima de 2: explica mas executa se configurado.
**R6.** Falha parcial nunca deixa `em_andamento` órfão.
**R7.** `/maestro:retomar` reconstrói lote interrompido sem arquivo de estado adicional.
**R8.** Bloco C5 nunca vai para um lote paralelo, mesmo que C1–C4 e C6 passem.
**R9.** `--paralelo` ausente em proxima.md → comportamento idêntico à v1.2.
**R10.** `scripts/paralelo.py` não despacha agente e não escreve em `blocos.json`.

## 7. Arquivos
- `scripts/paralelo.py` (criar)
- `plugins/maestro/scripts/paralelo.py` (criar — cópia byte-a-byte)
- `agents/maestro.md` (alterar — seção de despacho de lote)
- `plugins/maestro/agents/maestro.md` (alterar — cópia byte-a-byte)
- `commands/proxima.md` (alterar — flag `--paralelo`)
- `plugins/maestro/commands/proxima.md` (alterar — cópia byte-a-byte)

Nada mais.

## 8. Dados
- Blocos elegíveis vêm de `plano/blocos.json`.
- `arquivos_permitidos` vêm dos campos dos blocos.
- `max_paralelo` vem de `maestro.config.json` (padrão: 2 se ausente).
- Nenhum valor vem do modelo. `scripts/paralelo.py` é determinístico.

## 9. Critérios de aceite (EARS)

1. QUANDO `/maestro:proxima --paralelo` é invocado O SISTEMA DEVE rodar `scripts/paralelo.py` para selecionar até `max_paralelo` blocos cujo predicado C1–C6 seja verdadeiro e despachar todos simultaneamente.
2. SE a disjunção entre `arquivos_permitidos` de dois blocos não puder ser provada ENTÃO O SISTEMA DEVE serializar os blocos, nunca executá-los simultaneamente.
3. SE um bloco tiver complexidade C5 ENTÃO O SISTEMA DEVE excluí-lo de qualquer lote paralelo.
4. QUANDO a sessão for interrompida no meio de um lote O SISTEMA DEVE permitir que `/maestro:retomar` reconstrua o estado encontrando os blocos `em_andamento` e tratando-os individualmente.
5. SE qualquer bloco do lote for reprovado ou falhar ENTÃO O SISTEMA DEVE marcar esse bloco como `pendente` e completar o ciclo dos demais sem deixar nenhum `em_andamento` sem aviso.
6. O SISTEMA DEVE serializar todos os commits do lote, no máximo um por vez, em ordem de ID crescente.
7. O SISTEMA DEVE serializar todos os writes em `plano/blocos.json` e `plano/metricas.json`, realizados exclusivamente pelo maestro após o lote.
8. QUANDO `--paralelo` estiver ausente O SISTEMA DEVE executar exatamente um bloco, com comportamento idêntico ao da v1.2.
9. QUANDO `max_paralelo: 1` estiver configurado O SISTEMA DEVE executar exatamente um bloco por lote.
10. QUANDO a verificação `paridade` roda O SISTEMA DEVE reportar zero divergências entre as cópias root e plugins/maestro.

## 10. Casos de teste obrigatórios

- T1 — dois blocos com `arquivos_permitidos` disjuntos (`src/a/**` vs `src/b/**`): `paralelo.py` retorna lote de 2.
- T2 — dois blocos com globs sobrepostos (`src/a/**` vs `src/**`): `paralelo.py` retorna lote de 1 (serializa).
- T3 — um bloco C5 no candidato: `paralelo.py` o exclui do lote, retorna o outro sozinho.
- T4 — bloco com `bloqueado_por` preenchido: excluído do lote.
- T5 — bloco A depende de bloco B (transitivo): ambos excluídos do mesmo lote.
- T6 — `/maestro:proxima` sem `--paralelo`: exatamente um bloco despachado.
- T7 — `max_paralelo: 1` em config: exatamente um bloco despachado mesmo com `--paralelo`.
- T8 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T9 — `python scripts/validar-plano.py` sai com 0.

## 11. Pare e pergunte

- Se o algoritmo `disjoint()` não puder ser provado terminante para padrões reais de `arquivos_permitidos` usados no repositório → pare e reporte antes de implementar.
- Se a serialização de writes em `blocos.json` exigir mecanismo de IPC entre agentes (lock, pipe, socket) → pare e pergunte; o maestro não tem canal direto com subagentes em execução.
- Se `/maestro:retomar` não conseguir distinguir "lote paralelo interrompido" de "bloco único interrompido" sem novo campo em `blocos.json` → pause, proponha o campo e confirme antes de alterar o schema.
- Se `max_paralelo` maior que 2 for necessário para ganho real em algum plano de teste → pause e pergunte; o padrão é 2 por razão arquitetural (commit serializado).

## Red-team — 8 cenários de corrida e resposta do sistema

| # | Cenário | Resposta do sistema |
|---|---------|---------------------|
| 1 | Globs sobrepostos que análise estática não pega (ex.: `src/**` vs `src/components/**`) | `disjoint()` detecta na etapa de planejamento: C5 falha → serializa. Nunca chega a despachar. |
| 2 | Agente de bloco A escreve arquivo fora de `arquivos_permitidos` | Revisor de A deteta e reprova. B não é afetado. A → pendente, tentativas++. |
| 3 | Dois blocos escrevem `plano/blocos.json` simultaneamente | Impossível por R3: somente o maestro escreve blocos.json, após o lote, de forma serializada. |
| 4 | Revisor de A reprova enquanto B já commitou | B está commitado. A → pendente, tentativas++. Dono é avisado. Nenhum rollback automático de B. |
| 5 | Sessão interrompida no meio do lote | Múltiplos blocos ficam em_andamento. `/maestro:retomar` detecta modo lote, trata cada um individualmente. |
| 6 | Bloco ganha `bloqueado_por` depois de o lote iniciar | `paralelo.py` verifica C3 antes do despacho. Se `bloqueado_por` for definido durante execução (raro): maestro detecta na fase de commit e não commita o bloco; marca pendente. |
| 7 | Dependência descoberta em tempo de execução | Dependências declaradas foram verificadas em C1/C2. Dependências não declaradas manifestam-se como conflito de arquivo (capturado pelo revisor) ou como ausência de artefato (teste falha). Revisor reprova. |
| 8 | Lote com um bloco muito mais lento que o outro | Bloco rápido aguarda na fase de commit. Correto por R4 (commits serializados). Sem consequência de corretude, apenas latência. |