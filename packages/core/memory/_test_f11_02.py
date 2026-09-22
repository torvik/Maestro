"""Tests for F11-02: WorkingMemory and EpisodicMemory.

Run with: python packages/core/memory/_test_f11_02.py
"""
import sys
import os
import tempfile
import time

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print(f"  PASS  {name}")


def fail(name, reason):
    FAIL.append(name)
    print(f"  FAIL  {name}: {reason}")


def run_tests():
    # --- T1: Smoke test --- (CA11: sem I/O no import)
    try:
        from packages.core.memory import WorkingMemory, EpisodicMemory
        ok("T1-smoke-import")
    except Exception as e:
        fail("T1-smoke-import", e)
        return  # sem import, não tem como continuar

    from packages.core.memory import MemoryCore, MemoryError
    from packages.core.memory.working import extract_module

    def make_core(tmpdir):
        return MemoryCore(root=tmpdir)

    # === extract_module (T26) ===
    try:
        assert extract_module("F11-02") == "F11", extract_module("F11-02")
        assert extract_module("F3-02") == "F3"
        assert extract_module("F11") == "F11"
        assert extract_module("F3-02a") == "F3"
        assert extract_module("") == ""
        ok("T26-extract_module")
    except Exception as e:
        fail("T26-extract_module", e)

    # === WorkingMemory - criação ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        wm = WorkingMemory(core)

        # T2: create retorna UUID4, arquivo existe, frontmatter correto
        try:
            mid = wm.create(
                session_id="F11-02-test",
                bloco_id="F11-02",
                modelo_usado="claude-sonnet-4-6",
            )
            import re
            UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
            assert UUID4_RE.match(mid), f"Not UUID4: {mid}"
            path = os.path.join(tmpdir, "working", mid + ".md")
            assert os.path.exists(path), f"File not found: {path}"
            fm, _ = wm.get("F11-02-test")
            assert fm["type"] == "working"
            assert fm["authority"] == "session"
            assert fm["session_id"] == "F11-02-test"
            assert fm["bloco_id"] == "F11-02"
            assert fm["modelo_usado"] == "claude-sonnet-4-6"
            assert fm["status"] == "running"
            assert fm["pinned"] == False
            # decay_at = created_at + 24h
            from packages.core.memory.schema import parse_iso
            from datetime import timedelta
            created = parse_iso(fm["created_at"])
            decay = parse_iso(fm["decay_at"])
            diff = decay - created
            assert abs(diff.total_seconds() - 86400) < 5, f"decay diff: {diff}"
            ok("T2-create-working")
        except Exception as e:
            fail("T2-create-working", e)

        # T3: segunda criação com mesmo session_id levanta MemoryError
        try:
            raised = False
            try:
                wm.create(session_id="F11-02-test", bloco_id="F11-02", modelo_usado="claude-sonnet-4-6")
            except MemoryError:
                raised = True
            assert raised, "Expected MemoryError on duplicate session_id"
            # Apenas uma entrada
            actives = wm.list_active()
            sess = [x for x in actives if x.get("session_id") == "F11-02-test"]
            assert len(sess) == 1, f"Expected 1, got {len(sess)}"
            ok("T3-duplicate-session-error")
        except Exception as e:
            fail("T3-duplicate-session-error", e)

        # T4: session_id vazio levanta MemoryError
        try:
            raised = False
            try:
                wm.create(session_id="", bloco_id="F11-02", modelo_usado="x")
            except MemoryError:
                raised = True
            assert raised
            ok("T4-empty-session-id")
        except Exception as e:
            fail("T4-empty-session-id", e)

        # T5: session_id com / levanta MemoryError
        try:
            raised = False
            try:
                wm.create(session_id="F11/02", bloco_id="F11-02", modelo_usado="x")
            except MemoryError:
                raised = True
            assert raised
            ok("T5-slash-in-session-id")
        except Exception as e:
            fail("T5-slash-in-session-id", e)

        # T6: extra_frontmatter com campo protegido levanta MemoryError
        try:
            raised = False
            try:
                wm.create(
                    session_id="F11-02-test-t6",
                    bloco_id="F11-02",
                    modelo_usado="x",
                    extra_frontmatter={"type": "episodic"},
                )
            except MemoryError:
                raised = True
            assert raised
            ok("T6-protected-field-in-extra")
        except Exception as e:
            fail("T6-protected-field-in-extra", e)

        # === WorkingMemory - leitura e atualização ===

        # T7: get retorna frontmatter correto
        try:
            result = wm.get("F11-02-test")
            assert result is not None
            fm2, body2 = result
            assert fm2["status"] == "running"
            ok("T7-get-working")
        except Exception as e:
            fail("T7-get-working", e)

        # T8: update status
        try:
            wm.update("F11-02-test", updates={"status": "failed"})
            fm3, _ = wm.get("F11-02-test")
            assert fm3["status"] == "failed", f"Got {fm3['status']}"
            ok("T8-update-status")
        except Exception as e:
            fail("T8-update-status", e)

        # T9: update com campo protegido levanta MemoryError
        try:
            raised = False
            try:
                wm.update("F11-02-test", updates={"session_id": "outro"})
            except MemoryError:
                raised = True
            assert raised
            ok("T9-update-protected-field")
        except Exception as e:
            fail("T9-update-protected-field", e)

        # T10: get session inexistente retorna None
        try:
            result = wm.get("session-inexistente")
            assert result is None
            ok("T10-get-nonexistent")
        except Exception as e:
            fail("T10-get-nonexistent", e)

        # T11: list_active inclui a working criada
        try:
            actives = wm.list_active()
            sess = [x for x in actives if x.get("session_id") == "F11-02-test"]
            assert len(sess) == 1
            ok("T11-list-active")
        except Exception as e:
            fail("T11-list-active", e)

        core._index.close()

    # === EpisodicMemory - promoção ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        wm = WorkingMemory(core)
        em = EpisodicMemory(core)

        # Cria working para T12/T13
        w_mid = wm.create(
            session_id="F11-02-test",
            bloco_id="F11-02",
            modelo_usado="claude-sonnet-4-6",
            body="contexto da sessão",
        )

        # T12: promote retorna UUID4, episodic existe, working deletada
        try:
            e_mid = em.promote(
                session_id="F11-02-test",
                bloco_id="F11-02",
                resultado="success",
                duracao_segundos=42.5,
                modelo_usado="claude-sonnet-4-6",
            )
            import re
            UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
            assert UUID4_RE.match(e_mid), f"Not UUID4: {e_mid}"
            ep_path = os.path.join(tmpdir, "episodic", e_mid + ".md")
            assert os.path.exists(ep_path), f"Episodic file not found"
            # Working foi deletada
            assert wm.get("F11-02-test") is None, "Working should be deleted"
            ok("T12-promote-creates-episodic")
        except Exception as e:
            fail("T12-promote-creates-episodic", e)

        # T13: frontmatter da episodic
        try:
            result = em.get(e_mid)
            assert result is not None
            fm, body = result
            assert fm["type"] == "episodic", f"type={fm['type']}"
            assert fm["authority"] == "session"
            assert fm["bloco_id"] == "F11-02"
            assert fm["modulo"] == "F11"
            assert fm["resultado"] == "success"
            assert abs(float(fm["duracao_segundos"]) - 42.5) < 0.01
            assert fm["modelo_usado"] == "claude-sonnet-4-6"
            assert fm["source_block"] == "F11-02"
            assert fm["source_working_id"] == w_mid
            assert "findings" not in fm
            # Coluna module no SQLite
            conn = core._index.connection()
            row = conn.execute("SELECT module FROM memories WHERE id = ?", (e_mid,)).fetchone()
            assert row is not None
            assert row[0] == "F11", f"module in DB: {row[0]}"
            ok("T13-episodic-frontmatter")
        except Exception as e:
            fail("T13-episodic-frontmatter", e)

        # T14: resultado inválido levanta MemoryError
        try:
            raised = False
            try:
                em.promote(
                    session_id="x", bloco_id="F11-02", resultado="invalid",
                    duracao_segundos=1.0, modelo_usado="m",
                )
            except MemoryError:
                raised = True
            assert raised
            ok("T14-invalid-resultado")
        except Exception as e:
            fail("T14-invalid-resultado", e)

        # T15: duracao_segundos negativa levanta MemoryError
        try:
            raised = False
            try:
                em.promote(
                    session_id="x", bloco_id="F11-02", resultado="success",
                    duracao_segundos=-1, modelo_usado="m",
                )
            except MemoryError:
                raised = True
            assert raised
            ok("T15-negative-duracao")
        except Exception as e:
            fail("T15-negative-duracao", e)

        # T16: findings vazio levanta MemoryError
        try:
            raised = False
            try:
                em.promote(
                    session_id="x2", bloco_id="F11-02", resultado="success",
                    duracao_segundos=1.0, modelo_usado="m", findings="",
                )
            except MemoryError:
                raised = True
            assert raised
            ok("T16-empty-findings")
        except Exception as e:
            fail("T16-empty-findings", e)

        # T17: findings appendado ao body, não ao frontmatter
        try:
            wm.create(session_id="sess-t17", bloco_id="F11-02", modelo_usado="m")
            eid = em.promote(
                session_id="sess-t17",
                bloco_id="F11-02",
                resultado="success",
                duracao_segundos=1.0,
                modelo_usado="m",
                findings="Revisor aprovou sem ressalvas",
            )
            fm, body = em.get(eid)
            assert "## Findings\nRevisor aprovou sem ressalvas" in body, f"body={body!r}"
            assert "findings" not in fm
            ok("T17-findings-in-body")
        except Exception as e:
            fail("T17-findings-in-body", e)

        # T18: promote sem working existente cria episodic com source_working_id=null
        try:
            eid2 = em.promote(
                session_id="sessao-nunca-criada",
                bloco_id="F3-01",
                resultado="failure",
                duracao_segundos=0.0,
                modelo_usado="m",
            )
            fm2, _ = em.get(eid2)
            assert fm2 is not None
            assert fm2.get("source_working_id") is None
            ok("T18-promote-without-working")
        except Exception as e:
            fail("T18-promote-without-working", e)

        # T19: atomicidade - falha na criação não deleta working
        try:
            wm.create(session_id="sess-t19", bloco_id="F11-02", modelo_usado="m")
            raised = False
            try:
                # bloco_id=None deve causar erro de validação antes de criar episodic
                em.promote(
                    session_id="sess-t19",
                    bloco_id=None,
                    resultado="success",
                    duracao_segundos=1.0,
                    modelo_usado="m",
                )
            except (MemoryError, Exception):
                raised = True
            assert raised, "Expected error"
            # Working ainda deve existir
            assert wm.get("sess-t19") is not None, "Working was deleted despite failure"
            ok("T19-atomicity")
        except Exception as e:
            fail("T19-atomicity", e)

        core._index.close()

    # === EpisodicMemory - consulta ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        wm = WorkingMemory(core)
        em = EpisodicMemory(core)

        # Cria algumas episodics
        ids = []
        for i in range(3):
            eid = em.promote(
                session_id=f"s{i}",
                bloco_id=f"F11-0{i+1}",
                resultado="success",
                duracao_segundos=float(i),
                modelo_usado="m",
            )
            ids.append(eid)
        # Uma do módulo F3
        f3_eid = em.promote(
            session_id="sF3",
            bloco_id="F3-01",
            resultado="failure",
            duracao_segundos=5.0,
            modelo_usado="m",
        )

        # T20: list_by_module
        try:
            results = em.list_by_module("F11", limit=5)
            assert len(results) <= 5
            assert all(r["modulo"] == "F11" for r in results), [r.get("modulo") for r in results]
            # Verifica ordenação DESC por created_at
            dates = [r["created_at"] for r in results]
            assert dates == sorted(dates, reverse=True), f"Not sorted DESC: {dates}"
            ok("T20-list-by-module")
        except Exception as e:
            fail("T20-list-by-module", e)

        # T21: list_by_bloco
        try:
            results = em.list_by_bloco("F11-01")
            assert len(results) >= 1
            assert all(r["source_block"] == "F11-01" for r in results)
            # Verifica ordenação DESC por created_at
            dates = [r["created_at"] for r in results]
            assert dates == sorted(dates, reverse=True), f"Not sorted DESC: {dates}"
            ok("T21-list-by-bloco")
        except Exception as e:
            fail("T21-list-by-bloco", e)

        # T22: list_recent
        try:
            results = em.list_recent(limit=3)
            assert len(results) <= 3
            # Verifica ordenação DESC por created_at
            dates = [r["created_at"] for r in results]
            assert dates == sorted(dates, reverse=True), f"Not sorted DESC: {dates}"
            ok("T22-list-recent")
        except Exception as e:
            fail("T22-list-recent", e)

        # T23: list_recent com filtros
        try:
            results = em.list_recent(modulo="F11", resultado="success")
            assert all(r["modulo"] == "F11" for r in results)
            assert all(r["resultado"] == "success" for r in results)
            ok("T23-list-recent-filtered")
        except Exception as e:
            fail("T23-list-recent-filtered", e)

        core._index.close()

    # === Performance T24/T25 ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        em = EpisodicMemory(core)

        # T24: 1000 episodics, list_by_module < 50ms
        try:
            for i in range(1000):
                em.promote(
                    session_id=f"perf-{i}",
                    bloco_id=f"F11-{i:04d}",
                    resultado="success",
                    duracao_segundos=float(i),
                    modelo_usado="m",
                )
            # Verifica que coluna module contém "F11" para todas as 1000 entradas
            conn = core._index.connection()
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE type = 'episodic'"
            ).fetchone()[0]
            assert total == 1000, f"Expected 1000 episodics, got {total}"
            wrong = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE type = 'episodic' AND module != 'F11'"
            ).fetchone()[0]
            assert wrong == 0, f"{wrong} entries without module='F11'"
            t0 = time.monotonic()
            results = em.list_by_module("F11", limit=10)
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"         list_by_module(1000 entries): {elapsed_ms:.1f}ms")
            assert elapsed_ms < 50, f"Too slow: {elapsed_ms:.1f}ms"
            assert len(results) <= 10
            ok("T24-performance-list-by-module")
        except Exception as e:
            fail("T24-performance-list-by-module", e)

        # T25: list_by_bloco 100 entries < 50ms
        try:
            for i in range(100):
                em.promote(
                    session_id=f"bloco-{i}",
                    bloco_id="F99-01",
                    resultado="success",
                    duracao_segundos=1.0,
                    modelo_usado="m",
                )
            t0 = time.monotonic()
            results = em.list_by_bloco("F99-01")
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"         list_by_bloco(100 entries): {elapsed_ms:.1f}ms")
            assert elapsed_ms < 50, f"Too slow: {elapsed_ms:.1f}ms"
            ok("T25-performance-list-by-bloco")
        except Exception as e:
            fail("T25-performance-list-by-bloco", e)

        core._index.close()

    # === Decay T27/T28 ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        wm = WorkingMemory(core)
        em = EpisodicMemory(core)

        # T27: working expirada não é "ativa"
        try:
            from packages.core.memory.schema import now_iso, parse_iso
            from datetime import datetime, timezone, timedelta

            mid = wm.create(session_id="expired-sess", bloco_id="F11-02", modelo_usado="m")
            # Força decay_at para o passado via patch
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            core.patch(mid, {"decay_at": past})
            result = wm.get("expired-sess")
            assert result is None, f"Expected None for expired working, got {result}"
            actives = wm.list_active()
            assert not any(x.get("session_id") == "expired-sess" for x in actives)
            ok("T27-expired-working-not-active")
        except Exception as e:
            fail("T27-expired-working-not-active", e)

        # T28: episodic expirada
        try:
            from datetime import datetime, timezone, timedelta
            eid = em.promote(
                session_id="exp-ep",
                bloco_id="F11-02",
                resultado="success",
                duracao_segundos=1.0,
                modelo_usado="m",
            )
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            core.patch(eid, {"decay_at": past})
            r1 = em.list_by_module("F11", include_expired=False)
            assert not any(x.get("id") == eid for x in r1), "Expired should not appear"
            r2 = em.list_by_module("F11", include_expired=True)
            assert any(x.get("id") == eid for x in r2), "Expired should appear with include_expired=True"
            ok("T28-expired-episodic")
        except Exception as e:
            fail("T28-expired-episodic", e)

        core._index.close()

    # === CA9/CA10 via T14/T15 already covered ===
    # === CA12: sem dependência externa - implícito pelo uso de stdlib only ===

    # Summary
    print(f"\n{'='*50}")
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()
