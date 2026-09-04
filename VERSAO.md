# Versionamento do Maestro

Versão atual: **1.0.0**

## Como numeramos

Seguimos versionamento semântico: `MAIOR.MENOR.CORREÇÃO`.

| Parte | Muda quando | Exemplo | O usuário precisa fazer algo? |
|---|---|---|---|
| **MAIOR** | O formato do `plano/blocos.json` ou do `maestro.config.json` muda de um jeito que quebra planos existentes | 1.x → 2.0 | Sim — rodar `/maestro:setup` para migrar |
| **MENOR** | Recurso novo compatível: agente, comando, campo opcional | 1.0 → 1.1 | Não. O plano antigo continua valendo |
| **CORREÇÃO** | Ajuste de texto de prompt, correção de bug, melhoria de skill | 1.0.0 → 1.0.1 | Não |

**Regra prática:** mexeu no formato do plano de um jeito que um plano antigo deixaria de carregar, é MAIOR. Todo o resto é MENOR ou CORREÇÃO.

## Onde a versão fica registrada

| Lugar | O que guarda | Para quê |
|---|---|---|
| `.claude-plugin/plugin.json` | Versão do plugin instalado | Fonte de verdade |
| `CHANGELOG.md` | O que mudou em cada versão | O usuário decide se atualiza |
| `maestro.config.json` → `maestro_versao` | Versão que **gerou** o plano do projeto | Detecta plano velho com plugin novo |

`/maestro:status` compara as duas e avisa quando estão diferentes.

## Ao publicar uma versão nova

1. Atualize `version` em `.claude-plugin/plugin.json`.
2. Escreva a entrada no `CHANGELOG.md` — **o que mudou e o que o usuário precisa fazer**, não o diff.
3. Se for MAIOR, escreva a seção de migração no CHANGELOG.
4. Marque no git: `git tag v1.1.0 && git push --tags`.
5. Publique. Quem instalou via marketplace atualiza com `/plugin update maestro`.

## Compatibilidade de plano

Um plano guarda a versão que o criou. Ao rodar com um plugin mais novo:

- **Mesma MAIOR** → roda normal.
- **MAIOR diferente** → o status avisa e pede `/maestro:setup` para migrar. Nunca migre um plano silenciosamente: o usuário precisa saber que o formato mudou.

## O que nunca fazer
- Nunca publicar sem entrada no CHANGELOG.
- Nunca reaproveitar um número de versão já publicado.
- Nunca mudar o formato do plano numa versão MENOR.
