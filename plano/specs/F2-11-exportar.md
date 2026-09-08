# F2-11 — F-EXPORTAR: `/maestro:exportar` gera `plano/RELATORIO.md`

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Revisor: claude-sonnet-5
- Depende de: F2-07 · Orçamento: 30 turnos

## 2. Objetivo
Depois deste bloco existe um documento único, legível por quem não usa Claude Code, com o plano inteiro, o status de cada bloco e as métricas. É o artefato que o dono manda para o time ou para o cliente.

## 3. Escopo
- Criar `scripts/exportar-relatorio.py` — gerador determinístico.
- Criar `commands/exportar.md` — comando que localiza e roda o script.
- Replicar os dois em `plugins/maestro/`.

## 4. Não faça
- Não gere texto novo. O relatório é uma reformatação de `blocos.json`, das specs e de `metricas.json`. Nenhuma frase de resumo escrita pelo modelo entra no arquivo. Um relatório com prosa gerada é um relatório que o dono não pode mostrar sem revisar linha a linha.
- Não consulte o git. Não estime prazo, custo em dinheiro nem percentual de conclusão que não seja contagem direta de blocos.
- Não escreva em `plano/blocos.json` nem em `plano/metricas.json`.
- Não gere HTML, PDF nem qualquer formato além de Markdown.
- Não use dependências fora da biblioteca padrão.
- Não trunque critérios de aceite.

## 5. Contrato

Invocação: `python scripts/exportar-relatorio.py [--saida <caminho>]`. Padrão da saída: `plano/RELATORIO.md`.

Estrutura do arquivo gerado:
```markdown
# <projeto> — plano de execucao
Gerado em <AAAA-MM-DD> a partir de plano/blocos.json

## Resumo
| Estado | Blocos |
|---|---|
| concluido | n |
| em_andamento | n |
| pendente | n |
| bloqueado | n |
| **total** | n |

## Blocos
### <id> — <titulo>
- Complexidade / modelo / revisor
- Estado (com motivo, se bloqueado)
- Depende de
- Comando de teste
- Critérios de aceite (lista numerada, integral)
- Trecho da spec: seções 2 (Objetivo) e 3 (Escopo), copiadas sem alteração
  (ou "spec ausente")

## Metricas          <- apenas se plano/metricas.json existir
| Bloco | Turnos | Tentativas | Veredito | Modelo efetivo |
```

Códigos de saída: `0` gerado; `1` `plano/blocos.json` ausente ou inválido.

## 6. Regras
**R1.** "Spec resumida" significa copiar literalmente as seções `## 2.` e `## 3.` do arquivo de spec. Se os cabeçalhos não forem encontrados, escreva `resumo indisponivel` — não invente resumo.
**R2.** Se o arquivo de spec não existir, escreva `spec ausente` e continue. Spec faltando não aborta o relatório.
**R3.** Ordem dos blocos: a mesma de `plano/blocos.json`. Não reordene.
**R4.** `plano/RELATORIO.md` é derivado: sobrescreva sem perguntar e sem `.bak`.
**R5.** A data vem do relógio do sistema.
**R6.** A linha de métricas de um bloco com mais de um registro usa o registro mais recente, e a coluna Tentativas mostra a contagem total de registros daquele bloco.
**R7.** Só biblioteca padrão; sem invocar binário externo.
**R8.** `commands/exportar.md` localiza o script pela skill `maestro-runtime` e, se não encontrar o script, gera o relatório lendo os arquivos diretamente, seguindo esta mesma estrutura.

## 7. Arquivos
- `scripts/exportar-relatorio.py` (criar) + cópia
- `commands/exportar.md` (criar) + cópia

`plano/RELATORIO.md` é saída em tempo de execução, não artefato deste bloco.

## 8. Dados
Todo conteúdo vem de `plano/blocos.json`, dos arquivos de spec, de `plano/metricas.json` e do relógio. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO o comando roda O SISTEMA DEVE gerar `plano/RELATORIO.md` com capa, quadro resumo por estado e uma seção por bloco.
2. QUANDO gera a seção de um bloco O SISTEMA DEVE incluir id, título, complexidade, estado, dependências e os critérios de aceite integrais.
3. ONDE `plano/metricas.json` existir O SISTEMA DEVE incluir uma seção de métricas com turnos usados sobre orçados por bloco e o total.
4. SE `plano/RELATORIO.md` já existir ENTÃO O SISTEMA DEVE sobrescrevê-lo sem perguntar.
5. O SISTEMA DEVE gerar o relatório apenas a partir de `plano/blocos.json`, dos arquivos de spec e de `plano/metricas.json`, sem consultar o git nem inventar texto.
6. SE um arquivo de spec referenciado não existir ENTÃO O SISTEMA DEVE escrever `spec ausente` naquela seção e continuar.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/exportar-relatorio.py` cria o arquivo e sai com 0.
- T2 — o relatório contém uma seção `### <id>` para cada um dos 17 blocos do plano.
- T3 — sem `metricas.json`, o relatório não contém a seção `## Metricas` e o script sai com 0.
- T4 — rodar duas vezes seguidas produz arquivos idênticos, exceto a data.
- T5 — o fonte não contém `subprocess`, `os.system` nem `git`.
- T6 — apontar o campo `spec` de um bloco para caminho inexistente: a seção diz `spec ausente` e o script sai com 0.
- T7 — borda: `blocos.json` inválido faz o script sair com 1 sem criar o arquivo.
- T8 — borda: critério de aceite longo aparece integral no relatório.
- T9 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se as specs não usarem os cabeçalhos `## 2.` e `## 3.` de forma consistente → pare e pergunte antes de inventar outra heurística de extração.
- Se o dono quiser o relatório em outro formato → pare; formato adicional é outro bloco.
