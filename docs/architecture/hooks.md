# Hooks bounded

`packages/core/hooks` executa comandos externos configurados pelo usuário em
pontos do ciclo de vida de um bloco. "Bounded" significa três limites duros
que nenhum hook consegue ultrapassar: tempo, tamanho de saída e ausência de
shell. Módulo puro: só stdlib.

## Eventos suportados

```python
HOOK_EVENTS = frozenset({
    "pre_run", "post_run",
    "pre_review", "post_review",
    "on_fail", "on_block_complete",
})
```

Rodar um evento fora dessa lista levanta `HookError` sem executar nada.

## API

```python
from packages.core.hooks import HookRunner, HookResult, HookError

runner = HookRunner(hooks=[
    {"event": "pre_run", "command": "python -c \"exit(0)\"", "timeout": 30, "critical": False},
])
results = runner.run_event("pre_run", context={"block_id": "F10-03"})
```

| Membro | Conteúdo |
|---|---|
| `HookRunner(hooks=None, spool_path=None, root=None)` | `hooks` aceita `HookConfig` ou `dict`; `root` é o cwd de execução dos comandos (default: raiz do projeto via `maestro_runtime`, senão `cwd`). |
| `run_event(event, context=None) -> list[HookResult]` | Roda, em ordem de configuração, todos os hooks do evento. |
| `flush_spool() -> list[HookResult]` | Lê o spool de falhas sem apagar nada. |
| `clear_spool() -> int` | Descarta o spool; devolve quantos registros foram removidos. |

`HookConfig(event, command, timeout=30, critical=False, env=None)` e
`HookResult(event, command, success, exit_code, stdout, stderr, timed_out, error)`
são dataclasses simples — sem lógica além de `to_dict()` em `HookResult`.

## Os três limites

1. **Tempo.** Todo hook tem `timeout` (default 30s). A execução usa
   `subprocess.Popen` + `proc.wait(timeout)`; ao expirar, `proc.kill()` e o
   resultado vem com `timed_out=True`, `success=False`.
2. **Saída.** `stdout`/`stderr` são capturados em arquivo temporário (não
   `PIPE`, para não travar em hook verboso) e truncados em `MAX_OUTPUT_CHARS`
   (8192) no resultado e `MAX_SPOOL_OUTPUT_CHARS` (4096) no spool.
3. **Shell.** Não há `shell=True`. O comando é dividido com `shlex.split` e
   executado direto — um `;` ou `&&` no valor de um `context` sanitizado não
   vira execução encadeada, porque nunca chega a um interpretador de shell.

## Sanitização de `context`

`run_event(event, context=...)` nunca repassa o dicionário do chamador direto
para o ambiente do processo filho:

- Chaves fora de `[A-Za-z_][A-Za-z0-9_]*` são descartadas em silêncio (uma
  chave digitada errado não deveria travar o hook, só ficar de fora).
- Valores viram string; os caracteres `\n`, `\r` e `\0` são trocados por
  espaço — impede injeção de variável de ambiente extra via quebra de linha.
- A chave final no ambiente é `MAESTRO_HOOK_` + chave em maiúsculas
  (`block_id` → `MAESTRO_HOOK_BLOCK_ID`).

Essa sanitização roda sempre, mesmo que o hook não use `context` (I3).

## Falha de hook: não-crítico vs. crítico

- **Não-crítico** (`critical=False`, padrão): falha vira `HookResult(success=False)`,
  é gravada no spool e a execução dos demais hooks do evento continua (I1).
- **Crítico** (`critical=True`): falha também vai para o spool, mas
  `run_event` levanta `HookError` imediatamente depois — a exceção carrega em
  `.results` tudo que já tinha rodado até ali, incluindo o hook que falhou
  (I2). Hooks seguintes do mesmo evento não rodam.

## Spool: single writer, append-only

Falhas (críticas ou não) são gravadas em `.maestro/hooks/spool.jsonl`, uma
linha JSON por registro, nunca reescrita (I4). Antes de cada escrita/leitura
há um lock exclusivo:

- Unix: `fcntl.flock` sobre um arquivo `.lock` ao lado do spool.
- Windows / sem `fcntl`: `open(lock_path, "x")` (falha se já existe) em loop
  com espera curta até `LOCK_TIMEOUT` (10s), depois `os.remove` do lockfile.

`flush_spool()` é leitura pura — devolve os registros como `HookResult` sem
apagar o arquivo. `clear_spool()` é a única operação que remove o spool, e só
depois de contar quantas linhas válidas existiam.

## Por que sem shell e sem dependência externa

Um hook roda com as credenciais e o ambiente de quem executa o Maestro. Dois
riscos concretos motivam as escolhas acima:

- **Injeção via `context`.** Se o comando fosse montado por interpolação de
  string e passado a um shell, um `block_id` malicioso (`"x; rm -rf /"`)
  viraria dois comandos. Sanitizar o `context` e nunca usar `shell=True`
  fecham essa porta nas duas pontas.
- **Hook preso trava o bloco inteiro.** Sem timeout, um hook que nunca
  termina (ou um comando interativo esperando stdin) bloquearia o ciclo de
  vida indefinidamente. `stdin=subprocess.DEVNULL` mais o `timeout` obrigatório
  garantem que todo hook devolve o controle, mesmo em erro.

## Adicionando um hook

Configuração é um `dict` (ou `HookConfig`) com `event` e `command`
obrigatórios; `timeout`, `critical` e `env` são opcionais. Configuração
inválida (evento desconhecido, `command` vazio, tipo errado) falha cedo, na
construção do `HookRunner` — fail-closed: um hook mal configurado nunca chega
a rodar parcialmente.
