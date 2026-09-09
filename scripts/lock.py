#!/usr/bin/env python3
"""Lock exclusivo sobre um plano do Maestro. Deterministico, criacao atomica.

Subcomandos: adquirir, liberar, status.
Nenhuma sondagem de PID (os.kill mata processos no Windows). O PID gravado
e diagnostico, nao token de posse. A posse e o conjunto de IDs de bloco.
"""
import argparse
import glob as _glob
import json
import os
import socket
import sys
from datetime import datetime, timezone

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")

# ---------------------------------------------------------------------------
# Resolucao de fase (4 regras de precedencia, identicas a scripts/status.py)
# ---------------------------------------------------------------------------


def _resolve_plano(fase_arg):
    """Resolve o caminho do blocos.json pelas 4 regras de precedencia.
    Sai com codigo 1 em erro. Retorna o caminho resolvido (blocos.json)."""
    env_plano = os.environ.get("MAESTRO_PLANO")

    if not fase_arg:
        if os.path.exists(CONFIG):
            try:
                c = json.load(open(CONFIG, encoding="utf-8"))
                fase_arg = c.get("fase_padrao") or None
            except Exception:
                pass

    # Regra 1: --fase explicito (ou fase_padrao do config)
    if fase_arg:
        if env_plano:
            print(
                f"AVISO: MAESTRO_PLANO={env_plano!r} ignorado — --fase {fase_arg!r} tem precedencia.",
                file=sys.stderr,
            )
        caminho = f"plano/{fase_arg}/blocos.json"
        if not os.path.exists(caminho):
            found = sorted(_glob.glob("plano/*/blocos.json"))
            print(f"ERRO: fase {fase_arg!r} nao encontrada ({caminho}).", file=sys.stderr)
            if found:
                fases = [f.split("/")[1] for f in found]
                print(f"  Fases disponiveis: {', '.join(fases)}", file=sys.stderr)
            sys.exit(1)
        return caminho

    # Regra 2: MAESTRO_PLANO ou legado plano/blocos.json
    if env_plano:
        return env_plano
    legacy = "plano/blocos.json"
    if os.path.exists(legacy):
        return legacy

    # Regras 3 & 4: glob
    found = sorted(_glob.glob("plano/*/blocos.json"))
    if len(found) == 1:
        print(f"Fase resolvida: {found[0]}", file=sys.stderr)
        return found[0]
    elif len(found) == 0:
        print("ERRO: nenhum plano encontrado. Rode /maestro:setup.", file=sys.stderr)
        sys.exit(1)
    else:
        fases = [f.split("/")[1] for f in found]
        print(f"ERRO: multiplas fases encontradas: {', '.join(fases)}", file=sys.stderr)
        print("  Passe --fase <nome> para selecionar.", file=sys.stderr)
        sys.exit(1)


def _lock_path(plano_path):
    """Caminho do lock, irmao do blocos.json resolvido."""
    diretorio = os.path.dirname(plano_path)
    if not diretorio:
        diretorio = "."
    return os.path.join(diretorio, ".lock")


def _carregar_config():
    if os.path.exists(CONFIG):
        try:
            return json.load(open(CONFIG, encoding="utf-8"))
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# Utilitarios de conteudo do lock
# ---------------------------------------------------------------------------


def _agora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _calc_idade_min(criado_em_str):
    """Retorna a idade em minutos inteiros, ou None se criado_em nao parseia."""
    try:
        dt = datetime.strptime(criado_em_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None
    delta = datetime.now(timezone.utc) - dt
    return int(delta.total_seconds() // 60)


def _parse_blocos(s):
    return [x.strip() for x in s.split(",") if x.strip()]


def _ler_lock_valido(lock_path):
    """Le e valida o lock existente. Retorna (conteudo, None) ou (None, texto_bruto)
    quando o conteudo nao e JSON valido ou esta incompleto."""
    with open(lock_path, "r", encoding="utf-8") as f:
        texto = f.read()
    try:
        conteudo = json.loads(texto)
        if not isinstance(conteudo, dict) or "blocos" not in conteudo:
            raise ValueError("lock sem o campo 'blocos'")
        return conteudo, texto
    except (json.JSONDecodeError, ValueError):
        return None, texto


def _imprimir_ocupado(conteudo, cfg, prefixo="LOCK OCUPADO"):
    blocos_str = ",".join(conteudo.get("blocos", []))
    criado_em = conteudo.get("criado_em", "?")
    host = conteudo.get("host", "?")
    pid = conteudo.get("pid", "?")
    idade_min = _calc_idade_min(criado_em) if isinstance(criado_em, str) else None
    idade_str = str(idade_min) if idade_min is not None else "?"
    print(
        f"{prefixo}  blocos={blocos_str}  criado_em={criado_em}  idade={idade_str}min  host={host}  pid={pid}"
    )
    limite = cfg.get("lock_timeout_min", 120)
    if idade_min is not None and idade_min > limite:
        print(f"  Lock com mais de {limite}min — possivelmente orfao de uma sessao interrompida.")
    print(
        f"  Outra sessao pode estar executando este plano. Feche-a ou rode: lock.py adquirir --blocos {blocos_str} --forcar"
    )


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


def cmd_adquirir(args, plano_path, lock_path, cfg):
    print(f"Lock: {lock_path}")

    diretorio = os.path.dirname(lock_path) or "."
    if not os.path.isdir(diretorio):
        print(f"ERRO: diretorio do plano nao existe: {diretorio}")
        sys.exit(3)

    blocos = _parse_blocos(args.blocos)
    conteudo_novo = {
        "schema": 1,
        "blocos": blocos,
        "criado_em": _agora_iso(),
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "plano": plano_path.replace("\\", "/"),
    }

    if args.forcar:
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    texto_antigo = f.read()
                print("Lock anterior (sera sobrescrito):")
                print(texto_antigo)
            except OSError:
                pass
        try:
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump(conteudo_novo, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            print(f"ERRO: falha ao escrever lock: {e}")
            sys.exit(3)
        print(f"Lock adquirido (forcado): blocos={','.join(blocos)}")
        sys.exit(0)

    # Criacao atomica: uma unica chamada, sem checar existencia antes.
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        conteudo_existente, texto_bruto = _ler_lock_valido(lock_path)
        if conteudo_existente is None:
            print(
                f"ERRO: lock existente em {lock_path} nao e JSON valido. Use --forcar para sobrescrever."
            )
            sys.exit(2)
        _imprimir_ocupado(conteudo_existente, cfg)
        sys.exit(1)
    except OSError as e:
        print(f"ERRO: falha ao criar lock: {e}")
        sys.exit(3)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(conteudo_novo, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        print(f"ERRO: falha ao escrever lock: {e}")
        sys.exit(3)

    print(f"Lock adquirido: blocos={','.join(blocos)}")
    sys.exit(0)


def cmd_liberar(args, plano_path, lock_path, cfg):
    print(f"Lock: {lock_path}")

    if not os.path.exists(lock_path):
        print("LOCK LIVRE")
        sys.exit(0)

    conteudo, texto_bruto = _ler_lock_valido(lock_path)

    if conteudo is None:
        if args.forcar:
            try:
                os.remove(lock_path)
            except OSError as e:
                print(f"ERRO: falha ao remover lock: {e}")
                sys.exit(3)
            print("Lock removido (forcado, conteudo malformado).")
            sys.exit(0)
        print(
            f"ERRO: lock existente em {lock_path} nao e JSON valido. Use --forcar para remover."
        )
        sys.exit(2)

    if args.forcar:
        try:
            os.remove(lock_path)
        except OSError as e:
            print(f"ERRO: falha ao remover lock: {e}")
            sys.exit(3)
        print("Lock removido (forcado).")
        sys.exit(0)

    blocos_pedidos = set(_parse_blocos(args.blocos))
    blocos_gravados = set(conteudo.get("blocos", []))

    if blocos_pedidos != blocos_gravados:
        print(
            "ERRO: conjunto de blocos informado "
            f"({','.join(sorted(blocos_pedidos))}) difere do gravado no lock "
            f"({','.join(sorted(blocos_gravados))})."
        )
        sys.exit(1)

    try:
        os.remove(lock_path)
    except OSError as e:
        print(f"ERRO: falha ao remover lock: {e}")
        sys.exit(3)
    print("Lock removido.")
    sys.exit(0)


def cmd_status(args, plano_path, lock_path, cfg):
    print(f"Lock: {lock_path}")

    if not os.path.exists(lock_path):
        print("LOCK LIVRE")
        sys.exit(0)

    conteudo, texto_bruto = _ler_lock_valido(lock_path)
    if conteudo is None:
        print(f"AVISO: lock existente em {lock_path} nao e JSON valido.")
        sys.exit(1)

    _imprimir_ocupado(conteudo, cfg, prefixo="LOCK PRESENTE")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Lock exclusivo sobre um plano do Maestro.")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_adq = sub.add_parser("adquirir", help="cria o lock")
    p_adq.add_argument("--blocos", required=True, help="IDs de bloco separados por virgula")
    p_adq.add_argument("--fase", default=None)
    p_adq.add_argument("--forcar", action="store_true")

    p_lib = sub.add_parser("liberar", help="remove o lock")
    p_lib.add_argument("--blocos", required=True, help="IDs de bloco separados por virgula")
    p_lib.add_argument("--fase", default=None)
    p_lib.add_argument("--forcar", action="store_true")

    p_st = sub.add_parser("status", help="mostra o estado do lock")
    p_st.add_argument("--fase", default=None)

    args = parser.parse_args()

    cfg = _carregar_config()
    plano_path = _resolve_plano(args.fase)
    lock_path = _lock_path(plano_path)

    if args.comando == "adquirir":
        cmd_adquirir(args, plano_path, lock_path, cfg)
    elif args.comando == "liberar":
        cmd_liberar(args, plano_path, lock_path, cfg)
    elif args.comando == "status":
        cmd_status(args, plano_path, lock_path, cfg)


if __name__ == "__main__":
    main()
