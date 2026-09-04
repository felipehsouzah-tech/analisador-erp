#!/usr/bin/env python3
"""
Calcula o delta de features de ISA entre duas GPUs AMD, a partir do
AMDGPU.td do LLVM (fonte publica e autoritativa para o back-end de shader).

Padrao: gfx1032 (Navi 23 / RX 6600, suportado no macOS)
     vs gfx1102 (Navi 33 / RX 7600, nao suportado)

Uso:
    python3 tools/isa_delta.py [--td caminho/AMDGPU.td] [--a 10_3_0] [--b 11_0_2]

Sem --td, baixa AMDGPU.td do main do llvm-project.

Nota de implementacao: os FeatureSet do LLVM sao aninhados via listconcat E
herdam de um "GCNSubtargetFeatureGeneration" (FeatureGFX10 / FeatureGFX11) que
carrega a propria lista. Um diff que nao expande a geracao superestima as
remocoes (ex.: acusa perda de BVHRayTracingInsts no gfx11, que na verdade vem
de dentro de FeatureGFX11). Este script expande os dois niveis.
"""
import argparse
import json
import re
import sys
import urllib.request

TD_URL = "https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/lib/Target/AMDGPU/AMDGPU.td"


def load_td(path):
    if path:
        return open(path, encoding="utf-8").read()
    with urllib.request.urlopen(TD_URL) as r:
        return r.read().decode("utf-8")


def parse(src):
    isa = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r"def\s+(FeatureISAVersion\w+)\s*:\s*FeatureSet<(.*?)>;", src, re.S
        )
    }
    gen = {
        m.group(1): set(re.findall(r"\bFeature\w+\b", m.group(2)))
        for m in re.finditer(
            r'def\s+(FeatureGFX\d+)\s*:\s*GCNSubtargetFeatureGeneration<\s*"[^"]*",'
            r'\s*"[^"]*",\s*\[(.*?)\]\s*>;',
            src,
            re.S,
        )
    }
    return isa, gen


def resolve(name, isa, gen, seen=None):
    seen = seen or set()
    if name in seen or name not in isa:
        return set()
    seen.add(name)
    body = isa[name]
    out = set()
    for ref in re.findall(r"(FeatureISAVersion\w+)\.Features", body):
        out |= resolve(ref, isa, gen, seen)
    inline = re.sub(r"FeatureISAVersion\w+\.Features", "", body)
    out |= set(re.findall(r"\bFeature\w+\b", inline))
    for g in list(out & set(gen)):
        out |= gen[g]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--td", help="caminho local para AMDGPU.td")
    p.add_argument("--a", default="10_3_0", help="ISA base (Navi 23 = 10_3_0)")
    p.add_argument("--b", default="11_0_2", help="ISA alvo (Navi 33 = 11_0_2)")
    p.add_argument("--json", help="grava o resultado em JSON")
    args = p.parse_args()

    isa, gen = parse(load_td(args.td))
    for v in (args.a, args.b):
        if "FeatureISAVersion" + v not in isa:
            sys.exit("ISA desconhecida: %s" % v)

    a = resolve("FeatureISAVersion" + args.a, isa, gen)
    b = resolve("FeatureISAVersion" + args.b, isa, gen)

    print("gfx%s: %d features" % (args.a.replace("_", ""), len(a)))
    print("gfx%s: %d features" % (args.b.replace("_", ""), len(b)))
    print("\n## Removidas no alvo (%d)" % len(a - b))
    for f in sorted(a - b):
        print("  -", f)
    print("\n## Novas no alvo (%d)" % len(b - a))
    for f in sorted(b - a):
        print("  +", f)
    print(
        "\n## Em comum: %d | Jaccard: %.1f%%"
        % (len(a & b), 100 * len(a & b) / len(a | b))
    )

    if args.json:
        json.dump(
            {args.a: sorted(a), args.b: sorted(b),
             "removed": sorted(a - b), "added": sorted(b - a)},
            open(args.json, "w"), indent=1,
        )


if __name__ == "__main__":
    main()
