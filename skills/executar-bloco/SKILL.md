---
name: executar-bloco
description: Executa um bloco do plano com disciplina de contexto e verificação por teste. Monta o prompt de despacho e o de revisão. Use ao despachar qualquer bloco para execução ou revisão, inclusive em /maestro:proxima.
---

# Executar um bloco

## 1. Disciplina de contexto

Contexto é orçamento de atenção, não espaço de armazenamento. O objetivo é **o menor conjunto de tokens de alto sinal** que faz o bloco fechar. Contexto grande demais degrada de forma previsível: o modelo perde o que está no meio.

O executor recebe **somente**:
- a spec do bloco
- o arquivo de convenções do projeto (caminho em `maestro.config.json → convencoes`)
- os arquivos citados na seção "Arquivos" da spec

Ele **não recebe**: o documento de produto, specs de outros blocos, histórico de conversa.

**Um bloco por sessão.** Rode `/clear` entre blocos. Isolar o contexto de cada bloco no seu próprio subagente é o padrão que mais economiza em projeto grande — a leitura pesada morre lá dentro e só o resultado volta.

Precisa entender código existente? Despache o agente `explorador` primeiro. Ele lê muito, devolve pouco, e roda no modelo mais barato.

## 2. O loop de verificação (teste antes de código)

O critério de aceite já está em EARS, então **cada critério vira um teste**. A ordem importa:

```
1. Escreva os testes a partir dos critérios EARS   → eles falham
2. Implemente até os testes passarem
3. Cole a saída literal do comando de teste
```

Um teste que passa é o sinal objetivo de que o bloco terminou. Sem ele, "pronto" é opinião do modelo — e essa é a origem da maior parte do retrabalho.

## 3. Prompt de despacho

```
Implemente o bloco <ID> conforme a spec anexa.

1. Antes de escrever código, liste em até 5 linhas o que vai fazer e confirme
   se bate com os critérios de aceite.
2. Escreva primeiro os testes que derivam dos critérios de aceite. Rode e veja
   falhar. Só então implemente.
3. Não implemente nada fora da seção "Escopo".
4. Nenhum valor de negócio pode ser inventado por você. Se faltar dado, PARE.
5. Se um gatilho de "Pare e pergunte" acontecer, pare e pergunte.
6. Não altere schema, contrato de API, nem arquivo de outro bloco. Se precisar, PARE.
7. Ao terminar, rode os testes e cole a saída literal.

Escreva apenas nestes caminhos: <arquivos_permitidos>
Convenções do projeto: <caminho lido de maestro.config.json → convencoes>
Orçamento: <orcamento_turnos> turnos. Ao estourar, pare e reporte onde travou.
```

## 4. Prompt de revisão (sessão nova, agente que não escreveu)

```
Revise o bloco <ID> contra a spec anexa. Não corrija nada — aponte.

Para cada critério de aceite: ATENDE / NÃO ATENDE / PARCIAL, com o trecho de
código ou a saída de comando que prova.

Depois liste:
(a) qualquer coisa implementada que NÃO está na spec
(b) qualquer valor de negócio escrito direto no código
(c) qualquer teste obrigatório ausente, ou que passa sem exercitar o critério

Veredito: APROVADO ou REPROVADO. Nunca "aprovado com ressalvas".
```

## 5. Checkpoint (para sobreviver à compactação)

Sessão longa é compactada, e o agente perde detalhe. Dois hábitos resolvem:

- **Commit a cada bloco concluído**, com mensagem descritiva. O histórico do git reconstrói o estado depois de qualquer compactação — `git log` e `git diff` valem mais que memória.
- **`plano/blocos.json` é o arquivo de progresso.** Depois de uma compactação, ler esse arquivo restaura o que foi feito, o que está em andamento e o que está travado. Mantenha-o atualizado *durante*, não no fim.

## 6. Definição de pronto
1. Critérios conferidos por **quem não escreveu o código**.
2. Todos os testes obrigatórios passam, com saída colada.
3. Nenhum item de "Não faça" violado.
4. Nada escrito fora de `arquivos_permitidos`.
5. Se C4 ou C5: revisão do modelo forte registrada.
6. Commit feito.

## 7. Depois da revisão
- Aprovado → `estado: "concluido"`, commit.
- Reprovado → `pendente`, `tentativas + 1`, motivo em `notas`.
- **Chegou a 2 tentativas → corrija a SPEC primeiro** e rode de novo no mesmo modelo. A causa quase sempre é ambiguidade, não capacidade. Se já corrigiu e falhou de novo, PARE e chame o usuário.
- **Estourou o orçamento de turnos** → mesmo tratamento: é sintoma de spec vaga.
