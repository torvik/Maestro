---
description: Panorama de custo — a distribuição planejada por modelo (Maestro) e um lembrete de onde checar o gasto real da sessão (Claude Code).
---

Encontre e rode o script `status.py` do Maestro. Tente nesta ordem:
1. `python3 scripts/status.py` (dentro do repo do Maestro)
2. `python3 .claude/plugins/maestro/scripts/status.py` (plugin local no projeto)
3. Resultado do comando: `find ~/.claude/plugins/cache/maestro -name "status.py" 2>/dev/null | head -1` — rode esse caminho se encontrado
4. Se nenhum existir: leia `plano/blocos.json` diretamente e calcule/exiba a distribuição por modelo (agrupe os blocos pelo campo `modelo`, classifique em tier haiku/sonnet/opus e mostre contagem e percentual de custo usando pesos haiku=1, sonnet=2, opus=5).

Destaque só a parte de distribuição por modelo e o bloco de comandos nativos.

Depois, se o usuário quiser o gasto real desta sessão (não o planejado), diga explicitamente para rodar `/context` (o que está ocupando a janela agora) e `/usage` (custo e limite do plano) — o Maestro não tem acesso a esses números, eles são internos do Claude Code.

Se o usuário pedir para "ver se algum bloco específico gastou muito", lembre que isso não é rastreado automaticamente: sugira anotar em `notas` do bloco no `plano/blocos.json` o que o `/usage` mostrou antes e depois de rodar aquele bloco, para comparar.
