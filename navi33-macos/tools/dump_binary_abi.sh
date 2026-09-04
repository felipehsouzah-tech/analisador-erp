#!/usr/bin/env bash
# Extrai a ABI de um binario Mach-O da Apple (kext ou bundle Metal).
#
# Nao e "abrir codigo fonte": e ler a tabela de simbolos, que o Mach-O carrega.
# Simbolos C++ sao mangled e desmangam para a assinatura completa — nome de
# classe, metodo, tipos dos parametros e const-ness. E assim que o NootRX
# descobriu AMDRadeonX6000_AmdAsicInfoNavi23::getEnumeratedRevisionNumber().
#
# Roda em Linux com llvm (nm/cxxfilt/objdump), nao precisa de macOS.
#
#   ./tools/dump_binary_abi.sh /caminho/AMDRadeonX6000MTLDriver
#   ./tools/dump_binary_abi.sh <bin> --grep Compil    # filtra por assunto
set -euo pipefail

BIN="${1:?uso: $0 <binario Mach-O> [--grep PADRAO]}"
FILTER="${3:-}"

NM=$(command -v llvm-nm || command -v nm)
FILT=$(command -v llvm-cxxfilt || command -v c++filt)
[ -n "$NM" ] && [ -n "$FILT" ] || { echo "precisa de llvm-nm e llvm-cxxfilt" >&2; exit 1; }

apply_filter() { [ -n "$FILTER" ] && grep -i -- "$FILTER" || cat; }

echo "=== $(basename "$BIN") ==="
echo

# -g: so globais/externos. Simbolos locais nao formam contrato.
syms=$("$NM" -g "$BIN" 2>/dev/null | awk '{print $NF}' | grep -E '^_?_?Z|^_[A-Za-z]' | sort -u || true)
[ -n "$syms" ] || { echo "(nenhum simbolo global — binario stripped?)"; exit 0; }

echo "--- Classes C++ e seus metodos (o contrato real) ---"
echo "$syms" | grep -E '^_?_Z' | sed 's/^_//' | "$FILT" | sed 's/^/  /' | apply_filter \
  | sed -E 's/^  ([A-Za-z_][A-Za-z0-9_]*)::/  \1 :: /' | sort | head -200

echo
echo "--- Simbolos C exportados ---"
echo "$syms" | grep -vE '^_?_Z' | sed 's/^/  /' | apply_filter | head -80

echo
echo "--- Resumo por classe ---"
echo "$syms" | grep -E '^_?_Z' | sed 's/^_//' | "$FILT" \
  | grep -oE '^[A-Za-z_][A-Za-z0-9_]*(::[A-Za-z_][A-Za-z0-9_]*)?' \
  | cut -d: -f1 | sort | uniq -c | sort -rn | head -30
