"""Stdlib tests for F14-03 (maestro migrate). No pytest.

Run: python packages/cli/commands/migrate/_test_migrate.py
Prints ALL TESTS PASSED and exits 0 on success.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "maestro_migrate.py")

_spec = importlib.util.spec_from_file_location("maestro_migrate", _SCRIPT)
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

_FAILURES = []


def check(condition, message):
    if not condition:
        _FAILURES.append(message)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_blocos(n=3):
    return [
        {
            "id": f"B{i:02d}",
            "titulo": f"Bloco {i}",
            "estado": "concluido" if i == 1 else "pendente",
            "depende_de": [] if i == 1 else [f"B{i - 1:02d}"],
        }
        for i in range(1, n + 1)
    ]


def _write_plano(root: Path, blocos, formato="array"):
    plano_dir = root / "plano"
    plano_dir.mkdir(parents=True, exist_ok=True)
    path = plano_dir / "blocos.json"
    content = blocos if formato == "array" else {"blocos": blocos}
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _run(root: Path, dry_run=False, force=False, plano=None):
    """Executa migrar() capturando stdout/stderr. Retorna (exit_code, stdout_text)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = mm.migrar(root, plano, dry_run, force)
    return code, buf.getvalue()


def _tree_hash(root: Path) -> str:
    """Hash determinístico do conteúdo de plano/ e .maestro/ (para provar 'nada mudou')."""
    h = hashlib.sha256()
    for base in (root / "plano", root / ".maestro"):
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(root)).encode("utf-8"))
                h.update(p.read_bytes())
    return h.hexdigest()


@contextlib.contextmanager
def _tmp_root():
    d = tempfile.mkdtemp(prefix="maestro_migrate_test_")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# T01 — --dry-run no repositorio atual nao altera nada
# ---------------------------------------------------------------------------


def test_T01_dry_run_real_repo_nao_altera_nada():
    root = Path(_REPO_ROOT)
    antes = _tree_hash(root)
    backup_existia = (root / ".maestro" / "migration-backup").exists()
    code, out = _run(root, dry_run=True)
    depois = _tree_hash(root)
    check(code == 0, "T01: exit code 0")
    check(antes == depois, "T01: hash da arvore plano/+.maestro/ inalterado")
    check(
        (root / ".maestro" / "migration-backup").exists() == backup_existia,
        "T01: nao criou .maestro/migration-backup",
    )
    check("NENHUMA alteracao foi feita" in out, "T01: mensagem de dry-run presente")


# ---------------------------------------------------------------------------
# T02 — migracao real de array flat -> .maestro/blocks + normaliza plano
# ---------------------------------------------------------------------------


def test_T02_migracao_array_para_blocks_e_normaliza_plano():
    with _tmp_root() as root:
        blocos = _sample_blocos(3)
        plano_path = _write_plano(root, blocos, formato="array")

        code, out = _run(root, dry_run=False)
        check(code == 0, "T02: exit code 0")

        blocks_dir = root / ".maestro" / "blocks"
        for b in blocos:
            f = blocks_dir / f"{b['id']}.json"
            check(f.exists(), f"T02: {f} existe")
            if f.exists():
                gravado = json.loads(f.read_text(encoding="utf-8"))
                check(gravado == b, f"T02: conteudo de {f.name} preserva todos os campos")

        novo = json.loads(plano_path.read_text(encoding="utf-8"))
        check(isinstance(novo, dict) and novo.get("blocos") == blocos,
              "T02: plano/blocos.json normalizado para {'blocos': [...]} preservando estados/IDs")


# ---------------------------------------------------------------------------
# T03 — backup criado antes de qualquer alteracao
# ---------------------------------------------------------------------------


def test_T03_backup_criado_antes_da_alteracao():
    with _tmp_root() as root:
        blocos_antigos = [{"id": "ZZ-OLD", "titulo": "antigo", "estado": "concluido"}]
        blocks_dir = root / ".maestro" / "blocks"
        blocks_dir.mkdir(parents=True)
        (blocks_dir / "ZZ-OLD.json").write_text(
            json.dumps(blocos_antigos[0], ensure_ascii=False), encoding="utf-8"
        )

        blocos_novos = _sample_blocos(2)
        plano_path = _write_plano(root, blocos_novos, formato="array")
        plano_original_bytes = plano_path.read_bytes()

        code, out = _run(root, dry_run=False, force=True)
        check(code == 0, "T03: exit code 0 (migracao com --force)")

        backups = sorted((root / ".maestro" / "migration-backup").glob("*"))
        check(len(backups) == 1, "T03: um diretorio de backup criado")
        if backups:
            backup_dir = backups[0]
            check((backup_dir / "blocos.json.bak").read_bytes() == plano_original_bytes,
                  "T03: backup do plano e copia fiel do original")
            backup_old_block = backup_dir / "blocks.bak" / "ZZ-OLD.json"
            check(backup_old_block.exists(),
                  "T03: backup capturou .maestro/blocks/ pre-existente antes da sobrescrita")

        check(not (blocks_dir / "ZZ-OLD.json").exists(),
              "T03: .maestro/blocks/ final nao contem mais o bloco antigo (foi substituido)")


# ---------------------------------------------------------------------------
# T04 — falha simulada restaura o backup, sem estado parcial
# ---------------------------------------------------------------------------


def test_T04_falha_restaura_estado_anterior():
    with _tmp_root() as root:
        blocos = _sample_blocos(3)
        plano_path = _write_plano(root, blocos, formato="array")
        plano_original_bytes = plano_path.read_bytes()

        original_verificar = mm._verificar_pos_migracao

        def _falha(root_arg, plano_arg):
            raise RuntimeError("falha simulada de pos-verificacao")

        mm._verificar_pos_migracao = _falha
        try:
            code, out = _run(root, dry_run=False)
        finally:
            mm._verificar_pos_migracao = original_verificar

        check(code == 1, "T04: exit code 1 em falha")
        check("ERRO" in out, "T04: mensagem de erro impressa")
        check(plano_path.read_bytes() == plano_original_bytes,
              "T04: plano/blocos.json restaurado ao conteudo original (array, nao normalizado)")
        check(not (root / ".maestro" / "blocks").exists(),
              "T04: .maestro/blocks/ nao existe (nao existia antes da tentativa)")
        backups = list((root / ".maestro" / "migration-backup").glob("*"))
        check(len(backups) == 1, "T04: diretorio de backup preservado como evidencia")
        if backups:
            check(not (backups[0] / "migration-report.json").exists(),
                  "T04: migration-report.json NAO foi escrito (falha ocorreu antes do sucesso)")


# ---------------------------------------------------------------------------
# T05 — --dry-run imprime o relatorio sem criar backup nem blocks/
# ---------------------------------------------------------------------------


def test_T05_dry_run_imprime_sem_alterar():
    with _tmp_root() as root:
        blocos = _sample_blocos(2)
        _write_plano(root, blocos, formato="array")

        code, out = _run(root, dry_run=True)
        check(code == 0, "T05: exit code 0")
        for b in blocos:
            check(b["id"] in out, f"T05: saida menciona {b['id']}")
        check("backup seria criado em" in out, "T05: saida menciona backup simulado")
        check(not (root / ".maestro" / "migration-backup").exists(),
              "T05: nenhum backup real foi criado")
        check(not (root / ".maestro" / "blocks").exists(),
              "T05: .maestro/blocks/ nao foi criado")


# ---------------------------------------------------------------------------
# T06 — ja migrado sem --force: nao altera nada
# ---------------------------------------------------------------------------


def test_T06_ja_migrado_sem_force_nao_altera():
    with _tmp_root() as root:
        blocos = _sample_blocos(2)
        _write_plano(root, blocos, formato="dict")
        blocks_dir = root / ".maestro" / "blocks"
        blocks_dir.mkdir(parents=True)
        (blocks_dir / "B01.json").write_text(json.dumps(blocos[0]), encoding="utf-8")

        antes = _tree_hash(root)
        code, out = _run(root, dry_run=False, force=False)
        depois = _tree_hash(root)

        check(code == 0, "T06: exit code 0")
        check("ja migrada" in out.lower(), "T06: mensagem de 'ja migrada' impressa")
        check(antes == depois, "T06: nenhuma alteracao no disco")
        check(not (root / ".maestro" / "migration-backup").exists(),
              "T06: nenhum backup criado")


# ---------------------------------------------------------------------------
# T07 — ja migrado com --force: cria novo backup e regenera blocks/
# ---------------------------------------------------------------------------


def test_T07_ja_migrado_com_force_regenera():
    with _tmp_root() as root:
        blocos = _sample_blocos(2)
        _write_plano(root, blocos, formato="dict")
        blocks_dir = root / ".maestro" / "blocks"
        blocks_dir.mkdir(parents=True)
        (blocks_dir / "OLD.json").write_text(json.dumps({"id": "OLD"}), encoding="utf-8")

        code, out = _run(root, dry_run=False, force=True)
        check(code == 0, "T07: exit code 0")
        check((root / ".maestro" / "migration-backup").exists(), "T07: backup criado")
        check(not (blocks_dir / "OLD.json").exists(), "T07: bloco antigo removido")
        for b in blocos:
            check((blocks_dir / f"{b['id']}.json").exists(), f"T07: {b['id']}.json regenerado")


# ---------------------------------------------------------------------------
# T08 — plano/blocos.json ausente: nada para migrar, sem backup
# ---------------------------------------------------------------------------


def test_T08_plano_ausente_nao_cria_backup():
    with _tmp_root() as root:
        code, out = _run(root, dry_run=False)
        check(code == 0, "T08: exit code 0")
        check("nao encontrado" in out.lower() or "nada para migrar" in out.lower(),
              "T08: mensagem informando ausencia do plano")
        check(not (root / ".maestro" / "migration-backup").exists(),
              "T08: nenhum backup criado")


# ---------------------------------------------------------------------------
# T09 — pos-verificacao real: status.py e maestro_next.py rodam apos migrar
# ---------------------------------------------------------------------------


def test_T09_pos_verificacao_status_e_next_funcionam():
    with _tmp_root() as root:
        blocos = _sample_blocos(3)
        _write_plano(root, blocos, formato="array")

        scripts_dir = root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for nome in ("status.py", "maestro_next.py", "maestro_state.py", "maestro_runtime.py"):
            shutil.copy2(Path(_REPO_ROOT) / "scripts" / nome, scripts_dir / nome)

        code, out = _run(root, dry_run=False)
        check(code == 0, "T09: migracao com pos-verificacao real termina com exit 0")
        check((root / ".maestro" / "blocks" / "B01.json").exists(),
              "T09: .maestro/blocks/ foi populado")


# ---------------------------------------------------------------------------
# T_DETECT — detectar_estrutura() identifica corretamente LEGADA vs NOVA
# ---------------------------------------------------------------------------


def test_T_detectar_estrutura_legada():
    with _tmp_root() as root:
        config_path = root / "maestro.config.json"
        config_path.write_text(
            json.dumps({"maestro_versao": "1.3.2"}, ensure_ascii=False), encoding="utf-8"
        )
        plano_path = root / "plano" / "blocos.json"  # nao criado de proposito

        info = mm.detectar_estrutura(root, config_path, plano_path)

        check(info["motivos_legado"] != [], "T_DETECT_LEGADA: motivos_legado nao vazio")
        check(
            len(info["motivos_legado"]) == 2,
            "T_DETECT_LEGADA: 2 motivos detectados (.maestro/blocks ausente + versao 1.x)",
        )
        check(
            any("ausente" in m for m in info["motivos_legado"]),
            "T_DETECT_LEGADA: motivo cita .maestro/blocks ausente ou vazio",
        )
        check(
            any("1.3.2" in m for m in info["motivos_legado"]),
            "T_DETECT_LEGADA: motivo cita maestro_versao 1.3.2 (v1.x)",
        )
        check(info["ja_migrado"] is False, "T_DETECT_LEGADA: ja_migrado False")


def test_T_detectar_estrutura_nova():
    with _tmp_root() as root:
        config_path = root / "maestro.config.json"
        config_path.write_text(
            json.dumps({"maestro_versao": "2.0.0"}, ensure_ascii=False), encoding="utf-8"
        )
        blocks_dir = root / ".maestro" / "blocks"
        blocks_dir.mkdir(parents=True)
        (blocks_dir / "B01.json").write_text(
            json.dumps({"id": "B01"}, ensure_ascii=False), encoding="utf-8"
        )
        plano_path = root / "plano" / "blocos.json"  # nao criado de proposito

        info = mm.detectar_estrutura(root, config_path, plano_path)

        check(info["motivos_legado"] == [], "T_DETECT_NOVA: motivos_legado vazio (estrutura NOVA)")
        check(info["ja_migrado"] is True, "T_DETECT_NOVA: ja_migrado True (.maestro/blocks/ populado)")


# ---------------------------------------------------------------------------
# T_RELATORIO — conteudo do migration-report.json em migracao bem-sucedida
# ---------------------------------------------------------------------------


def test_T_relatorio_conteudo_sucesso():
    with _tmp_root() as root:
        blocos = _sample_blocos(2)
        _write_plano(root, blocos, formato="array")

        code, out = _run(root, dry_run=False)
        check(code == 0, "T_RELATORIO: exit code 0")

        backups = sorted((root / ".maestro" / "migration-backup").glob("*"))
        check(len(backups) == 1, "T_RELATORIO: um diretorio de backup criado")
        if backups:
            report_path = backups[0] / "migration-report.json"
            check(report_path.exists(), "T_RELATORIO: migration-report.json existe")
            if report_path.exists():
                relatorio = json.loads(report_path.read_text(encoding="utf-8"))
                ids_esperados = [b["id"] for b in blocos]
                check(
                    relatorio.get("convertidos") == ids_esperados,
                    "T_RELATORIO: 'convertidos' lista os IDs convertidos",
                )
                check(
                    relatorio.get("preservados_em_plano") == ids_esperados,
                    "T_RELATORIO: 'preservados_em_plano' presente e igual aos convertidos",
                )
                check(
                    relatorio.get("nao_migrados") == [],
                    "T_RELATORIO: 'nao_migrados' presente como lista vazia",
                )
                check(
                    bool(relatorio.get("timestamp")),
                    "T_RELATORIO: 'timestamp' presente e nao vazio",
                )


def test_T_blocos_nao_migraveis():
    with _tmp_root() as root:
        blocos = [
            {"id": "F99-01", "titulo": "Bloco valido", "estado": "pendente"},
            {"titulo": "Bloco sem id", "estado": "pendente"},
            {"id": "F99-01", "titulo": "Bloco duplicado", "estado": "pendente"},
        ]
        _write_plano(root, blocos, formato="array")

        code, out = _run(root, dry_run=False)
        check(code == 0, "T_NAO_MIGRAVEL: exit code 0 (migracao parcial nao e falha)")

        backups = sorted((root / ".maestro" / "migration-backup").glob("*"))
        check(len(backups) == 1, "T_NAO_MIGRAVEL: um diretorio de backup criado")
        if backups:
            report_path = backups[0] / "migration-report.json"
            relatorio = json.loads(report_path.read_text(encoding="utf-8"))
            check(
                relatorio.get("convertidos") == ["F99-01"],
                "T_NAO_MIGRAVEL: 'convertidos' contem somente o bloco valido",
            )
            nao_migrados = relatorio.get("nao_migrados", [])
            check(
                len(nao_migrados) == 2,
                "T_NAO_MIGRAVEL: 'nao_migrados' contem as duas entradas invalidas",
            )
            check(
                any(item.get("indice") == 1 for item in nao_migrados),
                "T_NAO_MIGRAVEL: bloco sem 'id' esta em nao_migrados (indice 1)",
            )
            check(
                any(item.get("indice") == 2 and item.get("id") == "F99-01" for item in nao_migrados),
                "T_NAO_MIGRAVEL: bloco duplicado esta em nao_migrados (indice 2, id F99-01)",
            )

        blocks_dir = root / ".maestro" / "blocks"
        check(
            (blocks_dir / "F99-01.json").exists(),
            "T_NAO_MIGRAVEL: F99-01.json criado em .maestro/blocks/",
        )
        check(
            len(list(blocks_dir.glob("*.json"))) == 1,
            "T_NAO_MIGRAVEL: apenas 1 arquivo criado em .maestro/blocks/ (blocos invalidos ignorados)",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    tests = [
        test_T01_dry_run_real_repo_nao_altera_nada,
        test_T02_migracao_array_para_blocks_e_normaliza_plano,
        test_T03_backup_criado_antes_da_alteracao,
        test_T04_falha_restaura_estado_anterior,
        test_T05_dry_run_imprime_sem_alterar,
        test_T06_ja_migrado_sem_force_nao_altera,
        test_T07_ja_migrado_com_force_regenera,
        test_T08_plano_ausente_nao_cria_backup,
        test_T09_pos_verificacao_status_e_next_funcionam,
        test_T_detectar_estrutura_legada,
        test_T_detectar_estrutura_nova,
        test_T_relatorio_conteudo_sucesso,
        test_T_blocos_nao_migraveis,
    ]
    for test in tests:
        test()

    if _FAILURES:
        print("FAILURES:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        print(f"\n{len(_FAILURES)} check(s) failed.")
        sys.exit(1)

    print("ALL TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
