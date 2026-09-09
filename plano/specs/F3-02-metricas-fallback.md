# F3-02 — B-METRICAS-FALLBACK: `metricas.json` corrompido não derruba o `status.py`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Agente: operario · Revisor: claude-sonnet-5
- Depende de: F3-01 · Orçamento: 15 turnos
- Comando de teste: `python scripts/status.py && python scripts/exportar-relatorio.py && python scripts/verificar-repo.py --check paridade`

## 2. Objetivo
Depois deste bloco, um `plano/metricas.json` corrompido produz um aviso não fatal e o quadro do plano continua sendo impresso. Hoje há dois furos: o `try` de `resumo_metricas` cobre só o `json.load`, então um JSON válido com registro sem a chave `id` levanta `KeyError` e derruba o comando inteiro; e `detalhe_bloco` engole a falha em silêncio, deixando o dono sem saber que o arquivo está quebrado.

## 3. Escopo
- Blindagem da leitura de métricas em `resumo_metricas` e em `detalhe_bloco`, dentro de `scripts/status.py`.
- Aviso não fatal na leitura de métricas de `scripts/exportar-relatorio.py`, que hoje falha em silêncio.
- Réplica byte-a-byte das duas alterações em `plugins/maestro/scripts/`.

## 4. Não faça
- Não reescreva, não mova, não trunque e não apague `plano/metricas.json`. O arquivo é append-only e propriedade do agente `maestro`; recuperar dado corrompido é decisão do dono, nunca do script de leitura.
- Não crie backup automático nem arquivo `.bak` do `metricas.json`. Isso mascara o problema e multiplica arquivos que ninguém limpa.
- Não altere o formato do bloco `--- METRICAS ---` quando o arquivo está íntegro. A saída em caminho feliz permanece idêntica byte a byte.
- Não faça o `status.py` sair com código diferente de 0 por causa de métrica corrompida. Métrica é acessório; o quadro do plano é o produto.
- Não use `except:` nu nem `except Exception: pass`. Todo caminho de exceção termina imprimindo um aviso identificável.
- Não tente inferir, completar ou estimar valor de campo ausente. Registro sem os campos exigidos é descartado, não remendado.

## 5. Contrato

Três classes de defeito, todas tratadas como não fatais:

| Defeito | Detecção | Resposta |
|---|---|---|
| JSON sintaticamente inválido | exceção em `json.load` | aviso e nenhuma seção de métricas |
| `schema` diferente de 1 | comparação do campo | aviso e nenhuma seção de métricas |
| Registro individual malformado | campo `id` ausente, `registros` não é lista, ou registro não é objeto | registro descartado, demais processados |

Formato do aviso, em uma linha, no fluxo de saída padrão do `status.py`:

```
  AVISO: metricas.json ignorado — <motivo curto>. O quadro do plano nao foi afetado.
```

Em `exportar-relatorio.py` o aviso vai para `stderr` e o relatório é gerado sem a coluna de métricas.

Quando `registros` contém itens válidos e itens malformados, a linha adicional é:

```
  AVISO: <n> registro(s) de metricas.json descartado(s) por falta do campo 'id'.
```

Códigos de saída: `status.py` sem argumentos → 0; `status.py --bloco <ID>` → 0 se o bloco existe; `exportar-relatorio.py` → 0 se o relatório foi gravado.

## 6. Regras
**R1.** O bloco `try` deve envolver toda a leitura e toda a agregação dos registros, não apenas a chamada de `json.load`.
**R2.** Todo acesso a campo de registro usa `.get()` com valor padrão. Indexação direta por colchete em registro de métrica fica proibida nos três arquivos.
**R3.** Um registro sem `id` é descartado e contado. Um registro sem `turnos_usados` continua sendo processado, como já acontece hoje.
**R4.** `detalhe_bloco` passa a imprimir o mesmo aviso de uma linha em vez de seguir em silêncio.
**R5.** Se `metricas.json` não existir, nada muda e nenhum aviso é impresso. Ausência não é defeito.
**R6.** Se `registros` estiver presente mas não for uma lista, o arquivo inteiro é tratado como corrompido.
**R7.** Só biblioteca padrão do Python.

## 7. Arquivos
`scripts/status.py`, `scripts/exportar-relatorio.py` e as duas cópias correspondentes em `plugins/maestro/scripts/`.

## 8. Dados
Todo valor vem de `plano/metricas.json` e `plano/blocos.json`. Nenhum turno, veredito ou timestamp vem do modelo.

## 9. Critérios de aceite (EARS)
1. SE `plano/metricas.json` contém JSON sintaticamente inválido ENTÃO O SISTEMA DEVE imprimir um aviso de uma linha, imprimir o quadro do plano por inteiro e sair com código 0.
2. SE `plano/metricas.json` é um JSON válido cujo campo `registros` contém um objeto sem a chave `id` ENTÃO O SISTEMA DEVE descartar esse registro, processar os demais e sair com código 0.
3. SE `plano/metricas.json` declara `schema` diferente de 1 ENTÃO O SISTEMA DEVE imprimir aviso e omitir a seção de métricas.
4. QUANDO `status.py --bloco <ID>` encontra `metricas.json` corrompido O SISTEMA DEVE imprimir o aviso em vez de seguir em silêncio.
5. QUANDO `exportar-relatorio.py` encontra `metricas.json` corrompido O SISTEMA DEVE gravar `plano/RELATORIO.md` sem a seção de métricas e escrever o aviso em `stderr`.
6. SE `plano/metricas.json` não existe ENTÃO O SISTEMA DEVE omitir a seção de métricas sem imprimir aviso.
7. QUANDO `plano/metricas.json` está íntegro O SISTEMA DEVE produzir a mesma saída que produzia antes deste bloco.
8. O SISTEMA DEVE deixar `plano/metricas.json` inalterado em todos os cenários acima.
9. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `metricas.json` com o conteúdo `{` : `status.py` sai 0 e a saída contém `AVISO: metricas.json ignorado`.
- T2 — `metricas.json` com `{"schema":1,"registros":[{"veredito":"aprovado"}]}` : `status.py` sai 0 e reporta 1 registro descartado.
- T3 — `metricas.json` com `{"schema":2,"registros":[]}` : aviso impresso, nenhuma seção `--- METRICAS ---`.
- T4 — `metricas.json` com `{"schema":1,"registros":{}}` : tratado como corrompido, `status.py` sai 0.
- T5 — mesmo arquivo corrompido de T1 com `status.py --bloco <ID de bloco existente>`: sai 0 e imprime o aviso.
- T6 — mesmo arquivo corrompido de T1 com `exportar-relatorio.py`: sai 0, gera `plano/RELATORIO.md`, aviso em `stderr`.
- T7 — sem `metricas.json` no disco: a saída de `status.py` não contém a string `AVISO`.
- T8 — hash do `metricas.json` antes e depois de cada teste acima é idêntico.
- T9 — borda: `metricas.json` com registro que é uma string em vez de objeto: descartado, sem exceção.
- T10 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se você concluir que precisa gravar em `plano/metricas.json` para reparar o arquivo → pare, porque reparo de dado histórico é decisão do dono e não cabe num script de leitura.
- Se a saída em caminho feliz mudar em qualquer caractere durante a refatoração → pare e pergunte antes de continuar, porque o critério 7 é binário.
- Se o repositório tiver um `plano/metricas.json` real no momento do teste → pare e pergunte onde criar o arquivo de teste, em vez de sobrescrever o arquivo real.
