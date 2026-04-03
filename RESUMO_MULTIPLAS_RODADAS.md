# Resumo Executivo: Múltiplas Rodadas para o TCC

## 🎯 A Decisão-Chave

**Você deve rodar o benchmark 10-30 vezes?**

## 📊 Comparação: 1 Rodada vs 30 Rodadas

### Cenário 1: Uma Única Rodada (60s)

```
Resultados:
  Go:   12.34ms
  Rust: 10.12ms
  Conclusão: "Rust é 18% mais rápido"

Problema:
  ❌ Sem confidence interval
  ❌ Sem p-value (pode ser coincidência)
  ❌ Análise ANOVA impossível
  ❌ Variância do sistema desconhecida
  ❌ Rigor científico: EXPLORATÓRIO (⭐⭐)
```

### Cenário 2: 30 Rodadas (25 para análise)

```
Resultados:
  Go:   12.34ms ± 0.45  [95% CI: 12.11, 12.57]  n=25
  Rust: 10.12ms ± 0.38  [95% CI: 9.93, 10.31]  n=25
  t-test: p < 0.001 ***
  Conclusão: "Rust é 17.9% mais rápido com 99.9% confiança"

Benefícies:
  ✅ Intervalo de confiança 95%
  ✅ P-value com teste estatístico
  ✅ ANOVA possível (onde vem a variância?)
  ✅ Caracteriza variância do sistema
  ✅ Rigor científico: CONFIRMATIVO (⭐⭐⭐⭐⭐)
```

---

## 📈 O Que Muda em Cada Limitação

| Limitação | 1 Rodada | 30 Rodadas | Muda? |
|-----------|----------|-----------|-------|
| **#6** Amostragem única | 🔴 Crítica | 🟢 RESOLVIDA | ✅ SIM |
| **#8** Cold-start | 🟡 Média | 🔴 PIORA | ⚠️ SIM |
| **#16** Sem CI/p-values | 🔴 Crítica | 🟢 RESOLVIDA | ✅ SIM |
| **#17** Sem ANOVA | 🔴 Crítica | 🟡 MITIGADA | ✅ SIM |
| **#9** Threads fixo | 🟡 Média | 🟡 CONTINUA | ❌ NÃO |
| Demais 12 limitações | 🟡/🟠 | 🟡/🟠 IGUAL | ❌ NÃO |

---

## ⏱️ Tempo Total Necessário

```
30 replicações × 25 min cada = ~12.5 horas

Recomendado: Rodar durante a noite ou em máquina
dedicada enquanto você trabalha em outra coisa.
```

---

## 📋 O Que Você Precisa Fazer

### Opção 1: Rápida (10 replicações | ~4.5 horas)

```bash
./benchmark_replicated.sh  # Mudar NUM_REPLICATES=10
python3 analyze_results_statistical.py
```

**Resultado:** Estatística básica, ainda bom para TCC

### Opção 2: Completa (30 replicações | ~12.5 horas)

```bash
./benchmark_replicated.sh  # NUM_REPLICATES=30 (padrão)
python3 analyze_results_statistical.py
```

**Resultado:** Rigor máximo, publicável

### Opção 3: Minimalista (1 rodada | status quo)

Manter como está, justificar como "exploratório"

---

## 💡 Minha Recomendação

**Faça assim:**

1. **Agora**: Rodar 10 replicações (4.5h) para validar pipeline
2. **Depois**: Se tudo funcionar, expanda para 30 (mais 8h)
3. **Resultado final**: 30 replicações = máxima credibilidade

---

## 🔧 Como Começar

### Passo 1: Preparar Scripts

```bash
# Copiar e adaptar script ao seu projeto
cp PROTOCOLO_MULTIPLAS_RODADAS.md ./scripts/

# Criar benchmark_replicated.sh
nano benchmark_replicated.sh  # Cole o script do doc
chmod +x benchmark_replicated.sh

# Criar analyze_results_statistical.py
nano analyze_results_statistical.py  # Cole o script do doc
chmod +x analyze_results_statistical.py
```

### Passo 2: Testar com 1 Replicação

```bash
# Mudar temporariamente para teste
NUM_REPLICATES=1
WARMUP_REPLICATES=0

./benchmark_replicated.sh
```

### Passo 3: Se Funcionar, Expandir

```bash
# Voltar ao normal
NUM_REPLICATES=30
WARMUP_REPLICATES=5

# Rodar durante a noite com &
nohup ./benchmark_replicated.sh &
```

### Passo 4: Analisar Resultados

```bash
python3 analyze_results_statistical.py
# Vai gerar tabelas com CI, p-values, ANOVA
```

---

## 📝 Atualizar o Texto do TCC

### Seção: Metodologia

```markdown
### Protocolo de Replicação

Para assegurar robustez estatística, cada cenário de teste foi 
executado **N=30 vezes**, seguindo protocolo de replicação
recomendado por Kitchenham et al. (2007).

#### Estratégia:
- Rodadas 1-5: Warm-up (descartadas)
- Rodadas 6-30: Análise (n=25 amostras)

Isso permite cálculo de:
- Confidence intervals (95% CI)
- Teste de significância (t-test)
- Análise de variância (ANOVA)
```

### Seção: Limitações

```markdown
#### Limitação #6 RESOLVIDA: Amostragem Múltipla

Originalmente esperado como limitação crítica, foi RESOLVIDA
através de protocolo de 30 replicações com warm-up.

Resultado: 25 amostras por cenário, permitindo análise
estatística completa (CI, p-values, ANOVA).
```

---

## ⚠️ Armadilhas Comuns

### 1. Não Descartar Warm-up
❌ **Errado:** Usar todas as 30 rodadas
✅ **Certo:** Descartar 5 primeiras, usar 25

### 2. Esquecer de Meio de Rodadas
❌ **Errado:** Contar cada requisição como amostra independente
✅ **Certo:** Fazer rodada completa (60s) uma única vez

### 3. Não Registrar Configuração
❌ **Errado:** Não saber qual versão do Go/Rust foi usada
✅ **Certo:** Salvar test_config.json com todas as informações

### 4. Não Deixar Tempo Entre Rodadas
❌ **Errado:** Rodar imediatamente uma após outra (sem delay)
✅ **Certo:** Aguardar 30-60s entre replicações

---

## 🎓 Comparativo com Trabalhos Similares

### Trabalhos Exploratórios:
- 1-2 amostras por cenário
- Sem CI, sem p-values
- Usados para "estabelecer baseline"
- Seu projeto ATUAL: aqui

### Trabalhos Confirmadores:
- 10-30 amostras por cenário
- Com CI 95% e tests estatísticos
- Usados para "validar hipóteses"
- Seu projeto DEPOIS DE 30 rodadas: aqui

---

## 🚀 Próximas Etapas

- [ ] Copiar scripts de `PROTOCOLO_MULTIPLAS_RODADAS.md`
- [ ] Testar com 1 replicação
- [ ] Rodar 10 replicações (4.5h)
- [ ] Se houver tempo, expandir para 30 (mais 8h)
- [ ] Analisar com script Python
- [ ] Atualizar TCC com estatísticas
- [ ] Atualizar Capítulo 7 (Limitações)

---

## 📊 Resultado Final Esperado

**Com 30 replicações, você terá:**

```
✅ TCC com rigor científico máximo
✅ Resultados publicáveis
✅ Confidence intervals em todas as conclusões
✅ P-values para todas as diferenças
✅ ANOVA mostrando efeito de cada fator
✅ 3 limitações críticas (#6, #16, #17) RESOLVIDAS

Isso converte seu trabalho de:
  "Estudo exploratório de desempenho Go vs Rust"
para:
  "Análise confirmativa com rigor estatístico de performance Go vs Rust"
```

---

## 📚 Referências

- Kitchenham et al. (2007): "Guidelines for Performing Systematic Literature Reviews"
- Kalibera & Jones (2013): "Methodology and Guidelines for Empirical Evaluation"
- Mytkowicz et al. (2009): "Stabilizing and Analyzing the Variability"
- Jain (1991): "The Art of Computer Systems Performance Analysis"

---

## 🎯 Decisão Final

**Recomendação:** 🟢 **SIM, faça 30 replicações**

**Por quê:**
- Tempo: apenas 12 horas (aceitável)
- Retorno: converte trabalho de exploratório para confirmativo
- Diferença: tremenda em credibilidade científica
- Justificativa clara para avaliadores/examinadores

**Prazo apertado?** Faça pelo menos 10 replicações (4.5h), depois expanda.
