#!/usr/bin/env python3
"""Verificador de coerência interna do repositório Maestro.

Uso:
  python scripts/verificar-repo.py
  python scripts/verificar-repo.py --check paridade
  python scripts/verificar-repo.py --raiz /caminho/para/repo
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

CHECKS = ["paridade", "portabilidade", "comandos-documentados", "versao", "plano", "versao-remota"]

# URL base do repositório oficial — substituída se plugin.json tiver campo "repository"
REPO_PADRAO = "torvik/Maestro"
RAW_URL_TMPL = "https://raw.githubusercontent.com/{repo}/main/plugins/maestro/.claude-plugin/plugin.json"


def check_paridade(raiz: Path) -> list:
    falhas = []
    dirs = ["commands", "agents", "skills", "scripts"]
    plugin_base = raiz / "plugins" / "maestro"

    def ignorar(p: Path) -> bool:
        return "__pycache__" in p.parts or p.suffix == ".pyc"

    # raiz → plugin
    for d in dirs:
        root_dir = raiz / d
        if not root_dir.exists():
            continue
        for f in root_dir.rglob("*"):
            if not f.is_file() or ignorar(f):
                continue
            rel = f.relative_to(raiz)
            plugin_f = plugin_base / rel
            if not plugin_f.exists():
                falhas.append(f"FALHA paridade {rel}: ausente em plugins/maestro/{rel}")
            elif f.read_bytes() != plugin_f.read_bytes():
                falhas.append(f"FALHA paridade {rel}: conteúdo diverge de plugins/maestro/{rel}")

    # plugin → raiz (inverso)
    for d in dirs:
        plugin_dir = plugin_base / d
        if not plugin_dir.exists():
            continue
        for f in plugin_dir.rglob("*"):
            if not f.is_file() or ignorar(f):
                continue
            rel_plugin = f.relative_to(plugin_base)
            root_f = raiz / rel_plugin
            if not root_f.exists():
                falhas.append(
                    f"FALHA paridade plugins/maestro/{rel_plugin}: "
                    f"ausente na raiz ({rel_plugin})"
                )

    return falhas


def check_portabilidade(raiz: Path) -> list:
    falhas = []
    dirs = ["commands", "agents", "skills"]

    for copy_root in [raiz, raiz / "plugins" / "maestro"]:
        for d in dirs:
            search_dir = copy_root / d
            if not search_dir.exists():
                continue
            for f in search_dir.rglob("*.md"):
                try:
                    lines = f.read_text(encoding="utf-8").splitlines()
                except Exception as e:
                    falhas.append(
                        f"FALHA portabilidade {f.relative_to(raiz)}: erro de leitura: {e}"
                    )
                    continue
                for i, line in enumerate(lines, 1):
                    rel = f.relative_to(raiz)
                    if "find ~/" in line:
                        falhas.append(
                            f"FALHA portabilidade {rel}:{i}: contém 'find ~/' (não funciona no Windows)"
                        )
                    if "python3 " in line:
                        # Permitido se a linha documenta fallback: contém "python3" E "python" simples
                        has_plain = bool(re.search(r"\bpython\b(?!3)", line))
                        if not has_plain:
                            falhas.append(
                                f"FALHA portabilidade {rel}:{i}: contém 'python3 ' sem fallback 'python' na mesma linha"
                            )

    return falhas


def check_comandos_documentados(raiz: Path) -> list:
    falhas = []
    commands_dir = raiz / "commands"
    if not commands_dir.exists():
        return [f"FALHA comandos-documentados commands/: diretório ausente"]

    comandos = {f.stem for f in commands_dir.glob("*.md")}

    docs = {
        "INSTALACAO-USUARIO.md": raiz / "INSTALACAO-USUARIO.md",
        "skills/maestro-setup/SKILL.md": raiz / "skills" / "maestro-setup" / "SKILL.md",
    }

    for doc_nome, doc_path in docs.items():
        if not doc_path.exists():
            falhas.append(f"FALHA comandos-documentados {doc_nome}: arquivo não encontrado")
            continue
        try:
            content = doc_path.read_text(encoding="utf-8")
        except Exception as e:
            falhas.append(f"FALHA comandos-documentados {doc_nome}: erro de leitura: {e}")
            continue

        # Todos os comandos devem ser mencionados
        for cmd in sorted(comandos):
            if f"/maestro:{cmd}" not in content:
                falhas.append(
                    f"FALHA comandos-documentados {doc_nome}: /maestro:{cmd} não mencionado"
                )

        # Nenhum comando fantasma
        mencionados = set(re.findall(r"/maestro:([a-z][a-z0-9_-]*)", content))
        for m in sorted(mencionados):
            if m not in comandos:
                falhas.append(
                    f"FALHA comandos-documentados {doc_nome}: "
                    f"/maestro:{m} mencionado mas não existe em commands/"
                )

    return falhas


def check_versao(raiz: Path) -> list:
    falhas = []
    versoes = {}

    for pj in raiz.rglob("plugin.json"):
        if "__pycache__" in pj.parts:
            continue
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            versoes[str(pj.relative_to(raiz))] = data.get("version", "(ausente)")
        except Exception as e:
            falhas.append(f"FALHA versao {pj.relative_to(raiz)}: JSON inválido: {e}")

    versao_md = raiz / "VERSAO.md"
    if versao_md.exists():
        m = re.search(r"\d+\.\d+\.\d+", versao_md.read_text(encoding="utf-8"))
        versoes["VERSAO.md"] = m.group(0) if m else "(não encontrado)"
    else:
        falhas.append("FALHA versao VERSAO.md: arquivo não encontrado")

    changelog = raiz / "CHANGELOG.md"
    if changelog.exists():
        m = re.search(r"\d+\.\d+\.\d+", changelog.read_text(encoding="utf-8"))
        versoes["CHANGELOG.md"] = m.group(0) if m else "(não encontrado)"
    else:
        falhas.append("FALHA versao CHANGELOG.md: arquivo não encontrado")

    if len(set(versoes.values())) > 1:
        detalhe = ", ".join(f"{k}={v}" for k, v in sorted(versoes.items()))
        falhas.append(f"FALHA versao: versões divergentes — {detalhe}")

    return falhas


def check_plano(raiz: Path) -> list:
    falhas = []
    plano_path = raiz / "plano" / "blocos.json"

    if not plano_path.exists():
        return ["FALHA plano plano/blocos.json: arquivo não encontrado"]

    try:
        data = json.loads(plano_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"FALHA plano plano/blocos.json: JSON inválido: {e}"]

    for b in data.get("blocos", []):
        bid = b.get("id", "(sem id)")
        spec = b.get("spec", "")
        if spec and not (raiz / spec).exists():
            falhas.append(
                f"FALHA plano plano/blocos.json: bloco {bid} spec não encontrada: {spec}"
            )

    return falhas


def _versao_tuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0, 0, 0)


def check_versao_remota(raiz: Path) -> list:
    """Compara a versão instalada com a publicada no GitHub. Silencioso se offline."""
    # Versão local
    local_pj = raiz / ".claude-plugin" / "plugin.json"
    plugin_pj = raiz / "plugins" / "maestro" / ".claude-plugin" / "plugin.json"
    versao_local = None
    repo = REPO_PADRAO
    for pj in (local_pj, plugin_pj):
        if pj.exists():
            try:
                data = json.loads(pj.read_text(encoding="utf-8"))
                versao_local = data.get("version")
                repo = data.get("repository", repo)
                break
            except Exception:
                pass

    if not versao_local:
        return ["FALHA versao-remota: versão local não encontrada em plugin.json"]

    url = RAW_URL_TMPL.format(repo=repo)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "maestro-verificar-repo/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        versao_remota = data.get("version")
    except Exception as e:
        # Offline ou GitHub indisponível — não reporta como falha
        print(f"  versao-remota: nao foi possivel verificar ({e.__class__.__name__})")
        return []

    if not versao_remota:
        return ["FALHA versao-remota: campo 'version' ausente no plugin.json remoto"]

    if _versao_tuple(versao_remota) > _versao_tuple(versao_local):
        return [
            f"FALHA versao-remota: atualização disponível — local={versao_local} remota={versao_remota}. "
            f"Rode: /plugin update maestro"
        ]

    print(f"  versao-remota: {versao_local} — atualizado")
    return []


CHECKS_MAP = {
    "paridade": check_paridade,
    "portabilidade": check_portabilidade,
    "comandos-documentados": check_comandos_documentados,
    "versao": check_versao,
    "plano": check_plano,
    "versao-remota": check_versao_remota,
}


def main():
    parser = argparse.ArgumentParser(description="Verificador de coerência do Maestro")
    parser.add_argument("--check", metavar="NOME", help="Executa apenas a verificação informada")
    parser.add_argument(
        "--raiz", metavar="CAMINHO", help="Raiz do repositório (default: diretório pai do script)"
    )
    args = parser.parse_args()

    raiz = Path(args.raiz).resolve() if args.raiz else Path(__file__).resolve().parent.parent

    if args.check:
        if args.check not in CHECKS_MAP:
            print(f"Verificação desconhecida: '{args.check}'")
            print(f"Válidas: {', '.join(CHECKS)}")
            sys.exit(2)
        checks_to_run = [args.check]
    else:
        checks_to_run = CHECKS

    todas_falhas = []
    for nome in checks_to_run:
        try:
            falhas = CHECKS_MAP[nome](raiz)
        except Exception as e:
            falhas = [f"FALHA {nome}: exceção não tratada: {e}"]
        for linha in falhas:
            print(linha)
        todas_falhas.extend(falhas)

    n = len(checks_to_run)
    m = len(todas_falhas)
    print(f"{n} verificacao(oes) executada(s), {m} falha(s)")
    sys.exit(0 if m == 0 else 1)


if __name__ == "__main__":
    main()
