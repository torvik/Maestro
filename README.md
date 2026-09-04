<div align="center">

# Maestro

**O modelo caro planeja. O barato executa.**

Plugin gratuito e aberto para [Claude Code](https://claude.com/code) que quebra seu projeto em blocos,
decide o quanto cada um é arriscado e manda cada um para o modelo certo — com critério de aceite
verificável por teste, não por opinião do modelo.

[![Versão](https://img.shields.io/badge/vers%C3%A3o-1.1.0-blue)](plugins/maestro/CHANGELOG.md)
[![Licença](https://img.shields.io/badge/licença-MIT-lightgrey)](LICENSE)
[![Claude Code](https://img.shields.io/badge/requer-Claude%20Code-black)](https://claude.com/code)

[Instalar](#instalar) · [Como funciona](#como-funciona) · [Comandos](#comandos) · [Padrões aplicados](#padrões-aplicados) · [FAQ](#perguntas-frequentes)

</div>

---

## O problema

Rodar um projeto inteiro no modelo de raciocínio mais forte custa várias vezes mais e não entrega
melhor — a maior parte do trabalho de qualquer projeto é rotina: migração a partir de um schema
pronto, integração já documentada, boilerplate, dado de teste. Isso não precisa do modelo mais caro.

O problema oposto também existe: delegar tudo para um modelo barato, sem trilhos, produz escopo
inventado, valor de negócio chutado e "pronto" que não foi verificado por ninguém.

**O Maestro resolve os dois lados:** classifica cada parte do trabalho pela complexidade real —
não pelo tamanho — e só then decide o modelo, com um revisor independente conferindo o resultado
antes de qualquer coisa ser dada como concluída.

## Como funciona

```
 1. PLANEJAR                    2. VOCÊ APROVA              3. EXECUTAR
 ────────────────               ──────────────              ──────────────
 O modelo forte escreve    →    O plano vira um       →     O gestor despacha
 as especificações e            arquivo que você             cada bloco para o
 quebra o projeto em             lê e corrige antes           modelo certo, chama
 blocos com complexidade,        de qualquer linha            um revisor à parte
 modelo e critério de            ser escrita — o              e só marca como
 aceite já definidos             único erro que ainda          pronto se passar
                                 sai de graça
```

A fase cara acontece uma vez. A barata se repete até o projeto fechar.

### Para onde vai cada tipo de trabalho

| Modelo | Complexidade | Vai para | Custo relativo |
|---|---|---|---|
| **Haiku 4.5** | C1–C2 | Trabalho mecânico: migração de schema pronto, seed, boilerplate, conversão, documentação | 1× |
| **Sonnet 5** | C3–C4 | O grosso da construção: regra de negócio, integração documentada, funcionalidade nova, revisão | 2× |
| **Opus 5** | C4–C5 | Onde errar sai caro: arquitetura, contrato entre módulos, modelagem de dados, decisão irreversível | 5× |

Uma divisão saudável do trabalho fica perto de **15% Opus / 60% Sonnet / 25% Haiku** em custo. O
`/maestro:status` mede a sua distribuição real e avisa quando o modelo caro passa disso — sinal
quase sempre de que uma especificação ficou ambígua e alguém subiu de modelo por reflexo.

## Instalar

```
/plugin marketplace add SEU-USUARIO/maestro
/plugin install maestro@maestro
/maestro:setup
```

Guias completos:
- **[Instalação para o usuário final](plugins/maestro/INSTALACAO-USUARIO.md)** — passo a passo em linguagem simples, com solução de problemas.
- **[Instalação e publicação](plugins/maestro/INSTALAR.md)** — teste local e como manter o marketplace.
- **[README do plugin](plugins/maestro/README.md)** — referência técnica completa.

## Comandos

| Comando | O que faz |
|---|---|
| `/maestro:setup` | Detecta o que já existe no repositório, faz até 6 perguntas e gera o plano |
| `/maestro:status` | Mostra o quadro — concluído, liberado, travado — e a distribuição por modelo. Roda local, custo zero |
| `/maestro:proxima` | Executa o próximo bloco liberado no modelo certo e chama o revisor |
| `/maestro:planejar` | Escreve a especificação de um bloco novo, com o modelo forte |
| `/maestro:replanejar` | Ajusta o plano quando a realidade muda |

## Padrões aplicados

Delegar trabalho a um modelo mais barato só funciona com método. Nada aqui foi inventado —
são práticas que a engenharia com agentes já consolidou.

<details>
<summary><b>Critérios de aceite em notação EARS</b></summary><br>

Em vez de "o sistema deve tratar erros adequadamente" (não verificável), toda especificação
usa um formato que vira teste quase 1:1:

```
SE o banco estiver indisponível
ENTÃO O SISTEMA DEVE responder 503 e registrar o erro.
```

Referência completa em [`ears.md`](plugins/maestro/skills/planejar-projeto/references/ears.md).
</details>

<details>
<summary><b>Teste antes do código</b></summary><br>

Como cada critério já é um teste, o executor escreve os testes primeiro, vê falhar, e só então
implementa até passarem. Teste verde é o único sinal objetivo de "pronto" — sem ele, pronto é
opinião do modelo.
</details>

<details>
<summary><b>Uma tarefa por sessão</b></summary><br>

Cada bloco roda isolado, recebendo só a sua especificação e os arquivos que pode tocar — nunca
o documento de produto inteiro nem specs de outros blocos. Contexto é orçamento de atenção:
janela cheia degrada de forma previsível, perdendo justamente o que está no meio.
</details>

<details>
<summary><b>Checkpoint a cada bloco</b></summary><br>

Sessão longa é compactada e detalhe se perde. Um commit por bloco concluído, mais o arquivo
de progresso (`plano/blocos.json`), reconstroem o estado sem depender da memória da conversa.
</details>

<details>
<summary><b>Orçamento por tarefa</b></summary><br>

Todo bloco tem um limite de rodadas. Estourar não é sinal de modelo fraco — é sinal de
especificação ambígua. O sistema para e devolve, em vez de encarecer o mesmo erro em loop.
</details>

<details>
<summary><b>Sem conselho genérico</b></summary><br>

Um estudo de 2026 sobre 138 repositórios reais mostrou que arquivos de instrução gerados por
modelo *pioraram* o desempenho dos agentes — por encher o contexto de instrução vaga. Aqui,
"use código limpo" é proibido: estilo é trabalho de linter, não de contexto.
</details>

<details>
<summary><b>Trabalho difícil vira dois blocos</b></summary><br>

Tarefa de design incerto (C4) é dividida: o modelo forte desenha e escreve a especificação
detalhada; o modelo médio implementa. Mandar a tarefa inteira para o modelo forte é o que
mais infla custo sem melhorar o resultado.
</details>

<details>
<summary><b>Quem escreve não aprova</b></summary><br>

O revisor roda em sessão separada, sem permissão de editar arquivo. Confere critério por
critério com evidência — e procura especificamente o teste que passa sem exercitar nada.
</details>

## O que ele impede

- **Bloco crítico não cai no modelo barato.** Onde o erro é irreversível, o modelo forte
  executa e revisa — sempre.
- **Bloco sem informação não é despachado.** Falta uma decisão sua, uma credencial ou um
  dado? O bloco fica marcado como travado, em vez de o modelo inventar o que falta.
- **Falhou duas vezes? Corrige o texto, não o modelo.** A causa quase sempre é ambiguidade
  na especificação — subir de modelo só encareceria o mesmo erro.

## Estrutura do repositório

```
maestro/
├── .claude-plugin/marketplace.json     ← usado pelo Claude Code para listar o plugin
└── plugins/maestro/
    ├── agents/          seis agentes, cada um com o modelo fixado no papel
    ├── commands/        os cinco comandos /maestro:*
    ├── skills/          o método: EARS, anatomia de spec, disciplina de execução
    ├── scripts/         status e validador — determinísticos, custo zero
    ├── README.md        referência técnica
    ├── CHANGELOG.md      o que mudou em cada versão
    └── VERSAO.md         política de versionamento semântico
```

## Perguntas frequentes

**Preciso de quê para usar?**
Do Claude Code em qualquer plano pago, e de um projeto onde você já trabalha. Não é um
serviço à parte — roda dentro do Claude Code, na sua conta.

**Serve para projeto que não é de programação?**
Serve, desde que o trabalho possa ser dividido em blocos com um jeito objetivo de dizer que
ficou pronto. O que não encaixa é trabalho onde "pronto" é questão de gosto.

**Meu código sai da minha máquina?**
Não. O Maestro é um conjunto de arquivos de texto que roda dentro do seu Claude Code. Nada
passa por um servidor nosso.

**Como confirmo que o roteamento de modelo está funcionando?**
Rode `/tasks` depois de `/maestro:proxima` — ele mostra em qual modelo cada agente rodou.

**É pago mesmo que seja depois?**
Não. Gratuito e aberto, licença MIT.

---

<div align="center">

Um projeto do [Empreendedor Livre](https://empreendedorlivre.com).
Claude e Claude Code são produtos da Anthropic — este projeto não tem relação de parceria com ela.

</div>
