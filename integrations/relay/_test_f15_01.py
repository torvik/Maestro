"""Tests for F15-01 -- CI/CD headless e Relay integration (stub).

Stdlib only, no pytest. Run:

    python integrations/relay/_test_f15_01.py

Prints ALL TESTS PASSED and exits 0 when the contract holds.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from integrations.relay.adapter import RelayAdapter, RelayTrigger  # noqa: E402
from integrations.relay.headless import (  # noqa: E402
    AUTONOMIA_HEADLESS,
    HeadlessRunner,
)
import headless_cli  # noqa: E402
from packages.core.protocol import UEP, EventType, UCPEvent  # noqa: E402

CONFIG_PATH = os.path.join(_ROOT, "maestro.config.json")
BLOCOS_PATH = os.path.join(_ROOT, "plano", "blocos.json")

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# T01 -- headless_cli --headless --dry-run F0-01 -> exit 0
# ---------------------------------------------------------------------------


def test_t01_headless_dry_run_exit_zero():
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = headless_cli.main(["--headless", "--dry-run", "F0-01"])
    check("T01 headless_cli --headless --dry-run F0-01 -> exit 0", code == 0, f"code={code} stderr={err.getvalue()!r}")
    check("T01 saida contem manifest do bloco", '"block_id": "F0-01"' in out.getvalue())


# ---------------------------------------------------------------------------
# T02 -- modo headless nunca chama input()
# ---------------------------------------------------------------------------


def test_t02_never_calls_input():
    original_input = builtins.input

    def _boom(*a, **k):
        raise AssertionError("input() foi chamado em modo headless")

    builtins.input = _boom
    try:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = headless_cli.main(["--headless", "--dry-run", "F0-01"])
        check("T02 dry-run headless nao chama input()", code == 0)

        # Tambem cobre o caminho de erro (uso invalido) -- nao deve chamar
        # input() mesmo quando falta argumento.
        out2 = io.StringIO()
        err2 = io.StringIO()
        with redirect_stdout(out2), redirect_stderr(err2):
            code2 = headless_cli.main(["--headless"])
        check("T02 uso invalido tambem nao chama input()", code2 == 2)
    finally:
        builtins.input = original_input


# ---------------------------------------------------------------------------
# T03 -- RelayAdapter.receive_trigger nunca levanta
# ---------------------------------------------------------------------------


def test_t03_receive_trigger_never_raises():
    adapter = RelayAdapter()
    try:
        ack1 = adapter.receive_trigger({})
        ack2 = adapter.receive_trigger(None)
        ack3 = adapter.receive_trigger({"trigger_id": "T-1", "block_id": "F15-01", "source": "manual"})
        ack4 = adapter.receive_trigger("nao e um dict")  # type: ignore[arg-type]
        raised = False
    except Exception:
        raised = True
        ack1 = ack2 = ack3 = ack4 = None

    check("T03 receive_trigger nunca levanta", not raised)
    check("T03 receive_trigger({}) devolve ack True", bool(ack1) and ack1.get("ack") is True)
    check("T03 receive_trigger(None) devolve ack True", bool(ack2) and ack2.get("ack") is True)
    check(
        "T03 receive_trigger com payload valido preserva block_id",
        bool(ack3) and ack3.get("block_id") == "F15-01",
    )
    check("T03 receive_trigger com tipo invalido nao levanta", bool(ack4) and ack4.get("ack") is True)


# ---------------------------------------------------------------------------
# T04 -- RelayAdapter.publish_event nunca levanta
# ---------------------------------------------------------------------------


def test_t04_publish_event_never_raises():
    adapter = RelayAdapter()

    stream = UEP(block_id="F15-01")
    event = stream.emit(EventType.BLOCK_STARTED)

    raised = False
    try:
        adapter.publish_event(event)
        adapter.publish_event(event.to_dict())
        adapter.publish_event({"garbage": True})  # sem event_type/block_id -> from_dict levanta, capturado
        adapter.publish_event(object())
        adapter.publish_event(None)
    except Exception:
        raised = True

    check("T04 publish_event nunca levanta", not raised)
    check(
        "T04 publish_event registrou os eventos validos em memoria",
        len(adapter.published) >= 2 and isinstance(adapter.published[0], UCPEvent),
    )


# ---------------------------------------------------------------------------
# T05 -- effective_autonomia == "auto", maestro.config.json nao e alterado
# ---------------------------------------------------------------------------


def test_t05_autonomia_forcada_em_memoria():
    antes = _read_bytes(CONFIG_PATH)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg_antes = json.load(f)

    runner = HeadlessRunner()
    check("T05 effective_autonomia() == 'auto'", runner.effective_autonomia() == "auto")
    check("T05 AUTONOMIA_HEADLESS == 'auto'", AUTONOMIA_HEADLESS == "auto")

    depois = _read_bytes(CONFIG_PATH)
    check("T05 maestro.config.json nao foi escrito", antes == depois)
    check(
        "T05 autonomia no disco continua a original",
        cfg_antes.get("autonomia") == "parar_a_cada_bloco",
    )


# ---------------------------------------------------------------------------
# T06 -- block_pending_question constroi finish --fail --motivo, sem subprocess real
# ---------------------------------------------------------------------------


def test_t06_block_pending_question_sem_tocar_plano_real():
    chamadas = []

    class _FakeCompleted:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def _fake_runner(args):
        chamadas.append(list(args))
        return _FakeCompleted()

    antes = _read_bytes(BLOCOS_PATH)

    runner = HeadlessRunner(runner=_fake_runner)
    resultado = runner.block_pending_question("F15-01", "spec ambigua, precisa de decisao humana", fase="F15")

    depois = _read_bytes(BLOCOS_PATH)

    check("T06 exatamente uma chamada ao runner injetado", len(chamadas) == 1)
    check(
        "T06 argumentos == finish <id> --fail --motivo <texto> --fase <fase>",
        chamadas and chamadas[0] == [
            "finish", "F15-01", "--fail", "--motivo",
            "spec ambigua, precisa de decisao humana", "--fase", "F15",
        ],
    )
    check("T06 blocked_reason no resultado bate com o motivo", resultado.blocked_reason == "spec ambigua, precisa de decisao humana")
    check("T06 resultado.ok reflete returncode 0", resultado.ok is True)
    check("T06 plano/blocos.json real nao foi tocado", antes == depois)

    # motivo vazio deve falhar cedo (ValueError), sem chamar o runner.
    chamadas.clear()
    raised = False
    try:
        runner.block_pending_question("F15-01", "   ")
    except ValueError:
        raised = True
    check("T06 motivo vazio levanta ValueError sem chamar runner", raised and len(chamadas) == 0)


# ---------------------------------------------------------------------------
# T07 -- RelayTrigger.from_dict tolerante
# ---------------------------------------------------------------------------


def test_t07_relay_trigger_tolerante():
    raised = False
    try:
        t1 = RelayTrigger.from_dict(None)
        t2 = RelayTrigger.from_dict({})
        t3 = RelayTrigger.from_dict({"block_id": "F15-01"})
        t4 = RelayTrigger.from_dict("nao e dict")  # type: ignore[arg-type]
        t5 = RelayTrigger.from_dict({"payload": "nao e dict"})
    except Exception:
        raised = True
        t1 = t2 = t3 = t4 = t5 = None

    check("T07 from_dict nunca levanta", not raised)
    check("T07 from_dict(None) -> campos vazios", t1 is not None and t1.block_id == "" and t1.payload == {})
    check("T07 from_dict({}) -> campos vazios", t2 is not None and t2.trigger_id == "")
    check("T07 from_dict preserva block_id valido", t3 is not None and t3.block_id == "F15-01")
    check("T07 from_dict com tipo invalido nao levanta", t4 is not None and t4.block_id == "")
    check("T07 payload invalido vira dict vazio", t5 is not None and t5.payload == {})


# ---------------------------------------------------------------------------
# T08 -- artefatos de CI/CD e docs existem com os marcadores esperados
# ---------------------------------------------------------------------------


def test_t08_artefatos_existem():
    workflow_path = os.path.join(_ROOT, ".github", "workflows", "maestro-ci.yml")
    cicd_doc = os.path.join(_ROOT, "docs", "integrations", "cicd.md")
    relay_doc = os.path.join(_ROOT, "docs", "integrations", "relay.md")

    check("T08 workflow .github/workflows/maestro-ci.yml existe", os.path.exists(workflow_path))
    check("T08 docs/integrations/cicd.md existe", os.path.exists(cicd_doc))
    check("T08 docs/integrations/relay.md existe", os.path.exists(relay_doc))

    if os.path.exists(workflow_path):
        texto = open(workflow_path, encoding="utf-8").read()
        check("T08 workflow contem 'maestro_next.py --run'", "maestro_next.py --run" in texto)
        check("T08 workflow contem 'workflow_dispatch'", "workflow_dispatch" in texto)
        check("T08 workflow contem 'actions/checkout'", "actions/checkout" in texto)
        check("T08 workflow contem 'actions/setup-python'", "actions/setup-python" in texto)

    if os.path.exists(cicd_doc):
        texto = open(cicd_doc, encoding="utf-8").read()
        check("T08 cicd.md menciona headless_cli.py", "headless_cli.py" in texto)
        check("T08 cicd.md menciona autonomia auto", "\"auto\"" in texto or "'auto'" in texto)

    if os.path.exists(relay_doc):
        texto = open(relay_doc, encoding="utf-8").read()
        check("T08 relay.md documenta que e stub", "stub" in texto.lower())
        check("T08 relay.md menciona API do Relay nao definida", "não definida" in texto or "nao definida" in texto)


# ---------------------------------------------------------------------------


def main():
    test_t01_headless_dry_run_exit_zero()
    test_t02_never_calls_input()
    test_t03_receive_trigger_never_raises()
    test_t04_publish_event_never_raises()
    test_t05_autonomia_forcada_em_memoria()
    test_t06_block_pending_question_sem_tocar_plano_real()
    test_t07_relay_trigger_tolerante()
    test_t08_artefatos_existem()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} TESTE(S) FALHARAM: {', '.join(FAILURES)}")
        sys.exit(1)
    print("ALL TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
