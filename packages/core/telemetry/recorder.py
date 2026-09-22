"""Telemetry recorder: grava metricas de execucao de blocos em disco.

Registros sao acumulados em ``plano/metricas.json`` (schema 1), no formato
``{"schema": 1, "projeto": "...", "registros": [...]}``. Biblioteca pura: so
stdlib. Append-only — ``record()`` sempre le o arquivo existente e acrescenta
ao array ``registros``, nunca sobrescreve registros anteriores. Escrita
atomica via ``os.replace()``.

    from packages.core.telemetry import TelemetryRecorder
    rec = TelemetryRecorder()
    rec.record({"id": "F1", "veredito": "aprovado", "custo_usd": 0.01, "tentativas": 1})
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


class TelemetryError(Exception):
    """Erro de configuracao ou schema invalido em metricas.json."""


@dataclass
class TelemetryRecord:
    id: str
    modelo_planejado: "str | None" = None
    modelo_efetivo: "str | None" = None
    revisor_modelo: "str | None" = None
    turnos_orcados: "int | None" = None
    turnos_usados: "int | None" = None
    tentativas: "int | None" = None
    veredito: "str | None" = None
    commit_sha: "str | None" = None
    timestamp_inicio: "str | None" = None
    timestamp_fim: "str | None" = None
    tokens_in: "int | None" = None
    tokens_out: "int | None" = None
    custo_usd: "float | None" = None
    latencia_ms: "int | None" = None
    modelo_usado: "str | None" = None
    provider_usado: "str | None" = None
    cev: "float | None" = None
    resultado: "float | None" = None  # 1.0 se veredito=="aprovado", 0.0 se "reprovado", None se ausente


_FIELD_NAMES = [f.name for f in fields(TelemetryRecord)]


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


class TelemetryRecorder:
    """Grava e le metricas de execucao de blocos em ``plano/metricas.json``."""

    def __init__(
        self,
        metricas_path: "Path | str | None" = None,
        root: "Path | str | None" = None,
    ):
        self.root = Path(root) if root is not None else _default_root()
        if metricas_path is not None:
            self.metricas_path = Path(metricas_path)
        else:
            self.metricas_path = self.root / "plano" / "metricas.json"

    # -- helpers internos --------------------------------------------------

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + f".tmp-{os.getpid()}")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, path)  # I4: escrita atomica

    def _read_raw(self) -> dict:
        if not self.metricas_path.exists():
            return {"schema": 1, "projeto": None, "registros": []}
        with open(self.metricas_path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema") != 1:
            raise TelemetryError(
                "metricas.json com schema invalido: esperado 1, encontrado "
                f"{data.get('schema')!r}"
            )
        return data

    @staticmethod
    def _record_to_dict(record: TelemetryRecord) -> dict:
        d = asdict(record)
        # I2: campos ausentes nunca omitidos (asdict ja preserva todos os campos)
        return {name: d.get(name) for name in _FIELD_NAMES}

    # -- API publica ---------------------------------------------------------

    def compute_cev(
        self,
        veredito: "str | None",
        custo_usd: "float | None",
        tentativas: "int | None",
    ) -> "float | None":
        if custo_usd is None or tentativas is None:
            return None
        if custo_usd == 0 or tentativas == 0:
            return None
        # Apenas "aprovado" e "reprovado" são vereditos definidos.
        # veredito=None ou string desconhecida → resultado indefinido → cev=None.
        if veredito == "aprovado":
            resultado = 1.0
        elif veredito == "reprovado":
            resultado = 0.0
        else:
            return None
        return resultado / (custo_usd * tentativas)

    def record(self, data: dict) -> TelemetryRecord:
        payload = {k: v for k, v in data.items() if k in _FIELD_NAMES}
        record = TelemetryRecord(**payload)
        record.cev = self.compute_cev(
            record.veredito, record.custo_usd, record.tentativas
        )
        # resultado: 1.0 se aprovado, 0.0 se reprovado, None se veredito ausente
        if record.veredito == "aprovado":
            record.resultado = 1.0
        elif record.veredito == "reprovado":
            record.resultado = 0.0
        else:
            record.resultado = None

        raw = self._read_raw()
        raw.setdefault("schema", 1)
        raw.setdefault("projeto", None)
        raw.setdefault("registros", [])
        raw["registros"].append(self._record_to_dict(record))  # I1: append-only

        self._atomic_write(
            self.metricas_path, json.dumps(raw, indent=2, ensure_ascii=False) + "\n"
        )
        return record

    def load_all(self) -> "list[TelemetryRecord]":
        raw = self._read_raw()
        registros = raw.get("registros", [])
        result = []
        for reg in registros:
            payload = {k: v for k, v in reg.items() if k in _FIELD_NAMES}
            result.append(TelemetryRecord(**payload))
        return result

    def top_by_cost(self, n: int = 3) -> "list[TelemetryRecord]":
        records = self.load_all()
        with_cost = [r for r in records if r.custo_usd is not None]
        with_cost.sort(key=lambda r: r.custo_usd, reverse=True)
        return with_cost[:n]

    def average_cev(self) -> "float | None":
        records = self.load_all()
        valores = [r.cev for r in records if r.cev is not None]
        if not valores:
            return None
        return sum(valores) / len(valores)
