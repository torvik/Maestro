"""packages.core.hooks — Hooks bounded: comandos externos no ciclo de vida.

Executa comandos configurados pelo usuario em pontos do ciclo de vida de um
bloco (``pre_run``, ``post_run``, ``pre_review``, ``post_review``, ``on_fail``,
``on_block_complete``) com tres limites duros: timeout, saida truncada e
ausencia de shell. Falhas vao para ``.maestro/hooks/spool.jsonl`` (append-only).

    from packages.core.hooks import HookRunner
    runner = HookRunner(hooks=[{"event": "pre_run", "command": "python -c \\"exit(0)\\""}])
    results = runner.run_event("pre_run", context={"block_id": "F10-03"})

Biblioteca pura: so stdlib.
"""

from .runner import HookError, HookResult, HookRunner

__all__ = ["HookRunner", "HookResult", "HookError"]
