# Plano de adaptacao: RX 7600 (Navi 33) no macOS

Documento de arquitetura. Descreve **como** uma adaptacao dessas funciona, **o
que o macOS precisa** para acender a tela, **o que a RX 7600 e** por dentro, e
**o que teria que ser adaptado** — com o plano de implementacao em fases.

Todos os numeros vem das medicoes dos documentos 01 e 02, reproduziveis com as
ferramentas do repositorio.

---

## 1. A ideia: como uma adaptacao de GPU no macOS funciona

Existem dois modelos, e a diferenca entre eles decide o tamanho do projeto.

### Modelo A — habilitar (o que o NootRX faz)

O driver da arquitetura **ja existe** no binario da Apple. A GPU nao e
reconhecida apenas porque nao esta nas tabelas. Entao voce:

1. intercepta o matching e injeta o dispositivo;
2. adiciona entradas nas tabelas de ASIC (`CAIL_ASIC_CAPS_TABLE`,
   `DeviceCapabilityTbl`, `deviceTypeTable`);
3. injeta o firmware que a Apple nao distribui, pelo `_psp_cmd_km_submit`;
4. corrige alguns retornos com patches binarios pontuais.

Custo real, medido: **1.214 linhas** de kext e 28 pontos de contato. O trabalho
pesado ja estava escrito — voce so apontou o hardware para ele.

### Modelo B — implementar (o que a RX 7600 exige)

Nao ha driver da arquitetura. As tabelas nao apontam para lugar nenhum, porque
o codigo que saberia falar com gfx11 nao existe em canto algum do macOS. Aqui
o kext deixa de ser um *patch* e vira um **driver paralelo**: ele nao adiciona
linhas ao driver da Apple, ele precisa *substituir* a pilha para esse
dispositivo — publicar as proprias classes IOKit, fazer o proprio bring-up,
programar o proprio display.

Esta e a diferenca central do projeto, e ela nao e de grau. **Nao existe um
caminho "NootRX para RDNA 3"**: o mecanismo do NootRX pressupoe um driver
embaixo.

---

## 2. O que o macOS precisa para ter video

A cadeia, na ordem em que acontece no boot. Cada elo depende do anterior —
se um falhar, a tela fica preta e os posteriores nem executam.

### 2.1 Matching e enumeracao
`IOPCIMatch` no `Info.plist` casa `vendor-id 0x1002` + `device-id` com um
`IOPCIDevice`. A Apple usa **tabela estatica**: a GPU precisa estar listada.

### 2.2 Identificacao do ASIC
A Apple tem uma **classe C++ por ASIC**. Confirmado pelo simbolo que o NootRX
intercepta:

```
__ZNK32AMDRadeonX6000_AmdAsicInfoNavi2327getEnumeratedRevisionNumberEv
      → AMDRadeonX6000_AmdAsicInfoNavi23::getEnumeratedRevisionNumber() const
```

Existe `AmdAsicInfoNavi23`. Nao existe `AmdAsicInfoNavi33`. Essa classe
informa revisao, capacidades e qual caminho de HW seguir.

### 2.3 Selecao do HWLibs
`AMDRadeonX6000HWServices` decide qual plugin de HWLibs carregar
(`AMDRadeonX6800HWLibs`, `AMDRadeonX6810HWLibs`). O HWLibs concentra tabelas de
ASIC, PSP, SMU e firmware.

### 2.4 Bring-up de energia e seguranca (PSP)
O PSP autentica e carrega a cadeia de firmware: `sos`, `sys_drv`, `tos_spl`,
`key_database`. Sem isso a GPU nao aceita microcodigo. No RDNA 3 essa
sequencia inclui a **IMU** e um **TOC**, que nao existem no RDNA 2.

### 2.5 Clocks e energia (SMU)
O SMU liga dominios de clock e voltagem. No Navi 2x o simbolo e
`_smu_11_0_7_send_message_with_parameter`. **A versao do SMU faz parte do nome
da funcao** — e um caminho de codigo por versao, nao um parametro.

### 2.6 DisplayCore (DAL/DC)
A Apple embarca a pilha de display da AMD. Confirmado por
`__ZN14AmdDalDmLogger19LogEnableMaskMinorsE` e `_dm_logger_write`. E o DC que:

- le o **AtomBIOS** da placa para descobrir conectores e limites;
- instancia os recursos do DCN: timing generators, OPP, planes, DSC,
  stream encoders, link encoders;
- carrega o **DMCUB** (microcontrolador de display) — `atidmcub_instruction_dcn30.bin`,
  `dcn302.bin` no NootRX;
- faz deteccao de hot-plug, le EDID e executa **link training**.

### 2.7 Publicacao do framebuffer
Com o link treinado e o timing programado, o `AMDRadeonX6000Framebuffer`
publica a tela para o WindowServer. **Aqui aparece imagem.**

### 2.8 Aceleracao (depois, e opcional para ter video)
`AMDRadeonX6000` publica o acelerador; o driver Metal em userspace compila
AIR → ISA da GPU. Sem isso ha imagem, mas tudo e software rendering.

> Ponto importante para o planejamento: **video (2.1-2.7) e aceleracao (2.8)
> sao problemas separados.** Da para ter tela sem Metal. O primeiro marco real
> do projeto e a secao 2.7.

---

## 3. O que a RX 7600 tem

### Hardware
| | |
|---|---|
| GPU | Navi 33 XL, 6 nm |
| Arquitetura | RDNA 3 |
| Shader engines | 2 |
| Compute Units | 32 (2.048 stream processors) |
| Ray accelerators | 32 · AI accelerators: 64 |
| ROPs / TMUs | 64 / 128 |
| Memoria | 8 GB GDDR6, 128-bit |
| Interface | PCIe 4.0 **x8** |
| PCI ID | `1002:7480` |

### Blocos de IP
| Bloco | Versao | Observacao |
|---|---|---|
| GC (graphics) | **11.0.2** (`gfx1102`) | CP em RS64, sem Constant Engine |
| Display | **DCN 3.2.1** | HPO DP (DP 2.0/UHBR) |
| SDMA | **6.0.2** | filas de usuario via MES |
| SMU | **13.0.x** | outro caminho de codigo |
| PSP | 13.x | + IMU, + TOC |
| VCN | 4.0.x | video decode/encode |
| MES | v11 | escalonador de filas em hardware |
| Enumeracao | IP discovery | tabela lida da propria GPU |

---

## 4. O que teria que ser adaptado

Elo por elo da secao 2:

| Elo | Navi 23 (existe) | Navi 33 | Veredito |
|---|---|---|---|
| 2.1 matching | tabela estatica `0x73xx` | `0x7480` | **Trivial.** So adicionar o ID. |
| 2.2 AsicInfo | `AmdAsicInfoNavi23` | classe inexistente | **Escrever a classe** e faze-la ser instanciada dentro de um binario fechado. |
| 2.3 HWLibs | X6800/X6810 | nenhum atende gfx11 | **Escrever o equivalente.** |
| 2.4 PSP | cadeia RDNA 2 | + IMU, + TOC, formato novo | **Reescrever a sequencia de bring-up.** Sem IMU a GPU nao sai do reset. |
| 2.5 SMU | `smu_11_0_7_*` | SMU 13.0.x | **Sem simbolo para interceptar.** Codigo novo. |
| 2.6 DC | DCN 3.0.2 | DCN 3.2.1 | **Duas versoes maiores.** Ver abaixo. |
| 2.7 framebuffer | funciona | depende de tudo acima | consequencia |
| 2.8 Metal | back-end gfx10.3 | precisa gfx11 | **Back-end de compilador novo.** |

### O detalhe do display (elo 2.6), medido

Comparando os recursos declarados em `dcn302_resource.c` e `dcn321_resource.c`:

| Recurso | DCN 3.0.2 | DCN 3.2.1 |
|---|---|---|
| timing generators | 5 | 4 |
| OPP | 5 | 4 |
| video planes | 5 | 4 |
| DSC | 5 | 4 |
| HPO DP stream encoders | **0** | 4 |
| HPO DP link encoders | **0** | 2 |

Ocorrencias de `hpo_dp` no codigo: **0** em DCN 3.0.2, **59** em DCN 3.2.1.

Ou seja: nao e so contagem diferente de pipes. O **HPO** (High Performance
Output, o caminho de DisplayPort 2.0 / UHBR) e um bloco de hardware que
**nao existe** no DCN 3.0.2. Nao ha o que reconfigurar — ha o que implementar.

### Firmware

Nenhum blob `gc_11_*`, `sdma_6_*`, `psp_13_*`, `smu_13_*` ou DMCUB de DCN 3.2
existe no macOS. Como o NootRX, seria preciso embarcar todos. Diferente do
NootRX, nao ha codigo do outro lado esperando por eles.

---

## 5. Plano de implementacao

Ordem obrigatoria: cada fase so e testavel se a anterior funcionou.

### Fase 0 — Ambiente de depuracao (pre-requisito absoluto)
Sem isso nao ha projeto: cada tentativa termina em tela preta sem diagnostico,
e nao da para distinguir "o kext nao carregou" de "travou no bring-up da IMU".

- **Entrega:** depuracao de kernel por rede (KDP) via ethernet, com um segundo
  computador rodando o depurador; `boot-args` com `debug=0x144 -v keepsyms=1`.
- **Sucesso:** conseguir parar o kernel do alvo e ler um backtrace remoto.
- **Nota:** no seu hardware (3600X sem iGPU, so a RX 7600) esta e a **unica**
  via de diagnostico possivel.

### Fase 1 — Matching e carga
- **Entrega:** kext que casa `1002:7480`, publica um `IOService` e nao entra em
  panic.
- **Sucesso:** aparece em `ioreg`; sistema continua bootando.
- **Risco:** baixo. E a unica fase barata do projeto.

### Fase 2 — Bring-up: IMU, PSP, SMU 13
- **Entrega:** sequencia de power-up do RDNA 3; carga autenticada da cadeia PSP;
  SMU 13 respondendo.
- **Sucesso:** leitura de registradores retorna valores plausiveis em vez de
  `0xFFFFFFFF`; clocks reportados.
- **Risco:** **alto.** Sem documentacao publica completa do PSP/IMU da Apple.
  Referencia: `imu_v11_0.c` (398 linhas), `psp_v13_0.c` (984),
  `smu_v13_0.c` + `smu_v13_0_7_ppt.c` (5.297).

### Fase 3 — Motores: CP RS64, MES, SDMA 6
- **Entrega:** carga de microcodigo nos cores RS64, inicializacao do MES,
  filas de SDMA v6.
- **Sucesso:** *ring test* passa — a GPU executa um command buffer trivial.
- **Risco:** alto. Referencia: `gfx_v11_0.c` (7.408), `mes_v11_0.c` (2.092),
  `sdma_v6_0.c` (1.881).

### Fase 4 — Display: DCN 3.2.1 (**o marco principal**)
- **Entrega:** parse do AtomBIOS, criacao dos recursos DCN 3.2.1, DMCUB,
  caminho HPO, link training, EDID, publicacao do framebuffer.
- **Sucesso:** **imagem na tela.** A partir daqui o projeto tem valor de uso
  mesmo sem aceleracao.
- **Risco:** alto. Referencia: `dcn32_resource.c` (3.115) + `dcn321_resource.c`
  (2.253), sem contar `hwss` e DML.

### Fase 5 — Aceleracao: back-end gfx11 para Metal
- **Entrega:** compilador AIR → gfx1102, respeitando as 25 features novas e as
  17 ausentes (SDWA removido, VOPD e True16 novos, `ArchitectedFlatScratch`).
- **Sucesso:** Metal reporta o dispositivo e roda um shader trivial.
- **Risco:** o mais alto de todos. Este item sozinho e maior que as fases 1-4.

---

## 6. Esforco, em numeros

Somando apenas os **arquivos de topo** de cada bloco no driver de referencia —
sem headers, sem definicoes de registrador, sem DML, sem `hwss`, e **sem nada**
da fase 5:

| Bloco | Linhas |
|---|---|
| `gfx_v11_0.c` | 7.408 |
| `dcn32_resource.c` | 3.115 |
| `smu_v13_0_7_ppt.c` | 2.915 |
| `smu_v13_0.c` | 2.382 |
| `dcn321_resource.c` | 2.253 |
| `mes_v11_0.c` | 2.092 |
| `sdma_v6_0.c` | 1.881 |
| `psp_v13_0.c` | 984 |
| `imu_v11_0.c` | 398 |
| **Piso** | **23.428** |

Comparacao: o **NootRX inteiro tem 1.214 linhas**.

O piso e ~19x o NootRX, e e um piso generoso — o trabalho real e maior, porque
esse codigo de referencia roda em Linux com documentacao de registrador
disponivel, enquanto aqui ele teria que ser reimplementado *contra binarios
fechados da Apple*, encaixando-se em ABIs C++ nao documentadas e sujeitas a
mudar a cada release do macOS.

---

## 7. Riscos e criterios de parada

| Risco | Impacto |
|---|---|
| ABI C++ interna da Apple nao documentada e instavel | qualquer atualizacao do macOS pode quebrar tudo |
| Sem documentacao de registrador do lado Apple | fase 2 pode nao ter solucao por tentativa e erro |
| Tahoe 26 e o ultimo macOS com Intel | o alvo tem prazo de validade |
| Sem segunda GPU | diagnostico so por KDP; ciclo de iteracao lento |

**Criterio de parada honesto:** se a fase 2 nao chegar a "registradores
respondem" em um esforco delimitado, as fases 3-5 nao sao alcancaveis, porque
todas dependem de a GPU sair do reset.

**Primeiro marco que justifica continuar:** fase 4 (imagem na tela). E o unico
ponto do plano em que o projeto passa a ter utilidade pratica.

---

## 8. Proximo passo concreto

Independente da decisao sobre as fases 1-5, o passo imediato nao mudou:
rodar `tools/scan_amd_stack.py` sobre o instalador do Tahoe (ver
`03-inventario-sem-mac.md`) e confirmar que nao ha vestigio de gfx11 na pilha.

Esse resultado e a premissa de todo o documento. Se por algum motivo aparecer
codigo gfx11 na pilha da Apple, o plano inteiro encolhe do Modelo B para o
Modelo A — e ai vale reescrever isto do zero.
