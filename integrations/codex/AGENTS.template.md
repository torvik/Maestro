# {{projeto}} — Maestro (Codex)

## Regra fundamental

**NUNCA assuma o estado de uma tarefa baseado apenas na conversa.** O estado
real de cada bloco vive em `plano/blocos.json`. Consulte-o via script antes
de implementar, testar ou finalizar qualquer coisa.

## Antes de qualquer implementação

1. `python scripts/status.py` — consultar antes de implementar. Mostra o
   quadro do plano (equivalente ao intent `maestro status`: concluído, em
   andamento, liberado, travado).
2. `python scripts/maestro_next.py` — identifica o próximo bloco liberado.

## Lifecycle de um bloco

```
python scripts/maestro_run.py --dry-run <ID>
python scripts/maestro_run.py start <ID>
python scripts/maestro_run.py test <ID>
python scripts/maestro_run.py finish <ID> --success | --fail
```

## Verificação

`{{comando_verificacao}}`

## Regras

- Um bloco por sessão.
- O modelo usado vem do manifest (`maestro_run.py --dry-run <ID>`), nunca
  fixo neste arquivo.
- O revisor é sempre >= executor em capability.
- O estado de um bloco vem exclusivamente de `plano/blocos.json` — nunca da
  memória da conversa.
- Nada é marcado como concluído sem veredito do revisor.
