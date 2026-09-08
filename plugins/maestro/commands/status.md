---
description: Mostra o quadro do plano — concluído, em andamento, liberado, travado.
---

Encontre e rode o script `status.py` do Maestro. Tente nesta ordem:
1. `python3 scripts/status.py`
2. `python3 .claude/plugins/maestro/scripts/status.py`
3. Resultado do comando: `find ~/.claude/plugins/cache/maestro -name "status.py" 2>/dev/null | head -1` — rode esse caminho se encontrado
4. Se nenhum existir: leia `plano/blocos.json` diretamente e exiba o quadro de estado, próximo bloco liberado e bloqueados.

Depois do quadro, acrescente em no máximo 4 linhas: qual é o próximo bloco liberado, o que está travando os bloqueados, e se algum bloco chegou a 2 tentativas e precisa de decisão. Não invente informação que o script não retornou.
