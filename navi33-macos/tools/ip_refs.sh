#!/usr/bin/env bash
# Conta referencias a blocos de IP nos drivers de referencia gfx10 vs gfx11.
# Usa limite de identificador, nao substring: um grep por "mes" casa com
# "times"/"names" e infla a contagem.
#
#   ./tools/fetch_sources.sh sources && ./tools/ip_refs.sh sources
set -euo pipefail
SRC="${1:-sources}"
A="$SRC/gfx_v10_0.c"   # Navi 2x (RDNA 2)
B="$SRC/gfx_v11_0.c"   # Navi 3x (RDNA 3)
for f in "$A" "$B"; do
  [ -f "$f" ] || { echo "faltando $f — rode tools/fetch_sources.sh primeiro" >&2; exit 1; }
done

count() { grep -oE "$2" "$1" 2>/dev/null | wc -l | tr -d ' '; }

printf "%-28s %10s %10s\n" "bloco/simbolo" "gfx10" "gfx11"
printf "%-28s %10s %10s\n" "----------------------------" "-----" "-----"
row() { printf "%-28s %10s %10s\n" "$1" "$(count "$A" "$2")" "$(count "$B" "$2")"; }

row "MES (escalonador)"      '\b(mes|MES)(_[a-zA-Z0-9_]*)?\b'
row "IMU (bring-up)"         '\b(imu|IMU)(_[a-zA-Z0-9_]*)?\b'
row "RS64 (CP 64-bit)"       '[rR][sS]64'
row "CE (constant engine)"   '\bce_fw[_a-zA-Z0-9]*'

echo
echo "SDMA v6 -> dependencia de MES:"; grep -n "mes_userqueue" "$SRC/sdma_v6_0.c" || echo "  (nenhuma)"
echo "mes_v11_0.c: $(wc -l < "$SRC/mes_v11_0.c" 2>/dev/null || echo '?') linhas"
