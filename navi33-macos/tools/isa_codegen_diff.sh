#!/usr/bin/env bash
# Compila o mesmo kernel para gfx1032 (Navi 23) e gfx1102 (Navi 33) e compara
# a ISA gerada. Mede o tamanho real do trabalho da fase 5: nao o que a
# documentacao diz que mudou, e sim o que o compilador de fato emite diferente.
#
# Requer LLVM com target amdgcn (llc). Ubuntu: apt install llvm
#
#   ./tools/isa_codegen_diff.sh [dir-de-saida]
set -euo pipefail

OUT="${1:-isa-diff}"
A="${A:-gfx1032}"   # Navi 23 — o que o macOS emite hoje
B="${B:-gfx1102}"   # Navi 33 — o que precisaria emitir

command -v llc >/dev/null || { echo "llc nao encontrado (apt install llvm)" >&2; exit 1; }
mkdir -p "$OUT"

cat > "$OUT/kernel.ll" <<'LL'
target triple = "amdgcn-amd-amdhsa"

; exercita o que diverge entre as duas ISAs: aritmetica 16-bit (True16),
; fma f32, acesso a memoria global e atomic fadd (so existe no gfx11).
define amdgpu_kernel void @k(ptr addrspace(1) %out, ptr addrspace(1) %in,
                             half %h0, half %h1, float %f) {
entry:
  %tid = call i32 @llvm.amdgcn.workitem.id.x()
  %gep = getelementptr float, ptr addrspace(1) %in, i32 %tid
  %v   = load float, ptr addrspace(1) %gep, align 4
  %fma = call float @llvm.fma.f32(float %v, float %f, float %v)
  %hs  = fadd half %h0, %h1
  %hm  = fmul half %hs, %h0
  %he  = fpext half %hm to float
  %sum = fadd float %fma, %he
  %o   = getelementptr float, ptr addrspace(1) %out, i32 %tid
  store float %sum, ptr addrspace(1) %o, align 4
  %old = atomicrmw fadd ptr addrspace(1) %out, float %sum monotonic, align 4
  ret void
}
declare i32 @llvm.amdgcn.workitem.id.x()
declare float @llvm.fma.f32(float, float, float)
LL

for cpu in "$A" "$B"; do
  llc -mtriple=amdgcn-amd-amdhsa -mcpu="$cpu" -O2 "$OUT/kernel.ll" -o "$OUT/$cpu.s"
  grep -oE '^[[:space:]]+[a-z][a-z0-9_]+' "$OUT/$cpu.s" | tr -d ' \t' > "$OUT/$cpu.ops"
done

only_a=$(comm -23 <(sort -u "$OUT/$A.ops") <(sort -u "$OUT/$B.ops"))
only_b=$(comm -13 <(sort -u "$OUT/$A.ops") <(sort -u "$OUT/$B.ops"))
common=$(comm -12 <(sort -u "$OUT/$A.ops") <(sort -u "$OUT/$B.ops") | wc -l)
na=$(echo "$only_a" | grep -c . || true); nb=$(echo "$only_b" | grep -c . || true)

echo "=== opcodes emitidos ==="
printf "  so em %s: %s\n" "$A" "$na"
echo "$only_a" | sed 's/^/      - /'
printf "  so em %s: %s\n" "$B" "$nb"
echo "$only_b" | sed 's/^/      + /'
printf "  em comum: %s\n" "$common"
python3 -c "print('  sobreposicao: %.1f%%' % (100*$common/($common+$na+$nb)))"

echo
echo "=== s_delay_alu (mitigacao de hazard exigida pelo gfx11) ==="
printf "  %s: %s  |  %s: %s\n" \
  "$A" "$(grep -c s_delay_alu "$OUT/$A.s" || true)" \
  "$B" "$(grep -c s_delay_alu "$OUT/$B.s" || true)"

echo
echo "=== base dos argumentos do kernel (ABI) ==="
grep -m1 's_load' "$OUT/$A.s" | sed "s/^/  $A: /"
grep -m1 's_load' "$OUT/$B.s" | sed "s/^/  $B: /"

echo
echo "Assembly completo em $OUT/$A.s e $OUT/$B.s"
