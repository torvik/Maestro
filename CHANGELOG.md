# Changelog

Todas as mudanças relevantes do Maestro. Formato baseado em Keep a Changelog; numeração em versionamento semântico (ver `VERSAO.md`).

## [1.3.2] — 2026-09-08

### Adicionado
- **Detecção de blocos órfãos** — `/maestro:status` exibe seção `--- DEPENDENCIAS ORFAS ---` quando um bloco referencia ID inexistente. `verificar-repo.py --check plano` reporta cada par órfão e sai com código 1.
- **Lock de multissessão** — `scripts/lock.py adquirir/liberar/status` usa criação atômica (`O_CREAT | O_EXCL`). `/maestro:proxima` verifica o lock antes de despachar; `/maestro:retomar` diagnostica lock obsoleto. Arquivo `plano/.lock` adicionado ao `.gitignore`.
- **Fallback de métricas corrompidas** — `status.py` e `exportar-relatorio.py` não falham quando `plano/metricas.json` está com JSON inválido, schema divergente ou registro sem `id`. Quadro é exibido sem métricas com aviso não-fatal.
- **`scripts/novo-bloco.py`** — gera esqueleto de spec com as 11 seções obrigatórias e placeholders prontos para edição. Uso: `python scripts/novo-bloco.py F3-06 "Meu bloco"`.

### Não é necessário fazer nada
Patch sem mudança de formato. Planos 1.x continuam válidos.

## [1.3.1] — 2026-09-08

### Adicionado
- **Verificação de atualização remota** — `python scripts/verificar-repo.py --check versao-remota` consulta o GitHub e avisa se há versão mais nova.
- **`/maestro:status`** agora avisa automaticamente ao final do quadro quando há atualização disponível (silencioso se offline).
- `status.py --check-update` para verificar a atualização isoladamente.

### Não é necessário fazer nada
Patch sem mudança de formato.

## [1.3.0] — 2026-09-08

### Adicionado
- **`/maestro:destravar <ID>`** — limpa `bloqueado_por` com confirmação explícita, sem editar JSON manualmente.
- **`/maestro:editar <ID>`** — ajuste pontual ou regeração completa da spec de um bloco pelo arquiteto.
- **`/maestro:rollback <ID>`** — desfaz um bloco aprovado via `git revert` (nunca `git reset`). Exige commit SHA em `metricas.json`.
- **`/maestro:exportar`** — gera `plano/RELATORIO.md` com estado completo, specs e métricas. Pronto para compartilhar.
- **`/maestro:status --bloco <ID>`** — detalhe completo de um bloco: critérios, dependências, arquivos, notas e métricas históricas.
- **`/maestro:proxima --paralelo`** — despacha lote de até `max_paralelo` blocos simultaneamente, com commits serializados.
- **F-MULTIFASE:** todos os comandos e scripts aceitam `--fase <nome>` para operar em `plano/<nome>/blocos.json`. Planos legados continuam funcionando sem argumento.
- **`scripts/paralelo.py`** — analisador de lotes: predicado C1–C6, algoritmo `disjoint()` com memoização, modo `--check A B`.
- **`scripts/verificar-repo.py`** — 5 verificações do repositório: paridade root↔plugins, portabilidade (sem `find ~/`), comandos documentados, versão coerente, plano válido.
- **`scripts/exportar-relatorio.py`** — gerador determinístico de relatório Markdown. Sem modelo, sem git.
- **`plano/metricas.json`** — contrato de 11 campos por execução de bloco. Suporte a histórico de reprovações.
- **`maestro.config.json: fase_padrao`** — equivale a `--fase <valor>` quando o argumento está ausente (opcional).
- **`maestro.config.json: max_paralelo`** — teto de paralelismo (padrão: 2).
- **`validar-plano.py`**: detecta `depende_de` com referência cruzada de fase (`"outra:F1-01"`) e reporta ERRO.

### Corrigido
- Scripts e skills usavam `find ~/` e `python3` sem fallback — quebravam no Windows. Resolvido pela skill `maestro-runtime` com cadeia python → python3 → py -3.
- `maestro.config.json` gerado pelo setup não incluía todos os campos obrigatórios (`max_tentativas`, `orcamento_turnos`, `revisor_por_complexidade`).

### Não é necessário fazer nada
Esta versão não muda o formato de `plano/blocos.json`. Planos da 1.x continuam válidos sem migração. Os novos campos de config (`fase_padrao`, `max_paralelo`) são opcionais.

## [1.2.0] — 2026-09-08

### Adicionado
- **`/maestro:retomar`** — recupera blocos `em_andamento` após crash ou sessão interrompida; analisa o git e oferece retomar, resetar ou descartar.
- **`/maestro:revisar <ID>`** — revisão de auditoria de qualquer bloco, independente do fluxo de execução.
- **`/maestro:proxima --dry-run`** — mostra qual bloco seria executado sem despachar nada.
- **Skill `migrar-plano`** — migra `plano/blocos.json` de versão MAIOR mais antiga preservando estado, tentativas e notas.

### Corrigido
- `/maestro:status` falhava com "scripts/status.py não existe" em projetos com plugin instalado via marketplace. Agora usa fallback de caminhos (igual ao `custos.md`).
- `validar-plano.py` não validava `revisor_modelo`, `comando_teste`, `orcamento_turnos` e `tentativas` como campos obrigatórios — planos com esses campos ausentes passavam silenciosamente.
- `validar-plano.py` e `status.py` ignoravam blocos com `estado: "bloqueado"` (ficavam invisíveis no quadro).
- Todos os scripts com caminhos hardcoded para `scripts/validar-plano.py` (`/maestro:planejar`, `/maestro:replanejar`, setup, skills) agora usam estratégia de fallback de caminhos.
- Arquivo de convenções do projeto (`maestro.config.json → convencoes`) não era passado ao executor. Agents `maestro` e skill `executar-bloco` agora resolvem o caminho do config antes de despachar.

### Melhorado
- `revisor.md`: G1–G10 divididos em universais (G1, G2, G9, G10) e condicionais (G3–G8) para evitar falso reprovação em projetos que não usam banco/fila/LLM.
- `revisor.md`: instrução explícita para checar `arquivos_permitidos` via `git diff --name-only`.
- `revisor.md`: corrigido "Os 5 modos de falha" → "Os 6 modos de falha".
- `maestro.md`: detecta e trata blocos `em_andamento` antes de despachar novo bloco.
- `maestro.md`: caminho de convenções resolvido do config; `Write` adicionado ao `tools`; `maxTurns: 40`.
- `arquiteto.md`: `tools` declarado explicitamente; `maxTurns: 50`.
- `operario.md`: `memory: project` adicionado.
- `explorador.md`: `cacheTtl: 1h` adicionado (igual aos demais agentes).
- `anatomia-da-spec.md`: seção 1 alinhada com o schema — agora inclui `agente`, `revisor_modelo`, `arquivos_permitidos` e `comando_teste`.
- `status.py`: custo na distribuição agora ponderado por `orcamento_turnos` (bloco C5/40 turnos pesa proporcionalmente mais que C1/15 turnos).
- `status.py`: variável `by_id` morta removida.
- `validar-plano.py`: spec file existence check — aviso se `spec` aponta para arquivo inexistente.
- `replanejar.md`: valida o plano após alterações.

### Não é necessário fazer nada
Esta versão não muda o formato do `plano/blocos.json`. Planos da 1.x continuam válidos. Os novos campos obrigatórios (`revisor_modelo`, `comando_teste`, `orcamento_turnos`, `tentativas`) eram recomendados e agora são exigidos — blocos já existentes sem esses campos receberão ERRO no `validar-plano.py`; basta preenchê-los.

## [1.1.1] — 2026-09-08

### Corrigido
- `/maestro:custos` falhava com "scripts/status.py não existe" em projetos reais. O comando agora tenta encontrar o script em múltiplos caminhos (repo, plugin local, cache global) e, se não achar, lê `plano/blocos.json` diretamente para calcular a distribuição.

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
