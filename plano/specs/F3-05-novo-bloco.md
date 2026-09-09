# F3-05 — F-SPEC-TEMPLATE: `scripts/novo-bloco.py`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Agente: operario · Revisor: claude-sonnet-5
- Depende de: nenhum · Orçamento: 15 turnos
- Comando de teste: `python scripts/novo-bloco.py --auto-teste && python scripts/verificar-repo.py --check paridade`

## 2. Objetivo
Depois deste bloco, o arquiteto começa uma spec nova a partir de um esqueleto com as onze seções na ordem e nos títulos canônicos, em vez de copiar à mão o gabarito de `anatomia-da-spec.md`. O esqueleto sai com marcadores de preenchimento que o linter do bloco F3-06 reconhece e recusa.

## 3. Escopo
- Criação de `scripts/novo-bloco.py`, que grava um arquivo de spec em branco a partir de um ID e um título.
- Definição do formato do marcador de preenchimento, que é contrato de entrada do bloco F3-06.
- Réplica byte-a-byte em `plugins/maestro/scripts/novo-bloco.py`.

## 4. Não faça
- Não escreva em `plano/blocos.json`. Este script só cria o arquivo de spec. Registrar o bloco no plano é trabalho do `/maestro:planejar` e da skill `maestro-setup`.
- Não copie a spec gerada para `plugins/maestro/`. O diretório `plano/` não é espelhado; a paridade cobre apenas `commands/`, `agents/`, `skills/` e `scripts/`. O que precisa de cópia é o script, não o que ele gera.
- Não preencha nenhuma seção com conteúdo plausível. Um esqueleto com texto inventado é pior que um esqueleto vazio, porque o executor seguinte acredita nele.
- Não sobrescreva arquivo existente sem `--forcar`. Uma spec já escrita perdida por colisão de nome custa mais que o script inteiro.
- Não use `argparse` com subcomandos. O parsing posicional simples é o estilo dos scripts deste repositório.
- Não invente títulos de seção. Os onze títulos da seção 5 são literais e qualquer desvio quebra o linter do bloco F3-06.

## 5. Contrato

**Invocação:** `python scripts/novo-bloco.py <ID> <titulo> [--saida <caminho>] [--forcar]`

**Caminho de saída padrão:** `plano/specs/<ID>-<slug>.md`, onde `<slug>` é o título em minúsculas, com acentos reduzidos a ASCII, todo caractere fora de `[a-z0-9]` trocado por hífen, hifens consecutivos colapsados em um, hifens das pontas removidos e o resultado truncado em 40 caracteres.

**Os onze títulos de seção, literais e nesta ordem:**

```
## 1. Identificação
## 2. Objetivo
## 3. Escopo
## 4. Não faça
## 5. Contrato
## 6. Regras
## 7. Arquivos
## 8. Dados
## 9. Critérios de aceite (EARS)
## 10. Casos de teste obrigatórios
## 11. Pare e pergunte
```

**Marcador de preenchimento:** `<<PREENCHER: descrição do que falta>>`. É este literal, com dois sinais de menor, a palavra `PREENCHER` em maiúsculas, dois-pontos, espaço, texto livre e dois sinais de maior. O bloco F3-06 recusa qualquer spec que ainda contenha a subcadeia `<<PREENCHER:`.

**Cabeçalho gerado:** `# <ID> — <titulo>`, com travessão, seguido de linha em branco.

**Seção 1 gerada:** os campos `Complexidade`, `Modelo`, `Agente`, `Revisor`, `Depende de`, `Orçamento` e `Comando de teste` presentes, cada um com um marcador de preenchimento próprio. `ID` e título já vêm do argumento.

**Seções 3, 4, 6, 9, 10 e 11 geradas:** cada uma com três itens de lista, cada item um marcador de preenchimento distinto.

**Códigos de saída:** `0` arquivo criado, com o caminho impresso em uma linha; `1` arquivo já existe e `--forcar` ausente; `2` argumentos ausentes ou inválidos, com a linha de uso impressa; `3` falha de escrita.

**Modo de autoteste:** `python scripts/novo-bloco.py --auto-teste` gera um esqueleto num arquivo temporário, confere que os onze títulos aparecem na ordem, apaga o arquivo e sai com 0. Serve como comando de teste do bloco sem sujar `plano/specs/`.

## 6. Regras
**R1.** O arquivo gerado é UTF-8 com quebra de linha `\n`, sem BOM.
**R2.** O ID recebido é usado literalmente, sem normalização de caixa e sem validação de formato. Convenção de ID é assunto do plano, não do gerador.
**R3.** Se o diretório de saída não existir, o script o cria. Diferente do lock, aqui criar diretório é inofensivo e esperado.
**R4.** Se o slug resultar vazio, o caminho padrão vira `plano/specs/<ID>.md`.
**R5.** Todo marcador de preenchimento tem descrição própria e específica da seção. Três marcadores idênticos numa seção reprovam na revisão.
**R6.** O texto entre os títulos não contém instrução genérica de qualidade. O gabarito `anatomia-da-spec.md` proíbe isso e o esqueleto segue a mesma regra.
**R7.** Só biblioteca padrão do Python 3.9 ou superior.

## 7. Arquivos
`scripts/novo-bloco.py` e `plugins/maestro/scripts/novo-bloco.py`. Nenhum outro arquivo é criado ou alterado por este bloco.

## 8. Dados
O ID e o título vêm dos argumentos de linha de comando. Os títulos de seção vêm da seção 5 desta spec. Nenhum conteúdo de spec vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `novo-bloco.py <ID> <titulo>` roda O SISTEMA DEVE gravar um arquivo em `plano/specs/<ID>-<slug>.md` contendo os onze títulos de seção da seção 5, na ordem, e sair com código 0.
2. QUANDO o arquivo é gerado O SISTEMA DEVE incluir a linha de cabeçalho `# <ID> — <titulo>` como primeira linha.
3. SE o arquivo de saída já existe e `--forcar` não foi passado ENTÃO O SISTEMA DEVE sair com código 1 sem alterar o arquivo.
4. QUANDO `--forcar` é passado sobre um arquivo existente O SISTEMA DEVE sobrescrever e sair com código 0.
5. SE o ID ou o título não forem informados ENTÃO O SISTEMA DEVE imprimir a linha de uso e sair com código 2.
6. QUANDO `--saida <caminho>` é informado O SISTEMA DEVE gravar nesse caminho em vez do caminho padrão.
7. O SISTEMA DEVE incluir pelo menos um marcador `<<PREENCHER:` em cada uma das onze seções do arquivo gerado.
8. O SISTEMA DEVE deixar `plano/blocos.json` inalterado em todas as invocações.
9. QUANDO `--auto-teste` roda O SISTEMA DEVE verificar a presença e a ordem dos onze títulos, apagar o arquivo temporário e sair com código 0.
10. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `novo-bloco.py F9-01 "Titulo de teste"`: cria `plano/specs/F9-01-titulo-de-teste.md` e sai 0.
- T2 — o arquivo de T1 contém as onze linhas de título, na ordem, conferidas uma a uma.
- T3 — a primeira linha do arquivo de T1 é `# F9-01 — Titulo de teste`.
- T4 — repetir T1 sem `--forcar`: sai 1 e o conteúdo do arquivo não muda.
- T5 — repetir T1 com `--forcar`: sai 0.
- T6 — `novo-bloco.py F9-02`: sai 2 e imprime a linha de uso.
- T7 — `novo-bloco.py F9-03 "Acentuação e Çedilha"` gera slug `acentuacao-e-cedilha`.
- T8 — `novo-bloco.py F9-04 "!!!"` gera `plano/specs/F9-04.md`, conforme a regra R4.
- T9 — cada uma das onze seções do arquivo de T1 contém a subcadeia `<<PREENCHER:`.
- T10 — hash de `plano/blocos.json` antes e depois de todos os testes é idêntico.
- T11 — apagar os arquivos `F9-*` criados nos testes ao final; `git status` não lista nenhum resíduo.
- T12 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se você concluir que a spec gerada também deve ser copiada para dentro de `plugins/maestro/` → pare, porque a seção 4 diz o contrário e a paridade não cobre `plano/`.
- Se o dono pedir que o script registre o bloco em `plano/blocos.json` → pare e trate como bloco novo, porque muda o contrato e a verificação deste.
- Se algum dos onze títulos causar erro de codificação no Windows → pare e reporte, em vez de remover os acentos dos títulos.
