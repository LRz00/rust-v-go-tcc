# Guia Rápido de Início

Este guia permite que você execute os experimentos em menos de 5 minutos.

## Pré-requisitos

Certifique-se de ter instalado:

```bash
# Docker e Docker Compose
docker --version
docker compose version

# wrk (ferramenta de benchmark)
wrk --version

# Python 3
python3 --version
```

### Instalar wrk (se necessário)

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y wrk

# macOS
brew install wrk

# Outros (compilar do source)
git clone https://github.com/wg/wrk.git && cd wrk && make && sudo cp wrk /usr/local/bin/
```

---

## Execução em 3 Passos

### 1. Iniciar os serviços

```bash
cd /home/amp/Documents/tcc
docker compose up --build
```

Aguarde ver as mensagens:
- ✓ `Rust API listening on 0.0.0.0:8080`
- ✓ `Go API listening on :8080`

**Dica:** Em outro terminal, você pode verificar o status:

```bash
docker compose ps
```

Todos os serviços devem estar `healthy` (ou `running` se não tiver healthcheck).

---

### 2. Executar benchmark

Em um **novo terminal**:

```bash
cd /home/amp/Documents/tcc
./benchmark.sh
```

**O que acontece:**
- Testa 2 endpoints: `/days-since` (normal) e `/days-since-heavy` (allocation-heavy)
- Para cada endpoint, testa 6 cenários de carga (10, 50, 100, 200, 500, 1000 conexões)
- Para cada cenário, testa Go e Rust
- Cada teste dura 60 segundos
- **Total de testes:** 24 (2 endpoints × 6 cenários × 2 linguagens)
- **Tempo total:** ~24-30 minutos

**Durante a execução:**
- Você verá barras de progresso do wrk
- Métricas são coletadas antes e depois de cada teste
- Resultados salvos em `benchmark_results/YYYYMMDD_HHMMSS/`

---

### 3. Analisar resultados

Após o benchmark terminar:

```bash
python3 analyze_results.py
```

**O que você verá:**
- Tabela comparativa Go vs Rust
- Insights relacionados às hipóteses H1-H4
- Identificação de pontos de saturação
- Análise de uso de memória

**Output salvo em:**
- `benchmark_results/YYYYMMDD_HHMMSS/analysis.json`

---

## Verificação Rápida (antes do benchmark completo)

### Teste manual dos endpoints

```bash
# Go API
curl http://localhost:8080/health
# Esperado: OK

curl http://localhost:8080/days-since
# Esperado: {"days_since": 18993}

curl http://localhost:8080/days-since-heavy
# Esperado: {"days_since": 18993, "checksum": 2560}

curl http://localhost:8080/metrics | jq
# Esperado: JSON com métricas de Go

# Rust API
curl http://localhost:8081/health
# Esperado: OK

curl http://localhost:8081/days-since
# Esperado: {"days_since": 18993}

curl http://localhost:8081/days-since-heavy
# Esperado: {"days_since": 18993, "checksum": 2560}

curl http://localhost:8081/metrics | jq
# Esperado: JSON com métricas de Rust
```

### Teste rápido de carga (30 segundos)

```bash
# Go
wrk -t2 -c10 -d30s http://localhost:8080/days-since

# Rust
wrk -t2 -c10 -d30s http://localhost:8081/days-since
```

Se tudo funcionar, você está pronto para o benchmark completo!

---

## Estrutura de Pastas Após Execução

```
/home/amp/Documents/tcc/
├── benchmark_results/
│   └── 20260307_143000/          # Timestamp da sua execução
│       ├── go_c10/                # Resultados Go, 10 conexões
│       │   ├── test_config.json
│       │   ├── wrk_output.txt
│       │   ├── wrk_summary.json
│       │   ├── metrics_before.json
│       │   └── metrics_after.json
│       ├── rust_c10/              # Resultados Rust, 10 conexões
│       ├── go_c50/, rust_c50/     # Outros cenários...
│       ├── summary.txt            # Resumo do benchmark.sh
│       └── analysis.json          # Análise do Python
├── go-api/
├── rust-api/
├── benchmark.sh
├── analyze_results.py
└── ...
```

---

## Comandos Úteis

### Visualizar logs em tempo real

```bash
# Todos os serviços
docker compose logs -f

# Apenas Go
docker compose logs -f go-api

# Apenas Rust
docker compose logs -f rust-api
```

### Reiniciar tudo

```bash
docker compose down
docker compose up --build
```

### Limpar resultados antigos

```bash
rm -rf benchmark_results/
```

### Limpar containers e volumes

```bash
docker compose down -v
```

---

## Troubleshooting Rápido

### Porta já em uso

```bash
# Descobrir o que está usando a porta
sudo lsof -i :8080
sudo lsof -i :8081

# Parar o processo
docker compose down
```

### Erro "wrk: command not found"

```bash
sudo apt install wrk
```

### Erro "docker: command not found"

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### APIs não conectam ao Postgres

```bash
# Verificar se Postgres está healthy
docker compose ps

# Ver logs do Postgres
docker compose logs postgres

# Reiniciar com volumes limpos
docker compose down -v
docker compose up --build
```

### Benchmark.sh não executa

```bash
# Tornar executável
chmod +x benchmark.sh

# Executar explicitamente
bash benchmark.sh
```

---

## Próximos Passos

Após executar o benchmark básico:

1. **Ler os resultados:**
   - Abra `benchmark_results/YYYYMMDD_HHMMSS/analysis.json`
   - Revise `summary.txt`
   - Compare `metrics_before.json` vs `metrics_after.json`

2. **Adicionar cenário allocation-heavy:**
   - Siga o guia em `ALLOCATION_HEAVY_GUIDE.md`
   - Re-execute o benchmark
   - Compare resultados normal vs heavy

3. **Análise estatística:**
   - Execute múltiplas repetições
   - Calcule intervalos de confiança
   - Aplique testes de significância

4. **Visualizações:**
   - Crie gráficos de latência vs conexões
   - Plote crescimento de memória
   - Compare throughput Go vs Rust

---

## Checklist para Resultados Válidos

- [ ] Todas as APIs responderam aos testes
- [ ] Sem erros HTTP (timeouts, 5xx)
- [ ] Métricas coletadas antes e depois de cada teste
- [ ] Análise Python executou sem erros
- [ ] Resultados salvos com timestamp correto
- [ ] Nenhum processo externo consumindo muita CPU durante os testes

