# Fase 5: o back-end gfx11 para Metal

O objetivo do projeto e **aceleracao** — logo esta fase nao e opcional nem
posterior: e o alvo. Este documento mede o que ela exige, com dados gerados
neste repositorio.

Correcao de escopo: o `08-o-que-e-o-driver.md` propunha estreitar o alvo para
"driver so de display". **Isso foi descartado.** O driver de display continua
sendo um marco intermediario obrigatorio (nao ha aceleracao sem imagem), mas
nao e o produto final.

---

## 1. Onde a fase 5 acontece

O compilador de shader **nao esta nos kexts**. A cadeia e:

```
shader .metal  --(offline, Xcode)-->  AIR (bitcode LLVM)
AIR  --(runtime, driver Metal em userspace)-->  ISA da GPU
```

A traducao AIR → ISA e feita por um driver Metal em **userspace**, nao pelo
kext. Por isso `AMDRadeonX6000.kext` sozinho nao explica a aceleracao.

**Nao ha prior art conhecido aqui.** Verificado no codigo do NootRX: seus
unicos patches de userspace (`DYLDPatches.cpp`) tratam de DRM do VideoToolbox e
de CPUID para streaming — nada de compilador. O NootRX depende inteiramente do
back-end gfx10.3 que a Apple ja tem.

> Precisao: isso mostra que esses projetos **nao precisaram** mexer no bundle
> Metal — nao que ninguem o tenha desmontado. A afirmacao sustentada pelos
> dados e mais estreita: nao ha projeto publico conhecido que implemente um
> back-end Metal para GPU nao suportada. Ver `10-legibilidade-dos-binarios.md`.

## 2. O tamanho do trabalho, medido

`tools/isa_codegen_diff.sh` compila o mesmo kernel para os dois alvos com o
LLVM aberto e compara a ISA **efetivamente emitida** — nao o que a
documentacao diz que mudou.

Resultado com um kernel minusculo (fma f32, aritmetica 16-bit, load/store
global, atomic fadd):

```
opcodes distintos: gfx1032 = 32, gfx1102 = 35
so no gfx1032: 8   |   so no gfx1102: 11   |   em comum: 24
sobreposicao: 55.8%
```

Em um kernel de ~180 linhas, **44% dos opcodes distintos divergem**.

### O que muda, em tres categorias

**a) Renomeacao em massa de acesso a memoria** — encoding novo, nao apelido:

| gfx1032 | gfx1102 |
|---|---|
| `global_load_dword` | `global_load_b32` |
| `global_store_dword` | `global_store_b32` |
| `global_atomic_cmpswap` | `global_atomic_cmpswap_b32` |
| `s_load_dword` / `dwordx2` / `dwordx4` | `s_load_b32` / `b64` / `b128` |
| `s_andn2_b32` | `s_and_not1_b32` |
| `s_ff1_i32_b32` | `s_ctz_i32_b32` |

**b) `s_delay_alu` — e o achado mais serio.**

```
gfx1032: 0 ocorrencias   |   gfx1102: 6 ocorrencias
```

O gfx11 exige que o **compilador** emita dicas explicitas de dependencia entre
instrucoes ALU. Nao e otimizacao: e mitigacao de hazard. Um back-end que nao
as emita gera codigo que **executa e produz resultado errado**, silenciosamente.

Isso descarta qualquer fantasia de "tradutor de opcodes gfx10 → gfx11": a
informacao que o `s_delay_alu` carrega nao existe no codigo gfx10.3 ja
compilado. Ela vem da analise de dependencias, dentro do compilador.

**c) ABI de kernel diferente:**

```
gfx1032:  s_load_dwordx4 s[0:3], s[4:5], 0x0
gfx1102:  s_load_b128    s[4:7], s[0:1], 0x0
```

O ponteiro de argumentos chega em SGPRs diferentes. Isso e visivel do lado do
**driver**, nao so do compilador — conecta com `FeatureUserSGPRInit16Bug` e
`FeatureArchitectedFlatScratch` do `01-delta`.

## 3. O que joga a favor

- **O back-end gfx1102 ja existe e funciona no LLVM aberto.** Foi usado para
  gerar os dados acima. Nao ha nada a inventar em geracao de codigo.
- **A saida e verificavel sem hardware.** Da para compilar, desmontar e
  comparar contra a referencia — o unico ponto do projeto testavel neste
  container, sem GPU e sem macOS.
- **E a fase de maior alavancagem com LLM** (`06-o-que-muda-com-llm.md`).

## 4. O que joga contra

- **A ABI interna do bundle e fechada.** O *ponto de insercao* esta
  identificado (secao 6), mas o contrato que o Metal espera encontrar dentro do
  bundle nao esta documentado. E o que resta de engenharia reversa aqui.
- **Nao ha exemplo anterior.** Nem o NootRX chegou perto dessa fronteira.
- **Depende de tudo antes.** Nao adianta compilador correto sem a GPU sair do
  reset (fase 2) e sem filas funcionando (fase 3).

## 5. O que da para fazer agora, sem hardware

Trabalho real desta fase, executavel deste ambiente:

1. **Caracterizar a divergencia de ISA em escala.** O experimento atual usa um
   kernel. Ampliar para um corpus (texturas, controle de fluxo, wave ops,
   atomics, DS/LDS) e medir onde a divergencia se concentra.
2. **Mapear o formato AIR.** AIR e bitcode LLVM com metadados da Apple. E
   inspecionavel com ferramentas abertas.
3. **Montar um harness de verificacao** que compare ISA emitida contra
   referencia, para servir de teste de regressao quando houver back-end.

## 6. O ponto de insercao — ENCONTRADO

As quatro perguntas desta secao estavam listadas como "a VM precisa
responder". **Duas foram respondidas por fonte publica**, e a resposta muda a
arquitetura da fase 5.

### A cadeia real

```
1. o kext publica um IOAccelerator
2. esse IOAccelerator carrega a propriedade  MetalPluginName  no IORegistry
   (ex.: "AppleIntelHD5000GraphicsMTLDriver")
3. o Metal le essa propriedade e carrega o bundle de userspace correspondente
   em /System/Library/Extensions/<nome>.bundle
4. esse bundle contem o driver Metal, incluindo o JIT AIR -> ISA
```

Que `MetalPluginName` e o elo real esta confirmado pela mensagem de erro do
proprio Metal quando ela falta:

> "Unable to locate MetalPluginName property or is of the wrong type"

Os bundles existem e sao conhecidos:
`/System/Library/Extensions/AMDRadeonX6000MTLDriver.bundle`,
`AMDMTLBronzeDriver.bundle` — **userspace, nao kext**.

### Por que isso importa tanto

O documento assumia que a fase 5 exigiria modificar o compilador fechado da
Apple. **Nao exige.** O ponto de insercao e declarativo: o driver publica um
`IOAccelerator` cujo `MetalPluginName` aponta para **um bundle nosso**.

Ou seja, o back-end gfx11 nao precisa ser enxertado no codigo da Apple — ele e
codigo proprio, num bundle proprio, e o LLVM aberto ja gera gfx1102 (secao 2).

### O que ainda nao esta respondido

**A ABI interna do bundle.** Saber que o Metal carrega o bundle nao diz qual
interface ele espera encontrar la dentro: quais simbolos, quais classes, qual
contrato. Isso nao esta documentado, e continua sendo o trabalho de engenharia
reversa da fase 5 — agora concentrado num alvo unico e identificado
(`AMDRadeonX6000MTLDriver.bundle`), em vez de espalhado.

### Sobre o AIR (pergunta 3): respondida

AIR e **bitcode LLVM** dentro de um container `metallib`. O formato ja foi
revertido publicamente e ha ferramental aberto (`MetalShaderTools`,
`unmetallib.py`), alem das proprias ferramentas da Apple (`metal-as`,
`metal-objdump`, `metallib`). O AIR nao e especifico por ASIC — quem e
especifico e o JIT dentro do bundle. Isso confirma o desenho: **um bundle novo
por familia de GPU, com o AIR igual entrando nos dois**.

## 7. O que resta para a VM

Reduziu para duas perguntas, ambas empiricas:

1. **Qual a ABI interna do bundle MTLDriver?** Alvo unico: desmontar o
   `AMDRadeonX6000MTLDriver.bundle` e mapear a interface que o Metal chama.
   E o item de maior valor do projeto inteiro que nao depende da RX 7600.
2. **Que propriedades o `IOAccelerator` precisa expor** alem de
   `MetalPluginName` para o `MTLDevice` aparecer.

Ambas obtiveis numa VM, sem a GPU presente — portanto **antes** da fase 2. O
`scan_amd_stack.py` ja localiza os bundles candidatos.
