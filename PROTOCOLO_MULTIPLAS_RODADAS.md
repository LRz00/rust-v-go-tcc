# Protocolo Prático: Implementando Múltiplas Rodadas no Benchmark

## 🚀 Guia Passo a Passo Para Executar 30 Replicações

Este documento fornece instruções práticas para rodar seu benchmark 30 vezes e analisar os resultados com rigor estatístico.

---

## 📋 Pré-Requisitos

- ✅ Docker e Docker Compose instalados
- ✅ Python 3.8+ com `numpy`, `scipy`, `pandas` instalados
- ✅ `wrk` instalado e no PATH
- ✅ ~15-24 horas de tempo de computação disponível
- ✅ Máquina com pelo menos 4GB RAM

---

## 🔧 Script 1: Benchmark com Replicações

Crie um novo arquivo: `benchmark_replicated.sh`

```bash
#!/bin/bash

# ============================================================================
# BENCHMARK REPLICADO: Executa N replicações do benchmark
# Descarta primeiras WARMUP replicações para steady-state
# ============================================================================

set -e

# CONFIGURAÇÕES
NUM_REPLICATES=30
WARMUP_REPLICATES=5
ANALYSIS_REPLICATES=$((NUM_REPLICATES - WARMUP_REPLICATES))

RESULTS_DIR="benchmark_results_replicated"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$RESULTS_DIR/$TIMESTAMP"

GO_URL="http://localhost:8080"
RUST_URL="http://localhost:8081"
WRK_THREADS=4
DURATION="60s"
SCENARIOS=(10 50 100 200 500 1000)

# ============================================================================
# FUNÇÕES
# ============================================================================

setup_results_dir() {
    mkdir -p "$RUN_DIR"
    mkdir -p "$RUN_DIR/warmup"
    mkdir -p "$RUN_DIR/analysis"
    echo "Resultados serão salvos em: $RUN_DIR"
}

check_services() {
    echo "Verificando disponibilidade dos serviços..."
    
    for i in {1..10}; do
        if curl -s "$GO_URL/health" > /dev/null 2>&1 && \
           curl -s "$RUST_URL/health" > /dev/null 2>&1; then
            echo "✓ APIs online"
            return 0
        fi
        echo "  Tentativa $i/10..."
        sleep 2
    done
    
    echo "ERRO: APIs não responderam após 20 segundos"
    exit 1
}

collect_metrics() {
    local url=$1
    local output_file=$2
    curl -s "$url/metrics" > "$output_file" 2>/dev/null || \
        echo "{\"error\": \"failed\"}" > "$output_file"
}

parse_wrk_output() {
    local wrk_output=$1
    local output_json=$2
    
    # Extração similar ao benchmark.sh original
    local latency_line=$(echo "$wrk_output" | grep -E "^\s+Latency" | head -1)
    local latency_avg=$(echo "$latency_line" | awk '{print $2}')
    local latency_stdev=$(echo "$latency_line" | awk '{print $3}')
    local latency_max=$(echo "$latency_line" | awk '{print $4}')
    
    local req_line=$(echo "$wrk_output" | grep -E "^\s+Req/Sec" | head -1)
    local req_sec=$(echo "$req_line" | awk '{print $2}')
    
    local total_requests=$(echo "$wrk_output" | grep "requests in" | awk '{print $1}')
    
    local socket_errors=$(echo "$wrk_output" | grep "Socket errors" | grep -oE "[0-9]+" | head -1)
    local non2xx=$(echo "$wrk_output" | grep "Non-2xx" | grep -oE "[0-9]+" | head -1)
    local total_errors=0
    
    [ -n "$socket_errors" ] && total_errors=$((total_errors + socket_errors))
    [ -n "$non2xx" ] && total_errors=$((total_errors + non2xx))
    
    local requests_per_sec=$(echo "$wrk_output" | grep "Requests/sec:" | awk '{print $2}')
    
    # Defaults
    latency_avg=${latency_avg:-"0ms"}
    latency_stdev=${latency_stdev:-"0ms"}
    latency_max=${latency_max:-"0ms"}
    req_sec=${req_sec:-"0"}
    total_requests=${total_requests:-"0"}
    total_errors=${total_errors:-"0"}
    requests_per_sec=${requests_per_sec:-"0"}
    
    cat > "$output_json" <<EOF
{
    "latency": {
        "avg": "$latency_avg",
        "stdev": "$latency_stdev",
        "max": "$latency_max"
    },
    "requests_per_sec": {
        "avg": "$req_sec"
    },
    "total": {
        "requests": "$total_requests",
        "errors": "$total_errors"
    },
    "requests_per_sec_final": "$requests_per_sec"
}
EOF
}

run_benchmark() {
    local lang=$1
    local url=$2
    local connections=$3
    local replicate=$4
    
    local category="warmup"
    if [ $replicate -gt $WARMUP_REPLICATES ]; then
        category="analysis"
    fi
    
    local run_dir="$RUN_DIR/$category/rep${replicate}/${lang}_c${connections}"
    mkdir -p "$run_dir"
    
    if [ $replicate -le $WARMUP_REPLICATES ]; then
        echo "  [WARM-UP] Rep $replicate/$NUM_REPLICATES - $lang - $connections conexões"
    else
        echo "  [ANÁLISE] Rep $replicate/$NUM_REPLICATES - $lang - $connections conexões"
    fi
    
    # Coleta PRÉ
    collect_metrics "$url" "$run_dir/metrics_before.json"
    
    # Executa wrk
    local wrk_output=$(wrk -t$WRK_THREADS -c$connections -d$DURATION --latency "$url/days-since" 2>&1)
    echo "$wrk_output" > "$run_dir/wrk_output.txt"
    
    # Parseia
    parse_wrk_output "$wrk_output" "$run_dir/wrk_summary.json"
    
    # Aguarda estabilização
    sleep 5
    
    # Coleta PÓS
    collect_metrics "$url" "$run_dir/metrics_after.json"
    
    # Salva config
    cat > "$run_dir/test_config.json" <<EOF
{
    "language": "$lang",
    "url": "$url",
    "connections": $connections,
    "threads": $WRK_THREADS,
    "duration": "$DURATION",
    "replicate": $replicate,
    "category": "$category",
    "timestamp": "$(date --rfc-3339=seconds)"
}
EOF
}

run_allocation_heavy_benchmark() {
    local lang=$1
    local url=$2
    local connections=$3
    local replicate=$4
    
    local category="warmup"
    if [ $replicate -gt $WARMUP_REPLICATES ]; then
        category="analysis"
    fi
    
    local run_dir="$RUN_DIR/$category/rep${replicate}/${lang}_heavy_c${connections}"
    mkdir -p "$run_dir"
    
    if [ $replicate -le $WARMUP_REPLICATES ]; then
        echo "  [WARM-UP] Rep $replicate/$NUM_REPLICATES - $lang HEAVY - $connections conexões"
    else
        echo "  [ANÁLISE] Rep $replicate/$NUM_REPLICATES - $lang HEAVY - $connections conexões"
    fi
    
    collect_metrics "$url" "$run_dir/metrics_before.json"
    
    local wrk_output=$(wrk -t$WRK_THREADS -c$connections -d$DURATION --latency "$url/days-since-heavy" 2>&1)
    echo "$wrk_output" > "$run_dir/wrk_output.txt"
    
    parse_wrk_output "$wrk_output" "$run_dir/wrk_summary.json"
    
    sleep 5
    
    collect_metrics "$url" "$run_dir/metrics_after.json"
    
    cat > "$run_dir/test_config.json" <<EOF
{
    "language": "$lang",
    "url": "$url",
    "connections": $connections,
    "threads": $WRK_THREADS,
    "duration": "$DURATION",
    "replicate": $replicate,
    "category": "$category",
    "workload": "heavy",
    "timestamp": "$(date --rfc-3339=seconds)"
}
EOF
}

# ============================================================================
# MAIN
# ============================================================================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK REPLICADO: $NUM_REPLICATES rodadas                 ║"
echo "║  (Primeiras $WARMUP_REPLICATES = warm-up, últimas $ANALYSIS_REPLICATES = análise) ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

setup_results_dir

# Inicia Docker se necessário
echo "Iniciando serviços..."
docker compose restart > /dev/null 2>&1 || docker compose up -d

echo "Aguardando inicialização..."
sleep 10

check_services

# Loop de replicações
for replicate in $(seq 1 $NUM_REPLICATES); do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ $replicate -le $WARMUP_REPLICATES ]; then
        echo "REPLICAÇÃO $replicate/$NUM_REPLICATES (WARM-UP - será descartada)"
    else
        echo "REPLICAÇÃO $replicate/$NUM_REPLICATES (ANÁLISE)"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    for scenario in "${SCENARIOS[@]}"; do
        echo ""
        echo "Cenário: $scenario conexões"
        run_benchmark "go" "$GO_URL" "$scenario" "$replicate"
        run_benchmark "rust" "$RUST_URL" "$scenario" "$replicate"
        run_allocation_heavy_benchmark "go" "$GO_URL" "$scenario" "$replicate"
        run_allocation_heavy_benchmark "rust" "$RUST_URL" "$scenario" "$replicate"
    done
    
    # Aguarda entre rodadas (menos na última)
    if [ $replicate -lt $NUM_REPLICATES ]; then
        echo ""
        echo "Aguardando estabilização entre replicações (30s)..."
        sleep 30
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK CONCLUÍDO!                                          ║"
echo "║  Resultados em: $RUN_DIR               ║"
echo "║  Warm-up replicações: 1-$WARMUP_REPLICATES (descarte)         ║"
echo "║  Análise replicações: $((WARMUP_REPLICATES+1))-$NUM_REPLICATES (use estas)           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
```

### Como Usar:

```bash
# Fazer executable
chmod +x benchmark_replicated.sh

# Rodar (vai levar ~15-24 horas)
./benchmark_replicated.sh
```

---

## 📊 Script 2: Análise com Estatística

Crie: `analyze_results_statistical.py`

```python
#!/usr/bin/env python3
"""
Análise estatística dos resultados de benchmark replicado
Calcula CI, p-values, ANOVA, etc.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
from scipy import stats
import pandas as pd

def load_json(filepath: Path) -> Dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return {}

def parse_wrk_latency(latency_str: str) -> float:
    """Converte string de latência do wrk para ms"""
    if not latency_str or latency_str == "0":
        return 0.0
    
    latency_str = str(latency_str).strip()
    try:
        if latency_str.endswith('ms'):
            return float(latency_str.replace('ms', '').strip())
        elif latency_str.endswith('us'):
            return float(latency_str.replace('us', '').strip()) / 1000
        elif latency_str.endswith('s'):
            return float(latency_str.replace('s', '').strip()) * 1000
        else:
            return float(latency_str)
    except:
        return 0.0

def parse_requests(req_str: str) -> float:
    """Converte string de requisições para número"""
    if not req_str or req_str == "0":
        return 0.0
    
    req_str = str(req_str).strip()
    try:
        if 'k' in req_str.lower():
            return float(req_str.lower().replace('k', '').strip()) * 1000
        else:
            return float(req_str)
    except:
        return 0.0

def analyze_run(run_dir: Path, lang: str, connections: int) -> Dict:
    """Analisa uma replicação específica"""
    
    wrk_summary = load_json(run_dir / "wrk_summary.json")
    
    result = {
        'language': lang,
        'connections': connections,
        'latency_avg_ms': 0.0,
        'requests_per_sec': 0.0,
    }
    
    if wrk_summary.get('latency'):
        avg_val = wrk_summary['latency'].get('avg', '0')
        if avg_val and avg_val != "":
            result['latency_avg_ms'] = parse_wrk_latency(avg_val)
    
    if wrk_summary.get('requests_per_sec_final'):
        req_val = wrk_summary['requests_per_sec_final']
        if req_val:
            result['requests_per_sec'] = parse_requests(req_val)
    
    return result

def analyze_replicated_results(run_dir: Path) -> pd.DataFrame:
    """Analisa todos os resultados replicados (apenas ANALYSIS, não WARMUP)"""
    
    results = []
    
    analysis_dir = run_dir / "analysis"
    if not analysis_dir.exists():
        print(f"ERRO: {analysis_dir} não encontrado")
        return pd.DataFrame()
    
    # Itera por replicação
    for rep_dir in sorted(analysis_dir.iterdir()):
        if not rep_dir.is_dir():
            continue
        
        rep_num = int(rep_dir.name.replace('rep', ''))
        
        # Itera por cenário (go_c10, rust_c10, etc)
        for scenario_dir in sorted(rep_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            
            dirname = scenario_dir.name
            
            # Parse
            if dirname.startswith('go_heavy_c'):
                connections = int(dirname.replace('go_heavy_c', ''))
                result = analyze_run(scenario_dir, 'go_heavy', connections)
            elif dirname.startswith('go_c'):
                connections = int(dirname.replace('go_c', ''))
                result = analyze_run(scenario_dir, 'go', connections)
            elif dirname.startswith('rust_heavy_c'):
                connections = int(dirname.replace('rust_heavy_c', ''))
                result = analyze_run(scenario_dir, 'rust_heavy', connections)
            elif dirname.startswith('rust_c'):
                connections = int(dirname.replace('rust_c', ''))
                result = analyze_run(scenario_dir, 'rust', connections)
            else:
                continue
            
            result['replicate'] = rep_num
            results.append(result)
    
    return pd.DataFrame(results)

def print_statistical_summary(df: pd.DataFrame):
    """Imprime resumo estatístico com CI e p-values"""
    
    print("\n" + "="*120)
    print("ANÁLISE ESTATÍSTICA: GO vs RUST (30 Replicações, N=25 análise)")
    print("="*120)
    
    for workload_type in ['normal', 'heavy']:
        # Filter
        if workload_type == 'normal':
            go_data = df[df['language'] == 'go']
            rust_data = df[df['language'] == 'rust']
        else:
            go_data = df[df['language'] == 'go_heavy']
            rust_data = df[df['language'] == 'rust_heavy']
        
        if go_data.empty or rust_data.empty:
            continue
        
        print(f"\n[CENÁRIO: {workload_type.upper()}]")
        print("-" * 120)
        
        for connections in sorted(df['connections'].unique()):
            go_subset = go_data[go_data['connections'] == connections]['latency_avg_ms'].values
            rust_subset = rust_data[rust_data['connections'] == connections]['latency_avg_ms'].values
            
            if len(go_subset) == 0 or len(rust_subset) == 0:
                continue
            
            # Descritivas
            go_mean = np.mean(go_subset)
            go_std = np.std(go_subset)
            go_ci_lower = np.percentile(go_subset, 2.5)
            go_ci_upper = np.percentile(go_subset, 97.5)
            
            rust_mean = np.mean(rust_subset)
            rust_std = np.std(rust_subset)
            rust_ci_lower = np.percentile(rust_subset, 2.5)
            rust_ci_upper = np.percentile(rust_subset, 97.5)
            
            # Teste t
            t_stat, p_value = stats.ttest_ind(go_subset, rust_subset)
            
            # Output
            print(f"\nConexões: {connections}")
            print(f"  Go:   {go_mean:7.2f}ms ± {go_std:.2f}  [95% CI: {go_ci_lower:7.2f}, {go_ci_upper:7.2f}]  n={len(go_subset)}")
            print(f"  Rust: {rust_mean:7.2f}ms ± {rust_std:.2f}  [95% CI: {rust_ci_lower:7.2f}, {rust_ci_upper:7.2f}]  n={len(rust_subset)}")
            
            diff_pct = ((go_mean - rust_mean) / rust_mean) * 100 if rust_mean > 0 else 0
            print(f"  Diferença: {diff_pct:+6.1f}%")
            
            if p_value < 0.001:
                print(f"  t-test: t={t_stat:.2f}, p < 0.001 ***")
                print(f"  ✓ Diferença MUITO significativa")
            elif p_value < 0.05:
                print(f"  t-test: t={t_stat:.2f}, p = {p_value:.4f} **")
                print(f"  ✓ Diferença significativa")
            else:
                print(f"  t-test: t={t_stat:.2f}, p = {p_value:.4f}")
                print(f"  ✗ Diferença NÃO significativa")

def print_anova_analysis(df: pd.DataFrame):
    """Análise de variância (ANOVA) para normal workload"""
    
    print("\n" + "="*120)
    print("ANÁLISE DE VARIÂNCIA (ANOVA): Qual fator explica mais variância?")
    print("="*120)
    
    # Para workload normal
    go_data = df[df['language'] == 'go'].copy()
    rust_data = df[df['language'] == 'rust'].copy()
    
    if go_data.empty or rust_data.empty:
        print("Dados insuficientes para ANOVA")
        return
    
    combined = pd.concat([go_data, rust_data])
    
    # ANOVA 2-way: language × connections
    print("\n[ANOVA 2-Way: Language × Connections]")
    print("-" * 120)
    
    # Preparar dados
    combined['connection_group'] = pd.Categorical(combined['connections'], 
                                                  categories=sorted(combined['connections'].unique()),
                                                  ordered=True)
    
    # Fazer grupos para ANOVA
    groups_by_lang_conn = []
    factors = {'language': [], 'connections': [], 'latency': []}
    
    for lang in ['go', 'rust']:
        for conn in sorted(combined['connections'].unique()):
            subset = combined[(combined['language'] == lang) & 
                            (combined['connections'] == conn)]['latency_avg_ms'].values
            if len(subset) > 0:
                factors['language'].extend([lang] * len(subset))
                factors['connections'].extend([conn] * len(subset))
                factors['latency'].extend(subset.tolist())
    
    df_anova = pd.DataFrame(factors)
    
    # Calcular de forma manual (ANOVA básica)
    overall_mean = df_anova['latency'].mean()
    
    # Variância total
    ss_total = np.sum((df_anova['latency'] - overall_mean) ** 2)
    
    # Variância por Language
    ss_language = 0
    for lang in df_anova['language'].unique():
        subset = df_anova[df_anova['language'] == lang]['latency']
        n = len(subset)
        subset_mean = subset.mean()
        ss_language += n * (subset_mean - overall_mean) ** 2
    
    # Variância por Connections
    ss_connections = 0
    for conn in df_anova['connections'].unique():
        subset = df_anova[df_anova['connections'] == conn]['latency']
        n = len(subset)
        subset_mean = subset.mean()
        ss_connections += n * (subset_mean - overall_mean) ** 2
    
    ss_error = ss_total - ss_language - ss_connections
    
    # Percentuais
    pct_language = (ss_language / ss_total) * 100
    pct_connections = (ss_connections / ss_total) * 100
    pct_error = (ss_error / ss_total) * 100
    
    print(f"Language (Go vs Rust):     {pct_language:6.1f}% da variância")
    print(f"Connections (10 vs 1000):  {pct_connections:6.1f}% da variância")
    print(f"Error/Residual:            {pct_error:6.1f}% da variância")
    print("\nInterpretação:")
    if pct_connections > pct_language:
        print(f"  → Número de conexões tem MAIOR efeito que a linguagem")
        print(f"  → Ambas escaláveis similarmente? Ou degradação é universal?")
    else:
        print(f"  → Linguagem tem MAIOR efeito que conexões")
        print(f"  → Uma linguagem escala melhor que a outra")

def main():
    import sys
    
    if len(sys.argv) < 2:
        # Procurar o diretório mais recente
        results_dir = Path("benchmark_results_replicated")
        if not results_dir.exists():
            print("Erro: benchmark_results_replicated não encontrado")
            sys.exit(1)
        
        run_dir = sorted(results_dir.iterdir())[-1]
    else:
        run_dir = Path(sys.argv[1])
    
    print(f"Analisando: {run_dir}")
    
    # Carregar dados
    df = analyze_replicated_results(run_dir)
    
    if df.empty:
        print("Nenhum resultado encontrado ou erro ao parsing")
        sys.exit(1)
    
    print(f"Total de replicações analisadas: {df['replicate'].max()}")
    print(f"Total de observações: {len(df)}")
    
    # Análises
    print_statistical_summary(df)
    print_anova_analysis(df)
    
    print("\n" + "="*120)
    print("ANÁLISE CONCLUÍDA")
    print("="*120)

if __name__ == '__main__':
    main()
```

### Como Usar:

```bash
# Fazer executable
chmod +x analyze_results_statistical.py

# Rodar (vai analisar automaticamente o diretório mais recente)
python3 analyze_results_statistical.py

# Ou especificar diretório
python3 analyze_results_statistical.py benchmark_results_replicated/20260403_101530
```

---

## ⏱️ Estimativa de Tempo

```
Tempo por replicação: 6 cenários × 2 linguagens × 2 workloads × 60s = ~24 min
+ tempo de warm-up entre replicações (30s) = ~25 min/replicação

Total para 30 replicações:
- 5 warm-up:  5 × 25 min = 125 min = ~2h
- 25 análise: 25 × 25 min = 625 min = ~10.4h
- TOTAL:                      = ~12.4 horas

⚠️ Considere rodar durante a noite ou em background
```

---

## 📝 Interpretação dos Resultados

Depois de rodar `analyze_results_statistical.py`, você vai ver algo como:

```
[CENÁRIO: NORMAL]
─────────────────────────────────────────

Conexões: 100
  Go:   12.34ms ± 0.45  [95% CI: 12.11, 12.57]  n=25
  Rust:  10.12ms ± 0.38  [95% CI: 9.93, 10.31]  n=25
  Diferença: +21.9%
  t-test: t=12.45, p < 0.001 ***
  ✓ Diferença MUITO significativa

[ANOVA 2-Way: Language × Connections]
─────────────────────────────────────────

Language (Go vs Rust):     35.2% da variância
Connections (10 vs 1000):  62.1% da variância
Error/Residual:             2.7% da variância

Interpretação:
  → Número de conexões tem MAIOR efeito que a linguagem
  → Ambas linguagens degradam similarmente com mais conexões?
```

---

## ✅ Próximos Passos Após Análise

1. **Documentar warm-up behavior**
   - Incluir gráfico de latência ao longo das 30 replicações
   - Mostrar convergência para steady-state
   - Documentar quantas rodadas foram necessárias para estabilização

2. **Atualizar Capítulo de Metodologia**
   - Mencionar protocolo de 30 replicações
   - Explicar warm-up de 5 rodadas
   - Citar como isso garante "análise em steady-state"

3. **Atualizar Capítulo de Limitações**
   - Marcar #6, #16 como "RESOLVIDAS"
   - Marcar #17 como "MITIGADA com ANOVA implementada"
   - Mencionar #8 (cold-start) mitigado com warm-up

4. **Incluir Tabelas com CI nos Resultados**
   - Em vez de:
     ```
     Go: 12.34ms
     Rust: 10.12ms
     ```
   - Usar:
     ```
     Go:   12.34ms [95% CI: 12.11, 12.57]
     Rust: 10.12ms [95% CI: 9.93, 10.31], p < 0.001
     ```

---

## 🎯 Recomendação Final

**Execute 30 replicações?** 

- ✅ **SIM** se seu TCC vai ser avaliado com rigor estatístico
- ✅ **SIM** se você quer publicar os resultados depois
- ✅ **SIM** se quer "credibilidade máxima"
- ❌ **NÃO** se você tem prazo apertado (leva 12+ horas)
- ⚠️ **TALVEZ** começar com 10 replicações (4.5 horas) e fazer 30 se houver tempo

A diferença em credibilidade científica é **ENORME** com múltiplas rodadas.
