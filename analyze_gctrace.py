#!/usr/bin/env python3
"""
Analisa arquivos gctrace.log (Fase 6), calculando estatísticas de pausa
STW e, opcionalmente, correlacionando com o p99 reportado pelo wrk do
mesmo cenário.
"""

import re
import statistics
import sys
import json
from pathlib import Path

GC_LINE_PATTERN = re.compile(
    r'gc (?P<n>\d+) @(?P<elapsed>[\d.]+)s (?P<cpu_pct>\d+)%: '
    r'(?P<stw1>[\d.]+)\+(?P<concurrent>[\d.]+)\+(?P<stw2>[\d.]+) ms clock'
)


def parse_gctrace(path: Path):
    events = []
    for line in path.read_text().splitlines():
        m = GC_LINE_PATTERN.search(line)
        if not m:
            continue
        stw_total_ms = float(m.group('stw1')) + float(m.group('stw2'))
        events.append({
            'n': int(m.group('n')),
            'elapsed_s': float(m.group('elapsed')),
            'stw_ms': stw_total_ms,
            'concurrent_ms': float(m.group('concurrent')),
        })
    return events


def summarize(events):
    if not events:
        return None
    stw_values = sorted(e['stw_ms'] for e in events)

    def percentile(values, p):
        if not values:
            return 0.0
        k = (len(values) - 1) * (p / 100)
        f = int(k)
        c = min(f + 1, len(values) - 1)
        if f == c:
            return values[f]
        return values[f] + (values[c] - values[f]) * (k - f)

    return {
        'total_gc_cycles': len(events),
        'stw_mean_ms': statistics.mean(stw_values),
        'stw_median_ms': statistics.median(stw_values),
        'stw_p95_ms': percentile(stw_values, 95),
        'stw_p99_ms': percentile(stw_values, 99),
        'stw_max_ms': max(stw_values),
    }


def main():
    if len(sys.argv) < 2:
        print("Uso: analyze_gctrace.py <diretorio_do_cenario>")
        print("Ex.: analyze_gctrace.py benchmark_results/20260727_193059/go_heavy_c10")
        sys.exit(1)

    scenario_dir = Path(sys.argv[1])
    gctrace_file = scenario_dir / "gctrace.log"

    if not gctrace_file.exists():
        print(f"Erro: {gctrace_file} não encontrado")
        sys.exit(1)

    events = parse_gctrace(gctrace_file)
    summary = summarize(events)

    if summary is None:
        print("Nenhum evento de GC encontrado no arquivo.")
        sys.exit(0)

    print(f"Cenário: {scenario_dir.name}")
    print(f"Ciclos de GC capturados: {summary['total_gc_cycles']}")
    print(f"Pausa STW média:  {summary['stw_mean_ms']:.4f} ms")
    print(f"Pausa STW mediana: {summary['stw_median_ms']:.4f} ms")
    print(f"Pausa STW p95:    {summary['stw_p95_ms']:.4f} ms")
    print(f"Pausa STW p99:    {summary['stw_p99_ms']:.4f} ms")
    print(f"Pausa STW máxima: {summary['stw_max_ms']:.4f} ms")

    # Correlação com p99 de latência do wrk, se disponível
    wrk_summary_file = scenario_dir / "wrk_summary.json"
    if wrk_summary_file.exists():
        wrk_data = json.loads(wrk_summary_file.read_text())
        p99_us = float(wrk_data.get('latency', {}).get('p99', 0))
        p99_ms = p99_us / 1000
        print(f"\np99 de latência (wrk): {p99_ms:.4f} ms")
        if summary['stw_max_ms'] > 0:
            ratio = summary['stw_max_ms'] / p99_ms if p99_ms > 0 else 0
            print(f"Maior pausa STW / p99 latência: {ratio:.2%}")
            print("(se próximo de 100% ou maior, sugere que pausas de GC")
            print(" contribuem significativamente para a cauda de latência)")


if __name__ == '__main__':
    main()