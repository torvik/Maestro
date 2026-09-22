"""Planner do Maestro: analise do plano como grafo, antes de qualquer execucao.

Tres niveis de planejamento:

- **L0** — `Plan`: projeto e objetivo global.
- **L1** — `Phase`: blocos agrupados por prefixo do id ("F0", "F10", ...).
- **L2** — blocos executaveis, acessiveis por `plan.all_blocks()`.

    from packages.core.planner import load_plan, validate_plan, critical_path

    validate_plan("plano/blocos.json")          # levanta PlannerError se invalido
    plano = load_plan("plano/blocos.json")
    critical_path([b.raw for b in plano.all_blocks()])

Biblioteca pura: so stdlib, sem estado global, sem AI. `detect_cycles`,
`topo_sort` e `critical_path` nao fazem IO e nao modificam a entrada.
Importar este pacote nao produz output nem executa IO.
"""

from .graph import PlannerError, critical_path, detect_cycles, topo_sort
from .loader import load_plan, validate_plan
from .model import Phase, Plan

__all__ = [
    "PlannerError",
    "load_plan",
    "validate_plan",
    "detect_cycles",
    "critical_path",
    "topo_sort",
    "Plan",
    "Phase",
]
