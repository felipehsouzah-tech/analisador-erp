# Chances de exito

Estimativa honesta, por fase, com o raciocinio exposto para que voce possa
discordar de cada numero separadamente.

**Sao julgamentos, nao medicoes.** Nao ha base estatistica: o numero de
projetos comparaveis e proximo de zero. O valor deles esta em tornar o
raciocinio criticavel, nao em precisao.

---

## 1. Antes dos numeros: meu historico nesta analise

Relevante porque afeta o peso que voce deve dar as estimativas. Nesta
conversa eu errei varias vezes, e os erros tem **direcao**:

| Erro | Direcao |
|---|---|
| Contagens de `grep` infladas (MES 37→26, IMU 38→29) | exagerava a diferenca |
| "Fronteira do compilador virgem" — sem evidencia | exagerava o ineditismo |
| "So da para inventariar montando imagem no Linux" | subestimava caminhos |
| "Sem segunda GPU nao ha ciclo de diagnostico" | ignorei VM + VFIO |
| "Precisa de VM para extrair ABI" | precisava so dos arquivos |
| Bugs meus: `lstrip("_")`, geracao sem expandir `FeatureGFX11` | — |

Cinco dos seis erros foram **pessimistas**: eu tratei como impossivel ou caro
algo que tinha caminho mais barato. Isso sugere que as estimativas abaixo, se
enviesadas, provavelmente estao **baixas**. Nao as ajustei por isso — prefiro
registrar o vies a corrigi-lo no escuro.

## 2. Fase a fase

### Fase 0 — ambiente (KDP, VM/VFIO) — **~95%**
Trabalho conhecido e documentado. O unico risco e operacional: passthrough de
GPU unica, com host sem video, e chato de montar. Nao e risco tecnico.

### Fase 1 — matching, kext carrega sem panic — **~90%**
Tecnicamente trivial. Os 10% cobrem atrito de assinatura de kext, SIP e
convivencia com os drivers da Apple.

### Fase 2 — bring-up: IMU, PSP, SMU 13 — **~40-50%**

Este e o portao. E aqui houve uma revisao para cima em relacao ao que este
repositorio vinha assumindo:

**O bring-up nao exige engenharia reversa da Apple.** Ele acontece entre o
nosso codigo e o *hardware*, e o hardware esta documentado em codigo aberto
(`imu_v11_0.c`, `psp_v13_0.c`, `smu_v13_0*.c`). O que a Apple precisa fornecer
sao mecanismos genericos e documentados do IOKit: mapear BAR, registrar
interrupcao, alocar DMA. Nao e ABI secreta.

A favor:
- referencia aberta e completa;
- firmware da AMD e embarcavel — o NootRX ja faz isso com blobs da AMD;
- objetivo estreito e verificavel: registrador responde em vez de `0xFFFFFFFF`.

Contra:
- o `amdgpu` do Linux apoia-se em infraestrutura enorme (TTM, DRM, gerenciador
  de memoria) que precisaria de substituto;
- ordem e temporizacao de sequencia de bring-up sao implicitas no codigo e
  cruel de depurar quando erradas;
- sem tela, o diagnostico depende inteiramente do ambiente da fase 0.

### Fase 3 — CP RS64, MES, SDMA 6 (ring test) — **~50-60%**, dado 2
Mesma natureza da fase 2 e referencia aberta igualmente boa. Se a fase 2 passou,
o mais dificil (fazer a GPU acordar) ja aconteceu.

### Fase 4 — DCN 3.2.1, imagem na tela — **~40-50%**, dado 3
Display e notoriamente chato: parse de AtomBIOS, DMCUB, link training, EDID,
HPO. Referencia aberta existe, mas aqui aparece a **primeira** dependencia real
de interface fechada da Apple (`IOFramebuffer`, publicacao para o WindowServer),
o que soma custo de engenharia reversa.

### Fase 5 — back-end gfx11 para Metal — **~15-30%**, dado 4
A mais incerta, e a unica sem qualquer precedente.

A favor: ponto de insercao identificado (`MetalPluginName`); LLVM ja gera
gfx1102; a saida e testavel sem hardware.

Contra: a ABI interna do bundle e fechada, nao documentada e sem prior art. Ela
pode ser pequena e estavel — ou centenas de metodos entrelacados. **Hoje nao
sabemos qual**, e essa incerteza domina a faixa.

## 3. O numero composto

| Alvo | Fases | Probabilidade |
|---|---|---|
| Imagem na tela (marco) | 0–4 | **~10%** |
| **Aceleracao (o objetivo)** | 0–5 | **~2%** |

Faixa razoavel para o objetivo: **1% a 5%**.

## 4. O que esses numeros nao dizem

**Nao sao chance de "descobrir se e possivel".** Sao chance de *completar*.
Chegar a fase 2 e aprender se os registradores respondem tem probabilidade bem
mais alta — perto de 70-80%, porque depende so de montar ambiente e escrever
codigo com referencia aberta.

**O maior fator nao e tecnico: e atrito.** Projetos assim morrem de desistencia,
nao de impossibilidade. Um ciclo de depuracao ruim, meses sem resultado
visivel, e o interesse acaba. A fase 0 existe justamente para atacar isso.

**Os numeros mudam com informacao barata.** Duas medicoes de poucos dias podem
mexer bastante:

| Medicao | Se der bem | Se der mal |
|---|---|---|
| Inventario da pilha | confirma a premissa | encontrar gfx11 mudaria tudo, para melhor |
| Intersecao da ABI do bundle | contrato pequeno → fase 5 sobe muito | contrato enorme → fase 5 cai para ~5% |

A segunda e a mais valiosa do projeto inteiro: hoje a fase 5 e uma faixa de
15-30% **por ignorancia**, nao por dificuldade conhecida. Medir substitui a
faixa por um numero.

## 5. Interpretacao honesta

2% e baixo. Nao e zero, e nao e "impossivel" — e o numero de um projeto de
pesquisa dificil, com referencia aberta do lado do hardware e uma parede
fechada do lado do software.

Vale a pena depende do que voce chama de exito. Se for **so** a RX 7600
acelerada no macOS, 2% e ruim e existem caminhos mais baratos para o mesmo fim.
Se incluir o percurso — engenharia reversa, driver de kernel, back-end de
compilador, num projeto com resultado publicavel — o calculo muda, porque as
fases 0 a 2 entregam aprendizado independente do desfecho.

O proximo passo continua sendo o mesmo, e e barato: rodar o inventario e a
intersecao de ABI. Depois disso estes numeros deixam de ser chute em cima de
ignorancia e passam a ser estimativa em cima de medicao.
