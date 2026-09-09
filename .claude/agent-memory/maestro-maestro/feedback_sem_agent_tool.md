---
name: feedback_sem_agent_tool
description: Este ambiente de execução do maestro não expõe ferramenta Agent/Task para despachar subagentes.
type: feedback
---

Nas sessões observadas até agora neste ambiente, a lista de ferramentas disponíveis para o agente maestro é apenas Read, Grep, Glob, Bash, Edit, Write — não há `Agent`/`Task` para despachar `operario`, `implementador`, `arquiteto` ou `revisor` como subagentes isolados.

**Por quê:** o protocolo do maestro (`plugins/maestro/agents/maestro.md`) descreve um fluxo de dispatch via ferramenta Agent, mas essa ferramenta não está no toolset real desta instalação/ambiente.

**Como aplicar:** quando isso acontecer, não trave o ciclo. Execute o bloco diretamente (papel de implementador) seguindo a disciplina da skill `executar-bloco` (ler só spec + convenções + arquivos citados, escopo restrito a `arquivos_permitidos`), depois faça uma revisão genuína e separada por critério EARS (papel de revisor) antes de marcar `concluido`. Documente esse desvio no relatório final ao usuário e considere registrar `modelo_efetivo` como o modelo que de fato executou a sessão (visível no system prompt, ex. "claude-sonnet-5"). Se em uma sessão futura a ferramenta Agent estiver disponível, volte a usá-la — isolamento de contexto por bloco é o padrão preferido.

Confirmado em F3-03 e F3-04 (blocos C4, revisor planejado `claude-opus-5`): quando não há Agent tool para acionar um revisor Opus de verdade, registre em `plano/metricas.json` o campo `revisor_modelo` como o modelo que *de fato* revisou (ex. `claude-sonnet-5`), não o valor planejado no bloco — mesmo o schema-metricas.md dizendo "campo `revisor_modelo` do bloco". A intenção do campo é auditoria do que aconteceu, e o desvio já fica registrado em `notas` no `blocos.json`. Nesses blocos, recomende revisão humana ou por sessão Opus separada antes de tratar o resultado como componente crítico de segurança em produção.
