# Schema de `plano/blocos.json`

Fonte de verdade do estado da execução. Só o agente `maestro` escreve aqui.

```json
{
  "projeto": "bento",
  "atualizado_em": "2026-09-02",
  "blocos": [
    {
      "id": "F0-06",
      "titulo": "Agente Triagem de Segurança (gate)",
      "fase": "F0",
      "spec": "specs/F0-06-triagem-seguranca.md",
      "complexidade": "C5",
      "modelo": "claude-opus-5",
      "agente": "arquiteto",
      "revisor_modelo": "claude-opus-5",
      "depende_de": ["F0-05"],
      "arquivos_permitidos": ["src/agents/safety/**", "tests/safety/**"],
      "criterio_aceite": [
        "npm run eval -- --suite=safety passa com zero falso negativo",
        "60+ casos de segurança no arquivo de testes",
        "red-team de 20 tentativas documentado"
      ],
      "estado": "pendente",
      "tentativas": 0,
      "bloqueado_por": null,
      "notas": []
    }
  ]
}
```

## Campos

| Campo | Obrigatório | Observação |
|---|---|---|
| `id` | sim | Único. Convenção `F<fase>-<n>` |
| `spec` | sim | Caminho do arquivo. O executor lê isto e mais nada do produto |
| `complexidade` | sim | `C1`…`C5` |
| `modelo` | sim | ID completo. É passado como `model` na invocação do agente |
| `agente` | sim | `operario` \| `implementador` \| `arquiteto` |
| `revisor_modelo` | sim | Sempre ≥ o modelo do executor |
| `depende_de` | sim | Lista de IDs. Vazia = liberado |
| `arquivos_permitidos` | sim | Globs. Escrita fora disto reprova na revisão |
| `criterio_aceite` | sim | **Em notação EARS** (ver `ears.md`). Cada item vira um teste |
| `comando_teste` | sim | O comando que prova o bloco. É a verificação objetiva de pronto |
| `orcamento_turnos` | sim | 15 para C1–C2, 30 para C3–C4, 40 para C5. Estourou = spec vaga |
| `estado` | sim | `pendente` \| `em_andamento` \| `concluido` \| `bloqueado` |
| `tentativas` | sim | Em 2, para e chama o usuário |
| `bloqueado_por` | não | Texto. Preenchido = **nunca despachar** |
| `notas` | não | Histórico de falhas e decisões |

## Bloqueio: `estado` vs `bloqueado_por`

`bloqueado_por` preenchido impede o despacho mesmo com `estado: "pendente"`. `estado: "bloqueado"` sem `bloqueado_por` é inválido — corrija antes do despacho. Use `/maestro:destravar <ID>` para limpar.

| Situação | `estado` | `bloqueado_por` | Efeito |
|---|---|---|---|
| Liberado | `pendente` | `null` | Despachável |
| Travado com motivo | `pendente` | texto | **Nunca despachar** |
| Estado inválido | `bloqueado` | `null` | Corrigir antes do despacho |
| Em execução | `em_andamento` | `null` | `/maestro:retomar` |
| Fechado | `concluido` | `null` | — |

## Layout multifase

Quando o projeto tem mais de uma fase independente, cada fase fica em sua própria subpasta:

```
plano/
  principal/blocos.json   ← fase "principal"
  beta/blocos.json        ← fase "beta"
  metricas.json           ← legado (uma fase só)
  principal/metricas.json ← multifase
```

### Regras de precedência (--fase)

1. `--fase <nome>` presente → usa `plano/<nome>/blocos.json`. Erro se não existir.
2. `--fase` ausente e `plano/blocos.json` existe → usa `plano/blocos.json` (legado, sem aviso).
3. `--fase` ausente, sem `plano/blocos.json`, exatamente uma subpasta `plano/*/blocos.json` → usa essa subpasta e imprime o caminho resolvido.
4. `--fase` ausente, sem `plano/blocos.json`, duas ou mais subpastas → erro com lista das fases e instrução para passar `--fase`.

### Dependência entre fases

`depende_de` nunca cruza fases. `"depende_de": ["outra_fase:F1-01"]` é **ERRO de validação**. A ordem entre fases é responsabilidade do dono.

### Colisão de ID

O mesmo `id` em duas fases carregadas na mesma invocação é **ERRO de validação**.

### `fase_padrao` em `maestro.config.json`

```json
{ "fase_padrao": "principal" }
```

Equivale a `--fase principal` quando `--fase` não é passado. Não é obrigatório.

## Regras invioláveis
1. Bloco **C5 nunca** recebe modelo Haiku, nem para executar, nem para revisar.
2. `revisor_modelo` é sempre igual ou superior ao `modelo`.
3. `bloqueado_por` preenchido impede o despacho, mesmo com dependências satisfeitas.
4. `tentativas >= 2` para a execução e devolve ao usuário — sem laço.
