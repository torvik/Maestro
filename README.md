<div align="center">

# Maestro

<<<<<<< HEAD
Planeja projetos complexos com o modelo forte e executa distribuindo **cada bloco para o modelo que a complexidade exige** — com critério de aceite verificável e revisor independente.

O Maestro não inventa metodologia. Ele automatiza a que você já definiu: blocos com spec própria, escala de complexidade C1–C5, roteamento de modelo, regras globais e definição de pronto.
=======
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
>>>>>>> 9fac1958f59764c2fa661824a68c8f1c9718b4f0

## Instalação

**Para o usuário final:** [INSTALACAO-USUARIO.md](INSTALACAO-USUARIO.md) — passo a passo em linguagem simples.
**Para publicar:** [INSTALAR.md](INSTALAR.md) — teste local e publicação via GitHub.
**Versão e atualizações:** [CHANGELOG.md](CHANGELOG.md) e [VERSAO.md](VERSAO.md).

Resumo:

```bash
# 1. Copie a pasta para o projeto
cp -r maestro /caminho/do/projeto/.claude/plugins/

# 2. Ou use como agentes/comandos locais do projeto:
cp -r maestro/agents/*   /caminho/do/projeto/.claude/agents/
cp -r maestro/commands/* /caminho/do/projeto/.claude/commands/
cp -r maestro/skills/*   /caminho/do/projeto/.claude/skills/
cp -r maestro/scripts    /caminho/do/projeto/scripts/
```

Reinicie o Claude Code (a pasta `.claude/agents/` só é detectada se existir na inicialização).

## Uso — cinco comandos

| Comando | O que faz |
|---|---|
| `/maestro:setup` | Configura por conversa. Detecta suas specs e gera o plano. Faz até 6 perguntas |
| `/maestro:status` | Quadro do plano: concluído, liberado, travado. **Roda em Python, custo zero** |
| `/maestro:proxima` | Executa o próximo bloco liberado, no modelo certo, e chama o revisor |
| `/maestro:planejar` | Escreve a spec de um bloco (Opus) no padrão de 11 seções |
| `/maestro:replanejar` | Ajusta o plano quando a realidade mudou |
| `/maestro:custos` | Distribuição planejada por modelo + lembrete dos comandos nativos de custo |

## Como a troca de modelo acontece

Cada agente declara seu modelo no frontmatter. Despachar o bloco **já troca o modelo** — não há código de roteamento a manter.

| Agente | Modelo | Usado em |
|---|---|---|
| `arquiteto` | Opus 5 | Specs, arquitetura, blocos C5, revisão C4–C5 |
| `implementador` | Sonnet 5 | Blocos C2–C4 (o cavalo de batalha) |
| `operario` | Haiku 4.5 | Blocos C1–C2 mecânicos |
| `revisor` | Sonnet 5 | Validação de C1–C3 |
| `maestro` | Sonnet 5 | Despacha, valida, registra |

**Confirme o roteamento com `/tasks`**, que mostra o modelo de cada subagente. Já houve casos de subagente ignorar o campo `model` — verifique antes de confiar.

## Regras invioláveis (o validador barra)

1. Bloco **C5 nunca** vai para Haiku — nem executar, nem revisar.
2. Revisor é sempre **igual ou superior** ao executor.
3. Bloco com `bloqueado_por` preenchido **não é despachado**.
4. Em 2 tentativas: **conserte a spec primeiro**, não escale o modelo por reflexo.
5. Um bloco por sessão. O executor recebe a spec e as convenções — nunca o brief do produto.

## Arquivos que o Maestro cria

- `maestro.config.json` — configuração (gerada pelo setup)
- `plano/blocos.json` — **fonte de verdade do estado**; só o agente `maestro` escreve aqui

## Scripts (custo zero, sem modelo)

```bash
python3 scripts/status.py          # quadro do plano + distribuicao por modelo
python3 scripts/validar-plano.py   # checa as regras invioláveis
```

Use `MAESTRO_PLANO=caminho/blocos.json` para apontar outro plano.

## Contexto e performance

Quatro mecanismos, todos já configurados nos agentes:

| Mecanismo | Onde | Ganho |
|---|---|---|
| **Cache de prompt (1h)** | `experimental.cacheTtl` nos executores | Spec + convenções são relidas a cada bloco. Leitura em cache custa 10% da entrada |
| **Isolamento de contexto** | Subagente por bloco | A leitura pesada morre no contexto do subagente; a sessão principal recebe só o resumo |
| **Agente `explorador` (Haiku)** | Busca no código | Mapear repositório é a operação que mais polui contexto. Fica no modelo mais barato |
| **`maxTurns`** | 15 no operário, 30 no implementador, 20 no revisor | Corta o agente que entra em laço antes de queimar a franquia |
| **`memory: project`** | Executores e revisor | Acumulam padrões e armadilhas do projeto entre sessões, reduzindo redescoberta |

Regras de higiene que valem mais que qualquer configuração:
- **Um bloco por sessão.** Rode `/clear` entre blocos.
- **O executor nunca recebe o brief do produto** — só a spec e as convenções.
- **`/maestro:status`** mostra também a distribuição real por modelo e avisa quando o modelo caro passa de 25%.

## Publicar como marketplace

Para que outras pessoas instalem com dois comandos, publique num repositório GitHub público com esta estrutura:

```
seu-repo/
├── .claude-plugin/marketplace.json
└── plugins/maestro/        <- o conteúdo desta pasta
```

`marketplace.json`:
```json
{
  "name": "maestro",
  "owner": { "name": "Empreendedor Livre" },
  "plugins": [
    { "name": "maestro", "source": "./plugins/maestro",
      "description": "Orquestra projetos distribuindo cada bloco para o modelo certo." }
  ]
}
```

Instalação para o usuário final:
```
/plugin marketplace add SEU-USUARIO/seu-repo
/plugin install maestro@maestro
/maestro:setup
```

<<<<<<< HEAD
## Comandos nativos do Claude Code que valem a pena conhecer

O Maestro não substitui estes — ele não tem acesso ao consumo real de uma sessão, só ao que o plano planejou. Use os dois juntos:

| Comando | Nativo do Claude Code | O que mostra |
|---|---|---|
| `/context` | sim | O que está ocupando a janela **desta sessão**, por categoria, com sugestão de corte |
| `/usage` (`/cost`, `/stats`) | sim | Custo e limite do seu plano |
| `/agents` | sim | Agentes carregados no projeto |
| `/plugin` | sim | Plugins instalados, origem, atualizar/remover |
| `/tasks` | sim | Em qual modelo cada subagente rodou de fato — **confira sempre** depois de `/maestro:proxima` |
| `/maestro:status` | Maestro | Quadro do plano + distribuição planejada por modelo |
| `/maestro:custos` | Maestro | Atalho que junta os dois e lembra qual comando nativo checar |

## Práticas que o Maestro aplica

| Prática | Onde entra | Por quê |
|---|---|---|
| **Critérios em EARS** | Toda spec | Critério em EARS vira caso de teste quase 1:1 — é o que torna a spec executável em vez de consultiva |
| **Teste antes do código** | Executor | Teste verde é o único sinal objetivo de "pronto". Sem ele, pronto é opinião do modelo |
| **Fase de esclarecimento** | Antes de especificar | Spec pode estar errada, e código que cumpre spec errada não atende requisito nenhum |
| **Isolamento de contexto** | Um bloco por subagente | Contexto é orçamento de atenção; o modelo perde o que fica no meio de uma janela cheia |
| **Checkpoint em git** | A cada bloco concluído | Sessão longa é compactada. O histórico do git e o arquivo de progresso reconstroem o estado |
| **Orçamento de turnos** | Por bloco | Estourar o orçamento é sintoma de spec ambígua — o sistema para em vez de encarecer o mesmo erro |
| **Restrição na instrução** | Specs e convenções | Estudo de 138 repositórios: instrução genérica em arquivo de agente piorou o desempenho. Nada de "use código limpo" |
| **Quebrar C4 em dois** | Planejamento | Desenho no modelo forte, implementação no médio. Tratar o C4 inteiro como forte é o que mais infla custo sem ganho |

O validador (`python3 scripts/validar-plano.py`) avisa quando um critério não está em EARS, usa termo vago, não tem comando de teste, ou quando um C4 está inteiro no modelo forte.
=======
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
>>>>>>> 9fac1958f59764c2fa661824a68c8f1c9718b4f0
