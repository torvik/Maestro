---
name: maestro-setup
description: Configura o Maestro em um projeto por conversa, sem o usuário editar arquivo. Detecta o que já existe, faz poucas perguntas e gera o plano. Use quando o usuário quiser configurar, instalar ou começar a usar o Maestro, rodar /maestro:setup, ou pedir para executar um bloco antes de o plano existir.
---

# Setup do Maestro

Configure por **conversa**. O usuário nunca deve precisar abrir um JSON.

## Princípio
Detecte o máximo, pergunte o mínimo. Toda pergunta tem um padrão sugerido que o usuário aceita com um "pode ser".

## Passo 1 — Detectar antes de perguntar

Varra o repositório em silêncio procurando:
- specs existentes (`specs/`, `docs/specs/`, `.kiro/`, `.specify/`) → extraia ID, título, complexidade, modelo e dependências
- um plano ou roteiro de execução já escrito
- padrão de spec ou convenções de código
- `AGENTS.md` / `CLAUDE.md` → já existem princípios do projeto
- `plano/blocos.json` → **já configurado**; não sobrescreva, ofereça atualizar
- linguagem, gerenciador de pacotes e comando de teste (leia `package.json`, `pyproject.toml`, `Makefile`)

Relate o que encontrou em até 3 linhas. Se as specs já existem, **preencha o plano a partir delas** — nunca peça ao usuário para digitar o que já está escrito.

## Passo 2 — Perguntar (no máximo 6, uma por vez)

Só o que a detecção não respondeu:

1. **Comando de verificação** — o que roda para saber se está tudo certo? (detecte de `package.json`; confirme)
2. **Onde ficam as specs?** (padrão: `specs/`)
3. **Autonomia** — parar a cada bloco para você aprovar, ou emendar até falhar? (padrão: **parar a cada bloco**)
4. **Modelos por complexidade** — confirmar o padrão forte/médio/barato para C5–C4 / C3–C2 / C2–C1?
5. **Há blocos travados** por decisão pendente, credencial ou dado que ainda não existe? Registre em `bloqueado_por`.
6. **Existe convenção de código escrita?** Se não, ofereça criar um esqueleto — os executores dependem dela.

## Passo 3 — Gerar

`maestro.config.json` na raiz:

```json
{
  "maestro_versao": "<leia de .claude-plugin/plugin.json>",
  "projeto": "<nome>",
  "specs_dir": "specs/",
  "convencoes": "docs/convencoes-de-codigo.md",
  "comando_verificacao": "npm run check",
  "autonomia": "parar_a_cada_bloco",
  "modelos": {
    "C1": "claude-haiku-4-5-20251001", "C2": "claude-haiku-4-5-20251001",
    "C3": "claude-sonnet-5", "C4": "claude-sonnet-5", "C5": "claude-opus-5"
  },
  "revisor_por_complexidade": {
    "C1": "claude-sonnet-5", "C2": "claude-sonnet-5", "C3": "claude-sonnet-5",
    "C4": "claude-opus-5", "C5": "claude-opus-5"
  },
  "max_tentativas": 2,
  "orcamento_turnos": { "C1": 15, "C2": 15, "C3": 30, "C4": 30, "C5": 40 }
}
```

E `plano/blocos.json` conforme `../planejar-projeto/references/schema-blocos.md`.

**Grave sempre o `maestro_versao`**, lendo do `plugin.json` instalado. É o que permite detectar depois que um plano antigo está rodando com um plugin de formato novo.

## Passo 4 — Validar e mostrar
Encontre e rode `validar-plano.py` (tente: `scripts/validar-plano.py`, `.claude/plugins/maestro/scripts/validar-plano.py`, ou `find ~/.claude/plugins/cache/maestro -name "validar-plano.py" 2>/dev/null | head -1`). Depois encontre e rode `status.py` da mesma forma. Mostre o quadro e diga qual é o próximo bloco liberado.

## Passo 5 — Fechar com as três ações
- `/maestro:status` — ver onde está
- `/maestro:proxima` — executar o próximo bloco
- `/maestro:planejar` — especificar um bloco sem spec

## Nunca
- Nunca sobrescreva um plano existente sem confirmar.
- Nunca invente a complexidade de um bloco: se a spec não diz, pergunte.
- Nunca marque como pendente um bloco que depende de decisão do dono — use `bloqueado_por`.
- Nunca gere um arquivo de convenções recheado de conselho genérico ("use código limpo"). Instrução genérica em arquivo de agente piora o desempenho: escreva só o que é específico deste projeto.
