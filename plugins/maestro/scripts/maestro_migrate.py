#!/usr/bin/env python3
"""
maestro_migrate.py - Migracao incremental da estrutura legada do Maestro
para o layout .maestro/blocks/ (um arquivo JSON por bloco), com backup e
relatorio. Fail-safe: qualquer falha durante a migracao real restaura o
estado anterior a partir do backup, sem deixar estado parcial.

Uso:
  python scripts/maestro_migrate.py [--dry-run] [--force] [--plano <caminho>]

Flags:
  --dry-run          mostra o que seria feito, sem alterar nada
  --force            migra mesmo que .maestro/blocks/ ja exista e nao esteja vazio
  --plano <caminho>  caminho alternativo para o plano legado (default: plano/blocos.json)

Estrutura legada (qualquer uma):
  - .maestro/blocks/ ausente ou sem nenhum arquivo *.json
  - plano/blocos.json no formato array flat (sem chave "blocos")
  - maestro.config.json com maestro_versao major < 2

Estrutura nova:
  - .maestro/blocks/<bloco-id>.json (um arquivo por bloco)
  - plano/blocos.json sempre normalizado como {"blocos": [...]}

scripts/status.py e scripts/maestro_next.py NUNCA sao alterados por este
script - so sao invocados (leitura) para verificar que continuam
funcionando apos a migracao, quando presentes na raiz.

Ver plano/specs/F14-03-maestro-migrate.md para o fluxo completo.

Stdlib only: json, os, shutil, subprocess, sys, datetime, pathlib.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------


def _timestamp_unico(base_dir: Path) -> str:
    """Nome de diretorio de backup unico (evita colisao no mesmo segundo)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidato = ts
    n = 2
    while (base_dir / candidato).exists():
        candidato = f"{ts}-{n}"
        n += 1
    return candidato


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _major(versao) -> int | None:
    try:
        return int(str(versao).split(".")[0])
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Deteccao de estrutura (somente leitura)
# ---------------------------------------------------------------------------


def detectar_estrutura(root: Path, config_path: Path, plano_path: Path) -> dict:
    """Le o estado atual do projeto. Nunca escreve nada."""
    blocks_dir = root / ".maestro" / "blocks"
    blocks_existentes = sorted(blocks_dir.glob("*.json")) if blocks_dir.exists() else []
    ja_migrado = blocks_dir.exists() and len(blocks_existentes) > 0

    plano_existe = plano_path.exists()
    formato = None
    erro_plano = None
    if plano_existe:
        try:
            data = json.loads(plano_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            erro_plano = f"JSON invalido: {exc}"
            data = None
        if data is not None:
            if isinstance(data, list):
                formato = "array"
            elif isinstance(data, dict) and isinstance(data.get("blocos"), list):
                formato = "dict"
            else:
                erro_plano = "formato desconhecido: esperado array ou objeto com chave 'blocos'"

    config_versao = None
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            config_versao = cfg.get("maestro_versao")
        except (OSError, ValueError):
            pass

    motivos = []
    if not blocks_dir.exists() or not blocks_existentes:
        motivos.append(f"{blocks_dir} ausente ou vazio")
    if formato == "array":
        motivos.append(f"{plano_path} no formato array flat (sem chave 'blocos')")
    major = _major(config_versao)
    if config_versao is not None and major is not None and major < 2:
        motivos.append(f"maestro.config.json com maestro_versao {config_versao!r} (v1.x)")

    return {
        "ja_migrado": ja_migrado,
        "blocks_dir": blocks_dir,
        "blocks_existentes": [p.stem for p in blocks_existentes],
        "plano_existe": plano_existe,
        "formato": formato,
        "erro_plano": erro_plano,
        "config_versao": config_versao,
        "motivos_legado": motivos,
    }


def _extrair_blocos(data, formato):
    return data if formato == "array" else data["blocos"]


def classificar_blocos(blocos):
    """Retorna (convertidos, nao_migrados). convertidos = lista de ids
    validos e unicos. nao_migrados = lista de dicts {indice, motivo} para
    blocos sem 'id' valido ou com 'id' duplicado."""
    convertidos = []
    nao_migrados = []
    vistos = {}
    for idx, b in enumerate(blocos):
        if not isinstance(b, dict) or not isinstance(b.get("id"), str) or not b["id"].strip():
            nao_migrados.append(
                {"indice": idx, "motivo": "bloco sem campo 'id' valido (string nao vazia)"}
            )
            continue
        bid = b["id"]
        if bid in vistos:
            nao_migrados.append(
                {
                    "indice": idx,
                    "id": bid,
                    "motivo": f"id duplicado (primeira ocorrencia no indice {vistos[bid]})",
                }
            )
            continue
        vistos[bid] = idx
        convertidos.append(bid)
    return convertidos, nao_migrados


# ---------------------------------------------------------------------------
# Pos-verificacao (le, nunca escreve status.py/maestro_next.py)
# ---------------------------------------------------------------------------


def _verificar_pos_migracao(root: Path, plano_path: Path) -> None:
    status_script = root / "scripts" / "status.py"
    next_script = root / "scripts" / "maestro_next.py"
    env = dict(os.environ)
    env["MAESTRO_PLANO"] = str(plano_path)
    for script in (status_script, next_script):
        if not script.exists():
            continue  # ambiente isolado (ex.: testes) pode nao ter os scripts
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            saida = (proc.stderr or proc.stdout or "").strip()[:500]
            raise RuntimeError(
                f"pos-verificacao falhou: {script.name} saiu com codigo "
                f"{proc.returncode}: {saida}"
            )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def _rollback(plano_path: Path, blocks_dir: Path, backup_plano, backup_blocks) -> None:
    """Restaura plano_path e blocks_dir ao estado anterior a partir do backup.
    Idempotente e best-effort - nunca levanta."""
    if backup_plano is not None:
        try:
            shutil.copy2(backup_plano, plano_path)
        except OSError:
            pass
    try:
        if blocks_dir.exists():
            shutil.rmtree(blocks_dir)
    except OSError:
        pass
    if backup_blocks is not None:
        try:
            shutil.copytree(backup_blocks, blocks_dir)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Impressao
# ---------------------------------------------------------------------------


def _imprimir_plano_dry_run(root, plano_path, info, convertidos, nao_migrados, normaliza_plano):
    print("=== MAESTRO MIGRATE (--dry-run) ===")
    print(f"raiz:            {root}")
    print(f"plano de origem: {plano_path}  (formato: {info['formato']})")
    if info["motivos_legado"]:
        print("estrutura detectada: LEGADA")
        for m in info["motivos_legado"]:
            print(f"  - {m}")
    else:
        print("estrutura detectada: NOVA (migrando de novo via --force)")

    print(f"\nblocos a converter para {info['blocks_dir']}: {len(convertidos)}")
    for bid in convertidos[:10]:
        print(f"  -> {info['blocks_dir'] / (bid + '.json')}")
    if len(convertidos) > 10:
        print(f"  ... e mais {len(convertidos) - 10} bloco(s)")

    if nao_migrados:
        print(f"\nblocos que NAO podem ser migrados automaticamente: {len(nao_migrados)}")
        for item in nao_migrados:
            print(f"  - {item}")

    normaliza_txt = "SIM (array -> objeto com chave 'blocos')" if normaliza_plano else "nao necessario"
    print(f"\nnormalizar {plano_path}: {normaliza_txt}")
    print(f"backup seria criado em: {root / '.maestro' / 'migration-backup' / '<timestamp>'}")
    print("\nNENHUMA alteracao foi feita (--dry-run).")


def _imprimir_resumo(relatorio: dict) -> None:
    print("=== MAESTRO MIGRATE ===")
    print("estrutura legada -> nova: OK")
    print(
        f"plano de origem: {relatorio['plano_origem']}  "
        f"(formato original: {relatorio['formato_original']})"
    )
    print(f"blocos convertidos: {len(relatorio['convertidos'])} em {relatorio['blocks_dir']}")
    if relatorio["nao_migrados"]:
        print(f"blocos NAO migrados automaticamente: {len(relatorio['nao_migrados'])}")
        for item in relatorio["nao_migrados"]:
            print(f"  - {item}")
    print(f"backup: {relatorio['backup_dir']}")
    print(f"relatorio: {Path(relatorio['backup_dir']) / 'migration-report.json'}")


# ---------------------------------------------------------------------------
# Execucao real
# ---------------------------------------------------------------------------


def _executar_migracao(root, plano_path, info, blocos, convertidos, nao_migrados, normaliza_plano, config_path) -> int:
    maestro_dir = root / ".maestro"
    migration_backups = maestro_dir / "migration-backup"
    migration_backups.mkdir(parents=True, exist_ok=True)
    ts = _timestamp_unico(migration_backups)
    backup_dir = migration_backups / ts
    backup_dir.mkdir(parents=True, exist_ok=False)

    blocks_dir = info["blocks_dir"]
    backup_plano = backup_dir / "blocos.json.bak"
    backup_blocks = backup_dir / "blocks.bak"
    backup_config = backup_dir / "maestro.config.json.bak"

    try:
        shutil.copy2(plano_path, backup_plano)
        if blocks_dir.exists():
            shutil.copytree(blocks_dir, backup_blocks)
        if config_path.exists():
            shutil.copy2(config_path, backup_config)

        staging = backup_dir / "staging" / "blocks"
        staging.mkdir(parents=True)
        convertidos_set = set(convertidos)
        for b in blocos:
            if not isinstance(b, dict):
                continue
            bid = b.get("id")
            if bid not in convertidos_set:
                continue
            texto = json.dumps(b, indent=2, ensure_ascii=False) + "\n"
            (staging / f"{bid}.json").write_text(texto, encoding="utf-8", newline="\n")

        if normaliza_plano:
            novo_texto = json.dumps({"blocos": blocos}, indent=2, ensure_ascii=False) + "\n"
            _atomic_write_text(plano_path, novo_texto)

        if blocks_dir.exists():
            shutil.rmtree(blocks_dir)
        os.replace(staging, blocks_dir)

        _verificar_pos_migracao(root, plano_path)

        relatorio = {
            "schema": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raiz": str(root),
            "plano_origem": str(plano_path),
            "formato_original": info["formato"],
            "formato_final": "dict",
            "blocks_dir": str(blocks_dir),
            "total_blocos": len(blocos),
            "convertidos": convertidos,
            "preservados_em_plano": convertidos,
            "nao_migrados": nao_migrados,
            "backup_dir": str(backup_dir),
        }
        _atomic_write_text(
            backup_dir / "migration-report.json",
            json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n",
        )
    except Exception as exc:  # noqa: BLE001 - fail-safe abrangente e intencional
        _rollback(
            plano_path,
            blocks_dir,
            backup_plano if backup_plano.exists() else None,
            backup_blocks if backup_blocks.exists() else None,
        )
        print(f"ERRO: migracao falhou ({exc}).", file=sys.stderr)
        print(f"Estado restaurado a partir do backup em {backup_dir}", file=sys.stderr)
        return 1

    _imprimir_resumo(relatorio)
    return 0


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------


def migrar(root: Path, plano_arg, dry_run: bool, force: bool) -> int:
    root = Path(root)
    config_path = root / "maestro.config.json"
    plano_path = Path(plano_arg) if plano_arg else (root / "plano" / "blocos.json")

    info = detectar_estrutura(root, config_path, plano_path)

    if info["ja_migrado"] and not force:
        print("Estrutura ja migrada.")
        print(f"  {info['blocks_dir']}  ({len(info['blocks_existentes'])} bloco(s))")
        print("  Use --force para migrar novamente (cria novo backup do estado atual).")
        return 0

    if not info["plano_existe"]:
        print(f"{plano_path} nao encontrado. Nada para migrar.")
        return 0

    if info["erro_plano"]:
        print(f"ERRO: {plano_path} invalido - {info['erro_plano']}", file=sys.stderr)
        return 1

    data = json.loads(plano_path.read_text(encoding="utf-8"))
    blocos = _extrair_blocos(data, info["formato"])
    convertidos, nao_migrados = classificar_blocos(blocos)
    normaliza_plano = info["formato"] == "array"

    if dry_run:
        _imprimir_plano_dry_run(root, plano_path, info, convertidos, nao_migrados, normaliza_plano)
        return 0

    return _executar_migracao(
        root, plano_path, info, blocos, convertidos, nao_migrados, normaliza_plano, config_path
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0

    dry_run = "--dry-run" in argv
    force = "--force" in argv
    plano_arg = None
    if "--plano" in argv:
        i = argv.index("--plano")
        if i + 1 < len(argv):
            plano_arg = argv[i + 1]
        else:
            print("Uso: maestro_migrate.py [--dry-run] [--force] [--plano <caminho>]", file=sys.stderr)
            return 1

    root = Path.cwd()
    return migrar(root, plano_arg, dry_run, force)


if __name__ == "__main__":
    sys.exit(main())
