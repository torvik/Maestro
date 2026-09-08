# F2-08 — F-STATUS-BLOCO: `/maestro:status --bloco <ID>`

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Revisor: claude-sonnet-5
- Depende de: F2-07 · Orçamento: 30 turnos

## 2. Objetivo
Depois deste bloco o dono vê tudo sobre um bloco em uma tela, sem abrir o JSON nem a spec. Hoje `status.py` só imprime o quadro geral, que trunca o título em 44 caracteres e não mostra critério, arquivos permitidos nem histórico.

## 3. Escopo
- Acrescentar o modo `--bloco <ID>` a `scripts/status.py`.
- Atualizar `commands/status.md` para repassar o argumento.
- Replicar as duas alterações em `plugins/maestro/`.

## 4. Não faça
- Não altere a saída do `status.py` sem argumentos. Ela é consumida por `/maestro:status`, `/maestro:custos` e pela skill `maestro-setup`; mudá-la quebra os três.
- Não leia o conteúdo do arquivo de spec para resumi-lo. Imprima o **caminho** da spec. Resumo de spec é F2-11.
- Não escreva em `plano/blocos.json` nem em `plano/metricas.json`. Este modo é somente leitura.
- Não use `argparse` com subcomandos; o parsing atual é posicional e simples — mantenha o estilo do arquivo.
- Não invente métricas quando não houver registro.

## 5. Contrato

Invocação: `python scripts/status.py --bloco <ID>`

Saída, nesta ordem, uma seção por grupo:
```
=== <id> — <titulo completo> ===
  estado           <estado>[  <- TRAVADO: <motivo>]
  complexidade     <C?>   agente <agente>
  modelo           <modelo>   revisor <revisor_modelo>
  tentativas       <n> de <max>
  orcamento        <orcamento_turnos> turnos
  spec             <caminho>[  (AUSENTE)]
  comando_teste    <comando>

--- DEPENDENCIAS ---
  <id> <estado>            (uma por linha; "nenhuma" se vazio)

--- ARQUIVOS PERMITIDOS ---
  <glob>                   (um por linha)

--- CRITERIOS DE ACEITE ---
  1. <texto>               (numerados, integrais, sem truncar)

--- NOTAS ---
  <texto>                  (uma por linha; "nenhuma" se vazio)

--- METRICAS ---             (apenas se houver registro em metricas.json)
  <timestamp_fim>  <veredito>  turnos <usados>/<orcados>  modelo <modelo_efetivo>  commit <sha>
```

Códigos de saída: `0` bloco encontrado e impresso; `1` ID inexistente.

## 6. Regras
**R1.** O modo `--bloco` substitui o quadro geral; nunca imprime os dois.
**R2.** Nenhum campo é truncado neste modo. O truncamento em 44 caracteres existe só no quadro geral.
**R3.** O estado de cada dependência é lido do próprio `blocos.json`, não assumido.
**R4.** Se a spec declarada não existir no disco, imprima o caminho seguido de `(AUSENTE)`. Não é erro de saída, é informação.
**R5.** Se houver mais de um registro do bloco em `metricas.json`, imprima todos, em ordem cronológica de `timestamp_fim`.
**R6.** Se `bloqueado_por` estiver preenchido, além do destaque na linha `estado`, acrescente ao final uma linha sugerindo `/maestro:destravar <ID>`.
**R7.** `<max>` em `tentativas` vem de `max_tentativas` do `maestro.config.json` se o arquivo existir; caso contrário use `2`.
**R8.** Só a biblioteca padrão, como no resto do `status.py`.

## 7. Arquivos
`scripts/status.py`, `commands/status.md` e as duas cópias em `plugins/maestro/`.

## 8. Dados
Todo valor vem de `plano/blocos.json`, `plano/metricas.json` e `maestro.config.json`. Nada vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `status.py` recebe `--bloco <ID>` O SISTEMA DEVE imprimir id, título, complexidade, estado, modelo, revisor, caminho da spec, comando de teste, tentativas, orçamento, dependências com o estado de cada uma, arquivos permitidos, critérios numerados e notas.
2. QUANDO `status.py` recebe `--bloco <ID>` O SISTEMA DEVE imprimir o quadro do bloco e não o quadro geral.
3. SE o ID não existir ENTÃO O SISTEMA DEVE imprimir `bloco nao encontrado` seguido dos IDs válidos e sair com código 1.
4. ONDE existir registro do bloco em `plano/metricas.json` O SISTEMA DEVE imprimir turnos usados sobre orçados, veredito e modelo efetivo de cada registro.
5. SE o bloco tiver `bloqueado_por` preenchido ENTÃO O SISTEMA DEVE imprimir o motivo em destaque e sugerir `/maestro:destravar`.
6. O SISTEMA DEVE manter o comportamento atual de `status.py` sem argumentos inalterado.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/status.py --bloco F2-01` imprime as 7 seções e sai com 0.
- T2 — a saída de `--bloco` não contém a string `--- PROXIMO ---`.
- T3 — `--bloco XX-99` imprime `bloco nao encontrado` e sai com 1.
- T4 — com `metricas.json` contendo 2 registros de F2-01, ambos aparecem em ordem cronológica.
- T5 — bloco com `bloqueado_por` preenchido: a saída contém `/maestro:destravar`.
- T6 — a saída de `python scripts/status.py` sem argumentos é byte-a-byte igual à de antes do bloco (capturar antes de começar).
- T7 — borda: critério de aceite com mais de 44 caracteres aparece integral.
- T8 — borda: bloco com `depende_de: []` imprime `nenhuma`.
- T9 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se `maestro.config.json` não existir e você precisar de `max_tentativas` → use `2` conforme R7; só pare se R7 conflitar com algo no repositório.
- Se preservar a saída atual de `status.py` exigir duplicar mais de 30 linhas de código → pare e pergunte antes de refatorar a função existente.
