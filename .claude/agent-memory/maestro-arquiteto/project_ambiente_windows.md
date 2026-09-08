---
name: Ambiente do dono é Windows sem python3
description: Na máquina do dono `python3` não existe e `find` não funciona no PowerShell — afeta todo comando_teste e toda instrução de script
type: project
---

A máquina do dono roda Windows 11. Verificado em 2026-09-08: `python3 --version` falha com a mensagem do alias da Microsoft Store; `python --version` retorna 3.14.3. `find ~/...` também não funciona no PowerShell.

**Why:** o Maestro é um plugin distribuído, e o próprio dono é o primeiro usuário Windows. Comandos e skills do repositório hoje usam `find ~/.claude/plugins/cache/maestro ...` e `python3 <script>`, ambos quebrados nesse ambiente. É a origem do bloco F2-02 (B-WIN), cujo escopo foi ampliado além do enunciado original para cobrir `python3` também.

**How to apply:** ao escrever qualquer `comando_teste`, exemplo de invocação ou instrução de script para este repositório, use `python`, nunca `python3`. Nunca use `find`, `which`, `where` nem `Get-ChildItem` para localizar arquivo — use caminhos candidatos testados um a um, ou `pathlib` dentro de um script já em execução. Antes de recomendar rodar um script, confirme que ele não depende de binário externo.
