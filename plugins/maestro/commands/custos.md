---
description: Panorama de custo — a distribuição planejada por modelo (Maestro) e um lembrete de onde checar o gasto real da sessão (Claude Code).
---

Rode `python3 scripts/status.py` e destaque só a parte de distribuição por modelo e o bloco de comandos nativos.

Depois, se o usuário quiser o gasto real desta sessão (não o planejado), diga explicitamente para rodar `/context` (o que está ocupando a janela agora) e `/usage` (custo e limite do plano) — o Maestro não tem acesso a esses números, eles são internos do Claude Code.

Se o usuário pedir para "ver se algum bloco específico gastou muito", lembre que isso não é rastreado automaticamente: sugira anotar em `notas` do bloco no `plano/blocos.json` o que o `/usage` mostrou antes e depois de rodar aquele bloco, para comparar.
