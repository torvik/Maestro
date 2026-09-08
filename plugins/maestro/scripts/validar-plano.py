#!/usr/bin/env python3
"""Valida o plano contra as regras invioláveis. Deterministico."""
import json, sys, os, glob as _glob

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")

HAIKU = "haiku"
OBRIG = ["id","titulo","spec","complexidade","modelo","agente","revisor_modelo",
         "depende_de","arquivos_permitidos","criterio_aceite","estado",
         "comando_teste","orcamento_turnos","tentativas"]
# marcadores EARS (pt-BR e en) — criterio deve virar teste
EARS = ("DEVE", "SHALL", "QUANDO", "WHEN", "SE ", "IF ", "ENQUANTO", "WHILE", "ONDE", "WHERE")
VAGO = ("rapido", "rápido", "adequadamente", "corretamente", "bem ", "boa ", "funcionar bem",
        "amigavel", "amigável", "otimizado", "eficiente", "robusto", "limpo")
ORC = {"C1": 15, "C2": 15, "C3": 30, "C4": 30, "C5": 40}
RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4}

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


def rank(model):
    for k, v in RANK.items():
        if k in (model or "").lower():
            return v
    return 0

def main():
    # Parsing de argumentos
    args = sys.argv[1:]
    fase_arg = None
    i = 0
    while i < len(args):
        if args[i] == "--fase" and i + 1 < len(args):
            fase_arg = args[i + 1]; i += 2
        elif args[i] == "--fase":
            print("Uso: validar-plano.py [--fase <nome>]"); return 1
        else:
            i += 1

    plano = _resolve_plano(fase_arg)

    if not os.path.exists(plano):
        print(f"ERRO: plano nao encontrado em {plano}"); return 1
    with open(plano, encoding="utf-8") as f:
        dados = json.load(f)

    blocos = dados.get("blocos", [])
    ids = [b.get("id") for b in blocos]
    erros, avisos = [], []

    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        erros.append(f"IDs duplicados: {', '.join(sorted(dup))}")

    for b in blocos:
        bid = b.get("id", "?")
        for campo in OBRIG:
            if campo not in b or b[campo] in (None, ""):
                erros.append(f"{bid}: campo obrigatorio ausente: {campo}")

        # Verificar se arquivo de spec existe no caminho declarado
        spec_path = b.get("spec", "")
        if spec_path and not os.path.exists(spec_path):
            avisos.append(f"{bid}: arquivo de spec nao encontrado: {spec_path}")

        comp = (b.get("complexidade") or "").upper()
        if comp not in ("C1","C2","C3","C4","C5"):
            erros.append(f"{bid}: complexidade invalida ({comp!r})")

        # Regra inviolavel: C5 nunca em Haiku
        if comp == "C5":
            if HAIKU in (b.get("modelo") or "").lower():
                erros.append(f"{bid}: bloco C5 com modelo Haiku — PROIBIDO")
            if HAIKU in (b.get("revisor_modelo") or "").lower():
                erros.append(f"{bid}: bloco C5 revisado por Haiku — PROIBIDO")

        # Revisor >= executor
        rv = b.get("revisor_modelo")
        if rv and rank(rv) < rank(b.get("modelo")):
            erros.append(f"{bid}: revisor ({rv}) inferior ao executor ({b.get('modelo')})")

        # depende_de: sem cruzamento de fase (formato "fase:ID" proibido)
        for dep in b.get("depende_de", []):
            if ":" in str(dep):
                erros.append(f"{bid}: depende_de cruza fase — '{dep}' e invalido (blocos de fases diferentes sao planos independentes)")
            elif dep not in ids:
                erros.append(f"{bid}: depende de bloco inexistente: {dep}")

        crits = b.get("criterio_aceite") or []
        if not crits:
            erros.append(f"{bid}: sem criterio de aceite")
        for c in crits:
            cu = c.upper()
            if not any(k in cu for k in EARS):
                avisos.append(f"{bid}: criterio fora de EARS -> \"{c[:52]}...\"")
            cl = c.lower()
            for v in VAGO:
                if v in cl:
                    avisos.append(f"{bid}: criterio vago (termo '{v.strip()}') -> reescreva com numero")
                    break
        orc = b.get("orcamento_turnos")
        if orc is not None and orc > 60:
            avisos.append(f"{bid}: orcamento de {orc} turnos e alto — bloco provavelmente grande demais")
        # C4 inteiro no modelo forte: quase sempre deve virar desenho + implementacao
        if comp == "C4" and "opus" in (b.get("modelo") or "").lower():
            avisos.append(f"{bid}: C4 inteiro no modelo forte — considere quebrar em desenho + implementacao")
        if b.get("tentativas", 0) >= 2 and b.get("estado") == "pendente":
            avisos.append(f"{bid}: {b['tentativas']} tentativas — revisar a SPEC antes de escalar modelo")
        if b.get("estado") == "em_andamento":
            avisos.append(f"{bid}: marcado em_andamento (sessao interrompida?) — rode /maestro:retomar")

    # ciclos
    grafo = {b["id"]: b.get("depende_de", []) for b in blocos if b.get("id")}
    visto, pilha = set(), set()
    def ciclo(n):
        if n in pilha: return True
        if n in visto: return False
        visto.add(n); pilha.add(n)
        for d in grafo.get(n, []):
            if d in grafo and ciclo(d): return True
        pilha.discard(n); return False
    for n in list(grafo):
        if ciclo(n):
            erros.append(f"Ciclo de dependencia envolvendo {n}"); break

    print(f"\nValidando {plano} — {len(blocos)} blocos\n")
    for e in erros: print(f"  ERRO   {e}")
    for a in avisos: print(f"  AVISO  {a}")
    if not erros and not avisos:
        print("  Plano valido. Nenhum problema encontrado.")
    elif not erros:
        print(f"\n  Plano valido com {len(avisos)} aviso(s).")
    print()
    return 1 if erros else 0

if __name__ == "__main__":
    sys.exit(main())
