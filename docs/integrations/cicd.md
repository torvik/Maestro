# CI/CD headless

> Bloco F15-01. Implementação em `integrations/relay/headless.py` e
> `integrations/relay/headless_cli.py`. Spec:
> `plano/specs/F15-01-cicd-relay.md`.

## O que é modo headless

Modo interativo (`/maestro:proxima <ID>`) para a cada bloco e espera o dono
do projeto revisar. Modo headless não pode fazer isso — não há humano do
outro lado em um runner de CI. Duas regras definem o modo headless:

1. **Autonomia forçada em memória.** `maestro.config.json` continua com
   `"autonomia": "parar_a_cada_bloco"` no disco (não é reescrito). Em modo
   headless, toda decisão usa autonomia efetiva `"auto"` — override que só
   existe em memória, dentro de `HeadlessRunner`.
2. **Pendência vira bloqueio, nunca pergunta.** Se algo exigiria uma
   pergunta em modo interativo (spec ambígua, dado de negócio faltando), o
   modo headless registra a falha com `HeadlessRunner.block_pending_question`
   (equivalente a `maestro_run.py finish <ID> --fail --motivo <texto>`) e
   sai com código 1. Nunca chama `input()`.

## Restrição de escopo importante

`scripts/maestro_run.py` (bloco F4-03) **não foi modificado** por F15-01 —
não estava em `arquivos_permitidos` deste bloco. Por isso a sintaxe headless
não é `scripts/maestro_run.py --headless ...` (essa flag não existe no
parser atual), e sim o wrapper:

```bash
python integrations/relay/headless_cli.py --headless --dry-run <ID> [--fase <nome>]
python integrations/relay/headless_cli.py --headless --block-pending <ID> --motivo "<texto>" [--fase <nome>]
```

O wrapper nunca importa nem edita `scripts/maestro_run.py`; ele invoca o
binário existente via `subprocess`, do mesmo jeito que o próprio
`maestro_run.py` invoca `scripts/lock.py`. Detalhes e a evidência de por que
a sintaxe literal falha estão na spec, seção 4.

Se um bloco futuro adicionar `scripts/**` a `arquivos_permitidos`, a flag
`--headless` pode ser adicionada diretamente ao parser de `maestro_run.py`
delegando para `HeadlessRunner` — sem mudar o contrato do `HeadlessRunner`
em si.

## GitHub Actions

Workflow de exemplo: `.github/workflows/maestro-ci.yml`.

```yaml
name: Maestro CI

on:
  push:
  workflow_dispatch:
    inputs:
      block_id:
        description: 'ID do bloco para dry-run headless (opcional)'
        required: false
        default: ''

jobs:
  run-next:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Mostrar proximo bloco liberado
        run: python scripts/maestro_next.py --run
```

Esse passo (`maestro_next.py --run`) é somente leitura: mostra qual bloco
seria executado a seguir e não requer nenhuma credencial.

Para rodar um dry-run headless de um bloco específico, dispare o workflow
manualmente (`workflow_dispatch`) informando `block_id`, ou adicione um passo
equivalente ao seu próprio pipeline:

```yaml
- name: Dry-run headless
  env:
    MAESTRO_HEADLESS: 'true'
  run: python integrations/relay/headless_cli.py --headless --dry-run F0-01
```

### Variáveis de ambiente relevantes

| Variável | Uso |
|----------|-----|
| `MAESTRO_CONFIG` | caminho alternativo para `maestro.config.json` (herdado de `maestro_run.py`) |
| `MAESTRO_PLANO` | caminho alternativo para `blocos.json` (herdado de `maestro_run.py`) |
| `MAESTRO_HEADLESS` | informativo — sinaliza ao operador/logs que a execução é headless; não é lido pelo código, é só convenção de documentação |

Nenhuma credencial é necessária para `--dry-run` ou para
`maestro_next.py --run` (ambos somente leitura). Executar `start`/`finish`
em CI real requer que o runner tenha permissão de escrita no checkout (lock
de arquivo local, não um serviço externo).

## Equivalentes a GitHub Actions

Qualquer executor que rode um contêiner Python 3.11+ e faça checkout do
repositório serve: GitLab CI, Jenkins, um cron local. O único requisito é
invocar `python integrations/relay/headless_cli.py --headless ...` (ou
`python scripts/maestro_next.py --run` para inspeção) — nenhum passo é
específico do GitHub.

## Código de saída

- `0` — bloco executado (dry-run bem-sucedido) sem pendência.
- `1` — falha ou bloqueio (`block_pending_question`, ou `maestro_run.py`
  saiu com código diferente de 0).
- `2` — uso inválido da CLI do wrapper (faltou `--headless`, faltou
  `--dry-run`/`--block-pending`, ou faltou `--motivo`).

## Integração com Relay

A integração com o Relay (receber triggers externos, publicar eventos UEP)
está documentada separadamente em
[`docs/integrations/relay.md`](relay.md) — é um stub, porque a API do Relay
ainda não foi definida.
