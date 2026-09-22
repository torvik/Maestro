#!/usr/bin/env python3
"""
maestro_run.py - Lifecycle de execucao de um bloco do plano.

Uso:
  python scripts/maestro_run.py --dry-run <ID>   [--fase <nome>] [--json]
  python scripts/maestro_run.py start <ID>       [--fase <nome>] [--json]
  python scripts/maestro_run.py test <ID>        [--fase <nome>]
  python scripts/maestro_run.py finish <ID> --success [--veredito <v>]
                                                 [--commit-sha <sha>]
                                                 [--modelo-efetivo <m>]
                                                 [--turnos-usados <n>]
  python scripts/maestro_run.py finish <ID> --fail [--motivo <texto>]

Maquina de estados:
  pendente -> start -> em_andamento -> test -> (exit 0) -> finish --success -> concluido
                                            -> (exit !=0) -> finish --fail  -> falhou
                                                                            -> bloqueado

Invariantes:
  I1 --dry-run nao toca disco (sem lock, sem escrita).
  I2 finish sempre tenta liberar o lock, em todos os caminhos.
  I3 plano/metricas.json e append-only; schema != 1 interrompe sem sobrescrever.
  I4 falha de import ou escrita de maestro_state nao bloqueia o lifecycle.
  I5 somente stdlib; lock.py e chamado por subprocess, nunca importado.
  I7 nenhum nome de modelo hardcoded: tudo vem de maestro.config.json.
"""

import argparse
import glob as _glob
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_SCRIPT = os.path.join(SCRIPT_DIR, "lock.py")

COMPLEXIDADES_COM_REVISOR = ("C4", "C5")

# estado (blocos.json) -> status canonico (.maestro/state.json)
ESTADO_PARA_STATUS = {
    "pendente": "ready",
    "em_andamento": "running",
    "em_revisao": "review",
    "concluido": "completed",
    "falhou": "failed",
    "bloqueado": "blocked",
    "cancelado": "cancelled",
}


# ---------------------------------------------------------------------------
# Resolucao de fase (4 regras, identicas a status.py / maestro_next.py)
# ---------------------------------------------------------------------------


def _resolve_plano(fase_arg):
    """Resolve o caminho do blocos.json pelas 4 regras de precedencia."""
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
            print(
                f"AVISO: MAESTRO_PLANO={env_plano!r} ignorado - --fase {fase_arg!r} tem precedencia.",
                file=sys.stderr,
            )
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


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def _carregar_config():
    if os.path.exists(CONFIG):
        try:
            return json.load(open(CONFIG, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _agora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _erro(msg, codigo=1):
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(codigo)


def _ler_json(caminho):
    """Retorna (documento, bytes_brutos). Sai com 1 se o JSON for invalido."""
    try:
        with open(caminho, "rb") as f:
            raw = f.read()
    except OSError as exc:
        _erro(f"nao foi possivel ler {caminho}: {exc}")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        _erro(f"{caminho} nao e JSON valido: {exc}")
    return doc, raw


def _escrever_json(caminho, doc, raw_antigo=None):
    """Escreve JSON preservando o estilo de quebra de linha do arquivo original.

    A gravacao e atomica (arquivo temporario + os.replace) para que uma
    interrupcao no meio da escrita nunca deixe blocos.json truncado.
    """
    fim_de_linha = "\n"
    termina_com_nl = True
    if raw_antigo:
        if b"\r\n" in raw_antigo:
            fim_de_linha = "\r\n"
        termina_com_nl = raw_antigo.endswith(b"\n")

    texto = json.dumps(doc, indent=2, ensure_ascii=False)
    if termina_com_nl:
        texto += "\n"
    dados = texto.replace("\n", fim_de_linha).encode("utf-8")

    diretorio = os.path.dirname(os.path.abspath(caminho))
    fd, tmp = tempfile.mkstemp(dir=diretorio, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        _erro(f"falha ao escrever {caminho}: {exc}")


def _carregar_blocos(plano_path):
    doc, raw = _ler_json(plano_path)
    if not isinstance(doc, dict) or not isinstance(doc.get("blocos"), list):
        _erro(f"{plano_path} nao tem a chave 'blocos' com uma lista.")
    return doc, raw


def _achar_bloco(doc, block_id):
    for b in doc["blocos"]:
        if isinstance(b, dict) and b.get("id") == block_id:
            return b
    return None


def _exigir_bloco(doc, block_id, plano_path):
    bloco = _achar_bloco(doc, block_id)
    if bloco is None:
        ids = [b.get("id") for b in doc["blocos"] if isinstance(b, dict)]
        print(f"ERRO: bloco {block_id!r} nao encontrado em {plano_path}.", file=sys.stderr)
        if ids:
            amostra = ", ".join(str(i) for i in ids[:10])
            sufixo = ", ..." if len(ids) > 10 else ""
            print(f"  IDs disponiveis: {amostra}{sufixo}", file=sys.stderr)
        sys.exit(1)
    return bloco


# ---------------------------------------------------------------------------
# Manifest de dispatch
# ---------------------------------------------------------------------------


def montar_manifest(bloco, cfg):
    """Monta o manifest de dispatch. Nenhum nome de modelo e hardcoded (I7).

    modelo/revisor vem de maestro.config.json indexado pela complexidade;
    o valor gravado no bloco e apenas fallback quando o config nao cobre
    aquela complexidade.
    """
    complexidade = bloco.get("complexidade") or ""

    modelos = cfg.get("modelos") or {}
    revisores = cfg.get("revisor_por_complexidade") or {}
    orcamentos = cfg.get("orcamento_turnos") or {}

    modelo = modelos.get(complexidade) or bloco.get("modelo")
    revisor = revisores.get(complexidade) or bloco.get("revisor_modelo")

    orcamento = bloco.get("orcamento_turnos")
    if orcamento is None:
        orcamento = orcamentos.get(complexidade)

    spec = bloco.get("spec") or ""
    max_tentativas = cfg.get("max_tentativas", 2)

    return {
        "block_id": bloco.get("id"),
        "titulo": bloco.get("titulo"),
        "complexidade": complexidade,
        "agente": bloco.get("agente"),
        "modelo": modelo,
        "revisor_modelo": revisor,
        "spec": spec,
        "spec_exists": bool(spec) and os.path.exists(spec),
        "arquivos_permitidos": bloco.get("arquivos_permitidos") or [],
        "orcamento_turnos": orcamento,
        "tentativas": bloco.get("tentativas", 0) or 0,
        "max_tentativas": max_tentativas,
        "requires_reviewer": complexidade in COMPLEXIDADES_COM_REVISOR,
        "comando_teste": bloco.get("comando_teste"),
    }


def _imprimir_manifest(manifest, compacto=False):
    if compacto:
        print(json.dumps(manifest, ensure_ascii=False))
    else:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Lock (sempre por subprocess - I5)
# ---------------------------------------------------------------------------


def _chamar_lock(subcomando, block_id, fase):
    """Invoca scripts/lock.py. Retorna o CompletedProcess (nunca levanta)."""
    if not os.path.exists(LOCK_SCRIPT):
        return None
    cmd = [sys.executable, LOCK_SCRIPT, subcomando, "--blocos", block_id]
    if fase:
        cmd += ["--fase", fase]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError:
        return None


def _eco(proc):
    if proc is None:
        return
    for fluxo in (proc.stdout, proc.stderr):
        if fluxo and fluxo.strip():
            print(fluxo.rstrip(), file=sys.stderr)


# ---------------------------------------------------------------------------
# Checkpoint em .maestro/state.json (I4: nunca bloqueia o lifecycle)
# ---------------------------------------------------------------------------


def _checkpoint(block_id, estado, current):
    """Atualiza .maestro/state.json. Qualquer falha e silenciosa (I4)."""
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import maestro_state  # noqa: PLC0415
    except Exception:
        return False

    try:
        try:
            estado_doc = maestro_state.read_state()
        except Exception:
            estado_doc = maestro_state.empty_state()
        if not isinstance(estado_doc, dict):
            estado_doc = maestro_state.empty_state()

        blocks = estado_doc.get("blocks")
        if not isinstance(blocks, dict):
            blocks = {}
        entrada = blocks.get(block_id)
        if not isinstance(entrada, dict):
            entrada = {}
        entrada["status"] = ESTADO_PARA_STATUS.get(estado, "running")
        if estado == "em_andamento":
            entrada.setdefault("started_at", _agora_iso())
        else:
            entrada["finished_at"] = _agora_iso()
        blocks[block_id] = entrada
        estado_doc["blocks"] = blocks

        estado_doc["current_block"] = block_id if current else None
        if current:
            fase = block_id.split("-")[0] if "-" in block_id else None
            estado_doc["phase"] = fase
        estado_doc.setdefault("locks", [])

        maestro_state.write_state(estado_doc)
        return True
    except Exception:
        return False


def _ler_started_at(block_id):
    """Le o started_at gravado no checkpoint. None se indisponivel (I4)."""
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import maestro_state  # noqa: PLC0415

        doc = maestro_state.read_state()
        entrada = (doc.get("blocks") or {}).get(block_id) or {}
        valor = entrada.get("started_at")
        return valor if isinstance(valor, str) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# metricas.json (append-only - I3)
# ---------------------------------------------------------------------------


def _caminho_metricas(plano_path):
    diretorio = os.path.dirname(plano_path) or "."
    return os.path.join(diretorio, "metricas.json")


def _ler_metricas(plano_path, cfg):
    """Le e valida metricas.json ANTES de qualquer mutacao (fail-closed).

    Retorna (caminho, documento, bytes_brutos). Sai com 1 sem escrever nada se
    o arquivo existir com schema diferente de 1 ou estrutura inesperada (I3).
    """
    caminho = _caminho_metricas(plano_path)
    if not os.path.exists(caminho):
        return caminho, {"schema": 1, "projeto": cfg.get("projeto") or "", "registros": []}, None

    doc, raw = _ler_json(caminho)
    if not isinstance(doc, dict):
        _erro(f"{caminho} nao e um objeto JSON; nada foi alterado.")
    schema = doc.get("schema")
    if schema != 1:
        _erro(
            f"{caminho} tem schema {schema!r}; esta versao so escreve schema 1. "
            "Nada foi alterado."
        )
    if not isinstance(doc.get("registros"), list):
        _erro(f"{caminho} nao tem 'registros' como lista; nada foi alterado.")
    return caminho, doc, raw


def _append_metrica(caminho, doc, raw, registro):
    """Acrescenta um registro ao documento ja validado. Append-only (I3)."""
    doc["registros"].append(registro)
    _escrever_json(caminho, doc, raw)
    return caminho


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


def cmd_dry_run(args):
    """Valida e imprime o manifest. Nao escreve nada, nao toca o lock (I1)."""
    plano_path = _resolve_plano(args.fase)
    doc, _raw = _carregar_blocos(plano_path)
    bloco = _exigir_bloco(doc, args.id, plano_path)
    cfg = _carregar_config()

    manifest = montar_manifest(bloco, cfg)
    _imprimir_manifest(manifest, compacto=args.json)
    return 0


def cmd_start(args):
    plano_path = _resolve_plano(args.fase)
    doc, raw = _carregar_blocos(plano_path)
    bloco = _exigir_bloco(doc, args.id, plano_path)
    cfg = _carregar_config()

    # Guardas fail-closed: recusam ANTES de adquirir o lock, para nunca deixar
    # um lock orfao atras de uma recusa.
    if bloco.get("bloqueado_por"):
        _erro(
            f"bloco {args.id} tem bloqueado_por={bloco['bloqueado_por']!r}; "
            "resolva o bloqueio antes de iniciar."
        )
    estado_atual = bloco.get("estado")
    if estado_atual in ("concluido", "bloqueado"):
        _erro(
            f"bloco {args.id} esta {estado_atual!r}; start recusado. "
            "Reabra o bloco no plano antes de reexecutar."
        )

    # 1. lock
    proc = _chamar_lock("adquirir", args.id, args.fase)
    if proc is None:
        _erro(f"nao foi possivel executar {LOCK_SCRIPT}.")
    if proc.returncode != 0:
        _eco(proc)
        _erro(f"lock nao adquirido para {args.id} (lock.py saiu com {proc.returncode}).")

    # 2. em_andamento
    bloco["estado"] = "em_andamento"
    _escrever_json(plano_path, doc, raw)

    # 3. checkpoint (I4)
    _checkpoint(args.id, "em_andamento", current=True)

    # 4. manifest
    manifest = montar_manifest(bloco, cfg)
    _imprimir_manifest(manifest, compacto=args.json)
    return 0


def cmd_test(args):
    plano_path = _resolve_plano(args.fase)
    doc, _raw = _carregar_blocos(plano_path)
    bloco = _exigir_bloco(doc, args.id, plano_path)

    comando = bloco.get("comando_teste")
    if not comando or not str(comando).strip():
        _erro(f"bloco {args.id} nao tem comando_teste definido.")

    print(f"$ {comando}", file=sys.stderr)
    proc = subprocess.run(comando, shell=True)
    return proc.returncode


def _registro_metrica(bloco, manifest, veredito, args, inicio):
    turnos_usados = getattr(args, "turnos_usados", None)
    return {
        "id": bloco.get("id"),
        "modelo_planejado": manifest["modelo"],
        "modelo_efetivo": getattr(args, "modelo_efetivo", None),
        "revisor_modelo": manifest["revisor_modelo"],
        "turnos_orcados": manifest["orcamento_turnos"],
        "turnos_usados": turnos_usados,
        "tentativas": bloco.get("tentativas", 0) or 0,
        "veredito": veredito,
        "commit_sha": getattr(args, "commit_sha", None),
        "timestamp_inicio": inicio,
        "timestamp_fim": _agora_iso(),
    }


def _anotar(bloco, texto):
    notas = bloco.get("notas")
    if not isinstance(notas, list):
        notas = []
    notas.append(texto)
    bloco["notas"] = notas


def cmd_finish(args):
    plano_path = _resolve_plano(args.fase)
    doc, raw = _carregar_blocos(plano_path)
    bloco = _exigir_bloco(doc, args.id, plano_path)
    cfg = _carregar_config()
    manifest = montar_manifest(bloco, cfg)

    inicio = _ler_started_at(args.id) or _agora_iso()

    try:
        # Fail-closed: metricas.json e validado antes de qualquer escrita, para
        # que um arquivo com schema desconhecido nunca deixe blocos.json
        # adiantado. Fica DENTRO do try para que a saida por erro ainda passe
        # pelo finally que libera o lock (I2).
        caminho_met, doc_met, raw_met = _ler_metricas(plano_path, cfg)

        if args.success:
            bloco["estado"] = "concluido"
            if args.motivo:
                _anotar(bloco, args.motivo)
            _escrever_json(plano_path, doc, raw)
            _checkpoint(args.id, "concluido", current=False)
            veredito = args.veredito or "aprovado"
            registro = _registro_metrica(bloco, manifest, veredito, args, inicio)
            caminho = _append_metrica(caminho_met, doc_met, raw_met, registro)
            print(f"{args.id}: concluido. Metrica em {caminho}.")
        else:
            tentativas = bloco.get("tentativas", 0) or 0
            tentativas += 1
            bloco["tentativas"] = tentativas
            max_tentativas = cfg.get("max_tentativas", 2)
            esgotou = isinstance(max_tentativas, int) and tentativas >= max_tentativas
            bloco["estado"] = "bloqueado" if esgotou else "falhou"
            motivo = args.motivo or "falha sem motivo informado"
            marca = "bloqueado" if esgotou else "falhou"
            _anotar(
                bloco,
                f"[{_agora_iso()}] {marca} (tentativa {tentativas}/{max_tentativas}): {motivo}",
            )
            if esgotou:
                bloco["bloqueado_por"] = motivo
            _escrever_json(plano_path, doc, raw)
            _checkpoint(args.id, bloco["estado"], current=False)
            veredito = args.veredito or "reprovado"
            registro = _registro_metrica(bloco, manifest, veredito, args, inicio)
            caminho = _append_metrica(caminho_met, doc_met, raw_met, registro)
            print(
                f"{args.id}: {bloco['estado']} (tentativa {tentativas}/{max_tentativas}). "
                f"Metrica em {caminho}."
            )
    finally:
        # I2: o lock e liberado em todo caminho de saida, inclusive em erro.
        proc = _chamar_lock("liberar", args.id, args.fase)
        if proc is not None and proc.returncode != 0:
            print(
                f"AVISO: lock.py liberar saiu com {proc.returncode} para {args.id}.",
                file=sys.stderr,
            )
            _eco(proc)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _adicionar_globais(p):
    p.add_argument("--fase", default=None, help="nome da fase (plano/<fase>/blocos.json)")
    p.add_argument("--json", action="store_true", help="saida JSON em uma linha")


def construir_parser():
    p = argparse.ArgumentParser(
        prog="maestro_run.py",
        description="Lifecycle de execucao de um bloco do plano do Maestro.",
    )
    sub = p.add_subparsers(dest="comando")

    p_dry = sub.add_parser("dry-run", help="valida e imprime o manifest, sem IO")
    p_dry.add_argument("id")
    _adicionar_globais(p_dry)
    p_dry.set_defaults(func=cmd_dry_run)

    p_start = sub.add_parser("start", help="lock + em_andamento + checkpoint + manifest")
    p_start.add_argument("id")
    _adicionar_globais(p_start)
    p_start.set_defaults(func=cmd_start)

    p_test = sub.add_parser("test", help="executa comando_teste do bloco")
    p_test.add_argument("id")
    _adicionar_globais(p_test)
    p_test.set_defaults(func=cmd_test)

    p_fin = sub.add_parser("finish", help="encerra o bloco (sucesso ou falha)")
    p_fin.add_argument("id")
    grupo = p_fin.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--success", action="store_true")
    grupo.add_argument("--fail", action="store_true")
    p_fin.add_argument("--veredito", default=None)
    p_fin.add_argument("--commit-sha", dest="commit_sha", default=None)
    p_fin.add_argument("--modelo-efetivo", dest="modelo_efetivo", default=None)
    p_fin.add_argument("--turnos-usados", dest="turnos_usados", type=int, default=None)
    p_fin.add_argument("--motivo", default=None)
    _adicionar_globais(p_fin)
    p_fin.set_defaults(func=cmd_finish)

    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # `--dry-run <ID>` e uma flag global na interface publica; internamente
    # vira o subcomando `dry-run` para reaproveitar o parser.
    if "--dry-run" in argv:
        argv = [a for a in argv if a != "--dry-run"]
        argv.insert(0, "dry-run")

    parser = construir_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
