# Anatomia da spec de bloco

Gabarito. Copie e preencha. Seções vazias são sinal de bloco mal definido — não deixe placeholder.

```markdown
# <ID> — <título>

## 1. Identificação
- Complexidade: C<1-5>
- Modelo: <id do modelo>
- Agente: <operario | implementador | arquiteto>
- Revisor modelo: <id do modelo — deve ser >= executor>
- Depende de: <IDs ou "nenhum">
- Arquivos permitidos: <globs — escrita fora disto reprova na revisão>
- Comando de teste: <comando que prova o bloco objetivamente>
- Orçamento de turnos: <15 para C1-C2 | 30 para C3-C4 | 40 para C5>

## 2. Objetivo
O que existe depois que este bloco fecha. Duas linhas.

## 3. Escopo
- O que está dentro (lista fechada)

## 4. Não faça
- O que está fora, e de quem é
- Erros específicos que um executor tenderia a cometer aqui

## 5. Contrato
Entrada e saída, em JSON com schema versionado.

## 6. Regras
R1. …
R2. …
(numeradas, para o revisor citar)

## 7. Arquivos
Caminhos que este bloco pode criar ou tocar. Escrita fora disto reprova.

## 8. Dados
De onde vem cada valor de negócio. Nenhum vem do modelo.

## 9. Critérios de aceite (EARS)
QUANDO … O SISTEMA DEVE …
SE … ENTÃO O SISTEMA DEVE …

## 10. Casos de teste obrigatórios
T1. <nome> — deriva do critério de aceite 1
T2. …
(um por critério, mais os de borda)

## 11. Pare e pergunte
- <gatilho concreto> → pare
- <gatilho concreto> → pare
```

## O que não escrever
Nada de "use boas práticas", "escreva código limpo", "adicione testes", "trate erros". Instrução genérica ocupa atenção e não informa. Convenção de estilo é trabalho do linter.

Escreva só o que é específico deste bloco e que o executor não teria como adivinhar.
