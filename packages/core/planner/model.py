"""Modelo de dados L0/L1/L2 do Planner.

- L0: `Plan` (projeto, objetivo)
- L1: `Phase` (agrupamento por prefixo de id, ex.: "F0", "F10")
- L2: `Block` (unidade executavel do grafo)

Este modulo nao faz IO e nao importa nada fora da stdlib.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["Block", "Phase", "Plan", "fase_do_id"]


def fase_do_id(block_id: str) -> str:
    """Deriva o id da fase a partir do id do bloco.

    Regra: tudo antes do ultimo "-". `"F0-01"` -> `"F0"`, `"F10-03"` -> `"F10"`.
    Se nao houver "-", a fase e o proprio id.
    """
    texto = str(block_id)
    if "-" not in texto:
        return texto
    return texto.rsplit("-", 1)[0]


def _ordem_da_fase(phase_id: str):
    """Chave de ordenacao natural: F0 < F2 < F9 < F10 (nao lexicografica)."""
    digitos = "".join(ch for ch in phase_id if ch.isdigit())
    prefixo = "".join(ch for ch in phase_id if not ch.isdigit())
    if digitos:
        return (0, prefixo, int(digitos), phase_id)
    return (1, phase_id, 0, phase_id)


@dataclass
class Block:
    """L2 — bloco executavel. `raw` preserva o dict original, sem mutacao."""

    id: str
    titulo: str
    fase: str
    complexidade: str
    estado: str
    depende_de: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, dados: Dict[str, Any]) -> "Block":
        """Constroi um Block a partir de um dict do plano.

        Nao modifica `dados`: `raw` guarda uma copia rasa e `depende_de` uma
        lista nova (I2).
        """
        block_id = str(dados.get("id", ""))
        fase = dados.get("fase") or fase_do_id(block_id)
        deps = dados.get("depende_de") or []
        if isinstance(deps, str):
            deps = [deps]
        return cls(
            id=block_id,
            titulo=str(dados.get("titulo", "")),
            fase=str(fase),
            complexidade=str(dados.get("complexidade", "")),
            estado=str(dados.get("estado", "")),
            depende_de=[str(d) for d in deps],
            raw=dict(dados),
        )


@dataclass
class Phase:
    """L1 — fase: conjunto de blocos que compartilham o mesmo prefixo de id."""

    id: str
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Plan:
    """L0 — plano completo, com as fases ja ordenadas."""

    projeto: str = ""
    objetivo: str = ""
    phases: List[Phase] = field(default_factory=list)

    def all_blocks(self) -> List[Block]:
        """Todos os blocos, na ordem das fases."""
        return [b for fase in self.phases for b in fase.blocks]

    def block_by_id(self, id: str) -> Optional[Block]:
        """Bloco com o id informado, ou None se nao existir."""
        for fase in self.phases:
            for bloco in fase.blocks:
                if bloco.id == id:
                    return bloco
        return None

    def to_blocks(self) -> List[Dict[str, Any]]:
        """Reexporta os dicts originais dos blocos (schema-blocos.md).

        Devolve copias rasas; alterar o resultado nao afeta o `Plan`.
        """
        return [dict(b.raw) for b in self.all_blocks()]

    @classmethod
    def from_blocks(
        cls,
        blocos: List[Dict[str, Any]],
        projeto: str = "",
        objetivo: str = "",
    ) -> "Plan":
        """Agrupa uma lista de dicts em fases ordenadas naturalmente."""
        por_fase: Dict[str, List[Block]] = {}
        ordem_aparicao: List[str] = []
        for dados in blocos:
            bloco = Block.from_dict(dados)
            if bloco.fase not in por_fase:
                por_fase[bloco.fase] = []
                ordem_aparicao.append(bloco.fase)
            por_fase[bloco.fase].append(bloco)
        fases_ordenadas = sorted(ordem_aparicao, key=_ordem_da_fase)
        return cls(
            projeto=projeto,
            objetivo=objetivo,
            phases=[Phase(id=f, blocks=por_fase[f]) for f in fases_ordenadas],
        )
