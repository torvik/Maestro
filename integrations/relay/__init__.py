"""integrations/relay -- modo headless (CI/CD) e integracao Relay (F15-01).

Ver plano/specs/F15-01-cicd-relay.md.

  - headless.py      HeadlessRunner: executa scripts/maestro_run.py via
                      subprocess, sem interacao humana.
  - headless_cli.py   wrapper de linha de comando do modo headless.
  - adapter.py        RelayAdapter: STUB -- API do Relay ainda nao definida.

Docs: docs/integrations/cicd.md (headless + GitHub Actions),
docs/integrations/relay.md (Relay -- API em definicao).
"""

from integrations.relay.adapter import RelayAdapter, RelayTrigger
from integrations.relay.headless import (
    AUTONOMIA_HEADLESS,
    HeadlessResult,
    HeadlessRunner,
)

__all__ = [
    "RelayAdapter",
    "RelayTrigger",
    "HeadlessRunner",
    "HeadlessResult",
    "AUTONOMIA_HEADLESS",
]
