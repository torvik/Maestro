#!/usr/bin/env python3
"""Gera um esqueleto de spec de bloco com as onze secoes canonicas.

Uso: python scripts/novo-bloco.py <ID> <titulo> [--saida <caminho>] [--forcar]

O esqueleto gerado nao contem conteudo inventado: cada campo e cada item de
lista carrega um marcador <<PREENCHER: ...>> especifico da secao. O linter do
bloco F3-06 reconhece e recusa qualquer spec que ainda contenha esse literal.
"""
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

USO = "Uso: python scripts/novo-bloco.py <ID> <titulo> [--saida <caminho>] [--forcar]"

TITULOS = [
    "## 1. Identificação",
    "## 2. Objetivo",
    "## 3. Escopo",
    "## 4. Não faça",
    "## 5. Contrato",
    "## 6. Regras",
    "## 7. Arquivos",
    "## 8. Dados",
    "## 9. Critérios de aceite (EARS)",
    "## 10. Casos de teste obrigatórios",
    "## 11. Pare e pergunte",
]


def _p(descricao):
    """Formata um marcador de preenchimento com descricao especifica da secao."""
    return f"<<PREENCHER: {descricao}>>"


def _slug(titulo):
    """Minusculas, acentos reduzidos a ASCII, fora de [a-z0-9] vira hifen,
    hifens consecutivos colapsados, pontas removidas, truncado em 40 chars."""
    minusculo = titulo.lower()
    normalizado = unicodedata.normalize("NFKD", minusculo)
    ascii_str = normalizado.encode("ascii", "ignore").decode("ascii")
    trocado = re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")
    return trocado[:40].rstrip("-")


def _conteudo(id_bloco, titulo):
    linhas = [f"# {id_bloco} — {titulo}", ""]

    linhas.append(TITULOS[0])
    linhas.append(f"- Complexidade: {_p('complexidade C1 a C5 deste bloco')}")
    linhas.append(f"- Modelo: {_p('modelo do executor deste bloco')}")
    linhas.append(f"- Agente: {_p('agente executor (operario, implementador ou arquiteto)')}")
    linhas.append(f"- Revisor: {_p('modelo do revisor deste bloco')}")
    linhas.append(f"- Depende de: {_p('IDs dos blocos dos quais este depende, ou nenhum')}")
    linhas.append(f"- Orçamento: {_p('orcamento de turnos deste bloco')}")
    linhas.append(f"- Comando de teste: {_p('comando que valida este bloco')}")
    linhas.append("")

    linhas.append(TITULOS[1])
    linhas.append(_p("o que muda no sistema depois deste bloco e por que isso importa"))
    linhas.append("")

    linhas.append(TITULOS[2])
    linhas.append(f"- {_p('primeiro item do escopo deste bloco')}")
    linhas.append(f"- {_p('segundo item do escopo deste bloco')}")
    linhas.append(f"- {_p('terceiro item do escopo deste bloco')}")
    linhas.append("")

    linhas.append(TITULOS[3])
    linhas.append(f"- {_p('primeira restricao explicita deste bloco')}")
    linhas.append(f"- {_p('segunda restricao explicita deste bloco')}")
    linhas.append(f"- {_p('terceira restricao explicita deste bloco')}")
    linhas.append("")

    linhas.append(TITULOS[4])
    linhas.append(_p("invocacao, formatos de entrada e saida, codigos de saida deste bloco"))
    linhas.append("")

    linhas.append(TITULOS[5])
    linhas.append(f"- {_p('primeira regra de implementacao deste bloco')}")
    linhas.append(f"- {_p('segunda regra de implementacao deste bloco')}")
    linhas.append(f"- {_p('terceira regra de implementacao deste bloco')}")
    linhas.append("")

    linhas.append(TITULOS[6])
    linhas.append(_p("arquivos criados ou alterados por este bloco"))
    linhas.append("")

    linhas.append(TITULOS[7])
    linhas.append(_p("de onde vem os dados e valores usados por este bloco"))
    linhas.append("")

    linhas.append(TITULOS[8])
    linhas.append(f"1. {_p('primeiro criterio EARS (QUANDO/SE ... O SISTEMA DEVE ...)')}")
    linhas.append(f"2. {_p('segundo criterio EARS (QUANDO/SE ... O SISTEMA DEVE ...)')}")
    linhas.append(f"3. {_p('terceiro criterio EARS (QUANDO/SE ... O SISTEMA DEVE ...)')}")
    linhas.append("")

    linhas.append(TITULOS[9])
    linhas.append(f"- {_p('primeiro caso de teste, com entrada e saida esperada')}")
    linhas.append(f"- {_p('segundo caso de teste, com entrada e saida esperada')}")
    linhas.append(f"- {_p('terceiro caso de teste, com entrada e saida esperada')}")
    linhas.append("")

    linhas.append(TITULOS[10])
    linhas.append(f"- {_p('primeira condicao em que o executor deve parar e perguntar ao dono')}")
    linhas.append(f"- {_p('segunda condicao em que o executor deve parar e perguntar ao dono')}")
    linhas.append(f"- {_p('terceira condicao em que o executor deve parar e perguntar ao dono')}")
    linhas.append("")

    return "\n".join(linhas)


def _gravar(caminho, texto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def _auto_teste():
    texto = _conteudo("AUTO-TESTE", "Autoteste de novo-bloco")
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "auto-teste.md"
        _gravar(caminho, texto)
        with open(caminho, "r", encoding="utf-8") as f:
            gerado = f.read()

    titulos_encontrados = [linha for linha in gerado.splitlines() if linha.startswith("## ")]
    if titulos_encontrados != TITULOS:
        print("FALHA: titulos ausentes ou fora de ordem no esqueleto gerado.")
        sys.exit(1)

    print("OK: autoteste de novo-bloco.py passou.")
    sys.exit(0)


def main():
    argv = sys.argv[1:]

    if "--auto-teste" in argv:
        _auto_teste()
        return

    forcar = "--forcar" in argv
    if forcar:
        argv = [a for a in argv if a != "--forcar"]

    saida = None
    if "--saida" in argv:
        idx = argv.index("--saida")
        if idx + 1 >= len(argv):
            print(USO)
            sys.exit(2)
        saida = argv[idx + 1]
        argv = argv[:idx] + argv[idx + 2:]

    posicionais = argv
    if len(posicionais) < 2 or not posicionais[0] or not posicionais[1]:
        print(USO)
        sys.exit(2)

    id_bloco, titulo = posicionais[0], posicionais[1]

    if saida:
        caminho = Path(saida)
    else:
        slug = _slug(titulo)
        nome = f"{id_bloco}-{slug}.md" if slug else f"{id_bloco}.md"
        caminho = Path("plano/specs") / nome

    if caminho.exists() and not forcar:
        print(f"ERRO: arquivo ja existe: {caminho}")
        sys.exit(1)

    texto = _conteudo(id_bloco, titulo)

    try:
        _gravar(caminho, texto)
    except OSError as e:
        print(f"ERRO: falha ao escrever arquivo: {e}")
        sys.exit(3)

    print(str(caminho).replace("\\", "/"))
    sys.exit(0)


if __name__ == "__main__":
    main()
