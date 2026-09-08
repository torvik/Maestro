#!/usr/bin/env python3
"""Analisador e planejador de lotes paralelos.
Deterministico: nao despacha agente, nao escreve em plano/blocos.json.

Uso:
  python scripts/paralelo.py               # imprime lote de ate max_paralelo blocos
  python scripts/paralelo.py --check A B   # verifica se A e B sao paralelizaveis
  python scripts/paralelo.py --max N       # sobrescreve max_paralelo do config
  python scripts/paralelo.py --fase <nome> # usa plano/<nome>/blocos.json
"""
import json, sys, os, glob as _glob

CONFIG = os.environ.get("MAESTRO_CONFIG", "maestro.config.json")
DEFAULT_MAX = 2

# ---------------------------------------------------------------------------
# Resolucao de fase
# ---------------------------------------------------------------------------

def _resolve_plano(fase_arg):
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
            print(f"AVISO: MAESTRO_PLANO ignorado — --fase {fase_arg!r} tem precedencia.", file=sys.stderr)
        caminho = f"plano/{fase_arg}/blocos.json"
        if not os.path.exists(caminho):
            found = sorted(_glob.glob("plano/*/blocos.json"))
            print(f"ERRO: fase {fase_arg!r} nao encontrada ({caminho}).", file=sys.stderr)
            if found:
                fases = [f.split("/")[1] for f in found]
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
        return found[0]
    elif len(found) == 0:
        print("ERRO: nenhum plano encontrado. Rode /maestro:setup.", file=sys.stderr)
        sys.exit(1)
    else:
        fases = [f.split("/")[1] for f in found]
        print(f"ERRO: multiplas fases: {', '.join(fases)} — passe --fase.", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# Algoritmo de disjuncao de globs (fail-closed)
# ---------------------------------------------------------------------------

def _seg_pode_coincidir(a, b):
    """Dois segmentos concretos (sem **) podem coincidir?"""
    if a == "*" or b == "*":
        return True   # * bate com qualquer segmento
    if "*" not in a and "*" not in b:
        return a == b  # dois literais
    return True        # fail-closed: um tem wildcard, assume sobreposicao


def _segs_sobrepoem(pa, pb, memo):
    """Verifica recursivamente se duas listas de segmentos podem coincidir."""
    chave = (tuple(pa), tuple(pb))
    if chave in memo:
        return memo[chave]

    if not pa and not pb:
        resultado = True
    elif not pa:
        resultado = all(s == "**" for s in pb)
    elif not pb:
        resultado = all(s == "**" for s in pa)
    elif pa[0] == "**":
        # ** = 0 segmentos (pula o **) OU ** consome pb[0]
        resultado = (
            _segs_sobrepoem(pa[1:], pb, memo) or
            _segs_sobrepoem(pa, pb[1:], memo)
        )
    elif pb[0] == "**":
        resultado = (
            _segs_sobrepoem(pa, pb[1:], memo) or
            _segs_sobrepoem(pa[1:], pb, memo)
        )
    else:
        if _seg_pode_coincidir(pa[0], pb[0]):
            resultado = _segs_sobrepoem(pa[1:], pb[1:], memo)
        else:
            resultado = False

    memo[chave] = resultado
    return resultado


def globs_podem_sobrepor(pa, pb):
    """True se os dois globs podem bater no mesmo caminho (fail-closed)."""
    memo = {}
    segs_a = pa.replace("\\", "/").split("/")
    segs_b = pb.replace("\\", "/").split("/")
    return _segs_sobrepoem(segs_a, segs_b, memo)


def disjoint(globs_a, globs_b):
    """True se os dois conjuntos de globs sao provadamente disjuntos.
    False (conflito) se qualquer par pode sobrepor."""
    for ga in globs_a:
        for gb in globs_b:
            if globs_podem_sobrepor(ga, gb):
                return False, (ga, gb)   # (disjoint=False, par conflitante)
    return True, None

# ---------------------------------------------------------------------------
# Predicado de elegibilidade C1-C6
# ---------------------------------------------------------------------------

def _deps_transitivas(bid, grafo, cache=None):
    if cache is None:
        cache = {}
    if bid in cache:
        return cache[bid]
    result = set()
    for d in grafo.get(bid, []):
        result.add(d)
        result |= _deps_transitivas(d, grafo, cache)
    cache[bid] = result
    return result


def predicado(a, b, blocos_por_id, done):
    """Verifica C1-C6. Retorna (True, None) ou (False, motivo)."""
    grafo = {bid: bloco.get("depende_de", []) for bid, bloco in blocos_por_id.items()}

    # C1: nenhum depende do outro (transitivo)
    deps_a = _deps_transitivas(a["id"], grafo)
    deps_b = _deps_transitivas(b["id"], grafo)
    if b["id"] in deps_a:
        return False, f"C1: {a['id']} depende de {b['id']}"
    if a["id"] in deps_b:
        return False, f"C1: {b['id']} depende de {a['id']}"

    # C2: ambos pendente com todas as dependencias concluido
    for bloco in (a, b):
        if bloco.get("estado") != "pendente":
            return False, f"C2: {bloco['id']} nao e pendente (estado: {bloco.get('estado')})"
        faltam = [d for d in bloco.get("depende_de", []) if d not in done]
        if faltam:
            return False, f"C2: {bloco['id']} tem dependencias nao concluidas: {faltam}"

    # C3: nenhum tem bloqueado_por preenchido
    for bloco in (a, b):
        if bloco.get("bloqueado_por"):
            return False, f"C3: {bloco['id']} tem bloqueado_por: {bloco['bloqueado_por']}"

    # C4: nenhum e C5
    for bloco in (a, b):
        if (bloco.get("complexidade") or "").upper() == "C5":
            return False, f"C4: {bloco['id']} e C5 — nunca paraleliza"

    # C5: arquivos_permitidos sao provadamente disjuntos
    ga = bloco_globs(a)
    gb = bloco_globs(b)
    ok, par = disjoint(ga, gb)
    if not ok:
        return False, f"C5: globs sobrepoem — '{par[0]}' vs '{par[1]}'"

    # C6: nenhum em_andamento no momento
    for bloco in (a, b):
        if bloco.get("estado") == "em_andamento":
            return False, f"C6: {bloco['id']} esta em_andamento"

    return True, None


def bloco_globs(bloco):
    """Retorna os globs declarados em arquivos_permitidos (nao inclui blocos.json)."""
    return bloco.get("arquivos_permitidos") or []

# ---------------------------------------------------------------------------
# Planejador de lote
# ---------------------------------------------------------------------------

def planejar_lote(blocos, max_n):
    """Retorna lista de blocos para o lote (ate max_n), fail-closed.
    Algoritmo: greedy — pega o primeiro liberado, depois tenta adicionar o proximo
    que seja paralelizavel com todos os ja no lote."""
    done = {b["id"] for b in blocos if b.get("estado") == "concluido"}
    blocos_por_id = {b["id"]: b for b in blocos}

    # Candidatos: pendente, deps ok, sem bloqueio, nao C5
    candidatos = []
    for b in blocos:
        if b.get("estado") != "pendente":
            continue
        if b.get("bloqueado_por"):
            continue
        if (b.get("complexidade") or "").upper() == "C5":
            continue
        faltam = [d for d in b.get("depende_de", []) if d not in done]
        if faltam:
            continue
        candidatos.append(b)

    if not candidatos:
        return [], "nenhum bloco liberado"

    lote = [candidatos[0]]
    for candidato in candidatos[1:]:
        if len(lote) >= max_n:
            break
        # Verifica se paralelizavel com todos os do lote
        pode = True
        for no_lote in lote:
            ok, motivo = predicado(candidato, no_lote, blocos_por_id, done)
            if not ok:
                pode = False
                break
        if pode:
            lote.append(candidato)

    return lote, None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    fase_arg = None
    max_override = None
    check_ids = None

    i = 0
    while i < len(args):
        if args[i] == "--fase" and i + 1 < len(args):
            fase_arg = args[i + 1]; i += 2
        elif args[i] == "--max" and i + 1 < len(args):
            try:
                max_override = int(args[i + 1])
            except ValueError:
                print(f"ERRO: --max requer numero inteiro, recebeu {args[i+1]!r}")
                return 1
            i += 2
        elif args[i] == "--check":
            check_ids = args[i + 1:]
            break
        else:
            i += 1

    plano_path = _resolve_plano(fase_arg)
    if not os.path.exists(plano_path):
        print(f"ERRO: plano nao encontrado em {plano_path}.")
        return 1

    with open(plano_path, encoding="utf-8") as f:
        plano = json.load(f)

    blocos = plano.get("blocos", [])
    blocos_por_id = {b["id"]: b for b in blocos}
    done = {b["id"] for b in blocos if b.get("estado") == "concluido"}

    # Modo --check A B: verifica par especifico
    if check_ids:
        if len(check_ids) < 2:
            print("Uso: paralelo.py --check <ID1> <ID2>")
            return 1
        id_a, id_b = check_ids[0], check_ids[1]
        if id_a not in blocos_por_id:
            print(f"ERRO: bloco {id_a!r} nao encontrado")
            return 1
        if id_b not in blocos_por_id:
            print(f"ERRO: bloco {id_b!r} nao encontrado")
            return 1
        ok, motivo = predicado(blocos_por_id[id_a], blocos_por_id[id_b], blocos_por_id, done)
        if ok:
            print(f"PARALELIZAVEL: {id_a} e {id_b} satisfazem C1-C6")
            return 0
        else:
            print(f"CONFLITO: {id_a} e {id_b} nao podem rodar em paralelo")
            print(f"  Motivo: {motivo}")
            return 1

    # Modo normal: planejar lote
    max_n = max_override
    if max_n is None:
        max_n = DEFAULT_MAX
        if os.path.exists(CONFIG):
            try:
                c = json.load(open(CONFIG, encoding="utf-8"))
                max_n = c.get("max_paralelo", DEFAULT_MAX)
            except Exception:
                pass

    lote, erro = planejar_lote(blocos, max_n)

    if not lote:
        print(f"Lote vazio: {erro}")
        return 1

    print(f"Lote paralelo ({len(lote)} bloco(s), max={max_n}):")
    for b in lote:
        print(f"  {b['id']:<10} {b.get('complexidade','?')}  {b.get('titulo','')[:50]}")
        print(f"             modelo: {b.get('modelo','?')}  agente: {b.get('agente','?')}")

    if len(lote) == 1:
        print("\n  (apenas 1 bloco elegivel — execucao serial equivalente)")

    # Saida estruturada para o maestro (JSON em stderr, texto em stdout)
    print(json.dumps({"lote": [b["id"] for b in lote], "max": max_n}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
