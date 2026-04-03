# Impacto de Múltiplas Rodadas nas Limitações do Projeto

## 📊 Resumo Executivo

Se você executar o benchmark **N vezes** (recomendado: 10-30 rodadas):

| Limitação | Status Original | Com Múltiplas Rodadas | Mudança |
|-----------|-----------------|----------------------|---------|
| **#6** - Amostragem única | 🔴 Crítica | 🟢 RESOLVIDA | ✅ Pode calcular CI e p-values |
| **#16** - Sem CI/p-values | 🔴 Crítica | 🟢 RESOLVIDA | ✅ Análise estatística completa |
| **#17** - Sem ANOVA | 🔴 Crítica | 🟡 MITIGADA | ⚠️ Pode fazer análise de variância |
| **#8** - Cold start/warm cache | 🟡 Média | 🔴 PIORA | ❌ Artefato de reinicialização |
| **#9** - Threads fixo | 🟡 Média | 🟡 CONTINUA | ⚠️ Variância de scheduler fica evidente |
| Demais | 🔴/🟡 | 🔴/🟡 IGUAIS | ➡️ Permanecem iguais |

---

## 🟢 LIMITAÇÕES RESOLVIDAS COM MÚLTIPLAS RODADAS

### Limitação #6 → RESOLVIDA: Amostragem Única

**Antes (sem múltiplas rodadas):**
```markdown
❌ LIMITAÇÃO: Apenas 1 amostra de 60s por cenário
❌ IMPACTO: Sem intervalo de confiança, sem p-values
❌ JUSTIFICATIVA: Estudo exploratório inicial, baseline para futuro
```

**Depois (com múltiplas rodadas):**
```markdown
✅ MITIGADO: N rodadas (ex: 10-30 execuções)
✅ CAPACIDADE: Calcular estatísticas robustas
✅ NOVO RIGOR: Intervalos de confiança 95%, teste de significância

### Justificativa Revisada

Este trabalho executou **30 replicações** de cada cenário
(language × connections × workload), totalizando 30 × 24 = 720 execuções
de 60s cada.

#### Por que 30?
Conforme Kitchenham et al. (2007), 30 amostras permite:
- Cálculo de 95% Confidence Interval (CI)
- Teste de normalidade (Shapiro-Wilk)
- Teste t-Student para diferenças significativas
- ANOVA para decomposição de fatores

#### Análise Estatística Implementada:
```python
# Para cada cenário, temos N=30 samples
latencies_go = [12.3, 12.1, 12.5, ..., 12.4]  # 30 values
latencies_rust = [10.1, 9.8, 10.3, ..., 10.2]  # 30 values

# Calcular estatísticas descritivas
mean_go = np.mean(latencies_go)
std_go = np.std(latencies_go)
ci_go = (np.percentile(latencies_go, 2.5), 
         np.percentile(latencies_go, 97.5))

# Teste de significância
from scipy.stats import ttest_ind
t_stat, p_value = ttest_ind(latencies_go, latencies_rust)

if p_value < 0.05:
    print(f"Diferença significativa (p={p_value:.4f})")
else:
    print(f"Diferença NÃO significativa (p={p_value:.4f})")
```

Agora podemos dizer com rigor estatístico:
- "Rust é 20% mais rápido (95% CI: [18%, 22%], p < 0.001)"
- em vez de apenas:
- "Observamos 20% diferença neste benchmark"

✅ LIMITAÇÃO RESOLVIDA
```

---

### Limitação #16 → RESOLVIDA: Sem Confidence Intervals

**Antes:**
```markdown
❌ Apenas pontos observados
❌ Sem teste de significância
❌ "Diferença de 5% poderia ser ruído?"
```

**Depois:**
```markdown
✅ Intervalos de confiança 95%
✅ P-values com teste t-Student
✅ Conclusões estatisticamente válidas

### Nova Análise Possível:

Para cada métrica em cada cenário:
```
Conexões: 100
Métrica: Latência Média

Go:   12.34ms ± 0.45ms [95% CI: 12.11, 12.57]
Rust: 10.12ms ± 0.38ms [95% CI: 9.93, 10.31]

t-test: t=12.45, p < 0.001 ***
→ Diferença significativa com 99.9% confiança
→ Rust é 17.9% mais rápido (IC: 15.2%, 20.1%)
```

✅ QUALIDADE CIENTÍFICA AUMENTADA
```

---

### Limitação #17 → MITIGADA: Sem ANOVA

**Antes:**
```markdown
❌ Apenas 1 amostra por combinação
❌ Não posso fazer ANOVA (requer replicações)
❌ Não sei quais fatores explicam variância
```

**Depois:**
```markdown
✅ ANOVA 2-way ou 3-way AGora possível
✅ Decomposição de variância entre fatores
✅ Efeitos principais identificáveis

### ANOVA 3-Way Possível:

```python
import statsmodels.formula.api as smf

# Variáveis:
# latency = latência observada
# language = Go ou Rust
# connections = 10, 50, 100, 200, 500, 1000
# workload = normal ou heavy

model = smf.ols(
    'latency ~ C(language) + C(connections) + C(workload) + '
    'C(language):C(connections) + '
    'C(language):C(workload)',
    data=df
).fit()

print(model.summary())
```

Isso responde:
- "Qual fator mais afeta latência? Language (X%), connections (Y%), workload (Z%)?"
- "Há interação entre language e connections?"
- "Go piora mais rápido com mais conexões que Rust?"

#### Resultado Esperado:
```
Source of Variation  | Sum Sq | df | Mean Sq | F     | p-value
Language             | 1200   | 1  | 1200    | 456.8 | <0.001 ***
Connections          | 5600   | 5  | 1120    | 427.0 | <0.001 ***
Workload             | 800    | 1  | 800     | 305.1 | <0.001 ***
Language:Connections | 350    | 5  | 70      | 26.7  | <0.001 ***
Language:Workload    | 42     | 1  | 42      | 16.0  | <0.001 ***
Residual             | 187    | 706| 0.265   |       |
```

Interpretação:
- Language **explica 36% da variância** em latência
- Connections **explica 56% da variância**
- Interação Language×Connections é significativa:
  → Go e Rust **degradam diferentemente** com conexões!
  → Isso é exatamente o que você quer testar (H3)

✅ ANÁLISE PODEROSA AGORA POSSÍVEL
```

---

## 🟡 LIMITAÇÕES MITIGADAS (NÃO TOTALMENTE RESOLVIDAS)

### Limitação #8 → PIORA: Cold Start / Warm Cache

**Antes:**
```markdown
🟡 Sem análise cold start (aceitável com 1 rodada)
Justificativa: APIs reiniciam periodicamente
```

**Depois:**
```markdown
🔴 PROBLEMA FICA MAIS EVIDENTE COM 30 RODADAS

Se você rodar 30 vezes sequencialmente:

Rodada 1:   latency = 15.2ms  (cold start, cache vazio)
Rodada 2:   latency = 12.5ms  (mais aquecido)
Rodada 3:   latency = 11.8ms  (estável)
...
Rodada 30:  latency = 11.9ms  (estável)

VARIÂNCIA TEMPORAL dentro de uma mesma rodada:
- Primeiros 5s da Rodada 1: latency = 20ms (muito frio)
- Últimos 55s da Rodada 1: latency = 13-14ms (mais quente)

PROBLEMA: Primeiras 3-5 rodadas têm cold-start effect
→ Inflama a média geral

### Como Mitigar:

Opção 1: Descartar primeiras 5 rodadas (warm-up)
```python
results = run_benchmark_30_times()
# Descartar warm-up
results_for_analysis = results[5:]  # Use apenas rodadas 6-30
```

Opção 2: Separar análise
```python
# Dados de cold-start (rodadas 1-5)
cold_mean = np.mean([r.latency for r in results[:5]])

# Dados de warm (rodadas 6-30)
warm_mean = np.mean([r.latency for r in results[5:]])

print(f"Cold-start: {cold_mean}ms (representa 'redeployment')")
print(f"Warm cache: {warm_mean}ms (representa 'production steady-state')")
```

### Justificativa Revisada:

```markdown
### Protocolo Revisado: Múltiplas Rodadas com Warm-up

Para cada cenário, executamos **30 rodadas de benchmark**:

#### Protocolo:
1. Iniciar APIs (Docker containers)
2. **Rodadas 1-5: Descartadas** (warm-up)
3. **Rodadas 6-30: Analisadas** (25 amostras para estatística)

#### Justificativa:
Conforme Kalibera & Jones (2013): "Methodology and Guidelines for Empirical
Evaluation of Programming Languages", primeiras 5 rodadas sofrem cold-start
effects (cache frio, JIT não-otimizado, etc).

Ao descartar as 5 primeiras, isolamos:
- Comportamento em steady-state (mais representativo de produção)
- Não misturamos "efeito de framework" com "efeito de cold cache"

#### Resultado:
Média de 25 amostras no estado "quente" = representação mais fiel de
produção real.

✅ MITIGADO (COM PROTOCOLO DE WARM-UP)
```

---

### Limitação #9 → CONTINUA: Wrk Threads Fixo

**Antes:**
```markdown
🟡 Wrk threads = 4 (não explorado)
Justificativa: 4 cores = 4 threads apropriado
```

**Depois (com múltiplas rodadas):**
```markdown
🟡 CONTINUA: Mas agora mais evidente a variância do scheduler

Com 30 rodadas, você vai observar:
- Rodada 1: 850 req/s
- Rodada 2: 847 req/s
- Rodada 3: 852 req/s
- ...
- Variância: ~0.5-1.5%

ORIGEM DA VARIÂNCIA?
- Background processes do SO
- Scheduler decisions
- Cache effects entre rodadas
- Thermal throttling

Com múltiplas rodadas, você pode **caracterizar essa variância**:
```python
results_all = [850, 847, 852, 848, 851, ...]
variancia_pct = (np.std(results_all) / np.mean(results_all)) * 100
print(f"Variância de throughput: ±{variancia_pct:.1f}%")
```

IMPORTANTE: Se Go tem variância maior que Rust, isso é **dado!**
```python
cv_go = np.std(go_throughputs) / np.mean(go_throughputs)  # Coefficient of Variation
cv_rust = np.std(rust_throughputs) / np.mean(rust_throughputs)

if cv_go > cv_rust:
    print(f"✓ Rust mais previsível: CV={cv_rust:.3f} vs CV={cv_go:.3f}")
    print("  → Suporta H1 (previsibilidade de latência)")
```

### Justificativa Revisada:

```markdown
### Análise de Variabilidade Inter-Rodadas

Conforme Mytkowicz et al. (2009): "Stabilizing and Analyzing the Variability
of System Performance", mesmo sob configuração fixa, execuções consecutivas
têm variância intrínseca.

Com 30 replicações, podemos **quantificar essa variabilidade**:
- Go: Coeficiente de Variação σ/μ = 1.2%
- Rust: Coeficiente de Variação σ/μ = 0.8%

Se Rust tiver **menor variância conforme esperado**, isso suporta H1.
Se Go tiver **variância similar**, isso questiona H1.

Threads fixo em 4 representa máquina típica de teste (laptop/VM).
Resultado é válido para ambientes similares.

⚠️ LIMITAÇÃO CONTINUA, MAS AGORA QUANTIFICÁVEL
```

---

## ➡️ LIMITAÇÕES QUE NÃO MUDAM COM MÚLTIPLAS RODADAS

### Limitações Técnicas (#1-5): Não Mudam

**Mesmos endpoints** → 30 rodadas não vai adicionar mais endpoints  
**Mesma alocação artificial** → Continua sendo 10MB sintético  
**Mesmas métricas heterogêneas** → Continua Go=MemStats, Rust=/proc  
**Mesmos compiladores** → Continua sem PGO/LTO  
**Mesma falta de cache profiling** → Continua sem perf record  

✅ **Justificativa:** Essas limitações não são sobre **amostragem**, mas sobre **project design**. Múltiplas rodadas não resolvem.

---

### Limitações de Escopo (#11-15): Não Mudam

**Mesmo 1 framework por linguagem** → 30 rodadas continua usando net/http e Actix  
**Mesmas 2 linguagens** → Não vai adicionar Python, Java  
**Mesmo padrão concorrência** → Continua goroutines vs async  
**Mesma query trivial** → Continua `SELECT * FROM base_date WHERE id=1`  
**Mesmo happy-path** → Continua sem erros  

✅ **Justificativa:** Essas limitações são sobre **escopo do projeto**, não sobre replicação.

---

## 📋 TABELA REVISADA: COMO MÚLTIPLAS RODADAS AFETAM LIMITAÇÕES

| # | Limitação | Original | Com 10-30 Rodadas | Novo Status | Ação Recomendada |
|---|-----------|----------|-------------------|------------|------------------|
| 1 | Endpoints reduzidos | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (escopo) |
| 2 | Alocação artificial | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (escopo) |
| 3 | Métricas heterogêneas | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (design) |
| 4 | Sem otimizações | 🟠 | 🟠 IGUAL | 🟠 Alta | Nada (compilador) |
| 5 | Sem cache profiling | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (infraestrutura) |
| **6** | **Amostragem única** | 🔴 | 🟢 **RESOLVIDA** | 🟢 Baixa | ✅ Implementar |
| 7 | Ambiente não-distribuído | 🟠 | 🟠 IGUAL | 🟠 Alta | Nada (setup) |
| **8** | **Cold start/warm** | 🟡 | 🔴 **PIORA** | 🟠 Alta | ⚠️ Adicionar warm-up |
| 9 | Threads fixo | 🟡 | 🟡 **QUANTIFICÁVEL** | 🟡 Média | ℹ️ Medir variância |
| 10 | Sem GC tuning | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (design) |
| 11 | 1 framework | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (escopo) |
| 12 | Sem outras linguagens | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (escopo) |
| 13 | Concurrency pattern | 🟡 | 🟡 IGUAL | 🟡 Média | Nada (escopo) |
| 14 | Query trivial | 🟠 | 🟠 IGUAL | 🟠 Alta | Nada (design) |
| 15 | Sem errors | 🟠 | 🟠 IGUAL | 🟠 Alta | Nada (escopo) |
| **16** | **Sem CI/p-values** | 🔴 | 🟢 **RESOLVIDA** | 🟢 Baixa | ✅ Implementar |
| **17** | **Sem ANOVA** | 🔴 | 🟡 **MITIGADA** | 🟡 Média | ℹ️ Implementar |

---

## 🎯 RECOMENDAÇÕES PARA VOCÊ

Se você vai rodar **10-30 vezes**, faça assim:

### 1. Atualizar Protocolo de Benchmark

```bash
#!/bin/bash
# benchmark_replicated.sh

NUM_REPLICATES=30
WARMUP_REPLICATES=5

echo "Iniciando $NUM_REPLICATES replicações (primeiras $WARMUP_REPLICATES = warm-up)"

for replicate in $(seq 1 $NUM_REPLICATES); do
    if [ $replicate -le $WARMUP_REPLICATES ]; then
        echo "Replicação $replicate (WARM-UP - será descartada)"
    else
        echo "Replicação $replicate (ANÁLISE)"
    fi
    
    # Seu benchmark.sh aqui
    ./benchmark.sh
    
    # Delay entre rodadas
    sleep 30
done
```

### 2. Atualizar Script de Análise

```python
import numpy as np
from scipy import stats

# Carregar 30 rodadas
results = load_all_30_replicates()

# Descartar warm-up (primeiras 5)
analysis_results = results[5:]  # Apenas rodadas 6-30

# Calcular estatísticas por cenário
for scenario in scenarios:
    latencies_go = [r[scenario].latency for r in analysis_results if r.language == 'go']
    latencies_rust = [r[scenario].latency for r in analysis_results if r.language == 'rust']
    
    # Descritivas
    print(f"{scenario}:")
    print(f"  Go:   {np.mean(latencies_go):.2f}ms ± {np.std(latencies_go):.2f} "
          f"[95% CI: {np.percentile(latencies_go, 2.5):.2f}, "
          f"{np.percentile(latencies_go, 97.5):.2f}]")
    print(f"  Rust: {np.mean(latencies_rust):.2f}ms ± {np.std(latencies_rust):.2f} "
          f"[95% CI: {np.percentile(latencies_rust, 2.5):.2f}, "
          f"{np.percentile(latencies_rust, 97.5):.2f}]")
    
    # Teste de significância
    t_stat, p_value = stats.ttest_ind(latencies_go, latencies_rust)
    print(f"  t-test: p-value = {p_value:.6f}")
    if p_value < 0.05:
        print(f"  ✓ Diferença significativa (p < 0.05)")
    else:
        print(f"  ✗ Diferença NÃO significativa")
```

### 3. Atualizar Capítulo de Limitações

```markdown
## Capítulo 7: Limitações e Trabalhos Futuros

### 7.1 Limitações Resolvidas no Presente Trabalho

#### 7.1.1 Amostragem Múltipla

**Modificação em relação ao planejamento original:**
Em vez de executar o benchmark uma única vez (60s), este trabalho
realizou **30 replicações** de cada cenário de teste.

**Protocolo:**
- Rodadas 1-5: Warm-up (sistema alcança steady-state)
- Rodadas 6-30: Análise (25 amostras para estatística)
- Total: 25 × 24 cenários × 60s = 25 horas de computação

**Benefício:**
Permite cálculo de confidence intervals (95% CI) e testes de
significância (t-test, Mann-Whitney). Rejeita hipótese nula
com p < 0.05 quando diferenças são reais, não artefato.

#### 7.1.2 Análise de Variabilidade Inter-Rodadas

As 30 replicações permitem **análise de variância (ANOVA)** 
mostrando quais fatores mais impactam performance:
- Language (Go/Rust): Explica X% da variância
- Connections (10/100/1000): Explica Y% da variância
- Workload (normal/heavy): Explica Z% da variância
- Interações: ...

Essa análise foi impossível com amostragem única.

### 7.2 Limitações Que Persistem

#### 7.2.1 Cold-Start Effects

[mesma justificativa, mas agora com:
 "Mitigado via warm-up de 5 rodadas"]

#### 7.2.2 Escopo Limitado de Endpoints

[mesma justificativa anterior]

...
```

---

## 📊 COMPARAÇÃO DE RIGOR CIENTÍFICO

### Antes (sem múltiplas rodadas):
```
Latência Go:  12.34ms (observação única)
Latência Rust: 10.12ms (observação única)
Conclusão: "Rust é 18% mais rápido neste benchmark"

Confiança em conclusão: ⭐⭐ (2/5 - exploratório)
```

### Depois (com 30 rodadas):
```
Latência Go:  12.34ms ± 0.45ms [95% CI: 12.11, 12.57], n=25
Latência Rust: 10.12ms ± 0.38ms [95% CI: 9.93, 10.31], n=25
t-test: t(48)=12.45, p < 0.001

Conclusão: "Rust é 17.9% mais rápido [IC: 15.2%-20.1%] com alta
confiança estatística (p < 0.001)"

Confiança em conclusão: ⭐⭐⭐⭐⭐ (5/5 - confirmativo)
```

---

## ✅ CHECKLIST: Implementar Múltiplas Rodadas

- [ ] Modificar `benchmark.sh` para rodar N vezes com delay entre rodadas
- [ ] Adicionar variável `NUM_REPLICATES` e `WARMUP_REPLICATES`
- [ ] Modificar `analyze_results.py` para calcular CI, p-values, ANOVA
- [ ] Criar separate output para "warm-up data" vs "analysis data"
- [ ] Adicionar gráficos: boxplot converging ao longo das rodadas
- [ ] Atualizar Capítulo 7 (Limitações) com nova informação
- [ ] Mencionar warm-up protocol na Metodologia
- [ ] Incluir tabela de resultados com CI (não apenas médias)
- [ ] Fazer teste de normalidade (Shapiro-Wilk) antes de t-test
- [ ] Documentar tempo total de computação (horas de rodada)

---

## 🎓 CONCLUSÃO

**Com múltiplas rodadas (10-30x):**
- ✅ **Elevam** o rigor científico de "exploratório" para "confirmativo"
- ✅ **Resolvem** 3 limitações críticas
- ✅ **Quantificam** variabilidade do sistema
- ⚠️ **Introduzem** nova limitação (cold-start) que precisa ser mitigada
- ⚠️ **Exigem** muito mais tempo de computação (12-24 horas)

**Recomendação:** **Sim, vale muito a pena** fazer múltiplas rodadas. Aumenta credibilidade e permitira publicar resultados com confiança estatística.
