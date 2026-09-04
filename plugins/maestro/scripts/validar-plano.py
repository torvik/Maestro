#!/usr/bin/env python3
"""Valida o plano contra as regras invioláveis. Deterministico."""
import json, sys, os

PLANO = os.environ.get("MAESTRO_PLANO", "plano/blocos.json")
HAIKU = "haiku"
OBRIG = ["id","titulo","spec","complexidade","modelo","agente","depende_de",
         "arquivos_permitidos","criterio_aceite","estado"]
# marcadores EARS (pt-BR e en) — criterio deve virar teste
EARS = ("DEVE", "SHALL", "QUANDO", "WHEN", "SE ", "IF ", "ENQUANTO", "WHILE", "ONDE", "WHERE")
VAGO = ("rapido", "rápido", "adequadamente", "corretamente", "bem ", "boa ", "funcionar bem",
        "amigavel", "amigável", "otimizado", "eficiente", "robusto", "limpo")
ORC = {"C1": 15, "C2": 15, "C3": 30, "C4": 30, "C5": 40}
RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4}

def rank(model):
    for k, v in RANK.items():
        if k in (model or "").lower():
            return v
    return 0

def main():
    if not os.path.exists(PLANO):
        print(f"ERRO: plano nao encontrado em {PLANO}"); return 1
    with open(PLANO, encoding="utf-8") as f:
        plano = json.load(f)

    blocos = plano.get("blocos", [])
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

        for dep in b.get("depende_de", []):
            if dep not in ids:
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
        if not b.get("comando_teste"):
            avisos.append(f"{bid}: sem comando_teste — nao ha prova objetiva de pronto")
        orc = b.get("orcamento_turnos")
        if orc is None:
            avisos.append(f"{bid}: sem orcamento_turnos (sugerido: {ORC.get(comp, 30)})")
        elif orc > 60:
            avisos.append(f"{bid}: orcamento de {orc} turnos e alto — bloco provavelmente grande demais")
        # C4 inteiro no modelo forte: quase sempre deve virar desenho + implementacao
        if comp == "C4" and "opus" in (b.get("modelo") or "").lower():
            avisos.append(f"{bid}: C4 inteiro no modelo forte — considere quebrar em desenho + implementacao")
        if b.get("tentativas", 0) >= 2 and b.get("estado") == "pendente":
            avisos.append(f"{bid}: {b['tentativas']} tentativas — revisar a SPEC antes de escalar modelo")
        if b.get("estado") == "em_andamento":
            avisos.append(f"{bid}: marcado em_andamento (sessao interrompida?)")

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

    print(f"\nValidando {PLANO} — {len(blocos)} blocos\n")
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
