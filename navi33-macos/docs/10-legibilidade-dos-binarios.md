# O que da para ler nos binarios da Apple — e o que nao da

Pergunta que motivou este documento: *"e legivel, e ninguem leu isso ate hoje?"*

A pergunta expoe uma imprecisao que este repositorio cometeu, corrigida abaixo,
e uma confusao comum entre **ler** e **reimplementar**.

---

## 1. Correcao: o que foi medido, e o que foi afirmado a mais

O `09-fase5-metal-gfx11.md` afirmou que a fronteira do compilador Metal estava
"intocada" e "virgem".

**A evidencia nao sustenta isso.** O que foi medido: NootRX, WhateverGreen e
NootedRed nao referenciam nenhum bundle `*MTLDriver*` no codigo-fonte deles.
Isso mostra que esses projetos **nao precisaram fazer patch ali** — nao que
ninguem no mundo tenha desmontado esses binarios.

A afirmacao correta e mais estreita: *nao ha projeto publico conhecido que
implemente um back-end Metal para uma GPU nao suportada*. Sobre quem ja leu
esses bundles por curiosidade ou pesquisa, este repositorio nao tem dados.

## 2. Os binarios sao lidos rotineiramente — ha mais de uma decada

A cena de Hackintosh inteira funciona lendo binario da Apple. Nao e tecnica
exotica nem descoberta recente.

A prova esta no proprio `02-pilha-macos.md`: aqueles simbolos vieram do
codigo-fonte do NootRX, e alguem os obteve lendo o binario:

```
__ZNK32AMDRadeonX6000_AmdAsicInfoNavi2327getEnumeratedRevisionNumberEv
  → AMDRadeonX6000_AmdAsicInfoNavi23::getEnumeratedRevisionNumber() const
```

Ninguem tinha o codigo-fonte disso. Leram a tabela de simbolos.

`tools/dump_binary_abi.sh` faz exatamente essa leitura, e roda no Linux — nao
precisa de macOS. Testado sobre um Mach-O sintetico com a mesma forma:

```
--- Classes C++ e seus metodos (o contrato real) ---
  AMDRadeonX6000_AmdAsicInfoNavi23 :: getEnumeratedRevisionNumber() const
  AMDRadeonX6000_AmdAsicInfoNavi23 :: initWithPciInfo(void*)
  vtable for AMDRadeonX6000_AmdAsicInfoNavi23
```

## 3. Por que da para ler: o Mach-O carrega metadados

Nao e brecha nem falha de seguranca — e como C++ funciona em bibliotecas
dinamicas. Para o *linker* resolver chamadas, o binario precisa expor:

| O que o binario carrega | O que voce descobre |
|---|---|
| Simbolo C++ *mangled* | nome da classe, do metodo, tipos dos parametros, `const` |
| `vtable for X` | existencia e ordem dos metodos virtuais |
| `typeinfo for X` | hierarquia de heranca |
| Simbolos C exportados | funcoes de entrada do modulo |
| Metadados Objective-C | classes, metodos e ivars, quando ha ObjC |

Se um binario nao expusesse nada disso, nada conseguiria se ligar a ele.

## 4. O que a leitura **nao** entrega

Aqui esta a resposta a pergunta. Ler simbolo da a **forma da interface**, nao o
**comportamento**:

| Voce ve | Voce nao ve |
|---|---|
| `initWithPciInfo(void*)` existe | o que precisa haver dentro desse `void*` |
| a ordem dos metodos na vtable | em que ordem devem ser chamados |
| que ha uma classe `AmdAsicInfoNavi23` | quais campos ela guarda e o que significam |
| que uma funcao retorna `bool` | o que faz falhar |
| o nome de um metodo de compilador | qual formato de dado ele espera |

E a diferenca entre ver o indice de um livro e ter o livro. O indice diz que o
capitulo 7 existe e como se chama — nao o que esta escrito nele.

Para reimplementar, e preciso o comportamento. Isso vem de desmontar a
implementacao instrucao por instrucao, inferir estruturas de dados a partir de
como sao acessadas, e **validar contra o hardware** — que e o ponto onde o
`06-o-que-muda-com-llm.md` mostra que a alavancagem cai e o
`04-plano-de-adaptacao.md` situa o gargalo.

## 5. Entao por que ninguem fez?

Nao por falta de acesso aos binarios. As razoes plausiveis, em ordem:

1. **Nao havia demanda.** Quem tem GPU AMD no macOS resolveu com RDNA 2, que
   funciona. Ninguem *precisava* de RDNA 3.
2. **A Apple encerrou o Intel** — o trabalho tem prazo de validade
   (`05-estado-da-arte.md`).
3. **A Apple nao fez, tendo o codigo-fonte.** Se fosse barato, a parte com
   fonte, contrato com a AMD e incentivo comercial (modulos MPX) teria feito.
4. **Reimplementar e ordens de grandeza mais caro que ler.** As secoes 3 e 4
   acima sao a explicacao tecnica; a secao 6 do `04` da o numero.

Nenhuma dessas razoes e "e impossivel ver o que ha dentro". A dificuldade nunca
esteve na legibilidade.

## 6. O que isso significa para o projeto

**A favor:** o alvo da fase 5 e inspecionavel hoje, sem macOS, com ferramenta
aberta. Da para levantar o contrato do `AMDRadeonX6000MTLDriver.bundle` — nomes
de classe, metodos, vtables — assim que houver acesso ao arquivo. Isso e
trabalho real e barato.

**Contra:** esse levantamento entrega o **esqueleto** do contrato. A carne —
semantica, ordem de chamada, formato das estruturas — sai de desmontagem e
experimentacao, e e a parte cara.

Ordem pratica sugerida: extrair a ABI primeiro (barato, e nao depende da
RX 7600), porque ela dita se existe ponto de entrada implementavel. Se as
assinaturas revelarem uma interface pequena e estavel, a fase 5 fica muito mais
plausivel do que este repositorio vinha assumindo. Se revelarem centenas de
metodos entrelacados com estruturas opacas, o contrario.

**Isso e mensuravel, e ninguem precisa adivinhar.**

---

## 7. "Mas essa ABI nao e da RX 7600" — por que ela serve mesmo assim

Objecao correta e importante. A resposta tem duas partes.

### 7.1 A ABI que interessa nao e da GPU, e da Apple

O `AMDRadeonX6000MTLDriver.bundle` e a **implementacao** para gfx10.3. A
**interface** que ele implementa e o contrato de plugin do Metal — e esse
contrato precisa ser o mesmo para AMD, Intel e (antes) NVIDIA, senao a Apple
nao conseguiria carregar plugins de fornecedores diferentes com o mesmo
mecanismo (`MetalPluginName`, secao 6 do doc 09).

O que precisamos satisfazer e o contrato, nao a implementacao. E o contrato
esta visivel em **qualquer** implementacao dele.

### 7.2 Como separar um do outro: intersecao

Havendo varias implementacoes independentes da mesma interface, da para
isola-la:

```
simbolos comuns a fornecedores diferentes  = contrato da Apple
simbolos exclusivos de um fornecedor       = implementacao dele
```

Os plugins da Intel (`AppleIntelKBLGraphicsMTLDriver`, ICL, etc.) sao
especialmente valiosos aqui: sendo de **outro fornecedor**, tudo que eles tem
em comum com o plugin da AMD e necessariamente lado Apple — nao pode ser
detalhe de AMD.

`tools/abi_intersect.sh` faz isso. Verificado sobre dois Mach-O sinteticos que
implementam a mesma interface e divergem no resto:

```
=== CONTRATO — comum a todas as implementacoes (8) ===
  MTLPluginBase::pluginInitialize(void*)
  MTLPluginBase::newCompilerContext(unsigned int)
  MTLPluginBase::compileAIR(void const*, unsigned int, void**)
  MTLPluginBase::pluginTeardown()
  vtable for MTLPluginBase
=== ESPECIFICO ===
  vendorA   5 exclusivos de 13 (38.5%)
  vendorB   4 exclusivos de 12 (33.3%)
```

A ferramenta separou o contrato do que e especifico de cada um. Com os bundles
reais, o mesmo procedimento diz **quanto** do plugin e contrato e quanto e
trabalho novo — que e exatamente a medida que falta para dimensionar a fase 5.

### 7.3 O segundo valor: um exemplo resolvido

Alem do contrato, o bundle do Navi 23 e **um caso resolvido do problema que
queremos resolver**: uma GPU AMD funcionando dentro das interfaces da Apple.

Boa parte desse mapeamento nao e especifica do gfx10.3 — gerenciamento de
memoria, submissao de comando, ciclo de vida do contexto, tratamento de erro.
Essa parte transfere direto. O que muda e a geracao de codigo, que e justamente
a parte que o LLVM aberto ja resolve para gfx1102 (doc 09, secao 2).

O mesmo raciocinio vale um nivel abaixo, nos kexts: `AMDRadeonX6000` mostra
como um driver AMD satisfaz `IOAccelerator`. A forma e reaproveitavel; o
conteudo de hardware e que muda.

### 7.4 O limite honesto

Nada disso entrega semantica (secao 4). A intersecao diz **quais** metodos o
Metal chama e com que tipos — nao em que ordem, nem o que precisa estar dentro
dos ponteiros. Isso continua saindo de desmontagem e teste.

O que a intersecao entrega e **dimensionamento**: se o contrato comum for
pequeno e estavel, a fase 5 tem um alvo definido. Se for enorme e entrelacado,
nao tem. Hoje o projeto nao sabe qual dos dois e — e essa e uma das poucas
incognitas grandes que da para eliminar **sem** a RX 7600 e **sem** bare metal.
