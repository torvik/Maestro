# Maestro

Planeja projetos complexos com o modelo forte e executa distribuindo **cada bloco para o modelo que a complexidade exige** — com critério de aceite verificável e revisor independente.

O Maestro não inventa metodologia. Ele automatiza a que você já definiu: blocos com spec própria, escala de complexidade C1–C5, roteamento de modelo, regras globais e definição de pronto.

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
```

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
