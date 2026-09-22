# Complexity Engine (F5-01)

Módulo: `scripts/maestro_complexity.py` (cópia byte-a-byte em `plugins/maestro/scripts/maestro_complexity.py`).

## Propósito

Classifica um bloco de trabalho em um nível de complexidade (`C1` a `C5`) e
retorna os requisitos de execução associados. A classificação é
**desacoplada de nomes de modelos de IA**: este módulo não sabe, e não
deve saber, qual modelo executa cada nível — essa decisão pertence a
outra camada.

## API pública

```python
ComplexityError(Exception)
classify(block: dict) -> dict
requirements(level: str) -> dict
LEVELS: tuple  # ("C1", "C2", "C3", "C4", "C5")
```

### `classify(block)`

Recebe um dict de bloco (precisa ter o campo `"complexidade"`) e retorna:

```python
{
    "level": "C3",
    "requirements": {
        "reasoning": "medium",
        "context": "medium",
        "coding": "medium",
        "autonomy": "medium",
        "risk": "medium",
        "review_required": False,
        "isolation_recommended": False,
    },
    "adjustments": []
}
```

### `requirements(level)`

Retorna o dict de requisitos base (7 campos) para um nível, sem aplicar
ajustes de bloco.

## Tabela de requisitos por nível

| Nível | reasoning | context | coding | autonomy | risk | review_required | isolation_recommended |
|---|---|---|---|---|---|---|---|
| C1 | low | low | low | high | low | false | false |
| C2 | low | low | medium | high | low | false | false |
| C3 | medium | medium | medium | medium | medium | false | false |
| C4 | high | medium | high | low | high | true | false |
| C5 | high | high | high | low | high | true | true |

## Definição por nível

### C1 — Trivial
Tarefa de escopo mínimo: afeta um único arquivo ou uma área claramente delimitada. Não requer análise de impacto nem raciocínio sobre interações entre módulos. O resultado é facilmente revertido e dificilmente introduz regressão. Um humano revisaria o diff em menos de um minuto.
Exemplos: boilerplate de arquivo novo sem lógica, inserção de seed com schema já pronto, renomeação puramente mecânica de variável ou arquivo, atualização de README/CHANGELOG, adição de entrada a lista de constantes existente.

### C2 — Simples
Pequeno número de arquivos, lógica conhecida, testes simples, baixo impacto arquitetural.
Exemplos: migrations a partir de schema pronto, conversores, refactor mecânico, casos de teste listados.

### C3 — Médio
Múltiplos componentes, necessidade de análise, integração moderada, revisão recomendada.
Exemplos: nova feature pequena, integração de módulo existente, script com lógica não trivial.

### C4 — Complexo
Alterações arquiteturais, múltiplos módulos, risco relevante, maior contexto, revisão obrigatória.
Exemplos: novo contrato de API, refactor de módulo central, feature com múltiplos casos de borda.

### C5 — Crítico
Decisões estruturais, mudanças amplas, alto impacto, segurança, migrações, risco de regressão elevado, revisão independente obrigatória.
Exemplos: mudança de schema persistido, autenticação, migração de dados, decisão arquitetural irreversível.

## Significado dos campos de requirements

- **reasoning** — nível de raciocínio/profundidade de análise necessário para executar o bloco.
- **context** — quantidade de contexto (arquivos, histórico, documentação) necessária para executar com segurança.
- **coding** — nível de capacidade de geração/edição de código exigido.
- **autonomy** — grau de autonomia permitido antes de exigir checagem humana.
- **risk** — risco associado a um erro ou regressão introduzida pelo bloco.
- **review_required** — indica se o resultado exige revisão humana antes de ser aceito.
- **isolation_recommended** — indica se a execução deve ocorrer em ambiente isolado (ex.: branch/sandbox dedicado).

> Este módulo não conhece nomes de modelos de AI; a tradução requirements → modelo é responsabilidade do provider adapter.

## Ajustes opcionais

Aplicados sobre a base do nível, a partir de campos do bloco:

| Campo do bloco | Condição | Ajuste |
|---|---|---|
| `risco` | `"alto"` ou `"high"` | `risk -> "high"`, `review_required -> True` |
| `arquivos_permitidos` | lista com mais de 10 itens | `context -> "high"`, `isolation_recommended -> True` |
| `bloqueado_por` | string não vazia | registra em `adjustments`: `"bloqueado_por presente"` (não altera requirements) |

Regras:

- Ajustes nunca **rebaixam** campos (só elevam).
- **C5 é imutável**: nenhum ajuste remove `review_required=True` ou
  `isolation_recommended=True` de um bloco C5.

## Erros

- `classify({})` → `ComplexityError("campo 'complexidade' ausente")`
- `classify({"complexidade": "C6"})` → `ComplexityError("nível 'C6' inválido; esperado: C1–C5")`

## Invariantes

- **I1** — Nenhum nome de modelo (`haiku`, `sonnet`, `opus`, `gpt`, `codex`) aparece no código.
- **I2** — Funções puras: não leem/escrevem disco, não importam módulo local.
- **I3** — Para C5, `review_required` e `isolation_recommended` são sempre `True`.
- **I5** — Somente stdlib Python 3.9+ (`argparse`, `json`, `sys`).
- **I6** — Paridade byte-a-byte entre `scripts/` e `plugins/maestro/scripts/`.

## CLI

```bash
# Classificar um bloco (JSON inline)
python scripts/maestro_complexity.py --classify '{"complexidade": "C3"}'

# Mostrar a tabela de todos os níveis
python scripts/maestro_complexity.py --show

# Sem argumentos: imprime a docstring do módulo
python scripts/maestro_complexity.py
```

Códigos de saída: `0` em sucesso (incluindo `--show` e chamada sem
argumentos); `1` quando `--classify` recebe um bloco inválido
(`ComplexityError`); `2` quando `--classify` recebe um JSON malformado.
