---
description: Limpa o bloqueio de um bloco sem editar plano/blocos.json manualmente. Exige confirmação explícita antes de gravar.
argument-hint: <ID>
---

Se `$ARGUMENTS` contiver `--fase <nome>`: use `plano/<nome>/blocos.json` em vez de `plano/blocos.json`. Encerre com erro se o arquivo não existir.

Leia `plano/blocos.json` (ou o caminho resolvido acima).

Se `$ARGUMENTS` estiver vazio: liste todos os blocos com `bloqueado_por` preenchido ou `estado: "bloqueado"` e pergunte qual ID o usuário quer destravar. Pare aqui.

Se `$ARGUMENTS` tiver um ID:

1. **Encontre o bloco.** Se o ID não existir, liste os blocos bloqueados e encerre sem gravar.

2. **Verifique se é destravável.** O bloco é destravável se `bloqueado_por` está preenchido **ou** `estado == "bloqueado"`. Se nenhuma das duas condições for verdadeira, informe que o bloco não está bloqueado e encerre sem gravar.

3. **Exiba o contexto:**
   ```
   ID:       <id>
   Título:   <titulo>
   Estado:   <estado>
   Bloqueio: <bloqueado_por ou "(estado: bloqueado)">
   Depende de ainda não concluídos: <lista ou "nenhum">
   ```
   Se houver dependências pendentes, avise que destravar não basta — o bloco só será despachado quando elas concluírem.

4. **Peça confirmação explícita.** Qualquer resposta que não seja afirmativa inequívoca encerra sem gravar.

5. **Se confirmado, atualize `plano/blocos.json`:**
   - `estado` → `"pendente"`
   - `bloqueado_por` → `null`
   - `notas` → acrescente `"<AAAA-MM-DD> destravado: <motivo que foi removido>"` (data do sistema, não inventada)
   - **Não altere** `tentativas`, `spec`, `complexidade`, `modelo`, `revisor_modelo`, `depende_de`, `arquivos_permitidos`, `criterio_aceite`, `comando_teste`, `orcamento_turnos`.

6. **Rode `validar-plano.py`** via skill `maestro-runtime` e reporte o resultado.

7. Se o bloco continuar não-despachável por dependências pendentes, diga isso na mensagem final. Destravar não é o mesmo que liberar.

## Nunca
- Nunca grave antes da confirmação.
- Nunca destrave mais de um bloco por invocação.
- Nunca altere `tentativas`.
- Nunca substitua a lista `notas` — sempre acrescente.
