#!/usr/bin/env python3
"""
Script de análise dos resultados do benchmark Go vs Rust
Gera visualizações e estatísticas comparativas para o TCC
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import statistics
import re


METRIC_FIELDS: Tuple[str, ...] = (
    'latency_avg_ms',
    'latency_max_ms',
    'latency_p95_ms',
    'latency_p99_ms',
    'requests_per_sec',
    'total_requests',
    'errors',
    'timeouts',
    # --- Métricas primárias
    # Comparáveis diretamente entre Go e Rust.
    'memory_before_mb',
    'memory_after_mb',
    'memory_growth_mb',
    'peak_rss_mb_before',
    'peak_rss_mb_after',
    'cgroup_current_mb_before',
    'cgroup_current_mb_after',
    'cgroup_current_mb_growth',
    'cgroup_peak_mb_before',
    'cgroup_peak_mb_after',
    'cpu_percent',
    # --- Métricas complementares (runtime_specific), não comparáveis
    # diretamente entre linguagens: Go usa heap_alloc_bytes (runtime
    # gerenciado por GC); Rust usa legacy_rss_mb (via /proc/self/statm).
    'legacy_runtime_memory_mb_before',
    'legacy_runtime_memory_mb_after',
    'legacy_runtime_memory_mb_growth',
)

def load_json(filepath: Path) -> Dict:
    """Carrega arquivo JSON"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao ler {filepath}: {e}")
        return {}

def parse_wrk_latency(latency_str: str) -> float:
    """Converte string de latência do wrk para ms"""
    if not latency_str or latency_str == "0":
        return 0.0
    
    latency_str = str(latency_str).strip()
    
    # Remove whitespace
    latency_str = latency_str.strip()
    
    try:
        if latency_str.endswith('ms'):
            return float(latency_str.replace('ms', '').strip())
        elif latency_str.endswith('us'):
            return float(latency_str.replace('us', '').strip()) / 1000
        elif latency_str.endswith('s'):
            return float(latency_str.replace('s', '').strip()) * 1000
        elif latency_str.endswith('ns'):
            return float(latency_str.replace('ns', '').strip()) / 1000000
        else:
            # Try to parse as number
            return float(latency_str)
    except (ValueError, AttributeError):
        return 0.0

def parse_requests(req_str: str) -> float:
    """Converte string de requisições para número"""
    if not req_str or req_str == "0":
        return 0.0
    
    req_str = str(req_str).strip()
    
    try:
        if 'k' in req_str.lower():
            return float(req_str.lower().replace('k', '').strip()) * 1000
        elif 'm' in req_str.lower():
            return float(req_str.lower().replace('m', '').strip()) * 1000000
        else:
            return float(req_str)
    except (ValueError, AttributeError):
        return 0.0

def parse_count(count_value) -> int:
    """Converte um valor numérico em inteiro, aceitando strings."""
    if count_value in (None, "", 0, "0"):
        return 0

    try:
        return int(float(str(count_value).strip()))
    except (ValueError, TypeError):
        return 0

def parse_wrk_output_for_timeouts(wrk_output_path: Path) -> int:
    """Extrai timeouts do arquivo wrk_output.txt analisando a linha 'Socket errors'"""
    if not wrk_output_path.exists():
        return 0
    
    try:
        with open(wrk_output_path, 'r') as f:
            for line in f:
                # Procura por linha como: "Socket errors: connect 0, read 0, write 0, timeout 8"
                if 'Socket errors:' in line:
                    # Extrai o valor de timeout
                    if 'timeout' in line:
                        parts = line.split('timeout')
                        if len(parts) > 1:
                            # Pega tudo após "timeout" e extrai o número
                            timeout_part = parts[1].strip()
                            # Remove qualquer texto após o número
                            timeout_str = ''.join(c for c in timeout_part if c.isdigit() or c == '.')
                            if timeout_str:
                                return parse_count(timeout_str)
    except Exception as e:
        return 0
    
    return 0

def analyze_run(run_dir: Path, lang: str, connections: int) -> Dict:
    """Analisa resultados de uma execução específica"""
    
    wrk_summary = load_json(run_dir / "wrk_summary.json")
    metrics_before = load_json(run_dir / "metrics_before.json")
    metrics_after = load_json(run_dir / "metrics_after.json")
    
    result = {
        'language': lang,
        'connections': connections,
        'latency_avg_ms': 0.0,
        'latency_max_ms': 0.0,
        'latency_p95_ms': 0.0,
        'latency_p99_ms': 0.0,
        'requests_per_sec': 0.0,
        'total_requests': 0,
        'errors': 0,
        'timeouts': 0,
        # --- Métricas primárias (camada "common", Fase 2) ---
        # Comparáveis diretamente entre Go e Rust: RSS do processo (via
        # /proc/self/status) e uso de memória do cgroup do container.
        'memory_before_mb': 0.0,
        'memory_after_mb': 0.0,
        'memory_growth_mb': 0.0,
        'peak_rss_mb_before': 0.0,
        'peak_rss_mb_after': 0.0,
        'cgroup_current_mb_before': 0.0,
        'cgroup_current_mb_after': 0.0,
        'cgroup_current_mb_growth': 0.0,
        'cgroup_peak_mb_before': 0.0,
        'cgroup_peak_mb_after': 0.0,
        'cpu_percent': 0.0,
        # --- Métricas complementares (runtime_specific, Fase 2) ---
        # NÃO comparáveis diretamente entre linguagens: em Go é
        # heap_alloc_bytes (memória gerenciada pelo GC); em Rust é
        # legacy_rss_mb (via /proc/self/statm, mantido por continuidade
        # histórica com coletas anteriores à Fase 2).
        'legacy_runtime_memory_mb_before': 0.0,
        'legacy_runtime_memory_mb_after': 0.0,
        'legacy_runtime_memory_mb_growth': 0.0,
    }
    
    # Parseia latência (verifica se campos existem e não são vazios)
    # Parseia latência (verifica se campos existem e não são vazios)
    if wrk_summary.get('latency'):
        avg_val = wrk_summary['latency'].get('avg', '0')
        max_val = wrk_summary['latency'].get('max', '0')
        p95_val = wrk_summary['latency'].get('p95', '0')
        p99_val = wrk_summary['latency'].get('p99', '0')

        if avg_val and avg_val != "":
            result['latency_avg_ms'] = parse_wrk_latency(avg_val)
        if max_val and max_val != "":
            result['latency_max_ms'] = parse_wrk_latency(max_val)
        # p95/p99 vêm do script percentiles.lua em formato numérico puro
        # (ex.: "12.34"), não com sufixo de unidade como avg/max/stdev —
        # parse_wrk_latency ainda funciona corretamente nesse caso, já
        # que cai no fallback de "tentar como número puro".
        if p95_val and p95_val != "0":
            result['latency_p95_ms'] = parse_wrk_latency(p95_val)
        if p99_val and p99_val != "0":
            result['latency_p99_ms'] = parse_wrk_latency(p99_val)
    
    # Parseia throughput
    if wrk_summary.get('requests_per_sec'):
        avg_req = wrk_summary['requests_per_sec'].get('avg', '0')
        if avg_req and avg_req != "":
            result['requests_per_sec'] = parse_requests(avg_req)
    
    # Total de requisições
    if wrk_summary.get('total', {}).get('requests'):
        total_str = wrk_summary['total']['requests']
        if total_str and total_str != "":
            try:
                if 'k' in str(total_str).lower():
                    result['total_requests'] = int(float(str(total_str).lower().replace('k', '')) * 1000)
                else:
                    result['total_requests'] = int(float(total_str))
            except (ValueError, AttributeError):
                result['total_requests'] = 0

    # Erros reportados pelo wrk
    if 'errors' in wrk_summary:
        result['errors'] = parse_count(wrk_summary.get('errors'))
    
    # Timeouts - tenta extrair do wrk_output.txt primeiro, depois do JSON
    timeouts_from_file = parse_wrk_output_for_timeouts(run_dir / "wrk_output.txt")
    if timeouts_from_file > 0:
        result['timeouts'] = timeouts_from_file
    elif 'socket_errors' in wrk_summary:
        socket_errors = wrk_summary['socket_errors']
        if isinstance(socket_errors, dict):
            result['timeouts'] = parse_count(socket_errors.get('timeout', 0))
        else:
            result['timeouts'] = parse_count(socket_errors)
    elif 'timeouts' in wrk_summary:
        result['timeouts'] = parse_count(wrk_summary.get('timeouts'))
    
    # lang pode ser 'go', 'go_heavy', 'go_mock', 'go_heavy_mock' (ou os
    # equivalentes 'rust_*') — usar startswith em vez de lista fixa
    # evita ter que atualizar esta função a cada novo tipo de endpoint.
    is_go = lang.startswith('go')

    # --- Bloco common: métricas primárias, mesmo schema em Go e Rust ---
    common_before = metrics_before.get('common', {}) or {}
    common_after = metrics_after.get('common', {}) or {}

    if common_before.get('rss_kb'):
        result['memory_before_mb'] = float(common_before['rss_kb']) / 1024
    if common_after.get('rss_kb'):
        result['memory_after_mb'] = float(common_after['rss_kb']) / 1024
    result['memory_growth_mb'] = result['memory_after_mb'] - result['memory_before_mb']

    if common_before.get('peak_rss_kb'):
        result['peak_rss_mb_before'] = float(common_before['peak_rss_kb']) / 1024
    if common_after.get('peak_rss_kb'):
        result['peak_rss_mb_after'] = float(common_after['peak_rss_kb']) / 1024

    if common_before.get('cgroup_current_bytes'):
        result['cgroup_current_mb_before'] = float(common_before['cgroup_current_bytes']) / (1024 * 1024)
    if common_after.get('cgroup_current_bytes'):
        result['cgroup_current_mb_after'] = float(common_after['cgroup_current_bytes']) / (1024 * 1024)
    result['cgroup_current_mb_growth'] = result['cgroup_current_mb_after'] - result['cgroup_current_mb_before']

    if common_before.get('cgroup_peak_bytes'):
        result['cgroup_peak_mb_before'] = float(common_before['cgroup_peak_bytes']) / (1024 * 1024)
    if common_after.get('cgroup_peak_bytes'):
        result['cgroup_peak_mb_after'] = float(common_after['cgroup_peak_bytes']) / (1024 * 1024)

    cpu_usec_before = common_before.get('cpu_usage_usec', 0) or 0
    cpu_usec_after = common_after.get('cpu_usage_usec', 0) or 0
    test_config = load_json(run_dir / "test_config.json")
    duration_str = test_config.get('duration', '0s') if test_config else '0s'

    duration_seconds = 0.0
    try:
        if duration_str.endswith('s'):
            duration_seconds = float(duration_str[:-1])
    except (ValueError, AttributeError):
        duration_seconds = 0.0

    ALLOCATED_CORES = 2
    if duration_seconds > 0 and cpu_usec_after >= cpu_usec_before:
        cpu_usec_delta = cpu_usec_after - cpu_usec_before
        duration_usec = duration_seconds * 1_000_000
        result['cpu_percent'] = (cpu_usec_delta / (duration_usec * ALLOCATED_CORES)) * 100

    # --- Bloco runtime_specific: métricas legadas/complementares ---
    runtime_before = metrics_before.get('runtime_specific', {}) or {}
    runtime_after = metrics_after.get('runtime_specific', {}) or {}

    if is_go:
        if runtime_before.get('heap_alloc_bytes'):
            result['legacy_runtime_memory_mb_before'] = float(runtime_before['heap_alloc_bytes']) / (1024 * 1024)
        if runtime_after.get('heap_alloc_bytes'):
            result['legacy_runtime_memory_mb_after'] = float(runtime_after['heap_alloc_bytes']) / (1024 * 1024)
    else:  # rust
        if runtime_before.get('legacy_rss_mb'):
            result['legacy_runtime_memory_mb_before'] = float(runtime_before['legacy_rss_mb'])
        if runtime_after.get('legacy_rss_mb'):
            result['legacy_runtime_memory_mb_after'] = float(runtime_after['legacy_rss_mb'])

    result['legacy_runtime_memory_mb_growth'] = (
        result['legacy_runtime_memory_mb_after'] - result['legacy_runtime_memory_mb_before']
    )

    return result

def find_benchmark_results(results_dir: Path) -> List[Path]:
    """Encontra todos os diretórios de resultados"""
    if not results_dir.exists():
        return []
    
    # Retorna os diretórios com timestamp
    return sorted([d for d in results_dir.iterdir() if d.is_dir()])

_DIR_PATTERN = re.compile(r'^(go|rust)(_heavy)?(_mock)?_c(\d+)$')

def _classify_dir(dirname: str) -> Tuple[str, int] | Tuple[None, None]:
    """Classifica um nome de diretório de resultado, retornando
    (language_key, connections) ou (None, None) se não reconhecido.

    language_key segue a convenção já usada internamente:
    'go', 'go_heavy', 'go_mock', 'go_heavy_mock' (e equivalentes rust_*).
    """
    m = _DIR_PATTERN.match(dirname)
    if not m:
        return None, None

    base_lang, heavy_suffix, mock_suffix, conn_str = m.groups()

    language_key = base_lang
    if heavy_suffix:
        language_key += '_heavy'
    if mock_suffix:
        language_key += '_mock'

    return language_key, int(conn_str)


def analyze_benchmark_run(run_path: Path) -> Tuple[List[Dict], List[Dict]]:
    """Analisa todos os resultados de uma execução de benchmark"""

    go_results = []
    rust_results = []

    # Percorre todos os subdiretórios
    for subdir in sorted(run_path.iterdir()):
        if not subdir.is_dir():
            continue

        dirname = subdir.name
        language_key, connections = _classify_dir(dirname)

        if language_key is None:
            continue

        result = analyze_run(subdir, language_key, connections)

        if language_key.startswith('go'):
            go_results.append(result)
        else:
            rust_results.append(result)

    # Ordena por número de conexões
    go_results.sort(key=lambda x: x['connections'])
    rust_results.sort(key=lambda x: x['connections'])

    return go_results, rust_results

def _is_replicated_run_dir(run_path: Path) -> bool:
    """Detecta se o diretório é um 'run/' dentro de benchmark_replicated."""
    if not run_path.exists() or not run_path.is_dir():
        return False
    # benchmark_replicated.sh move o diretório de resultados original para repX/run
    # que contém pastas go_c10, rust_c10 etc.
    for child in run_path.iterdir():
        if child.is_dir() and (child.name.startswith('go_c') or child.name.startswith('rust_c')):
            return True
    return False


def find_replicate_run_dirs(replicated_timestamp_dir: Path, category: str = 'analysis') -> List[Path]:
    """Lista diretórios 'run/' de cada replicação dentro de benchmark_results_replicated/<ts>.

    Estrutura esperada:
      <ts>/analysis/rep6/run/
      <ts>/analysis/rep7/run/
      ...
    """
    base = replicated_timestamp_dir / category
    if not base.exists() or not base.is_dir():
        return []

    run_dirs: List[Path] = []
    for rep_dir in sorted(base.iterdir()):
        if not rep_dir.is_dir() or not rep_dir.name.startswith('rep'):
            continue
        run_dir = rep_dir / 'run'
        if _is_replicated_run_dir(run_dir):
            run_dirs.append(run_dir)
    return run_dirs


def _mean(values: List[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _stdev(values: List[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def aggregate_replicates(all_results: List[List[Dict]]) -> List[Dict]:
    """Agrega resultados de várias replicações.

    Entrada: lista de listas, onde cada sublista é o output (go_results OU rust_results)
    de uma replicação específica.

    Saída: lista de dicts no mesmo formato base do analyze_run, porém com métricas
    representando a média e campos extras '*_stdev' + 'n'.
    """
    buckets: Dict[Tuple[str, int], List[Dict]] = {}
    for replicate_results in all_results:
        for r in replicate_results:
            key = (r.get('language', ''), int(r.get('connections', 0)))
            buckets.setdefault(key, []).append(r)

    aggregated: List[Dict] = []
    for (lang, connections), items in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1])):
        agg: Dict = {
            'language': lang,
            'connections': connections,
            'n': len(items),
        }

        # Preserva chaves esperadas pelo print atual, usando média
        for field in METRIC_FIELDS:
            vals: List[float] = []
            for it in items:
                v = it.get(field, 0.0)
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    vals.append(0.0)

            agg[field] = _mean(vals)
            agg[f'{field}_stdev'] = _stdev(vals)

        aggregated.append(agg)

    # Ordena por conexões para manter consistência visual
    aggregated.sort(key=lambda x: x.get('connections', 0))
    return aggregated

# Metadados de cada tipo de cenário: chave interna (language) e título
# de exibição. A ordem aqui define a ordem de impressão no relatório.
_SCENARIO_DISPLAY = [
    ('normal', 'go', 'rust', 'CENÁRIO NORMAL - /days-since'),
    ('heavy', 'go_heavy', 'rust_heavy', 'CENÁRIO ALLOCATION-HEAVY - /days-since-heavy (1MB alocação/req)'),
    ('mock', 'go_mock', 'rust_mock', 'CENÁRIO MOCK - /days-since-mock (sem I/O de banco)'),
    ('heavy_mock', 'go_heavy_mock', 'rust_heavy_mock', 'CENÁRIO MOCK ALLOCATION-HEAVY - /days-since-heavy-mock (sem I/O de banco)'),
]


def _print_scenario_table(go_subset: List[Dict], rust_subset: List[Dict], title: str):
    """Imprime uma tabela comparativa Go vs Rust para um único tipo de
    cenário (normal, heavy, mock ou heavy_mock)."""

    if not go_subset or not rust_subset:
        return

    print("\n" + "=" * 140)
    print(f"[{title}]")
    print("-" * 140)
    print("{:^10} | {:^26} | {:^20} | {:^15} | {:^20}".format(
        "Conexões", "Latência ms (avg/p95/p99)", "Throughput (req/s)", "Timeouts", "Mem. Antes→Depois (MB)"
    ))
    print("-" * 140)

    for go, rust in zip(go_subset, rust_subset):
        if go['connections'] != rust['connections']:
            continue

        conn = go['connections']
        go_lat = f"{go['latency_avg_ms']:.1f}/{go['latency_p95_ms']:.1f}/{go['latency_p99_ms']:.1f}"
        rust_lat = f"{rust['latency_avg_ms']:.1f}/{rust['latency_p95_ms']:.1f}/{rust['latency_p99_ms']:.1f}"
        print(f"\n{conn:^10} | Go: {go_lat:>18}   | Go: {go['requests_per_sec']:>10.0f}      | Go: {go['timeouts']:>6}    | Go: {go['memory_before_mb']:>7.2f}→{go['memory_after_mb']:>7.2f}")
        print(f"{'':^10} | Rust: {rust_lat:>16} | Rust: {rust['requests_per_sec']:>10.0f}    | Rust: {rust['timeouts']:>6}  | Rust: {rust['memory_before_mb']:>7.2f}→{rust['memory_after_mb']:>7.2f}")

        if rust['latency_avg_ms'] > 0:
            lat_diff = ((go['latency_avg_ms'] - rust['latency_avg_ms']) / rust['latency_avg_ms']) * 100
            print(f"{'':^10} | Diff: {lat_diff:>+7.1f}%", end="")

        if rust['requests_per_sec'] > 0:
            thr_diff = ((go['requests_per_sec'] - rust['requests_per_sec']) / rust['requests_per_sec']) * 100
            print(f"      | Diff: {thr_diff:>+8.1f}%", end="")

        print()


def print_comparison_table(go_results: List[Dict], rust_results: List[Dict]):
    """Imprime tabelas comparativas para os 4 tipos de cenário (Fase 3):
    normal, allocation-heavy, mock e mock allocation-heavy."""

    print("\n" + "=" * 120)
    print("COMPARAÇÃO DE DESEMPENHO: GO vs RUST (Normal / Heavy / Mock / Heavy-Mock)")
    print("=" * 120)

    for _, go_lang, rust_lang, title in _SCENARIO_DISPLAY:
        go_subset = [r for r in go_results if r['language'] == go_lang]
        rust_subset = [r for r in rust_results if r['language'] == rust_lang]
        _print_scenario_table(go_subset, rust_subset, title)

def generate_insights(go_results: List[Dict], rust_results: List[Dict]):
    """Gera insights para a pesquisa"""
    
    print("\n" + "="*100)
    print("INSIGHTS PARA ANÁLISE (relacionados às hipóteses H1-H4)")
    print("="*100)
    
    # H1: Tail latency — usa p99, conforme definido em
    # METODOLOGIA_CIENTIFICA.md (H1 é sobre p99 sob pressão de memória,
    # não sobre latência média).
    print("\n[H1] Tail Latency (p99) e Previsibilidade:")
    go_p99s = [r['latency_p99_ms'] for r in go_results]
    rust_p99s = [r['latency_p99_ms'] for r in rust_results]

    if go_p99s and rust_p99s:
        avg_go_p99 = statistics.mean(go_p99s)
        avg_rust_p99 = statistics.mean(rust_p99s)
        go_p99_var = statistics.stdev(go_p99s) if len(go_p99s) > 1 else 0
        rust_p99_var = statistics.stdev(rust_p99s) if len(rust_p99s) > 1 else 0

        print(f"  - p99 médio Go: {avg_go_p99:.2f} ms (variação entre cenários: {go_p99_var:.2f} ms)")
        print(f"  - p99 médio Rust: {avg_rust_p99:.2f} ms (variação entre cenários: {rust_p99_var:.2f} ms)")
        print(f"  - Rust {'mantém' if rust_p99_var < go_p99_var else 'não mantém'} p99 mais estável entre cenários")

        # Foco específico no cenário allocation-heavy, onde H1 é mais
        # diretamente testável (maior pressão de alocação/GC).
        go_heavy_p99 = [r['latency_p99_ms'] for r in go_results if 'heavy' in r['language']]
        rust_heavy_p99 = [r['latency_p99_ms'] for r in rust_results if 'heavy' in r['language']]
        if go_heavy_p99 and rust_heavy_p99:
            avg_go_heavy_p99 = statistics.mean(go_heavy_p99)
            avg_rust_heavy_p99 = statistics.mean(rust_heavy_p99)
            print(f"  - p99 médio Go (cenários heavy): {avg_go_heavy_p99:.2f} ms")
            print(f"  - p99 médio Rust (cenários heavy): {avg_rust_heavy_p99:.2f} ms")
            if avg_rust_heavy_p99 > 0:
                diff_pct = ((avg_go_heavy_p99 - avg_rust_heavy_p99) / avg_rust_heavy_p99) * 100
                print(f"  - Diferença de p99 sob pressão de alocação: {diff_pct:+.1f}% (Go vs Rust)")
    
    # H2: Throughput em carga moderada
    print("\n[H2] Throughput em Carga Moderada (até 100 conexões):")
    go_moderate = [r for r in go_results if r['connections'] <= 100]
    rust_moderate = [r for r in rust_results if r['connections'] <= 100]
    
    if go_moderate and rust_moderate:
        avg_go_thr = statistics.mean([r['requests_per_sec'] for r in go_moderate])
        avg_rust_thr = statistics.mean([r['requests_per_sec'] for r in rust_moderate])
        
        print(f"  - Throughput médio Go: {avg_go_thr:.0f} req/s")
        print(f"  - Throughput médio Rust: {avg_rust_thr:.0f} req/s")
        
        if avg_go_thr > 0 and avg_rust_thr > 0:
            if avg_go_thr > avg_rust_thr:
                diff_pct = ((avg_go_thr - avg_rust_thr) / avg_rust_thr) * 100
                print(f"  - Go supera Rust em {diff_pct:.1f}%")
            else:
                diff_pct = ((avg_rust_thr - avg_go_thr) / avg_go_thr) * 100
                print(f"  - Rust supera Go em {diff_pct:.1f}%")
        else:
            print(f"  - ⚠️  Dados insuficientes para comparação (valores zerados)")
    
    # H3: Ponto de saturação
    print("\n[H3] Escalabilidade e Ponto de Saturação:")
    
    # Verifica degradação de throughput
    for lang_name, results in [("Go", go_results), ("Rust", rust_results)]:
        if len(results) >= 2:
            throughputs = [r['requests_per_sec'] for r in results]
            if all(t == 0 for t in throughputs):
                print(f"  - {lang_name}: ⚠️  Dados indisponíveis (valores zerados)")
                continue
            
            peak_thr = max(throughputs)
            peak_idx = throughputs.index(peak_thr)
            
            if peak_thr > 0:
                print(f"  - {lang_name}: pico de throughput em {results[peak_idx]['connections']} conexões ({peak_thr:.0f} req/s)")
                
                # Verifica degradação após o pico
                if peak_idx < len(results) - 1:
                    final_thr = throughputs[-1]
                    if final_thr > 0:
                        degradation = ((peak_thr - final_thr) / peak_thr) * 100
                        print(f"    → Degradação de {degradation:.1f}% no cenário mais pesado")
            else:
                print(f"  - {lang_name}: ⚠️  Todos os valores de throughput são zero")
    
    # H4: Uso de memória
    print("\n[H4] Uso de Memória e Crescimento:")
    
    for lang_name, results in [("Go", go_results), ("Rust", rust_results)]:
        if results:
            total_growth = sum([r['memory_growth_mb'] for r in results])
            avg_growth = statistics.mean([r['memory_growth_mb'] for r in results])
            max_mem = max([r['memory_after_mb'] for r in results])
            
            print(f"  - {lang_name}:")
            print(f"    → Crescimento total: {total_growth:.2f} MB")
            print(f"    → Crescimento médio por cenário: {avg_growth:.2f} MB")
            print(f"    → Pico de memória: {max_mem:.2f} MB")
    
    # Análise de Timeouts
    print("\n[H5] Resiliência e Timeouts:")
    
    for lang_name, results in [("Go", go_results), ("Rust", rust_results)]:
        if results:
            total_timeouts = sum([r['timeouts'] for r in results])
            results_with_timeouts = [r for r in results if r['timeouts'] > 0]
            
            print(f"  - {lang_name}:")
            print(f"    → Total de timeouts: {total_timeouts}")
            
            if results_with_timeouts:
                avg_timeouts = statistics.mean([r['timeouts'] for r in results_with_timeouts])
                max_timeouts = max([r['timeouts'] for r in results_with_timeouts])
                max_timeout_conn = [r['connections'] for r in results_with_timeouts if r['timeouts'] == max_timeouts][0]
                print(f"    → Cenários com timeouts: {len(results_with_timeouts)} de {len(results)}")
                print(f"    → Média de timeouts (quando > 0): {avg_timeouts:.0f}")
                print(f"    → Máximo: {max_timeouts} timeouts em {max_timeout_conn} conexões")
            else:
                print(f"    → Nenhum timeout registrado")

def print_legacy_memory_section(go_results: List[Dict], rust_results: List[Dict]):
    """Imprime, em seção separada, as métricas de memória complementares
    (runtime_specific): heap_alloc_bytes para Go, legacy_rss_mb (via
    /proc/self/statm) para Rust. NÃO comparáveis diretamente entre
    linguagens — servem apenas para explicar o mecanismo interno de cada
    runtime por trás dos números já comparados na seção primária (common).
    """
    print("\n" + "=" * 100)
    print("MÉTRICAS COMPLEMENTARES DE MEMÓRIA (runtime_specific — NÃO comparável entre linguagens)")
    print("=" * 100)
    print("Go: heap_alloc_bytes (memória gerenciada pelo GC)")
    print("Rust: legacy_rss_mb (via /proc/self/statm, mantido por continuidade histórica)")
    print("-" * 100)

    for lang_name, results in [("Go", go_results), ("Rust", rust_results)]:
        if not results:
            continue
        avg_before = statistics.mean([r['legacy_runtime_memory_mb_before'] for r in results])
        avg_after = statistics.mean([r['legacy_runtime_memory_mb_after'] for r in results])
        avg_growth = statistics.mean([r['legacy_runtime_memory_mb_growth'] for r in results])

        print(f"\n{lang_name}:")
        print(f"  Média antes:  {avg_before:8.2f} MB")
        print(f"  Média depois: {avg_after:8.2f} MB")
        print(f"  Crescimento médio: {avg_growth:+8.2f} MB")

def main():
    """Função principal"""
    
    if len(sys.argv) > 1:
        results_path = Path(sys.argv[1])
    else:
        results_path = Path("benchmark_results")
    
    if not results_path.exists():
        print(f"Erro: Diretório {results_path} não encontrado")
        print("Execute o benchmark.sh primeiro!")
        sys.exit(1)
    
    # Encontra execuções de benchmark
    runs = find_benchmark_results(results_path)
    
    if not runs:
        print(f"Nenhum resultado encontrado em {results_path}")
        sys.exit(1)
    
    # Analisa a execução mais recente
    latest_run = runs[-1]
    print(f"\nAnalisando resultados de: {latest_run.name}")

    # Detecta layout de benchmark replicado (benchmark_results_replicated)
    replicate_runs = find_replicate_run_dirs(latest_run, category='analysis')
    if replicate_runs:
        print(f"Detectado benchmark replicado: {len(replicate_runs)} replicações (categoria=analysis)")

        go_by_rep: List[List[Dict]] = []
        rust_by_rep: List[List[Dict]] = []

        for run_dir in replicate_runs:
            go_rep, rust_rep = analyze_benchmark_run(run_dir)
            if go_rep and rust_rep:
                go_by_rep.append(go_rep)
                rust_by_rep.append(rust_rep)

        go_results = aggregate_replicates(go_by_rep)
        rust_results = aggregate_replicates(rust_by_rep)
        output_file = latest_run / "analysis_replicated.json"
        payload = {
            'mode': 'replicated',
            'timestamp': latest_run.name,
            'replicates_analyzed': len(go_by_rep),
            'replicate_run_dirs': [str(p) for p in replicate_runs],
            'go_results': go_results,
            'rust_results': rust_results,
        }
    else:
        go_results, rust_results = analyze_benchmark_run(latest_run)
        output_file = latest_run / "analysis.json"
        payload = {
            'mode': 'single',
            'timestamp': latest_run.name,
            'go_results': go_results,
            'rust_results': rust_results,
        }
    
    if not go_results or not rust_results:
        print("Erro: Resultados incompletos")
        sys.exit(1)
    
    # Gera análises
    print_comparison_table(go_results, rust_results)
    generate_insights(go_results, rust_results)
    print_legacy_memory_section(go_results, rust_results)
    
    # Salva resultados consolidados
    with open(output_file, 'w') as f:
        json.dump(payload, f, indent=2)
    
    print(f"\n✓ Análise completa salva em: {output_file}")

if __name__ == '__main__':
    main()
