# maestro — plano de execucao
Gerado em 2026-09-08 a partir de plano/blocos.json

## Resumo
| Estado | Blocos |
|---|---|
| concluido | 8 |
| em_andamento | 0 |
| pendente | 9 |
| bloqueado | 0 |
| **total** | 17 |

## Blocos

### F2-01 — Harness de verificacao do repositorio (verificar-repo.py)

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** nenhum
- **Comando de teste:** `python scripts/verificar-repo.py`

**Critérios de aceite:**
1. QUANDO o script roda sem argumentos O SISTEMA DEVE executar as 5 verificacoes (paridade, portabilidade, comandos-documentados, versao, plano) e sair com codigo 0 se todas passarem.
2. SE qualquer verificacao falhar ENTAO O SISTEMA DEVE imprimir uma linha por falha no formato 'FALHA <check> <caminho>: <motivo>' e sair com codigo 1.
3. QUANDO invocado com --check <nome> O SISTEMA DEVE executar apenas a verificacao de nome informado.
4. SE --check receber um nome inexistente ENTAO O SISTEMA DEVE listar os nomes validos e sair com codigo 2.
5. O SISTEMA DEVE usar apenas a biblioteca padrao do Python 3.9+ e nao invocar nenhum binario externo.
6. QUANDO um arquivo existe em commands/, agents/, skills/ ou scripts/ sem gemeo byte-a-byte em plugins/maestro/ O SISTEMA DEVE reportar falha na verificacao 'paridade'.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe um script que prova, com código de saída, que o repositório do Maestro está internamente coerente. Ele é o `comando_teste` de quase todos os blocos da fase 2 — sem ele os outros blocos não têm verificação binária.

## 3. Escopo
- Criar `scripts/verificar-repo.py`.
- Copiar o arquivo idêntico para `plugins/maestro/scripts/verificar-repo.py`.
- Implementar exatamente 5 verificações: `paridade`, `portabilidade`, `comandos-documentados`, `versao`, `plano`.

---

### F2-02 — B-WIN: localizacao de scripts cross-platform (elimina find ~/)

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-opus-5
- **Estado:** concluido
- **Depende de:** F2-01
- **Comando de teste:** `python scripts/verificar-repo.py --check portabilidade && python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. QUANDO a verificacao 'portabilidade' roda O SISTEMA DEVE reportar zero ocorrencias da string 'find ~/' em commands/, agents/ e skills/, nas duas copias.
2. QUANDO a verificacao 'portabilidade' roda O SISTEMA DEVE reportar zero ocorrencias de 'python3 ' como comando literal em commands/, agents/ e skills/, nas duas copias.
3. O SISTEMA DEVE conter o arquivo skills/maestro-runtime/SKILL.md com a sequencia canonica de localizacao de script e de deteccao de interpretador.
4. QUANDO um comando precisa localizar um script do Maestro O SISTEMA DEVE referenciar a skill maestro-runtime em vez de repetir a sequencia de busca no proprio arquivo.
5. SE nenhum interpretador Python for encontrado ENTAO O SISTEMA DEVE instruir o agente a ler plano/blocos.json diretamente e nunca a inventar os numeros do quadro.
6. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, nenhum comando ou skill do Maestro depende de `find` ou de `python3`, e a sequência de localização de script existe em um único lugar. Hoje o Maestro quebra no PowerShell e em qualquer máquina onde o executável se chame `python`.

## 3. Escopo
- Criar `skills/maestro-runtime/SKILL.md` com a sequência canônica de detecção de interpretador e localização de script.
- Substituir, nos 6 arquivos que hoje trazem `find ~/...`, a instrução inline por uma referência à skill `maestro-runtime`.
- Substituir toda ocorrência de `python3 <script>` por `python <script>` com fallback documentado.
- Replicar cada alteração em `plugins/maestro/`.

---

### F2-03 — B-VERSAO: coerencia de versao entre plugin.json, VERSAO.md e CHANGELOG.md

- **Complexidade / modelo / revisor:** C2 / claude-haiku-4-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** F2-01
- **Comando de teste:** `python scripts/verificar-repo.py --check versao`

**Critérios de aceite:**
1. O SISTEMA DEVE registrar em .claude-plugin/plugin.json a mesma versao declarada no titulo da entrada mais recente de CHANGELOG.md.
2. QUANDO a verificacao 'versao' roda O SISTEMA DEVE reportar zero divergencias entre plugin.json, VERSAO.md e o topo do CHANGELOG.md.
3. SE existir mais de um plugin.json no repositorio ENTAO O SISTEMA DEVE exigir que todos declarem a mesma versao.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, a versão declarada no `plugin.json` é a mesma do `CHANGELOG.md` e do `VERSAO.md`. Hoje `plugin.json` diz `1.1.0` enquanto o CHANGELOG já registra `1.2.0` — quem instala pelo marketplace vê a versão errada e o `migrar-plano` compara contra um número falso.

## 3. Escopo
- Corrigir o campo `version` em `.claude-plugin/plugin.json` e na cópia sob `plugins/maestro/`.
- Conferir e, se preciso, corrigir a versão citada em `VERSAO.md` e na cópia.

---

### F2-04 — B-SETUP-DEFAULTS: setup gera todos os campos obrigatorios do bloco

- **Complexidade / modelo / revisor:** C2 / claude-haiku-4-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** F2-01
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. QUANDO a skill maestro-setup gera um bloco novo O SISTEMA DEVE incluir os 14 campos obrigatorios listados em OBRIG no validar-plano.py.
2. QUANDO a skill maestro-setup gera um bloco novo O SISTEMA DEVE preencher tentativas com 0, notas com lista vazia e bloqueado_por com null.
3. SE o usuario nao informar o comando de teste de um bloco ENTAO O SISTEMA DEVE parar e perguntar, em vez de gravar comando_teste vazio.
4. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, todo bloco criado pelo `/maestro:setup` passa no `validar-plano.py` na primeira tentativa. Hoje o setup omite `tentativas` e `notas`, e o plano recém-criado já nasce reprovado pelo validador.

## 3. Escopo
- Alterar `skills/maestro-setup/SKILL.md` (Passo 3, geração do `plano/blocos.json`) para incluir um bloco-modelo com os 14 campos obrigatórios preenchidos.
- Replicar em `plugins/maestro/skills/maestro-setup/SKILL.md`.

---

### F2-05 — D-SCHEMA: documentar estado bloqueado versus campo bloqueado_por

- **Complexidade / modelo / revisor:** C2 / claude-haiku-4-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** nenhum
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. O SISTEMA DEVE documentar em schema-blocos.md uma secao que distingue estado igual a bloqueado de bloqueado_por preenchido, com uma frase de quando usar cada um.
2. O SISTEMA DEVE declarar que bloqueado_por preenchido impede o despacho mesmo com estado igual a pendente.
3. O SISTEMA DEVE declarar que estado igual a bloqueado sem bloqueado_por e um estado invalido e deve ser corrigido antes do despacho.
4. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, `schema-blocos.md` explica a diferença entre o estado `bloqueado` e o campo `bloqueado_por`. Hoje os dois existem, o `status.py` trata cada um de um jeito, e nada documenta quando usar qual — o que faz o `/maestro:destravar` (F2-06) não ter semântica definida.

## 3. Escopo
- Acrescentar uma seção a `skills/planejar-projeto/references/schema-blocos.md`.
- Replicar em `plugins/maestro/skills/planejar-projeto/references/schema-blocos.md`.

---

### F2-06 — F-DESTRAVAR: comando /maestro:destravar <ID>

- **Complexidade / modelo / revisor:** C2 / claude-sonnet-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** F2-02, F2-05
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check comandos-documentados`

**Critérios de aceite:**
1. QUANDO o comando recebe um ID cujo bloco tem bloqueado_por preenchido O SISTEMA DEVE exibir o motivo do bloqueio e pedir confirmacao explicita antes de alterar o arquivo.
2. QUANDO o usuario confirma O SISTEMA DEVE gravar bloqueado_por igual a null, estado igual a pendente e acrescentar uma nota com a data e o motivo removido.
3. SE o bloco informado nao tiver bloqueado_por nem estado bloqueado ENTAO O SISTEMA DEVE recusar a operacao e nao gravar nada.
4. SE o ID informado nao existir em plano/blocos.json ENTAO O SISTEMA DEVE listar os IDs bloqueados e nao gravar nada.
5. SE o usuario nao confirmar ENTAO O SISTEMA DEVE encerrar sem escrever em plano/blocos.json.
6. O SISTEMA DEVE deixar tentativas inalterado.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, o dono limpa um bloqueio sem abrir `plano/blocos.json` no editor. Hoje a única saída é editar JSON à mão, e edição manual do arquivo de estado é a forma mais comum de corromper o plano.

## 3. Escopo
- Criar `commands/destravar.md` e a cópia em `plugins/maestro/commands/destravar.md`.

---

### F2-07 — F-METRICAS: contrato de plano/metricas.json e gravacao pelo maestro

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-opus-5
- **Estado:** concluido
- **Depende de:** F2-02
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade && python scripts/status.py`

**Critérios de aceite:**
1. QUANDO um bloco muda para concluido O SISTEMA DEVE acrescentar um registro em plano/metricas.json com os 11 campos do contrato da secao 5 da spec.
2. QUANDO um bloco e reprovado pelo revisor O SISTEMA DEVE acrescentar um registro com veredito igual a reprovado, em vez de sobrescrever o registro anterior.
3. SE plano/metricas.json nao existir no momento da gravacao ENTAO O SISTEMA DEVE cria-lo com schema igual a 1 e registros igual a lista vazia antes de acrescentar.
4. SE plano/metricas.json existir com JSON invalido ENTAO O SISTEMA DEVE parar, reportar ao usuario e nao sobrescrever o arquivo.
5. O SISTEMA DEVE gravar timestamp_inicio e timestamp_fim em ISO 8601 com sufixo Z.
6. SE nenhum commit foi feito para o bloco ENTAO O SISTEMA DEVE gravar commit_sha igual a null em vez de omitir o campo.
7. ONDE plano/metricas.json existir O SISTEMA DEVE fazer o status.py imprimir um resumo com total de blocos medidos, turnos usados sobre orcados e contagem de reprovacoes.
8. ONDE plano/metricas.json nao existir O SISTEMA DEVE omitir a secao de metricas sem emitir erro.
9. O SISTEMA DEVE tratar plano/metricas.json como append-only e nunca remover registros existentes.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe um registro histórico de execução por bloco: qual modelo rodou de fato, quantos turnos custou contra o orçado, e qual commit saiu. É a base do `/maestro:status --bloco` (F2-08), do `/maestro:rollback` (F2-10) e do `/maestro:exportar` (F2-11) — sem ele, nenhum dos três tem de onde ler.

## 3. Escopo
- Criar `skills/planejar-projeto/references/schema-metricas.md` com o contrato do arquivo.
- Alterar `agents/maestro.md` para gravar um registro ao fechar cada bloco.
- Alterar `scripts/status.py` para imprimir um resumo quando o arquivo existir.
- Alterar `commands/status.md` para mencionar o resumo.
- Replicar as quatro alterações em `plugins/maestro/`.

---

### F2-08 — F-STATUS-BLOCO: /maestro:status --bloco <ID>

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-sonnet-5
- **Estado:** pendente
- **Depende de:** F2-07
- **Comando de teste:** `python scripts/status.py --bloco F2-01 && python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. QUANDO status.py recebe --bloco <ID> O SISTEMA DEVE imprimir id, titulo, complexidade, estado, modelo, revisor_modelo, caminho da spec, comando_teste, tentativas, orcamento_turnos, dependencias com o estado de cada uma, arquivos_permitidos, criterios de aceite numerados e notas.
2. QUANDO status.py recebe --bloco <ID> O SISTEMA DEVE imprimir o quadro do bloco e nao o quadro geral do plano.
3. SE o ID informado nao existir ENTAO O SISTEMA DEVE imprimir 'bloco nao encontrado' seguido dos IDs validos e sair com codigo 1.
4. ONDE existir registro do bloco em plano/metricas.json O SISTEMA DEVE imprimir turnos usados sobre orcados, tentativas medidas e veredito de cada registro.
5. SE o bloco tiver bloqueado_por preenchido ENTAO O SISTEMA DEVE imprimir o motivo em destaque e sugerir /maestro:destravar.
6. O SISTEMA DEVE manter o comportamento atual de status.py sem argumentos inalterado.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco o dono vê tudo sobre um bloco em uma tela, sem abrir o JSON nem a spec. Hoje `status.py` só imprime o quadro geral, que trunca o título em 44 caracteres e não mostra critério, arquivos permitidos nem histórico.

## 3. Escopo
- Acrescentar o modo `--bloco <ID>` a `scripts/status.py`.
- Atualizar `commands/status.md` para repassar o argumento.
- Replicar as duas alterações em `plugins/maestro/`.

---

### F2-09 — F-EDITAR: comando /maestro:editar <ID>

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-sonnet-5
- **Estado:** concluido
- **Depende de:** F2-02
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check comandos-documentados`

**Critérios de aceite:**
1. QUANDO o comando recebe um ID O SISTEMA DEVE exibir o caminho da spec e as duas vias disponiveis: ajuste pontual e regeracao pelo arquiteto.
2. QUANDO o usuario escolhe ajuste pontual O SISTEMA DEVE aplicar apenas as alteracoes que o usuario descreveu e nao reescrever secoes nao mencionadas.
3. QUANDO o usuario escolhe regeracao O SISTEMA DEVE despachar o agente arquiteto e gravar a nova spec no mesmo caminho, preservando o arquivo anterior como <spec>.bak.
4. SE o bloco estiver com estado concluido ENTAO O SISTEMA DEVE avisar que a spec ja foi executada e pedir confirmacao antes de editar.
5. SE o bloco estiver com estado em_andamento ENTAO O SISTEMA DEVE recusar a edicao e mandar rodar /maestro:retomar primeiro.
6. QUANDO a spec e alterada O SISTEMA DEVE rodar validar-plano.py ao final e reportar o resultado.
7. O SISTEMA DEVE deixar estado e tentativas do bloco inalterados.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe um caminho suportado para ajustar a spec de um bloco. Hoje só existe `/maestro:replanejar`, que refaz o plano inteiro — desproporcional quando o que falta é uma linha em "Não faça".

## 3. Escopo
- Criar `commands/editar.md` e a cópia em `plugins/maestro/commands/editar.md`.
- Duas vias: ajuste pontual (o agente aplica o que o dono descreveu) e regeração (o arquiteto reescreve a spec inteira).

---

### F2-10 — F-ROLLBACK: comando /maestro:rollback <ID>

- **Complexidade / modelo / revisor:** C4 / claude-sonnet-5 / claude-opus-5
- **Estado:** pendente
- **Depende de:** F2-07
- **Comando de teste:** `python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check comandos-documentados`

**Critérios de aceite:**
1. QUANDO o comando recebe um ID O SISTEMA DEVE localizar o commit_sha do bloco em plano/metricas.json e exibir o resumo de git show --stat antes de qualquer alteracao.
2. O SISTEMA DEVE usar git revert e nunca git reset, git checkout -- nem git clean.
3. SE o bloco nao tiver commit_sha em plano/metricas.json ENTAO O SISTEMA DEVE recusar a operacao e instruir o usuario a reverter manualmente.
4. SE a arvore de trabalho tiver alteracoes nao commitadas ENTAO O SISTEMA DEVE recusar a operacao e nao tocar no git.
5. SE existirem commits posteriores que alteram os mesmos arquivos do commit alvo ENTAO O SISTEMA DEVE listar esses commits e pedir confirmacao explicita antes de reverter.
6. SE git revert terminar em conflito ENTAO O SISTEMA DEVE rodar git revert --abort, deixar o repositorio no estado anterior e nao alterar plano/blocos.json.
7. QUANDO o revert conclui sem conflito O SISTEMA DEVE gravar estado igual a pendente, deixar tentativas inalterado e acrescentar uma nota com o SHA revertido e a data.
8. O SISTEMA DEVE pedir confirmacao explicita do usuario antes de executar o git revert em todos os casos.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco o dono desfaz um bloco aprovado por engano, com um comando, sem tocar no git à mão. O desenho está fechado nesta spec; a incerteza de design que classificava o bloco como C4 — o que fazer quando existem commits posteriores — está resolvida na regra R4.

## 3. Escopo
- Criar `commands/rollback.md` e a cópia em `plugins/maestro/commands/rollback.md`.

---

### F2-11 — F-EXPORTAR: comando /maestro:exportar gera plano/RELATORIO.md

- **Complexidade / modelo / revisor:** C3 / claude-sonnet-5 / claude-sonnet-5
- **Estado:** pendente
- **Depende de:** F2-07
- **Comando de teste:** `python scripts/exportar-relatorio.py && python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. QUANDO o comando roda O SISTEMA DEVE gerar plano/RELATORIO.md contendo capa com nome do projeto e data, quadro resumo por estado, e uma secao por bloco.
2. QUANDO gera a secao de um bloco O SISTEMA DEVE incluir id, titulo, complexidade, estado, dependencias e os criterios de aceite integrais.
3. ONDE plano/metricas.json existir O SISTEMA DEVE incluir uma secao de metricas com turnos usados sobre orcados por bloco e o total.
4. SE plano/RELATORIO.md ja existir ENTAO O SISTEMA DEVE sobrescreve-lo sem perguntar, porque o arquivo e derivado.
5. O SISTEMA DEVE gerar o relatorio apenas a partir de plano/blocos.json, dos arquivos de spec e de plano/metricas.json, sem consultar o git nem inventar texto.
6. SE um arquivo de spec referenciado nao existir ENTAO O SISTEMA DEVE escrever 'spec ausente' naquela secao e continuar.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe um documento único, legível por quem não usa Claude Code, com o plano inteiro, o status de cada bloco e as métricas. É o artefato que o dono manda para o time ou para o cliente.

## 3. Escopo
- Criar `scripts/exportar-relatorio.py` — gerador determinístico.
- Criar `commands/exportar.md` — comando que localiza e roda o script.
- Replicar os dois em `plugins/maestro/`.

---

### F2-12 — F-MULTIFASE (desenho): contrato de resolucao do arquivo de plano

- **Complexidade / modelo / revisor:** C4 / claude-opus-5 / claude-opus-5
- **Estado:** pendente
- **Depende de:** F2-06, F2-08, F2-09, F2-10, F2-11
- **Comando de teste:** `python scripts/validar-plano.py`

**Critérios de aceite:**
1. O SISTEMA DEVE produzir plano/specs/F2-13-multifase-impl.md com as 11 secoes do gabarito de anatomia-da-spec.md preenchidas.
2. O SISTEMA DEVE definir a ordem de precedencia de resolucao do arquivo de plano em no maximo 4 regras numeradas e mutuamente exclusivas.
3. O SISTEMA DEVE definir o comportamento para plano/blocos.json legado sem diretorio de fase, garantindo que planos da v1.2 continuem funcionando sem migracao.
4. O SISTEMA DEVE definir como dependencias entre blocos de fases diferentes sao declaradas e validadas.
5. SE duas fases declararem o mesmo id de bloco ENTAO a spec DEVE definir o comportamento como erro de validacao, e nao como resolucao silenciosa.
6. O SISTEMA DEVE listar nominalmente todos os arquivos de comando que a implementacao precisa alterar.
7. O SISTEMA DEVE definir o comportamento de --fase ausente quando existe mais de uma fase.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe a spec de implementação `F2-13-multifase-impl.md`, fechando como o Maestro resolve qual arquivo de plano usar quando há mais de uma fase. Nenhuma linha de comando é alterada aqui — o produto deste bloco é uma spec.

## 3. Escopo
- Escrever `plano/specs/F2-13-multifase-impl.md` completa, nas 11 seções do gabarito.
- Acrescentar a `schema-blocos.md` (e cópia) a seção que documenta o layout multifase e a forma de declarar dependência entre fases.

---

### F2-13 — F-MULTIFASE (implementacao): --fase em todos os comandos

- **Complexidade / modelo / revisor:** C4 / claude-sonnet-5 / claude-opus-5
- **Estado:** pendente
- **Depende de:** F2-12
- **Comando de teste:** `python scripts/validar-plano.py && python scripts/verificar-repo.py`

**Critérios de aceite:**
1. QUANDO um comando recebe --fase <nome> O SISTEMA DEVE operar sobre plano/<nome>/blocos.json.
2. SE --fase for omitido e existir plano/blocos.json ENTAO O SISTEMA DEVE operar sobre plano/blocos.json sem exigir argumento.
3. SE --fase for omitido e existir mais de um diretorio de fase sem plano/blocos.json ENTAO O SISTEMA DEVE listar as fases disponiveis e sair com codigo 1 sem escrever nada.
4. SE --fase apontar para uma fase inexistente ENTAO O SISTEMA DEVE listar as fases existentes e sair com codigo 1.
5. SE o mesmo id de bloco aparecer em duas fases ENTAO validar-plano.py DEVE reportar erro e sair com codigo 1.
6. QUANDO validar-plano.py roda sem --fase sobre um plano legado da v1.2 O SISTEMA DEVE produzir o mesmo resultado que produzia antes desta alteracao.
7. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

resumo indisponivel

---

### F2-14 — F-PARALELO (desenho): contrato de despacho simultaneo e deteccao de conflito

- **Complexidade / modelo / revisor:** C5 / claude-opus-5 / claude-opus-5
- **Estado:** pendente
- **Depende de:** F2-07, F2-13
- **Comando de teste:** `python scripts/validar-plano.py`

**Critérios de aceite:**
1. O SISTEMA DEVE produzir plano/specs/F2-15-paralelo-impl.md com as 11 secoes do gabarito de anatomia-da-spec.md preenchidas.
2. O SISTEMA DEVE definir o predicado de elegibilidade para execucao simultanea como uma conjuncao de condicoes numeradas e verificaveis uma a uma.
3. O SISTEMA DEVE especificar o algoritmo de disjuncao de arquivos_permitidos, incluindo o tratamento de globs com ** e de globs que se sobrepoem parcialmente.
4. SE a disjuncao entre dois conjuntos de globs nao puder ser provada ENTAO a spec DEVE determinar serializacao, nunca execucao simultanea.
5. A spec DEVE proibir execucao simultanea de qualquer bloco de complexidade C5.
6. A spec DEVE definir a fase de commit como serializada, com no maximo um bloco commitando por vez.
7. A spec DEVE definir um teto de paralelismo com valor padrao numerico e o campo de configuracao que o altera.
8. SE qualquer bloco do lote paralelo falhar ENTAO a spec DEVE definir o destino dos blocos restantes sem deixar nenhum em estado em_andamento orfao.
9. A spec DEVE conter uma secao de red-team com no minimo 8 cenarios de corrida ou conflito e a resposta do sistema a cada um.
10. A spec DEVE definir o comportamento em caso de interrupcao da sessao no meio de um lote paralelo, de forma que /maestro:retomar reconstrua o estado.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco existe a spec `F2-15-paralelo-impl.md`, fechando quando dois blocos podem rodar ao mesmo tempo e o que acontece em cada corrida possível. Nenhum código é escrito aqui.

**Por que C5:** dois agentes escrevendo o mesmo arquivo destroem trabalho já aprovado, e o dono só descobre depois do commit. O dano é irreversível na prática — a sessão do agente que perdeu a escrita não existe mais. Erro de desenho aqui não aparece em teste; aparece em produção, uma vez, tarde.

## 3. Escopo
- Escrever `plano/specs/F2-15-paralelo-impl.md` completa, nas 11 seções do gabarito.
- Incluir a seção de red-team com no mínimo 8 cenários de corrida e a resposta do sistema a cada um.

---

### F2-15 — F-PARALELO (implementacao): despacho simultaneo no maestro.md

- **Complexidade / modelo / revisor:** C4 / claude-sonnet-5 / claude-opus-5
- **Estado:** pendente
- **Depende de:** F2-14
- **Comando de teste:** `python scripts/paralelo.py && python scripts/verificar-repo.py`

**Critérios de aceite:**
1. QUANDO paralelo.py roda sobre um plano O SISTEMA DEVE imprimir os lotes elegiveis para execucao simultanea, um lote por linha.
2. SE dois blocos liberados tiverem globs de arquivos_permitidos que se sobrepoem ENTAO O SISTEMA DEVE colocar cada um em um lote separado.
3. SE um bloco liberado for de complexidade C5 ENTAO O SISTEMA DEVE coloca-lo sozinho em um lote.
4. SE um bloco tiver bloqueado_por preenchido ENTAO O SISTEMA DEVE exclui-lo de todos os lotes.
5. O SISTEMA DEVE limitar cada lote ao teto de paralelismo definido na spec de desenho.
6. QUANDO o maestro despacha um lote O SISTEMA DEVE marcar todos os blocos do lote como em_andamento antes de invocar qualquer agente.
7. SE um bloco do lote falhar ENTAO O SISTEMA DEVE concluir os demais e reportar o lote inteiro ao usuario, sem deixar nenhum bloco em em_andamento.
8. O SISTEMA DEVE serializar a fase de commit, com no maximo um commit em andamento por vez.
9. SE paralelo.py nao conseguir provar a disjuncao de dois blocos ENTAO O SISTEMA DEVE separa-los em lotes distintos.

**Spec (objetivo e escopo):**

resumo indisponivel

---

### F2-16 — D-INSTALACAO: lista completa de comandos em INSTALACAO-USUARIO.md

- **Complexidade / modelo / revisor:** C2 / claude-haiku-4-5 / claude-sonnet-5
- **Estado:** pendente
- **Depende de:** F2-06, F2-08, F2-09, F2-10, F2-11
- **Comando de teste:** `python scripts/verificar-repo.py --check comandos-documentados && python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. O SISTEMA DEVE listar em INSTALACAO-USUARIO.md um item por arquivo existente em commands/, com o nome do comando e uma linha de descricao.
2. O SISTEMA DEVE declarar a quantidade de comandos por extenso e essa quantidade DEVE ser igual ao numero de arquivos em commands/.
3. QUANDO a verificacao 'comandos-documentados' roda O SISTEMA DEVE reportar zero divergencias entre a lista do documento e o conteudo de commands/.
4. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, `INSTALACAO-USUARIO.md` lista todos os comandos que o plugin realmente instala, com uma linha de descrição cada. Hoje o documento fala em "cinco comandos" e o plugin já tem mais que isso.

## 3. Escopo
- Substituir a contagem e a lista de comandos em `INSTALACAO-USUARIO.md`.
- Replicar em `plugins/maestro/INSTALACAO-USUARIO.md`.

---

### F2-17 — D-SETUP-STEP5: passo 5 da skill maestro-setup lista todos os comandos

- **Complexidade / modelo / revisor:** C2 / claude-haiku-4-5 / claude-sonnet-5
- **Estado:** pendente
- **Depende de:** F2-06, F2-08, F2-09, F2-10, F2-11
- **Comando de teste:** `python scripts/verificar-repo.py --check comandos-documentados && python scripts/verificar-repo.py --check paridade`

**Critérios de aceite:**
1. O SISTEMA DEVE listar no passo de fechamento da skill maestro-setup um item por arquivo existente em commands/.
2. O SISTEMA DEVE separar a lista em acoes do dia a dia e acoes de correcao, com no maximo 4 itens no primeiro grupo.
3. QUANDO a verificacao 'comandos-documentados' roda O SISTEMA DEVE reportar zero divergencias entre a lista do passo de fechamento e o conteudo de commands/.
4. QUANDO a verificacao 'paridade' roda apos a alteracao O SISTEMA DEVE reportar zero divergencias entre as duas copias.

**Spec (objetivo e escopo):**

## 2. Objetivo
Depois deste bloco, quem acabou de rodar `/maestro:setup` vê todos os comandos disponíveis, agrupados por uso. Hoje o Passo 5 se chama "Fechar com as três ações" e lista apenas `status`, `proxima` e `planejar` — o usuário novo nunca descobre o resto.

## 3. Escopo
- Reescrever o passo de fechamento de `skills/maestro-setup/SKILL.md`.
- Replicar em `plugins/maestro/skills/maestro-setup/SKILL.md`.

---
