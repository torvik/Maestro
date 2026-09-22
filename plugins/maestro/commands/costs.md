---
description: Panorama de custo — a distribuição planejada por modelo (Maestro) e um lembrete de onde checar o gasto real da sessão (Claude Code).
---

Se `$ARGUMENTS` contiver `--fase <nome>`: passe `--fase <nome>` ao script invocado.

Encontre e rode o script `status.py` do Maestro. Use a skill `maestro-runtime`: localize `status.py` com o procedimento `localizar` e invoque com o interpretador do procedimento `interpretador`. Se nenhum interpretador ou caminho existir: leia `plano/blocos.json` diretamente e calcule/exiba a distribuição por modelo (agrupe os blocos pelo campo `modelo`, classifique em tier haiku/sonnet/opus e mostre contagem e percentual de custo usando pesos haiku=1, sonnet=2, opus=5).

Destaque só a parte de distribuição por modelo e o bloco de comandos nativos.

Depois, se o usuário quiser o gasto real desta sessão (não o planejado), diga explicitamente para rodar `/context` (o que está ocupando a janela agora) e `/usage` (custo e limite do plano) — o Maestro não tem acesso a esses números, eles são internos do Claude Code.

Se o usuário pedir para "ver se algum bloco específico gastou muito", lembre que isso não é rastreado automaticamente: sugira anotar em `notas` do bloco no `plano/blocos.json` o que o `/usage` mostrou antes e depois de rodar aquele bloco, para comparar.
