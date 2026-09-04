#!/usr/bin/env bash
# Inventario SOMENTE-LEITURA da pilha grafica AMD do macOS.
# Nao copia binarios da Apple e nao modifica nada: gera um relatorio de texto.
#
# Modo 1 — macOS ja bootado (precisa de video funcionando):
#     ./dump_macos_amd_stack.sh > relatorio.txt
#
# Modo 2 — Terminal do Recovery, ou volume do sistema montado a partir de
# outro macOS. NAO precisa de GPU acelerada, entao serve quando a placa
# instalada nao tem driver. Descubra o ponto de montagem com `diskutil list`:
#     ./dump_macos_amd_stack.sh --root /Volumes/Macintosh\ HD > relatorio.txt
set -uo pipefail

ROOT=""
case "${1:-}" in
  --root) ROOT="${2:?uso: --root /caminho/do/volume}" ;;
  -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
esac

E="$ROOT/System/Library/Extensions"
LIVE=0
[ -z "$ROOT" ] && LIVE=1

if [ ! -d "$E" ]; then
  echo "ERRO: nao achei $E" >&2
  echo "Se estiver no Recovery, monte o volume do sistema e use --root." >&2
  exit 1
fi

plistget() { /usr/libexec/PlistBuddy -c "Print :$2" "$1" 2>/dev/null; }

echo "=== Contexto ==="
if [ "$LIVE" = 1 ]; then sw_vers; uname -a; else echo "modo offline, root=$ROOT"; fi
# versao do sistema alvo, funciona nos dois modos
plistget "$ROOT/System/Library/CoreServices/SystemVersion.plist" ProductVersion
plistget "$ROOT/System/Library/CoreServices/SystemVersion.plist" ProductBuildVersion
echo

echo "=== Kexts AMD presentes ==="
ls -1d "$E"/AMD*.kext 2>/dev/null || echo "(nenhum)"
echo

echo "=== Bundle IDs, versoes e device IDs declarados ==="
for k in "$E"/AMD*.kext; do
  [ -d "$k" ] || continue
  p="$k/Contents/Info.plist"; [ -f "$p" ] || continue
  echo "--- $(basename "$k")"
  echo "    id:  $(plistget "$p" CFBundleIdentifier)"
  echo "    ver: $(plistget "$p" CFBundleVersion)"
  ids=$(grep -ao '0x[0-9a-fA-F]\{4\}1002' "$p" 2>/dev/null | sort -u | tr '\n' ' ')
  echo "    ids: ${ids:-(nenhum no Info.plist)}"
done
echo

echo "=== PlugIns do HWServices (HWLibs por familia) ==="
ls -1 "$E"/AMDRadeonX6000HWServices.kext/Contents/PlugIns 2>/dev/null || echo "(nao encontrado)"
echo

echo "=== PERGUNTA CENTRAL: existe algum vestigio de RDNA 3 na pilha? ==="
# Se algo aqui retornar resultado, muda a analise. Esperado: nada.
found=0
while IFS= read -r bin; do
  hits=$(strings -a "$bin" 2>/dev/null \
    | grep -oiE 'gfx11[0-9]{2}|gc_11_[0-9]_[0-9]|dcn3[._]?2|smu_13|navi3[0-9]|rs64|mes_11' \
    | sort | uniq -c | sort -rn)
  if [ -n "$hits" ]; then
    echo "--- $(basename "$bin")"; echo "$hits" | sed 's/^/    /'; found=1
  fi
done < <(find "$E" -type f -perm -u+x -path "*AMD*" 2>/dev/null)
[ "$found" = 0 ] && echo "NENHUM vestigio de RDNA 3 encontrado (resultado esperado)."
echo

echo "=== Controle: ASICs RDNA 2 que a pilha conhece ==="
while IFS= read -r bin; do
  hits=$(strings -a "$bin" 2>/dev/null \
    | grep -oiE 'gfx10[0-9]{2}|gc_10_3[_0-9]*|dcn3[._]?0[0-9]?|smu_11|navi2[0-9]|sienna|dimgrey|navy_flounder|beige_goby' \
    | sort | uniq -c | sort -rn | head -12)
  [ -n "$hits" ] && { echo "--- $(basename "$bin")"; echo "$hits" | sed 's/^/    /'; }
done < <(find "$E" -type f -perm -u+x -path "*AMD*" 2>/dev/null)
echo

if [ "$LIVE" = 1 ]; then
  echo "=== GPU vista pelo sistema agora ==="
  ioreg -rw0 -c IOPCIDevice 2>/dev/null \
    | grep -E '"(model|IOName|vendor-id|device-id|revision-id|IOClass)"' | head -40
  echo
  system_profiler SPDisplaysDataType 2>/dev/null
fi
