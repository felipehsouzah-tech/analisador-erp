#!/usr/bin/env python3
"""
Inventario SOMENTE-LEITURA da pilha grafica AMD de um sistema macOS.

Roda em Linux, Windows ou macOS: nao usa PlistBuddy, `strings` nem qualquer
ferramenta da Apple. So precisa de Python 3.8+ e de um caminho para a raiz do
sistema macOS — que pode ser:

  - o proprio macOS bootado          --root /
  - um volume montado no Recovery    --root "/Volumes/Macintosh HD"
  - uma imagem do instalador montada no Linux (apfs-fuse), sem Mac nenhum

Uso:
    python3 scan_amd_stack.py --root /caminho/da/raiz [--out relatorio.txt]

A pergunta central: existe algum vestigio de RDNA 3 (gfx11xx, gc_11_x_x,
dcn32, smu_13, navi3x, rs64, mes_11) nos binarios AMD do macOS? O grupo de
controle RDNA 2 e impresso junto para que um resultado negativo seja
interpretavel, e nao apenas "o script nao achou nada".
"""

import argparse
import plistlib
import re
import sys
from pathlib import Path

# A busca por RDNA 3 e dividida em dois niveis, e a distincao importa.
#
# NIVEL 1 — marcadores de IMPLEMENTACAO. Sao nomes que so aparecem se houver
# codigo real de gfx11 (firmware, blocos de display, microengine). Se algum
# destes aparecer, a premissa do projeto cai e a analise precisa ser refeita.
RDNA3_IMPL = re.compile(
    rb"gfx11[0-9]{2}|gc_11_[0-9]_[0-9]|dcn3[._]?2[01]?|smu_13|mes_11|rs64",
    re.I,
)
# NIVEL 2 — apenas o NOME do ASIC. Isto NAO prova implementacao.
#
# Contexto historico: em 2020, numa beta do Big Sur, foi encontrada no
# AMDRadeonX6000HWServices uma referencia a "Navi 31" com 80 CUs / 5120
# shaders, ao lado das entradas de Navi 21/22/23. A leitura na epoca foi que
# a Apple teria trabalho de RDNA 3 planejado — que nunca se materializou em
# driver. Entao encontrar "navi3x" aqui e um falso positivo esperado, nao uma
# descoberta: e um nome numa tabela, sem codigo por tras.
RDNA3_NAME = re.compile(rb"navi3[0-9]", re.I)
# Grupo de controle: RDNA 2, que sabidamente esta na pilha.
RDNA2 = re.compile(
    rb"gfx10[0-9]{2}|gc_10_3[_0-9]*|dcn3[._]?0[0-9]?|smu_11|navi2[0-9]"
    rb"|sienna|dimgrey|navy_flounder|beige_goby",
    re.I,
)
DEVID = re.compile(rb"0x[0-9a-fA-F]{4}1002")


def printable_scan(path, pattern, chunk=8 << 20):
    """Procura o padrao no arquivo, em blocos, com sobreposicao nas bordas."""
    hits = {}
    overlap = 64
    try:
        with open(path, "rb") as fh:
            tail = b""
            while True:
                buf = fh.read(chunk)
                if not buf:
                    break
                for m in pattern.finditer(tail + buf):
                    key = m.group(0).decode("ascii", "replace").lower()
                    hits[key] = hits.get(key, 0) + 1
                tail = buf[-overlap:]
    except (OSError, PermissionError) as e:
        return None, str(e)
    return hits, None


def read_plist(path):
    try:
        with open(path, "rb") as fh:
            return plistlib.load(fh)
    except Exception:
        return None


def is_macho(path):
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
    except OSError:
        return False
    return magic in (
        b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",   # Mach-O 64/32 LE
        b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce",   # BE
        b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",   # fat
    )


def find_extensions(root, max_depth=8):
    """Localiza System/Library/Extensions sob root.

    A extracao por 7-Zip no Windows aninha as pastas de forma imprevisivel
    (IA/SharedSupport/.../AssetData/...), entao exigir o caminho exato faz o
    script falhar por um motivo que nao e o interessante. Procura em largura
    e devolve a primeira arvore que realmente tenha kexts AMD; se nenhuma
    tiver, devolve a primeira Extensions encontrada.
    """
    direct = root / "System" / "Library" / "Extensions"
    if direct.is_dir():
        return direct

    fallback = None
    queue = [(root, 0)]
    while queue:
        cur, depth = queue.pop(0)
        if depth > max_depth:
            continue
        try:
            entries = sorted(p for p in cur.iterdir() if p.is_dir())
        except (OSError, PermissionError):
            continue
        for d in entries:
            if d.name == "Extensions" and d.parent.name == "Library" \
               and d.parent.parent.name == "System":
                if any(d.glob("AMD*.kext")):
                    return d
                if fallback is None:
                    fallback = d
            queue.append((d, depth + 1))
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="raiz do sistema macOS")
    ap.add_argument("--out", help="grava o relatorio neste arquivo")
    args = ap.parse_args()

    root = Path(args.root)
    ext = find_extensions(root)
    out = []

    def emit(s=""):
        out.append(s)
        print(s)

    if ext is None:
        sys.exit(
            "ERRO: nao achei System/Library/Extensions sob %s\n"
            "Extracao por 7-Zip costuma aninhar pastas; aponte --root para a\n"
            "pasta que contem a arvore extraida e o script procura sozinho." % root
        )
    sysroot = ext.parent.parent.parent

    emit("=== Contexto ===")
    emit("root informado: %s" % root)
    emit("raiz do sistema: %s" % sysroot)
    sv = read_plist(sysroot / "System/Library/CoreServices/SystemVersion.plist")
    if sv:
        emit("macOS %s (build %s)" % (sv.get("ProductVersion", "?"),
                                      sv.get("ProductBuildVersion", "?")))
    else:
        emit("(SystemVersion.plist ilegivel)")
    emit()

    kexts = sorted(p for p in ext.glob("AMD*.kext"))
    emit("=== Kexts AMD presentes (%d) ===" % len(kexts))
    for k in kexts:
        emit("  " + k.name)
    if not kexts:
        emit("  (nenhum — este macOS pode nao ter a pilha AMD)")
    emit()

    emit("=== Bundle IDs, versoes e device IDs declarados ===")
    for k in kexts:
        info = read_plist(k / "Contents" / "Info.plist")
        emit("--- %s" % k.name)
        if not info:
            emit("    (Info.plist ilegivel)")
            continue
        emit("    id:  %s" % info.get("CFBundleIdentifier", "?"))
        emit("    ver: %s" % info.get("CFBundleVersion", "?"))
        raw = (k / "Contents" / "Info.plist").read_bytes()
        ids = sorted({m.group(0).decode() for m in DEVID.finditer(raw)})
        emit("    ids: %s" % (" ".join(ids) if ids else "(nenhum aqui)"))
    emit()

    plugins = ext / "AMDRadeonX6000HWServices.kext" / "Contents" / "PlugIns"
    emit("=== PlugIns do HWServices (HWLibs por familia) ===")
    if plugins.is_dir():
        for p in sorted(plugins.iterdir()):
            emit("  " + p.name)
    else:
        emit("  (nao encontrado)")
    emit()

    binaries = [p for p in ext.rglob("*")
                if p.is_file() and "AMD" in str(p) and is_macho(p)]

    emit("=== NIVEL 1: ha IMPLEMENTACAO de RDNA 3 na pilha? ===")
    emit("(binarios Mach-O varridos: %d)" % len(binaries))
    emit("Procurando: gfx11xx, gc_11_x_x, dcn32/321, smu_13, mes_11, rs64")
    impl = False
    for b in binaries:
        hits, err = printable_scan(b, RDNA3_IMPL)
        if err:
            emit("--- %s: erro de leitura: %s" % (b.name, err))
            continue
        if hits:
            impl = True
            emit("--- %s" % b.relative_to(ext))
            for k, v in sorted(hits.items(), key=lambda x: -x[1]):
                emit("    %6d  %s" % (v, k))
    if not impl:
        emit("NENHUMA implementacao de RDNA 3 encontrada.")
        emit("Resultado esperado: confirma a premissa do plano (modelo B).")
    else:
        emit(">>> A PREMISSA DO PROJETO CAIU. Ha codigo gfx11 na pilha.")
        emit(">>> Reveja docs/04: o plano encolhe do modelo B para o modelo A.")
        emit(">>> Antes disso, descarte falso positivo: 'rs64' pode aparecer")
        emit(">>> em contexto sem relacao com o command processor.")
    emit()

    emit("=== NIVEL 2: o NOME de algum ASIC RDNA 3 aparece? ===")
    emit("Isto NAO prova implementacao. Em 2020 uma beta do Big Sur ja tinha")
    emit("'Navi 31' numa tabela do HWServices, e driver nunca existiu.")
    emit("Serve so para saber se sobrou resquicio de planejamento abandonado.")
    named = False
    for b in binaries:
        hits, err = printable_scan(b, RDNA3_NAME)
        if hits:
            named = True
            emit("--- %s" % b.relative_to(ext))
            for k, v in sorted(hits.items(), key=lambda x: -x[1]):
                emit("    %6d  %s" % (v, k))
    if not named:
        emit("Nenhum nome de ASIC RDNA 3 na pilha.")
    elif not impl:
        emit(">>> Nome presente, implementacao ausente: e o caso historico do")
        emit(">>> Big Sur se repetindo. NAO altera a conclusao do plano.")
    emit()

    emit("=== Controle: ASICs RDNA 2 que a pilha conhece ===")
    emit("(se este bloco tambem vier vazio, a varredura falhou —")
    emit(" o resultado negativo acima nao valeria nada)")
    for b in binaries:
        hits, err = printable_scan(b, RDNA2)
        if hits:
            top = sorted(hits.items(), key=lambda x: -x[1])[:10]
            emit("--- %s" % b.relative_to(ext))
            for k, v in top:
                emit("    %6d  %s" % (v, k))
    emit()

    if args.out:
        Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
        print("\n[relatorio gravado em %s]" % args.out)


if __name__ == "__main__":
    main()
