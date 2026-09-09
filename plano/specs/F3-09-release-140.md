# F3-09 — Fechamento da fase: versão 1.4.0 coerente em todos os arquivos

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Agente: operario · Revisor: claude-sonnet-5
- Depende de: F3-01, F3-02, F3-04, F3-06, F3-07, F3-08 · Orçamento: 15 turnos
- Comando de teste: `python scripts/verificar-repo.py`

## 2. Objetivo
Depois deste bloco a versão 1.4.0 aparece de forma idêntica em todos os arquivos que a declaram, e o `CHANGELOG.md` descreve o que a fase F3 entregou. Sem ele o repositório termina a fase com funcionalidades novas anunciadas como 1.3.1.

## 3. Escopo
- Atualização da versão para 1.4.0 em todo `plugin.json` do repositório, em `VERSAO.md` e no campo `maestro_versao` de `maestro.config.json`.
- Entrada nova no topo do `CHANGELOG.md` descrevendo as seis funcionalidades da fase F3.
- Réplica byte-a-byte dos arquivos espelhados em `plugins/maestro/`.

## 4. Não faça
- Não reescreva entradas antigas do `CHANGELOG.md`. A entrada nova vai no topo e o histórico permanece intacto, porque é o registro do que o dono já entregou.
- Não altere nenhum arquivo de `commands/`, `agents/`, `skills/` ou `scripts/`. Este bloco é de versão e documentação; mudança de comportamento aqui passa despercebida na revisão.
- Não descreva no `CHANGELOG.md` funcionalidade que não esteja concluída em `plano/blocos.json`. A entrada é derivada do estado real do plano, não da intenção da fase.
- Não invente data. A data da entrada é a data em que este bloco roda.
- Não mexa em `plano/blocos.json`, em `plano/metricas.json` nem em nenhuma spec.

## 5. Contrato

**Arquivos que declaram a versão e precisam ficar idênticos:**

| Arquivo | Campo |
|---|---|
| `.claude-plugin/plugin.json` | `version` |
| `plugins/maestro/.claude-plugin/plugin.json` | `version` |
| `VERSAO.md` | primeiro número no formato `x.y.z` |
| `plugins/maestro/VERSAO.md` | primeiro número no formato `x.y.z` |
| `CHANGELOG.md` | primeiro número no formato `x.y.z`, no título da entrada do topo |
| `plugins/maestro/CHANGELOG.md` | primeiro número no formato `x.y.z`, no título da entrada do topo |
| `maestro.config.json` | `maestro_versao` |

**Versão alvo:** `1.4.0`.

**Entrada do `CHANGELOG.md`:** título com a versão e a data, seguido de uma linha por funcionalidade entregue, cada uma nomeando o identificador da funcionalidade da fase e o que passou a existir. As funcionalidades da fase são as seis do plano F3, mais o fechamento de versão.

A verificação `versao` de `verificar-repo.py` compara todos esses arquivos entre si e falha se houver qualquer divergência; ela é o portão binário deste bloco.

## 6. Regras
**R1.** O número da versão é escrito por extenso em cada arquivo, nunca gerado por script neste bloco.
**R2.** A verificação `versao` lê o primeiro número no formato `x.y.z` de `VERSAO.md` e do `CHANGELOG.md`. A entrada nova precisa estar no topo do arquivo para que esse primeiro número seja `1.4.0`.
**R3.** Se `plugins/maestro/CHANGELOG.md` existir, ele recebe a mesma entrada. Se não existir, não é criado.
**R4.** O campo `maestro_versao` de `maestro.config.json` acompanha a versão do plugin, porque `status.py` compara o primeiro componente dos dois e avisa o dono quando divergem.
**R5.** Nenhum outro campo de `plugin.json` é alterado.

## 7. Arquivos
`.claude-plugin/plugin.json`, `plugins/maestro/.claude-plugin/plugin.json`, `VERSAO.md`, `plugins/maestro/VERSAO.md`, `CHANGELOG.md`, `plugins/maestro/CHANGELOG.md` e `maestro.config.json`.

## 8. Dados
A versão alvo vem da seção 5 desta spec. A lista de entregas vem de `plano/blocos.json`, considerando apenas blocos com estado concluído. A data vem do relógio do sistema. Nenhum item vem do modelo.

## 9. Critérios de aceite (EARS)
1. O SISTEMA DEVE declarar `1.4.0` em todo `plugin.json` do repositório.
2. O SISTEMA DEVE declarar `1.4.0` como primeiro número no formato `x.y.z` de `VERSAO.md` e das suas cópias.
3. O SISTEMA DEVE declarar `1.4.0` no título da entrada do topo do `CHANGELOG.md`.
4. O SISTEMA DEVE declarar `1.4.0` no campo `maestro_versao` de `maestro.config.json`.
5. QUANDO a verificação `versao` roda O SISTEMA DEVE reportar zero divergências entre todos os arquivos da tabela do contrato.
6. QUANDO a entrada do `CHANGELOG.md` é escrita O SISTEMA DEVE incluir uma linha por funcionalidade concluída da fase F3.
7. SE algum bloco da fase F3 não estiver com estado concluído ENTÃO O SISTEMA DEVE omitir a funcionalidade correspondente do `CHANGELOG.md` e avisar o dono.
8. O SISTEMA DEVE preservar todas as entradas anteriores do `CHANGELOG.md`.
9. QUANDO `verificar-repo.py` roda sem argumentos O SISTEMA DEVE reportar zero falhas.

## 10. Casos de teste obrigatórios
- T1 — `python scripts/verificar-repo.py --check versao` sai com 0.
- T2 — busca por `1.3.1` nos sete arquivos da tabela do contrato: nenhuma ocorrência como versão corrente.
- T3 — a entrada do topo do `CHANGELOG.md` tem o título com `1.4.0` e a data do dia.
- T4 — a contagem de entradas do `CHANGELOG.md` é a anterior mais um.
- T5 — o número de linhas de funcionalidade na entrada nova é igual ao número de blocos F3 concluídos.
- T6 — `git diff --stat` não lista nenhum arquivo de `commands/`, `agents/`, `skills/` ou `scripts/`.
- T7 — `python scripts/verificar-repo.py` sem argumentos sai com 0.
- T8 — `python scripts/status.py` não imprime o aviso de divergência entre versão do plugin e do plano.

## 11. Pare e pergunte
- Se algum bloco da fase F3 ainda não estiver concluído quando este bloco rodar → pare e pergunte ao dono se a versão deve ser publicada mesmo assim.
- Se a verificação `versao` encontrar um `plugin.json` além dos dois da tabela do contrato → pare e reporte o caminho antes de editá-lo.
- Se o dono quiser numerar a versão de outra forma → pare, porque o número está fixado na seção 5 e mudá-lo altera o critério de aceite.
