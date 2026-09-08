#!/usr/bin/env python3
"""Gera plano/RELATORIO.md a partir de blocos.json, specs e metricas.json.
Deterministico: sem texto gerado por modelo, sem consulta ao git.

Uso:
  python scripts/exportar-relatorio.py
  python scripts/exportar-relatorio.py --fase <nome>
  python scripts/exportar-relatorio.py --saida outro/caminho.md
"""

import json
import sys
import os
import re
import glob as _glob
from pathlib import Path
from datetime import datetime

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")

# ---------------------------------------------------------------------------
# Resolucao de fase (4 regras de precedencia)
# ---------------------------------------------------------------------------

def _resolve_plano(fase_arg):
    """Resolve o caminho do blocos.json pelas 4 regras de precedencia.
    Sai com codigo 1 em erro. Retorna o caminho resolvido."""
    env_plano = os.environ.get("MAESTRO_PLANO")

    # fase_padrao do config equivale a --fase quando --fase ausente
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
            print(f"AVISO: MAESTRO_PLANO={env_plano!r} ignorado — --fase {fase_arg!r} tem precedencia.",
                  file=sys.stderr)
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


def _resolve_metricas(plano_path):
    """Deriva o caminho de metricas.json a partir do plano resolvido."""
    env = os.environ.get("MAESTRO_METRICAS")
    if env:
        return env
    return os.path.join(os.path.dirname(plano_path), "metricas.json")


# ---------------------------------------------------------------------------
# Geracao do relatorio
# ---------------------------------------------------------------------------

def _raiz():
    return Path(__file__).resolve().parent.parent


def _extrair_secoes(spec_path: Path) -> str:
    """Extrai as secoes ## 2. e ## 3. do arquivo de spec, sem alteracao."""
    if not spec_path.exists():
        return "spec ausente"
    try:
        texto = spec_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"erro ao ler spec: {e}"

    linhas = texto.splitlines()
    trechos = []
    capturando = False
    buf = []

    for linha in linhas:
        # Cabecalho de secao 2 ou 3
        if re.match(r"^##\s+[23]\.", linha):
            if buf and capturando:
                trechos.append("\n".join(buf).rstrip())
            buf = [linha]
            capturando = True
        elif capturando:
            # Para quando encontra outro cabecalho de nivel 2+
            if re.match(r"^##\s+[^23\.]", linha) or re.match(r"^##\s+[456789]\.", linha):
                trechos.append("\n".join(buf).rstrip())
                buf = []
                capturando = False
            else:
                buf.append(linha)

    if buf and capturando:
        trechos.append("\n".join(buf).rstrip())

    if not trechos:
        return "resumo indisponivel"
    return "\n\n".join(trechos)


def gerar(saida: Path, raiz: Path, plano_str: str, metricas_str: str):
    plano_path = raiz / plano_str
    if not plano_path.exists():
        print(f"Erro: {plano_path} nao encontrado.")
        return 1

    try:
        with open(plano_path, encoding="utf-8") as f:
            plano = json.load(f)
    except Exception as e:
        print(f"Erro: blocos.json invalido: {e}")
        return 1

    blocos = plano.get("blocos", [])
    projeto = plano.get("projeto", "projeto")
    hoje = datetime.now().strftime("%Y-%m-%d")

    # Metricas (opcional)
    metricas_path = raiz / metricas_str
    regs_por_id = {}
    if metricas_path.exists():
        try:
            m = json.load(open(metricas_path, encoding="utf-8"))
            if m.get("schema") == 1:
                for r in m.get("registros", []):
                    bid = r.get("id")
                    if bid:
                        regs_por_id.setdefault(bid, []).append(r)
                # Ordena por timestamp_fim
                for bid in regs_por_id:
                    regs_por_id[bid].sort(key=lambda x: x.get("timestamp_fim", ""))
        except Exception:
            pass  # metricas indisponivel nao aborta

    # Contagem por estado
    cont_estado = {}
    for b in blocos:
        e = b.get("estado", "pendente")
        # Blocos com bloqueado_por preenchido mas estado=pendente contam como bloqueado
        if b.get("bloqueado_por") and e == "pendente":
            e = "bloqueado"
        cont_estado[e] = cont_estado.get(e, 0) + 1

    linhas = []
    linhas.append(f"# {projeto} — plano de execucao")
    linhas.append(f"Gerado em {hoje} a partir de {plano_str}")
    linhas.append("")

    # Resumo
    linhas.append("## Resumo")
    linhas.append("| Estado | Blocos |")
    linhas.append("|---|---|")
    for estado in ("concluido", "em_andamento", "pendente", "bloqueado"):
        n = cont_estado.get(estado, 0)
        linhas.append(f"| {estado} | {n} |")
    linhas.append(f"| **total** | {len(blocos)} |")
    linhas.append("")

    # Blocos
    linhas.append("## Blocos")
    linhas.append("")

    for b in blocos:
        bid = b.get("id", "?")
        titulo = b.get("titulo", "")
        linhas.append(f"### {bid} — {titulo}")
        linhas.append("")

        estado = b.get("estado", "pendente")
        motivo = b.get("bloqueado_por", "")
        estado_txt = estado
        if motivo:
            estado_txt += f"  <- TRAVADO: {motivo}"

        linhas.append(f"- **Complexidade / modelo / revisor:** {b.get('complexidade','?')} / {b.get('modelo','?')} / {b.get('revisor_modelo','?')}")
        linhas.append(f"- **Estado:** {estado_txt}")
        dep = b.get("depende_de") or []
        linhas.append(f"- **Depende de:** {', '.join(dep) if dep else 'nenhum'}")
        linhas.append(f"- **Comando de teste:** `{b.get('comando_teste', '') or 'nao definido'}`")
        linhas.append("")

        criterios = b.get("criterio_aceite") or []
        if criterios:
            linhas.append("**Critérios de aceite:**")
            for i, c in enumerate(criterios, 1):
                linhas.append(f"{i}. {c}")
            linhas.append("")

        spec_rel = b.get("spec", "")
        if spec_rel:
            spec_path = raiz / spec_rel
            secoes = _extrair_secoes(spec_path)
            linhas.append("**Spec (objetivo e escopo):**")
            linhas.append("")
            for linha in secoes.splitlines():
                linhas.append(linha)
            linhas.append("")
        else:
            linhas.append("spec ausente")
            linhas.append("")

        linhas.append("---")
        linhas.append("")

    # Metricas
    if regs_por_id:
        linhas.append("## Metricas")
        linhas.append("")
        linhas.append("| Bloco | Turnos | Tentativas | Veredito | Modelo efetivo |")
        linhas.append("|---|---|---|---|---|")
        for b in blocos:
            bid = b.get("id", "?")
            regs = regs_por_id.get(bid)
            if not regs:
                continue
            ultimo = regs[-1]
            usados = ultimo.get("turnos_usados")
            orcados = ultimo.get("turnos_orcados", "?")
            turnos = f"{usados}/{orcados}" if usados is not None else f"?/{orcados}"
            tent = len(regs)
            veredito = ultimo.get("veredito", "?")
            modelo_ef = ultimo.get("modelo_efetivo", "?")
            linhas.append(f"| {bid} | {turnos} | {tent} | {veredito} | {modelo_ef} |")
        linhas.append("")

    conteudo = "\n".join(linhas)
    try:
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(conteudo, encoding="utf-8")
        print(f"Relatorio gerado: {saida}")
    except Exception as e:
        print(f"Erro ao gravar {saida}: {e}")
        return 1

    return 0


def main():
    args = sys.argv[1:]
    fase_arg = None
    saida_str = None
    i = 0
    while i < len(args):
        if args[i] == "--fase" and i + 1 < len(args):
            fase_arg = args[i + 1]; i += 2
        elif args[i] == "--saida" and i + 1 < len(args):
            saida_str = args[i + 1]; i += 2
        elif args[i] in ("--fase", "--saida"):
            print(f"Uso: exportar-relatorio.py [--fase <nome>] [--saida <caminho>]"); return 1
        else:
            i += 1

    plano_str = _resolve_plano(fase_arg)

    # Saida padrao deriva do diretorio do plano
    if saida_str is None:
        saida_str = os.path.join(os.path.dirname(plano_str), "RELATORIO.md")

    metricas_str = _resolve_metricas(plano_str)
    raiz = Path(__file__).resolve().parent.parent
    saida = raiz / saida_str
    sys.exit(gerar(saida, raiz, plano_str, metricas_str))


if __name__ == "__main__":
    main()
