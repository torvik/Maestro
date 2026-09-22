#!/usr/bin/env python3
"""Complexity Engine: classificação C1-C5 desacoplada de nomes de modelos.

Classifica um bloco de trabalho em um nível de complexidade (C1 a C5) e
retorna os requisitos de execução associados (raciocínio, contexto,
capacidade de codificação, autonomia, risco, necessidade de revisão e
recomendação de isolamento). A classificação é puramente estrutural: não
há qualquer referência a nomes de modelos de IA neste módulo — a escolha
de qual modelo usar para cada nível é decidida em outra camada, fora
deste arquivo.

Uso via CLI:
  python scripts/maestro_complexity.py --classify '{"complexidade": "C3"}'
  python scripts/maestro_complexity.py --show
  python scripts/maestro_complexity.py
"""

import argparse
import json
import sys

LEVELS = ("C1", "C2", "C3", "C4", "C5")

_BASE_REQUIREMENTS = {
    "C1": {
        "reasoning": "low",
        "context": "low",
        "coding": "low",
        "autonomy": "high",
        "risk": "low",
        "review_required": False,
        "isolation_recommended": False,
    },
    "C2": {
        "reasoning": "low",
        "context": "low",
        "coding": "medium",
        "autonomy": "high",
        "risk": "low",
        "review_required": False,
        "isolation_recommended": False,
    },
    "C3": {
        "reasoning": "medium",
        "context": "medium",
        "coding": "medium",
        "autonomy": "medium",
        "risk": "medium",
        "review_required": False,
        "isolation_recommended": False,
    },
    "C4": {
        "reasoning": "high",
        "context": "medium",
        "coding": "high",
        "autonomy": "low",
        "risk": "high",
        "review_required": True,
        "isolation_recommended": False,
    },
    "C5": {
        "reasoning": "high",
        "context": "high",
        "coding": "high",
        "autonomy": "low",
        "risk": "high",
        "review_required": True,
        "isolation_recommended": True,
    },
}


class ComplexityError(Exception):
    """Erro de classificação de complexidade."""


def requirements(level: str) -> dict:
    """Retorna os requisitos base (dict com 7 campos) para um nível C1-C5."""
    if level not in LEVELS:
        raise ComplexityError(f"nível '{level}' inválido; esperado: C1–C5")
    return dict(_BASE_REQUIREMENTS[level])


def classify(block: dict) -> dict:
    """Classifica um bloco em um nível de complexidade e seus requisitos.

    `block` deve conter o campo 'complexidade' com um valor em C1..C5.
    Ajustes opcionais (nunca rebaixam campos; C5 é imutável quanto a
    review_required/isolation_recommended):
      - risco == "alto"/"high" -> risk="high", review_required=True
      - arquivos_permitidos com mais de 10 itens -> context="high",
        isolation_recommended=True
      - bloqueado_por não vazio -> registrado em 'adjustments' (sem
        alterar requirements)
    """
    if not isinstance(block, dict) or "complexidade" not in block:
        raise ComplexityError("campo 'complexidade' ausente")

    level = block["complexidade"]
    if level not in LEVELS:
        raise ComplexityError(f"nível '{level}' inválido; esperado: C1–C5")

    reqs = requirements(level)
    adjustments = []

    risco = block.get("risco")
    if isinstance(risco, str) and risco.strip().lower() in ("alto", "high"):
        if reqs["risk"] != "high":
            reqs["risk"] = "high"
            adjustments.append("risco alto: risk -> high")
        if not reqs["review_required"]:
            reqs["review_required"] = True
            adjustments.append("risco alto: review_required -> True")

    arquivos_permitidos = block.get("arquivos_permitidos")
    if isinstance(arquivos_permitidos, list) and len(arquivos_permitidos) > 10:
        if reqs["context"] != "high":
            reqs["context"] = "high"
            adjustments.append("arquivos_permitidos > 10: context -> high")
        if not reqs["isolation_recommended"]:
            reqs["isolation_recommended"] = True
            adjustments.append("arquivos_permitidos > 10: isolation_recommended -> True")

    bloqueado_por = block.get("bloqueado_por")
    if isinstance(bloqueado_por, str) and bloqueado_por.strip() != "":
        adjustments.append("bloqueado_por presente")

    # C5 imutável: ajustes nunca removem review_required/isolation_recommended.
    if level == "C5":
        reqs["review_required"] = True
        reqs["isolation_recommended"] = True

    return {
        "level": level,
        "requirements": reqs,
        "adjustments": adjustments,
    }


def _print_show() -> None:
    for level in LEVELS:
        print(f"{level}: {json.dumps(requirements(level), ensure_ascii=False)}")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv:
        print(__doc__)
        return 0

    parser = argparse.ArgumentParser(
        prog="maestro_complexity.py",
        description="Complexity Engine: classificação C1-C5.",
        add_help=True,
    )
    parser.add_argument("--classify", metavar="JSON", help="Classifica um bloco (JSON)")
    parser.add_argument("--show", action="store_true", help="Imprime tabela de todos os níveis")
    args = parser.parse_args(argv)

    if args.show:
        _print_show()
        return 0

    if args.classify is not None:
        try:
            block = json.loads(args.classify)
        except json.JSONDecodeError as e:
            print(f"Erro: JSON inválido — {e}", file=sys.stderr)
            return 2
        try:
            result = classify(block)
        except ComplexityError as exc:
            print(f"ComplexityError: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
