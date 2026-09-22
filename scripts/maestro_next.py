#!/usr/bin/env python3
"""
maestro_next.py - Retorna o próximo bloco liberado do plano.

Uso:
  python scripts/maestro_next.py [--fase <nome>] [--run] [--json]

Saída:
  Sem flags: <id>  <complexidade>  <agente>  <modelo>
  --run: detalhe completo + linha final com instrução /maestro:proxima <ID>
  --json: JSON de uma linha com o bloco completo
"""

import json
import sys
import os
import glob as _glob

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")


def _resolve_plano(fase_arg):
    """Resolve o caminho do blocos.json pelas 4 regras de precedencia (identico a status.py)."""
    env_plano = os.environ.get("MAESTRO_PLANO")

    if not fase_arg:
        if os.path.exists(CONFIG):
            try:
                c = json.load(open(CONFIG, encoding="utf-8"))
                fase_arg = c.get("fase_padrao") or None
            except Exception:
                pass

    if fase_arg:
        if env_plano:
            print(f"AVISO: MAESTRO_PLANO={env_plano!r} ignorado — --fase {fase_arg!r} tem precedencia.",
                  file=sys.stderr)
        caminho = f"plano/{fase_arg}/blocos.json"
        if not os.path.exists(caminho):
            found = sorted(_glob.glob("plano/*/blocos.json"))
            print(f"ERRO: fase {fase_arg!r} nao encontrada ({caminho}).", file=sys.stderr)
            if found:
                fases = [f.replace("\\", "/").split("/")[1] for f in found]
                print(f"  Fases disponiveis: {', '.join(fases)}", file=sys.stderr)
            sys.exit(1)
        return caminho

    if env_plano:
        return env_plano
    legacy = "plano/blocos.json"
    if os.path.exists(legacy):
        return legacy

    found = sorted(_glob.glob("plano/*/blocos.json"))
    if len(found) == 1:
        print(f"Fase resolvida: {found[0]}", file=sys.stderr)
        return found[0]
    elif len(found) == 0:
        print("ERRO: nenhum plano encontrado. Rode /maestro:setup.", file=sys.stderr)
        sys.exit(1)
    else:
        fases = [f.replace("\\", "/").split("/")[1] for f in found]
        print(f"ERRO: multiplas fases encontradas: {', '.join(fases)}", file=sys.stderr)
        print("  Passe --fase <nome> para selecionar.", file=sys.stderr)
        sys.exit(1)


def load_blocos(blocos_file):
    """Carrega e valida o arquivo blocos.json."""
    if not os.path.exists(blocos_file):
        return None
    try:
        with open(blocos_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("blocos", [])
    except (json.JSONDecodeError, IOError):
        return None


def find_next_bloco(blocos):
    """
    Retorna o primeiro bloco pendente com todas as dependências concluídas
    e bloqueado_por nulo/vazio.
    """
    # Criar dicionário de blocos por ID para verificar dependências
    blocos_by_id = {b.get("id"): b for b in blocos}

    for bloco in blocos:
        # Verificar estado
        if bloco.get("estado") != "pendente":
            continue

        # Verificar bloqueado_por
        bloqueado_por = bloco.get("bloqueado_por")
        if bloqueado_por:
            continue

        # Verificar dependências
        deps = bloco.get("depende_de", [])
        all_deps_done = True
        for dep_id in deps:
            dep_bloco = blocos_by_id.get(dep_id)
            if not dep_bloco or dep_bloco.get("estado") != "concluido":
                all_deps_done = False
                break

        if all_deps_done:
            return bloco

    return None


def format_output(bloco, output_mode="default"):
    """Formata a saída conforme o modo solicitado."""
    if output_mode == "json":
        return json.dumps(bloco, ensure_ascii=False)
    elif output_mode == "run":
        # Detalhe completo
        lines = []
        lines.append(f"ID: {bloco.get('id')}")
        lines.append(f"Título: {bloco.get('titulo')}")
        lines.append(f"Complexidade: {bloco.get('complexidade')}")
        lines.append(f"Agente: {bloco.get('agente')}")
        lines.append(f"Modelo: {bloco.get('modelo')}")
        lines.append(f"Revisor Modelo: {bloco.get('revisor_modelo')}")
        lines.append(f"Spec: {bloco.get('spec')}")
        lines.append(f"Estado: {bloco.get('estado')}")
        lines.append(f"Orçamento de turnos: {bloco.get('orcamento_turnos')}")
        lines.append(f"Tentativas: {bloco.get('tentativas')}")

        deps = bloco.get("depende_de", [])
        if deps:
            lines.append(f"Depende de: {', '.join(deps)}")

        arquivos = bloco.get("arquivos_permitidos", [])
        if arquivos:
            lines.append(f"Arquivos permitidos: {len(arquivos)} arquivo(s)")
            for arq in arquivos:
                lines.append(f"  - {arq}")

        lines.append("")
        lines.append(f"--- Para executar este bloco, invoque: /maestro:proxima {bloco.get('id')} ---")

        return "\n".join(lines)
    else:  # default
        return f"{bloco.get('id')}  {bloco.get('complexidade')}  {bloco.get('agente')}  {bloco.get('modelo')}"


def main():
    fase = None
    output_mode = "default"

    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--fase" and i + 1 < len(sys.argv):
            fase = sys.argv[i + 1]
            i += 2
        elif arg == "--run":
            output_mode = "run"
            i += 1
        elif arg == "--json":
            output_mode = "json"
            i += 1
        else:
            i += 1

    # Resolver caminho do arquivo (4 regras, idêntico a status.py)
    blocos_file = _resolve_plano(fase)

    # Carregar blocos
    blocos = load_blocos(blocos_file)
    if blocos is None:
        print(f"ERRO: nao foi possivel carregar {blocos_file}", file=sys.stderr)
        sys.exit(1)

    # Encontrar próximo bloco liberado
    next_bloco = find_next_bloco(blocos)

    if next_bloco is None:
        print("nenhum bloco liberado")
        sys.exit(0)

    # Imprimir saída
    output = format_output(next_bloco, output_mode)
    print(output)
    sys.exit(0)


if __name__ == "__main__":
    main()
