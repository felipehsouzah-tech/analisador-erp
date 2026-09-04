# Fase 2 sem Mac: inventariar a pilha AMD a partir do Linux

## O bloqueio

Hardware alvo: **Ryzen 5 3600X + RX 7600**, sem outra GPU.

O 3600X (Matisse) **nao tem grafico integrado**. A RX 7600 nao tem driver de
framebuffer no macOS. Somando os dois: depois que o kernel assume o controle
do video, nao ha nada que desenhe na tela. O boot picker do OpenCore aparece
(e UEFI GOP, antes do kernel), mas o desktop nao.

Consequencia: **nao da para rodar um inventario de dentro do macOS.** Nem
instalado, nem no Recovery de forma confiavel.

## A saida: nao bootar o macOS

O inventario nao precisa do sistema rodando — precisa apenas dos arquivos.
`tools/scan_amd_stack.py` foi escrito para isso: Python puro, sem PlistBuddy,
sem `strings`, sem nada da Apple. Roda no Linux (ou WSL) contra uma raiz de
sistema macOS montada.

### Passo 1 — obter o instalador

Baixe o instalador do macOS Tahoe pelos meios normais. No Linux, o
`gibMacOS` (script publico) resolve o download a partir do catalogo da Apple e
entrega o `InstallAssistant.pkg`.

### Passo 2 — desempacotar

```bash
sudo apt install p7zip-full dmg2img apfs-fuse   # ou o equivalente da sua distro

7z x InstallAssistant.pkg -oIA          # pkg (xar) -> payload
# procure o SharedSupport.dmg dentro de IA/
7z x IA/SharedSupport.dmg -oSS          # ou: dmg2img SharedSupport.dmg
```

Dentro do SharedSupport ha o asset do sistema
(`com_apple_MobileAsset_MacSoftwareUpdate/*.zip`). Descompacte-o ate chegar
numa imagem que contenha `System/Library/Extensions`.

### Passo 3 — montar

```bash
mkdir -p /mnt/macos
apfs-fuse -o allow_other imagem.img /mnt/macos
ls /mnt/macos/*/System/Library/Extensions/AMD*   # confirma que chegou
```

Se a imagem for HFS+ em vez de APFS, `sudo mount -t hfsplus -o loop,ro`
resolve.

### Passo 4 — inventariar

```bash
python3 tools/scan_amd_stack.py \
    --root /mnt/macos/<volume> \
    --out relatorio-tahoe.txt
```

## O que o relatorio responde

O script varre os binarios Mach-O dos kexts AMD atras de marcadores de
RDNA 3 (`gfx11xx`, `gc_11_x_x`, `dcn32`, `smu_13`, `navi3x`, `rs64`, `mes_11`)
e imprime, junto, um **grupo de controle** com os marcadores RDNA 2.

O controle existe por um motivo: sem ele, "nao achei nada" pode significar
tanto "nao ha RDNA 3" quanto "a varredura falhou". Se o bloco RDNA 2 vier
populado e o RDNA 3 vier vazio, o resultado negativo e confiavel.

O script foi testado nos dois sentidos contra uma arvore de kexts sintetica:
detecta corretamente a ausencia, detecta a presenca, e pega marcador partido
na borda de bloco de leitura (le com sobreposicao de 64 bytes).

## O problema maior, que o inventario nao resolve

Vale registrar de forma explicita, porque afeta o projeto inteiro e nao so
esta fase: **nesta maquina nao existe ciclo de desenvolvimento de driver.**

Escrever bring-up de GPU exige iterar: bootar, travar, ler o panic, corrigir,
repetir. Isso normalmente depende de uma das tres coisas:

1. uma segunda GPU que funcione, para ter tela enquanto a primeira e o alvo;
2. depuracao de kernel por rede (KDP) ou serial, a partir de outra maquina;
3. um alvo virtualizado.

Sem nenhuma delas, cada tentativa termina em tela preta sem diagnostico — nao
ha como distinguir "o kext nao carregou" de "carregou e travou no bring-up da
IMU". O inventario da fase 2 e viavel sem isso; o desenvolvimento do item 8
da secao 5 do `02-pilha-macos.md`, nao.

A opcao (2) e a unica que nao envolve comprar hardware de video: KDP por
ethernet, com um segundo computador rodando o depurador. Se o projeto seguir,
e por ai que ele teria que comecar — montar o ambiente de depuracao antes de
escrever qualquer linha de kext.
