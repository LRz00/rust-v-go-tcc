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
    if not latency_str:
        return 0.0
    
    latency_str = latency_str.strip()
    
    if latency_str.endswith('ms'):
        return float(latency_str.replace('ms', ''))
    elif latency_str.endswith('us'):
        return float(latency_str.replace('us', '')) / 1000
    elif latency_str.endswith('s'):
        return float(latency_str.replace('s', '')) * 1000
    else:
        return float(latency_str)

def parse_requests(req_str: str) -> float:
    """Converte string de requisições para número"""
    if not req_str:
        return 0.0
    
    req_str = req_str.strip()
    
    if 'k' in req_str.lower():
        return float(req_str.lower().replace('k', '')) * 1000
    else:
        return float(req_str)

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
    
    # Parseia latência
    if wrk_summary.get('latency'):
        result['latency_avg_ms'] = parse_wrk_latency(wrk_summary['latency'].get('avg', '0'))
        result['latency_max_ms'] = parse_wrk_latency(wrk_summary['latency'].get('max', '0'))
    
    # Parseia throughput
    if wrk_summary.get('requests_per_sec'):
        result['requests_per_sec'] = parse_requests(wrk_summary['requests_per_sec'].get('avg', '0'))
    
    # Total de requisições
    if wrk_summary.get('total', {}).get('requests'):
        total_str = wrk_summary['total']['requests']
        if 'k' in total_str.lower():
            result['total_requests'] = int(float(total_str.lower().replace('k', '')) * 1000)
        else:
            result['total_requests'] = int(total_str)
    
    # Memória
    if lang == 'go':
        if metrics_before.get('heap_alloc_bytes'):
            result['memory_before_mb'] = metrics_before['heap_alloc_bytes'] / (1024 * 1024)
        if metrics_after.get('heap_alloc_bytes'):
            result['memory_after_mb'] = metrics_after['heap_alloc_bytes'] / (1024 * 1024)
    else:  # rust
        if metrics_before.get('rss_mb'):
            result['memory_before_mb'] = metrics_before['rss_mb']
        if metrics_after.get('rss_mb'):
            result['memory_after_mb'] = metrics_after['rss_mb']
    
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
    for subdir in run_path.iterdir():
        if not subdir.is_dir():
            continue
        
        dirname = subdir.name
        
        # Extrai linguagem e número de conexões
        if dirname.startswith('go_c'):
            connections = int(dirname.replace('go_c', ''))
            result = analyze_run(subdir, 'go', connections)
            go_results.append(result)
        elif dirname.startswith('rust_c'):
            connections = int(dirname.replace('rust_c', ''))
            result = analyze_run(subdir, 'rust', connections)
            rust_results.append(result)
    
    # Ordena por número de conexões
    go_results.sort(key=lambda x: x['connections'])
    rust_results.sort(key=lambda x: x['connections'])
    
    return go_results, rust_results

def print_comparison_table(go_results: List[Dict], rust_results: List[Dict]):
    """Imprime tabela comparativa"""
    
    print("\n" + "="*100)
    print("COMPARAÇÃO DE DESEMPENHO: GO vs RUST")
    print("="*100)
    
    print("\n{:^10} | {:^20} | {:^20} | {:^20} | {:^20}".format(
        "Conexões", "Latência Média (ms)", "Throughput (req/s)", "Mem. Antes (MB)", "Mem. Depois (MB)"
    ))
    print("-"*100)
    
    for go, rust in zip(go_results, rust_results):
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
        
        if avg_go_thr > avg_rust_thr:
            diff_pct = ((avg_go_thr - avg_rust_thr) / avg_rust_thr) * 100
            print(f"  - Go supera Rust em {diff_pct:.1f}%")
        else:
            diff_pct = ((avg_rust_thr - avg_go_thr) / avg_go_thr) * 100
            print(f"  - Rust supera Go em {diff_pct:.1f}%")
    
    # H3: Ponto de saturação
    print("\n[H3] Escalabilidade e Ponto de Saturação:")
    
    # Verifica degradação de throughput
    for lang_name, results in [("Go", go_results), ("Rust", rust_results)]:
        if len(results) >= 2:
            throughputs = [r['requests_per_sec'] for r in results]
            peak_thr = max(throughputs)
            peak_idx = throughputs.index(peak_thr)
            
            print(f"  - {lang_name}: pico de throughput em {results[peak_idx]['connections']} conexões ({peak_thr:.0f} req/s)")
            
            # Verifica degradação após o pico
            if peak_idx < len(results) - 1:
                final_thr = throughputs[-1]
                degradation = ((peak_thr - final_thr) / peak_thr) * 100
                print(f"    → Degradação de {degradation:.1f}% no cenário mais pesado")
    
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
    
    go_results, rust_results = analyze_benchmark_run(latest_run)
    
    if not go_results or not rust_results:
        print("Erro: Resultados incompletos")
        sys.exit(1)
    
    # Gera análises
    print_comparison_table(go_results, rust_results)
    generate_insights(go_results, rust_results)
    
    # Salva resultados consolidados
    output_file = latest_run / "analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'go_results': go_results,
            'rust_results': rust_results,
            'timestamp': latest_run.name
        }, f, indent=2)
    
    print(f"\n✓ Análise completa salva em: {output_file}")

if __name__ == '__main__':
    main()
