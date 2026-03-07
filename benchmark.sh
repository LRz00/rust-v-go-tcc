#!/bin/bash

# Script de benchmark para comparação Go vs Rust
# Coleta métricas de latência (p95, p99), throughput, uso de memória e CPU
# Gera resultados em JSON estruturado para análise

set -e

# Configurações
RESULTS_DIR="benchmark_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
GO_URL="http://localhost:8080"
RUST_URL="http://localhost:8081"
WRK_THREADS=4
DURATION="60s"

# Cenários de carga progressivos (conexões simultâneas)
SCENARIOS=(10 50 100 200 500 1000)

# Função para criar diretório de resultados
setup_results_dir() {
    mkdir -p "$RESULTS_DIR/$TIMESTAMP"
    echo "Resultados serão salvos em: $RESULTS_DIR/$TIMESTAMP"
}

# Função para verificar se serviços estão rodando
check_services() {
    echo "Verificando disponibilidade dos serviços..."
    
    if ! curl -s "$GO_URL/health" > /dev/null; then
        echo "ERRO: API Go não está respondendo em $GO_URL"
        exit 1
    fi
    echo "✓ API Go online"
    
    if ! curl -s "$RUST_URL/health" > /dev/null; then
        echo "ERRO: API Rust não está respondendo em $RUST_URL"
        exit 1
    fi
    echo "✓ API Rust online"
    echo ""
}

# Função para coletar métricas do serviço
collect_metrics() {
    local url=$1
    local output_file=$2
    curl -s "$url/metrics" > "$output_file" 2>/dev/null || echo "{\"error\": \"failed to collect metrics\"}" > "$output_file"
}

# Função para esperar estabilização
wait_stabilize() {
    echo "Aguardando estabilização (10s)..."
    sleep 10
}

# Função para parsear resultados do wrk
parse_wrk_output() {
    local wrk_output=$1
    local output_json=$2
    
    # Extrai métricas do wrk usando awk/grep
    local latency_avg=$(echo "$wrk_output" | grep "Latency" | awk '{print $2}')
    local latency_stdev=$(echo "$wrk_output" | grep "Latency" | awk '{print $3}')
    local latency_max=$(echo "$wrk_output" | grep "Latency" | awk '{print $4}')
    
    local req_sec=$(echo "$wrk_output" | grep "Req/Sec" | awk '{print $2}')
    local req_stdev=$(echo "$wrk_output" | grep "Req/Sec" | awk '{print $3}')
    local req_max=$(echo "$wrk_output" | grep "Req/Sec" | awk '{print $4}')
    
    local total_requests=$(echo "$wrk_output" | grep "requests in" | awk '{print $1}')
    local total_time=$(echo "$wrk_output" | grep "requests in" | awk '{print $3}')
    local total_read=$(echo "$wrk_output" | grep "Transfer/sec:" | awk '{print $2}')
    
    local errors=$(echo "$wrk_output" | grep -i "Socket errors\|Non-2xx" || echo "0")
    
    # Cria JSON estruturado
    cat > "$output_json" <<EOF
{
    "latency": {
        "avg": "$latency_avg",
        "stdev": "$latency_stdev",
        "max": "$latency_max"
    },
    "requests_per_sec": {
        "avg": "$req_sec",
        "stdev": "$req_stdev",
        "max": "$req_max"
    },
    "total": {
        "requests": "$total_requests",
        "duration": "$total_time",
        "transfer": "$total_read"
    },
    "errors": "$errors"
}
EOF
}

# Função principal de benchmark para uma API
run_benchmark() {
    local lang=$1
    local url=$2
    local connections=$3
    local run_dir="$RESULTS_DIR/$TIMESTAMP/${lang}_c${connections}"
    
    mkdir -p "$run_dir"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[$lang] Testando com $connections conexões"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Coleta métricas PRÉ-teste
    echo "Coletando métricas iniciais..."
    collect_metrics "$url" "$run_dir/metrics_before.json"
    
    # Executa wrk e salva output completo
    echo "Executando wrk (threads=$WRK_THREADS, connections=$connections, duration=$DURATION)..."
    local wrk_output=$(wrk -t$WRK_THREADS -c$connections -d$DURATION --latency "$url/days-since" 2>&1)
    echo "$wrk_output" > "$run_dir/wrk_output.txt"
    
    # Parseia resultados
    parse_wrk_output "$wrk_output" "$run_dir/wrk_summary.json"
    
    # Aguarda estabilização
    wait_stabilize
    
    # Coleta métricas PÓS-teste
    echo "Coletando métricas finais..."
    collect_metrics "$url" "$run_dir/metrics_after.json"
    
    # Salva configuração do teste
    cat > "$run_dir/test_config.json" <<EOF
{
    "language": "$lang",
    "url": "$url",
    "connections": $connections,
    "threads": $WRK_THREADS,
    "duration": "$DURATION",
    "timestamp": "$(date --rfc-3339=seconds)"
}
EOF
    
    echo "✓ Teste concluído. Resultados em: $run_dir"
    echo ""
}

# Função para benchmark do cenário allocation-heavy
run_benchmark_heavy() {
    local lang=$1
    local url=$2
    local connections=$3
    local run_dir="$RESULTS_DIR/$TIMESTAMP/${lang}_heavy_c${connections}"
    
    mkdir -p "$run_dir"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "[$lang HEAVY] Testando com $connections conexões"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Coleta métricas PRÉ-teste
    echo "Coletando métricas iniciais..."
    collect_metrics "$url" "$run_dir/metrics_before.json"
    
    # Executa wrk no endpoint heavy
    echo "Executando wrk no endpoint allocation-heavy..."
    local wrk_output=$(wrk -t$WRK_THREADS -c$connections -d$DURATION --latency "$url/days-since-heavy" 2>&1)
    echo "$wrk_output" > "$run_dir/wrk_output.txt"
    
    parse_wrk_output "$wrk_output" "$run_dir/wrk_summary.json"
    
    wait_stabilize
    
    # Coleta métricas PÓS-teste
    echo "Coletando métricas finais..."
    collect_metrics "$url" "$run_dir/metrics_after.json"
    
    cat > "$run_dir/test_config.json" <<EOF
{
    "language": "$lang",
    "url": "$url",
    "endpoint": "/days-since-heavy",
    "connections": $connections,
    "threads": $WRK_THREADS,
    "duration": "$DURATION",
    "timestamp": "$(date --rfc-3339=seconds)"
}
EOF
    
    echo "✓ Teste heavy concluído. Resultados em: $run_dir"
    echo ""
}

# Função para gerar relatório consolidado
generate_summary() {
    local summary_file="$RESULTS_DIR/$TIMESTAMP/summary.txt"
    
    echo "========================================" > "$summary_file"
    echo "RESUMO DO BENCHMARK - $TIMESTAMP" >> "$summary_file"
    echo "========================================" >> "$summary_file"
    echo "" >> "$summary_file"
    
    for conn in "${SCENARIOS[@]}"; do
        echo "--- Conexões: $conn ---" >> "$summary_file"
        
        if [ -f "$RESULTS_DIR/$TIMESTAMP/go_c${conn}/wrk_summary.json" ]; then
            echo "Go:" >> "$summary_file"
            cat "$RESULTS_DIR/$TIMESTAMP/go_c${conn}/wrk_summary.json" | jq -r '.latency.avg + " (avg latency), " + .requests_per_sec.avg + " (req/s)"' >> "$summary_file" 2>/dev/null || echo "N/A" >> "$summary_file"
        fi
        
        if [ -f "$RESULTS_DIR/$TIMESTAMP/rust_c${conn}/wrk_summary.json" ]; then
            echo "Rust:" >> "$summary_file"
            cat "$RESULTS_DIR/$TIMESTAMP/rust_c${conn}/wrk_summary.json" | jq -r '.latency.avg + " (avg latency), " + .requests_per_sec.avg + " (req/s)"' >> "$summary_file" 2>/dev/null || echo "N/A" >> "$summary_file"
        fi
        
        echo "" >> "$summary_file"
    done
    
    echo "Relatório consolidado gerado: $summary_file"
}

# Função principal
main() {
    echo "╔════════════════════════════════════════════════╗"
    echo "║  Benchmark TCC: Go vs Rust                     ║"
    echo "║  Análise de Desempenho e Escalabilidade       ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    
    setup_results_dir
    check_services
    
    echo "Configuração do teste:"
    echo "  - Threads: $WRK_THREADS"
    echo "  - Duração: $DURATION"
    echo "  - Cenários: ${SCENARIOS[*]} conexões"
    echo ""
    read -p "Pressione ENTER para iniciar ou Ctrl+C para cancelar..."
    echo ""
    
    # Testa cada cenário em ambas as linguagens
    for connections in "${SCENARIOS[@]}"; do
        run_benchmark "go" "$GO_URL" "$connections"
        run_benchmark "rust" "$RUST_URL" "$connections"
    done
    
    # Testa cenário allocation-heavy
    echo ""
    echo "════════════════════════════════════════════"
    echo "Testando cenário ALLOCATION-HEAVY"
    echo "════════════════════════════════════════════"
    echo ""
    
    for connections in "${SCENARIOS[@]}"; do
        run_benchmark_heavy "go" "$GO_URL" "$connections"
        run_benchmark_heavy "rust" "$RUST_URL" "$connections"
    done
    
    generate_summary
    
    echo ""
    echo "╔════════════════════════════════════════════════╗"
    echo "║  Benchmark concluído!                          ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    echo "Resultados disponíveis em: $RESULTS_DIR/$TIMESTAMP"
    echo ""
    echo "Próximos passos:"
    echo "  1. Analise os arquivos JSON em cada diretório"
    echo "  2. Compare as métricas de latência (p95/p99) se disponíveis"
    echo "  3. Observe o crescimento de memória (metrics_before vs metrics_after)"
    echo "  4. Identifique pontos de saturação nas curvas de throughput"
}

# Executa script
main
