# F2-09 — F-EDITAR: `/maestro:editar <ID>`

## 1. Identificação
- Complexidade: C3 · Modelo: claude-sonnet-5 · Revisor: claude-sonnet-5
- Depende de: F2-02 · Orçamento: 30 turnos

## 2. Objetivo
Depois deste bloco existe um caminho suportado para ajustar a spec de um bloco. Hoje só existe `/maestro:replanejar`, que refaz o plano inteiro — desproporcional quando o que falta é uma linha em "Não faça".

## 3. Escopo
- Criar `commands/editar.md` e a cópia em `plugins/maestro/commands/editar.md`.
- Duas vias: ajuste pontual (o agente aplica o que o dono descreveu) e regeração (o arquiteto reescreve a spec inteira).

## 4. Não faça
- Não altere `estado` nem `tentativas` do bloco. Editar spec não é executar nem reprovar.
- Não reescreva seções da spec que o dono não mencionou, na via de ajuste pontual. Reescrita silenciosa de "Não faça" e "Pare e pergunte" é o modo de falha mais provável aqui.
- Não edite `plano/blocos.json`, exceto o campo `spec` se e somente se o caminho do arquivo mudar.
- Não permita edição de bloco `em_andamento`. Há um agente escrevendo contra essa spec agora.
- Não crie um comando que edite vários blocos.
- Não apague o `.bak` ao final.

## 5. Contrato

Entrada: `$ARGUMENTS` = um ID. Vazio = listar os blocos com spec e perguntar.

Saída da primeira interação — o comando apresenta:
```
<id> — <titulo>   estado: <estado>
spec: <caminho>  (<n> linhas)

(a) ajuste pontual  — descreva a mudanca, eu aplico so ela
(b) regerar         — o arquiteto reescreve a spec inteira do zero
```

Via (b), sequência obrigatória:
1. copiar `<spec>` para `<spec>.bak`;
2. despachar o agente `arquiteto` com `model` = `revisor_modelo` do bloco;
3. gravar a nova spec no mesmo caminho;
4. exibir o diff resumido entre `.bak` e o novo.

## 6. Regras
**R1.** Guarda de estado, verificada antes de qualquer coisa:
- `em_andamento` → recusa, manda rodar `/maestro:retomar`;
- `concluido` → avisa que a spec já foi executada e pede confirmação explícita;
- `pendente` ou `bloqueado` → segue.

**R2.** Na via (a), toda alteração é enunciada ao dono antes de gravar, na forma "vou mudar X para Y".
**R3.** Na via (b), o arquiteto recebe a spec atual como contexto e o gabarito de `anatomia-da-spec.md`. A nova spec tem as 11 seções.
**R4.** Ao final de qualquer via, rode `validar-plano.py` (via skill `maestro-runtime`) e reporte. Se ele acusar erro no bloco editado, reporte sem tentar corrigir sozinho.
**R5.** Se a edição mudar os critérios de aceite de um bloco `concluido`, avise que o bloco pode precisar de nova execução e ofereça `/maestro:proxima <ID>`. Não re-execute por conta própria.
**R6.** O `.bak` é sobrescrito a cada regeração; só a versão imediatamente anterior é preservada.
**R7.** Front-matter com `argument-hint: <ID>`, no formato dos comandos existentes.

## 7. Arquivos
`commands/editar.md` e `plugins/maestro/commands/editar.md`. O comando, em execução, escreve no arquivo de spec do bloco alvo e em `<spec>.bak` — isso é comportamento, não escrita deste bloco.

## 8. Dados
O caminho da spec vem do campo `spec` do bloco. O conteúdo da alteração vem do dono. O modelo do arquiteto vem de `revisor_modelo`. Nada vem do modelo executor.

## 9. Critérios de aceite (EARS)
1. QUANDO o comando recebe um ID O SISTEMA DEVE exibir o caminho da spec e as duas vias disponíveis.
2. QUANDO o usuário escolhe ajuste pontual O SISTEMA DEVE aplicar apenas as alterações descritas e não reescrever seções não mencionadas.
3. QUANDO o usuário escolhe regeração O SISTEMA DEVE despachar o agente `arquiteto` e gravar a nova spec no mesmo caminho, preservando a anterior como `<spec>.bak`.
4. SE o bloco estiver `concluido` ENTÃO O SISTEMA DEVE avisar que a spec já foi executada e pedir confirmação antes de editar.
5. SE o bloco estiver `em_andamento` ENTÃO O SISTEMA DEVE recusar a edição e mandar rodar `/maestro:retomar` primeiro.
6. QUANDO a spec é alterada O SISTEMA DEVE rodar `validar-plano.py` ao final e reportar o resultado.
7. O SISTEMA DEVE deixar `estado` e `tentativas` do bloco inalterados.

## 10. Casos de teste obrigatórios
- T1 — `/maestro:editar F2-01` mostra o caminho e as opções (a) e (b).
- T2 — via (a) com "acrescente um item em Não faça": as demais seções ficam byte-a-byte iguais.
- T3 — via (b): `<spec>.bak` existe e é igual ao conteúdo anterior; a nova spec tem os 11 cabeçalhos numerados.
- T4 — bloco `concluido`: o comando pede confirmação antes de tocar no arquivo.
- T5 — bloco `em_andamento`: recusa e cita `/maestro:retomar`; nenhum arquivo alterado.
- T6 — após qualquer via, o resultado de `validar-plano.py` aparece na resposta.
- T7 — `estado` e `tentativas` antes e depois são idênticos.
- T8 — borda: bloco cujo campo `spec` aponta para arquivo inexistente → o comando oferece só a via (b).
- T9 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se a alteração pedida mudar o escopo do bloco a ponto de ele não caber mais em uma sessão → pare e proponha quebrar em dois blocos; não gere uma spec grande demais.
- Se a alteração pedida introduzir um valor de negócio (preço, prazo, identificador) que o dono não forneceu → pare e pergunte o valor.
- Se a alteração afetar o contrato consumido por outro bloco (`depende_de` aponta para este) → pare e liste os blocos afetados antes de gravar.
