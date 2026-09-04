# navi33-macos

Analise tecnica do que seria necessario para dar suporte a **AMD Radeon RX 7600
(Navi 33 / RDNA 3 / gfx1102)** no macOS, partindo do driver que ja funciona
para a **RX 6600 (Navi 23 / RDNA 2 / gfx1032)**.

## Estado

**Fase 1 (concluida): levantamento do delta.**
`docs/01-delta-navi23-navi33.md` mede, com dados reproduziveis, a distancia
entre as duas GPUs em cada camada — enumeracao PCI, bring-up, command
processor, escalonamento, DMA, display e ISA.

Resultado resumido: a divergencia e arquitetural e simultanea em todas as
camadas. Um device-ID spoof nao resolve nenhuma delas. Os detalhes, com os
numeros, estao no documento.

**Fase 2 (parcial): mapeamento da pilha do macOS.**
`docs/02-pilha-macos.md` mapeia como o macOS divide o driver AMD e mede,
pelo codigo do NootRX (que habilita RDNA 2 nao suportada), qual e a superficie
real que um kext de terceiro alcanca: **28 pontos de contato**, quase todos
tabelas de ASIC, mais firmware embarcado. Depois mostra, ponto a ponto, por
que nenhum deles se traduz para Navi 33.

**Fase 2 (pendente, precisa de um Mac):** rodar `tools/dump_macos_amd_stack.sh`
para fechar a ultima duvida — se existe qualquer vestigio de gfx11 / DCN 3.2 /
SMU 13 na pilha instalada.

## Reproduzir a analise

```bash
./tools/fetch_sources.sh sources     # baixa amdgpu (Linux) + AMDGPU.td (LLVM)
python3 tools/isa_delta.py --td sources/AMDGPU.td
./tools/ip_refs.sh sources           # MES / IMU / RS64 / CE: gfx10 vs gfx11
```

Sem argumentos, `isa_delta.py` baixa o `AMDGPU.td` sozinho. Da para comparar
qualquer par de ISAs:

```bash
python3 tools/isa_delta.py --a 10_3_0 --b 11_0_2   # Navi 23 vs Navi 33 (padrao)
python3 tools/isa_delta.py --a 10_1_0 --b 10_3_0   # RDNA 1 vs RDNA 2 (referencia)
```

## Fase 2: rodar no Mac

```bash
./tools/dump_macos_amd_stack.sh > relatorio-$(sw_vers -productVersion).txt
```

Somente leitura: nao copia binarios da Apple e nao altera nada no sistema.

## Estrutura

```
docs/01-delta-navi23-navi33.md   delta de hardware Navi 23 vs Navi 33
docs/02-pilha-macos.md           pilha AMD do macOS e alcance de um kext
tools/fetch_sources.sh           baixa as fontes publicas de referencia
tools/isa_delta.py               diff de feature set de ISA (LLVM AMDGPU.td)
tools/ip_refs.sh                 contagem de referencias a blocos de IP
tools/dump_macos_amd_stack.sh    inventario da pilha AMD do macOS (fase 2)
data/isa_features.json           saida capturada do diff gfx1032 vs gfx1102
```

## Fontes

- `amdgpu` do kernel Linux (GPL-2.0) — `torvalds/linux`,
  `drivers/gpu/drm/amd/`
- Back-end AMDGPU do LLVM (Apache-2.0 with LLVM exceptions) — `llvm/llvm-project`
- NootRX (ChefKissInc) e WhateverGreen (Acidanthera) — consultados como
  referencia de como a pilha do macOS e modificada na pratica. Nenhum codigo
  deles foi copiado para este repositorio.

Este repositorio contem apenas analise propria e ferramentas que consultam
essas fontes publicas. Nao inclui nem redistribui codigo, firmware ou binarios
da Apple ou da AMD.
