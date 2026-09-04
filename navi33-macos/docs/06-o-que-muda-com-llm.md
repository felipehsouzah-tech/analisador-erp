# O que muda quando o trabalho e feito com LLM

As tentativas anteriores documentadas em `05-estado-da-arte.md` sao anteriores
aos modelos atuais. A pergunta e legitima: **o plano do doc 04 continua valendo
com um LLM competente no circuito?**

Resposta curta: o esforco muda de forma significativa em algumas fases e
**quase nada** nas que decidem o projeto. Este documento separa uma coisa da
outra, fase a fase.

Ressalva de vies: quem escreve isto e o LLM sendo avaliado. Ha risco de erro
nos dois sentidos — superestimar a propria utilidade, ou subestima-la por
excesso de cautela. O criterio usado para reduzir isso foi perguntar, em cada
fase, **qual e o recurso escasso** — se for producao de codigo, o LLM ajuda
muito; se for informacao que nao existe publicamente ou ciclo de feedback com
hardware, nao ajuda.

---

## 1. O que o LLM realmente muda

**Producao de codigo deixou de ser o gargalo.** As 23.428 linhas do doc 04
assustavam quando a referencia era digitacao humana. Nao assustam mais: e
codigo de porte, com referencia aberta (amdgpu, Mesa, LLVM) do lado do
hardware. Isso e real e nao deve ser minimizado.

**Engenharia reversa em escala.** Ler disassembly de `AMDRadeonX6000`,
inferir layout de struct, correlacionar simbolo com comportamento — trabalho
que consumia meses de uma pessoa e hoje e paralelizavel e barato.

**Traducao entre idiomas.** Pegar a logica do `dcn321_resource.c` e reexprimir
em C++ IOKit no formato da Apple e exatamente o tipo de tarefa em que um LLM e
forte.

## 2. O que o LLM nao muda

**Informacao que nao existe.** O gargalo das fases 2 e 3 nao e escrever codigo,
e saber *o que escrever*: a ABI C++ interna do HWLibs, os offsets de registrador
do lado da Apple, a ordem exata da sequencia de PSP/IMU. Nada disso foi
publicado. Um LLM nao recupera informacao inexistente — ele **gera codigo
plausivel**, que em bring-up de kernel e pior que nenhum: compila, carrega, e
falha de um jeito que nao ensina nada.

**O ciclo de feedback com hardware.** Bring-up e empirico: escreve, boota,
trava, le o panic, ajusta. O recurso escasso e o *ciclo*, nao a digitacao.
Escrever dez hipoteses em vez de uma nao ajuda se so da para testar uma por
reboot — e, neste hardware, cada teste depende de KDP por rede, porque nao ha
tela.

**A verificacao.** Todo codigo gerado precisa ser validado contra o
comportamento real do silicio. Sem ciclo de depuracao funcionando, nao ha como
distinguir "o modelo alucinou o offset" de "a ordem da sequencia esta errada".
O LLM aumenta o volume de hipoteses; a capacidade de testa-las continua igual.

**Firmware e autenticacao.** O PSP autentica blobs assinados. Isso e
criptografia, nao inteligencia.

## 3. Fase a fase

| Fase | Recurso escasso | Ganho com LLM |
|---|---|---|
| 0 — ambiente KDP | configuracao conhecida | **Alto.** Trabalho documentado, so trabalhoso. |
| 1 — matching | trivial | Alto, mas a fase ja era barata. |
| 2 — IMU / PSP / SMU 13 | **informacao nao publicada + ciclo de teste** | **Baixo.** E aqui que o projeto morre ou passa. |
| 3 — CP RS64 / MES / SDMA 6 | ABI da Apple + ciclo de teste | **Baixo a medio.** A logica e aberta; o encaixe nao. |
| 4 — DCN 3.2.1 | volume de codigo + ABI | **Medio a alto.** Muita logica aberta para portar. |
| 5 — back-end gfx11 | volume de codigo | **Alto.** LLVM ja tem gfx1102; e software puro, com saida testavel sem bootar. |

Note a inversao: a fase que o doc 04 aponta como **a maior de todas** (a 5) e
justamente a que mais se beneficia — o back-end gfx11 do LLVM e aberto, e da
para validar a saida do compilador sem hardware. Ja a fase 2, que e a **mais
barata em linhas de codigo** (398 linhas de `imu_v11_0.c`), e a que menos se
beneficia, porque o que falta ali nao e codigo — e conhecimento do lado fechado
e um ciclo de teste que este hardware nao tem.

## 4. A conclusao honesta

O plano do doc 04 **nao muda estruturalmente**, mas a razao muda.

Antes eu dizia: "sao 23 mil linhas, ~19x o NootRX". Esse argumento perdeu
forca — e correto reconhecer isso. Volume de codigo nao e mais o obstaculo que
era.

O argumento que **permanece de pe**, e que nao depende de quanto codigo alguem
consegue produzir:

1. A informacao do lado da Apple nao esta publicada, e nao ha como deduzi-la
   sem experimentacao no hardware.
2. A experimentacao exige um ciclo de boot/panic/diagnostico que, com 3600X
   sem iGPU e so a RX 7600, so existe via KDP por rede — e ainda assim lento.
3. A Apple, que tinha o codigo-fonte e incentivo comercial, nao fez (doc 05).

O item 2 e o mais concreto e o menos discutivel: **e um fato de hardware, nao
de capacidade intelectual.** Nenhum modelo melhora a taxa de reboots por hora.

## 5. Onde isso deixa o projeto

Ha uma leitura otimista defensavel: com LLM, as fases 4 e 5 sao mais viaveis
hoje do que eram em 2023, e isso e verdade. Mas elas so importam depois da
fase 2, e a fase 2 e justamente a de menor alavancagem.

O teste barato que decide isso continua sendo o mesmo, e nao mudou desde o
doc 03:

1. Rodar o inventario (`scan_amd_stack.py`) e confirmar a premissa.
2. Montar a fase 0 (KDP por rede) — util em qualquer cenario, e o unico jeito
   de ter diagnostico neste hardware.
3. Tentar a fase 2 com escopo de tempo definido. Se os registradores comecarem
   a responder, o resto vira problema de volume de codigo — que e exatamente o
   problema que o LLM resolve bem, e ai o projeto muda de patamar.

Ou seja: a duvida nao se resolve discutindo, se resolve na fase 2. E a fase 0
e pre-requisito dela de qualquer forma.
