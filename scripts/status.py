#!/usr/bin/env python3
"""Quadro do plano. Deterministico: nao consome token de modelo."""
import json, sys, os, glob as _glob, urllib.request

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
# Versao
# ---------------------------------------------------------------------------

_REPO_PADRAO = "torvik/Maestro"
_RAW_URL = "https://raw.githubusercontent.com/{repo}/main/plugins/maestro/.claude-plugin/plugin.json"

def checar_atualizacao():
    """Verifica versao remota. Silencioso se offline. Avisa se ha update."""
    inst = _ver_plugin()
    if not inst:
        return
    repo = _REPO_PADRAO
    # Tenta ler campo repository do plugin.json local
    for base in (".claude/plugins/maestro", ".claude", "."):
        c = os.path.join(base, ".claude-plugin", "plugin.json")
        if os.path.exists(c):
            try:
                data = json.load(open(c, encoding="utf-8"))
                repo = data.get("repository", repo)
            except Exception:
                pass
            break
    url = _RAW_URL.format(repo=repo)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "maestro-status/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        remota = data.get("version")
    except Exception:
        return  # offline ou GitHub indisponivel — silencioso

    if not remota:
        return

    def _t(v):
        try: return tuple(int(x) for x in str(v).split("."))
        except: return (0, 0, 0)

    if _t(remota) > _t(inst):
        print(f"  ATENCAO: nova versao {remota} disponivel (instalada: {inst}).")
        print(f"  Rode /plugin update maestro para atualizar.")
        print()


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

# ---------------------------------------------------------------------------
# Icones e distribuicao
# ---------------------------------------------------------------------------

ICON = {"concluido": "[x]", "em_andamento": "[~]", "bloqueado": "[!]", "pendente": "[ ]"}

PESO = {"haiku": 1, "sonnet": 2, "opus": 5, "fable": 10}
ORC_DEFAULT = {"C1": 15, "C2": 15, "C3": 30, "C4": 30, "C5": 40}

def _tier(m):
    m = (m or "").lower()
    for k in PESO:
        if k in m:
            return k
    return "?"

def distribuicao(blocos):
    """Distribuicao de trabalho por modelo. Meta: ~15% Opus, ~60% Sonnet, ~25% Haiku.
    Custo ponderado por orcamento_turnos — um bloco C5/40 turnos pesa mais que C1/15."""
    cont, custo = {}, {}
    for b in blocos:
        t = _tier(b.get("modelo"))
        comp = (b.get("complexidade") or "").upper()
        orc = b.get("orcamento_turnos") or ORC_DEFAULT.get(comp, 30)
        cont[t] = cont.get(t, 0) + 1
        custo[t] = custo.get(t, 0) + PESO.get(t, 0) * orc
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

# ---------------------------------------------------------------------------
# Dependencias orfas
# ---------------------------------------------------------------------------

def orfaos_por_bloco(blocos):
    """Mapeia id de bloco -> lista de dependencias orfas (ausentes do plano).
    Orfao (R1): dep presente em depende_de e ausente do conjunto de id de
    todos os blocos do mesmo arquivo de plano. R2: todas as orfas do bloco
    sao reportadas, nenhuma e omitida. R5: blocos concluidos tambem entram."""
    ids_validos = {b.get("id") for b in blocos}
    mapa = {}
    for b in blocos:
        orfas = [d for d in b.get("depende_de", []) if d not in ids_validos]
        if orfas:
            mapa[b["id"]] = orfas
    return mapa

# ---------------------------------------------------------------------------
# Metricas: leitura blindada (metricas.json e append-only, nunca escrito aqui)
# ---------------------------------------------------------------------------

def _carregar_metricas(metricas_path):
    """Le e valida plano/metricas.json. Retorna (registros_validos, aviso, descartados).
    aviso e None quando o arquivo esta ausente ou integro; nesse caso a secao de
    metricas deve ser omitida sem nenhuma mensagem (R5). Quando aviso nao e None,
    o arquivo inteiro e tratado como corrompido e registros_validos vem vazio (R6).
    Registro individual sem 'id', ou que nao e objeto, e descartado e contado em
    'descartados', sem afetar os demais nem gerar excecao (R2, R3)."""
    if not os.path.exists(metricas_path):
        return [], None, 0
    try:
        with open(metricas_path, encoding="utf-8") as f:
            m = json.load(f)
    except Exception as e:
        return [], f"JSON invalido ({e})", 0
    if not isinstance(m, dict):
        return [], "formato invalido", 0
    if m.get("schema") != 1:
        return [], f"schema {m.get('schema')} desconhecido", 0
    regs = m.get("registros")
    if not isinstance(regs, list):
        return [], "campo 'registros' nao e uma lista", 0
    validos, descartados = [], 0
    for r in regs:
        if not isinstance(r, dict) or not r.get("id"):
            descartados += 1
            continue
        validos.append(r)
    return validos, None, descartados

# ---------------------------------------------------------------------------
# Detalhe de bloco
# ---------------------------------------------------------------------------

def detalhe_bloco(bid, plano_path, metricas_path):
    if not os.path.exists(plano_path):
        print(f"Plano nao encontrado em {plano_path}.")
        return 1
    with open(plano_path, encoding="utf-8") as f:
        plano = json.load(f)
    blocos = plano.get("blocos", [])
    by_id = {b["id"]: b for b in blocos}

    if bid not in by_id:
        print(f"bloco nao encontrado: {bid}")
        print("IDs validos: " + ", ".join(b["id"] for b in blocos))
        return 1

    b = by_id[bid]
    estado = b.get("estado", "pendente")
    motivo = b.get("bloqueado_por", "")

    estado_txt = estado
    if motivo:
        estado_txt += f"  <- TRAVADO: {motivo}"

    # max_tentativas do config
    max_tent = 2
    if os.path.exists(CONFIG):
        try:
            max_tent = json.load(open(CONFIG, encoding="utf-8")).get("max_tentativas", 2)
        except Exception:
            pass

    spec = b.get("spec", "")
    spec_txt = spec if spec else "(nao definido)"
    if spec and not os.path.exists(spec):
        spec_txt += "  (AUSENTE)"

    print(f"\n=== {b['id']} — {b.get('titulo', '')} ===")
    print(f"  estado           {estado_txt}")
    print(f"  complexidade     {b.get('complexidade','?')}   agente {b.get('agente','?')}")
    print(f"  modelo           {b.get('modelo','?')}   revisor {b.get('revisor_modelo','?')}")
    print(f"  tentativas       {b.get('tentativas', 0)} de {max_tent}")
    print(f"  orcamento        {b.get('orcamento_turnos','?')} turnos")
    print(f"  spec             {spec_txt}")
    print(f"  comando_teste    {b.get('comando_teste','') or '(nao definido)'}")

    print("\n--- DEPENDENCIAS ---")
    deps = b.get("depende_de") or []
    if deps:
        for d in deps:
            dep_estado = by_id[d].get("estado", "?") if d in by_id else "INEXISTENTE"
            print(f"  {d}  {dep_estado}")
    else:
        print("  nenhuma")

    print("\n--- ARQUIVOS PERMITIDOS ---")
    arqs = b.get("arquivos_permitidos") or []
    for a in arqs:
        print(f"  {a}")
    if not arqs:
        print("  (nao definido)")

    print("\n--- CRITERIOS DE ACEITE ---")
    criterios = b.get("criterio_aceite") or []
    for i, c in enumerate(criterios, 1):
        print(f"  {i}. {c}")
    if not criterios:
        print("  (nao definido)")

    print("\n--- NOTAS ---")
    notas = b.get("notas") or []
    for n in notas:
        print(f"  {n}")
    if not notas:
        print("  nenhuma")

    # Metricas do bloco
    regs_todos, aviso, _descartados = _carregar_metricas(metricas_path)
    if aviso:
        print(f"\n  AVISO: metricas.json ignorado — {aviso}. O quadro do plano nao foi afetado.")
    else:
        regs = [r for r in regs_todos if r.get("id") == bid]
        regs.sort(key=lambda x: x.get("timestamp_fim", ""))
        if regs:
            print("\n--- METRICAS ---")
            for r in regs:
                usados = r.get("turnos_usados")
                orcados = r.get("turnos_orcados", "?")
                turnos = f"{usados}/{orcados}" if usados is not None else f"?/{orcados}"
                sha = r.get("commit_sha") or "null"
                print(f"  {r.get('timestamp_fim','')}  {r.get('veredito','?')}  "
                      f"turnos {turnos}  modelo {r.get('modelo_efetivo','?')}  commit {sha}")

    if motivo:
        print(f"\n  -> Para destravar: /maestro:destravar {bid}")

    print()
    return 0

# ---------------------------------------------------------------------------
# Resumo de metricas
# ---------------------------------------------------------------------------

def resumo_metricas(metricas_path):
    regs, aviso, descartados = _carregar_metricas(metricas_path)
    if aviso:
        print(f"  AVISO: metricas.json ignorado — {aviso}. O quadro do plano nao foi afetado.")
        print()
        return
    if descartados:
        print(f"  AVISO: {descartados} registro(s) de metricas.json descartado(s) por falta do campo 'id'.")
    if not regs:
        if descartados:
            print()
        return
    reprovados = sum(1 for r in regs if r.get("veredito") == "reprovado")
    usados = [r.get("turnos_usados") for r in regs if r.get("turnos_usados") is not None]
    orcados = [r.get("turnos_orcados") for r in regs if r.get("turnos_usados") is not None]
    ignorados = sum(1 for r in regs if r.get("turnos_usados") is None)
    ids_duplos = [i for i in {r.get("id") for r in regs} if sum(1 for r in regs if r.get("id") == i) >= 2]
    print("--- METRICAS ---")
    print(f"  blocos medidos: {len(regs)}")
    if usados:
        extra = f"  ({ignorados} sem contagem)" if ignorados else ""
        print(f"  turnos: {sum(usados)}/{sum(orcados)}{extra}")
    else:
        print(f"  turnos: n/a ({ignorados} sem contagem)")
    print(f"  reprovacoes: {reprovados}")
    if ids_duplos:
        print(f"  blocos com 2+ registros: {', '.join(sorted(ids_duplos))}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    fase_arg = None
    bloco_arg = None
    check_update = False

    i = 0
    while i < len(args):
        if args[i] == "--fase" and i + 1 < len(args):
            fase_arg = args[i + 1]; i += 2
        elif args[i] == "--bloco" and i + 1 < len(args):
            bloco_arg = args[i + 1]; i += 2
        elif args[i] == "--check-update":
            check_update = True; i += 1
        elif args[i] == "--fase":
            print("Uso: status.py --fase <nome>"); return 1
        elif args[i] == "--bloco":
            print("Uso: status.py --bloco <ID>"); return 1
        else:
            i += 1

    if check_update:
        checar_atualizacao()
        return 0

    plano_path = _resolve_plano(fase_arg)
    metricas_path = _resolve_metricas(plano_path)

    if bloco_arg:
        return detalhe_bloco(bloco_arg, plano_path, metricas_path)

    if not os.path.exists(plano_path):
        print(f"Plano nao encontrado em {plano_path}. Rode /maestro:setup.")
        return 1
    checar_versao()
    with open(plano_path, encoding="utf-8") as f:
        plano = json.load(f)

    blocos = plano.get("blocos", [])
    done = {b["id"] for b in blocos if b.get("estado") == "concluido"}
    orfaos_map = orfaos_por_bloco(blocos)

    liberados, travados, bloqueados = [], [], []
    for b in blocos:
        if b.get("estado") == "bloqueado":
            bloqueados.append(b); continue
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
            orfas_bloco = orfaos_map.get(b["id"])
            if b.get("bloqueado_por"):
                extra = f"  <- TRAVADO: {b['bloqueado_por']}"
            elif estado == "bloqueado":
                extra = "  <- BLOQUEADO"
            elif orfas_bloco:
                extra = f"  <- ORFAO: {', '.join(orfas_bloco)}"
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
            motivo = b.get("bloqueado_por") or "(estado: bloqueado)"
            print(f"  {b['id']}  {motivo}")
    print()

    if orfaos_map:
        print("--- DEPENDENCIAS ORFAS ---")
        for b in blocos:
            for d in orfaos_map.get(b["id"], []):
                print(f"  {b['id']}  depende de {d}")
        print()

    distribuicao(blocos)
    resumo_metricas(metricas_path)
    checar_atualizacao()
    return 0


if __name__ == "__main__":
    sys.exit(main())
