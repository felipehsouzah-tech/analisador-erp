#!/usr/bin/env bash
# Isola o CONTRATO da Apple a partir de varias implementacoes dele.
#
# Ideia: o bundle Metal da AMD e o da Intel implementam a MESMA interface —
# senao o Metal nao conseguiria carregar os dois. Entao:
#
#   simbolos comuns a fornecedores diferentes  = contrato da Apple  (o que
#                                                precisamos satisfazer)
#   simbolos exclusivos de um                  = implementacao dele (o que
#                                                precisamos reescrever)
#
# Por isso ler o bundle do Navi 23 ajuda mesmo nao sendo a RX 7600: o que se
# extrai dali nao e "como falar com Navi 23", e "como falar com o Metal".
#
# Roda no Linux com llvm-nm/llvm-cxxfilt.
#
#   ./tools/abi_intersect.sh AMDRadeonX6000MTLDriver AppleIntelKBLGraphicsMTLDriver [...]
set -euo pipefail

[ $# -ge 2 ] || { echo "uso: $0 <bin1> <bin2> [bin3...]  (2+ implementacoes)" >&2; exit 1; }

NM=$(command -v llvm-nm || command -v nm)
FILT=$(command -v llvm-cxxfilt || command -v c++filt)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

names=()
for bin in "$@"; do
  n=$(basename "$bin")
  names+=("$n")
  "$NM" -g "$bin" 2>/dev/null | awk '{print $NF}' \
    | grep -E '^_?_?Z|^_[A-Za-z]' | sed 's/^_//' | sort -u > "$TMP/$n.syms" || true
  echo "$n: $(wc -l < "$TMP/$n.syms") simbolos globais"
done

# intersecao progressiva
cp "$TMP/${names[0]}.syms" "$TMP/common"
for n in "${names[@]:1}"; do
  comm -12 "$TMP/common" "$TMP/$n.syms" > "$TMP/c2" && mv "$TMP/c2" "$TMP/common"
done

nc=$(wc -l < "$TMP/common")
echo
echo "=== CONTRATO DA APPLE — comum a todas as implementacoes ($nc) ==="
echo "Isto e o que um plugin novo precisa expor, independente da GPU."
"$FILT" < "$TMP/common" | sed 's/^/  /' | head -120

echo
echo "=== ESPECIFICO DE CADA IMPLEMENTACAO ==="
for n in "${names[@]}"; do
  only=$(comm -23 "$TMP/$n.syms" "$TMP/common" | wc -l)
  tot=$(wc -l < "$TMP/$n.syms")
  pct=$(python3 -c "print('%.1f' % (100*$only/$tot))" 2>/dev/null || echo "?")
  printf "  %-45s %5s exclusivos de %s (%s%%)\n" "$n" "$only" "$tot" "$pct"
done

echo
echo "Leitura: quanto maior o contrato comum e menor a fracao exclusiva,"
echo "mais viavel a fase 5 — o trabalho novo e so a parte exclusiva."
