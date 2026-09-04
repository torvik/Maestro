#!/usr/bin/env python3
"""Quadro do plano. Deterministico: nao consome token de modelo."""
import json, sys, os

PLANO = os.environ.get("MAESTRO_PLANO", "plano/blocos.json")
CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")

def _ver_plugin():
    for base in (".claude/plugins/maestro", ".claude", "."):
        c = os.path.join(base, ".claude-plugin", "plugin.json")
        if os.path.exists(c):
            try:
                return json.load(open(c, encoding="utf-8")).get("version")
            except Exception:
                return None
    return None

def checar_versao():
    inst = _ver_plugin()
    usada = None
    if os.path.exists(CONFIG):
        try:
            usada = json.load(open(CONFIG, encoding="utf-8")).get("maestro_versao")
        except Exception:
            pass
    if not inst and not usada:
        return
    print(f"Maestro {inst or '?'}" + (f"  (plano criado com {usada})" if usada else ""))
    if inst and usada and inst.split(".")[0] != usada.split(".")[0]:
        print(f"  ATENCAO: o plano foi criado na versao {usada} e o plugin e {inst}.")
        print("  O formato do plano mudou. Rode /maestro:setup para migrar antes de executar.")
    print()
ICON = {"concluido": "[x]", "em_andamento": "[~]", "bloqueado": "[!]", "pendente": "[ ]"}


PESO = {"haiku": 1, "sonnet": 2, "opus": 5, "fable": 10}

def _tier(m):
    m = (m or "").lower()
    for k in PESO:
        if k in m:
            return k
    return "?"

def distribuicao(blocos):
    """Distribuicao de trabalho por modelo. Meta: ~15% Opus, ~60% Sonnet, ~25% Haiku."""
    cont, custo = {}, {}
    for b in blocos:
        t = _tier(b.get("modelo"))
        cont[t] = cont.get(t, 0) + 1
        custo[t] = custo.get(t, 0) + PESO.get(t, 0)
    if not cont:
        return
    total_b, total_c = len(blocos), sum(custo.values()) or 1
    print("--- DISTRIBUICAO POR MODELO ---")
    for t in ("haiku", "sonnet", "opus", "fable", "?"):
        if t not in cont:
            continue
        print(f"  {t:<8}{cont[t]:>4} blocos{100*cont[t]/total_b:>6.0f}% dos blocos{100*custo[t]/total_c:>6.0f}% do custo")
    opus = 100 * custo.get("opus", 0) / total_c
    if opus > 25:
        print(f"\n  ATENCAO: modelo forte em {opus:.0f}% do custo (meta: ate 25%).")
        print("  Cheque se algum bloco C4 pode ser quebrado em desenho (forte) + implementacao (medio).")
    tent = [(b["id"], b.get("tentativas", 0)) for b in blocos if b.get("tentativas", 0) >= 2]
    for bid, n in tent:
        print(f"  {bid}: {n} tentativas -> corrija a SPEC antes de escalar o modelo")
    print()

def main():
    if not os.path.exists(PLANO):
        print(f"Plano nao encontrado em {PLANO}. Rode /maestro:setup.")
        return 1
    checar_versao()
    with open(PLANO, encoding="utf-8") as f:
        plano = json.load(f)

    blocos = plano.get("blocos", [])
    by_id = {b["id"]: b for b in blocos}
    done = {b["id"] for b in blocos if b.get("estado") == "concluido"}

    liberados, travados, bloqueados = [], [], []
    for b in blocos:
        if b.get("estado") != "pendente":
            continue
        if b.get("bloqueado_por"):
            bloqueados.append(b); continue
        faltam = [d for d in b.get("depende_de", []) if d not in done]
        (travados if faltam else liberados).append((b, faltam))

    total = len(blocos)
    pct = round(100 * len(done) / total) if total else 0
    print(f"\n=== {plano.get('projeto','projeto').upper()} — {len(done)}/{total} blocos ({pct}%) ===\n")

    fases = {}
    for b in blocos:
        fases.setdefault(b.get("fase", "-"), []).append(b)

    for fase in sorted(fases):
        itens = fases[fase]
        d = sum(1 for b in itens if b.get("estado") == "concluido")
        print(f"{fase}  ({d}/{len(itens)})")
        for b in itens:
            estado = b.get("estado", "pendente")
            marca = ICON.get(estado, "[ ]")
            extra = ""
            if b.get("bloqueado_por"):
                extra = f"  <- TRAVADO: {b['bloqueado_por']}"
            elif estado == "pendente":
                faltam = [x for x in b.get("depende_de", []) if x not in done]
                if faltam:
                    extra = f"  (espera {', '.join(faltam)})"
            if b.get("tentativas", 0) >= 2:
                extra += f"  !! {b['tentativas']} tentativas"
            print(f"  {marca} {b['id']:<8} {b.get('complexidade','--'):<3} {b['titulo'][:44]}{extra}")
        print()

    print("--- PROXIMO ---")
    if liberados:
        for b, _ in liberados[:3]:
            print(f"  {b['id']}  {b.get('complexidade')}  {b['titulo']}  -> {b.get('agente','?')} / {b.get('modelo','?')}")
    else:
        print("  Nenhum bloco liberado.")
    if bloqueados:
        print("\n--- TRAVADOS (decisao/credencial pendente) ---")
        for b in bloqueados:
            print(f"  {b['id']}  {b['bloqueado_por']}")
    print()
    distribuicao(blocos)
    return 0

if __name__ == "__main__":
    sys.exit(main())
