# F2-12 — F-MULTIFASE (desenho): contrato de resolução do arquivo de plano

## 1. Identificação
- Complexidade: C4 (metade de desenho de um C4 quebrado em dois)
- Modelo: claude-opus-5 · Agente: `arquiteto` · Revisor: claude-opus-5
- Depende de: F2-06, F2-08, F2-09, F2-10, F2-11
- Orçamento de turnos: 30

## 2. Objetivo
Depois deste bloco existe a spec de implementação `F2-13-multifase-impl.md`, fechando como o Maestro resolve qual arquivo de plano usar quando há mais de uma fase. Nenhuma linha de comando é alterada aqui — o produto deste bloco é uma spec.

## 3. Escopo
- Escrever `plano/specs/F2-13-multifase-impl.md` completa, nas 11 seções do gabarito.
- Acrescentar a `schema-blocos.md` (e cópia) a seção que documenta o layout multifase e a forma de declarar dependência entre fases.

## 4. Não faça
- Não altere nenhum comando, script ou agente. Este bloco produz spec, não implementação.
- Não proponha migração automática de `plano/blocos.json` para `plano/fase1/blocos.json`. Planos existentes na v1.2 têm que continuar funcionando sem que ninguém mova arquivo. Quebrar isso invalida o plano de todo usuário instalado.
- Não introduza um arquivo de índice de fases (`plano/fases.json` ou equivalente) sem antes esgotar a resolução por convenção de diretório. Um arquivo de índice é mais um estado para dessincronizar.
- Não deixe "o comportamento padrão será decidido na implementação". Se ficar em aberto, o Sonnet vai chutar.

## 5. Contrato
Produto: `plano/specs/F2-13-multifase-impl.md`, com as 11 seções de `references/anatomia-da-spec.md`, critérios em EARS, seções "Não faça" e "Pare e pergunte" preenchidas com casos concretos.

Layout alvo:
```
plano/blocos.json            <- layout legado, uma fase, continua valido
plano/<fase>/blocos.json     <- layout multifase
plano/<fase>/specs/
plano/<fase>/metricas.json
```

## 6. Regras — decisões que a spec produzida tem de fechar

**R1 — precedência.** No máximo 4 regras numeradas, mutuamente exclusivas, cobrindo: `--fase` presente; `--fase` ausente com `plano/blocos.json` existente; `--fase` ausente com exatamente uma fase; `--fase` ausente com mais de uma fase.

**R2 — compatibilidade.** `plano/blocos.json` existente continua funcionando sem argumento e sem migração. Este é um requisito duro, não uma preferência.

**R3 — coexistência.** Defina o que acontece quando `plano/blocos.json` **e** `plano/<fase>/blocos.json` existem ao mesmo tempo. Escolha um comportamento e justifique em uma linha.

**R4 — dependência entre fases.** Defina a sintaxe de `depende_de` apontando para bloco de outra fase e como `validar-plano.py` a resolve. Se a decisão for proibir dependência entre fases, diga isso explicitamente e diga o que o validador reporta.

**R5 — colisão de id.** Mesmo id em duas fases é **erro de validação**, nunca resolução silenciosa por ordem de leitura.

**R6 — inventário.** Liste nominalmente cada arquivo que a implementação vai tocar. Após F2-06, F2-08, F2-09, F2-10 e F2-11, `commands/` terá 12 arquivos. Derive a lista de `commands/` no momento da execução, não do texto desta spec.

**R7 — métricas por fase.** Defina onde vive `metricas.json` no layout multifase e o que acontece com um `plano/metricas.json` legado.

**R8 — variável de ambiente.** `validar-plano.py` já lê `MAESTRO_PLANO`. Defina como `--fase` e `MAESTRO_PLANO` interagem, incluindo qual vence.

**R9 — orçamento.** A spec produzida declara `orcamento_turnos: 30` e `arquivos_permitidos` fechados. Se você concluir que a implementação não cabe em 30 turnos, quebre em dois blocos e diga isso no relatório em vez de inflar o orçamento.

## 7. Arquivos
- `plano/specs/F2-13-multifase-impl.md` (criar; substitui o placeholder existente)
- `skills/planejar-projeto/references/schema-blocos.md` + cópia em `plugins/maestro/`

## 8. Dados
A lista de comandos vem de `commands/` no momento da execução. O comportamento atual de `MAESTRO_PLANO` vem de `scripts/validar-plano.py`. Nada vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE produzir `plano/specs/F2-13-multifase-impl.md` com as 11 seções do gabarito preenchidas.
2. O SISTEMA DEVE definir a precedência de resolução em no máximo 4 regras numeradas e mutuamente exclusivas.
3. O SISTEMA DEVE definir o comportamento para `plano/blocos.json` legado, garantindo que planos da v1.2 funcionem sem migração.
4. O SISTEMA DEVE definir como dependências entre blocos de fases diferentes são declaradas e validadas.
5. SE duas fases declararem o mesmo id ENTÃO a spec DEVE definir o comportamento como erro de validação, e não como resolução silenciosa.
6. O SISTEMA DEVE listar nominalmente todos os arquivos de comando que a implementação precisa alterar.
7. O SISTEMA DEVE definir o comportamento de `--fase` ausente quando existe mais de uma fase.

## 10. Casos de teste obrigatórios
- T1 — o arquivo produzido contém os 11 cabeçalhos numerados do gabarito.
- T2 — a seção 6 contém no máximo 4 regras de precedência e elas cobrem os 4 casos de R1 sem sobreposição.
- T3 — a spec contém um critério EARS afirmando compatibilidade com `plano/blocos.json` sem argumento.
- T4 — a spec contém a sintaxe de dependência entre fases, ou a proibição explícita.
- T5 — a spec contém um critério EARS de erro para id duplicado entre fases.
- T6 — a lista da seção 7 da spec produzida contém todo arquivo de `commands/*.md` existente.
- T7 — a spec define o comportamento de `--fase` ausente com múltiplas fases.
- T8 — `python scripts/validar-plano.py` sai com 0.

## 11. Pare e pergunte
- Se a compatibilidade com o layout legado exigir uma escolha que o dono precisa fazer (por exemplo, tratar `plano/blocos.json` como fase implícita chamada `principal`) → pare e pergunte. Nome de fase padrão é decisão do dono.
- Se `--fase` colidir com o parsing posicional já usado por `status.py --bloco` → pare e pergunte antes de trocar o parser por `argparse` em todos os scripts.
- Se o inventário derivado de `commands/` divergir dos 12 arquivos esperados → pare e reporte antes de escrever a spec; significa que um bloco anterior não fechou como planejado.
