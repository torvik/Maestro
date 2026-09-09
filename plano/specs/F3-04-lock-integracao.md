# F3-04 — B-LOCK-MULTISESSAO (integração): lock no ciclo de execução

## 1. Identificação
- Complexidade: C4 · Modelo: claude-sonnet-5 · Agente: implementador · Revisor: claude-opus-5
- Depende de: F3-03 · Orçamento: 30 turnos
- Comando de teste: `python scripts/lock.py status && python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check portabilidade`

## 2. Objetivo
Depois deste bloco, nenhum bloco é marcado como `em_andamento` sem que a sessão tenha adquirido o lock do plano, e o lock é liberado em todo caminho de saída, inclusive nos de falha. O ciclo passa a ser seguro com duas sessões do Claude Code abertas no mesmo repositório.

## 3. Escopo
- Aquisição do lock em `agents/maestro.md`, imediatamente antes de marcar `em_andamento`, no ciclo de bloco único e no ciclo de lote paralelo.
- Liberação do lock em `agents/maestro.md` em todos os caminhos de encerramento: aprovado, reprovado, abortado por orçamento e abortado por erro.
- Guarda de lock em `commands/proxima.md`, antes de delegar ao agente `maestro`.
- Instrução de diagnóstico e liberação de lock órfão em `commands/retomar.md`.
- Entrada de `plano/.lock` no `.gitignore`.
- Réplica byte-a-byte dos três arquivos de `commands/` e `agents/` em `plugins/maestro/`.

## 4. Não faça
- Não escreva a lógica de lock em prosa dentro dos comandos. Todo acesso ao lock passa por `scripts/lock.py`, localizado pela skill `maestro-runtime`. Instrução em linguagem natural para criar ou apagar arquivo de lock é o que este bloco existe para eliminar.
- Não libere o lock antes do commit. A ordem é: adquirir, executar, revisar, commitar, liberar. Liberar antes do commit reabre a janela de corrida no momento mais caro.
- Não faça o agente decidir sozinho usar `--forcar`. `--forcar` só é usado depois de confirmação explícita do dono, com o conteúdo do lock antigo exibido na tela.
- Não altere o campo `bloqueado_por` nem o comando `/maestro:destravar` para tratar lock. Lock e bloqueio são coisas diferentes: `bloqueado_por` é decisão de produto pendente, lock é exclusão mútua entre sessões.
- Não introduza `python3` literal nem `find ~/` em nenhuma das linhas novas. A verificação `portabilidade` faz parte do comando de teste deste bloco.
- Não crie um comando `/maestro:lock`. Isso mudaria a contagem de comandos e quebraria a verificação `comandos-documentados` de dois documentos.
- Não toque em `scripts/lock.py`. Ele está pronto e é contrato de entrada deste bloco.

## 5. Contrato

**Ponto de aquisição, ciclo de bloco único** (`agents/maestro.md`, passo que hoje marca `em_andamento`):

```
lock.py adquirir --blocos <ID>   →  0  segue
                                 →  1  imprime a saida ao dono e ENCERRA sem escrever em blocos.json
                                 →  2  imprime a saida ao dono e ENCERRA sem escrever em blocos.json
                                 →  3  imprime a saida ao dono e ENCERRA sem escrever em blocos.json
```

**Ponto de aquisição, ciclo de lote paralelo:** uma única aquisição para o lote inteiro, com todos os IDs do lote em `--blocos`, antes de marcar qualquer bloco do lote como `em_andamento`.

**Pontos de liberação**, todos com `lock.py liberar --blocos <mesmos IDs da aquisição>`:

| Caminho de encerramento | Libera? |
|---|---|
| Revisor aprovou e o commit foi feito | sim |
| Revisor reprovou e `tentativas` foi incrementado | sim |
| Orçamento de turnos estourado | sim |
| Erro não tratado durante a execução | sim |
| Dono interrompeu a sessão | não há como; é o caso que `/maestro:retomar` resolve |

**Guarda em `commands/proxima.md`:** antes de delegar ao agente `maestro`, rodar `lock.py status`. Saída 1 significa plano ocupado: exibir o conteúdo do lock e encerrar sem delegar. O modo `--dry-run` não consulta lock, porque não escreve nada.

**Instrução em `commands/retomar.md`:** ao encontrar bloco em `em_andamento`, rodar `lock.py status` e apresentar as três situações — lock ausente (sessão morreu antes de adquirir, siga o fluxo atual), lock com os mesmos IDs do bloco em limbo (é o lock da sessão morta, ofereça `lock.py liberar --blocos <IDs>`), lock com IDs diferentes (há outra sessão viva, não libere nada e avise o dono).

## 6. Regras
**R1.** A aquisição precede a escrita de `em_andamento` em `plano/blocos.json`. Nenhuma escrita no plano ocorre entre a decisão de executar e a saída 0 do `adquirir`.
**R2.** O conjunto de IDs passado ao `liberar` é o mesmo passado ao `adquirir`, sem acréscimo nem remoção, porque `lock.py` compara conjuntos exatos.
**R3.** No lote paralelo, o lock é do lote inteiro e é liberado uma única vez, ao final do lote, mesmo que blocos individuais tenham terminado antes.
**R4.** Qualquer código de saída diferente de 0 no `adquirir` encerra a sessão de execução. Não há repetição automática, não há espera, não há laço.
**R5.** A liberação é chamada mesmo quando o bloco falhou. Lock retido após falha trava o dono na próxima sessão.
**R6.** `--fase <nome>` recebido pelo comando é repassado a `lock.py`, para que o lock resolva o mesmo plano que o comando está usando.
**R7.** O `.gitignore` recebe duas linhas: `plano/.lock` e `plano/*/.lock`. O arquivo de lock nunca entra em commit.
**R8.** A localização de `lock.py` segue a skill `maestro-runtime`, como todos os demais scripts invocados por comando.

## 7. Arquivos
`agents/maestro.md`, `commands/proxima.md`, `commands/retomar.md`, `.gitignore` e as três cópias correspondentes em `plugins/maestro/`.

## 8. Dados
Os IDs de bloco vêm de `plano/blocos.json` e do lote montado por `scripts/paralelo.py`. O estado do lock vem de `scripts/lock.py`. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO o agente `maestro` vai marcar um bloco como `em_andamento` O SISTEMA DEVE ter adquirido o lock do plano antes de qualquer escrita em `plano/blocos.json`.
2. SE `lock.py adquirir` sai com código diferente de 0 ENTÃO O SISTEMA DEVE exibir a saída do script ao dono e encerrar sem escrever em `plano/blocos.json`.
3. QUANDO a execução de um bloco termina com o revisor aprovando e o commit feito O SISTEMA DEVE liberar o lock.
4. QUANDO a execução de um bloco termina com reprovação, estouro de orçamento ou erro O SISTEMA DEVE liberar o lock nos três casos.
5. QUANDO o maestro despacha um lote paralelo O SISTEMA DEVE adquirir um único lock com todos os IDs do lote antes de marcar qualquer bloco do lote.
6. SE `/maestro:proxima` roda com `lock.py status` retornando 1 ENTÃO O SISTEMA DEVE exibir o conteúdo do lock e encerrar sem delegar ao agente `maestro`.
7. SE `/maestro:proxima` roda com `--dry-run` ENTÃO O SISTEMA DEVE ignorar o lock, porque nada é escrito.
8. QUANDO `/maestro:retomar` encontra um bloco em `em_andamento` O SISTEMA DEVE consultar `lock.py status` e apresentar as três situações do contrato antes de qualquer ação.
9. SE o lock existente aponta para IDs diferentes do bloco em limbo ENTÃO O SISTEMA DEVE recusar a liberação e avisar que pode haver outra sessão ativa.
10. O SISTEMA DEVE usar `--forcar` apenas após confirmação explícita do dono, com o conteúdo do lock antigo exibido.
11. QUANDO `--fase <nome>` é passado ao comando O SISTEMA DEVE repassar `--fase <nome>` a `lock.py`.
12. O SISTEMA DEVE registrar `plano/.lock` e `plano/*/.lock` no `.gitignore`.
13. QUANDO as verificações `paridade` e `portabilidade` rodam após a alteração O SISTEMA DEVE reportar zero falhas.

## 10. Casos de teste obrigatórios
- T1 — leitura de `agents/maestro.md`: a chamada de aquisição aparece antes da instrução de marcar `em_andamento`, no ciclo de bloco único.
- T2 — leitura de `agents/maestro.md`: existe instrução de liberação nos quatro caminhos de encerramento da tabela do contrato.
- T3 — leitura de `agents/maestro.md`: no ciclo de lote, a aquisição lista todos os IDs do lote e ocorre antes de marcar qualquer bloco.
- T4 — leitura de `commands/proxima.md`: a guarda de lock existe e o caminho `--dry-run` está explicitamente isento.
- T5 — leitura de `commands/retomar.md`: as três situações de lock estão descritas com a ação de cada uma.
- T6 — `.gitignore` contém as duas linhas e `git status` não lista `plano/.lock` após `lock.py adquirir --blocos F3-04`.
- T7 — busca textual nos arquivos alterados: nenhuma ocorrência de `python3 ` sem fallback e nenhuma de `find ~/`.
- T8 — busca textual nos arquivos alterados: nenhuma instrução de criar ou apagar o arquivo de lock sem passar por `lock.py`.
- T9 — `python scripts/verificar-repo.py --check comandos-documentados` sai com 0, provando que nenhum comando novo foi criado.
- T10 — `python scripts/verificar-repo.py --check paridade` e `--check portabilidade` saem com 0.
- T11 — borda: `lock.py adquirir --blocos X` deixa o lock no disco; `lock.py status` retorna 1; limpar com `lock.py liberar --blocos X` ao final do teste.

## 11. Pare e pergunte
- Se o ciclo de lote paralelo em `agents/maestro.md` não tiver um ponto único de encerramento onde a liberação caiba → pare e descreva a estrutura encontrada antes de reorganizar o ciclo.
- Se você concluir que o lock precisa ser por bloco em vez de por plano → pare, porque o que o lock protege é a escrita em `blocos.json`, que é um arquivo só.
- Se alguma alteração exigir tocar em `scripts/paralelo.py` → pare e pergunte, porque esse arquivo está fora da seção 7 e escrita fora dela reprova na revisão.
- Se adicionar a guarda de lock em `commands/proxima.md` tornar o comando dependente de Python instalado → pare e pergunte, porque a skill `maestro-runtime` define um caminho de degradação para máquina sem interpretador.
