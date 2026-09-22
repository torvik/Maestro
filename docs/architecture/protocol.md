# Protocolo universal: UCP e UEP

> Implementado em `packages/core/protocol/`.
> Detalhes por contrato: [ucp.md](ucp.md) · [uep.md](uep.md).

Dois contratos cortam a dependência entre o núcleo do Maestro e qualquer harness
de execução:

```
  Planner · Context Builder · Memory Engine
                   │
                   │  UCP — contrato de DADOS
                   ▼
   ┌───────────────┴───────────────────────────┐
   │                                           │
 claude-code      codex      generic-cli    <futuro>
   │                                           │
   └───────────────┬───────────────────────────┘
                   │  UEP — contrato de EVENTOS
                   ▼
   Evidence Store · Telemetry · Reviewer · State
```

O núcleo fala **só** UCP e UEP. Nenhum componente do core conhece o nome de um
harness. Criar um adapter novo não exige tocar Planner nem Memory Engine.

## Versões

| Protocolo | Constante | Valor |
|-----------|-----------|-------|
| Context Packet | `CONTEXT_PACKET_VERSION` | 1 |
| Event Protocol | `EVENT_PROTOCOL_VERSION` | 1 |
| Adapter API | `ADAPTER_API_VERSION` | 1 |

## A regra da folha

`packages/core/protocol/**` **não importa nada deste repositório** — nem
`packages.core.context`, nem `packages.core.memory`, nem
`packages.core.handoff`. Só stdlib, e internamente só o próprio
`packages.core.protocol`.

Isso é mais forte que "o core não importa Claude/Codex": um pacote que não
importa **nada** não pode importar um harness por acidente nem por
transitividade. E é verificável estaticamente — o teste T11 parseia o AST de
cada módulo do pacote — em vez de depender de revisão humana.

Consequência deliberada: tipos parecidos com os de outros pacotes (`ContextFile`
de `packages.core.context`, `ResumePacket` de `packages.core.handoff`) são
**redefinidos** aqui em vez de importados. A duplicação de algumas linhas é o
preço da independência do contrato. Traduzir entre eles é trabalho do adapter
(F14-02), não do protocolo.

O pacote também **não faz I/O** em ponto nenhum: nem no import, nem no `__init__`
das classes, nem em método. Serialização produz string; quem grava é o chamador.

## Versionamento

Todo objeto dos dois protocolos carrega `schema_version`.

| Situação | Comportamento |
|----------|---------------|
| ausente | assume a versão corrente; não é erro |
| igual à corrente | parse normal |
| menor que a corrente | aplica a cadeia de migrações e normaliza; registra `extensions["_migrated_from"]` |
| **maior** que a corrente | **não levanta**; parseia o que conhece, preserva o resto em `extensions`, mantém a versão declarada e marca `is_forward_version` |
| não-inteiro ou `<= 0` | `ValueError` — pacote malformado não é pacote do futuro |

## Degradação graceful

- **Campo desconhecido** → vai para `extensions`, nunca levanta. E `to_dict()` o
  reemite no topo: um relay v1 entre dois v2 não destrói dado que não entende.
  Campos conhecidos têm precedência na reemissão, então uma extensão nunca
  consegue sobrescrever um campo do contrato.
- **Chave desconhecida** em `budget`, `conventions` ou `payload` → preservada.
- **`event_type` desconhecido na leitura** → preservado;
  `UCPEvent.is_known_type` fica `False`. Na emissão → `ValueError`.

### Feature negotiation

O protocolo não negocia sozinho; ele só precisa não atrapalhar.

```
adapter → declara capabilities no manifest (F14-02)
Maestro → monta o UCP somente com os recursos suportados
recurso não suportado → ausente do UCP, indistinguível de inexistente
hook não suportado     → instalação do hook é pulada
```

Se um campo não suportado chegar mesmo assim, ele cai na regra de campo
desconhecido: ignorado, nunca erro. É isso que permite degradar sem versão nova
do protocolo.

## Trust boundary

O UCP é o objeto que **sai** do Maestro em direção a um processo que o Maestro
não controla, e que pode persistir, logar ou transmitir esse objeto. Payload de
evento UEP tem o mesmo destino (log, Evidence Store). Tudo que entra nos dois é
tratado como potencialmente exfiltrado.

### Nunca pode atravessar

| Proibido | Exemplos |
|----------|----------|
| Credenciais e segredos | chave de API, senha, token de sessão, cookie |
| Chaves privadas | `id_rsa`, `-----BEGIN ... PRIVATE KEY-----`, `*.pem` |
| Tokens de provedor | `sk-…`, `ghp_…`, `github_pat_…`, `AKIA…`, `xoxb-…`, `AIza…`, JWT, `Bearer …` |
| Ambiente cru | dump de `os.environ`, `.env`, `.envrc` |
| PII do usuário | e-mail pessoal, telefone, endereço, documento, dado de cliente |
| Valor de negócio real | preço real, URL/nome de cliente, dado de produção |

### Pode atravessar

Spec do bloco, critérios de aceite, caminhos permitidos, convenções, trechos de
arquivos **do repositório de código**, memória do próprio Maestro, limites
numéricos de orçamento, ids de agente e de bloco, resumo de handoff. Nada além
disso é necessário para executar um bloco.

### Enforcement — fail-closed

`scan_for_secrets` roda na construção de **todo** `UCP`, de **todo** `UCPEvent`
e em **todo** `UEP.emit()`, percorrendo recursivamente todas as folhas string,
incluindo `context_files[].content` e `extensions`.

- Achou → `UCPSecurityError`. **Não há flag para desligar.**
- A exceção nomeia o **caminho** (`$.context_files[2].content`), **nunca o
  valor** — ecoar o segredo na mensagem é o próprio vazamento, e a mensagem vai
  para log.
- Payload que não pode ser **completamente** escaneado (ciclo de referência, ou
  aninhamento acima de `MAX_SCAN_DEPTH`) é rejeitado com `ValueError`, nunca
  liberado. Encontrado em red-team.

Duas regras de detecção, ambas necessárias:

1. **Nome da chave** — dispara só quando o valor é string não vazia. A chave é
   quebrada em tokens por `[^a-z0-9]+`, então `author` não dispara `auth` e
   `max_tokens` (valor numérico) não dispara `token`.
2. **Padrão do valor** — regex de alta confiança sobre toda string. Aceita-se
   falso positivo; não se aceita falso negativo.

Escanear `context_files[].content` é o ponto central: o vazamento realista não é
alguém digitar uma chave num campo `api_key`, é o Context Builder incluir um
`.env` que casou com um glob.

### Remédio para falso positivo

```python
from packages.core.protocol import UCP, redact

packet = UCP.from_dict(redact(raw))   # valores ofensores viram "[REDACTED]"
```

A saída é **redigir**, nunca afrouxar. Se um arquivo legítimo do repositório
disparar o scanner de forma recorrente, a ação padrão é excluir o arquivo do
contexto; relaxar a regra é decisão do dono do projeto.

### Garantia resultante

**Não existe instância de `UCP` ou `UCPEvent` em memória carregando credencial.**
Por isso `redact()` opera sobre dicts, não sobre instâncias: depois da
construção não há o que redigir.

## Fail-closed, os três pontos

1. Payload com segredo → rejeitado.
2. Payload que não pode ser escaneado → rejeitado.
3. Stream de eventos sem terminal `block_completed` → `outcome == "incomplete"`,
   `succeeded == False`. **Nunca sucesso.** Ver [uep.md](uep.md#outcome--fail-closed).

## O que um adapter precisa fazer

1. Consumir um UCP sem nenhuma lógica específica de harness — tudo que é preciso
   para executar está no pacote.
2. Emitir os seis eventos do UEP.
3. Aplicar `block_spec.allowed_paths` como limite de escrita.
4. Resolver `context_files[].path` contra a raiz do projeto e recusar o que
   escapar dela (o protocolo não faz I/O e não pode verificar isso).
5. Nunca tratar `outcome == "incomplete"` como sucesso.

Manifest, conformance suite e Support Matrix são o bloco F14-02.

## Verificação

```bash
python -c "from packages.core.protocol import UCP, UEP; print('ok')"
python packages/core/protocol/_test_f14_01.py
```
