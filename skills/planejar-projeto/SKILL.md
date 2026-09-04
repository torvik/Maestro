---
name: planejar-projeto
description: Escreve especificações de bloco e monta o plano de execução — com critérios de aceite em notação EARS, complexidade C1-C5 e modelo atribuído. Use ao planejar um projeto novo, especificar um bloco sem spec, replanejar, ou quando o usuário rodar /maestro:planejar.
---

# Planejar: da ideia à spec executável

Quando o agente escreve o código, **a spec é a coisa de maior alavancagem que um humano produz**. Uma spec ambígua vira código ruim barato — e custa três vezes mais para desfazer.

## Regra zero
**Nunca mande um modelo codar direto do documento de produto.** Documento de produto é estratégico: tem opinião, não contrato. Modelo lendo documento de produto preenche lacuna com invenção plausível. Cada bloco precisa da sua própria spec.

## O ciclo (portão humano entre cada fase)

```
esclarecer → especificar → planejar blocos → você aprova → executar → conferir consistência
```

**Não pule o esclarecer.** É a fase mais barata e a que mais economiza. Antes de escrever qualquer spec, liste as ambiguidades e pergunte. Uma spec pode estar errada — e código que cumpre uma spec errada não atende requisito nenhum.

## Critérios de aceite: use EARS

EARS (Easy Approach to Requirements Syntax) é o padrão de fato para critério que não deixa margem a interpretação. **O ganho real: um critério em EARS vira caso de teste quase um para um.** É isso que torna a spec executável em vez de consultiva.

Os cinco padrões, e quando usar cada um, estão em `references/ears.md`. Leia esse arquivo antes de escrever critérios.

Exemplo do formato:
```
QUANDO o usuário envia um e-mail válido
  O SISTEMA DEVE enviar um link de acesso válido por 15 minutos.
SE o link for usado mais de uma vez
  ENTÃO O SISTEMA DEVE recusar com HTTP 410.
```

Critério que não vira teste não é critério — é desejo. Reescreva.

## Anatomia da spec

As 11 seções e o gabarito completo estão em `references/anatomia-da-spec.md`.

Duas seções são obrigatórias e costumam ser as esquecidas:
- **"Não faça"** — impede o executor de inventar escopo.
- **"Pare e pergunte"** — com gatilhos explícitos; impede o executor de chutar uma decisão que é do dono.

## Complexidade decide o modelo

Complexidade **não é tamanho** — é quanta decisão o executor toma sozinho.

| | Característica | Executor |
|---|---|---|
| **C1** | Zero decisão: transcrever, boilerplate, seed, migration de schema pronto | Haiku |
| **C2** | Uma integração documentada ou CRUD com regras claras | Haiku (spec forte) ou Sonnet |
| **C3** | Lógica de negócio própria, casos de borda que a spec lista | Sonnet |
| **C4** | Incerteza de design; o comportamento correto precisa ser descoberto | Opus desenha → Sonnet implementa |
| **C5** | Erro causa dano físico, exposição jurídica, ou é irreversível | Opus do início ao fim |

**Quebre todo bloco C4 em dois:** um de desenho (Opus, produz a spec detalhada) e um de implementação (Sonnet, executa). Tratar o C4 inteiro como Opus é o erro que mais infla custo sem ganho.

## Orçamento por bloco
Todo bloco declara `orcamento_turnos` — quantas rodadas o executor tem antes de parar. Estourou o orçamento é sinal de spec ambígua, não de modelo fraco. Padrão: 15 para C1–C2, 30 para C3–C4.

## Portão de qualidade da spec

Antes de dar por pronta, responda:
- [ ] Todo critério de aceite está em EARS e vira um teste?
- [ ] Um executor **sem nenhum contexto do produto** conseguiria implementar só com esta spec?
- [ ] Existe algum valor de negócio (preço, medida, prazo, identificador) que o executor teria que inventar? Se sim, **a spec está incompleta**.
- [ ] "Não faça" e "Pare e pergunte" estão preenchidas com casos reais, não genéricos?
- [ ] O bloco cabe em uma sessão?

## Restrição (isto importa mais do que parece)
Um estudo de 2026 sobre 138 repositórios reais encontrou que arquivos de instrução gerados por modelo **pioraram** o desempenho dos agentes — porque encheram o contexto de instrução genérica.

Então: **não escreva "use código limpo", "siga boas práticas", "escreva testes"**. Isso ocupa atenção e não informa nada. Convenção de estilo é trabalho de linter, não de spec. Escreva só o que é específico deste bloco e que o executor não teria como adivinhar.

## Ao terminar
Registre o bloco em `plano/blocos.json` (formato em `references/schema-blocos.md`) e rode `python3 scripts/validar-plano.py`.
