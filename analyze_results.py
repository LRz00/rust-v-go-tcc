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


METRIC_FIELDS: Tuple[str, ...] = (
    'latency_avg_ms',
    'latency_max_ms',
    'requests_per_sec',
    'total_requests',
    'errors',
    'memory_before_mb',
    'memory_after_mb',
    'memory_growth_mb',
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
        'requests_per_sec': 0.0,
        'total_requests': 0,
        'errors': 0,
        'memory_before_mb': 0.0,
        'memory_after_mb': 0.0,
        'memory_growth_mb': 0.0,
    }
    
    # Parseia latência (verifica se campos existem e não são vazios)
    if wrk_summary.get('latency'):
        avg_val = wrk_summary['latency'].get('avg', '0')
        max_val = wrk_summary['latency'].get('max', '0')
        
        if avg_val and avg_val != "":
            result['latency_avg_ms'] = parse_wrk_latency(avg_val)
        if max_val and max_val != "":
            result['latency_max_ms'] = parse_wrk_latency(max_val)
    
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
    
    # Memória
    if lang == 'go':
        if metrics_before.get('heap_alloc_bytes') and metrics_before['heap_alloc_bytes'] > 0:
            result['memory_before_mb'] = metrics_before['heap_alloc_bytes'] / (1024 * 1024)
        if metrics_after.get('heap_alloc_bytes') and metrics_after['heap_alloc_bytes'] > 0:
            result['memory_after_mb'] = metrics_after['heap_alloc_bytes'] / (1024 * 1024)
    else:  # rust
        if metrics_before.get('rss_mb'):
            result['memory_before_mb'] = float(metrics_before['rss_mb'])
        if metrics_after.get('rss_mb'):
            result['memory_after_mb'] = float(metrics_after['rss_mb'])
    
    result['memory_growth_mb'] = result['memory_after_mb'] - result['memory_before_mb']
    
    return result

def find_benchmark_results(results_dir: Path) -> List[Path]:
    """Encontra todos os diretórios de resultados"""
    if not results_dir.exists():
        return []
    
    # Retorna os diretórios com timestamp
    return sorted([d for d in results_dir.iterdir() if d.is_dir()])

def analyze_benchmark_run(run_path: Path) -> Tuple[List[Dict], List[Dict]]:
    """Analisa todos os resultados de uma execução de benchmark"""
    
    go_results = []
    rust_results = []
    
    # Percorre todos os subdiretórios
    for subdir in sorted(run_path.iterdir()):
        if not subdir.is_dir():
            continue
        
        dirname = subdir.name
        
        # Extrai linguagem e número de conexões
        # Padrões: go_c10, rust_c10, go_heavy_c10, rust_heavy_c10
        if dirname.startswith('go_heavy_c'):
            connections = int(dirname.replace('go_heavy_c', ''))
            result = analyze_run(subdir, 'go_heavy', connections)
            go_results.append(result)
        elif dirname.startswith('go_c'):
            connections = int(dirname.replace('go_c', ''))
            result = analyze_run(subdir, 'go', connections)
            go_results.append(result)
        elif dirname.startswith('rust_heavy_c'):
            connections = int(dirname.replace('rust_heavy_c', ''))
            result = analyze_run(subdir, 'rust_heavy', connections)
            rust_results.append(result)
        elif dirname.startswith('rust_c'):
            connections = int(dirname.replace('rust_c', ''))
            result = analyze_run(subdir, 'rust', connections)
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

def print_comparison_table(go_results: List[Dict], rust_results: List[Dict]):
    """Imprime tabela comparativa"""
    
    print("\n" + "="*120)
    print("COMPARAÇÃO DE DESEMPENHO: GO vs RUST (Normal + Allocation-Heavy)")
    print("="*120)
    
    # Agrupa por tipo de teste
    go_normal = [r for r in go_results if r['language'] == 'go']
    go_heavy = [r for r in go_results if r['language'] == 'go_heavy']
    rust_normal = [r for r in rust_results if r['language'] == 'rust']
    rust_heavy = [r for r in rust_results if r['language'] == 'rust_heavy']
    
    # Exibe resultados normais
    if go_normal and rust_normal:
        print("\n[CENÁRIO NORMAL - /days-since]")
        print("-" * 120)
        print("{:^10} | {:^20} | {:^20} | {:^20} | {:^20}".format(
            "Conexões", "Latência Média (ms)", "Throughput (req/s)", "Mem. Antes (MB)", "Mem. Depois (MB)"
        ))
        print("-" * 120)
        
        for go, rust in zip(go_normal, rust_normal):
            if go['connections'] != rust['connections']:
                continue
            
            conn = go['connections']
            print(f"\n{conn:^10} | Go: {go['latency_avg_ms']:>8.2f}        | Go: {go['requests_per_sec']:>10.0f}      | Go: {go['memory_before_mb']:>8.2f}        | Go: {go['memory_after_mb']:>8.2f}")
            print(f"{'':^10} | Rust: {rust['latency_avg_ms']:>8.2f}      | Rust: {rust['requests_per_sec']:>10.0f}    | Rust: {rust['memory_before_mb']:>8.2f}      | Rust: {rust['memory_after_mb']:>8.2f}")
            
            # Calcula diferenças percentuais
            if rust['latency_avg_ms'] > 0:
                lat_diff = ((go['latency_avg_ms'] - rust['latency_avg_ms']) / rust['latency_avg_ms']) * 100
                print(f"{'':^10} | Diff: {lat_diff:>+7.1f}%", end="")
            
            if rust['requests_per_sec'] > 0:
                thr_diff = ((go['requests_per_sec'] - rust['requests_per_sec']) / rust['requests_per_sec']) * 100
                print(f"      | Diff: {thr_diff:>+8.1f}%", end="")
            
            print()
    
    # Exibe resultados allocation-heavy
    if go_heavy and rust_heavy:
        print("\n" + "="*120)
        print("[CENÁRIO ALLOCATION-HEAVY - /days-since-heavy (10MB alocação/req)]")
        print("-" * 120)
        print("{:^10} | {:^20} | {:^20} | {:^20} | {:^20}".format(
            "Conexões", "Latência Média (ms)", "Throughput (req/s)", "Mem. Antes (MB)", "Mem. Depois (MB)"
        ))
        print("-" * 120)
        
        for go, rust in zip(go_heavy, rust_heavy):
            if go['connections'] != rust['connections']:
                continue
            
            conn = go['connections']
            print(f"\n{conn:^10} | Go: {go['latency_avg_ms']:>8.2f}        | Go: {go['requests_per_sec']:>10.0f}      | Go: {go['memory_before_mb']:>8.2f}        | Go: {go['memory_after_mb']:>8.2f}")
            print(f"{'':^10} | Rust: {rust['latency_avg_ms']:>8.2f}      | Rust: {rust['requests_per_sec']:>10.0f}    | Rust: {rust['memory_before_mb']:>8.2f}      | Rust: {rust['memory_after_mb']:>8.2f}")
            
            # Calcula diferenças percentuais
            if rust['latency_avg_ms'] > 0:
                lat_diff = ((go['latency_avg_ms'] - rust['latency_avg_ms']) / rust['latency_avg_ms']) * 100
                print(f"{'':^10} | Diff: {lat_diff:>+7.1f}%", end="")
            
            if rust['requests_per_sec'] > 0:
                thr_diff = ((go['requests_per_sec'] - rust['requests_per_sec']) / rust['requests_per_sec']) * 100
                print(f"      | Diff: {thr_diff:>+8.1f}%", end="")
            
            print()

def generate_insights(go_results: List[Dict], rust_results: List[Dict]):
    """Gera insights para a pesquisa"""
    
    print("\n" + "="*100)
    print("INSIGHTS PARA ANÁLISE (relacionados às hipóteses H1-H4)")
    print("="*100)
    
    # H1: Tail latency
    print("\n[H1] Latência e Previsibilidade:")
    go_latencies = [r['latency_avg_ms'] for r in go_results]
    rust_latencies = [r['latency_avg_ms'] for r in rust_results]
    
    if go_latencies and rust_latencies:
        go_latency_var = statistics.stdev(go_latencies) if len(go_latencies) > 1 else 0
        rust_latency_var = statistics.stdev(rust_latencies) if len(rust_latencies) > 1 else 0
        
        print(f"  - Variação de latência Go: {go_latency_var:.2f} ms")
        print(f"  - Variação de latência Rust: {rust_latency_var:.2f} ms")
        print(f"  - Rust {'mantém' if rust_latency_var < go_latency_var else 'não mantém'} latência mais estável")
    
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
    
    # Salva resultados consolidados
    with open(output_file, 'w') as f:
        json.dump(payload, f, indent=2)
    
    print(f"\n✓ Análise completa salva em: {output_file}")

if __name__ == '__main__':
    main()
