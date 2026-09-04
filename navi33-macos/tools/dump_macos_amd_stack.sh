#!/usr/bin/env bash
# EXECUTE ESTE SCRIPT NO SEU MAC / HACKINTOSH (nao no container).
# Faz um inventario SOMENTE-LEITURA da pilha grafica AMD do macOS instalado.
# Nao copia binarios da Apple e nao modifica nada: gera um relatorio de texto
# que e o insumo para a fase 2 da analise.
#
#   ./dump_macos_amd_stack.sh > relatorio-$(sw_vers -productVersion).txt
set -uo pipefail

E=/System/Library/Extensions

echo "=== macOS ==="
sw_vers
uname -a
echo

echo "=== Kexts AMD presentes ==="
ls -1d "$E"/AMD*.kext 2>/dev/null || echo "(nenhum em $E)"
echo

echo "=== Bundle IDs, versoes e IOPCIMatch (device IDs suportados) ==="
for k in "$E"/AMD*.kext; do
  [ -d "$k" ] || continue
  plist="$k/Contents/Info.plist"
  [ -f "$plist" ] || continue
  echo "--- $(basename "$k")"
  /usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$plist" 2>/dev/null
  /usr/libexec/PlistBuddy -c "Print :CFBundleVersion"    "$plist" 2>/dev/null
  # Device IDs declarados pelo kext (0x1002 = AMD)
  grep -ao '0x[0-9a-fA-F]\{4\}1002' "$plist" 2>/dev/null | sort -u | tr '\n' ' '
  echo
done
echo

echo "=== Personalities de controller (mapeamento ASIC -> driver) ==="
for k in "$E"/AMDRadeonX6000*.kext "$E"/AMDRadeonX6800*.kext; do
  [ -d "$k" ] || continue
  echo "--- $(basename "$k")"
  /usr/libexec/PlistBuddy -c "Print :IOKitPersonalities" "$k/Contents/Info.plist" 2>/dev/null \
    | grep -E "IOClass|IOPCIMatch|IOName|CFBundleIdentifier" | sed 's/^ */  /'
done
echo

echo "=== Bundles de acelerador por ASIC (dentro do X6000 framework) ==="
find "$E" -maxdepth 6 -name "*.plugin" -o -maxdepth 6 -name "AMDRadeon*Bundle*" 2>/dev/null | head -40
ls -1 /System/Library/Extensions/AMDRadeonX6000HWServices.kext/Contents/PlugIns 2>/dev/null
echo

echo "=== Drivers Metal instalados (userspace) ==="
ls -1 /System/Library/Frameworks/Metal.framework/Versions/A/Resources 2>/dev/null | head -20
ls -1d /System/Library/Extensions/AMDRadeonX*.kext/Contents/MacOS/* 2>/dev/null
echo

echo "=== ASICs que o AMDRadeonX6000HWLibs conhece (strings) ==="
HWLIB=$(find "$E" -name "AMDRadeonX6000HWLibs*" -maxdepth 4 2>/dev/null | head -1)
if [ -n "${HWLIB:-}" ]; then
  strings -a "$HWLIB" 2>/dev/null \
    | grep -oiE 'navi[0-9]{2}|sienna|dimgrey|navy_flounder|beige_goby|gfx10[0-9]{2}|gfx11[0-9]{2}|dcn[0-9_]+' \
    | sort | uniq -c | sort -rn | head -40
else
  echo "(AMDRadeonX6000HWLibs nao encontrado)"
fi
echo

echo "=== GPU vista pelo sistema agora ==="
ioreg -rw0 -c IOPCIDevice -k IOName 2>/dev/null \
  | grep -E '"(model|IOName|vendor-id|device-id|revision-id|IOClass)"' | head -40
echo
system_profiler SPDisplaysDataType 2>/dev/null
