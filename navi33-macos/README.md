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

**Fase 2 (pendente, so falta rodar):** `docs/03-inventario-sem-mac.md` resolve
o bloqueio pratico. Com Ryzen 3600X (sem iGPU) e apenas uma RX 7600, o macOS
nao chega ao desktop — nao ha driver de framebuffer. Entao o inventario nao
passa por bootar o macOS: `tools/scan_amd_stack.py` roda no Linux, em Python
puro, contra a imagem do instalador montada. Falta so executar.

**Plano de adaptacao:** `docs/04-plano-de-adaptacao.md` descreve como a
adaptacao ocorreria — a cadeia que o macOS percorre para acender a tela, o que
a RX 7600 tem por dentro, o que precisaria ser adaptado em cada elo, e o plano
em 6 fases com criterio de sucesso e de parada por fase.

**Estado da arte:** `docs/05-estado-da-arte.md` levanta quem ja tentou. O
mantenedor do NootRX confirma de forma independente que RDNA 3 exigiria
reimplementar o HWLibs; e a Apple nunca entregou driver nem para as Radeon Pro
W7800/W7900, sucessoras diretas das W6800 que ela mesma suportava.

**Viabilidade com LLM:** `docs/06-o-que-muda-com-llm.md` avalia quanto do plano
muda quando o trabalho e feito com modelos atuais. Resumo: o argumento de
volume de codigo perdeu forca; o de informacao nao publicada e ciclo de teste
em hardware, nao.

**Ambiente em VM:** `docs/07-ambiente-em-vm.md` — macOS em VM resolve o
inventario e o ambiente de build de imediato; e num host Linux com VFIO a VM
fica *melhor* que bare metal para a fase 0, porque a GPU virtual faz o papel da
segunda placa ausente.

**O deliverable:** `docs/08-o-que-e-o-driver.md` define o que o projeto
realmente e — um driver, nao um kext de patch — e estreita o alvo para
**driver so de display** (fases 0-4), que ja entrega desktop utilizavel. Metal
(fase 5) vira projeto separado.

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
# Linux, contra a imagem do instalador montada (nao precisa de Mac):
python3 tools/scan_amd_stack.py --root /mnt/macos/<volume> --out relatorio.txt

# ou, se houver um macOS acessivel:
python3 tools/scan_amd_stack.py --root / --out relatorio.txt
```

Passo a passo da montagem em `docs/03-inventario-sem-mac.md`.
Somente leitura: nao copia binarios da Apple e nao altera nada no sistema.

## Estrutura

```
docs/01-delta-navi23-navi33.md   delta de hardware Navi 23 vs Navi 33
docs/02-pilha-macos.md           pilha AMD do macOS e alcance de um kext
docs/03-inventario-sem-mac.md    como inventariar a partir do Linux
docs/04-plano-de-adaptacao.md    arquitetura e plano de implementacao
docs/05-estado-da-arte.md        trabalho anterior e o que ele corrigiu aqui
docs/06-o-que-muda-com-llm.md    o que muda no plano com LLM no circuito
docs/07-ambiente-em-vm.md        o que da para fazer em VM, e o que nao da
docs/08-o-que-e-o-driver.md      definicao do deliverable e do alvo minimo
tools/fetch_sources.sh           baixa as fontes publicas de referencia
tools/isa_delta.py               diff de feature set de ISA (LLVM AMDGPU.td)
tools/ip_refs.sh                 contagem de referencias a blocos de IP
tools/scan_amd_stack.py          inventario da pilha AMD (Linux/macOS, fase 2)
tools/dump_macos_amd_stack.sh    variante em shell, para macOS bootado
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
