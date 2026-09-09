---
name: project_paridade_crlf
description: verificar-repo.py --check paridade falha pré-existente por CRLF (raiz) vs LF (plugins/maestro/) em ~31 arquivos, não relacionado ao conteúdo.
type: project
---

Em 2026-09-09, ao executar o bloco F3-01, descobri que `python scripts/verificar-repo.py --check paridade` já saía com código 1 **antes** de qualquer alteração feita neste bloco: 31 arquivos de `commands/`, `agents/`, `skills/` e outros `scripts/` divergem em bytes entre a raiz e `plugins/maestro/` apenas por causa de terminação de linha — CRLF na raiz (checkout Windows local, provável `core.autocrlf=true`) vs LF em `plugins/maestro/`. `git diff` não mostra essas linhas como alteradas (o git normaliza), então o conteúdo lógico é idêntico; só o `check_paridade` de `verificar-repo.py`, que compara bytes crus, acusa a divergência.

**Por quê importa:** todo bloco da fase F3 cujo `comando_teste` encadeia `verificar-repo.py --check paridade` vai reportar exit 1 mesmo quando a mudança do bloco está correta, a menos que o bloco toque e normalize os arquivos específicos que ele edita (como fiz em F3-01, reescrevendo os dois arquivos tocados com LF via Write/copy para garantir paridade byte-a-byte só entre eles).

**Como aplicar:** ao revisar blocos futuros da fase F3, não interprete `paridade` saindo 1 como reprovação automática — verifique se as falhas reportadas são dos arquivos que o bloco realmente tocou. Se forem só dos arquivos pré-existentes na lista, é uma condição alheia ao bloco. Recomendei nas notas de F3-01 (`plano/blocos.json`) um bloco futuro dedicado a normalizar line endings via `.gitattributes` (`* text=auto eol=lf` ou similar) para destravar `paridade` 100% no repositório inteiro. Antes de despachar esse bloco de normalização, confirme que ele ainda é necessário (rode `verificar-repo.py --check paridade` e veja quantos arquivos persistem).

Contagem decrescente conforme blocos tocam e corrigem os arquivos divergentes: 31 (antes de F3-01) → confirmado 30 ainda pendentes após F3-01/F3-02/F3-03 tocarem apenas scripts já normalizados → 27 após F3-04 tocar `agents/maestro.md`, `commands/proxima.md` e `commands/retomar.md` (cada um desses 3 saiu da lista de falhas). Padrão usado para "consertar" um arquivo tocado: copiar os bytes da cópia raiz (CRLF, via `Edit`) direto para `plugins/maestro/...` (sobrescrevendo o LF antigo), em vez de converter a raiz para LF — isso é o que os blocos anteriores fizeram (confirmado lendo `scripts/status.py` e `scripts/lock.py`, ambos CRLF nas duas cópias e byte-idênticos).
