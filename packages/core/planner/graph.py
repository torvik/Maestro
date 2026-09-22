"""Algoritmos de grafo sobre o plano.

Funcoes puras (I1): recebem uma lista de dicts de blocos e devolvem listas de
ids. Nenhuma faz IO e nenhuma modifica a entrada (I2).

Aresta do grafo: `bloco -> dependencia`. Dependencias que apontam para ids
ausentes da lista sao ignoradas aqui — quem reporta isso e `validate_plan`.
"""

from typing import Any, Dict, List, Sequence, Tuple

__all__ = ["PlannerError", "detect_cycles", "topo_sort", "critical_path"]


class PlannerError(Exception):
    """Plano invalido ou operacao impossivel sobre o grafo do plano."""


def _extrai(item: Any) -> Tuple[str, List[str]]:
    """Le (id, depende_de) de um dict ou de um objeto tipo Block, sem mutar."""
    if isinstance(item, dict):
        bruto_id = item.get("id", "")
        deps = item.get("depende_de") or []
    else:
        bruto_id = getattr(item, "id", "")
        deps = getattr(item, "depende_de", None) or []
    if isinstance(deps, str):
        deps = [deps]
    return str(bruto_id), [str(d) for d in deps]


def _indexa(blocks: Sequence[Any]) -> Tuple[List[str], Dict[str, List[str]]]:
    """Devolve (ordem dos ids, mapa id -> deps existentes no proprio plano).

    Ids duplicados na entrada mantem apenas a primeira ocorrencia na ordem, mas
    as deps da ultima ocorrencia prevalecem — `validate_plan` rejeita duplicados
    antes de chegar aqui.
    """
    ordem: List[str] = []
    deps_por_id: Dict[str, List[str]] = {}
    for item in blocks:
        bloco_id, deps = _extrai(item)
        if bloco_id not in deps_por_id:
            ordem.append(bloco_id)
        deps_por_id[bloco_id] = deps
    conhecidos = set(deps_por_id)
    filtrado = {
        bloco_id: [d for d in deps if d in conhecidos]
        for bloco_id, deps in deps_por_id.items()
    }
    return ordem, filtrado


def detect_cycles(blocks: Sequence[Any]) -> List[List[str]]:
    """Detecta ciclos de dependencia via DFS com coloracao.

    branco = nao visitado, cinza = na pilha atual, preto = finalizado.
    Devolve uma lista de ciclos; cada ciclo e a lista minima de ids que fecham o
    loop, na ordem em que foram percorridos. Devolve `[]` se o grafo for acíclico.
    """
    ordem, deps_por_id = _indexa(blocks)

    BRANCO, CINZA, PRETO = 0, 1, 2
    cor: Dict[str, int] = {bloco_id: BRANCO for bloco_id in ordem}
    ciclos: List[List[str]] = []
    vistos = set()

    def registra(ciclo: List[str]) -> None:
        if not ciclo:
            return
        menor = min(range(len(ciclo)), key=lambda i: (ciclo[i], i))
        canonico = tuple(ciclo[menor:] + ciclo[:menor])
        if canonico in vistos:
            return
        vistos.add(canonico)
        ciclos.append(list(canonico))

    for raiz in ordem:
        if cor[raiz] != BRANCO:
            continue
        # DFS iterativa: pilha de (no, indice da proxima dep a visitar).
        pilha: List[List[Any]] = [[raiz, 0]]
        caminho: List[str] = [raiz]
        cor[raiz] = CINZA
        while pilha:
            no, i = pilha[-1]
            vizinhos = deps_por_id.get(no, [])
            if i < len(vizinhos):
                pilha[-1][1] = i + 1
                proximo = vizinhos[i]
                if cor.get(proximo, PRETO) == CINZA:
                    corte = caminho.index(proximo)
                    registra(caminho[corte:])
                elif cor.get(proximo, PRETO) == BRANCO:
                    cor[proximo] = CINZA
                    caminho.append(proximo)
                    pilha.append([proximo, 0])
            else:
                cor[no] = PRETO
                pilha.pop()
                caminho.pop()
    return ciclos


def topo_sort(blocks: Sequence[Any]) -> List[str]:
    """Ordem topologica (Kahn). Dependencias sempre antes dos dependentes.

    Desempate deterministico pela ordem de aparicao na entrada.
    Levanta `PlannerError` se houver ciclo.
    """
    ordem, deps_por_id = _indexa(blocks)
    posicao = {bloco_id: n for n, bloco_id in enumerate(ordem)}

    grau = {bloco_id: len(set(deps)) for bloco_id, deps in deps_por_id.items()}
    dependentes: Dict[str, List[str]] = {bloco_id: [] for bloco_id in ordem}
    for bloco_id, deps in deps_por_id.items():
        for dep in set(deps):
            dependentes[dep].append(bloco_id)

    prontos = sorted(
        [bloco_id for bloco_id in ordem if grau[bloco_id] == 0],
        key=lambda b: posicao[b],
    )
    resultado: List[str] = []
    while prontos:
        atual = prontos.pop(0)
        resultado.append(atual)
        novos = []
        for dependente in dependentes[atual]:
            grau[dependente] -= 1
            if grau[dependente] == 0:
                novos.append(dependente)
        if novos:
            prontos = sorted(prontos + novos, key=lambda b: posicao[b])

    if len(resultado) != len(ordem):
        ciclos = detect_cycles(blocks)
        if ciclos:
            raise PlannerError("ciclo detectado: %s" % (ciclos[0],))
        restantes = [b for b in ordem if b not in set(resultado)]
        raise PlannerError("ciclo detectado: %s" % (restantes,))
    return resultado


def critical_path(blocks: Sequence[Any]) -> List[str]:
    """Caminho critico = maior cadeia de dependencias, medida em numero de blocos.

    DP sobre a ordem topologica (DAG longest path). Sem pesos por complexidade.
    Devolve os ids em ordem de execucao (dependencia primeiro).
    Levanta `PlannerError` se houver ciclo.
    """
    ordem_topo = topo_sort(blocks)
    _, deps_por_id = _indexa(blocks)

    comprimento: Dict[str, int] = {}
    anterior: Dict[str, Any] = {}
    melhor_id = None
    for bloco_id in ordem_topo:
        maior = 0
        pai = None
        for dep in deps_por_id.get(bloco_id, []):
            if comprimento.get(dep, 0) > maior:
                maior = comprimento[dep]
                pai = dep
        comprimento[bloco_id] = maior + 1
        anterior[bloco_id] = pai
        if melhor_id is None or comprimento[bloco_id] > comprimento[melhor_id]:
            melhor_id = bloco_id

    if melhor_id is None:
        return []
    caminho: List[str] = []
    atual = melhor_id
    while atual is not None:
        caminho.append(atual)
        atual = anterior.get(atual)
    caminho.reverse()
    return caminho
