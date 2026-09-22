"""Telemetria do Maestro: grava metricas de execucao de blocos em disco.

Registros de execucao (turnos, tentativas, custo, veredito, CEV) sao
acumulados em ``plano/metricas.json``. Biblioteca pura: so stdlib.
Append-only — ``record()`` nunca sobrescreve registros existentes.

    from packages.core.telemetry import TelemetryRecorder
    rec = TelemetryRecorder()
    rec.record({"id": "F1", "veredito": "aprovado", "custo_usd": 0.01, "tentativas": 1})
"""

from .recorder import TelemetryError, TelemetryRecord, TelemetryRecorder

__all__ = [
    "TelemetryRecorder",
    "TelemetryRecord",
    "TelemetryError",
]
