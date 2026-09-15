#!/usr/bin/env python3
"""Gera AGENTS.md no projeto alvo a partir do template Codex.

Usage:
  python integrations/codex/installer/install.py \
    --projeto <nome> --verificacao <cmd> [--destino <dir>] [--harness codex]
"""

import argparse
import os
import sys

TEMPLATE_RELATIVO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "AGENTS.template.md"
)


def gerar_agents_md(projeto, verificacao, destino):
    template_path = os.path.abspath(TEMPLATE_RELATIVO)

    if not os.path.exists(template_path):
        print("Erro: template nao encontrado em {0}".format(template_path), file=sys.stderr)
        return 1

    with open(template_path, "r", encoding="utf-8") as f:
        conteudo = f.read()

    conteudo = conteudo.replace("{{projeto}}", projeto)
    conteudo = conteudo.replace("{{comando_verificacao}}", verificacao)

    if not os.path.isdir(destino):
        os.makedirs(destino, exist_ok=True)

    destino_path = os.path.join(destino, "AGENTS.md")

    try:
        with open(destino_path, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except OSError as exc:
        print("Erro ao escrever {0}: {1}".format(destino_path, exc), file=sys.stderr)
        return 1

    print("AGENTS.md gerado em {0}".format(destino_path))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Gera AGENTS.md no projeto alvo a partir do template Codex."
    )
    parser.add_argument("--projeto", required=True, help="Nome do projeto")
    parser.add_argument(
        "--verificacao", required=True, help="Comando de verificacao do projeto"
    )
    parser.add_argument(
        "--destino", default=".", help="Diretorio de destino (default: .)"
    )
    parser.add_argument(
        "--harness", default="codex", choices=["codex"],
        help="Harness alvo (atualmente apenas 'codex')"
    )

    args = parser.parse_args()

    return gerar_agents_md(args.projeto, args.verificacao, args.destino)


if __name__ == "__main__":
    sys.exit(main())
