# Instalar o Maestro — passo a passo

Leva uns 5 minutos. Você não precisa saber programar para instalar.

---

## Antes de começar

Você precisa de duas coisas:

1. **Claude Code instalado**, em qualquer plano pago. É o programa da Anthropic que roda no seu terminal. Se ainda não tem, instale em [claude.com/code](https://claude.com/code).
2. **Um projeto** — qualquer pasta no seu computador onde você já trabalhe.

> O Maestro roda **dentro** do seu Claude Code, com a sua conta. Não é um serviço à parte, não pede cartão e não manda seu código para lugar nenhum.

---

## Jeito 1 — instalação automática (recomendado)

### Passo 1. Abra o Claude Code na pasta do seu projeto

No terminal:

```
cd caminho/do/seu/projeto
claude
```

### Passo 2. Adicione o repositório do Maestro

Dentro do Claude Code, digite:

```
/plugin marketplace add SEU-USUARIO/maestro
```

### Passo 3. Instale

```
/plugin install maestro@maestro
```

### Passo 4. Reinicie o Claude Code

**Não pule este passo.** Feche com `/exit` e abra de novo com `claude`. Os agentes só são carregados quando o programa inicia — sem reiniciar, parece que nada foi instalado.

### Passo 5. Confira se deu certo

Digite uma barra:

```
/
```

Devem aparecer na lista: `maestro:setup`, `maestro:status`, `maestro:proxima`, `maestro:planejar` e `maestro:replanejar`.

Se apareceram, **está instalado**. Pule para "Primeiro uso".

---

## Jeito 2 — instalação manual (baixando o arquivo)

Use este se preferir baixar o arquivo em vez de conectar ao repositório.

### Passo 1. Baixe e descompacte

Baixe o `maestro-plugin.tar.gz` e descompacte. Vai virar uma pasta chamada `maestro`.

- **Windows:** clique com o botão direito e use o 7-Zip ou o WinRAR.
- **Mac/Linux:** `tar -xzf maestro-plugin.tar.gz`

### Passo 2. Crie as pastas dentro do seu projeto

No terminal, dentro da pasta do seu projeto:

```
mkdir -p .claude/agents .claude/commands .claude/skills scripts
```

> A pasta `.claude` começa com ponto, então fica escondida. No Mac, use `Cmd + Shift + .` no Finder para ver.

### Passo 3. Copie os arquivos

Troque `CAMINHO` pelo lugar onde você descompactou:

```
cp    CAMINHO/maestro/agents/*    .claude/agents/
cp    CAMINHO/maestro/commands/*  .claude/commands/
cp -r CAMINHO/maestro/skills/*    .claude/skills/
cp    CAMINHO/maestro/scripts/*   scripts/
```

No Windows, dá para simplesmente arrastar as pastas no Explorador de Arquivos.

### Passo 4. Abra o Claude Code e confira

```
claude
```

Digite `/` e veja se os comandos `maestro:*` aparecem.

---

## Primeiro uso

### 1. Configure

```
/maestro:setup
```

Ele vai olhar o seu projeto, contar o que encontrou e fazer no máximo seis perguntas. Cada pergunta já vem com uma sugestão — você pode só responder "pode ser" e seguir.

Ao final, ele cria dois arquivos no seu projeto:
- `maestro.config.json` — as suas preferências
- `plano/blocos.json` — o plano de trabalho

### 2. Veja o quadro

```
/maestro:status
```

Mostra o que está pronto, o que está liberado para executar e o que está travado esperando alguma decisão sua.

### 3. Execute o primeiro bloco

```
/maestro:proxima
```

Ele pega a próxima tarefa liberada, manda para o modelo certo, chama um revisor e só marca como pronta se passar.

### 4. Confira se o roteamento funcionou

Este passo vale muito. Enquanto ou logo depois de executar, digite:

```
/tasks
```

Isso mostra em qual modelo cada agente rodou. **Confirme que uma tarefa simples foi mesmo para o modelo mais barato.** Se todas rodaram no mesmo modelo, a economia não está acontecendo — e é melhor descobrir agora.

---

## Se algo der errado

| O que acontece | O que fazer |
|---|---|
| Os comandos `/maestro:*` não aparecem | Reinicie o Claude Code. É a causa em 9 de 10 casos |
| `/agents` não lista os agentes | Os arquivos foram para o lugar errado. Rode `ls .claude/agents/` e veja se estão lá |
| `/maestro:status` reclama que não achou o plano | O plano ainda não existe. Rode `/maestro:setup` |
| Aparece "python3 não encontrado" | Instale o Python 3, ou peça ao Claude: "rode o script de status para mim" |
| Todas as tarefas rodam no mesmo modelo | Confira com `/tasks`. Se persistir, reinstale e reinicie |
| Um bloco aparece como "travado" | É proposital: falta uma decisão sua, uma credencial ou um dado. O status diz qual |

---

## Manter atualizado

Se instalou pelo **Jeito 1**:

```
/plugin update maestro
```

Se instalou pelo **Jeito 2**: baixe a versão nova e repita a cópia dos arquivos.

Para saber o que mudou, veja o `CHANGELOG.md`. Se a mudança for de versão maior (por exemplo, de 1.x para 2.0), o `/maestro:status` avisa que seu plano precisa ser migrado, e basta rodar `/maestro:setup` de novo.

---

## Perguntas rápidas

**Preciso pagar alguma coisa?**
Não. O Maestro é gratuito. Você só precisa já ter o Claude Code, que é da Anthropic.

**Ele funciona com projeto que não é de programação?**
Funciona, desde que o trabalho possa ser dividido em partes com um jeito objetivo de dizer que ficou pronto.

**Posso desinstalar?**
Pelo Jeito 1: `/plugin uninstall maestro`. Pelo Jeito 2: apague os arquivos que você copiou. Os arquivos `maestro.config.json` e `plano/` são seus e ficam.

**Meu código vai para algum servidor?**
Não. Tudo roda na sua máquina, dentro do seu Claude Code.
