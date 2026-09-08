# F2-16 — D-INSTALACAO: lista completa de comandos em `INSTALACAO-USUARIO.md`

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Revisor: claude-sonnet-5
- Depende de: F2-06, F2-08, F2-09, F2-10, F2-11 · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, `INSTALACAO-USUARIO.md` lista todos os comandos que o plugin realmente instala, com uma linha de descrição cada. Hoje o documento fala em "cinco comandos" e o plugin já tem mais que isso.

## 3. Escopo
- Substituir a contagem e a lista de comandos em `INSTALACAO-USUARIO.md`.
- Replicar em `plugins/maestro/INSTALACAO-USUARIO.md`.

## 4. Não faça
- Não escreva o número de comandos a partir do enunciado que originou este bloco. **Derive de `commands/`** rodando `ls commands/*.md` no momento da execução. O pedido original dizia "de cinco para oito", mas este bloco roda depois de quatro comandos novos entrarem; o número correto é o que estiver no disco.
- Não descreva um comando que você não conseguiu ler. Abra cada `commands/<nome>.md` e derive a descrição da primeira frase do arquivo.
- Não altere as seções de instalação, de solução de problemas nem de perguntas rápidas.
- Não crie um comando novo nem altere `commands/`.

## 5. Contrato
Formato de cada item da lista:
```
- `/maestro:<nome>` — <uma linha, derivada da primeira frase de commands/<nome>.md>
```
A lista é ordenada por fluxo de uso: primeiro os de operação (`setup`, `status`, `proxima`), depois os de planejamento, depois os de correção.

## 6. Regras
**R1.** Contagem por extenso no texto (`doze comandos`) igual ao número de arquivos em `commands/`.
**R2.** Um item por arquivo em `commands/`, sem exceção e sem item extra.
**R3.** A descrição sai do próprio arquivo do comando. Não invente.
**R4.** Onde o documento hoje diz "cinco comandos", troque; procure a string, não confie em número de linha.
**R5.** Alteração replicada byte-a-byte em `plugins/maestro/`.

## 7. Arquivos
`INSTALACAO-USUARIO.md` e `plugins/maestro/INSTALACAO-USUARIO.md`.

## 8. Dados
A lista e a contagem vêm de `commands/`. As descrições vêm do conteúdo de cada arquivo de comando. Nenhum valor vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE listar um item por arquivo existente em `commands/`, com o nome do comando e uma linha de descrição.
2. O SISTEMA DEVE declarar a quantidade de comandos por extenso, igual ao número de arquivos em `commands/`.
3. QUANDO a verificação `comandos-documentados` roda O SISTEMA DEVE reportar zero divergências entre a lista do documento e o conteúdo de `commands/`.
4. QUANDO a verificação `paridade` roda O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/verificar-repo.py --check comandos-documentados` sai com 0.
- T2 — a contagem por extenso no texto bate com `ls commands/*.md | wc -l`.
- T3 — cada `/maestro:<nome>` da lista tem um arquivo correspondente.
- T4 — a string "cinco comandos" não aparece mais no documento.
- T5 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se algum arquivo em `commands/` não tiver uma primeira frase que sirva de descrição → pare e pergunte; não invente a descrição.
- Se `commands/` tiver um número de arquivos diferente de 12 → pare e reporte antes de escrever; significa que um bloco anterior não fechou como planejado.
