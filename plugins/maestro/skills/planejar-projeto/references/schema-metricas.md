# Schema de `plano/metricas.json`

Arquivo append-only de histórico de execução. Escrito pelo agente `maestro` a cada aprovação ou reprovação. Nunca sobrescreva registros anteriores.

```json
{
  "schema": 1,
  "projeto": "<copiado de blocos.json>",
  "registros": [
    {
      "id": "F1-01",
      "modelo_planejado": "claude-sonnet-5",
      "modelo_efetivo": "claude-sonnet-5",
      "revisor_modelo": "claude-opus-5",
      "turnos_orcados": 30,
      "turnos_usados": 22,
      "tentativas": 1,
      "veredito": "aprovado",
      "commit_sha": "a1b2c3d",
      "timestamp_inicio": "2026-09-08T14:00:00Z",
      "timestamp_fim": "2026-09-08T14:22:00Z"
    }
  ]
}
```

## Campos do registro

| Campo | Tipo | Origem |
|---|---|---|
| `id` | string | `blocos.json` |
| `modelo_planejado` | string | campo `modelo` do bloco |
| `modelo_efetivo` | string | `model` realmente passado na invocação do Agent |
| `revisor_modelo` | string | campo `revisor_modelo` do bloco |
| `turnos_orcados` | int | campo `orcamento_turnos` do bloco |
| `turnos_usados` | int \| null | contagem de rodadas do executor; `null` se desconhecido |
| `tentativas` | int | valor de `tentativas` no momento da gravação |
| `veredito` | `"aprovado"` \| `"reprovado"` | resultado do revisor |
| `commit_sha` | string \| null | SHA curto do commit; `null` em reprovação |
| `timestamp_inicio` | string | ISO 8601 com sufixo `Z` |
| `timestamp_fim` | string | ISO 8601 com sufixo `Z` |

## Regras

- **Append-only.** Uma reprovação seguida de aprovação produz dois registros, não um atualizado.
- **`modelo_efetivo` pode divergir de `modelo_planejado`** quando houve escalonamento — nunca copie um do outro.
- **`commit_sha: null`** em reprovação (não há commit). A chave deve estar presente com valor `null`.
- **Se o arquivo não existir:** crie com `schema: 1` e `registros: []` antes de acrescentar.
- **Se o arquivo tiver JSON inválido ou `schema != 1`:** pare, reporte ao usuário, não sobrescreva.
- **`status.py` só lê este arquivo**, nunca escreve.
