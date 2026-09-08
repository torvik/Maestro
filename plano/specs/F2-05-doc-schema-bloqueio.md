# F2-05 — D-SCHEMA: `estado: "bloqueado"` versus `bloqueado_por`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Revisor: claude-sonnet-5
- Depende de: nenhum · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, `schema-blocos.md` explica a diferença entre o estado `bloqueado` e o campo `bloqueado_por`. Hoje os dois existem, o `status.py` trata cada um de um jeito, e nada documenta quando usar qual — o que faz o `/maestro:destravar` (F2-06) não ter semântica definida.

## 3. Escopo
- Acrescentar uma seção a `skills/planejar-projeto/references/schema-blocos.md`.
- Replicar em `plugins/maestro/skills/planejar-projeto/references/schema-blocos.md`.

## 4. Não faça
- Não altere a tabela de campos existente nem as "Regras invioláveis" numeradas — outros arquivos citam esses números.
- Não invente um terceiro mecanismo de bloqueio nem um campo novo.
- Não altere `status.py` para mudar o comportamento. Este bloco só documenta o que já existe.

## 5. Contrato
Semântica a documentar, derivada do comportamento atual de `scripts/status.py` e de `agents/maestro.md`:

| Situação | `estado` | `bloqueado_por` | Efeito |
|---|---|---|---|
| Liberado | `pendente` | `null` | Despachável se dependências concluídas |
| Travado por decisão do dono | `pendente` | texto do motivo | **Nunca despachar**, mesmo com dependências ok |
| Travado sem motivo registrado | `bloqueado` | `null` | Estado inválido — corrigir antes do despacho |
| Em execução | `em_andamento` | `null` | `/maestro:retomar` |
| Fechado | `concluido` | `null` | — |

## 6. Regras
**R1.** `bloqueado_por` é o mecanismo preferido: ele carrega o motivo. `estado: "bloqueado"` sem `bloqueado_por` é sinal de plano mal preenchido.
**R2.** A seção declara explicitamente que `bloqueado_por` preenchido impede o despacho mesmo com `estado: "pendente"`.
**R3.** A seção aponta `/maestro:destravar` como a forma de limpar o bloqueio.
**R4.** Máximo de 15 linhas somadas. Documento de referência longo é documento não lido.

## 7. Arquivos
`skills/planejar-projeto/references/schema-blocos.md` e a cópia em `plugins/maestro/`.

## 8. Dados
Nenhum valor de negócio. A semântica vem de `scripts/status.py` e `agents/maestro.md` deste repositório.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE documentar uma seção que distingue `estado: "bloqueado"` de `bloqueado_por` preenchido, com uma frase de quando usar cada um.
2. O SISTEMA DEVE declarar que `bloqueado_por` preenchido impede o despacho mesmo com `estado: "pendente"`.
3. O SISTEMA DEVE declarar que `estado: "bloqueado"` sem `bloqueado_por` é inválido e deve ser corrigido antes do despacho.
4. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — o arquivo contém um cabeçalho de seção citando ambos os termos.
- T2 — o texto contém a afirmação sobre despacho impedido com `estado: "pendente"`.
- T3 — o texto marca `bloqueado` sem motivo como inválido.
- T4 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T5 — borda: a numeração das "Regras invioláveis" existentes permanece 1 a 4.

## 11. Pare e pergunte
- Se `status.py` e `maestro.md` tratarem `estado: "bloqueado"` de formas incompatíveis entre si → pare e pergunte qual é o comportamento pretendido; não documente uma média dos dois.
