# Ambiente de trabalho em VM

Hardware disponivel: **Ryzen 5 3600X + RX 7600 (unica GPU) + Windows 11**.

Este documento responde o que da para fazer em maquina virtual, e corrige o
desenho da fase 0 do `04-plano-de-adaptacao.md`: uma VM nao e um paliativo
aqui — para este hardware ela e **melhor** que bare metal.

---

## 1. O que a VM resolve de imediato

macOS rodando em VM usa **GPU virtual** (SVGA da VMware). Nao ha driver AMD
envolvido, entao **ha imagem na tela**. Isso derruba de uma vez o bloqueio que
os documentos 02 e 03 tentavam contornar.

| Tarefa | Bare metal (3600X + RX 7600) | VM no Windows 11 |
|---|---|---|
| Bootar macOS ate o desktop | **nao** (sem framebuffer) | **sim** |
| Rodar o inventario da fase 2 | so por imagem montada | **direto, no sistema** |
| Xcode, compilar kext | nao | **sim** |
| `ioreg`, `kextstat`, disassembly ao vivo | nao | **sim** |
| Ver a RX 7600 real no barramento | sim | **nao** |

Ou seja: **o caminho do `03-inventario-sem-mac.md` deixa de ser necessario.**
Montar imagem de instalador no Linux continua valendo como alternativa, mas e
o caminho mais dificil. Com a VM, e so rodar:

```
python3 tools/scan_amd_stack.py --root / --out relatorio.txt
```

### Viabilidade no seu hardware
macOS em Ryzen sob VMware Workstation e caminho conhecido e mantido: precisa do
**unlocker** (VMware nao oferece macOS como convidado por padrao), do OpenCore
e do conjunto de **AMD kernel patches** do projeto `AMD_Vanilla` — hoje 25
patches, aplicaveis a familia 17h do 3600X, com o quirk
`ProvideCurrentCpuInfo`. A comunidade AMD OS X mantem uma thread ativa que
reporta funcionamento ate **Tahoe**. AMD-V precisa estar habilitado na BIOS.

## 2. O que a VM no Windows **nao** resolve

Para tentar a fase 2 do plano (a GPU sai do reset? os registradores
respondem?) o kext precisa enxergar a **RX 7600 fisica**. Isso exige
*passthrough* de PCIe, e no Windows 11 isso nao existe de forma pratica:

- **Hyper-V DDA**: a Microsoft declara suporte apenas em Windows **Server**;
  em Windows 11 cliente a tentativa falha com
  `HV_STATUS_ACCESS_DENIED (0xC035001E)`. Ha contorno de comunidade, mas
  macOS como convidado do Hyper-V nao e caminho viavel de qualquer forma.
- **VMware Workstation / VirtualBox**: nao fazem passthrough de GPU.

## 3. O achado: com VFIO, a VM e melhor que bare metal

Isto corrige o `04-plano-de-adaptacao.md`, que desenhou a fase 0 assumindo
bare metal e tratou "nao ter segunda GPU" como limitacao insuperavel.

Num host **Linux com KVM/VFIO** (Proxmox, por exemplo), a VM pode ter as duas
coisas ao mesmo tempo:

- uma **GPU virtual**, que da o console do macOS — fazendo o papel da segunda
  placa que voce nao tem;
- a **RX 7600 real**, passada por VFIO, presente no barramento PCI do
  convidado para o kext se ligar a ela.

Isso resolve o problema estrutural da fase 0. E melhora o ciclo de iteracao,
que o `06-o-que-muda-com-llm.md` identificou como **o recurso escasso do
projeto**:

| | Bare metal | VM com VFIO |
|---|---|---|
| Console durante o bring-up | nenhum | GPU virtual |
| Reboot apos panic | minuto(s), POST completo | segundos |
| Voltar a um estado bom | reinstalar | **snapshot** |
| Ler o panic | so KDP por rede | console + KDP |
| Inspecionar estado do device | nao | do lado do host, via `lspci`/sysfs |

Um panic deixa de custar um ciclo de POST e passa a custar segundos, com
snapshot para voltar. Para um trabalho que e essencialmente
tentativa-e-erro, essa diferenca e grande.

## 4. O custo dessa mudanca

Ela exige trocar o host de Windows para Linux, e traz consequencias concretas:

1. **O host fica sem video.** Passar a unica GPU para a VM significa que o
   Linux perde a saida de tela. Contorna-se rodando o host *headless*,
   administrado por SSH ou pela interface web do Proxmox a partir de outro
   computador — o console do macOS vem por VNC/SPICE da GPU virtual. Nao exige
   segunda placa de video, mas exige **outra maquina para administrar**.
2. **Reset da GPU.** Passthrough de GPU AMD depende do dispositivo reinicializar
   corretamente entre boots do convidado. RDNA 2/3 estao em situacao melhor que
   Vega/Polaris nesse aspecto, mas **isto precisa ser verificado na pratica** com
   a 7600 antes de contar com o ciclo rapido.
3. **Windows vira convidado** (ou dual boot), com o inconveniente de que jogos
   com a 7600 passariam a depender da mesma disputa pela placa.

## 5. Recomendacao pratica, em ordem

**Agora, sem trocar nada:** VMware Workstation no Windows 11, macOS Tahoe com
OpenCore + AMD_Vanilla. Isso ja entrega:

- o inventario da fase 2, do jeito facil;
- o ambiente de build (Xcode, SDK de kext);
- inspecao ao vivo da pilha AMD (`ioreg`, `kextstat`, disassembly);
- a fase 1 do plano — compilar um kext que casa `1002:7480`, ainda que sem
  dispositivo real para casar.

**Depois, se a fase 2 for realmente tentada:** host Linux com VFIO. Nao antes —
nao ha motivo para desmontar o Windows para rodar um inventario.

## 6. O que isso muda no plano

A fase 0 do `04-plano-de-adaptacao.md` dizia: "depuracao de kernel por rede
(KDP), unica via de diagnostico possivel neste hardware". Isso estava correto
para bare metal, mas incompleto: **com VM e VFIO existe console**, e o KDP
passa de unica via a complemento.

O que **nao** muda: a VM nao cria driver. Com a RX 7600 passada por VFIO, o
macOS continua sem saber falar com ela — e exatamente esse o problema que a
fase 2 existe para atacar. A VM melhora o *ciclo de teste*, nao o conteudo do
teste.
