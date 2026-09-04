#!/usr/bin/env python3
"""
Extrai a ABI de binarios Mach-O da Apple. Python puro.

Nao precisa de macOS, nem de VM, nem de WSL, nem de LLVM instalado. Precisa
apenas dos ARQUIVOS — que saem do instalador do macOS com 7-Zip.

Dois modos:

  # 1) despejar a ABI de um binario
  python macho_abi.py AMDRadeonX6000MTLDriver

  # 2) isolar o contrato da Apple, interseccionando implementacoes de
  #    fornecedores diferentes (o que e comum nao pode ser detalhe de um deles)
  python macho_abi.py --intersect AMDRadeonX6000MTLDriver AppleIntelKBLGraphicsMTLDriver
"""

import argparse
import struct
import sys
from pathlib import Path

MH_MAGIC_64, MH_CIGAM_64 = 0xFEEDFACF, 0xCFFAEDFE
FAT_MAGIC, FAT_CIGAM = 0xCAFEBABE, 0xBEBAFECA
LC_SYMTAB = 0x2
N_EXT, N_TYPE, N_SECT = 0x01, 0x0E, 0x0E


def _slices(data):
    """Devolve (offset, endian) de cada arquitetura; trata binario fat."""
    if len(data) < 8:
        return []
    magic = struct.unpack(">I", data[:4])[0]
    if magic in (FAT_MAGIC, FAT_CIGAM):
        n = struct.unpack(">I", data[4:8])[0]
        out = []
        for i in range(n):
            off = 8 + i * 20
            if off + 20 > len(data):
                break
            _, _, sub, _, _ = struct.unpack(">5I", data[off:off + 20])
            out.append(sub)
        return [(o, None) for o in out]
    return [(0, None)]


def symbols(path):
    """Simbolos globais definidos ou referenciados no Mach-O."""
    data = Path(path).read_bytes()
    found = set()
    for base, _ in _slices(data):
        if base + 4 > len(data):
            continue
        magic = struct.unpack("<I", data[base:base + 4])[0]
        if magic == MH_MAGIC_64:
            e = "<"
        elif magic == MH_CIGAM_64:
            e = ">"
        else:
            continue
        ncmds = struct.unpack(e + "I", data[base + 16:base + 20])[0]
        off = base + 32
        for _ in range(ncmds):
            if off + 8 > len(data):
                break
            cmd, sz = struct.unpack(e + "2I", data[off:off + 8])
            if sz == 0:
                break
            if cmd == LC_SYMTAB and off + 24 <= len(data):
                symoff, nsyms, stroff, strsize = struct.unpack(
                    e + "4I", data[off + 8:off + 24])
                symoff += base
                stroff += base
                for i in range(nsyms):
                    p = symoff + i * 16
                    if p + 16 > len(data):
                        break
                    strx, ntype = struct.unpack(e + "IB", data[p:p + 5])
                    if not (ntype & N_EXT):
                        continue
                    s = stroff + strx
                    if s >= len(data):
                        continue
                    end = data.find(b"\x00", s)
                    name = data[s:end if end != -1 else None].decode(
                        "utf-8", "replace")
                    if name:
                        # Mach-O prefixa com um '_'; remover APENAS esse.
                        # lstrip("_") comeria tambem o '_' do mangling _Z,
                        # quebrando o demangling silenciosamente.
                        found.add(name[1:] if name.startswith("_") else name)
            off += sz
    return found


def _llvm_demangle(syms):
    """Usa llvm-cxxfilt/c++filt se existir: da a assinatura COMPLETA.

    O desmanglador embutido abaixo recupera classe e metodo, mas nao os tipos
    dos parametros. Para reimplementar uma interface os tipos importam, entao
    quando a ferramenta do LLVM esta disponivel ela e preferida.
    """
    import shutil
    import subprocess
    exe = shutil.which("llvm-cxxfilt") or shutil.which("c++filt")
    if not exe:
        return None
    try:
        out = subprocess.run([exe], input="\n".join(syms), text=True,
                             capture_output=True, timeout=60)
        if out.returncode != 0:
            return None
        lines = out.stdout.splitlines()
        return dict(zip(syms, lines)) if len(lines) == len(syms) else None
    except Exception:
        return None


def demangle(sym):
    """Desmangla os casos Itanium comuns: Classe::metodo e vtable/typeinfo.

    Nao cobre a gramatica inteira — cobre o suficiente para levantar a
    superficie de uma interface, que e o objetivo aqui. Simbolos nao
    reconhecidos voltam inalterados.
    """
    if not sym.startswith("_Z"):
        return sym
    body = sym[2:]
    tag = ""
    for pref, label in (("TV", "vtable for "), ("TI", "typeinfo for "),
                        ("TS", "typeinfo name for ")):
        if body.startswith(pref):
            tag, body = label, body[2:]
            break
    nested = body.startswith("N")
    if nested:
        body = body[1:]
    for q in ("K", "V"):          # cv-qualifiers do 'this'
        body = body[1:] if body.startswith(q) else body
    parts, i = [], 0
    while i < len(body) and body[i].isdigit():
        j = i
        while j < len(body) and body[j].isdigit():
            j += 1
        n = int(body[i:j])
        if j + n > len(body):
            break
        parts.append(body[j:j + n])
        i = j + n
    if not parts:
        return sym
    name = "::".join(parts)
    if tag:
        return tag + name
    return name + ("()" if nested else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binaries", nargs="+")
    ap.add_argument("--intersect", action="store_true",
                    help="isola o que e comum a todos (= contrato da Apple)")
    ap.add_argument("--raw", action="store_true", help="nao desmanglar")
    args = ap.parse_args()

    sets = {}
    for b in args.binaries:
        try:
            sets[Path(b).name] = symbols(b)
        except Exception as e:
            print("erro lendo %s: %s" % (b, e), file=sys.stderr)
    if not sets:
        sys.exit("nenhum binario legivel")

    if args.raw:
        show = lambda s: s
        note = ""
    else:
        allsyms = sorted(set().union(*sets.values()))
        table = _llvm_demangle(allsyms)
        if table:
            show = lambda s: table.get(s, demangle(s))
            note = "  [assinaturas completas via llvm-cxxfilt]"
        else:
            show = demangle
            note = ("  [sem llvm-cxxfilt: nomes de classe/metodo apenas,\n"
                    "   sem tipos de parametro. instale llvm para o completo]")
    if note:
        print(note)

    for n, s in sets.items():
        print("%s: %d simbolos globais" % (n, len(s)))

    if not args.intersect or len(sets) < 2:
        for n, s in sets.items():
            print("\n=== %s ===" % n)
            for sym in sorted(show(x) for x in s):
                print("  " + sym)
        return

    common = set.intersection(*sets.values())
    print("\n=== CONTRATO — comum a todas as implementacoes (%d) ===" % len(common))
    print("O que um plugin novo precisa expor, independente da GPU.\n")
    for sym in sorted(show(x) for x in common):
        print("  " + sym)

    print("\n=== ESPECIFICO DE CADA IMPLEMENTACAO ===")
    for n, s in sets.items():
        only = len(s - common)
        pct = 100.0 * only / len(s) if s else 0
        print("  %-46s %5d de %5d exclusivos (%.1f%%)" % (n, only, len(s), pct))


if __name__ == "__main__":
    main()
