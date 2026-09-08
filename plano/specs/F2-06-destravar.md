# F2-06 — F-DESTRAVAR: `/maestro:destravar <ID>`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-sonnet-5 · Revisor: claude-sonnet-5
- Depende de: F2-02, F2-05 · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, o dono limpa um bloqueio sem abrir `plano/blocos.json` no editor. Hoje a única saída é editar JSON à mão, e edição manual do arquivo de estado é a forma mais comum de corromper o plano.

## 3. Escopo
- Criar `commands/destravar.md` e a cópia em `plugins/maestro/commands/destravar.md`.

## 4. Não faça
- Não crie um script Python. Este comando é um prompt de comando; a leitura e a escrita do JSON são feitas pelo agente com as ferramentas de arquivo.
- Não altere `tentativas`. Destravar não é uma tentativa.
- Não destrave em lote nem aceite `--todos`. Um ID por invocação.
- Não remova a nota do histórico do bloco; o comando **acrescenta** uma nota, nunca substitui a lista.
- Não altere `plano/blocos.json` antes da confirmação do usuário.

## 5. Contrato

Entrada: `$ARGUMENTS` = um ID de bloco. Vazio = listar bloqueados e perguntar.

Transição de estado, aplicada só após confirmação:
```
antes:  { "estado": <qualquer>, "bloqueado_por": "<motivo>" }
depois: { "estado": "pendente",  "bloqueado_por": null,
          "notas": [...anteriores, "<AAAA-MM-DD> destravado: <motivo removido>"] }
```
Campos que **não** mudam: `tentativas`, `spec`, `complexidade`, `modelo`, `revisor_modelo`, `depende_de`, `arquivos_permitidos`, `criterio_aceite`, `comando_teste`, `orcamento_turnos`.

## 6. Regras
**R1.** Um bloco é destravável se `bloqueado_por` está preenchido **ou** `estado == "bloqueado"`. Caso contrário, recuse.
**R2.** Antes de perguntar, exiba: id, título, estado atual, motivo do bloqueio, e as dependências ainda não concluídas. O dono precisa ver que destravar não basta se ainda faltam dependências.
**R3.** A confirmação é explícita e afirmativa. Silêncio, "ok" ambíguo ou qualquer outra coisa que não seja confirmação encerra sem escrever.
**R4.** A data da nota é a data corrente, obtida do sistema. Não a invente.
**R5.** Ao final, rode `validar-plano.py` (via skill `maestro-runtime`) e reporte o resultado.
**R6.** Se o bloco continuar não-despachável por dependências pendentes, diga isso na mensagem final. Destravar não é liberar.
**R7.** O front-matter do comando declara `argument-hint: <ID>`, no mesmo formato usado pelos comandos existentes.

## 7. Arquivos
`commands/destravar.md` (criar) e `plugins/maestro/commands/destravar.md` (criar, idêntico). Nada mais.

## 8. Dados
O motivo do bloqueio vem do campo `bloqueado_por` do bloco. A data vem do sistema. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO o comando recebe um ID cujo bloco tem `bloqueado_por` preenchido O SISTEMA DEVE exibir o motivo e pedir confirmação explícita antes de alterar o arquivo.
2. QUANDO o usuário confirma O SISTEMA DEVE gravar `bloqueado_por: null`, `estado: "pendente"` e acrescentar uma nota com a data e o motivo removido.
3. SE o bloco não tiver `bloqueado_por` nem `estado: "bloqueado"` ENTÃO O SISTEMA DEVE recusar a operação e não gravar nada.
4. SE o ID não existir em `plano/blocos.json` ENTÃO O SISTEMA DEVE listar os IDs bloqueados e não gravar nada.
5. SE o usuário não confirmar ENTÃO O SISTEMA DEVE encerrar sem escrever em `plano/blocos.json`.
6. O SISTEMA DEVE deixar `tentativas` inalterado.

## 10. Casos de teste obrigatórios
- T1 — bloco com `bloqueado_por` preenchido: o comando mostra o motivo e para para confirmar.
- T2 — após confirmar: `bloqueado_por` é `null`, `estado` é `pendente`, `notas` cresceu em exatamente 1 item contendo a data.
- T3 — bloco `pendente` com `bloqueado_por: null`: recusa, arquivo intacto (comparar hash antes/depois).
- T4 — ID `XX-99`: lista os bloqueados, arquivo intacto.
- T5 — usuário responde "não": arquivo intacto.
- T6 — `tentativas` antes e depois são iguais.
- T7 — borda: bloco com `estado: "bloqueado"` e `bloqueado_por: null` também é destravável (regra R1).
- T8 — borda: bloco destravado que ainda tem dependência pendente recebe o aviso de R6.

## 11. Pare e pergunte
- Se `plano/blocos.json` não for JSON válido → pare, reporte, não tente consertar.
- Se o motivo em `bloqueado_por` indicar credencial ou dado ainda ausente → confirme com o dono que o impedimento foi de fato resolvido antes de destravar. Destravar sem resolver só adia a falha para dentro do executor.
- Se houver mais de um bloco com o ID informado → pare; o plano está corrompido e é caso de `validar-plano.py`.
