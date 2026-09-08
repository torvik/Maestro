#!/usr/bin/env python3
"""Gera plano/RELATORIO.md a partir de blocos.json, specs e metricas.json.
Deterministico: sem texto gerado por modelo, sem consulta ao git.

Uso:
  python scripts/exportar-relatorio.py
  python scripts/exportar-relatorio.py --saida outro/caminho.md
"""

import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime

PLANO = os.environ.get("MAESTRO_PLANO", "plano/blocos.json")
METRICAS = os.environ.get("MAESTRO_METRICAS", "plano/metricas.json")


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


def gerar(saida: Path, raiz: Path):
    plano_path = raiz / PLANO
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
    metricas_path = raiz / METRICAS
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
    linhas.append(f"Gerado em {hoje} a partir de {PLANO}")
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
    saida_str = "plano/RELATORIO.md"
    i = 0
    while i < len(args):
        if args[i] == "--saida" and i + 1 < len(args):
            saida_str = args[i + 1]
            i += 2
        else:
            i += 1

    raiz = Path(__file__).resolve().parent.parent
    saida = raiz / saida_str
    sys.exit(gerar(saida, raiz))


if __name__ == "__main__":
    main()
