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

E `plano/blocos.json` conforme `../planejar-projeto/references/schema-blocos.md`. Use este modelo para cada bloco — **todos os 14 campos são obrigatórios**. Se o usuário não informar `comando_teste`, pare e pergunte antes de gravar:

```json
{
  "id": "F1-01",
  "titulo": "<título curto>",
  "spec": "specs/F1-01-<slug>.md",
  "complexidade": "C3",
  "modelo": "<leia de modelos[complexidade] no config acima>",
  "agente": "implementador",
  "revisor_modelo": "<leia de revisor_por_complexidade[complexidade] no config>",
  "depende_de": [],
  "arquivos_permitidos": ["src/**"],
  "criterio_aceite": ["SE ... ENTÃO O SISTEMA DEVE ..."],
  "estado": "pendente",
  "comando_teste": "<comando que prova o bloco — obrigatório>",
  "orcamento_turnos": 30,
  "tentativas": 0,
  "bloqueado_por": null,
  "notas": []
}
```

**Grave sempre o `maestro_versao`**, lendo do `plugin.json` instalado. É o que permite detectar depois que um plano antigo está rodando com um plugin de formato novo.

## Passo 4 — Validar e mostrar
Use a skill `maestro-runtime` para localizar e rodar `validar-plano.py` e depois `status.py`. Mostre o quadro e diga qual é o próximo bloco liberado.

## Passo 5 — Comandos disponíveis

**No dia a dia**

- `/maestro:setup` — Configura o Maestro neste projeto por conversa — detecta specs, faz poucas perguntas e gera o plano.
- `/maestro:status` — Mostra o quadro do plano — concluído, em andamento, liberado, travado.
- `/maestro:proxima` — Executa o próximo bloco liberado do plano, no modelo que a complexidade exige.
- `/maestro:planejar` — Escreve a spec de um bloco (ou planeja um projeto novo) com o arquiteto no Opus.

**Quando algo sai do trilho**

- `/maestro:replanejar` — Revisa o plano quando a realidade mudou — bloco maior que a spec, dependência nova, decisão tomada.
- `/maestro:custos` — Panorama de custo — a distribuição planejada por modelo (Maestro) e um lembrete de onde checar o gasto real da sessão (Claude Code).
- `/maestro:retomar` — Recupera blocos em_andamento após sessão interrompida — analisa o que foi feito e oferece opções de continuação.
- `/maestro:revisar <ID>` — Dispara revisão de auditoria de um bloco específico, independente do fluxo de execução.
- `/maestro:destravar <ID>` — Limpa o bloqueio de um bloco sem editar plano/blocos.json manualmente. Exige confirmação explícita antes de gravar.
- `/maestro:editar <ID>` — Ajusta a spec de um bloco — ajuste pontual (só a mudança descrita) ou regeração completa pelo arquiteto. Não altera estado nem tentativas.
- `/maestro:rollback <ID>` — Desfaz um bloco aprovado usando git revert (nunca git reset). Exige confirmação explícita. Só opera quando a árvore está limpa.
- `/maestro:exportar` — Gera plano/RELATORIO.md com o plano completo, status de cada bloco e métricas. Artefato para compartilhar com o time sem precisar do Claude Code.

## Nunca
- Nunca sobrescreva um plano existente sem confirmar.
- Nunca invente a complexidade de um bloco: se a spec não diz, pergunte.
- Nunca marque como pendente um bloco que depende de decisão do dono — use `bloqueado_por`.
- Nunca gere um arquivo de convenções recheado de conselho genérico ("use código limpo"). Instrução genérica em arquivo de agente piora o desempenho: escreva só o que é específico deste projeto.

## CLAUDE.md do projeto

Após gerar `plano/blocos.json`, crie `CLAUDE.md` no projeto a partir de
`integrations/claude-code/CLAUDE.md.template`, substituindo:
- `{{projeto}}` pelo nome do projeto detectado
- `{{comando_verificacao}}` pelo comando de verificação detectado

