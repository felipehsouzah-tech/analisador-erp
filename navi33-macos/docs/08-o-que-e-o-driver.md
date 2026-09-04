# O que exatamente e o deliverable

Sim: o que este projeto exige e **escrever um driver**, nao um patch de
compatibilidade. Este documento define, com precisao, o que isso significa —
o que seria escrito, o que seria portado, o que nao pode ser tocado, e onde da
para parar e ainda ter algo util.

---

## 1. Por que "driver" e nao "kext de patch"

A distincao ja aparece no `04-plano-de-adaptacao.md` como modelo A vs modelo B,
e e confirmada pelo mantenedor do NootRX (`05-estado-da-arte.md`):

> "RDNA 3 support would need a full reimplementation of the hardware
> abstraction code (HWLibs)."

WhateverGreen e NootRX sao **kexts de patch**: eles interceptam um driver que
existe e corrigem seu comportamento. Isso pressupoe o driver embaixo. Para
gfx11 nao ha driver embaixo — entao o que precisa existir e a coisa em si.

Escala do que isso significa: e um driver no mesmo sentido em que o suporte a
Navi 33 no `amdgpu` do Linux e um driver. A diferenca e o alvo: em vez de um
kernel aberto e documentado, ele precisa se encaixar em ABIs C++ fechadas do
macOS.

## 2. O que seria escrito do zero

Codigo que nao existe em lugar nenhum e nao tem de onde ser copiado:

- **A casca IOKit.** `IOService` proprio, matching por `IOPCIMatch`, ciclo de
  vida (`probe`/`start`/`stop`), mapeamento de BARs, registro de interrupcao,
  publicacao do framebuffer. Isso e forma macOS, nao forma Linux.
- **A ponte com a pilha da Apple.** Decidir onde o driver se insere: publicar
  um `IOFramebuffer` proprio, e como conviver com (ou substituir) o
  `AMDRadeonX6000Framebuffer` para este dispositivo.
- **O encaixe nas ABIs fechadas** — a parte sem documentacao, e a que
  `06-o-que-muda-com-llm.md` identifica como de menor alavancagem.

## 3. O que seria portado, nao inventado

Esta e a parte que torna o projeto menos absurdo do que soa: **a logica do
lado do hardware e aberta.**

| Precisa | Fonte aberta de referencia |
|---|---|
| Sequencia de bring-up da IMU | `imu_v11_0.c` |
| Cadeia PSP 13 | `psp_v13_0.c` |
| SMU 13 (clocks, energia) | `smu_v13_0.c`, `smu_v13_0_7_ppt.c` |
| Carga de microcodigo RS64 | `gfx_v11_0.c` |
| MES (escalonamento de filas) | `mes_v11_0.c` |
| SDMA v6 | `sdma_v6_0.c` |
| DCN 3.2.1 (display) | `dcn32_resource.c`, `dcn321_resource.c`, DC/DAL |
| ISA gfx1102 | back-end AMDGPU do LLVM |
| Definicoes de registrador | headers abertos do `amdgpu` |

Não é engenharia reversa do hardware — a AMD publica isso. É **tradução**: pegar
lógica conhecida e reexprimi-la na forma que o macOS espera. É exatamente o tipo
de trabalho em que um LLM ajuda muito.

O trabalho de engenharia reversa fica concentrado num ponto so: **a fronteira
com o binario da Apple**.

## 4. O que nao pode ser feito

- **Redistribuir binario ou firmware da Apple.** O NootRX embarca firmware da
  AMD, nao da Apple. Mesma regra aqui.
- **Reescrever o compilador Metal.** O pipeline AIR → ISA e fechado. A fase 5
  teria que se encaixar nele, nao substitui-lo.

## 5. O ponto de parada util: driver so de display

Esta e a descoberta que muda o tamanho do alvo, e ela precisa ser dita com o
grau de certeza correto.

**macOS Tahoe roda com renderizacao por software, sem Metal.** A prova e
empirica e esta em uso hoje: macOS em VMware usa o SVGA virtual, que nao tem
aceleracao — Metal e Quartz Extreme ficam desabilitados — e o desktop funciona.
Gente roda Tahoe assim em Ryzen agora.

O que o macOS exige nao e *aceleracao*, e **alguem publicando um framebuffer**.
Em VM, o driver SVGA faz isso. Em bare metal com GPU sem suporte, ninguem faz —
e por isso da tela preta e o WindowServer morre.

Consequencia direta para o plano: as **fases 1 a 4 sozinhas ja entregam um
sistema utilizavel**. Sem Metal, sem jogos, sem aceleracao de video — mas com
desktop, resolucao nativa e multiplos monitores. Equivalente ao que uma VM
entrega hoje, so que em hardware real.

A **fase 5 (back-end gfx11) vira projeto separado**, nao pre-requisito.

> Grau de confianca: alto para "macOS Tahoe funciona sem Metal" — ha uso
> corrente em VM. Menor para "um framebuffer AMD sem aceleracao satisfaz o
> WindowServer da mesma forma que o SVGA da VMware": o caminho de codigo nao e
> o mesmo. **Isso precisa ser confirmado**, e da para confirmar cedo, sem
> escrever driver nenhum: basta observar o comportamento do WindowServer numa
> VM Tahoe sem aceleracao (que voce vai montar de qualquer jeito).

## 6. O deliverable, redefinido

| Alvo | Fases | Entrega | Metal |
|---|---|---|---|
| **Minimo util** | 0–4 | desktop em resolucao nativa na RX 7600 | nao |
| Completo | 0–5 | aceleracao grafica | sim |

O alvo do projeto passa a ser o **minimo util**. Nao porque o completo seja
proibido, mas porque:

- e o primeiro ponto com valor pratico real;
- e o unico cuja viabilidade se decide cedo (fase 2);
- a fase 5, embora seja a maior, e tambem a de maior alavancagem com LLM
  (`06`), entao faz sentido deixa-la por ultimo.

## 7. O que continua valendo

Nada aqui contradiz os documentos 01–07. O que muda e o **escopo declarado**:
o projeto deixa de ser "fazer a RX 7600 funcionar no macOS" e passa a ser
**"escrever um driver de display para Navi 33 no macOS"** — enunciado mais
honesto, mais estreito, e verificavel.

O gate continua sendo a fase 2: os registradores respondem? Se sim, o resto e
volume de trabalho de traducao. Se nao, nada acima importa.
