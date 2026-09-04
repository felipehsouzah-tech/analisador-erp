#!/usr/bin/env bash
# Baixa as fontes publicas usadas na analise (kernel Linux amdgpu + LLVM AMDGPU).
# Nada aqui e codigo da Apple: e o material de referencia sobre o hardware.
set -euo pipefail

OUT="${1:-sources}"
mkdir -p "$OUT"

LINUX=https://raw.githubusercontent.com/torvalds/linux/master/drivers/gpu/drm/amd
LLVM=https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/lib/Target/AMDGPU

fetch() { echo "  -> $(basename "$2")"; curl -fsSL "$1" -o "$OUT/$2"; }

echo "[amdgpu] blocos de IP"
fetch "$LINUX/amdgpu/gfx_v10_0.c"          gfx_v10_0.c          # GC 10.3 (Navi 2x)
fetch "$LINUX/amdgpu/gfx_v11_0.c"          gfx_v11_0.c          # GC 11.0 (Navi 3x)
fetch "$LINUX/amdgpu/sdma_v5_2.c"          sdma_v5_2.c
fetch "$LINUX/amdgpu/sdma_v6_0.c"          sdma_v6_0.c
fetch "$LINUX/amdgpu/mes_v11_0.c"          mes_v11_0.c          # so existe no RDNA3+
fetch "$LINUX/amdgpu/amdgpu_discovery.c"   amdgpu_discovery.c
fetch "$LINUX/amdgpu/amdgpu_drv.c"         amdgpu_drv.c

echo "[display] DCN"
fetch "$LINUX/display/dc/core/dc_resource.c"  dc_resource.c
fetch "$LINUX/display/include/dal_types.h"    dal_types.h

echo "[llvm] ISA"
fetch "$LLVM/AMDGPU.td"          AMDGPU.td
fetch "$LLVM/GCNProcessors.td"   GCNProcessors.td

echo "OK -> $OUT"
