# F2-07 — F-METRICAS: `plano/metricas.json`

## 1. Identificação
- Complexidade: C3
- Modelo: claude-sonnet-5 · Revisor: claude-opus-5
- Depende de: F2-02
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco existe um registro histórico de execução por bloco: qual modelo rodou de fato, quantos turnos custou contra o orçado, e qual commit saiu. É a base do `/maestro:status --bloco` (F2-08), do `/maestro:rollback` (F2-10) e do `/maestro:exportar` (F2-11) — sem ele, nenhum dos três tem de onde ler.

## 3. Escopo
- Criar `skills/planejar-projeto/references/schema-metricas.md` com o contrato do arquivo.
- Alterar `agents/maestro.md` para gravar um registro ao fechar cada bloco.
- Alterar `scripts/status.py` para imprimir um resumo quando o arquivo existir.
- Alterar `commands/status.md` para mencionar o resumo.
- Replicar as quatro alterações em `plugins/maestro/`.

## 4. Não faça
- Não estime tokens nem custo em dólar. O Maestro não tem acesso a esses números — `commands/custos.md` já diz isso ao usuário e essa posição não muda aqui. Métrica aqui é turnos e tentativas, não dinheiro.
- Não sobrescreva registros. O arquivo é append-only: uma reprovação seguida de aprovação produz **dois** registros, não um atualizado.
- Não faça `status.py` falhar quando `plano/metricas.json` não existir. Ausência do arquivo é o estado normal de um plano novo.
- Não coloque métricas dentro de `plano/blocos.json`. São arquivos com donos diferentes: `blocos.json` é estado corrente, `metricas.json` é histórico.
- Não implemente o comando `--bloco` aqui. Isso é F2-08.
- Não invente `turnos_usados` quando o número não for conhecido — grave `null`.

## 5. Contrato

`plano/metricas.json`:
```json
{
  "schema": 1,
  "projeto": "<copiado de blocos.json>",
  "registros": []
}
```

Cada item de `registros` tem exatamente estes 11 campos, nesta ordem:

| Campo | Tipo | Origem |
|---|---|---|
| `id` | string | `blocos.json` |
| `modelo_planejado` | string | campo `modelo` do bloco |
| `modelo_efetivo` | string | o `model` realmente passado na invocação do Agent |
| `revisor_modelo` | string | campo `revisor_modelo` do bloco |
| `turnos_orcados` | int | campo `orcamento_turnos` do bloco |
| `turnos_usados` | int \| null | contagem de rodadas do executor; `null` se desconhecido |
| `tentativas` | int | valor de `tentativas` no momento da gravação |
| `veredito` | `"aprovado"` \| `"reprovado"` | resultado do revisor |
| `commit_sha` | string \| null | SHA curto do commit do bloco; `null` se não houve commit |
| `timestamp_inicio` | string | ISO 8601 com sufixo `Z` |
| `timestamp_fim` | string | ISO 8601 com sufixo `Z` |

Resumo impresso por `status.py` quando o arquivo existe:
```
--- METRICAS ---
  blocos medidos: <n>
  turnos: <soma usados>/<soma orcados>
  reprovacoes: <contagem de veredito=reprovado>
  blocos com 2+ registros: <lista de ids>
```

## 6. Regras
**R1.** O gatilho de gravação é o passo 8 do ciclo em `agents/maestro.md` ("Registre"). Um registro é gravado tanto na aprovação quanto na reprovação, antes de o maestro reportar ao usuário.
**R2.** `modelo_efetivo` pode divergir de `modelo_planejado` quando houve escalonamento. É justamente essa divergência que a métrica existe para revelar; nunca copie um do outro.
**R3.** `commit_sha` é o SHA curto obtido do commit que o próprio maestro acabou de fazer. Em reprovação não há commit: grave `null`.
**R4.** Se `plano/metricas.json` não existir, crie com `schema: 1` e `registros: []` antes de acrescentar.
**R5.** Se o arquivo existir mas não for JSON válido, ou se `schema` for diferente de `1`: pare, reporte ao usuário, **não** sobrescreva. Fail-closed — perder histórico é pior do que não gravar.
**R6.** `status.py` lê `plano/metricas.json` somente para leitura. Ele nunca escreve.
**R7.** Blocos sem registro não aparecem no resumo e não contam no denominador de turnos.
**R8.** Soma de `turnos_usados` ignora registros com `null`, e o resumo indica quantos foram ignorados quando houver algum.

## 7. Arquivos
- `skills/planejar-projeto/references/schema-metricas.md` (criar) + cópia
- `agents/maestro.md` (editar o passo 8 do ciclo) + cópia
- `scripts/status.py` (acrescentar a função de resumo) + cópia
- `commands/status.md` (uma linha sobre o resumo) + cópia

`plano/metricas.json` não é criado por este bloco — ele é criado em tempo de execução, na primeira conclusão de bloco.

## 8. Dados
Todo valor vem de `plano/blocos.json`, do resultado do revisor, do relógio do sistema ou do git. Nenhum valor vem do modelo. `projeto` é copiado de `blocos.json`, não digitado.

## 9. Critérios de aceite (EARS)
1. QUANDO um bloco muda para `concluido` O SISTEMA DEVE acrescentar um registro em `plano/metricas.json` com os 11 campos da seção 5.
2. QUANDO um bloco é reprovado pelo revisor O SISTEMA DEVE acrescentar um registro com `veredito: "reprovado"`, em vez de sobrescrever o registro anterior.
3. SE `plano/metricas.json` não existir no momento da gravação ENTÃO O SISTEMA DEVE criá-lo com `schema: 1` e `registros: []` antes de acrescentar.
4. SE `plano/metricas.json` existir com JSON inválido ENTÃO O SISTEMA DEVE parar, reportar ao usuário e não sobrescrever o arquivo.
5. O SISTEMA DEVE gravar `timestamp_inicio` e `timestamp_fim` em ISO 8601 com sufixo `Z`.
6. SE nenhum commit foi feito para o bloco ENTÃO O SISTEMA DEVE gravar `commit_sha: null` em vez de omitir o campo.
7. ONDE `plano/metricas.json` existir O SISTEMA DEVE fazer o `status.py` imprimir um resumo com total de blocos medidos, turnos usados sobre orçados e contagem de reprovações.
8. ONDE `plano/metricas.json` não existir O SISTEMA DEVE omitir a seção de métricas sem emitir erro.
9. O SISTEMA DEVE tratar `plano/metricas.json` como append-only e nunca remover registros existentes.

## 10. Casos de teste obrigatórios
- T1 — criar um `metricas.json` com 1 registro à mão; `python scripts/status.py` imprime o bloco `--- METRICAS ---`.
- T2 — registro com `veredito: "reprovado"` aparece na contagem de reprovações.
- T3 — sem o arquivo, `python scripts/status.py` sai com 0 e não imprime a seção.
- T4 — arquivo com JSON quebrado: `status.py` reporta e sai sem alterar o arquivo (comparar hash).
- T5 — todo `timestamp_*` casa com `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`.
- T6 — registro de reprovação tem a chave `commit_sha` presente com valor `null`.
- T7 — dois registros do mesmo `id` coexistem e o id aparece em "blocos com 2+ registros".
- T8 — registro com `turnos_usados: null` não quebra a soma e é contado como ignorado.
- T9 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se `agents/maestro.md` não tiver como saber o número de turnos gastos pelo agente executor → pare e pergunte. Não estime. A resposta aceitável é gravar `null`, mas a decisão é do dono.
- Se o maestro fizer mais de um commit por bloco → pare e pergunte qual SHA registrar; a spec assume um.
- Se `plano/metricas.json` já existir com um `schema` diferente de `1` → pare; migração de schema não está no escopo deste bloco.
