# F3-07 — F-LINT-SPEC (integração): `/maestro:editar` roda o linter

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Agente: operario · Revisor: claude-sonnet-5
- Depende de: F3-06 · Orçamento: 15 turnos
- Comando de teste: `python scripts/verificar-repo.py --check paridade && python scripts/verificar-repo.py --check portabilidade && python scripts/verificar-repo.py --check comandos-documentados`

## 2. Objetivo
Depois deste bloco, toda spec gravada por `/maestro:editar` passa por `scripts/lint-spec.py` antes de o comando encerrar, e o resultado é mostrado ao dono. Hoje o comando só roda `validar-plano.py`, que confere o plano e não olha o conteúdo estrutural da spec.

## 3. Escopo
- Acréscimo da chamada do linter ao passo de fechamento de `commands/editar.md`, nas duas vias do comando.
- Definição da resposta a cada código de saída do linter dentro do comando.
- Réplica byte-a-byte em `plugins/maestro/commands/editar.md`.

## 4. Não faça
- Não faça o comando corrigir a spec sozinho quando o linter reprova. O comando mostra as violações e pergunta; corrigir sem pedir é como o executor barato inventa escopo.
- Não reverta a spec gravada por causa de reprovação do linter. O dono pode ter gravado um rascunho de propósito e perder a edição é pior que ter uma spec reprovada no disco.
- Não altere `estado` nem `tentativas` do bloco. A regra já vale no comando hoje e continua valendo.
- Não remova nem reordene o passo que roda `validar-plano.py`. As duas verificações convivem: o linter olha a spec, o validador olha o plano.
- Não escreva o caminho do script em linha dura. A localização segue a skill `maestro-runtime`, como todos os demais scripts invocados por comando.
- Não introduza `python3` literal sem fallback nem `find ~/`, porque a verificação `portabilidade` está no comando de teste deste bloco.

## 5. Contrato

**Ponto de inserção:** dentro do bloco "Ao final de qualquer via" de `commands/editar.md`, antes da chamada de `validar-plano.py`.

**Chamada:** `lint-spec.py <caminho da spec gravada>`, com o script localizado pela skill `maestro-runtime`.

**Resposta por código de saída:**

| Saída | Ação do comando |
|---|---|
| `0` | imprime `spec valida` e segue para `validar-plano.py` |
| `1` | imprime as violações na íntegra, pergunta ao dono se quer corrigir agora, e só corrige o que ele autorizar |
| `2` | imprime que o caminho da spec não foi encontrado e segue para `validar-plano.py` |
| script ausente ou sem interpretador | imprime que o linter não pôde rodar e segue para `validar-plano.py` |

Em todos os quatro casos o comando encerra com o resumo habitual e a spec permanece gravada.

## 6. Regras
**R1.** O linter roda uma vez por invocação do comando, sobre a spec que acabou de ser gravada, e não sobre todas as specs do plano.
**R2.** Na via de regeração, o linter roda sobre o arquivo novo e não sobre o `.bak`.
**R3.** As violações são exibidas na íntegra, sem resumo e sem interpretação. O texto do linter já é a mensagem.
**R4.** Se o dono autorizar a correção, o comando aplica apenas as correções das violações listadas e roda o linter de novo, no máximo uma vez.
**R5.** Reprovação do linter não impede o comando de terminar. O portão é informativo aqui; o portão duro é o revisor no momento da execução do bloco.
**R6.** Se `--fase <nome>` foi recebido pelo comando, ele continua sendo repassado ao `validar-plano.py` como já acontece. O linter não recebe `--fase`, porque opera sobre um caminho de arquivo.

## 7. Arquivos
`commands/editar.md` e `plugins/maestro/commands/editar.md`. Nenhum outro arquivo é alterado por este bloco.

## 8. Dados
O caminho da spec vem do campo `spec` do bloco em `plano/blocos.json`. As violações vêm da saída de `scripts/lint-spec.py`. Nenhum texto de violação vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `/maestro:editar` termina de gravar uma spec por qualquer das duas vias O SISTEMA DEVE rodar `lint-spec.py` sobre o caminho gravado antes de rodar `validar-plano.py`.
2. SE `lint-spec.py` sai com código 1 ENTÃO O SISTEMA DEVE exibir todas as violações na íntegra e perguntar ao dono se deve corrigir.
3. SE o dono não autoriza a correção ENTÃO O SISTEMA DEVE encerrar deixando a spec gravada como está.
4. SE `lint-spec.py` sai com código 0 ENTÃO O SISTEMA DEVE informar que a spec é válida e prosseguir.
5. SE o linter não puder ser executado ENTÃO O SISTEMA DEVE informar o fato e prosseguir para `validar-plano.py` em vez de encerrar com erro.
6. QUANDO a via de regeração é usada O SISTEMA DEVE rodar o linter sobre o arquivo novo e nunca sobre o arquivo `.bak`.
7. O SISTEMA DEVE deixar `estado` e `tentativas` do bloco inalterados em todos os caminhos.
8. QUANDO as verificações `paridade`, `portabilidade` e `comandos-documentados` rodam após a alteração O SISTEMA DEVE reportar zero falhas.

## 10. Casos de teste obrigatórios
- T1 — leitura de `commands/editar.md`: a chamada do linter aparece antes da chamada de `validar-plano.py`.
- T2 — leitura de `commands/editar.md`: a tabela de resposta cobre os quatro casos do contrato.
- T3 — leitura de `commands/editar.md`: existe instrução explícita de não corrigir sem autorização do dono.
- T4 — leitura de `commands/editar.md`: existe instrução explícita de rodar o linter sobre o arquivo novo na via de regeração.
- T5 — a seção `Nunca` do arquivo continua contendo as quatro proibições que já existiam.
- T6 — busca textual: nenhuma ocorrência de `python3 ` sem fallback e nenhuma de `find ~/` no arquivo alterado.
- T7 — busca textual: o caminho de `lint-spec.py` não aparece em linha dura; há referência à skill `maestro-runtime`.
- T8 — `python scripts/verificar-repo.py --check paridade` sai com 0.
- T9 — `python scripts/verificar-repo.py --check portabilidade` sai com 0.
- T10 — `python scripts/verificar-repo.py --check comandos-documentados` sai com 0.

## 11. Pare e pergunte
- Se você concluir que o linter deveria bloquear a gravação da spec quando reprova → pare, porque a seção 4 diz o contrário e a mudança afeta o fluxo de trabalho do dono.
- Se o passo de fechamento de `commands/editar.md` tiver mudado de forma a não existir mais → pare e descreva a estrutura encontrada antes de reorganizar o arquivo.
- Se a integração exigir alterar `commands/planejar.md` ou `commands/replanejar.md` → pare e pergunte, porque esses arquivos estão fora da seção 7.
