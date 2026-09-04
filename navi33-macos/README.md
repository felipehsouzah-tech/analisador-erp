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

**Fase 2 (pendente, precisa de um Mac):** inventariar a pilha grafica AMD do
macOS instalado para fechar as quatro perguntas em aberto listadas no final do
documento — principalmente se existe qualquer vestigio de suporte gfx11 na
pilha da Apple.

## Reproduzir a analise

```bash
./tools/fetch_sources.sh sources     # baixa amdgpu (Linux) + AMDGPU.td (LLVM)
python3 tools/isa_delta.py --td sources/AMDGPU.td
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
docs/01-delta-navi23-navi33.md   analise principal, com os dados
tools/fetch_sources.sh           baixa as fontes publicas de referencia
tools/isa_delta.py               diff de feature set de ISA (LLVM AMDGPU.td)
tools/dump_macos_amd_stack.sh    inventario da pilha AMD do macOS (fase 2)
data/isa_features.json           saida capturada do diff gfx1032 vs gfx1102
```

## Fontes

- `amdgpu` do kernel Linux (GPL-2.0) — `torvalds/linux`,
  `drivers/gpu/drm/amd/`
- Back-end AMDGPU do LLVM (Apache-2.0 with LLVM exceptions) — `llvm/llvm-project`

Este repositorio contem apenas analise propria e ferramentas que consultam
essas fontes publicas. Nao inclui nem redistribui codigo, firmware ou binarios
da Apple ou da AMD.
