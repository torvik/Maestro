---
description: Ajusta a spec de um bloco — ajuste pontual (só a mudança descrita) ou regeração completa pelo arquiteto. Não altera estado nem tentativas.
argument-hint: <ID>
---

Leia `plano/blocos.json`.

Se `$ARGUMENTS` estiver vazio: liste os blocos que têm campo `spec` preenchido e pergunte qual ID o usuário quer editar. Pare aqui.

Se `$ARGUMENTS` tiver um ID:

1. **Encontre o bloco.** Se o ID não existir, informe e encerre.

2. **Guarda de estado:**
   - `em_andamento` → recuse a edição e diga ao usuário para rodar `/maestro:retomar` primeiro. Encerre.
   - `concluido` → avise que a spec já foi executada e peça confirmação explícita antes de continuar.
   - `pendente` ou `bloqueado` → prossiga.

3. **Exiba o resumo do bloco:**
   ```
   <id> — <titulo>   estado: <estado>
   spec: <caminho>  (<n> linhas)
   ```

   Se o arquivo de spec não existir, ofereça apenas a via (b).

4. **Apresente as duas vias:**
   ```
   (a) ajuste pontual  — descreva a mudança, eu aplico só ela
   (b) regerar         — o arquiteto reescreve a spec inteira do zero
   ```
   Aguarde a escolha do usuário.

**Via (a) — ajuste pontual:**
- Pergunte qual mudança deve ser aplicada.
- Antes de gravar, anuncie exatamente o que vai mudar: "vou alterar X para Y na seção Z".
- Aplique **apenas** a mudança descrita. Não reescreva seções não mencionadas.
- Grave no mesmo caminho de spec.

**Via (b) — regeração:**
1. Copie `<spec>` para `<spec>.bak` (sobrescreve `.bak` anterior se existir).
2. Despache o agente `arquiteto` com `model` = campo `revisor_modelo` do bloco, passando a spec atual como contexto e o gabarito de `skills/planejar-projeto/references/anatomia-da-spec.md`.
3. Grave a nova spec no mesmo caminho.
4. Exiba o diff resumido entre `.bak` e o novo arquivo (seções adicionadas, removidas ou alteradas).

**Ao final de qualquer via:**
- Rode `validar-plano.py` via skill `maestro-runtime` e reporte o resultado.
- Se os critérios de aceite mudaram e o bloco está `concluido`, avise que pode ser necessária nova execução e ofereça `/maestro:proxima <ID>`. Não re-execute por conta própria.

## Nunca
- Nunca altere `estado` nem `tentativas` do bloco em `plano/blocos.json`.
- Nunca reescreva seções não mencionadas (via a).
- Nunca edite dois blocos em uma invocação.
- Nunca apague o `.bak` ao final.
