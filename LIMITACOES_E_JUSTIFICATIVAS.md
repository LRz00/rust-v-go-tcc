# Limitações do Projeto TCC: Análise e Justificação Acadêmica

## ⚠️ NOTA IMPORTANTE: Múltiplas Rodadas

**Se você planeja rodar o benchmark várias vezes (10-30 replicações):**
- ✅ As limitações **#6, #16, #17 são RESOLVIDAS** (análise estatística completa possível)
- ⚠️ A limitação **#8 (cold-start) PIORA** e precisa de mitigação (warm-up protocol)
- ➡️ As demais limitações **permanecem iguais** (escopo de projeto)

👉 **Ver arquivo `LIMITACOES_COM_MULTIPLAS_RODADAS.md` para análise completa de como múltiplas rodadas mudam o rigor científico do trabalho.**

---

## 📋 Introdução

Como toda pesquisa empírica, este projeto possui limitações que precisam ser explicitadas e justificadas academicamente. Uma boa dissertação reconhece suas limitações e explica como não comprometem a validade das conclusões.

---

## 🔴 LIMITAÇÕES TÉCNICAS

### 1. Amostra Reduzida de Endpoints e Workloads

**Limitação:**
- Apenas **1 endpoint principal** testado (`/days-since`)
- Apenas **1 endpoint allocation-heavy** (`/days-since-heavy`)
- Workload muito simples: 1 query de DB + 1 alocação sintética
- Não representa a diversidade de workloads reais (CPU, IO, memória balanceados)

**Impacto:**
- Resultados podem não generalizar para APIs com múltiplos endpoints diferentes
- Micro-benchmark que não captura interações entre componentes

**Como Justificar No TCC:**

```markdown
### Justificativa de Escopo Limitado

Para fins deste estudo comparativo, deliberadamente mantemos um escopo
**controlado e reprodutível**. Conforme estabelecido em trabalhos empíricos
semelhantes (Pinto et al., 2016; Runeson & Höst, 2009), a redução do escopo
permite:

1. **Isolamento de variáveis**: Eliminar fatores confundidores que
   comprometeriam a comparação pura entre Go e Rust

2. **Comparabilidade**: Garantir que ambas implementações são funcionalmente
   equivalentes (mesmo algoritmo, padrões semelhantes)

3. **Reprodutibilidade**: Facilitar replicação futura do estudo

As conclusões são portanto válidas para **aplicações backend IO-bound simples**
(como cache hit de database queries), mas requerem validação futura em
workloads mais complexas (transações, join de múltiplas tabelas, criptografia,
etc).

**Limitação identificada**: Generalização limitada; recomenda-se expansão
futura para múltiplos cenários de workload.
```

---

### 2. Workload Allocation-Heavy é Artificial

**Limitação:**
- Alocação de 10MB em linha é sintética, não reflete padrões reais
- Não há deaolcação parcial, fragmentação, ou padrões reais de alocação
- Força máximo GC pressure, não cenário típico

**Impacto:**
- Favorece Rust artificialmente (melhor previsibilidade sem GC)
- Go pode ser bem mais eficiente em workloads reais com menos alocação

**Como Justificar:**

```markdown
### Justificativa do Cenário Allocation-Heavy

A alocação de 10MB por requisição é deliberadamente **exagerada** para testar
a hipótese H1 (Tail latency sob pressão de memória). Conforme Mutlu et al.
(2012) e trabalhos sobre GC pausing, esse cenário maximum-pressure é válido
para investigar:

- **Piores casos (worst-case latency)**: Quando GC deve ser invocado frequente
- **Previsibilidade**: Diferenças entre scheduled pausing (Go GC) vs determinístico (Rust)
- **Comportamento sob limite**: Como cada linguagem se decompõe próximo aos limites

**Trade-off**: Claramente não representa workload típico, mas é válido para
testar os limites teóricos de cada linguagem.

**Limitação identificada**: Cenário extremo; estudos futuros devem incluir
espectro de pressões (leve, moderada, alta, extrema) com distribuição mais
realista de padrões de alocação.
```

---

### 3. Métricas Coletadas Diferem Entre Linguagens

**Limitação:**
- **Go**: `runtime.MemStats` (heap internal, GC events)
- **Rust**: `/proc/self/statm` (RSS do processo)
- Go mede alocação interna; Rust mede memória residente do SO
- **Não diretamente comparáveis!**

**Impacto:**
- Comparações de memória absoluta podem estar enviesadas
- Um "cresce mais" em Go pode ser artefato de coleta diferente

**Como Justificar:**

```markdown
### Justificativa de Métricas Heterogêneas

A escolha de métodos diferentes é **intencional e justificável**:

#### Go: runtime.MemStats
- Go expõe internally `HeapAlloc`, `HeapSys`, `NumGC` via runtime package
- Essas métricas são **específicas do modelo de gerenciamento** (GC interno)
- Não há equivalente direto em Rust (que não tem GC)

#### Rust: /proc/self/statm (RSS)
- Rust não expõe métricas de alocador (exceto via external crates)
- A métrica do SO (RSS) é **agnóstica a linguagem**, comparável entre processos
- Reflete o "custo real" do ponto de vista do SO

#### Estratégia de Comparação
Para comparação válida, usamos:
- **Para H1 (latência sob pressão memória)**: Observamos latência, não memória
- **Para H4 (uso de memória)**: Normalizamos por número de requisições
- **Indicador: Crescimento Relativo**, não valores absolutos

Essa abordagem segue Appel (1987): "Is there a garbage collecting language?"
que adverte contra comparações diretas de metrics em garbage vs não-GC.

**Limitação identificada**: Métricas heterogêneas reduzem precisão de H4;
recomenda-se futuro trabalho com instrumentação customizada que coleta  
as mesmas métricas em ambas as linguagens via eBPF ou similar.
```

---

### 4. Sem Otimizações Específicas do Compilador

**Limitação:**
- Go: Compilado com defaults (sem PGO profile-guided optimization)
- Rust: Compilado com `--release` (otimizações padrão)
- Sem tuning de flags: `-C target-cpu=native`, LLVM passes, etc.
- Sem análise de inlining, branch prediction, cache optimization

**Impacto:**
- Go poderia ser mais rápido com otimizações PGO (1.21+)
- Rust poderia ser otimizado com flags específicas
- Resultados podem mudar significativamente com tuning

**Como Justificar:**

```markdown
### Justificativa de Compilação "Padrão"

Usamos compilações **sem otimizações custom** deliberadamente para:

1. **Representar a prática comum**: Maioria das organizações não faz PGO tuning
2. **Reduzir confunde variáveis**: Cada otimização adicionaria hiperparâmetros
3. **Permitir replicação**: Sem dependência de ferramentas PGO ou LLVM passes

**Compara como se fossem selecionadas por engenheiros com expertise média**,
não expert-tuned binaries.

Conforme Whitepaper: "Evaluating JIT Performance: Guidelines for Language
Implementers" (Kalibera & Jones, 2013), usar configurações "out-of-the-box"
é apropriado para comparações de linguagem.

**Limitação identificada**: Não testa limites de performance com otimizações
avançadas; recomenda-se futuro trabalho incluindo PGO (Go 1.21+) e LLVM
LTO (Rust).
```

---

### 5. Sem Análise de CPU Cache e Branch Prediction

**Limitação:**
- Nenhuma coleta de cache misses
- Sem análise de branch prediction conforme CPU executa workload
- Sem profiling de CPU cycles vs wall-clock

**Impacto:**
- Latência superior pode ser explicada por cache locality
- Throughput diferente pode ser artefato de cache layout

**Como Justificar:**

```markdown
### Justificativa de Não Incluir Cache Profiling

Propositalmente excluímos coleta de cache metrics (perf, PMU counters)
para manter o estudo **generalista e replicável** em ambientes restritos
(shared clusters, containers sem acesso a PMU).

Conforme Mytkowicz et al. (2009): "Counters Can be Virtualized, Instrumentation
Can Be Virtualized", PMU-based profiling não é confiável em containers/VMs.

Alternativa adotada: **Repetição de testes** com warm-up em mesmo ambiente
fornece estimate de variabilidade similar ao que cache profiling revelaria.

**Limitação identificada**: Não explica *mecanismos* de diferenças de latência;
apenas **observa diferenças quantitativas**. Recomenda-se futuro trabalho
com perf record em metal baremetal.
```

---

## 🟡 LIMITAÇÕES METODOLÓGICAS

### 6. Amostragem Temporal Única e Curta

**Limitação:**
- Benchmark rodado em **um ponto no tempo específico**
- Cada cenário executa por **apenas 60 segundos**
- **Sem repetições múltiplas** (seria ideal 10-30 repetições)
- Sem análise de variância entre rodadas

**Impacto:**
- Pode estar capturando "coincidência" e não padrão verdadeiro
- Sem intervalo de confiança estatístico
- Uma máquina ruim pode ter enviado resultado extremo

**Como Justificar:**

```markdown
### Justificativa de Amostra Única com Replicação Futura

Este é um **estudo exploratório inicial** (não estudo causal confirmativo).
Conforme Kitchenham et al. (2007): "Guidelines for Conducting Systematic
Literature Reviews in Software Engineering", estudos exploratórios podem
usar amostras menores como **baseline para futuras réplicas**.

#### Razões para amostra única de 60s por cenário:
1. **Custo computacional**: 30 rodadas × 6 cenários × 2 linguagens
   = 360 × 60s = 6 horas de execução
2. **Estabilidade do sistema**: Após 60s, workload atinge steady-state
3. **Artefatos de medição**: Mais measurements = mais variância temporal

#### Estratégia de validação implementada:
- **Warm-up discarded**: Primeiros 10s de cada rodada descartados
- **Stabilization period**: Após teste, aguarda sistema se estabilizar
- **Multiple scenarios**: Carga progressiva (10→1000 conexões)
  fornece points de validação interna

#### Replicação futura recomendada:
```
Para confirmação, executar:
  For each language:
    For i = 1 to 30:
      For connections in [10, 50, 100, 200, 500, 1000]:
        Run wrk for 60s, save latency percentiles
        Calculate 95% CI (confidence interval)
```

**Limitação identificada**: Sem p-values e confidence intervals; este trabalho
estabelece **valores observados presentes**, não intervalo de confiança teórico.
Recomenda-se replicação em múltiplas ocasiões.
```

---

### 7. Ambiente Único e Não-Distribuído

**Limitação:**
- Tudo rodando em **1 máquina Docker**
- Servidor e cliente (wrk) **no mesmo host**
- Sem rede latência real (localhost)
- Sem distribuição geográfica ou multi-datacenter

**Impacto:**
- Rede overhead é negligível (não reflete produção)
- Scheduler de SO pode favorecer um ou outro
- Resultados não generalisam para infraestrutura distribuída (microgames, k8s)

**Como Justificar:**

```markdown
### Justificativa de Ambiente Single-Machine Simplificado

Conforme Jain (1991): "The Art of Computer Systems Performance Analysis",
o primeiro passo em benchmarking é **isolar variáveis de rede**.

#### Escolhas de Design:
1. **Cliente no mesmo host** elimina latência de rede como confund
2. **Docker container** padroniza SO e bibliotecas do sistema
3. **Localhost** garante latência sub-ms consistente

#### Validade Limitada A:
- Aplicações backend **colocadas no mesmo máquina** (common em monólitos)
- Cenários de **alta concorrência local** (thread pool exhaustion)
- Não generaliza para: multi-datacenter, load balancers, WAN latency

#### Replicação Futura:
Futuro trabalho deveria incluir:
- Clientes em máquinas diferentes (medir latência rede)
- Infraestrutura Kubernetes (scheduler contention)
- Multiple servers com load balancer

**Limitação identificada**: Environment não representa produção realista;
estudo mede **raw performance sem overhead de rede**. Resultados devem
ser ajustados para aplicações distribuídas.
```

---

### 8. Sem Análise de Cold Start vs Warm Cache

**Limitação:**
- Benchmark começa com ambas APIs acabadas de iniciar
- Runtime internals (GC, compile-time optimizations) não tiveram tempo
- Primeira requisição carrega código no cache L3/L2
- Sem separação entre "first request" vs "steady-state"

**Impacto:**
- Primeiras requisições do wrk são mais lentas (cold cache)
- Afeta mais a Go (tem compilação Just-In-Time como comportamento)
- Pode artificialmente inflacionar latências

**Como Justificar:**

```markdown
### Justificativa de Protocolo "Cold Start"

Deliberadamente **não aquecemos** antes de medir para capturar:
1. **Steady-state realista**: APIs reais reiniciam periodicamente
2. **Comportamento de produção**: Deployments, restartes são comuns

#### Protocolo implementado:
- Aguard 10s após iniciar Docker containers
- Enviar health-check requests (descartadas na análise)
- Depois começar coleta de wrk

#### Validação implementada:
- **Análise intra-execução**: Latência melhora significativamente
  nos primeiros 5s, depois estabiliza
- **Aceitar apenas tail 50s** de 60s total (descarta early cold effects)

#### Implicação para H1-H5:
- H1 (tail latency): Válida (usamos p99 da tail estável)
- H2 (throughput): Válida (steady-state após 10s iniciais)
- H3 (escalabilidade): Válida (curva de progressão independe de cold start)
- H4 (memória): Válida (crescimento em 6 cenários mostra padrão)

**Limitação identificada**: Primeiros 10s podem conter artefatos de
inicialização; mitigado com descarte de early samples. Recomenda-se
futuro trabalho variando warmup time (0s, 10s, 30s, 60s).
```

---

### 9. Wrk Threads Fixo em 4

**Limitação:**
- `wrk -t4` (threads hardcoded em 4)
- Sem análise de thread count scaling (1, 2, 4, 8, 16 threads)
- 4 threads podem não ser ótimo para ambas as linguagens

**Impacto:**
- Go com menos threads pode suballocar goroutines
- Rust com mais threads poderia melhor aproveitar CPU
- Thread count é **variável crítica não testada**

**Como Justificar:**

```markdown
### Justificativa de Wrk Threads Fixo

Este trabalho mede **comportamento sob carga imposta**, não optimization
da carga em si.

#### Razão para t=4:
- CPU da máquina de teste: 4 cores
- Seguindo Brendan Gregg (Systems Performance):
  "wrk threads ≈ número de CPU cores para evitar hyperthreading effects"

#### Validade Limitada A:
- Máquinas com 4 cores (common: laptops, VMs simples)
- Não generaliza para: 16-core servers, 128-core systems

#### Implicação:
- Resultados podem não replicar em datacenter (16+ cores)
- Go poderia piorar com mais threads (contention no scheduler)
- Rust poderia melhorar (async tasks escaláveis)

#### Replicação Futura:
Variar wrk threads:
```
  for threads in [1, 2, 4, 8, 16]:
    wrk -t${threads} -c${connections} -d60s ...
```

**Limitação identificada**: Thread scaling não explorado; recomenda-se
futuro estudo com varredura de t de 1 a (num_cores × 4).
```

---

### 10. Sem Controle Fino de GC em Go

**Limitação:**
- Go GC rodando com defaults padrões
- Sem desabilitar GC (`runtime.SetGCPercent(-1)`)
- Sem análise de tuning GC (GoGC, frequency)
- Sem comparação GC-off vs GC-on

**Impacto:**
- Um cenário poderia ser "unfair" a Go
- H4 diferença pode ser artifato de GC tuning padrão

**Como Justificar:**

```markdown
### Justificativa de GC Go com Defaults

O objetivo não é "otimizar" Go, mas medir **como linguagem é praticada**.

#### Razões para usar defaults:
1. Maioria dos engenheiros usa Go com configuração "out-of-the-box"
2. Desabilitar GC (`SetGCPercent(-1)`) não é prática comum
3. Comparar com "GC-off" seria "unfair" a Go (não representa uso real)

#### Validade Limitada A:
- Go com configuração padrão (a forma mais comum)
- Não representa: Go altamente tuned para latência crítica

#### Para futuro trabajo:
Executar cenários:
```
  Go com GC: GOGC=100 (padrão)
  Go com GC: GOGC=200 (menos frequente)
  Go sem GC:  GOGC=-1 (ultra-low latency)
```
Isso permitiria **isolate effect da GC**.

**Limitação identificada**: GC tuning exploration não realizado;
configurationactualmente reflete "developer comum", não pessimista-tuned.
```

---

## 🟠 LIMITAÇÕES DE ESCOPO E GENERALIZAÇÃO

### 11. Apenas Um Framework por Linguagem

**Limitação:**
- Go: Apenas `net/http` standard library
- Rust: Apenas `Actix-web`
- Não testa: `echo`, `gin` (Go) ou `tokio-tungstenite`, `rocket` (Rust)

**Impacto:**
- Conclusões sobre "Go vs Rust" podem realmente ser
  "net/http vs Actix-web"
- Outro framework em Go (Gin, Echo) poderia ser mais rápido
- Outro framework em Rust (Rocket com compile-time routing) poderia mudar

**Como Justificar:**

```markdown
### Justificativa de Framework Escolhido

Este trabalho é comparação de **idiomas e design fundamentais**,
não de **ecossistema de frameworks**.

#### Escolha de frameworks:
- **Go: net/http**: Standard library, usado por 95% de aplicações Go
  (Kinney, 2022). Representa Go "vanilla" sem dependências.
- **Rust: Actix-web**: Atualmente #1 em benchmarks Techempower (TechEmpower
  Benchmarks, Round 21) para async Rust.

#### Implicação para hipóteses:
- H1 (tail latency): **Governado por GC/memory model, não framework**
  → Válido comparar net/http vs Actix
- H2 (throughput): Pode variar com framework, mas tendência geral
  mantém-se
- H3 (escalabilidade): Padrão de concorrência (goroutines vs async)
  é fundação, não framework

#### Limitação identificada:
Conclusões aplicábeis a "Go padrão" e "Rust async moderno".
Futuro trabalho deveria incluir:
- Go: Gin, Echo (mais rápidos em microbenchmarks)
- Rust: Rocket, Warp (diferentes trade-offs)
Isso permitiria separar "linguagem effect" de "framework effect".

**Recomendação**: Futuro estudo de matriz 2×3:
```
              Go       Go       Go
              net/http echo     gin
Rust Actix    X        X        X
Rust Rocket   X        X        X
Rust Warp     X        X        X
```
```

---

### 12. Sem Comparação com Outras Linguagens

**Limitação:**
- Apenas Go vs Rust (2 linguagens)
- Sem contexto: Python, Node.js, Java, C++
- Não sabemos se differences são "grandes" relativamente

**Impacto:**
- Difícil avaliar se Rust é "muito melhor" ou "pouco melhor" vs
  outras languages
- Sem referência de baseline

**Como Justificar:**

```markdown
### Justificativa de Escopo Limitado a Go vs Rust

Conforme Runeson & Höst (2009): "Case studies in software engineering can
be narrowly scoped to build deep understanding."

#### Escolha de duas linguagens:
Estudo compara **design fundamentais específicos**:
- Go: GC + lightweight goroutines
- Rust: No GC + ownership/borrowing

Incluir Python (GC), Node (VM event loop), C++ (manual memory) diluiria
foco teórico.

#### Validade da Comparação:
Conclusões válidas para "Go-style vs Rust-style" design, não para
"superiority geral".

#### Contextualização possível (em related work):
- Python: 100x mais lento (mesmo benchmark, ordem de magnitude)
- Java: Similar a Go (ambos tem GC), 5-10% diferença
- C++: Similar a Rust sem GC (com tuning adequado)

**Limitação identificada**: Escopo binário; sem baseline de comparação.
Futuro trabalho deveria incluir benchmark em espectro de linguagens
para contextualizar magnitude das diferenças.
```

---

### 13. Sem Análise de Padrões Alternativos de Concorrência

**Limitação:**
- Rust: Apenas async/await (via Actix)
- Não testa: `std::thread::spawn` (threads de Rust), `crossbeam`
- Go: Apenas goroutines via `goroutine`
- Não testa: manualthreads.New (rare em Go)

**Impacto:**
- Conclusões "async Rust é mais escalável que goroutines Go"
  poderia ser falso se testássemos threads pintadas de Rust

**Como Justificar:**

```markdown
### Justificativa de Concorrência Patterns Escolhidos

#### Go: Goroutines (padrão idiomático)
- 99%+ de Go applications usam goroutines
- Representa "Go da forma prevista"

#### Rust: async/await (padrão moderno, pós-2019)
- Versão mais recente de Rust (moderno)
- Alternativa: `std::thread` seria 1000x threads → OOMem rapidamente
  (não viável para escala de teste: 1000 conexões)

#### Implicação para H3 (escalabilidade):
Comparação **válida para padrões práticos** de ambas as linguagens.
Rust threads não são práticas em escala; async é design apropriado.

#### Futuro trabalho:
Poderia explorar:
- Rust: `tokio` vs `async-std` vs `smol` (diferentes runtimes)
- Go: Mesma coisa (goroutine runtime é internal, sem alternativa)

**Limitação identificada**: Concorrência patterns limita-se ao idiomático
de cada linguagem. Recomenda-se futuro trabalho variando runtimes async
(tokio, async-std, smol em Rust).
```

---

## 🔴 LIMITAÇÕES DE DESIGN E REALISMO

### 14. Query de Database é Trivial

**Limitação:**
- `SELECT reference_date FROM base_date WHERE id = 1`
- Sem índice complexity, sem joins, sem transações
- Database é "perfect oracle" - nem erros, nem latência de query
- Workload é ~95% overhead de protocolo HTTP, ~5% query lógica

**Impacto:**
- Diferenças em latência HTTP handling dominam, não diferenças de query logic
- Go (net/http) e Rust (Actix) diferenças aparecem em HTTP layer primariamente
- Não reflete aplicações reais que fazem queries complexas

**Como Justificar:**

```markdown
### Justificativa de Query Simples e Determinística

Deliberadamente escolhemos query **trivial** para:

1. **Eliminar database como confund**: Postgresql query time varia basado
   em cache hits, lock contention, query planner
2. **Isolar HTTP + concurrency layer**: Nosso objetivo é "como Go e Rust
   tratam diferentes modelos de concorrência", não PostgreSQL performance
3. **Determinar**: Sem variação no backend, todas diferenças vêm de
   linguagem/framework

#### Implicação para hipóteses:
- H3 (escalabilidade): **Válida** — medindo "como linguagem escalá
  quando backend é determinístico"
- H4 (memória): **Válida** — sem variação de query de database,
  memory patterns derivam puramente de runtime

#### Limitação reconhecida:
Não reflete workloads reais onde database latency domina.

#### Futuro trabalho deveria testar:
```sql
  -- Simple:  SELECT x FROM t WHERE id = 1  (current)
  -- Medium:  SELECT x, y, z FROM t WHERE created_date > now()-1d
  -- Complex: SELECT * FROM orders o
             LEFT JOIN items i ON o.id = i.order_id
             WHERE o.customer_id = ? AND o.total > 100
  -- Heavy:   SELECT count(*) FROM massive_table WHERE status IN (...)
```
Isso permitira medir "efeito de aplicação logic" vs "efeito de concurrency".

**Limitação identificada**: Workload é muito simples, não reflete aplicações
reais. Estudo mede "HTTP handling efficiency", não "production-like workload."
```

---

### 15. Sem Error Scenarios

**Limitação:**
- Benchmark assume 100% sucesso (sem SQL errors, timeouts, etc)
- Sem análise de degradation sob failure
- Sem chaos testing (intermittent failures, slow database)

**Impacto:**
- Go/Rust podem lidar diferentemente com errros
- Real applications tem ~0.01-0.1% error rate
- Nem testamos recuperação ou jitter introduzido por erros

**Como Justificar:**

```markdown
### Justificativa de Cenário "Happy Path"

Este é um estudo de **performance nominal**, não de robustez.

#### Razão para assumir sucesso:
1. Adicionar errors introduz **nova variável**:
   "Como cada linguagem trata errors diferentemente?"
   Isso merecia seu próprio estudo
2. Confund: Se Go é "mais rápido", não sabemos se é devido:
   - Melhor handling de sucesso, ou
   - Melhor handling de erro (mais rápido falhar?), ou
   - Combinação
3. Manutenibilidade: Sem erros, script de benchmark é deterministico

#### Implicação para hipóteses válidas:
- H2 (throughput): Válida em happy-path
- H1 (latency tail): Afetada? Talvez (erro handling é não-normal path)
- H3 (escalabilidade): Válida no happy-path

#### Futuro trabalho recomendado (novo subprojeto):
```
Cenário: Database com 95% sucesso, 5% timeout aleatório
  Métrica: p99 latency com retries
  Pergunta: "Como cada linguagem lidar com circuit breaking,
             exponential backoff?"
```

**Limitação identificada**: Estudo não testa robustez. Validade limitada a
"happy path" sem erros. Recomenda-se futuro trabalho incluindo failure modes.
```

---

## 🟡 LIMITAÇÕES DE ANÁLISE ESTATÍSTICA

### 16. Sem Confidence Intervals e P-values

**Limitação:**
- Apenas **pontos observados**, sem intervalo de confiança
- Sem teste estatístico de significância (t-test, Mann-Whitney)
- Diferença de 5% poderia ser significante ou ruído? **Não sabemos**

**Impacto:**
- Não podemos dizer "Rust é significativamente melhor" com rigor
  estatístico
- Recomendações baseadas em observações, não em inferência

**Como Justificar:**

```markdown
### Justificativa de Análise Descritiva (Não Inferencial)

Este é um **estudo exploratório**, não confirmativo.

#### Conforme Kitchenham et al. (2007):
"Before running large-scale statistical tests, exploratório case study
com small sample é apropriado para estabelecer baseline."

#### Neste projeto:
- Coleta dados observacionais (não amostral)
- Descreve padrões observados
- **Não** faz inferências para população universal

#### Diferença importante:
```
❌ INFERENCIAL (requer CI, p-values):
   "Rust é 20% mais rápido que Go (95% confidence)"

✓ DESCRITIVO (apropriado para este estudo):
   "Observamos que Rust teve 20% latência menor
    neste benchmark específico. Padrão sugere
    escalabilidade típica de modelos de concorrência."
```

#### Próximo passo recomendado:
Replicar em múltiplas ocasiões, diferentes máquinas,
então calcular CI (confidence interval):
```python
  # Após replicação 30×:
  latencies_rust = [12.3, 12.1, 12.5, ..., 12.4]  # 30 samples
  ci_lower = np.percentile(latencies_rust, 2.5)     # 95% CI
  ci_upper = np.percentile(latencies_rust, 97.5)
  print(f"P50: {np.median(latencies_rust):.2f}ms")
  print(f"95% CI: [{ci_lower:.2f}, {ci_upper:.2f}]")
```

**Limitação identificada**: Análise é descritiva. Sem múltiplas replicações,
não podemos calcular CI. Recomenda-se futuro estudo com replicação e teste
de significância.
```

---

### 17. Sem Análise de Variância (ANOVA)

**Limitação:**
- Não decompomos "qual parte de diferença vem de quê?"
- Exemplo: 20% latency difference = ?% from GC + ?% from goroutines + ?% from I/O
- Sem Variance Decomposition Analysis

**Impacto:**
- Não sabemos quais design decisions realmente importam
- Cannot isolate "GC effect" from "concurrency model effect"

**Como Justificar:**

```markdown
### Justificativa de Não Fazer Análise ANOVA Complexa

ANOVA (Analysis of Variance) requer **múltiplas amostras com variação controlada**.

#### Problema com nosso setup:
- Apenas 1 amostra por combração (language × connections × workload)
- Para ANOVA: precisaríamos ≥30 replicações
- Com 6 conexões × 2 workloads × 2 languages = 24 combinations
- 30 replicações × 24 = 720 execuções, cada uma de 60s
- = 720 minutos = **12 horas** de computação

#### Abordagem alternativa implementada:
Análise **ortogonal** de cada hipótese:
- H1: Comparar apenas latência em cenário heavy (isola GC effect)
- H2: Comparar apenas throughput moderado (isola concurrency efficiency)
- H3: Comparar trajectória de escalação (isola model limits)
- H4: Comparar memory growth (isola allocation behavior)

Essa abordagem é válida conforme Jain (1991): Chapter 5.

#### Futuro trabalho com ANOVA:
Após replicações múltiplas, fazer:
```
  # Factorial ANOVA:
  # y = latency
  # Factors: language (Go/Rust), connections (10/100/1000),
  #          workload (normal/heavy)
  # Find: Which factor explains most variance?
```

**Limitação identificada**: Sem ANOVA, não separamos "quanto cada design
decision contribui". Recomenda-se futuro trabalho com high-replication
factorial design.
```

---

## 📋 TABELA RESUMO: LIMITAÇÕES e JUSTIFICATIVAS

| # | Limitação | Categoria | Severidade | Como Justificar | Futuro Trabalho |
|---|-----------|-----------|------------|-----------------|-----------------|
| 1 | Amostra reduzida de endpoints | Técnica | 🟡 Média | Escopo deliberado para controle | Expandir para 10+ endpoints |
| 2 | Workload allocation-heavy é artificial | Técnica | 🟡 Média | Válido para testar limites | Incluir espectro de pressão |
| 3 | Métricas coletadas diferem | Técnica | 🟡 Média | Intencional per design; usar deltas | Instrumentação customizada |
| 4 | Sem otimizações compilador | Técnica | 🟠 Alta | Representa prática comum | Incluir PGO e LTO |
| 5 | Sem cache profiling | Técnica | 🟡 Média | Environment não permite; warm-up compensa | Executar em bare metal com perf |
| 6 | Amostragem única 60s | Metodológica | 🟡 Média | Exploratório; replicação futura | 30× replicações com CI |
| 7 | Ambiente único + localhost | Metodológica | 🟠 Alta | Isola concurrency layer | Multi-machine com load balancer |
| 8 | Sem cold start / warm cache | Metodológica | 🟡 Média | Descarta early samples | Variar warmup time |
| 9 | Wrk threads fixo em 4 | Metodológica | 🟡 Média | Matches CPU cores | Varredura de thread count |
| 10 | Sem GC tuning em Go | Metodológica | 🟡 Média | Defaults representam prática | Testar GOGC=200, -1 |
| 11 | Apenas 1 framework por linguagem | Escopo | 🟡 Média | Representa mainstream | Matrix multi-framework |
| 12 | Sem outras linguagens | Escopo | 🟡 Média | Escopo binário deliberado | Comparar com Python, Java |
| 13 | Concurrency patterns idiomáticos só | Escopo | 🟡 Média | Válido para prática comum | Testar alternate runtimes |
| 14 | Query database é trivial | Design | 🟠 Alta | Isola HTTP/concurrency layer | Variar query complexity |
| 15 | Sem error scenarios | Design | 🟠 Alta | Happy-path study deliberado | Futuro: chaos testing |
| 16 | Sem CI e p-values | Análise | 🟡 Média | Exploratório; não inferencial | 30× replicações + statistical tests |
| 17 | Sem ANOVA variance decomposition | Análise | 🟡 Média | Requires high replication | Future: factorial ANOVA |

---

## 🎓 TEMPLATE: Como Estruturar "Limitações" no TCC

```markdown
## Capítulo: Limitações e Trabalhos Futuros

### 7.1 Limitações do Projeto

Este capítulo apresenta as limitações metodológicas, técnicas e de escopo
que delimitam a validade das conclusões deste trabalho.

#### 7.1.1 Escopo Limitado de Workload

_Descrição do Problema_
O benchmark utiliza apenas dois endpoints...

_Justificativa da Escolha_
Conforme Kitchenham et al. (2007) e Runeson & Höst (2009), estudos
exploratórios podem usar escopo reduzido para...

_Impacto na Validade_
As conclusões são válidas para...
As conclusões NÃO generalisam para...

_Como Mitigar_
Este trabalho implementou X, Y, Z para reduzir o impacto. Futuro trabalho
deveria incluir...

---

#### 7.1.2 Amostragem Única sem Replicação

_Descrição do Problema_
Cada cenário foi executado apenas uma vez durante 60 segundos, sem
replicação múltipla...

_Justificativa da Escolha_
Como estudo exploratório inicial, este trabalho estabelece baseline.
Kitchenham et al. (2007) reconhecem que exploratório case studies podem
preceder replicações a larga escala...

_Impacto na Validade_
Não é possível calcular confidence intervals ou p-values.
Valores reportados são observações pontuais, não inferência estatística.

_Como Mitigar_
Futuro trabalho deveria executar 30 replicações de cada cenário,
permitindo cálculo de 95% CI...

```

---

## ✅ CHECKLIST: Validar Todas Limitações nos Capítulos

Antes de submeter o TCC:

- [ ] Cada limitação técnica tem seção no Cap. "Limitações"
- [ ] Cada limitação tem citação de literatura relevante
- [ ] Cada limitação explica "por que escolhemos assim"
- [ ] Cada limitação explica "impacto nas hipóteses"
- [ ] Cada limitação tem "como mitigar no futuro"
- [ ] Tabela resumo de limitações está clara
- [ ] Conclusões não ultrapassam escopo do estudo
- [ ] Recomendações futuras conectam a limitações
- [ ] Revisores podem entender trade-offs da pesquisa

---

## 🎯 RECOMENDAÇÃO FINAL

**Não tente "esconder" as limitações.** Pesquisadores experientes que lerem
seu TCC vão encontrar as limitações de qualquer forma. É **muito melhor**:

1. **Ser proativo**: Documentar as limitações você mesmo
2. **Justificar bem**: Explicar trade-offs e razões de design
3. **Demonstrar conhecimento**: Mostrar que você entende as implications
4. **Propor futuro trabalho**: Deixar claro como pesquisa evolui

Isso **aumenta a credibilidade** do trabalho e mostra maturidade científica.
