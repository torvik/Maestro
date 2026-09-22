# Handoff — transferência tipada de trabalho entre agentes

Bloco F13-01. Código em `packages/core/handoff/`.

## Por que existe

O Maestro opera com mais de um agente (Claude Code, Codex, outros adapters). Quando um agente encerra a sessão no meio de um bloco, duas coisas podem dar errado:

1. **Entrega repetida** — dois agentes leem o mesmo handoff pendente e refazem o mesmo trabalho.
2. **Edição concorrente** — dois agentes mexem no mesmo conjunto de arquivos ao mesmo tempo.

Este módulo resolve o primeiro com *claim exactly-once* e o segundo com *lease exclusivo por workstream*.

## Visão geral

```
Claude Code                                          Codex
     │                                                 │
 session-end                                       session-start
     │                                                 │
     ├─ create() ──► .maestro/handoffs/H-123.json      │
     │              status: open                       │
     │                                                 │
     │                       list_open(for_agent) ◄────┤
     │                                                 │
     │                              claim() ◄──────────┤
     │                       status: claimed           │
     │                       ResumePacket ────────────►│
     │                                                 │
     │                                            (trabalha)
     │                                                 │
     │                             accept() ◄──────────┤
     │                       status: accepted          │
```

O agente que retoma recebe um **ResumePacket**: contexto limitado, montado só a partir do handoff. Nada de varrer o repositório para reconstruir o que já estava escrito.

## Componentes

| Módulo | Responsabilidade |
|--------|------------------|
| `schema.py` | `Handoff`, `StateSnapshot`, `Checkpoint`, `ResumePacket`, `Workstream`, `Lease`, state machine, validação, exceções |
| `storage.py` | I/O atômico em `.maestro/handoffs/`, marcadores `O_EXCL` |
| `manager.py` | `HandoffManager` — ciclo de vida do handoff |
| `workstreams.py` | `WorkstreamRegistry` — registro e lease |

## Layout em disco

```
.maestro/handoffs/
  H-20260922T101530-a1b2c3d4.json    registro canônico
  .claims/<ID>.claim                 marcador de reserva (prova de entrega)
  workstreams/WS-01.json             registro do workstream
  workstreams/WS-01.lease            lease ativo
```

Toda escrita de `.json` é **atômica**: arquivo temporário no mesmo diretório + `os.replace()` (atômico em POSIX e Windows). Nunca existe um registro pela metade.

## State machine

```
                    claim()              accept()
      ┌────────┐   ──────────►  ┌─────────┐  ──────────►  ┌──────────┐
      │  open  │                │ claimed │               │ accepted │
      └────────┘                └─────────┘               └──────────┘
        │    │
        │    └──── cancel() ────────────────────────────►  ┌───────────┐
        │                                                  │ cancelled │
        │                                                  └───────────┘
        └──────── sweep_expired() ───────────────────────►  ┌─────────┐
                  (now > expires_at)                        │ expired │
                                                            └─────────┘
```

Quatro transições e nenhuma a mais. `accepted`, `expired` e `cancelled` são terminais — não há reabertura.

**`cancel()` sobre um handoff `claimed` falha de propósito.** Cancelar trabalho que outro agente já começou é exatamente o acidente que o módulo previne. Claim abandonado é liberado pelo TTL do lease do workstream, não por cancelamento.

## Exactly-once: como o claim funciona

```
Fase 1 — RESERVA    os.open(.claims/<ID>.claim, O_CREAT | O_EXCL)
                    Vence exatamente um processo. Todos os outros → ClaimError.
Fase 2 — MONTAGEM   carrega, valida estado/destinatário, monta o ResumePacket.
Fase 3 — COMMIT     escrita atômica com status=claimed.
```

Se a fase 2 ou 3 levantar exceção, o marcador é removido e o handoff volta a ficar `open` — falha antes da montagem nunca deixa trabalho preso.

Em caso de sucesso o marcador **permanece**. Ele é a prova durável da entrega: mesmo que o `.json` seja reescrito depois, um segundo `claim()` morre na fase 1.

Validado em red-team: 16 threads e 10 processos reais disputando o mesmo handoff produzem exatamente 1 vencedor.

### Limitação conhecida

`kill -9` entre a fase 1 e a fase 3 deixa o marcador órfão: o handoff fica `open` porém não reivindicável, até alguém apagar `.claims/<ID>.claim`.

Isso falha **para o lado seguro** (nunca entrega duas vezes), ao custo de intervenção manual. A alternativa — TTL no marcador — reintroduziria o risco de entrega repetida. A troca foi deliberada.

## Workstreams

Um workstream é uma linha lógica de trabalho dentro de um projeto: `WS-auth-refactor`, `WS-provider-routing`. Vários rodam em paralelo, cada um com seus próprios handoffs.

**A identidade é o `workstream_id`.** `name` é metadata: renomear não quebra handoff, lease nem histórico, porque nada indexa por nome.

O **lease** dá execução exclusiva. É fail-closed:

- não é reentrante — um segundo `acquire_lease()`, mesmo do próprio dono, falha. Reentrância mascararia bug de coordenação a montante;
- só o token do dono libera. Não existe `force_release`;
- só o TTL tira o lease de quem o segura.

## Uso

### Encerrando uma sessão

```python
from packages.core.handoff import HandoffManager, StateSnapshot, Checkpoint

manager = HandoffManager()  # raiz do projeto = cwd

manager.create(
    from_agent="claude-code",
    to_agent="any",                 # ou um agente específico
    block_id="B21",
    context_summary="Routing está ligado para dois adapters. O retry budget "
                    "ainda está hardcoded e precisa ir para config.",
    state_snapshot=StateSnapshot(
        completed=["registry de adapters"],
        remaining=["mover retry budget para config"],
        failed_approaches=["regex sobre a AST — frágil demais"],
        files_touched=["packages/core/routing/registry.py"],
        next_steps=["extrair o retry budget", "adicionar teste de regressão"],
        checkpoint=Checkpoint(branch="feat/routing", commit="c0ffee"),
    ),
    open_questions=["Qual camada de config é dona do retry budget?"],
    workstream="WS-provider-routing",
)
```

`failed_approaches` não é enfeite: é o que impede o próximo agente de gastar a sessão repetindo um caminho que já se provou errado.

### Retomando em outro agente

```python
manager = HandoffManager()

for pending in manager.list_open(for_agent="codex"):
    packet = manager.claim(pending.id, "codex")   # exactly-once

    print(packet.context_summary)   # contexto inicial
    print(packet.next_steps)
    print(packet.open_questions)
    print(packet.checkpoint.commit)

    # ... executa o trabalho ...

    manager.accept(pending.id, "codex")
    break
```

### Lease de workstream

```python
from packages.core.handoff import WorkstreamRegistry

registry = WorkstreamRegistry()
registry.register("WS-auth-refactor", name="Auth refactor", project="relay")

lease = registry.acquire_lease("WS-auth-refactor", "claude-code", ttl_seconds=3600)
try:
    ...  # execução exclusiva
finally:
    registry.release_lease("WS-auth-refactor", lease.token)
```

## Tratamento de erro

| Exceção | Quando |
|---------|--------|
| `ValueError` | campo obrigatório ausente/vazio, id malformado, timestamp inválido |
| `HandoffNotFoundError` | handoff inexistente |
| `HandoffExistsError` | `create()` com id já usado — nunca sobrescreve |
| `InvalidTransitionError` | transição fora da tabela, ou handoff vencido |
| `ClaimError` | já reivindicado, destinatário errado, ou accept por quem não reivindicou |
| `WorkstreamNotFoundError` | workstream não registrado |
| `LeaseError` | lease já vigente, ou token errado |

Todas herdam de `HandoffError`, exceto `ValueError`.

Campos obrigatórios: `id`, `from_agent`, `to_agent`, `block_id`, `context_summary`. A validação roda **antes** de qualquer escrita — handoff inválido nunca chega ao disco.

`list_open()` ignora arquivos corrompidos em vez de levantar exceção: um registro ruim não pode cegar o agente para todos os outros pendentes.

## Garantias

1. Registro nunca escrito pela metade (`os.replace`).
2. Um handoff é entregue no máximo uma vez.
3. Claim que falha deixa o handoff `open`, sem marcador.
4. `list_open()` nunca quebra por arquivo corrompido.
5. `load()` é round-trip fiel.
6. Renomear workstream não muda identidade.
7. Timestamps sempre ISO-8601 UTC com `Z`.
8. Workstreams distintos são mutuamente independentes.

## Testes

```bash
python packages/core/handoff/_test_f13_01.py
```

21 testes, stdlib apenas, I/O real em `tempfile.mkdtemp()`. Devem imprimir `ALL TESTS PASSED`.
