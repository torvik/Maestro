"""Tests for F11-03: SemanticMemory and ProceduralMemory.

Run with: python packages/core/memory/_test_f11_03.py
"""
import sys
import os
import tempfile

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
    # --- T1: Smoke test ---
    try:
        from packages.core.memory import SemanticMemory, ProceduralMemory
        ok("T1-smoke-import")
    except Exception as e:
        fail("T1-smoke-import", e)
        return

    from packages.core.memory import MemoryCore

    def make_core(tmpdir):
        return MemoryCore(root=tmpdir)

    # === SemanticMemory - schema + FTS5 ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        sm = SemanticMemory(core)

        # T2: ensure_schema cria tabelas, idempotente
        try:
            sm.ensure_schema()
            sm.ensure_schema()  # segunda chamada não deve levantar erro
            conn = core._index.connection()
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                ).fetchall()
            }
            assert "ext_fts" in tables, tables
            assert "ext_entities" in tables, tables
            assert "ext_entity_links" in tables, tables
            ok("T2-ensure-schema")
        except Exception as e:
            fail("T2-ensure-schema", e)

        # T3: index_memory + search
        try:
            mid = "11111111-1111-1111-1111-111111111111"
            sm.index_memory(mid, "def foo(): pass")
            results = sm.search("foo")
            assert len(results) >= 1, results
            assert any(r["memory_id"] == mid for r in results), results
            ok("T3-index-and-search")
        except Exception as e:
            fail("T3-index-and-search", e)

        # T4: search("") retorna [] sem erro
        try:
            results = sm.search("")
            assert results == []
            ok("T4-empty-search")
        except Exception as e:
            fail("T4-empty-search", e)

        # T5: index_all com diretório vazio retorna 0
        try:
            count = sm.index_all()
            assert count == 0, count
            ok("T5-index-all-empty")
        except Exception as e:
            fail("T5-index-all-empty", e)

        # T5b: index_all com diretório inexistente não falha
        try:
            core2 = MemoryCore(root=os.path.join(tmpdir, "does-not-exist"))
            sm2 = SemanticMemory(core2)
            count2 = sm2.index_all()
            assert count2 == 0, count2
            ok("T5b-index-all-missing-dir")
        except Exception as e:
            fail("T5b-index-all-missing-dir", e)
        finally:
            try:
                core2._index.close()
            except Exception:
                pass

        # === Entidades e links ===

        # T6: add_entity retorna string não vazia
        try:
            eid1 = sm.add_entity(mid, "function", "foo")
            assert isinstance(eid1, str) and len(eid1) > 0
            ok("T6-add-entity")
        except Exception as e:
            fail("T6-add-entity", e)

        # T7: entities_for_memory retorna lista com a entidade
        try:
            ents = sm.entities_for_memory(mid)
            assert any(e["id"] == eid1 and e["name"] == "foo" for e in ents), ents
            ok("T7-entities-for-memory")
        except Exception as e:
            fail("T7-entities-for-memory", e)

        # T8: add_link + links_for_entity
        try:
            eid2 = sm.add_entity(mid, "function", "bar")
            lid = sm.add_link(eid1, eid2, "calls")
            assert isinstance(lid, str) and len(lid) > 0
            links = sm.links_for_entity(eid1)
            assert any(l["id"] == lid for l in links), links
            ok("T8-add-link-and-query")
        except Exception as e:
            fail("T8-add-link-and-query", e)

        # T15: vectors_available retorna bool sem erro
        try:
            avail = sm.vectors_available()
            assert isinstance(avail, bool)
            ok("T15-vectors-available")
        except Exception as e:
            fail("T15-vectors-available", e)

        # T16: index_embedding retorna bool sem levantar exceção
        try:
            result = sm.index_embedding(mid, "texto de teste")
            assert isinstance(result, bool)
            ok("T16-index-embedding-no-crash")
        except Exception as e:
            fail("T16-index-embedding-no-crash", e)

        # T17: vectors_available() retorna False quando sentence_transformers ausente
        try:
            saved = sys.modules.get("sentence_transformers", "__absent__")
            sys.modules["sentence_transformers"] = None
            try:
                avail = sm.vectors_available()
            finally:
                if saved == "__absent__":
                    del sys.modules["sentence_transformers"]
                else:
                    sys.modules["sentence_transformers"] = saved
            assert avail is False, avail
            ok("T17-vectors-unavailable-without-sentence-transformers")
        except Exception as e:
            fail("T17-vectors-unavailable-without-sentence-transformers", e)

        core._index.close()

    # T18: reindexar não apaga entidade manual adicionada após a primeira indexação
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        sem = SemanticMemory(core)
        sem.ensure_schema()
        try:
            sem.index_memory("m1", "def foo(): pass")
            sem.add_entity("m1", "function", "manually_added")
            sem.index_memory("m1", "def foo(): pass")  # reindexar
            entities = sem.entities_for_memory("m1")
            names = [e["name"] for e in entities]
            assert "manually_added" in names, f"Entidade manual foi destruída: {names}"
            ok("T18-reindex-preserves-manual-entity")
        except Exception as e:
            fail("T18-reindex-preserves-manual-entity", e)
        core._index.close()

    # T19: index_memory() extrai entidades automaticamente
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        sem = SemanticMemory(core)
        sem.ensure_schema()
        try:
            content = "def minha_func(): pass\nclass MinhaClasse:\n    pass\n- DECISÃO: usar SQLite"
            sem.index_memory("m_auto", content)
            entities = sem.entities_for_memory("m_auto")
            kinds = {e["kind"] for e in entities}
            assert "function" in kinds, f"function não extraída: {entities}"
            assert "decision" in kinds, f"decision não extraída: {entities}"
            names = [e["name"] for e in entities]
            assert any("minha_func" in n for n in names), f"nome errado: {names}"
            ok("T19-index-memory-auto-extract-entities")
        except Exception as e:
            fail("T19-index-memory-auto-extract-entities", e)
        core._index.close()

    # T20: search() faz re-ranking coseno quando ext_vectors tem embeddings
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        sem = SemanticMemory(core)
        sem.ensure_schema()
        try:
            import struct
            import unittest.mock
            from datetime import datetime, timezone

            sem.index_memory("vec_a", "python programming language")
            sem.index_memory("vec_b", "cooking recipes pasta")

            conn = sem._core._index.connection()
            conn.execute(
                """CREATE TABLE IF NOT EXISTS ext_vectors (
                    memory_id   TEXT PRIMARY KEY,
                    embedding   BLOB NOT NULL,
                    model       TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                )"""
            )

            def pack_vec(v):
                return struct.pack(f"{len(v)}f", *v)

            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO ext_vectors VALUES (?,?,?,?)",
                ("vec_a", pack_vec([1.0, 0.0, 0.0, 0.0]), "fake", now),
            )
            conn.execute(
                "INSERT OR REPLACE INTO ext_vectors VALUES (?,?,?,?)",
                ("vec_b", pack_vec([0.0, 1.0, 0.0, 0.0]), "fake", now),
            )
            conn.commit()

            with unittest.mock.patch.object(sem, "vectors_available", return_value=True), \
                 unittest.mock.patch.object(sem, "_embed_text", return_value=[1.0, 0.0, 0.0, 0.0]):
                results = sem.search("python", limit=10)

            assert len(results) >= 1, results
            ids = [r["memory_id"] for r in results]
            if "vec_b" in ids:
                assert ids.index("vec_a") < ids.index("vec_b"), f"Re-ranking falhou: {ids}"
            ok("T20-search-cosine-reranking")
        except Exception as e:
            fail("T20-search-cosine-reranking", e)
        core._index.close()

    # === index_all com arquivos reais ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        core.ensure_dirs()
        sm = SemanticMemory(core)
        sm.ensure_schema()

        fm = {
            "type": "semantic",
            "authority": "project",
        }
        core.write(fm, "def indexed_function(): pass")

        try:
            count = sm.index_all()
            assert count == 1, count
            results = sm.search("indexed_function")
            assert len(results) >= 1, results
            ok("T3b-index-all-real-file")
        except Exception as e:
            fail("T3b-index-all-real-file", e)

        core._index.close()

    # === ProceduralMemory ===
    with tempfile.TemporaryDirectory() as tmpdir:
        core = make_core(tmpdir)
        pm = ProceduralMemory(core)

        # ensure_schema idempotente
        try:
            pm.ensure_schema()
            pm.ensure_schema()
            conn = core._index.connection()
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "ext_procedural" in tables, tables
            ok("T-proc-ensure-schema")
        except Exception as e:
            fail("T-proc-ensure-schema", e)

        # T9: record retorna id string
        try:
            pid = pm.record("impl", ["passo 1", "passo 2"], source_block="F11-03")
            assert isinstance(pid, str) and len(pid) > 0
            ok("T9-record")
        except Exception as e:
            fail("T9-record", e)

        # T10: get_by_task_type retorna lista com o registro
        try:
            results = pm.get_by_task_type("impl")
            assert any(r["id"] == pid for r in results), results
            ok("T10-get-by-task-type")
        except Exception as e:
            fail("T10-get-by-task-type", e)

        # T11: get_by_task_type inexistente retorna []
        try:
            results = pm.get_by_task_type("inexistente")
            assert results == []
            ok("T11-get-by-task-type-empty")
        except Exception as e:
            fail("T11-get-by-task-type-empty", e)

        # T12: increment_used incrementa used_count
        try:
            before = [r for r in pm.get_by_task_type("impl") if r["id"] == pid][0]
            pm.increment_used(pid)
            after = [r for r in pm.get_by_task_type("impl") if r["id"] == pid][0]
            assert after["used_count"] == before["used_count"] + 1, (before, after)
            ok("T12-increment-used")
        except Exception as e:
            fail("T12-increment-used", e)

        # T13: list_task_types inclui "impl"
        try:
            types = pm.list_task_types()
            assert "impl" in types, types
            ok("T13-list-task-types")
        except Exception as e:
            fail("T13-list-task-types", e)

        # T14: delete remove o registro
        try:
            pm.delete(pid)
            results = pm.get_by_task_type("impl")
            assert results == [], results
            ok("T14-delete")
        except Exception as e:
            fail("T14-delete", e)

        core._index.close()

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
