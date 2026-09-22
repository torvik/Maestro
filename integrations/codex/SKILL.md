---
name: maestro-codex
description: Intents do Maestro para o adapter Codex. Use quando o agente Codex precisar consultar o estado do plano, descobrir o próximo bloco, executar o lifecycle de um bloco, configurar o Maestro em um projeto novo ou retomar um bloco interrompido.
---

# Maestro — Intents Codex

## maestro_status

- **Nome:** `maestro_status`
- **Descrição:** Mostra o quadro do plano — blocos concluídos, em
  andamento, liberados e travados.
- **Invocação CLI:** `python scripts/status.py`

## maestro_next

- **Nome:** `maestro_next`
- **Descrição:** Identifica o próximo bloco liberado para execução,
  respeitando dependências e bloqueios.
- **Invocação CLI:** `python scripts/maestro_next.py`

## maestro_run

- **Nome:** `maestro_run`
- **Descrição:** Executa o lifecycle de um bloco (dry-run, start, test,
  finish).
- **Invocação CLI:**
  ```
  python scripts/maestro_run.py --dry-run <ID>
  python scripts/maestro_run.py start <ID>
  python scripts/maestro_run.py test <ID>
  python scripts/maestro_run.py finish <ID> --success | --fail
  ```

## maestro_setup

- **Nome:** `maestro_setup`
- **Descrição:** Configura o Maestro em um projeto novo — gera
  `maestro.config.json`, `plano/blocos.json` e `AGENTS.md` a partir do
  template Codex.
- **Invocação CLI:**
  `python integrations/codex/installer/install.py --projeto <nome> --verificacao <cmd> [--destino <dir>]`

## maestro_retomar

- **Nome:** `maestro_retomar`
- **Descrição:** Recupera blocos `em_andamento` após uma sessão
  interrompida — analisa o que foi feito e oferece opções de continuação.
- **Invocação CLI:** `python scripts/status.py` (identifica blocos
  `em_andamento`) seguido de `python scripts/lock.py status` (verifica lock
  ativo antes de decidir retomar, resetar ou descartar)

## maestro_custos

- **Nome:** `maestro_custos`
- **Descrição:** Exibe o resumo de custo e uso de turnos do plano.
- **Invocação CLI:** `python scripts/status.py` (inclui resumo de métricas)

## maestro_destravar

- **Nome:** `maestro_destravar`
- **Descrição:** Remove o bloqueio de um bloco travado após decisão do dono.
- **Invocação CLI:** editar `plano/blocos.json` limpando o campo `bloqueado_por` do bloco.

## maestro_editar

- **Nome:** `maestro_editar`
- **Descrição:** Ajusta a spec de um bloco — pontual ou regeração completa.
- **Invocação CLI:** editar o arquivo de spec em `plano/specs/<ID>-*.md`.

## maestro_exportar

- **Nome:** `maestro_exportar`
- **Descrição:** Gera relatório do plano em `plano/RELATORIO.md`.
- **Invocação CLI:** `python scripts/status.py > plano/RELATORIO.md`

## maestro_planejar

- **Nome:** `maestro_planejar`
- **Descrição:** Cria ou atualiza o plano de blocos para um novo projeto ou fase.
- **Invocação CLI:** editar `plano/blocos.json` e `maestro.config.json` conforme o schema.

## maestro_replanejar

- **Nome:** `maestro_replanejar`
- **Descrição:** Ajusta o plano existente sem perder o histórico de execução.
- **Invocação CLI:** editar `plano/blocos.json` preservando blocos `concluido`.

## maestro_revisar

- **Nome:** `maestro_revisar`
- **Descrição:** Dispara revisão de auditoria de um bloco específico.
- **Invocação CLI:** `python scripts/maestro_run.py finish <ID> --success|--fail` após revisão manual.

## maestro_rollback

- **Nome:** `maestro_rollback`
- **Descrição:** Desfaz um bloco aprovado usando `git revert` (nunca `git reset`).
- **Invocação CLI:** `git revert <commit-sha>` (SHA do commit do bloco).
