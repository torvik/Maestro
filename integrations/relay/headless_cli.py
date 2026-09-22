#!/usr/bin/env python3
"""Wrapper de linha de comando do modo headless (F15-01).

Ver plano/specs/F15-01-cicd-relay.md, secao 4: `scripts/maestro_run.py` nao
esta em `arquivos_permitidos` deste bloco e nao e editado; este wrapper vive
dentro de `integrations/relay/` e invoca o binario existente via subprocess
(HeadlessRunner), expondo a sintaxe que o comando de teste do bloco precisa.

Uso:
  python integrations/relay/headless_cli.py --headless --dry-run <ID> [--fase <nome>]
  python integrations/relay/headless_cli.py --headless --block-pending <ID> --motivo <texto> [--fase <nome>]

Sai com 0 (sucesso), 1 (falha/bloqueio do bloco) ou 2 (uso invalido da CLI).
Nunca chama input() -- criterio 6 do bloco F15-01.
"""

from __future__ import annotations

import argparse
import sys


def _ensure_local_import() -> None:
    """Permite `from headless import HeadlessRunner` independente de cwd."""
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


_ensure_local_import()

from headless import HeadlessRunner  # noqa: E402


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="headless_cli.py",
        description="Executa um bloco do plano Maestro em modo headless.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="obrigatorio: confirma que a chamada e para modo headless",
    )
    parser.add_argument("--dry-run", dest="dry_run_id", metavar="ID", default=None)
    parser.add_argument("--block-pending", dest="block_pending_id", metavar="ID", default=None)
    parser.add_argument("--motivo", default=None)
    parser.add_argument("--fase", default=None)
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = construir_parser()
    args = parser.parse_args(argv)

    if not args.headless:
        print("ERRO: headless_cli.py so opera com --headless.", file=sys.stderr)
        return 2

    runner = HeadlessRunner()

    if args.dry_run_id:
        resultado = runner.dry_run(args.dry_run_id, fase=args.fase)
        if resultado.stdout:
            sys.stdout.write(resultado.stdout)
        if resultado.stderr:
            sys.stderr.write(resultado.stderr)
        return 0 if resultado.ok else 1

    if args.block_pending_id:
        motivo = args.motivo or ""
        if not motivo.strip():
            print("ERRO: --block-pending requer --motivo.", file=sys.stderr)
            return 2
        resultado = runner.block_pending_question(args.block_pending_id, motivo, fase=args.fase)
        if resultado.stdout:
            sys.stdout.write(resultado.stdout)
        if resultado.stderr:
            sys.stderr.write(resultado.stderr)
        return 0 if resultado.ok else 1

    print("ERRO: informe --dry-run <ID> ou --block-pending <ID>.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
