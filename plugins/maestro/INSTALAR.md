# Como instalar o Maestro

Dois caminhos. **Comece pelo A** (é o que você usa hoje, para testar). O B é para quando quiser publicar.

---

## Caminho A — testar agora, na sua máquina

O Claude Code lê agentes, comandos e skills de uma pasta `.claude/` dentro do projeto. Instalar é copiar arquivos para lá.

### 1. Descompacte

```bash
tar -xzf maestro-plugin.tar.gz
```

Isso cria uma pasta `maestro/`.

### 2. Entre no seu projeto e crie as pastas

```bash
cd /caminho/do/seu/projeto
mkdir -p .claude/agents .claude/commands .claude/skills scripts
```

### 3. Copie os arquivos

```bash
cp    /caminho/onde/descompactou/maestro/agents/*    .claude/agents/
cp    /caminho/onde/descompactou/maestro/commands/*  .claude/commands/
cp -r /caminho/onde/descompactou/maestro/skills/*    .claude/skills/
cp    /caminho/onde/descompactou/maestro/scripts/*   scripts/
```

### 4. Reinicie o Claude Code

**Este passo não é opcional.** A pasta `.claude/agents/` só é lida quando o Claude Code inicia. Se você não reiniciar, os comandos não aparecem.

Feche e abra de novo, dentro do projeto:

```bash
claude
```

### 5. Confirme que funcionou

Digite `/` e veja se aparecem `setup`, `status`, `proxima`, `planejar` e `replanejar`.
Rode também:

```
/agents
```

Devem aparecer: `maestro`, `arquiteto`, `implementador`, `operario`, `revisor`, `explorador`.

### 6. Configure

```
/maestro:setup
```

Ele detecta o que já existe no repositório, faz até seis perguntas e cria dois arquivos: `maestro.config.json` e `plano/blocos.json`.

### 7. Veja o quadro

```
/maestro:status
```

### 8. Rode o primeiro bloco — e confira o modelo

```
/maestro:proxima
```

Enquanto roda, abra outro momento e digite:

```
/tasks
```

**Isso mostra em qual modelo cada subagente está rodando.** Confirme que um bloco simples foi mesmo para o Haiku. Se todos estiverem no modelo da sessão, o roteamento não pegou — e todo o ganho de custo some sem aviso.

---

## Caminho B — publicar para outras pessoas

Quando quiser que qualquer um instale com dois comandos.

### 1. Crie um repositório público no GitHub

Estrutura:

```
maestro/                          <- o repositório
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    └── maestro/                  <- todo o conteúdo do plugin
        ├── .claude-plugin/plugin.json
        ├── agents/
        ├── commands/
        ├── skills/
        └── scripts/
```

### 2. Crie o `marketplace.json`

```json
{
  "name": "maestro",
  "owner": { "name": "Empreendedor Livre" },
  "plugins": [
    {
      "name": "maestro",
      "source": "./plugins/maestro",
      "description": "Orquestra projetos distribuindo cada bloco para o modelo certo."
    }
  ]
}
```

### 3. O usuário instala assim

```
/plugin marketplace add SEU-USUARIO/maestro
/plugin install maestro@maestro
/maestro:setup
```

### 4. Atualize a landing page

No arquivo `maestro-landing.html`, procure o bloco `CONFIGURE AQUI` e troque:
- `REPO` → o caminho real (`seu-usuario/maestro`)
- `ENDPOINT` → o endereço do seu serviço de formulário, para capturar o lead

---

## Se algo não aparecer

| Sintoma | Causa provável |
|---|---|
| Comandos `/maestro:*` não aparecem | Não reiniciou o Claude Code depois de copiar |
| `/agents` não lista os agentes | Arquivos foram para o lugar errado — confira `ls .claude/agents/` |
| `/maestro:status` dá erro de arquivo | O plano ainda não existe: rode `/maestro:setup` |
| Todos os blocos rodam no mesmo modelo | Confira com `/tasks`; se persistir, o campo `model` do agente não está sendo respeitado |
| `python3` não encontrado | Instale o Python 3 ou peça ao Claude para rodar o script |
