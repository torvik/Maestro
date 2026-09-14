"""Leitura e validacao de `blocos.json`.

Unico modulo do pacote que faz IO (I1). `validate_plan` e fail-closed: qualquer
problema estrutural vira `PlannerError` (I3). Problemas nao estruturais viram
advertencia em stderr e nao interrompem nada.
"""

import json
import os
import sys
from typing import Any, Dict, List, Tuple

from .graph import PlannerError, detect_cycles
from .model import Plan

__all__ = ["load_plan", "validate_plan"]


def _le_json(path) -> Any:
    """Le o arquivo e devolve o JSON decodificado, ou levanta PlannerError."""
    caminho = os.fspath(path)
    if not os.path.isfile(caminho):
        raise PlannerError("arquivo inválido: %s não existe" % caminho)
    try:
        with open(caminho, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise PlannerError("arquivo inválido: %s não é JSON válido (%s)" % (caminho, exc))
    except OSError as exc:
        raise PlannerError("arquivo inválido: %s não pôde ser lido (%s)" % (caminho, exc))


def _extrai_blocos(dados: Any) -> Tuple[List[Dict[str, Any]], str, str]:
    """Aceita lista raiz OU {"blocos": [...]}. Devolve (blocos, projeto, objetivo)."""
    if isinstance(dados, list):
        blocos = dados
        projeto = ""
        objetivo = ""
    elif isinstance(dados, dict) and isinstance(dados.get("blocos"), list):
        blocos = dados["blocos"]
        projeto = str(dados.get("projeto", "") or "")
        objetivo = str(dados.get("objetivo", "") or "")
    else:
        raise PlannerError("formato desconhecido: esperado lista ou {\"blocos\": [...]}")
    for item in blocos:
        if not isinstance(item, dict):
            raise PlannerError("formato desconhecido: bloco não é objeto (%r)" % (item,))
        if not item.get("id"):
            raise PlannerError("formato desconhecido: bloco sem campo 'id' (%r)" % (item,))
    return blocos, projeto, objetivo


def _checa_ids_unicos(blocos: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = [str(b.get("id")) for b in blocos]
    vistos = set()
    duplicados: List[str] = []
    for bloco_id in ids:
        if bloco_id in vistos and bloco_id not in duplicados:
            duplicados.append(bloco_id)
        vistos.add(bloco_id)
    if duplicados:
        raise PlannerError("ids duplicados: %s" % (duplicados,))
    return ids


def _checa_dependencias(blocos: List[Dict[str, Any]], ids: List[str]) -> None:
    conhecidos = set(ids)
    ausentes: Dict[str, List[str]] = {}
    for bloco in blocos:
        deps = bloco.get("depende_de") or []
        if isinstance(deps, str):
            deps = [deps]
        faltando = [str(d) for d in deps if str(d) not in conhecidos]
        if faltando:
            ausentes[str(bloco.get("id"))] = faltando
    if ausentes:
        raise PlannerError("dependências ausentes: %s" % (ausentes,))


def _avisa(blocos: List[Dict[str, Any]], caminho_plano: str) -> None:
    """Advertencias em stderr — nunca interrompem a validacao."""
    base = os.path.dirname(os.path.abspath(caminho_plano))
    raiz = os.path.dirname(base) or base
    for bloco in blocos:
        bloco_id = str(bloco.get("id"))
        spec = bloco.get("spec")
        if not spec:
            print("aviso: bloco %s sem spec" % bloco_id, file=sys.stderr)
        else:
            candidatos = [
                os.path.join(base, str(spec)),
                os.path.join(raiz, str(spec)),
                str(spec),
            ]
            if not any(os.path.isfile(c) for c in candidatos):
                print(
                    "aviso: bloco %s aponta para spec inexistente: %s" % (bloco_id, spec),
                    file=sys.stderr,
                )
        if bloco.get("estado") == "em_andamento":
            print(
                "aviso: bloco %s está em_andamento (sessão possivelmente interrompida)"
                % bloco_id,
                file=sys.stderr,
            )


def validate_plan(path) -> None:
    """Valida o plano em `path`. Levanta `PlannerError` se invalido, senao None.

    Ordem: arquivo legível -> formato -> ids únicos -> dependências existem ->
    sem ciclos. Advertências (spec ausente/inexistente, bloco em_andamento) vão
    para stderr e não invalidam o plano.
    """
    dados = _le_json(path)
    blocos, _projeto, _objetivo = _extrai_blocos(dados)
    ids = _checa_ids_unicos(blocos)
    _checa_dependencias(blocos, ids)
    ciclos = detect_cycles(blocos)
    if ciclos:
        raise PlannerError("ciclo detectado: %s" % (ciclos[0],))
    _avisa(blocos, os.fspath(path))


def load_plan(path) -> Plan:
    """Valida e devolve o `Plan` (L0/L1/L2) do arquivo em `path`."""
    validate_plan(path)
    dados = _le_json(path)
    blocos, projeto, objetivo = _extrai_blocos(dados)
    return Plan.from_blocks(blocos, projeto=projeto, objetivo=objetivo)
