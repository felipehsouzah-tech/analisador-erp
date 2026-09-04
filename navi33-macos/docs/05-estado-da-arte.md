# Estado da arte: quem ja tentou, e onde parou

Levantamento do trabalho anterior sobre RDNA 3 no macOS. Esta fase deveria ter
vindo **antes** da analise propria: os becos sem saida de quem ja tentou valem
mais que deducao a partir de fonte primaria. Feita fora de ordem, serve agora
como verificacao independente — e trouxe uma correcao real a ferramenta.

**Limitacao de acesso:** `dortania.github.io`, `chefkiss.dev`, `techradar.com`
e `iatkos.uk` estao bloqueados pelo proxy deste ambiente. O conteudo desses
foi obtido indiretamente, por resultado de busca, e esta marcado como tal.

---

## 1. A confirmacao mais forte: o autor do NootRX

Em `ChefKissInc/NootRX`, discussao #97 ("Will this work with RDNA3?"), o
mantenedor **VisualEhrmanntraut** responde:

> "RDNA 3 support would need a full reimplementation of the hardware
> abstraction code (HWLibs)."

Isto e independente da nossa analise e chega a mesma conclusao: nao e patch de
tabela, e reimplementacao. E exatamente a distincao entre **modelo A** e
**modelo B** do `04-plano-de-adaptacao.md`, dita por quem escreveu o kext de
RDNA 2.

A issue #129 do mesmo projeto pede suporte a "Navi 40+" (RX 9060 XT). Esta
aberta, sem resposta de mantenedor.

## 2. A evidencia decisiva: a Radeon Pro W7000

Este e o dado que eu tinha deixado passar e que mais pesa.

A **Radeon Pro W7800 / W7900** sao RDNA 3, profissionais, e sucessoras diretas
da W6800 — que a Apple **suportou** e vendeu como modulo MPX para o Mac Pro
2019. Placas perfeitas para o Mac Pro 7,1.

A Apple nunca lancou driver para elas.

O contraste de cronograma e o que torna o dado forte:

| Geracao | Anuncio AMD | Driver macOS |
|---|---|---|
| W6000 (RDNA 2) | jun/2021 | **abr/2021, no macOS 11.4** — antes do anuncio |
| W7000 (RDNA 3) | abr/2023 | nunca |

Ou seja: nao e o caso de "ninguem se interessou por placa de consumidor". A
Apple, com cooperacao da AMD e incentivo comercial direto (vender modulos MPX),
**nao entregou** driver de RDNA 3. Se o caminho fosse barato, a parte
interessada com acesso ao codigo-fonte teria feito.

A leitura da comunidade (MacRumors, discussao sobre o 7,1) e que a Apple
possivelmente planejou suporte a RDNA 3 e abandonou ao acelerar a transicao
para Apple Silicon; e que o driver das 6000 so veio porque a Apple lancou os
proprios modulos MPX.

## 3. A nuance que corrigiu nossa ferramenta

Em 2020, numa beta do macOS Big Sur, o vazador *Rogame* (HardwareLeaks)
encontrou no arquivo **`AmdRadeonX6000HwServices`** referencias a **Navi 31**,
com 80 CUs e 5120 shaders, ao lado das entradas de Navi 21 (80 CUs), Navi 22
(40) e Navi 23 (32).

Isso **nao** virou driver: seis anos depois, RDNA 3 continua sem suporte. Mas
tem consequencia pratica direta para a fase 2 deste projeto.

O `scan_amd_stack.py` original procurava `navi3[0-9]` junto com os marcadores
de codigo, e teria reportado esse nome como "vestigio de RDNA 3 — a analise
muda". Seria um **falso positivo**, e do tipo pior: o que faz abandonar uma
conclusao correta.

A ferramenta foi dividida em dois niveis:

- **Nivel 1 — implementacao:** `gfx11xx`, `gc_11_x_x`, `dcn32/321`, `smu_13`,
  `mes_11`, `rs64`. So aparecem se houver codigo real. Se algum aparecer, a
  premissa do plano cai.
- **Nivel 2 — apenas o nome:** `navi3x`. Nome em tabela nao e implementacao.
  Se o nivel 2 acusar e o nivel 1 nao, e o caso do Big Sur se repetindo, e a
  conclusao do plano **nao** muda.

Testado nos dois cenarios contra a arvore sintetica.

## 4. Nenhum projeto conhecido

Nao ha, ate onde a busca alcanca, nenhum projeto publico tentando driver de
Navi 3x para macOS. Os projetos ativos da area tem escopo declarado anterior:

| Projeto | Escopo |
|---|---|
| NootRX | RDNA 2 dedicada (Navi 21/22/23) |
| NootedRed | APUs Vega |
| WhateverGreen | patches de compatibilidade sobre drivers existentes |

O consenso das fontes secundarias (guias de compra, foruns) e uniforme: Navi 3x
nao e utilizavel em Hackintosh, e a expectativa de suporte futuro e nula,
porque a Apple encerrou o Intel e o Apple Silicon nao aceita GPU de terceiro.

## 5. O que isso muda no plano

**Estruturalmente, nada.** Nenhuma fonte encontrada contradiz o
`04-plano-de-adaptacao.md`; a fala do mantenedor do NootRX o confirma de forma
independente, e o caso da W7000 reforca.

**Muda em tres pontos:**

1. A ferramenta da fase 2 ganhou dois niveis, para nao confundir nome com
   implementacao (secao 3).
2. Existe agora uma hipotese concreta a testar no inventario: *a string
   `Navi31` do Big Sur sobreviveu ate o Tahoe?* O scanner responde.
3. O risco "Apple nunca fez, logo talvez seja mais dificil do que parece"
   deixou de ser suposicao e virou dado: a parte com codigo-fonte, contrato
   com a AMD e incentivo comercial olhou para esse trabalho e nao o fez.

## 6. Fontes

- [NootRX discussao #97](https://github.com/ChefKissInc/NootRX/discussions/97) — fala do mantenedor
- [NootRX issue #129](https://github.com/ChefKissInc/NootRX/issues/129) — pedido de Navi 40+
- [NootRX](https://github.com/ChefKissInc/NootRX) — codigo, lido diretamente no doc 02
- [MacGeneration — W7800/W7900 incompativeis](https://www.macg.co/materiel/2023/04/des-cartes-amd-radeon-pro-parfaites-pour-le-mac-pro-et-incompatibles-pour-le-moment-136129)
- [MacRumors — RDNA 3 no Mac Pro 7,1](https://forums.macrumors.com/threads/7000-series-rdna-3-support-on-macos-for-7-1.2351610/)
- [HotHardware — Navi 31 no codigo do Big Sur](https://hothardware.com/news/amd-radeon-navi-31-rdna-3-gpu-macos-big-sur-code)
- [TechSpot — RX 6000 no codigo do Big Sur](https://www.techspot.com/news/86897-amd-radeon-rx-6000-gpus-revealed-macos-big.html)
- Dortania GPU Buyers Guide e chefkiss.dev: bloqueados pelo proxy, citados
  indiretamente por resultado de busca.
