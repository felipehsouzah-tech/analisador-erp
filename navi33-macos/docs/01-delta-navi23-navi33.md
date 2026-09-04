# Delta Navi 23 -> Navi 33: o que separa a RX 6600 (funciona no macOS) da RX 7600 (nao funciona)

**Metodo.** Todos os numeros abaixo foram extraidos de fontes publicas e
verificaveis — o driver `amdgpu` do kernel Linux e o back-end AMDGPU do LLVM —
e sao reproduziveis com `tools/fetch_sources.sh` + `tools/isa_delta.py`.
As contagens de referencia usam limite de identificador (`\b(mes|MES)[_a-zA-Z0-9]*`),
nao substring: um grep ingenuo por "mes" casa com `times`/`names` e infla o numero.
Nenhum dado veio de memoria ou de estimativa. Onde ha incerteza, esta marcado
como **[a verificar]**.

**Por que essas duas placas.** A RX 6600 e o vizinho suportado mais proximo da
RX 7600: mesma faixa, mesmo segmento, mesmo numero de CUs (32). Se existisse um
caminho de "spoof" para a 7600, seria por aqui. Este documento mede exatamente
o tamanho desse salto.

| | RX 6600 / 6650 XT | RX 7600 |
|---|---|---|
| Codinome | Dimgrey Cavefish (Navi 23) | Navi 33 |
| Arquitetura | RDNA 2 | RDNA 3 |
| Alvo de shader (LLVM) | `gfx1032` | `gfx1102` |
| Bloco GC | 10.3.4 | 11.0.2 |
| PCI ID | `1002:73FF` (tabela estatica) | enumerado por **IP discovery** |
| Display (DCN) | `DCN_VERSION_3_02` | `DCN_VERSION_3_21` |
| SDMA | v5.2 | v6.0 |
| Driver macOS | `AMDRadeonX6000` | **nao existe** |

---

## 1. Camada de ISA (compilador de shader)

Diff das feature sets do LLVM, expandindo `listconcat` **e** a geracao
(`FeatureGFX10` / `FeatureGFX11`), que tambem carrega features proprias:

```
gfx1032 (Navi 23): 91 features
gfx1102 (Navi 33): 99 features
Em comum: 74   |   Jaccard: 63.8%
```

**Presentes no Navi 23 e ausentes no Navi 33 (17):**
`AtomicFMinFMaxF64FlatInsts`, `AtomicFMinFMaxF64GlobalInsts`, `Dot1Insts`,
`Dot2Insts`, `Dot6Insts`, `FlatOffsetBits12`, `GFX10`, `InstCacheLineSize64`,
`MaxHardClauseLength63`, `PopsExitingWaveID`, `SDWA`, `SDWAOmod`, `SDWAScalar`,
`SDWASdst`, `SMemRealTime`, `SMemTimeInst`, `VMemToLDSLoad`

**Novas no Navi 33 (25):**
`ArchitectedFlatScratch`, `AtomicFaddNoRtnInsts`, `AtomicFaddRtnInsts`,
`D16Writes32BitVgpr`, `Dot8Insts`, `Dot9Insts`, `Dot12Insts`,
`FlatAtomicFaddF32Inst`, `GFX11`, `GFX11Insts`, `InstCacheLineSize128`,
`MADIntraFwdBug`, `MSAALoadDstSelBug`, `MaxHardClauseLength32`,
`MemoryAtomicFAddF32DenormalSupport`, `PackedTID`, `PartialNSAEncoding`,
`PrivEnabledTrap2NopBug`, `RealTrue16Insts`, `True16BitInsts`,
`UserSGPRInit16Bug`, `VALUTransUseHazard`, `VOPDInsts`, `VcmpxPermlaneHazard`,
`WMMA256bInsts`

### Os quatro itens que matam o spoof

1. **`SDWA` sumiu** (4 features). Sub-Dword Addressing e uma *classe de
   codificacao de instrucao* inteira. Codigo compilado para gfx1032 usa SDWA;
   no gfx1102 esses opcodes nao existem. Nao e um bit de configuracao, e o
   formato binario da instrucao.
2. **`VOPDInsts` e novo.** RDNA 3 introduz emissao dupla (VOPD) — outra
   codificacao nova que o compilador do macOS nao sabe gerar.
3. **`True16BitInsts` / `RealTrue16Insts`.** Muda o modelo de registradores de
   16 bits. Afeta alocacao de registrador, nao so selecao de instrucao.
4. **`FlatOffsetBits12` -> ausente** e **`ArchitectedFlatScratch`**. Muda a
   largura do offset em acessos flat e a forma como o *scratch* e configurado.
   Este ultimo tem impacto **no driver de kernel**, nao so no compilador.

Somam-se `InstCacheLineSize` 64 -> 128 e `MaxHardClauseLength` 63 -> 32:
parametros de agendamento que produzem codigo incorreto ou lento se herdados
do alvo errado.

> Consequencia pratica: o compilador Metal (AIR -> ISA) embarcado no macOS
> emite gfx10.3. Nao existe caminho de configuracao que o faca emitir gfx11 —
> o back-end gfx11 simplesmente nao foi escrito.

---

## 2. Camada de kernel (o que um kext teria que fazer)

Aqui o salto e maior que na ISA, e e mensuravel:

### 2.1 O Command Processor mudou de CPU

```
ocorrencias de "rs64" em gfx_v11_0.c (Navi 3x): 145
ocorrencias de "rs64" em gfx_v10_0.c (Navi 2x):   0
```

No RDNA 2 os microengines do CP (PFP/ME/MEC) sao cores **F32**. No RDNA 3 sao
cores **RS64** (64-bit). Todo o caminho de carga de microcodigo, configuracao
de cache de instrucao e bring-up do CP e codigo novo — `gfx_v11_0_cp_gfx_load_pfp_microcode_rs64`,
`gfx_v11_0_config_pfp_cache_rs64`, etc. nao tem equivalente no gfx10.

### 2.2 O Constant Engine deixou de existir

```
referencias a "ce_fw" em gfx_v10_0.c: 20
referencias a "ce_fw" em gfx_v11_0.c:  0
```

O RDNA 2 tem um Constant Engine com firmware proprio (`dimgrey_cavefish_ce.bin`).
No RDNA 3 ele foi removido. Qualquer driver que monte command buffers no
modelo gfx10 (que assume o CE) esta montando pacotes para um motor que nao
existe no silicio.

### 2.3 Firmware: nomes, quantidade e formato diferentes

| Navi 23 | Navi 33 |
|---|---|
| `dimgrey_cavefish_ce.bin` | *(removido)* |
| `dimgrey_cavefish_pfp.bin` | `gc_11_0_2_pfp.bin` (RS64) |
| `dimgrey_cavefish_me.bin` | `gc_11_0_2_me.bin` (RS64) |
| `dimgrey_cavefish_mec.bin` + `mec2.bin` | `gc_11_0_2_mec.bin` |
| `dimgrey_cavefish_rlc.bin` | `gc_11_0_2_rlc.bin` |
| — | `gc_11_0_2_mes.bin` / `mes_2.bin` / `mes1.bin` |
| — | firmware de **IMU** |
| — | `gc_11_0_0_toc.bin` |
| `sdma_5_2_*.bin` | `sdma_6_0_2.bin` |

O macOS nao distribui nenhum firmware `gc_11_*`. Ele nao esta no sistema, e
nao ha de onde carrega-lo dentro da pilha da Apple.

### 2.4 Blocos inteiramente novos que o driver teria que implementar

- **MES (Micro Engine Scheduler)** — 2.092 linhas so em `mes_v11_0.c`. E o
  escalonador de filas em hardware. Contando identificadores (nao substring),
  ha **26** referencias a MES em `gfx_v11_0.c` e **zero** em `gfx_v10_0.c`. O
  SDMA v6 tambem passa a depender dele: `sdma_v6_0.c` faz
  `#include "mes_userqueue.h"`, ou seja, as filas de usuario do DMA agora
  saem pelo MES. Existe firmware de MES para
  RDNA 2, mas o caminho grafico do RDNA 2 nao passa por ele — no RDNA 3 ele e
  central. O modelo de submissao de trabalho e diferente.
- **IMU (Infrastructure Management Unit)** — **29** referencias no gfx11 e
  **zero** no gfx10: o bloco e novo no RDNA 3. Faz o power-up e a
  inicializacao do bloco grafico. Sem trazer a IMU, a GPU nao sai do reset.
- **PSP / TOC** — sequencia de boot seguro diferente.

### 2.5 Display: DCN 3.0.2 -> DCN 3.2.1

Confirmado em `dc_resource.c`:

```c
if (ASICREV_IS_DIMGREY_CAVEFISH_P(...))  dc_version = DCN_VERSION_3_02;  // Navi 23
...
case AMDGPU_FAMILY_GC_11_0_0:
    dc_version = DCN_VERSION_3_2;
    if (ASICREV_IS_GC_11_0_2(...))       dc_version = DCN_VERSION_3_21;  // Navi 33
```

Duas versoes maiores de distancia no display engine. Registradores, DMCUB,
pipeline de scanout e gerenciamento de clock diferem. Isso e o que decide se
existe **imagem na tela**, independente de aceleracao 3D.

### 2.6 Enumeracao: a placa nem se apresenta do mesmo jeito

A RX 6600 esta numa tabela estatica de PCI ID no `amdgpu`:

```c
{ PCI_DEVICE(0x1002, 0x73FF), .driver_data = CHIP_DIMGREY_CAVEFISH },
```

As RDNA 3 nao estao. Elas casam por classe e sao resolvidas por
**IP discovery** — uma tabela lida da propria GPU em tempo de boot:

```c
{ PCI_DEVICE(0x1002, PCI_ANY_ID),
  .class = PCI_CLASS_DISPLAY_VGA << 8,
  .driver_data = CHIP_IP_DISCOVERY },
```

Os drivers da Apple sao construidos sobre tabelas estaticas de device ID nos
`Info.plist`. Nao ha parser de IP discovery na pilha do macOS **[a verificar
com o dump de fase 2]**.

---

## 3. Conclusao tecnica

O delta nao e de compatibilidade — e de arquitetura, e ele aparece em **todas**
as camadas simultaneamente:

| Camada | Situacao |
|---|---|
| Enumeracao PCI | tabela estatica vs IP discovery |
| Bring-up | IMU nova, PSP/TOC diferentes |
| Command Processor | F32 -> RS64, CE removido |
| Submissao de trabalho | MES novo (2k linhas) |
| DMA | SDMA v5.2 -> v6.0 |
| Display | DCN 3.0.2 -> DCN 3.2.1 |
| ISA / compilador | 36% das features divergem, encodings novos e removidos |
| Firmware | nenhum blob `gc_11_*` existe no macOS |

Um device-ID spoof (WhateverGreen) resolve **zero** dessas camadas: ele muda o
que o driver *pensa* que a placa e, sem mudar nada do que a placa *e*. O
resultado esperado e panic no bring-up ou tela preta.

O caminho tecnico restante e escrever driver novo em todas as camadas acima,
incluindo um back-end de compilador gfx11 para o Metal — trabalho que a
comunidade Hackintosh nunca conseguiu completar nem para casos muito mais
simples que este.

## 4. Onde ainda ha o que medir (fase 2)

O que este documento **nao** pode responder de dentro de um container Linux, e
que depende de rodar `tools/dump_macos_amd_stack.sh` no seu Mac/Hackintosh:

1. Quais ASICs o `AMDRadeonX6000HWLibs` realmente conhece (strings/tabelas).
2. Se ha algum resto de gfx11 na pilha da Apple (esperado: nenhum).
3. Como o `AMDRadeonX6000` particiona controller / accelerator / HWLibs, para
   saber quais fronteiras um driver novo teria que respeitar.
4. Se existe qualquer caminho de enumeracao dinamica alem do `IOPCIMatch`.

Os itens 1 e 2 sao os que decidem se sobra alguma brecha. Rode o script e
traga o relatorio.
