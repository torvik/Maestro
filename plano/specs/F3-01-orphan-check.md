# F3-01 — F-ORPHAN-CHECK: detecção de blocos órfãos

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Agente: implementador · Revisor: claude-sonnet-5
- Depende de: nenhum · Orçamento: 30 turnos
- Comando de teste: `python scripts/status.py && python scripts/verificar-repo.py --check plano && python scripts/verificar-repo.py --check paridade`

## 2. Objetivo
Depois deste bloco, um bloco cujo `depende_de` aponta para um ID que não existe no plano aparece nomeado no quadro do `status.py` e derruba `verificar-repo.py --check plano`. Hoje ele fica invisível: nunca entra em "liberado" porque a dependência jamais é satisfeita, e o quadro só mostra `(espera XX-99)`, indistinguível de uma espera legítima.

## 3. Escopo
- Detecção e exibição de dependências órfãs em `scripts/status.py`, no quadro geral e no modo `--bloco`.
- Extensão de `check_plano` em `scripts/verificar-repo.py` para reportar dependência órfã como falha.
- Réplica byte-a-byte das duas alterações em `plugins/maestro/scripts/`.

## 4. Não faça
- Não altere o código de saída de `scripts/status.py` sem argumentos. Ele continua saindo 0 mesmo com órfão detectado, porque é relatório e é consumido por `/maestro:custos` e pela skill `maestro-setup`. O portão binário é o `verificar-repo.py`.
- Não duplique em `status.py` a detecção que `validar-plano.py` já faz na linha `dep not in ids`. `validar-plano.py` fica inalterado neste bloco; ele já reporta ERRO e sai 1.
- Não crie um novo nome em `CHECKS` de `verificar-repo.py`. A detecção entra dentro de `check_plano`, que já é a verificação de integridade do plano.
- Não adicione suporte multifase a `check_plano`. Ele continua lendo só `plano/blocos.json`, como hoje. Multifase em `verificar-repo.py` é assunto de outro bloco.
- Não remova nem reescreva a dependência órfã encontrada. Este bloco só detecta e reporta; corrigir o plano é decisão do dono.
- Não trate `depende_de` no formato `"fase:ID"` como órfão. Esse caso já é ERRO em `validar-plano.py`; aqui ele é apenas mais um ID inexistente e a mensagem não precisa de tratamento especial.

## 5. Contrato

**`scripts/status.py` — quadro geral.** Um bloco com pelo menos uma dependência órfã recebe o sufixo `<- ORFAO: <dep1>[, <dep2>]` na sua linha da listagem de fase, no lugar do sufixo `(espera ...)`. Depois da seção `--- TRAVADOS ---` e antes da seção de distribuição, imprime:

```
--- DEPENDENCIAS ORFAS ---
  <id do bloco>  depende de <dep inexistente>
```

A seção é omitida por completo quando não há nenhum órfão. Código de saída permanece 0.

**`scripts/status.py --bloco <ID>`.** Na seção `--- DEPENDENCIAS ---`, uma dependência ausente de `blocos.json` é impressa como `  <dep>  INEXISTENTE` no lugar do `?` atual. Código de saída permanece 0.

**`scripts/verificar-repo.py --check plano`.** Uma linha de falha por par bloco/dependência órfã, no formato já usado pelo arquivo:

```
FALHA plano plano/blocos.json: bloco <id> depende de bloco inexistente: <dep>
```

Sai com 1 se houver qualquer falha, 0 caso contrário.

## 6. Regras
**R1.** Órfão é definido como: `dep` presente em `depende_de` de algum bloco e ausente do conjunto de `id` de todos os blocos do mesmo arquivo de plano.
**R2.** Um bloco pode ter mais de uma dependência órfã. Todas são reportadas, nenhuma é omitida.
**R3.** No quadro geral, quando o bloco tem órfão e também espera dependência válida, o sufixo `<- ORFAO:` tem precedência e lista apenas as órfãs. O sufixo `(espera ...)` não é impresso junto.
**R4.** O sufixo `<- TRAVADO:` de `bloqueado_por` tem precedência sobre `<- ORFAO:`. Um bloco travado com dependência órfã aparece como travado na listagem e mesmo assim entra na seção `--- DEPENDENCIAS ORFAS ---`.
**R5.** Blocos com `estado: "concluido"` também são inspecionados. Um bloco concluído com dependência órfã indica plano editado à mão e precisa aparecer.
**R6.** Só biblioteca padrão do Python, como no resto dos dois arquivos.
**R7.** A ordem das linhas na seção `--- DEPENDENCIAS ORFAS ---` segue a ordem dos blocos em `blocos.json`, não ordem alfabética.

## 7. Arquivos
`scripts/status.py`, `scripts/verificar-repo.py` e as duas cópias correspondentes em `plugins/maestro/scripts/`.

## 8. Dados
Todo valor vem de `plano/blocos.json`. Nenhum ID, nenhum nome de bloco e nenhuma contagem vem do modelo.

## 9. Critérios de aceite (EARS)
1. QUANDO `status.py` roda sem argumentos sobre um plano com dependência órfã O SISTEMA DEVE imprimir a seção `--- DEPENDENCIAS ORFAS ---` com uma linha por par bloco/dependência.
2. QUANDO `status.py` roda sem argumentos sobre um plano sem órfãos O SISTEMA DEVE omitir a seção `--- DEPENDENCIAS ORFAS ---` por inteiro.
3. QUANDO um bloco tem dependência órfã O SISTEMA DEVE marcar a linha desse bloco na listagem de fase com `<- ORFAO:` seguido dos IDs inexistentes.
4. SE `status.py` recebe `--bloco <ID>` e o bloco tem dependência órfã ENTÃO O SISTEMA DEVE imprimir `INEXISTENTE` como estado dessa dependência.
5. QUANDO `verificar-repo.py --check plano` roda sobre um plano com dependência órfã O SISTEMA DEVE imprimir uma linha `FALHA plano` por par e sair com código 1.
6. O SISTEMA DEVE manter o código de saída de `status.py` sem argumentos igual a 0 mesmo quando existem dependências órfãs.
7. SE um bloco tem duas ou mais dependências órfãs ENTÃO O SISTEMA DEVE reportar todas, e não apenas a primeira.
8. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — plano temporário com `"depende_de": ["XX-99"]`: `status.py` imprime `--- DEPENDENCIAS ORFAS ---` e a linha do bloco.
- T2 — plano atual do repositório (sem órfãos): a saída de `status.py` não contém a string `DEPENDENCIAS ORFAS`.
- T3 — a linha do bloco órfão na listagem de fase contém `<- ORFAO: XX-99` e não contém `(espera`.
- T4 — `status.py --bloco <bloco órfão>` imprime `XX-99  INEXISTENTE`.
- T5 — `verificar-repo.py --check plano` sobre o plano com órfão sai com 1 e imprime a linha `FALHA plano`.
- T6 — `verificar-repo.py --check plano` sobre o plano atual do repositório sai com 0.
- T7 — bloco com `depende_de: ["XX-99", "YY-88"]` gera duas linhas na seção de órfãos.
- T8 — borda: bloco com `bloqueado_por` preenchido e dependência órfã aparece como `<- TRAVADO:` na listagem e ainda assim na seção de órfãos.
- T9 — borda: bloco `concluido` com dependência órfã aparece na seção de órfãos.
- T10 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se preservar a saída atual do quadro geral exigir reescrever o laço de impressão de fases → pare e pergunte antes de refatorar, porque três consumidores dependem dessa saída.
- Se você concluir que a detecção precisa entrar em `validar-plano.py` para funcionar → pare, porque isso contradiz a seção 4 e indica que o contrato foi mal lido.
- Se o plano do repositório já contiver uma dependência órfã real no momento da execução → pare e reporte ao dono em vez de editar `plano/blocos.json` para fazer o teste passar.
