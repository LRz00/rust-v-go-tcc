#!/bin/bash

# ============================================================================
# collect_environment.sh
#
# Coleta informações de ambiente (SO, kernel, Docker, Go, Rust, wrk,
# Postgres, governor de CPU, GOMAXPROCS/GOGC, cgroup, THP) e gera um
# Apêndice em Markdown pronto para colar no TCC.
#
# Uso:
#   chmod +x collect_environment.sh
#   ./collect_environment.sh
#
# Requer os serviços rodando via `docker compose up -d` para inspecionar
# valores efetivos dentro dos containers (GOMAXPROCS, versão do Go/Rust
# usada no build, etc). Se os containers não estiverem rodando, o script
# ainda funciona, mas pula essas checagens e avisa.
# ============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_FILE="$SCRIPT_DIR/AMBIENTE_EXECUCAO.md"

DOCKER_CMD=(docker)
detect_docker_cmd() {
    if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
        DOCKER_CMD=(docker)
        return 0
    fi
    if command -v sudo >/dev/null 2>&1; then
        DOCKER_CMD=(sudo docker)
        return 0
    fi
    DOCKER_CMD=()
}

# Executa um comando e retorna a saída, ou "N/A (erro)" em caso de falha
safe_run() {
    local cmd="$1"
    local result
    result=$(eval "$cmd" 2>/dev/null)
    if [ -z "$result" ]; then
        echo "N/A (comando não disponível ou sem saída)"
    else
        echo "$result"
    fi
}

detect_docker_cmd
COMPOSE_RUNNING=0
if [ ${#DOCKER_CMD[@]} -gt 0 ]; then
    if "${DOCKER_CMD[@]}" compose ps --status running 2>/dev/null | grep -q "tcc_"; then
        COMPOSE_RUNNING=1
    fi
fi

echo "Coletando informações de ambiente..."
echo "Serviços Docker Compose rodando: $([ "$COMPOSE_RUNNING" -eq 1 ] && echo sim || echo não)"
echo ""

# ----------------------------------------------------------------------
# Hardware / SO / Kernel
# ----------------------------------------------------------------------
CPU_MODEL=$(safe_run "lscpu | grep 'Model name' | sed 's/Model name:\s*//'")
CPU_CORES=$(safe_run "nproc")
LSCPU_FULL=$(safe_run "lscpu")

OS_INFO=$(safe_run "lsb_release -a 2>/dev/null || cat /etc/os-release")
KERNEL_VERSION=$(safe_run "uname -r")
UNAME_FULL=$(safe_run "uname -a")

# Governor de CPU (todos os núcleos)
GOVERNORS=$(safe_run "cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u | tr '\n' ' '")
GOVERNORS_AVAILABLE=$(safe_run "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor_available 2>/dev/null; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null")

# THP
THP_STATUS=$(safe_run "cat /sys/kernel/mm/transparent_hugepage/enabled")

# Virtualização
VIRT_STATUS=$(safe_run "systemd-detect-virt")

# ----------------------------------------------------------------------
# Docker / Compose / cgroup
# ----------------------------------------------------------------------
DOCKER_VERSION="N/A (docker não acessível)"
COMPOSE_VERSION="N/A (docker não acessível)"
DOCKER_SERVER_VERSION="N/A"
STORAGE_DRIVER="N/A"
CGROUP_INFO="N/A"

if [ ${#DOCKER_CMD[@]} -gt 0 ]; then
    DOCKER_VERSION=$(safe_run "${DOCKER_CMD[*]} --version")
    COMPOSE_VERSION=$(safe_run "${DOCKER_CMD[*]} compose version")
    DOCKER_SERVER_VERSION=$(safe_run "${DOCKER_CMD[*]} info --format '{{.ServerVersion}}'")
    STORAGE_DRIVER=$(safe_run "${DOCKER_CMD[*]} info 2>/dev/null | grep -i 'storage driver'")
    CGROUP_INFO=$(safe_run "${DOCKER_CMD[*]} info 2>/dev/null | grep -i cgroup")
fi

# ----------------------------------------------------------------------
# Go (host e, se possível, dentro do container/imagem de build)
# ----------------------------------------------------------------------
GO_VERSION_HOST=$(safe_run "go version")
GO_VERSION_DOCKERFILE=$(safe_run "grep -m1 '^FROM' '$SCRIPT_DIR/go-api/Dockerfile'")
GO_MOD_VERSION=$(safe_run "grep '^go ' '$SCRIPT_DIR/go-api/go.mod'")
GO_SUM_PQ=$(safe_run "grep 'lib/pq' '$SCRIPT_DIR/go-api/go.sum' | head -1")

GOMAXPROCS_EFFECTIVE="N/A (containers não estão rodando)"
GOGC_EFFECTIVE="N/A (containers não estão rodando)"
if [ "$COMPOSE_RUNNING" -eq 1 ]; then
    GOMAXPROCS_EFFECTIVE=$(safe_run "${DOCKER_CMD[*]} compose exec -T go-api sh -c 'echo \${GOMAXPROCS:-<não setado, runtime decide automaticamente>}'")
    GOGC_EFFECTIVE=$(safe_run "${DOCKER_CMD[*]} compose exec -T go-api sh -c 'echo \${GOGC:-<não setado, padrão=100>}'")
fi

# ----------------------------------------------------------------------
# Rust / Cargo (host e Dockerfile)
# ----------------------------------------------------------------------
RUST_VERSION_HOST=$(safe_run "rustc --version")
CARGO_VERSION_HOST=$(safe_run "cargo --version")
RUST_VERSION_DOCKERFILE=$(safe_run "grep -m1 '^FROM' '$SCRIPT_DIR/rust-api/Dockerfile'")

CARGO_LOCK_PATH="$SCRIPT_DIR/rust-api/Cargo.lock"
CARGO_LOCK_STATUS="AUSENTE — recomenda-se gerar e commitar (rodar 'cargo build' dentro de rust-api/ e commitar Cargo.lock)"
ACTIX_VERSION="N/A"
TOKIO_VERSION="N/A"
TOKIO_PG_VERSION="N/A"
DEADPOOL_VERSION="N/A"
if [ -f "$CARGO_LOCK_PATH" ]; then
    CARGO_LOCK_STATUS="presente"
    ACTIX_VERSION=$(safe_run "grep -A1 'name = \"actix-web\"' '$CARGO_LOCK_PATH' | grep version")
    TOKIO_VERSION=$(safe_run "grep -A1 '^name = \"tokio\"$' '$CARGO_LOCK_PATH' | grep version")
    TOKIO_PG_VERSION=$(safe_run "grep -A1 'name = \"tokio-postgres\"' '$CARGO_LOCK_PATH' | grep version")
    DEADPOOL_VERSION=$(safe_run "grep -A1 'name = \"deadpool-postgres\"' '$CARGO_LOCK_PATH' | grep version")
fi

CARGO_PROFILE=$(safe_run "grep -A5 '\[profile' '$SCRIPT_DIR/rust-api/Cargo.toml'")
[ "$CARGO_PROFILE" = "N/A (comando não disponível ou sem saída)" ] && CARGO_PROFILE="Nenhum profile customizado — usa o padrão do Cargo para --release (opt-level = 3, lto = false)"

RUST_VERSION_CONTAINER="N/A (containers não estão rodando)"
if [ "$COMPOSE_RUNNING" -eq 1 ]; then
    RUST_VERSION_CONTAINER=$(safe_run "${DOCKER_CMD[*]} compose exec -T rust-api /usr/local/bin/rust-api --version 2>/dev/null || echo '<binário não expõe --version; ver GO_VERSION_DOCKERFILE/RUST_VERSION_DOCKERFILE como referência de build>'")
fi

# ----------------------------------------------------------------------
# wrk
# ----------------------------------------------------------------------
WRK_VERSION=$(safe_run "wrk --version 2>&1 | head -3")
WRK_APT=$(safe_run "apt list --installed 2>/dev/null | grep -i wrk")

# ----------------------------------------------------------------------
# Postgres
# ----------------------------------------------------------------------
POSTGRES_IMAGE=$(safe_run "grep -A1 'postgres:' '$SCRIPT_DIR/docker-compose.yml' | grep image")
POSTGRES_MAXCONN=$(safe_run "grep 'max_connections' '$SCRIPT_DIR/docker-compose.yml'")

# ----------------------------------------------------------------------
# Sistema no momento da coleta (baseline de "máquina dedicada")
# ----------------------------------------------------------------------
UPTIME_LOAD=$(safe_run "uptime")
LOGGED_USERS=$(safe_run "who")
TOP_CPU_PROCS=$(safe_run "ps aux --sort=-%cpu | head -6")
ACTIVE_TIMERS=$(safe_run "systemctl list-timers --all 2>/dev/null | head -15")

# ============================================================================
# Geração do arquivo Markdown
# ============================================================================

cat > "$OUT_FILE" <<EOF
# Apêndice — Ambiente de Execução

> Documento gerado automaticamente por \`collect_environment.sh\` em
> $(date --rfc-3339=seconds).
> Revisar valores marcados como "N/A" manualmente antes de incluir no TCC.

## Hardware e Sistema Operacional

- **CPU:** ${CPU_MODEL}
- **Núcleos lógicos:** ${CPU_CORES}
- **Governor de CPU ativo:** ${GOVERNORS}
- **Governors disponíveis no hardware:** ${GOVERNORS_AVAILABLE}
- **Transparent Huge Pages:** ${THP_STATUS}
- **Virtualização detectada:** ${VIRT_STATUS} (esperado: \`none\` para máquina física dedicada)
- **Kernel:** ${KERNEL_VERSION}
- **uname -a completo:** \`${UNAME_FULL}\`

<details>
<summary>Saída completa de <code>lsb_release -a</code> / <code>/etc/os-release</code></summary>

\`\`\`
${OS_INFO}
\`\`\`
</details>

<details>
<summary>Saída completa de <code>lscpu</code> (verificar hyperthreading/SMT)</summary>

\`\`\`
${LSCPU_FULL}
\`\`\`
</details>

## Containerização

- **Docker (cliente):** ${DOCKER_VERSION}
- **Docker (servidor/daemon):** ${DOCKER_SERVER_VERSION}
- **Docker Compose:** ${COMPOSE_VERSION}
- **Storage driver:** ${STORAGE_DRIVER}
- **Cgroup:** ${CGROUP_INFO}

## Go

- **Versão do compilador (host):** ${GO_VERSION_HOST}
- **Imagem de build usada no Dockerfile:** \`${GO_VERSION_DOCKERFILE}\`
  *(esta é a versão autoritativa — é a que efetivamente compila o binário testado)*
- **Versão declarada em go.mod:** ${GO_MOD_VERSION}
- **Driver PostgreSQL (go.sum):** ${GO_SUM_PQ}
- **GOMAXPROCS efetivo no container:** ${GOMAXPROCS_EFFECTIVE}
- **GOGC efetivo no container:** ${GOGC_EFFECTIVE}
- **Flags de build:** \`go build -o go-api\` (sem otimizações customizadas — ver Limitação #4)

## Rust

- **Versão do compilador (host):** ${RUST_VERSION_HOST}
- **Cargo (host):** ${CARGO_VERSION_HOST}
- **Imagem de build usada no Dockerfile:** \`${RUST_VERSION_DOCKERFILE}\`
  *(⚠️ se aparecer \`rust:latest\`, RECOMENDA-SE FIXAR uma tag antes da coleta
  final — ver observação abaixo)*
- **Cargo.lock:** ${CARGO_LOCK_STATUS}
- **actix-web (via Cargo.lock):** ${ACTIX_VERSION}
- **tokio (via Cargo.lock):** ${TOKIO_VERSION}
- **tokio-postgres (via Cargo.lock):** ${TOKIO_PG_VERSION}
- **deadpool-postgres (via Cargo.lock):** ${DEADPOOL_VERSION}
- **Profile de build:** ${CARGO_PROFILE}
- **Versão dentro do container (se disponível):** ${RUST_VERSION_CONTAINER}

> ⚠️ **Ação recomendada:** se \`RUST_VERSION_DOCKERFILE\` acima mostrar
> \`rust:latest\`, edite \`rust-api/Dockerfile\` para fixar uma tag exata
> (ex: \`rust:1.83-bookworm\`) e faça rebuild antes da coleta final, para
> que o build não mude silenciosamente entre execuções em datas diferentes.
> Da mesma forma, confirme se \`rust-api/Cargo.lock\` está commitado no
> repositório (\`git status rust-api/Cargo.lock\`) — sem ele, versões de
> dependências transitivas podem variar entre builds.

## Gerador de Carga (wrk)

- **wrk --version:** ${WRK_VERSION}
- **wrk via apt (se aplicável):** ${WRK_APT}

> Se wrk foi compilado do source, anote o commit usado:
> \`cd <pasta do wrk> && git log -1 --format="%H %ai"\`

## Banco de Dados

- **Imagem Postgres:** ${POSTGRES_IMAGE}
- **max_connections:** ${POSTGRES_MAXCONN}

## Baseline de Ambiente Dedicado (coletado no momento desta execução)

- **Load average (uptime):** ${UPTIME_LOAD}
- **Usuários logados:** 
\`\`\`
${LOGGED_USERS}
\`\`\`

<details>
<summary>Top 5 processos por uso de CPU no momento da coleta</summary>

\`\`\`
${TOP_CPU_PROCS}
\`\`\`
</details>

<details>
<summary>Timers systemd ativos (verificar automações que podem interferir, ex: apt-daily.timer)</summary>

\`\`\`
${ACTIVE_TIMERS}
\`\`\`
</details>

---

## Checklist de ações antes da coleta final (Fase 10 do plano de implementação)

- [ ] Governor de CPU fixado em \`performance\` em todos os núcleos
      (\`sudo cpupower frequency-set -g performance\`)
- [ ] \`rust-api/Dockerfile\` usa tag fixa (não \`rust:latest\`)
- [ ] \`rust-api/Cargo.lock\` commitado no repositório
- [ ] \`GOMAXPROCS\` fixado explicitamente no \`docker-compose.yml\`,
      alinhado ao \`cpuset\` definido para o serviço \`go-api\`
- [ ] Timers de atualização automática do sistema suspensos durante a
      janela de execução (\`apt-daily.timer\`, etc.)
- [ ] \`sar\`/\`vmstat\` configurado para monitorar a execução completa
- [ ] Nenhum outro usuário logado / processos pesados concorrentes
      confirmados ausentes imediatamente antes de iniciar

EOF

echo ""
echo "✓ Apêndice gerado em: $OUT_FILE"
echo ""
if [ "$COMPOSE_RUNNING" -eq 0 ]; then
    echo "⚠️  Os serviços Docker Compose não estavam rodando durante a coleta."
    echo "   Campos de GOMAXPROCS/GOGC efetivos e versão do Rust no container"
    echo "   ficaram como N/A. Rode 'docker compose up -d' e execute este"
    echo "   script novamente para preencher esses campos."
fi
