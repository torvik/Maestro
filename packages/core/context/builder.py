"""Context Builder: monta o contexto minimo suficiente de um bloco.

Le a spec do bloco, as convencoes do projeto e os arquivos cobertos por
``arquivos_permitidos``, prioriza por relevancia e corta o excedente pelo
budget de tokens, registrando o que foi omitido.

Biblioteca pura: so stdlib. Arquivo ilegivel nunca derruba o build — vai para
``omitted`` com o sufixo ``(ilegivel)``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .manifest import ContextFile, ContextManifest

#: Diretorios ignorados na expansao de globs (ruido nao textual/derivado).
_DIRS_IGNORADOS = frozenset({"__pycache__", ".git", ".maestro", "node_modules"})

#: Prioridades fixas (1 = maior). Spec e convencoes nunca disputam budget.
PRIORIDADE_SPEC = 1
PRIORIDADE_CONVENCOES = 2
PRIORIDADE_DOC = 3
PRIORIDADE_CODIGO = 4
PRIORIDADE_OUTROS = 5


class ContextError(Exception):
    """Erro de configuracao ao montar o contexto (ex.: bloco sem 'id')."""


def _default_root() -> Path:
    """Resolve a raiz do projeto: maestro_runtime.get_root() ou Path.cwd()."""
    root = None
    try:
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import maestro_runtime  # type: ignore

        root = maestro_runtime.get_root()
    except Exception:
        root = None
    return root if root is not None else Path.cwd()


def _ler_texto(caminho: Path) -> "str | None":
    """Le um arquivo como UTF-8. Retorna None se ilegivel (I4)."""
    try:
        return caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def _prioridade_de(caminho: str) -> int:
    """Classifica um arquivo de ``arquivos_permitidos`` por relevancia."""
    nome = caminho.rsplit("/", 1)[-1].lower()
    if nome.endswith(".md") or nome.startswith("adr") or "/adr" in caminho.lower():
        return PRIORIDADE_DOC
    if nome.endswith(".py"):
        return PRIORIDADE_CODIGO
    return PRIORIDADE_OUTROS


def _normalizar_gotchas(valor) -> list[str]:
    """Aceita str ou list e devolve sempre uma lista de linhas nao vazias."""
    if valor is None:
        return []
    if isinstance(valor, str):
        itens = [valor]
    elif isinstance(valor, (list, tuple)):
        itens = [str(item) for item in valor]
    else:
        itens = [str(valor)]
    return [item.strip() for item in itens if str(item).strip()]


class ContextBuilder:
    """Monta um :class:`ContextManifest` a partir de um bloco do plano."""

    def __init__(
        self,
        root: "Path | str | None" = None,
        budget_tokens: int = 8000,
        config_path: "Path | str | None" = None,
    ):
        self.root = Path(root) if root is not None else _default_root()
        self.config_path = (
            Path(config_path)
            if config_path is not None
            else self.root / "maestro.config.json"
        )
        # Budget: parâmetro explícito sobrepõe config; config sobrepõe default 8000.
        # Chave lida: "context_budget_tokens" em maestro.config.json.
        self.budget_tokens = self._ler_budget_do_config(int(budget_tokens))

    # -- API publica ----------------------------------------------------

    def estimate_tokens(self, text: str) -> int:
        """Estimativa grosseira e deterministica: 1 token ~ 4 caracteres."""
        if not text:
            return 0
        return len(text) // 4

    def build(self, block: dict) -> ContextManifest:
        """Monta o manifesto do bloco. Deterministico (I2)."""
        if not isinstance(block, dict):
            raise ContextError("bloco deve ser um dict")
        block_id = str(block.get("id") or "").strip()
        if not block_id:
            raise ContextError("campo 'id' ausente ou vazio no bloco")

        spec_path, spec_content = self._ler_spec(block)
        conventions_content, conventions_rel = self._ler_convencoes()

        manifest = ContextManifest(
            block_id=block_id,
            spec=spec_content,
            spec_path=spec_path,
            conventions=conventions_content,
            gotchas=_normalizar_gotchas(
                block.get("gotchas", block.get("notas"))
            ),
            budget_tokens=self.budget_tokens,
        )

        # I1: spec e convencoes entram sempre, mesmo estourando o budget.
        total = self.estimate_tokens(spec_content) + self.estimate_tokens(
            conventions_content
        )

        ja_usados = {p for p in (spec_path, conventions_rel) if p}
        candidatos, ilegiveis = self._coletar_arquivos(block, ja_usados)

        incluidos: list[ContextFile] = []
        omitidos: list[str] = list(ilegiveis)
        for arquivo in candidatos:
            if total + arquivo.tokens <= self.budget_tokens:
                incluidos.append(arquivo)
                total += arquivo.tokens
            else:
                omitidos.append(arquivo.path)

        manifest.files = incluidos
        manifest.omitted = omitidos
        manifest.total_tokens = total
        return manifest

    # -- internos -------------------------------------------------------

    def _ler_budget_do_config(self, budget_param: int) -> int:
        """Retorna budget efetivo. Se maestro.config.json tiver
        'context_budget_tokens', usa esse valor; caso contrário retorna
        budget_param. Falha silenciosa em caso de erro de IO ou JSON.
        """
        try:
            if self.config_path.exists():
                cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
                val = cfg.get("context_budget_tokens")
                if isinstance(val, int) and val > 0:
                    return val
        except Exception:
            pass
        return budget_param

    def _rel(self, caminho: Path) -> str:
        """Caminho relativo a raiz, sempre com barra normal (deterministico)."""
        try:
            return caminho.resolve().relative_to(self.root.resolve()).as_posix()
        except (ValueError, OSError):
            return caminho.as_posix()

    def _ler_spec(self, block: dict) -> "tuple[str, str]":
        """Retorna (spec_path, spec_content). Ausente ou ilegivel -> ('', '')."""
        bruto = block.get("spec")
        if not bruto:
            return "", ""
        caminho = Path(bruto)
        if not caminho.is_absolute():
            caminho = self.root / caminho
        if not caminho.is_file():
            return self._rel(caminho), ""
        conteudo = _ler_texto(caminho)
        return self._rel(caminho), conteudo if conteudo is not None else ""

    def _ler_convencoes(self) -> "tuple[str, str]":
        """Retorna (conteudo, caminho_relativo) das convencoes do projeto."""
        config = {}
        if self.config_path.is_file():
            bruto = _ler_texto(self.config_path)
            if bruto is not None:
                try:
                    carregado = json.loads(bruto)
                    if isinstance(carregado, dict):
                        config = carregado
                except (ValueError, TypeError):
                    config = {}

        rel = config.get("convencoes")
        if not rel or not isinstance(rel, str):
            return "", ""
        caminho = Path(rel)
        if not caminho.is_absolute():
            caminho = self.root / caminho
        if not caminho.is_file():
            return "", self._rel(caminho)
        conteudo = _ler_texto(caminho)
        return (conteudo or ""), self._rel(caminho)

    def _coletar_arquivos(
        self, block: dict, ja_usados: "set[str]"
    ) -> "tuple[list[ContextFile], list[str]]":
        """Expande globs de arquivos_permitidos e ordena por prioridade."""
        padroes = block.get("arquivos_permitidos") or []
        if isinstance(padroes, str):
            padroes = [padroes]

        vistos: set[str] = set(ja_usados)
        candidatos: list[ContextFile] = []
        ilegiveis: list[str] = []

        for padrao in padroes:
            if not isinstance(padrao, str) or not padrao.strip():
                continue
            for caminho in self._expandir(padrao.strip()):
                rel = self._rel(caminho)
                if rel in vistos:
                    continue
                vistos.add(rel)
                conteudo = _ler_texto(caminho)
                if conteudo is None:
                    ilegiveis.append(f"{rel} (ileg\u00edvel)")
                    continue
                candidatos.append(
                    ContextFile(
                        path=rel,
                        content=conteudo,
                        priority=_prioridade_de(rel),
                        tokens=self.estimate_tokens(conteudo),
                    )
                )

        ilegiveis.sort()
        candidatos.sort(key=lambda f: (f.priority, f.tokens, f.path))
        return candidatos, ilegiveis

    def _expandir(self, padrao: str) -> "list[Path]":
        """Expande um glob relativo a raiz, so arquivos, ordem estavel."""
        alvo = Path(padrao)
        if alvo.is_absolute():
            return [alvo] if alvo.is_file() else []

        try:
            achados = list(self.root.glob(padrao))
        except (ValueError, OSError, IndexError):
            return []

        resultado = []
        for caminho in achados:
            if not caminho.is_file():
                continue
            if _DIRS_IGNORADOS.intersection(caminho.parts):
                continue
            resultado.append(caminho)
        resultado.sort(key=lambda p: p.as_posix())
        return resultado
