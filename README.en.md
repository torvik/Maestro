<div align="center">

[🇧🇷 Versão em português](README.md)

# Maestro

**The expensive model plans. The cheap one executes.**

Free and open plugin for [Claude Code](https://claude.com/code) that breaks your project into blocks,
decides how risky each one is, and routes each to the right model — with acceptance criteria
verified by tests, not by model opinion.

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](plugins/maestro/CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Claude Code](https://img.shields.io/badge/requires-Claude%20Code-black)](https://claude.com/code)

[Install](#install) · [How it works](#how-it-works) · [Layers](#system-layers) · [Commands](#commands) · [Patterns](#patterns-applied) · [FAQ](#frequently-asked-questions)

</div>

---

## The problem

Running an entire project on the strongest reasoning model costs several times more and doesn't deliver
better results — most of any project's work is routine: migration from a ready schema,
already-documented integration, boilerplate, test data. This doesn't need the most expensive model.

The opposite problem exists too: delegating everything to a cheap model without guardrails produces
invented scope, guessed business value, and "done" that no one verified.

**Maestro solves both sides:** it classifies each part of the work by actual complexity —
not by size — and only then decides the model, with an independent reviewer checking the result
before anything is marked complete.

## How it works

```
 1. PLAN                        2. YOU APPROVE              3. EXECUTE
 ────────────────               ──────────────              ──────────────
 The powerful model writes  →    The plan becomes a    →     The router sends
 the specifications and          file you read and           each block to the
 breaks the project into         correct before any          right model, calls
 blocks with complexity,         code is written — the       a separate reviewer,
 model and acceptance            only mistake that still      and marks complete
 criteria already defined        comes free                   only if it passes
```

The expensive phase happens once. The cheap phase repeats until the project closes.

### Where each type of work goes

| Model | Complexity | Goes to | Relative cost |
|---|---|---|---|
| **Haiku 4.5** | C1–C2 | Mechanical work: ready schema migration, seed, boilerplate, conversion, documentation | 1× |
| **Sonnet 5** | C3–C4 | The bulk of construction: business rules, documented integration, new features, review | 2× |
| **Opus 5** | C4–C5 | Where mistakes cost: architecture, contracts between modules, data modeling, irreversible decisions | 5× |

A healthy division of work stays near **15% Opus / 60% Sonnet / 25% Haiku** by cost. The
`/maestro:status` command measures your actual distribution and warns when the expensive model exceeds it — almost always
a sign that a specification became ambiguous and someone bumped the model by reflex.

## System layers

Starting with 2.0.0, Maestro is not just a block router: it's a multi-agent foundation in five layers,
each isolated in `packages/core/` and usable separately.

| Layer | What it solves |
|---|---|
| 🧠 **Memory** | Working, Episodic, Semantic and Procedural Memory with SQLite index — the agent remembers across sessions, without depending on context window |
| ⚡ **Providers** | Usage-aware and capacity-aware routing; telemetry CEV (cost-efficiency-speed) per provider |
| 🤝 **Handoff** | Typed transfers between agents, with exactly-once semantics and workstreams under exclusive lease |
| 📦 **Protocol** | Universal Context Packet (UCP) and Universal Event Protocol (UEP) — harness-agnostic contracts, with trust boundaries |
| 🔌 **Adapter SDK** | Manifests, conformance suite and GenericCLI — any command-line tool becomes an adapter |

None of this needs to be configured to use the daily `/maestro:*` commands. The layers
appear when you want to switch models, integrate another tool, or run without a human at the helm.

## Install

```
/plugin marketplace add torvik/Maestro
/plugin install maestro@maestro
/maestro:setup
```

Complete guides:
- **[Installation for end users](plugins/maestro/INSTALACAO-USUARIO.md)** — step-by-step in plain language, with troubleshooting.
- **[Installation and publishing](plugins/maestro/INSTALAR.md)** — local testing and how to maintain the marketplace.
- **[Plugin README](plugins/maestro/README.md)** — complete technical reference.

## Commands

| Command | What it does |
|---|---|
| `/maestro:setup` | Detects what already exists in the repository, asks up to 6 questions and generates the plan. `--phase <name>` creates a separate phase plan |
| `/maestro:status` | Shows the board — complete, released, blocked — and distribution by model. `--block <ID>` shows full block details |
| `/maestro:proxima` | Executes the next block on the right model and calls the reviewer. `--dry-run` shows without dispatching; `--parallel` dispatches a batch of blocks simultaneously |
| `/maestro:planejar` | Writes the specification for a new block, with the powerful model |
| `/maestro:replanejar` | Adjusts the plan when reality changes |
| `/maestro:custos` | Planned distribution by model + reminder of native `/context` and `/usage` commands |
| `/maestro:retomar` | Recovers interrupted blocks (`in_progress`) after crash or session compaction |
| `/maestro:revisar <ID>` | Audit review of any block, independent of execution flow |
| `/maestro:destravar <ID>` | Clears a block's lock without editing JSON. Requires explicit confirmation |
| `/maestro:editar <ID>` | Spot adjustment or full regeneration of a block's spec by the architect |
| `/maestro:rollback <ID>` | Undoes an approved block with `git revert`. Never `git reset`. Requires clean tree |
| `/maestro:exportar` | Generates `plano/RELATORIO.md` with state, specs and metrics — ready to share |
| `/maestro:migrar` | Migrates legacy structure to the new one, with automatic backup and report |
| `/maestro:help` | Lists all commands with description, when to use each and examples. Includes 3-step quick start guide |

All commands accept `--phase <name>` to operate on `plano/<name>/blocos.json`. Legacy plans continue working without the argument.

## Patterns applied

Delegating work to a cheaper model only works with method. Nothing here was invented —
these are practices that agent engineering has already established.

<details>
<summary><b>Acceptance criteria in EARS notation</b></summary><br>

Instead of "the system should handle errors properly" (unverifiable), every specification
uses a format that becomes a test almost 1:1:

```
IF the database is unavailable
THEN THE SYSTEM MUST respond 503 and log the error.
```

Complete reference in [`ears.md`](plugins/maestro/skills/planejar-projeto/references/ears.md).
</details>

<details>
<summary><b>Test before code</b></summary><br>

Since each criterion is already a test, the executor writes tests first, sees them fail, and only then
implements until they pass. Green test is the only objective signal of "done" — without it, done is
just the model's opinion.
</details>

<details>
<summary><b>One task per session</b></summary><br>

Each block runs isolated, receiving only its specification and the files it can touch — never
the entire product document or specs from other blocks. Context is attention budget:
a full window degrades predictably, losing exactly what's in the middle.
</details>

<details>
<summary><b>Checkpoint at each block</b></summary><br>

A long session is compacted and detail is lost. One commit per completed block, plus the
progress file (`plano/blocos.json`), reconstruct the state without depending on conversation memory.
</details>

<details>
<summary><b>Budget per task</b></summary><br>

Every block has a round limit. Exceeding it is not a sign of a weak model — it's a sign of
an ambiguous specification. The system stops and hands it back, instead of getting more expensive with the same error in a loop.
</details>

<details>
<summary><b>No generic advice</b></summary><br>

A 2026 study of 138 real repositories showed that model-generated instruction files
*worsened* agent performance — by filling context with vague guidance. Here,
"write clean code" is forbidden: style is linter work, not context work.
</details>

<details>
<summary><b>Hard work becomes two blocks</b></summary><br>

A task with uncertain design (C4) is split: the powerful model draws and writes the detailed
specification; the medium model implements. Sending the whole task to the powerful model is what
most inflates cost without improving results.
</details>

<details>
<summary><b>The writer doesn't approve</b></summary><br>

The reviewer runs in a separate session, with no permission to edit the file. Checks criterion by
criterion with evidence — and specifically looks for the test that passes without exercising anything.
</details>

<details>
<summary><b>Independent phases in the same project</b></summary><br>

With `--phase <name>` each phase has its own `plano/<name>/blocos.json`. Old plans
continue working without the argument and without migration — backward compatibility is a hard rule.
</details>

<details>
<summary><b>Two blocks at the same time — only when it's safe</b></summary><br>

`--parallel` uses `scripts/paralelo.py` to check the predicate of six conditions: nothing depends on
the other (transitive), both `pending`, nothing blocked, no C5 blocks, provably disjoint file sets,
nothing in progress. On any ambiguity, it serializes. Commits always one at a time.
</details>

## What it prevents

- **Critical block doesn't fall to the cheap model.** Where the error is irreversible, the powerful
  model executes and reviews — always.
- **Block without information is not dispatched.** Missing a decision of yours, a credential or a
  data point? The block stays marked as blocked, instead of the model inventing what's missing.
- **Failed twice? Fix the text, not the model.** The cause is almost always ambiguity
  in the specification — bumping the model would just get more expensive with the same error.

## Repository structure

```
maestro/
├── .claude-plugin/marketplace.json     ← used by Claude Code to list the plugin
├── plugins/maestro/
│   ├── agents/          six agents, each with the model pinned to the role
│   ├── commands/        the /maestro:* commands
│   ├── skills/          the method: EARS, spec anatomy, execution discipline
│   ├── scripts/         status, validator, exporter, parallel — deterministic, zero cost
│   ├── README.md        technical reference
│   └── CHANGELOG.md     what changed in each version
├── packages/core/
│   ├── memory/          working, episodic, semantic and procedural memory
│   ├── providers/       usage-aware and capacity-aware routing
│   ├── handoff/         typed transfers between agents
│   ├── improvement/     improvement proposals with approval gate
│   └── protocol/        UCP, UEP and Adapter SDK
├── integrations/
│   ├── claude-code/     adapter manifest + harness
│   ├── codex/           adapter manifest + harness
│   └── relay/           headless mode and CI stub
├── .github/workflows/   Example CI with GitHub Actions
└── VERSAO.md            semantic versioning policy
```

## Frequently asked questions

**What do I need to use it?**
Claude Code on any paid plan, and a project you already work on. It's not a separate service — it runs inside Claude Code, in your account.

**Does it work for non-programming projects?**
Yes, as long as the work can be divided into blocks with an objective way to say it's done. What doesn't fit is work where "done" is a matter of taste.

**Does my code leave my machine?**
No. Maestro is a set of text files that runs inside your Claude Code. Nothing passes through our server.

**How do I confirm that model routing is working?**
Before each dispatch, Maestro prints the chosen model and agent to the conversation — for example:
`→ F2-04 B-SETUP-DEFAULTS · C2 · model: claude-haiku-4-5 · agent: maestro:operario`
To see the real cost of the session, use `/usage` (built into Claude Code).

**Does Maestro work with models other than Claude?**
Yes. Any tool with a valid `adapter.manifest.json` that passes the conformance suite becomes an adapter — the protocol (UCP/UEP) is harness-agnostic. Codex comes included in
`integrations/codex/`.

**How do I do automatic CI/CD?**
Use `integrations/relay/headless_cli.py --headless --dry-run <ID>` to execute without human interaction, or start from the example workflow in `.github/workflows/maestro-ci.yml`.

**Is it paid even though it's free later?**
No. Free and open, MIT license.

---

<div align="center">

A project by [Empreendedor Livre](https://empreendedorlivre.com).
Claude and Claude Code are products of Anthropic — this project has no partnership relationship with them.

</div>
