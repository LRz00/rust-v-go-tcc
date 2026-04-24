#!/bin/bash

# ============================================================================
# BENCHMARK REPLICADO: Executa benchmark.sh N vezes
# Descarta primeiras WARMUP replicações para steady-state
# ============================================================================

set -e

# CONFIGURAÇÕES
NUM_REPLICATES=30
WARMUP_REPLICATES=5
ANALYSIS_REPLICATES=$((NUM_REPLICATES - WARMUP_REPLICATES))

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_BENCHMARK="$SCRIPT_DIR/benchmark.sh"
ORIGINAL_RESULTS_DIR="$SCRIPT_DIR/benchmark_results"

RESULTS_DIR="$SCRIPT_DIR/benchmark_results_replicated"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$RESULTS_DIR/$TIMESTAMP"

GO_URL="http://localhost:8080"
RUST_URL="http://localhost:8081"

DOCKER_CMD=(docker)

detect_docker_cmd() {
    if command -v docker >/dev/null 2>&1; then
        if docker ps >/dev/null 2>&1; then
            DOCKER_CMD=(docker)
            return 0
        fi
    fi

    if command -v sudo >/dev/null 2>&1; then
        DOCKER_CMD=(sudo docker)
        return 0
    fi

    echo "ERRO: não foi possível executar 'docker' (sem permissão) e 'sudo' não está disponível." >&2
    echo "Dica: execute o script com sudo, ou adicione seu usuário ao grupo docker." >&2
    exit 1
}

setup_results_dir() {
    mkdir -p "$RUN_DIR/warmup" "$RUN_DIR/analysis" "$RUN_DIR/logs"
    echo "Resultados serão salvos em: $RUN_DIR"
}

check_services() {
    echo "Verificando disponibilidade dos serviços..."

    for i in {1..30}; do
        local go_ok=0
        local rust_ok=0

        if curl -sS "$GO_URL/health" > /dev/null 2>&1; then
            go_ok=1
        fi
        if curl -sS "$RUST_URL/health" > /dev/null 2>&1; then
            rust_ok=1
        fi

        if [ "$go_ok" -eq 1 ] && [ "$rust_ok" -eq 1 ]; then
            echo "✓ APIs online"
            return 0
        fi

        echo "  Tentativa $i/30... (go=$go_ok rust=$rust_ok)"
        sleep 2
    done

    echo "ERRO: APIs não responderam após 60 segundos"
    exit 1
}

find_latest_original_run() {
    if [ ! -d "$ORIGINAL_RESULTS_DIR" ]; then
        return 1
    fi

    find "$ORIGINAL_RESULTS_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
        | sort -nr \
        | head -1 \
        | cut -d' ' -f2-
}

run_one_replicate() {
    local replicate=$1
    local category="analysis"

    if [ "$replicate" -le "$WARMUP_REPLICATES" ]; then
        category="warmup"
    fi

    local rep_dir="$RUN_DIR/$category/rep${replicate}"
    local log_file="$RUN_DIR/logs/rep${replicate}.log"
    mkdir -p "$rep_dir"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ "$category" = "warmup" ]; then
        echo "REPLICAÇÃO $replicate/$NUM_REPLICATES (WARM-UP - será descartada)"
    else
        echo "REPLICAÇÃO $replicate/$NUM_REPLICATES (ANÁLISE)"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local before_latest
    before_latest=$(find_latest_original_run || true)

    # Envia ENTER automático para o prompt do benchmark.sh
    printf '\n' | bash "$ORIGINAL_BENCHMARK" | tee "$log_file"

    local source_dir
    source_dir=$(grep -E "Resultados disponíveis em:" "$log_file" | tail -1 | sed 's/.*Resultados disponíveis em: //')

    if [ -n "$source_dir" ] && [ -d "$SCRIPT_DIR/$source_dir" ]; then
        source_dir="$SCRIPT_DIR/$source_dir"
    fi

    if [ -z "$source_dir" ] || [ ! -d "$source_dir" ]; then
        source_dir=$(find_latest_original_run || true)
    fi

    if [ -z "$source_dir" ] || [ ! -d "$source_dir" ]; then
        echo "ERRO: não foi possível localizar resultados gerados pela replicação $replicate"
        exit 1
    fi

    if [ -n "$before_latest" ] && [ "$source_dir" = "$before_latest" ]; then
        echo "ERRO: nenhum novo diretório de resultado foi detectado na replicação $replicate"
        exit 1
    fi

    mv "$source_dir" "$rep_dir/run"
    echo "✓ Replicação $replicate arquivada em: $rep_dir/run"
}

# ============================================================================
# MAIN
# ============================================================================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK REPLICADO: $NUM_REPLICATES rodadas                 ║"
echo "║  (Primeiras $WARMUP_REPLICATES = warm-up, últimas $ANALYSIS_REPLICATES = análise) ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ ! -f "$ORIGINAL_BENCHMARK" ]; then
    echo "ERRO: benchmark original não encontrado em $ORIGINAL_BENCHMARK"
    exit 1
fi

setup_results_dir

detect_docker_cmd

echo "Iniciando serviços..."
if ! "${DOCKER_CMD[@]}" compose up -d --build; then
    echo "ERRO: falha ao iniciar serviços via Docker Compose." >&2
    echo "Comando: ${DOCKER_CMD[*]} compose up -d --build" >&2
    exit 1
fi

echo "Aguardando inicialização..."
sleep 10

check_services

for replicate in $(seq 1 "$NUM_REPLICATES"); do
    run_one_replicate "$replicate"

    if [ "$replicate" -lt "$NUM_REPLICATES" ]; then
        echo ""
        echo "Aguardando estabilização entre replicações (30s)..."
        sleep 30
    fi
done

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK CONCLUÍDO!                                          ║"
echo "║  Resultados em: $RUN_DIR"
echo "║  Warm-up replicações: 1-$WARMUP_REPLICATES (descarte)"
echo "║  Análise replicações: $((WARMUP_REPLICATES+1))-$NUM_REPLICATES (use estas)"
echo "╚════════════════════════════════════════════════════════════════╝"