# O que voce precisa de fato para comecar

Pergunta: *"preciso instalar o mac na VM, iniciar tudo certo e instalar algo
para capturar isso?"*

**Nao.** Para o trabalho de maior valor — levantar a ABI — voce nao precisa de
macOS rodando, nem de VM, nem de Mac, nem de instalar nada alem de Python e um
descompactador.

---

## 1. Por que menos do que parece

Os bundles do Metal e os kexts sao **arquivos**. A ABI esta na tabela de
simbolos deles, gravada no arquivo. Nao ha nada para "capturar em execucao":
o contrato ja esta escrito no binario, parado no disco.

Isso separa o trabalho em dois grupos, com custos muito diferentes:

| Precisa de | O que rende |
|---|---|
| **so os arquivos** | ABI dos bundles, contrato do Metal, inventario da pilha, dimensionamento da fase 5 |
| **macOS rodando (VM)** | propriedades vivas do `IORegistry`, valor real de `MetalPluginName`, o que o `MTLDevice` exige |

O primeiro grupo e onde estao as incognitas grandes do projeto. E ele nao
precisa de VM.

## 2. Receita minima, no Windows 11

Tres coisas, nenhuma exotica:

1. **Python 3** — https://python.org (marque "Add to PATH")
2. **7-Zip 22.00 ou mais novo** — le APFS, que e o formato de dentro do
   instalador. Versoes anteriores nao leem.
3. **gibMacOS** — script publico que baixa o instalador direto da Apple; no
   Windows roda com duplo clique no `.bat`.

Opcional, mas recomendado: **LLVM para Windows**. Sem ele o `macho_abi.py`
recupera classe e metodo; com ele, a assinatura completa com os tipos dos
parametros. Os tipos importam para reimplementar.

### Passos

```
1. gibMacOS.bat            -> baixa InstallAssistant.pkg (macOS Tahoe)
2. 7-Zip                   -> extrai o .pkg, depois o SharedSupport.dmg,
                              ate aparecer System/Library/Extensions
3. python tools\scan_amd_stack.py --root <pasta extraida> --out relatorio.txt
4. python tools\macho_abi.py --intersect ^
       <...>\AMDRadeonX6000MTLDriver.bundle\Contents\MacOS\AMDRadeonX6000MTLDriver ^
       <...>\AppleIntelKBLGraphicsMTLDriver.bundle\Contents\MacOS\AppleIntelKBLGraphicsMTLDriver
```

O passo 3 responde a premissa (ha vestigio de RDNA 3?). O passo 4 dimensiona a
fase 5 — quanto do plugin e contrato da Apple e quanto e trabalho novo.

O `scan_amd_stack.py` procura sozinho a arvore `System/Library/Extensions`
dentro da pasta extraida, porque o 7-Zip aninha as pastas de forma
imprevisivel. Nao e preciso acertar o caminho exato.

## 3. Quando a VM passa a ser necessaria

Depois, e para um conjunto menor de perguntas:

- qual o valor real de `MetalPluginName` no `IORegistry` de uma maquina viva;
- que outras propriedades o `IOAccelerator` precisa expor para o `MTLDevice`
  aparecer;
- observar o WindowServer sem aceleracao;
- compilar e carregar um kext de teste (fase 1).

Nada disso e pre-requisito do item 2. **Faca o item 2 primeiro** — ele e mais
barato e responde mais.

## 4. Ferramentas, e o que cada uma exige

| Ferramenta | Exige | Entrega |
|---|---|---|
| `scan_amd_stack.py` | Python | inventario da pilha; ha RDNA 3? |
| `macho_abi.py` | Python | ABI e contrato por intersecao |
| `isa_codegen_diff.sh` | LLVM | divergencia gfx1032 vs gfx1102 |
| `ip_refs.sh` / `isa_delta.py` | bash / Python | delta de hardware e de ISA |
| `dump_binary_abi.sh` / `abi_intersect.sh` | bash + LLVM | equivalentes em shell |

`macho_abi.py` e Python puro: le Mach-O (inclusive *fat*), extrai a tabela de
simbolos e desmangla. **Verificado contra o `llvm-nm`: saida identica,
simbolo a simbolo.** O desmanglador embutido recupera classe e metodo; havendo
`llvm-cxxfilt` no PATH, ele e usado automaticamente para a assinatura completa.

## 5. O que ja da para fazer hoje

Sem baixar nada, sem VM, sem macOS — ja esta feito e reproduzivel neste
repositorio:

- delta de hardware Navi 23 vs Navi 33 (docs 01, 02);
- divergencia de ISA medida com LLVM aberto (doc 09);
- metodo e ferramental de extracao de ABI, testados (docs 10, 11).

O que falta e apontar as ferramentas para os arquivos da Apple. E esse e o
passo que **so voce pode dar** — nao por dificuldade tecnica, mas porque este
ambiente nao tem acesso aos servidores da Apple (bloqueio de politica do proxy,
verificado: `403` em `swscan.apple.com`).
