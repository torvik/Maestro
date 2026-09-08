# F2-04 — B-SETUP-DEFAULTS: setup gera todos os campos obrigatórios

## 1. Identificação
- Complexidade: C2 · Modelo: claude-haiku-4-5 · Revisor: claude-sonnet-5
- Depende de: F2-01 · Orçamento: 15 turnos

## 2. Objetivo
Depois deste bloco, todo bloco criado pelo `/maestro:setup` passa no `validar-plano.py` na primeira tentativa. Hoje o setup omite `tentativas` e `notas`, e o plano recém-criado já nasce reprovado pelo validador.

## 3. Escopo
- Alterar `skills/maestro-setup/SKILL.md` (Passo 3, geração do `plano/blocos.json`) para incluir um bloco-modelo com os 14 campos obrigatórios preenchidos.
- Replicar em `plugins/maestro/skills/maestro-setup/SKILL.md`.

## 4. Não faça
- Não altere `validar-plano.py` para relaxar a lista `OBRIG`. O validador está certo; o setup é que está incompleto.
- Não invente valores de `comando_teste` nem de `criterio_aceite` para o usuário — esses campos vêm do usuário ou do arquiteto.
- Não mexa nos Passos 1, 2, 4 nem na seção "Nunca" da skill.
- Não adicione campos além dos 14 obrigatórios mais `bloqueado_por` e `fase`.

## 5. Contrato
Os 14 campos obrigatórios, conforme a constante `OBRIG` de `scripts/validar-plano.py`:
`id`, `titulo`, `spec`, `complexidade`, `modelo`, `agente`, `revisor_modelo`, `depende_de`, `arquivos_permitidos`, `criterio_aceite`, `estado`, `comando_teste`, `orcamento_turnos`, `tentativas`.

Valores padrão obrigatórios ao criar um bloco novo: `estado: "pendente"`, `tentativas: 0`, `notas: []`, `bloqueado_por: null`.

## 6. Regras
**R1.** Leia a lista `OBRIG` do `validar-plano.py` do repositório antes de escrever o modelo; não a copie desta spec de memória.
**R2.** `orcamento_turnos` vem da tabela já presente no `maestro.config.json` gerado pela própria skill (`C1/C2: 15`, `C3/C4: 30`, `C5: 40`).
**R3.** `modelo` e `revisor_modelo` vêm dos mapas `modelo_por_complexidade` e `revisor_por_complexidade` do `maestro.config.json`, nunca fixados no texto da skill.
**R4.** Se o usuário não informar `comando_teste`, a skill para e pergunta. Bloco sem comando de teste não é bloco.

## 7. Arquivos
`skills/maestro-setup/SKILL.md` e `plugins/maestro/skills/maestro-setup/SKILL.md`.

## 8. Dados
Nenhum valor de negócio. Todo default vem de `validar-plano.py` ou do `maestro.config.json` gerado no Passo 3.

## 9. Critérios de aceite (EARS)
1. QUANDO a skill `maestro-setup` gera um bloco novo O SISTEMA DEVE incluir os 14 campos obrigatórios listados em `OBRIG`.
2. QUANDO a skill gera um bloco novo O SISTEMA DEVE preencher `tentativas` com `0`, `notas` com lista vazia e `bloqueado_por` com `null`.
3. SE o usuário não informar o comando de teste de um bloco ENTÃO O SISTEMA DEVE parar e perguntar, em vez de gravar `comando_teste` vazio.
4. QUANDO a verificação `paridade` roda após a alteração O SISTEMA DEVE reportar zero divergências entre as duas cópias.

## 10. Casos de teste obrigatórios
- T1 — o bloco-modelo na skill contém os 14 nomes de campo; conferir um a um contra `OBRIG`.
- T2 — o bloco-modelo mostra `"tentativas": 0`, `"notas": []`, `"bloqueado_por": null`.
- T3 — a skill contém a instrução explícita de parar quando falta `comando_teste`.
- T4 — `python scripts/verificar-repo.py --check paridade` sai com 0.

## 11. Pare e pergunte
- Se `OBRIG` no `validar-plano.py` divergir da tabela de `schema-blocos.md` → pare e pergunte qual é a fonte de verdade.
- Se você concluir que algum dos 14 campos não pode ser preenchido no momento do setup → pare e pergunte; não grave string vazia para satisfazer o validador.
