# Mudança: Configuração de Pool de Conexões e Cenários de Carga

## Contexto

Durante a execução inicial do benchmark, os logs do PostgreSQL apresentaram repetidamente o erro:

```
FATAL: sorry, too many clients already
```

Esse erro indica que o banco de dados estava recusando novas conexões por ter atingido seu limite máximo. A investigação revelou um problema estrutural na configuração do experimento que comprometia a validade dos resultados em cenários de alta carga.

---

## Diagnóstico

### Configuração original

| Componente | Parâmetro | Valor original |
|---|---|---|
| PostgreSQL | `max_connections` | 100 (padrão) |
| Go API | `SetMaxOpenConns` | 50 |
| Rust API | `deadpool max_size` | 50 |

O total de conexões possíveis entre as duas APIs (100) já esgotava o limite padrão do PostgreSQL. Nos cenários com 500 e 1000 conexões simultâneas no wrk, cada requisição concorrente tentava adquirir uma conexão do pool. Com o pool esgotado, as requisições aguardavam em fila — mas o PostgreSQL frequentemente recusava novas conexões antes mesmo de o pool local gerenciar a espera, gerando os erros observados.

### Por que os cenários de 500 e 1000 conexões eram inválidos

Mesmo com o limite do PostgreSQL aumentado, manter 500 conexões no wrk contra um pool de 50 por API significa que a grande maioria das requisições passa a maior parte do tempo aguardando na fila interna do pool, não executando de fato. O que se mediria nesse cenário não seria a capacidade da linguagem de lidar com concorrência, mas sim o comportamento de fila sob contenção de recurso externo — uma variável que não diferencia Go de Rust de forma relevante para as hipóteses do estudo.

Em outras palavras: **os resultados dos cenários de 500 e 1000 conexões refletiam o comportamento do pool de banco de dados, não das linguagens**.

---

## Mudanças aplicadas

### 1. `docker-compose.yml` — limite do PostgreSQL

```yaml
# Antes
postgres:
  image: postgres:16

# Depois
postgres:
  image: postgres:16
  command: postgres -c max_connections=300
```

### 2. `go-api/main.go` — tamanho do pool

```go
// Antes
db.SetMaxOpenConns(50)
db.SetMaxIdleConns(10)

// Depois
db.SetMaxOpenConns(25)
db.SetMaxIdleConns(5)
```

### 3. `rust-api/src/main.rs` — tamanho do pool

```rust
// Antes
cfg.pool = Some(PoolConfig {
    max_size: 50,
    ..Default::default()
});

// Depois
cfg.pool = Some(PoolConfig {
    max_size: 25,
    ..Default::default()
});
```

### 4. `benchmark.sh` — cenários de carga

```bash
# Antes
SCENARIOS=(10 50 100 200 500 1000)

# Depois
SCENARIOS=(10 25 50 100 200 400)
```

---

## Justificativa dos novos cenários

Com pool de 25 conexões por API, o ponto de saturação do pool ocorre exatamente nos 25 primeiros clientes simultâneos. Os cenários acima desse valor exercem pressão progressiva de fila, que é o comportamento relevante para avaliar escalabilidade.

| Conexões wrk | Relação com pool (25) | O que se observa |
|---|---|---|
| 10 | Abaixo do pool | Comportamento sem contenção, baseline |
| 25 | No limite do pool | Início de contenção |
| 50 | 2× o pool | Pressão moderada de fila |
| 100 | 4× o pool | Pressão alta, diferenças de scheduler visíveis |
| 200 | 8× o pool | Alta carga, saturação esperada |
| 400 | 16× o pool | Carga extrema, curva de degradação |

O teto de 400 conexões é suficiente para revelar diferenças no comportamento de escalabilidade entre Go (goroutines + scheduler cooperativo) e Rust (async/await + tokio), que é o que as hipóteses H2 e H3 propõem investigar.

Os cenários originais de 500 e 1000 conexões foram removidos pois, nessa faixa, o gargalo dominante passa a ser o gerenciamento do pool de banco de dados — um comportamento comum às duas linguagens que obscurece as diferenças de design que o experimento pretende medir.

---

## Impacto na validade do experimento

### Dados anteriores

Os resultados coletados nos cenários de 500 e 1000 conexões antes dessa mudança devem ser descartados. Eles não representam o comportamento das linguagens sob carga, mas sim o comportamento do sistema sob exaustão de recurso externo. Os demais cenários (10 a 200 conexões) podem ser reaproveitados se não apresentarem erros HTTP nos arquivos `wrk_output.txt`.

### Variável de controle adicionada

A padronização do tamanho de pool (25 conexões por API) cria uma variável de controle explícita que antes estava implicitamente desequilibrada. Isso deve ser documentado na seção de metodologia do TCC como garantia de comparabilidade entre as implementações.

### Impacto nas hipóteses

| Hipótese | Impacto |
|---|---|
| H1 — Tail latency sob pressão de alocação | Neutro. Os cenários de 10 a 200 conexões são suficientes para observar diferenças de p99. |
| H2 — Throughput em carga moderada | Neutro. O intervalo até 100 conexões permanece inalterado. |
| H3 — Ponto de saturação | Positivo. Os novos cenários revelam a curva de degradação de forma mais limpa, sem o ruído da exaustão do banco. |
| H4 — Uso de memória | Neutro. O comportamento de heap e RSS é independente do número de cenários. |

---

## Recomendação para o texto do TCC

Na seção de metodologia, registrar essa decisão da seguinte forma:

> O tamanho do pool de conexões foi padronizado em 25 conexões por API (Go e Rust), com o PostgreSQL configurado para aceitar até 300 conexões simultâneas. Os cenários de carga foram definidos em 10, 25, 50, 100, 200 e 400 conexões simultâneas. Cenários acima de 400 conexões foram descartados após constatação de que, nessa faixa, o gargalo dominante passa a ser o pool de banco de dados e não o modelo de concorrência da linguagem — o que introduziria uma variável confundidora não relacionada às hipóteses do estudo.
