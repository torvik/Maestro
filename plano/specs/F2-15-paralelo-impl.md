# F2-15 — F-PARALELO (implementação): despacho simultâneo no `maestro.md`

> **PLACEHOLDER.** Este arquivo é substituído integralmente pelo bloco de desenho **F2-14**, executado pelo `arquiteto` em Opus com revisão adversarial. Não execute F2-15 enquanto este aviso estiver aqui.
>
> F2-14 pode legitimamente concluir que F-PARALELO deve ser descartado. Se concluir, F2-15 não é executado.

## Restrições já fixadas (entrada para F2-14)

**Fail-closed.** Toda ambiguidade resulta em serialização. Ausência de prova de disjunção é conflito.

**Nunca paralelize um bloco C5.** Ele roda sozinho no lote.

**Commit serializado.** No máximo um bloco commitando por vez, sempre.

**Nenhum `em_andamento` órfão.** Nenhum caminho de falha pode terminar com bloco marcado `em_andamento` sem aviso ao dono.

**Desligável.** Com paralelismo desligado, o comportamento é idêntico ao da v1.2.

**Superfície.** `agents/maestro.md`, `commands/proxima.md`, `scripts/paralelo.py`, nas duas cópias. `scripts/paralelo.py` é analisador e planejador de lotes — ele não despacha agente e não escreve em `plano/blocos.json`.

**Paridade.** Verificado por `python scripts/verificar-repo.py --check paridade`.
