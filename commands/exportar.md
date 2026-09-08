---
description: Gera plano/RELATORIO.md com o plano completo, status de cada bloco e métricas. Artefato para compartilhar com o time sem precisar do Claude Code.
---

Use a skill `maestro-runtime` para localizar `exportar-relatorio.py` e invoque com o interpretador do procedimento `interpretador`.

Se o script for encontrado: `<interpretador> scripts/exportar-relatorio.py`

Se o script **não** for encontrado: gere o relatório lendo diretamente `plano/blocos.json`, `plano/metricas.json` e os arquivos de spec referenciados, seguindo esta estrutura:

```
# <projeto> — plano de execucao
Gerado em <AAAA-MM-DD> a partir de plano/blocos.json

## Resumo
| Estado | Blocos |
|---|---|
...

## Blocos
### <id> — <titulo>
- Complexidade / modelo / revisor
- Estado (com motivo, se bloqueado)
- Depende de
- Comando de teste
- Critérios de aceite (numerados, integrais)
- Spec: seções ## 2. e ## 3. copiadas literalmente (ou "spec ausente")

## Metricas   <- apenas se plano/metricas.json existir
| Bloco | Turnos | Tentativas | Veredito | Modelo efetivo |
```

Regras:
- Nunca escreva texto gerado pelo modelo no relatório. Copie os dados, não os resuma.
- Nunca consulte o git.
- Se um arquivo de spec não existir: escreva `spec ausente` e continue.
- Sobrescreva `plano/RELATORIO.md` sem perguntar.
- Informe o caminho completo do arquivo gerado ao concluir.
