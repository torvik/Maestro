"""
maestro_runtime.py — Runtime agnóstico: MAESTRO_ROOT, resolução de paths e detecção de harness.

Primitivas:
  get_root()            -> Path | None
  resolve_path(relative) -> Path
  detect_harness()      -> str

Uso:
  import maestro_runtime
  python maestro_runtime.py --self-test
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_root() -> "Path | None":
    """Retorna a raiz do projeto Maestro.

    Precedência:
    1. Variável de ambiente MAESTRO_ROOT (tem prioridade absoluta).
    2. Busca subindo a árvore de diretórios a partir de cwd,
       procurando .maestro/ ou maestro.config.json.
    3. Retorna None se não encontrar.
    """
    env_root = os.environ.get("MAESTRO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = Path.cwd()
    while True:
        if (current / ".maestro").exists() or (current / "maestro.config.json").exists():
            return current
        parent = current.parent
        if parent == current:
            # Chegou à raiz do sistema de arquivos
            return None
        current = parent


def resolve_path(relative: "str | Path") -> Path:
    """Retorna root / relative. Usa cwd como fallback silencioso se root for None."""
    root = get_root()
    if root is None:
        root = Path.cwd()
    return root / relative


def detect_harness() -> str:
    """Detecta o harness ativo sem efeitos colaterais.

    Ordem de verificação:
    - claude-code: CLAUDE_CODE definida, ou CLAUDE_API_KEY definida e .claude/ existe na raiz
    - codex:       OPENAI_CODEX definida, ou CODEX_API_KEY definida
    - cli:         fallback
    """
    # claude-code
    if os.environ.get("CLAUDE_CODE"):
        return "claude-code"
    if os.environ.get("CLAUDE_API_KEY"):
        root = get_root()
        if root is not None and (root / ".claude").exists():
            return "claude-code"

    # codex
    if os.environ.get("OPENAI_CODEX") or os.environ.get("CODEX_API_KEY"):
        return "codex"

    return "cli"


def _self_test() -> int:
    """Executa self-test e retorna 0 (pass) ou 1 (fail)."""
    failed = False

    # MAESTRO_ROOT
    root = get_root()
    print(f"MAESTRO_ROOT: {root}")

    # harness
    harness = detect_harness()
    print(f"harness: {harness}")

    # resolve_path
    resolved = resolve_path("scripts/status.py")
    print(f"resolve_path(scripts/status.py): {resolved}")

    # Validações
    # 1. detect_harness nunca deve lançar exceção (já executou acima)
    if harness not in ("claude-code", "codex", "cli"):
        print(f"FAIL: harness inválido: {harness!r}")
        failed = True

    # 2. resolve_path deve terminar com scripts/status.py
    suffix = resolved.as_posix()
    if not suffix.endswith("scripts/status.py"):
        print(f"FAIL: resolve_path não termina com scripts/status.py: {resolved}")
        failed = True

    # 3. Se MAESTRO_ROOT está no ambiente, get_root() deve bater com ele
    env_root = os.environ.get("MAESTRO_ROOT")
    if env_root:
        expected = Path(env_root).resolve()
        if root != expected:
            print(f"FAIL: get_root()={root} != MAESTRO_ROOT={expected}")
            failed = True

    if failed:
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    else:
        print(__doc__)
