# Changelog

Todas as mudanças relevantes do Maestro. Formato baseado em Keep a Changelog; numeração em versionamento semântico (ver `VERSAO.md`).

## [1.0.0] — 2026-09-03

Primeira versão pública.

### Adicionado
- **Seis agentes com modelo fixado por papel** — `arquiteto` (forte), `maestro`, `implementador`, `revisor` (médios), `operario` e `explorador` (barato). Despachar o bloco já troca o modelo.
- **Cinco comandos** — `/maestro:setup`, `/maestro:status`, `/maestro:proxima`, `/maestro:planejar`, `/maestro:replanejar`.
- **Setup por conversa** — detecta specs, plano e convenções já existentes no repositório e faz no máximo seis perguntas.
- **Critérios de aceite em EARS** — notação que faz cada critério virar um caso de teste. Referência completa em `skills/planejar-projeto/references/ears.md`.
- **Teste antes do código** — o executor escreve os testes derivados dos critérios, vê falhar e só então implementa.
- **Escala de complexidade C1–C5** — decide o modelo por quanta decisão o executor precisa tomar sozinho.
- **Validador de plano** — barra bloco crítico em modelo barato, revisor inferior ao executor, dependência inexistente e ciclo. Avisa sobre critério fora de EARS, critério vago, bloco sem comando de teste e bloco C4 inteiro no modelo forte.
- **Quadro de status com distribuição por modelo** — roda localmente, sem consumir modelo. Avisa quando o modelo forte passa de 25% do custo.
- **Orçamento de turnos por bloco** — estourar é tratado como spec ambígua, não como modelo fraco.
- **Checkpoint em git** — commit a cada bloco concluído, para reconstruir o estado depois de uma compactação de sessão.
- **Cache de prompt de 1 hora e limite de turnos** nos executores.
- **Bloqueio explícito** — bloco que depende de decisão, credencial ou dado ausente não é despachado.

### Notas
- Requer Claude Code em qualquer plano pago.
- Confirme com `/tasks` que cada subagente está rodando no modelo esperado antes de confiar no roteamento.

## [1.1.0] — 2026-09-03

### Adicionado
- Comando `/maestro:custos` — panorama de distribuição planejada por modelo, com lembrete de quando usar `/context` e `/usage` nativos do Claude Code.
- `scripts/status.py` agora encerra com um bloco de referência aos comandos nativos (`/context`, `/usage`, `/agents`, `/plugin`, `/tasks`).

### Esclarecido
- Documentado no README que o Maestro não tem acesso ao consumo real de tokens de uma sessão — isso é interno do Claude Code (`/context`, `/usage`). O Maestro mede a distribuição *planejada* por modelo a partir do plano de blocos.
