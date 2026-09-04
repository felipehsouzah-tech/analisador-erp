# A pilha grafica AMD do macOS e o que um kext de terceiro consegue alcancar

**Metodo.** Esta fase mapeia a pilha da Apple a partir de projetos publicos que
ja a modificam com sucesso — principalmente o **NootRX** (ChefKiss), que
habilita GPUs RDNA 2 dedicadas que a Apple nao suporta de fabrica. Ele e o
melhor caso de referencia possivel: faz exatamente o tipo de coisa que voce
quer fazer, so que **dentro** da mesma arquitetura.

Nenhum binario da Apple foi inspecionado aqui (nao ha macOS neste ambiente).
O que se mede sao os **pontos de contato** que o NootRX declara — nomes de
simbolo, kexts alvo e firmware embarcado —, e isso ja e suficiente para
delimitar a fronteira.

---

## 1. Como a pilha e dividida

| Kext | Papel |
|---|---|
| `AMDRadeonX6000Framebuffer.kext` | display / framebuffer (DCN), DMCUB |
| `AMDRadeonX6000HWServices.kext` | despacho por familia; carrega o HWLibs certo |
| `└ PlugIns/AMDRadeonX6800HWLibs.kext` | abstracao de hardware: tabelas de ASIC, PSP, SMU, firmware |
| `└ PlugIns/AMDRadeonX6810HWLibs.kext` | idem, outra familia |
| `AMDRadeonX6000.kext` | acelerador (caminho Metal) |
| `AppleGraphicsControl.kext/PlugIns/AppleGraphicsDevicePolicy` | politica de GPU (AGDP) |

O HWLibs e a peca central: e onde vivem as tabelas que dizem *quais ASICs
existem* e *qual firmware carregar para cada um*.

## 2. O que o NootRX efetivamente toca

Superficie total de modificacao, contada no codigo-fonte:

| Arquivo | Rotas | Solves | Patches binarios |
|---|---|---|---|
| `HWLibs.cpp` | 5 | 3 | 11 |
| `X6000FB.cpp` (framebuffer) | 3 | 1 | 2 |
| `X6000.cpp` (acelerador) | 1 | 0 | 1 |
| `DYLDPatches.cpp` (userspace) | 1 | 0 | 0 |
| **Total** | **10** | **4** | **14** |

**28 pontos de contato** para habilitar uma GPU inteira. Os simbolos
interceptados dizem por que e tao pouco:

```
_CAILAsicCapsInitTable                  tabela de capacidades por ASIC
__ZL20CAIL_ASIC_CAPS_TABLE              idem (estatica)
_DeviceCapabilityTbl                    capacidades de dispositivo
__ZL15deviceTypeTable                   mapeamento device ID -> tipo
_psp_cmd_km_submit                      ponto de injecao de firmware via PSP
_smu_11_0_7_send_message_with_parameter gerenciamento de energia (SMU 11.0.7)
__ZN38AMDRadeonX6000_AMDRadeonHWServicesNavi16getMatchPropertyEv
```

Note o padrao: **sao quase todos tabelas**. O NootRX nao escreve driver — ele
adiciona linhas em tabelas de um driver que ja existe, e injeta o firmware que
a Apple nao distribui. O codigo que sabe falar com gfx10.3 ja esta no binario
da Apple; o NootRX so faz o hardware ser reconhecido por ele.

## 3. O firmware que o NootRX precisa embarcar

Ele carrega ~80 blobs proprios, porque a Apple so distribui os das ASICs que
ela mesma suporta:

```
gc_10_3_*, gc_10_3_2_*, gc_10_3_4_*    ce, me, mec, mec_jt, pfp, rlc,
                                        rlcp, rlc_lx6, srlist, tap_delays
sdma_5_2_ucode.bin, sdma_5_2_2, sdma_5_2_4
mes_10_3_mes0_ucode.bin / _data.bin
psp_sos_navi2x, psp_sys_drv_navi2x, psp_key_database_navi2x, psp_tos_spl_navi2x
navi2x_smc_firmware.bin
atidmcub_instruction_dcn30.bin, atidmcub_instruction_dcn302.bin
ativvaxy_vcn3.dat
```

Observe `gc_10_3_*_ce_ucode.bin`: o Constant Engine, que **nao existe no
RDNA 3**. E `mes_10_3_mes0_ucode.bin`: ha firmware de MES para RDNA 2, mas o
caminho grafico do RDNA 2 nao depende dele — no RDNA 3 o MES e central, a
ponto de o SDMA v6 rotear suas filas de usuario por ele
(`sdma_v6_0.c` faz `#include "mes_userqueue.h"`).

## 4. A fronteira, ponto a ponto

Aplicando a mesma receita do NootRX a uma RX 7600:

| Ponto de contato do NootRX | Vale para Navi 33? |
|---|---|
| Match por `(deviceID & 0xFF00) == 0x7300` | **Nao.** RX 7600 e `0x7480`. O proprio NootRX faz `PANIC` em ID desconhecido. |
| Adicionar entrada em `CAIL_ASIC_CAPS_TABLE` | Possivel escrever a entrada, mas ela aponta para **codigo de gfx11 que nao existe** no binario. |
| Injetar firmware via `_psp_cmd_km_submit` | Nao ha blob `gc_11_*` em lugar nenhum da pilha, e a sequencia de boot do RDNA 3 (IMU + TOC) e outra. |
| `_smu_11_0_7_send_message_with_parameter` | **Simbolo inexistente para o alvo.** Navi 2x usa SMU 11.0.7; Navi 33 usa SMU 13.0.x. Nao ha o que interceptar. |
| `atidmcub_instruction_dcn30/302` | Navi 33 e **DCN 3.2.1**. Nao ha DMCUB nem codigo de DCN 3.2 na pilha. |
| Patch do acelerador X6000 | O back-end de shader emite gfx10.3. Nao existe back-end gfx11 para redirecionar. |

**Resumo:** dos 28 pontos de contato, nenhum se traduz. Nao porque estejam
"faltando alguns bits", mas porque cada um deles e um ponteiro para codigo
gfx10.3 — e o alvo equivalente para gfx11 nao foi escrito por ninguem.

## 5. O que isso significa para o escopo do projeto

O NootRX prova que o caminho "habilitar ASIC nao suportada" e viavel **quando
o driver da arquitetura ja existe**: 28 pontos de contato, firmware embarcado,
e funciona.

Para o Navi 33 o trabalho nao e habilitar — e escrever, do zero, dentro de
binarios fechados da Apple:

1. Reconhecimento e enumeracao da familia `0x74xx` (incluindo IP discovery).
2. Bring-up: IMU, PSP/TOC no formato RDNA 3.
3. Command processor RS64 (carga de microcodigo, cache de instrucao) —
   **145** referencias a `rs64` no driver de referencia, zero equivalente na
   pilha da Apple.
4. MES como escalonador de filas (**2.092** linhas no driver de referencia),
   incluindo as filas de usuario do SDMA v6, que passam por ele.
5. SDMA v6.
6. DCN 3.2.1 completo, com DMCUB proprio, so para haver imagem na tela.
7. SMU 13.0.x para energia e clocks.
8. Back-end de compilador gfx11 para o Metal (ver `01-delta`: SDWA removido,
   VOPD e True16 novos, 36% das features divergem).

Os itens 1-7 sao driver de kernel. O item 8 e um back-end de compilador, e
sozinho ja e maior que o NootRX inteiro.

## 6. O que ainda depende do seu Mac

O mapa acima e inferido de fonte publica. O `tools/dump_macos_amd_stack.sh`
fecha a ultima duvida real: **existe algum vestigio de gfx11 / DCN 3.2 /
SMU 13 na pilha instalada?** Se a resposta for "nenhum" (esperado), o item 5
da secao 3 do `01-delta` esta confirmado e a analise se encerra. Se aparecer
qualquer simbolo `gfx11`, `dcn32` ou `smu_13`, ai muda a conversa e vale
investigar.

---

## 7. Qual macOS instalar, e o prazo do projeto

Dois fatos com impacto direto no escopo:

**macOS Tahoe 26 e a ultima versao que suporta Intel.** A partir do macOS 27 o
suporte a Intel acaba. Isso da ao projeto um prazo de validade: mesmo um driver
hipoteticamente pronto teria como alvo um sistema em fim de vida, sem mais
atualizacoes de seguranca a partir do fim do ciclo do Tahoe.

**Nenhuma versao do macOS tem suporte a RDNA 3.** As RX 6000 (RDNA 2) sao
suportadas no Tahoe; as RX 7000 nao, em nenhuma versao. Trocar de versao de
macOS nao altera nada da analise das secoes 1-6.

### O bloqueio pratico para a fase 2

Ha um problema de ordem antes do problema tecnico: **para rodar o inventario e
preciso conseguir video.** Com apenas uma RX 7600 na maquina nao ha driver de
framebuffer, entao nao ha desktop para abrir o Terminal.

Saidas, em ordem de preferencia:

1. **iGPU do processador.** Se o CPU tiver grafico integrado habilitado, ele da
   o video e o sistema instala normalmente. E o caminho mais simples.
2. **Terminal do Recovery.** O Recovery usa um caminho de video basico e
   costuma funcionar sem driver acelerado. Monte o volume do sistema
   (`diskutil list` para achar) e rode:
   ```
   ./dump_macos_amd_stack.sh --root "/Volumes/Macintosh HD" > relatorio.txt
   ```
   O script foi escrito para funcionar nesse modo, sem macOS bootado.
3. **Uma GPU suportada emprestada** so para instalar e inventariar.

O modo `--root` tambem serve para inventariar de um segundo Mac, ou de um
volume montado por outro sistema.

### Sobre a versao especifica

Para o inventario, a versao exata do Tahoe (26.5, 26.6.x) e indiferente: o
particionamento da pilha AMD nao muda entre releases de ponto. Se o objetivo
for tambem ter um sistema estavel para trabalhar, uma release de ponto anterior
a mais recente tende a ter mais relatos de compatibilidade acumulados na
comunidade OpenCore.
