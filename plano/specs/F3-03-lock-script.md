# F3-03 — B-LOCK-MULTISESSAO (script): `scripts/lock.py`

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Agente: implementador · Revisor: claude-opus-5
- Depende de: nenhum · Orçamento: 30 turnos
- Comando de teste: `python scripts/lock.py status && python scripts/verificar-repo.py --check paridade`

## 2. Objetivo
Depois deste bloco existe um utilitário determinístico que adquire e libera um lock exclusivo sobre um arquivo de plano, com criação atômica e sem heurística. Hoje duas sessões do Claude Code abertas no mesmo repositório podem marcar blocos como `em_andamento` e gravar em `plano/blocos.json` uma por cima da outra, e o dono só descobre quando o histórico de um dos blocos some.

## 3. Escopo
- Criação de `scripts/lock.py` com três subcomandos: `adquirir`, `liberar`, `status`.
- Resolução de fase idêntica à dos demais scripts, para que o lock viva ao lado do `blocos.json` correspondente.
- Réplica byte-a-byte em `plugins/maestro/scripts/lock.py`.

## 4. Não faça
- Não chame `os.kill(pid, 0)` para testar se o processo dono ainda vive. No Windows o `os.kill` do CPython encaminha para `TerminateProcess` e mata o processo alvo. Este bloco não faz sondagem de PID por nenhum meio.
- Não use `psutil` nem qualquer dependência externa. Só biblioteca padrão, como todo script do Maestro.
- Não remova lock automaticamente por idade. Lock velho vira aviso e exige `--forcar` explícito; remoção silenciosa é exatamente a corrida que este bloco existe para impedir.
- Não use o padrão "verificar se existe, depois criar". Entre as duas operações cabe a segunda sessão. A criação é uma única chamada atômica.
- Não escreva em `plano/blocos.json`, em `plano/metricas.json` nem em nenhuma spec. Este script mexe apenas no arquivo de lock.
- Não trate o campo `pid` como dono do lock. Cada invocação de `lock.py` é um processo novo e de vida curta; o PID gravado já estará morto quando o `liberar` rodar. O PID é diagnóstico, e nada mais.
- Não invente um comando `/maestro:lock`. A integração com os comandos é o bloco seguinte, e a interface é este script.

## 5. Contrato

**Caminho do lock.** Irmão do `blocos.json` resolvido: `plano/.lock` no layout legado, `plano/<fase>/.lock` no layout multifase. A resolução de fase copia as quatro regras de precedência já implementadas em `scripts/status.py`, incluindo `--fase`, `fase_padrao` do `maestro.config.json` e a variável `MAESTRO_PLANO`.

**Conteúdo do lock**, JSON com schema versionado:

```json
{
  "schema": 1,
  "blocos": ["F3-01"],
  "criado_em": "2026-09-08T14:03:11Z",
  "pid": 12345,
  "host": "nome-da-maquina",
  "plano": "plano/blocos.json"
}
```

**Invocações e códigos de saída:**

| Comando | Efeito | Saída |
|---|---|---|
| `lock.py adquirir --blocos <ID>[,<ID>] [--fase <n>] [--forcar]` | cria o lock | `0` adquirido |
| | lock vivo já existe | `1` recusado, imprime dono e idade |
| | lock ilegível ou malformado | `2` recusado, sem sobrescrever |
| | falha de escrita no disco | `3` recusado |
| `lock.py liberar --blocos <ID>[,<ID>] [--fase <n>] [--forcar]` | remove o lock | `0` removido ou já inexistente |
| | conjunto de blocos diverge do lock | `1` recusado |
| | lock ilegível | `2` recusado sem `--forcar` |
| `lock.py status [--fase <n>]` | plano livre | `0` |
| | lock presente | `1`, imprime o conteúdo |

**Linha de recusa de `adquirir`**, formato fixo:

```
LOCK OCUPADO  blocos=<lista>  criado_em=<iso>  idade=<n>min  host=<host>  pid=<pid>
  Outra sessao pode estar executando este plano. Feche-a ou rode: lock.py adquirir --blocos <IDs> --forcar
```

Quando a idade excede o limite, uma linha adicional antecede a instrução:

```
  Lock com mais de <limite>min — possivelmente orfao de uma sessao interrompida.
```

## 6. Regras
**R1.** A criação usa `os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)` numa única chamada. Se levantar `FileExistsError`, o lock já existe e a resposta é recusa. Nunca há `os.path.exists` antes da criação.
**R2.** O conteúdo é escrito e o descritor fechado antes de o comando retornar 0. Lock vazio no disco é considerado malformado pela invocação seguinte.
**R3.** Ownership é o conjunto de `blocos`. `liberar` só remove quando o conjunto informado é exatamente igual ao conjunto gravado, comparado como conjunto e não como lista ordenada.
**R4.** `--forcar` em `adquirir` sobrescreve qualquer lock, inclusive malformado, e imprime na saída o conteúdo antigo antes de sobrescrever. `--forcar` em `liberar` remove o arquivo sem comparar conjunto.
**R5.** O limite de idade vem de `lock_timeout_min` em `maestro.config.json`; na ausência do campo ou do arquivo o valor é 120. Idade não altera código de saída: lock velho continua sendo recusa 1.
**R6.** `liberar` sobre plano sem lock sai 0 e imprime `LOCK LIVRE`. A operação é idempotente porque o agente pode chamá-la duas vezes num fluxo de erro.
**R7.** `criado_em` é ISO 8601 UTC com sufixo `Z`, mesmo formato usado em `plano/metricas.json`.
**R8.** Se o diretório do plano resolvido não existir, `adquirir` sai 3 e não cria diretório. Criar estrutura de plano é trabalho do `/maestro:setup`.
**R9.** Todos os subcomandos imprimem em uma linha o caminho do lock que resolveram, para que o dono possa apagá-lo à mão se precisar.
**R10.** Só biblioteca padrão do Python 3.9 ou superior.

## 7. Arquivos
`scripts/lock.py` e `plugins/maestro/scripts/lock.py`. Nenhum outro arquivo é criado ou alterado por este bloco.

## 8. Dados
O nome do host vem de `socket.gethostname()`, o PID de `os.getpid()`, o horário de `datetime.now(timezone.utc)`, os IDs de bloco do argumento de linha de comando e o limite de idade de `maestro.config.json`. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `lock.py adquirir --blocos F3-01` roda sobre um plano sem lock O SISTEMA DEVE criar o arquivo de lock com os seis campos do contrato e sair com código 0.
2. SE o arquivo de lock já existe ENTÃO O SISTEMA DEVE recusar a aquisição, imprimir a linha `LOCK OCUPADO` com blocos, idade e host, e sair com código 1 sem alterar o arquivo.
3. SE o arquivo de lock existe e não é JSON válido ENTÃO O SISTEMA DEVE sair com código 2 e deixar o arquivo intacto.
4. QUANDO `lock.py adquirir --forcar` roda sobre um lock existente O SISTEMA DEVE imprimir o conteúdo antigo e substituir o arquivo, saindo com código 0.
5. QUANDO `lock.py liberar --blocos F3-01` roda sobre um lock cujo campo `blocos` é exatamente `["F3-01"]` O SISTEMA DEVE remover o arquivo e sair com código 0.
6. SE `lock.py liberar` recebe um conjunto de blocos diferente do gravado no lock ENTÃO O SISTEMA DEVE recusar a remoção e sair com código 1.
7. QUANDO `lock.py liberar` roda sobre um plano sem lock O SISTEMA DEVE imprimir `LOCK LIVRE` e sair com código 0.
8. QUANDO `lock.py status` roda sobre um plano sem lock O SISTEMA DEVE sair com código 0, e sobre um plano com lock DEVE sair com código 1.
9. SE a idade do lock excede `lock_timeout_min` ENTÃO O SISTEMA DEVE imprimir a linha de possível órfão e ainda assim sair com código 1.
10. QUANDO `--fase <nome>` é informado O SISTEMA DEVE operar sobre `plano/<nome>/.lock`.
11. O SISTEMA DEVE criar o arquivo de lock por uma única chamada atômica, sem consultar a existência do arquivo antes.
12. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `adquirir --blocos F3-01` em plano limpo: sai 0 e `plano/.lock` existe com os seis campos.
- T2 — `adquirir --blocos F3-02` logo em seguida: sai 1 e a saída contém `LOCK OCUPADO`.
- T3 — o conteúdo de `plano/.lock` após T2 é byte a byte igual ao de após T1.
- T4 — lock com o conteúdo `nao-e-json`: `adquirir` sai 2 e o arquivo permanece intacto.
- T5 — `adquirir --blocos F3-02 --forcar` sobre o lock de T4: sai 0 e o novo conteúdo é JSON válido.
- T6 — `liberar --blocos F3-99` com lock de `F3-02`: sai 1 e o arquivo continua no disco.
- T7 — `liberar --blocos F3-02`: sai 0 e o arquivo some.
- T8 — `liberar --blocos F3-02` repetido: sai 0 e imprime `LOCK LIVRE`.
- T9 — lote: `adquirir --blocos F3-01,F3-05` e `liberar --blocos F3-05,F3-01` (ordem trocada): ambos saem 0.
- T10 — lock com `criado_em` de 300 minutos atrás e `lock_timeout_min` ausente do config: `adquirir` imprime a linha de possível órfão e sai 1.
- T11 — `status` com e sem lock: saídas 1 e 0 respectivamente.
- T12 — `--fase inexistente`: sai 1 sem criar nada, como os demais scripts.
- T13 — busca textual no arquivo entregue: nenhuma ocorrência de `os.kill` e nenhuma de `os.path.exists` antes da criação do lock.
- T14 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se você achar necessário sondar se o PID gravado ainda está vivo → pare, porque a seção 4 proíbe e a alternativa segura no Windows não cabe no orçamento deste bloco.
- Se a criação atômica com `O_EXCL` se comportar de forma diferente no Windows durante o teste → pare e reporte o comportamento observado antes de trocar por qualquer alternativa.
- Se você concluir que precisa alterar `commands/` ou `agents/` para provar o bloco → pare, porque a integração é o bloco F3-04 e escrita fora da seção 7 reprova na revisão.
- Se o dono já tiver um `plano/.lock` no repositório quando você começar → pare e pergunte antes de tocar nele, porque pode haver outra sessão ativa.
