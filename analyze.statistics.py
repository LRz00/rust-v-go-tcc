#!/usr/bin/env python3
"""
Análise estatística inferencial sobre as réplicas do benchmark Go vs Rust.

Para cada combinação (tipo de cenário x número de conexões), compara as
N réplicas de Go contra as N réplicas de Rust como amostras PAREADAS
(mesmo índice de réplica em ambas), já que cada réplica compartilha
condições ambientais aproximadas (temperatura, estado do sistema).

Pipeline por combinação x métrica:
  1. Teste de normalidade das diferenças pareadas (Shapiro-Wilk).
  2. Se normal (p >= 0.05): teste t pareado (Student).
     Se não-normal (p < 0.05): teste de Wilcoxon (signed-rank).
  3. Intervalo de confiança de 95% para a diferença média (bootstrap).
  4. Tamanho de efeito: Cohen's d pareado.
  5. Ao final, correção de Benjamini-Hochberg (FDR) sobre o conjunto de
     p-valores de cada métrica, para controlar falsos positivos entre
     as múltiplas comparações (4 tipos de cenário x 6 conexões).

Reaproveita a lógica de leitura de diretórios já usada em
analyze_results.py (find_replicate_run_dirs, analyze_benchmark_run),
mas em vez de agregar (média/stdev), preserva os N valores brutos por
réplica, necessários para os testes pareados.

Uso:
    python3 analyze_statistics.py benchmark_results_replicated
    python3 analyze_statistics.py benchmark_results_replicated/20260803_085536
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats

# Reaproveita as funções de leitura já existentes em analyze_results.py.
# Este script assume que analyze_results.py está no mesmo diretório.
try:
    from analyze_results import (
        analyze_benchmark_run,
        find_replicate_run_dirs,
    )
except ImportError:
    print("Erro: analyze_statistics.py precisa estar no mesmo diretório "
          "que analyze_results.py (reaproveita suas funções de leitura).")
    sys.exit(1)


# Métricas avaliadas estatisticamente, mapeadas para rótulos legíveis e
# para a hipótese correspondente (apenas para organização do relatório).
METRICS_TO_TEST: List[Tuple[str, str, str]] = [
    ('latency_p99_ms', 'p99 de latência (ms)', 'H1'),
    ('latency_avg_ms', 'latência média (ms)', 'H1'),
    ('requests_per_sec', 'throughput (req/s)', 'H2/H3'),
    ('cpu_percent', 'uso de CPU (%)', 'H2'),
    ('memory_growth_mb', 'crescimento de memória (MB, camada common)', 'H4'),
]

SCENARIO_TYPES = ['normal', 'heavy', 'mock', 'heavy_mock']
SCENARIO_LABELS = {
    'normal': 'Normal (com banco)',
    'heavy': 'Allocation-Heavy (com banco)',
    'mock': 'Mock (sem I/O)',
    'heavy_mock': 'Mock Allocation-Heavy (sem I/O)',
}


def collect_paired_samples(run_dirs: List[Path]) -> Dict[Tuple[str, int], Dict[str, Tuple[List[float], List[float]]]]:
    """Para cada (scenario_type, connections), retorna um dict metric ->
    (valores_go, valores_rust), com os N valores brutos (um por réplica),
    na MESMA ordem de réplica em ambos os vetores (pareamento por índice)."""

    # go_by_rep[i] = lista de resultados go da réplica i (não agregados)
    go_by_rep: List[List[Dict]] = []
    rust_by_rep: List[List[Dict]] = []

    for run_dir in run_dirs:
        go_results, rust_results = analyze_benchmark_run(run_dir)
        if go_results and rust_results:
            go_by_rep.append(go_results)
            rust_by_rep.append(rust_results)

    if len(go_by_rep) != len(rust_by_rep):
        print(f"AVISO: número de réplicas Go ({len(go_by_rep)}) difere de "
              f"Rust ({len(rust_by_rep)}); usando o mínimo comum.")

    n_reps = min(len(go_by_rep), len(rust_by_rep))
    if n_reps < len(go_by_rep) or n_reps < len(rust_by_rep):
        go_by_rep = go_by_rep[:n_reps]
        rust_by_rep = rust_by_rep[:n_reps]

    lang_suffix = {
        'normal': ('go', 'rust'),
        'heavy': ('go_heavy', 'rust_heavy'),
        'mock': ('go_mock', 'rust_mock'),
        'heavy_mock': ('go_heavy_mock', 'rust_heavy_mock'),
    }

    # Descobre todas as combinações (scenario_type, connections) presentes
    combos: set = set()
    for go_results in go_by_rep:
        for r in go_results:
            for stype, (glang, _) in lang_suffix.items():
                if r['language'] == glang:
                    combos.add((stype, r['connections']))

    output: Dict[Tuple[str, int], Dict[str, Tuple[List[float], List[float]]]] = {}

    for (stype, connections) in sorted(combos):
        glang, rlang = lang_suffix[stype]
        metric_vectors: Dict[str, Tuple[List[float], List[float]]] = {}

        for metric_key, _, _ in METRICS_TO_TEST:
            go_vals: List[float] = []
            rust_vals: List[float] = []

            for rep_idx in range(n_reps):
                go_match = next(
                    (r for r in go_by_rep[rep_idx]
                     if r['language'] == glang and r['connections'] == connections),
                    None
                )
                rust_match = next(
                    (r for r in rust_by_rep[rep_idx]
                     if r['language'] == rlang and r['connections'] == connections),
                    None
                )
                # Só inclui a réplica se AMBOS os lados têm dado válido,
                # preservando o pareamento por índice de réplica.
                if go_match is not None and rust_match is not None:
                    go_vals.append(float(go_match.get(metric_key, 0.0)))
                    rust_vals.append(float(rust_match.get(metric_key, 0.0)))

            metric_vectors[metric_key] = (go_vals, rust_vals)

        output[(stype, connections)] = metric_vectors

    return output


def cohens_d_paired(diffs: np.ndarray) -> float:
    """Cohen's d para amostras pareadas: média das diferenças dividida
    pelo desvio-padrão das diferenças."""
    sd = np.std(diffs, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(diffs) / sd)


def bootstrap_ci_diff(go_vals: np.ndarray, rust_vals: np.ndarray,
                       n_boot: int = 10000, ci: float = 0.95,
                       seed: int = 42) -> Tuple[float, float]:
    """IC95% para a diferença média pareada (Go - Rust), via bootstrap
    dos pares. Não assume normalidade, ao contrário do IC paramétrico
    baseado no erro padrão do t-test."""
    rng = np.random.default_rng(seed)
    n = len(go_vals)
    diffs = go_vals - rust_vals
    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_means[b] = np.mean(diffs[idx])
    alpha = 1 - ci
    lower = np.percentile(boot_means, 100 * alpha / 2)
    upper = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return float(lower), float(upper)


def run_pair_test(go_vals: List[float], rust_vals: List[float]) -> Dict:
    """Executa o pipeline completo para um par de vetores pareados:
    Shapiro-Wilk -> t pareado OU Wilcoxon -> IC95% (bootstrap) -> Cohen's d.
    Retorna um dict com todos os resultados intermediários e finais."""

    n = len(go_vals)
    result = {'n': n}

    if n < 3:
        result['error'] = 'n insuficiente (<3) para testes estatísticos'
        return result

    go_arr = np.array(go_vals)
    rust_arr = np.array(rust_vals)
    diffs = go_arr - rust_arr

    result['go_mean'] = float(np.mean(go_arr))
    result['go_std'] = float(np.std(go_arr, ddof=1))
    result['rust_mean'] = float(np.mean(rust_arr))
    result['rust_std'] = float(np.std(rust_arr, ddof=1))
    result['diff_mean'] = float(np.mean(diffs))

    # Se todas as diferenças forem idênticas (variância zero), os testes
    # de normalidade/hipótese não são bem definidos.
    if np.allclose(diffs, diffs[0]):
        result['normality_p'] = None
        result['test_used'] = 'none (diferenças constantes)'
        result['p_value'] = 0.0 if diffs[0] != 0 else 1.0
        result['effect_size_cohens_d'] = None
        result['ci95_diff'] = (float(diffs[0]), float(diffs[0]))
        return result

    # 1. Shapiro-Wilk sobre as diferenças pareadas
    shapiro_stat, shapiro_p = stats.shapiro(diffs)
    result['normality_p'] = float(shapiro_p)

    # 2. Escolhe o teste conforme normalidade (alpha = 0.05)
    if shapiro_p >= 0.05:
        test_stat, p_value = stats.ttest_rel(go_arr, rust_arr)
        result['test_used'] = 't-pareado (Student)'
    else:
        try:
            test_stat, p_value = stats.wilcoxon(go_arr, rust_arr)
        except ValueError:
            # wilcoxon falha se todas as diferenças forem zero
            test_stat, p_value = 0.0, 1.0
        result['test_used'] = 'Wilcoxon (signed-rank)'

    result['test_statistic'] = float(test_stat)
    result['p_value'] = float(p_value)

    # 3. IC95% via bootstrap (não paramétrico, válido independente do
    #    teste escolhido acima)
    ci_lower, ci_upper = bootstrap_ci_diff(go_arr, rust_arr)
    result['ci95_diff'] = (ci_lower, ci_upper)

    # 4. Tamanho de efeito
    result['effect_size_cohens_d'] = cohens_d_paired(diffs)

    return result


def effect_size_label(d: float) -> str:
    ad = abs(d)
    if ad < 0.2:
        return 'desprezível'
    elif ad < 0.5:
        return 'pequeno'
    elif ad < 0.8:
        return 'médio'
    else:
        return 'grande'


def apply_fdr_correction(all_results: List[Dict]) -> None:
    """Aplica correção de Benjamini-Hochberg (FDR) sobre os p-valores de
    TODAS as comparações de uma mesma métrica, adicionando o campo
    'p_value_adjusted' e 'significant_fdr' (alpha=0.05) em cada resultado,
    in-place."""

    # Agrupa por métrica, já que a correção deve ser feita dentro do
    # conjunto de comparações da mesma família de testes.
    by_metric: Dict[str, List[Dict]] = {}
    for r in all_results:
        if 'p_value' not in r:
            continue
        by_metric.setdefault(r['metric_key'], []).append(r)

    for metric_key, group in by_metric.items():
        p_values = [r['p_value'] for r in group]
        p_adjusted = stats.false_discovery_control(p_values, method='bh')
        for r, p_adj in zip(group, p_adjusted):
            r['p_value_adjusted'] = float(p_adj)
            r['significant_fdr'] = bool(p_adj <= 0.05)


def main():
    if len(sys.argv) < 2:
        results_path = Path("benchmark_results_replicated")
    else:
        results_path = Path(sys.argv[1])

    if not results_path.exists():
        print(f"Erro: {results_path} não encontrado")
        sys.exit(1)

    # Se apontar para a pasta-mãe, pega a execução replicada mais recente
    if (results_path / "analysis").exists():
        run_path = results_path
    else:
        candidates = sorted([d for d in results_path.iterdir() if d.is_dir()])
        if not candidates:
            print(f"Erro: nenhuma execução encontrada em {results_path}")
            sys.exit(1)
        run_path = candidates[-1]

    print(f"Analisando: {run_path}")
    run_dirs = find_replicate_run_dirs(run_path, category='analysis')
    if not run_dirs:
        print("Erro: nenhum diretório de réplica encontrado (category=analysis)")
        sys.exit(1)
    print(f"Réplicas encontradas: {len(run_dirs)}")

    paired = collect_paired_samples(run_dirs)

    all_results: List[Dict] = []

    for (stype, connections), metrics in paired.items():
        for metric_key, metric_label, hypothesis in METRICS_TO_TEST:
            go_vals, rust_vals = metrics[metric_key]
            if len(go_vals) < 3:
                continue
            test_result = run_pair_test(go_vals, rust_vals)
            test_result.update({
                'scenario_type': stype,
                'connections': connections,
                'metric_key': metric_key,
                'metric_label': metric_label,
                'hypothesis': hypothesis,
            })
            all_results.append(test_result)

    apply_fdr_correction(all_results)

    # ---- Relatório em texto ----
    print("\n" + "=" * 130)
    print("ANÁLISE ESTATÍSTICA INFERENCIAL (testes pareados, IC95%, tamanho de efeito, correção FDR)")
    print("=" * 130)

    for stype in SCENARIO_TYPES:
        subset = [r for r in all_results if r['scenario_type'] == stype]
        if not subset:
            continue
        print(f"\n[{SCENARIO_LABELS[stype]}]")
        for r in sorted(subset, key=lambda x: (x['metric_key'], x['connections'])):
            if 'error' in r:
                print(f"  {r['metric_label']} | c={r['connections']:>3}: {r['error']}")
                continue

            sig_marker = "***" if r.get('significant_fdr') else "   "
            d = r.get('effect_size_cohens_d')
            d_str = f"d={d:+.2f} ({effect_size_label(d)})" if d is not None else "d=n/a"
            ci_low, ci_high = r['ci95_diff']

            print(f"  {r['metric_label']:<35} | c={r['connections']:>3} | "
                  f"Go={r['go_mean']:>10.3f} Rust={r['rust_mean']:>10.3f} | "
                  f"diff={r['diff_mean']:>+10.3f} [{ci_low:>+10.3f}, {ci_high:>+10.3f}] | "
                  f"{r['test_used']:<22} p={r['p_value']:.4g} p_adj={r['p_value_adjusted']:.4g} {sig_marker} | "
                  f"{d_str}")

    print("\n(*** = significativo após correção FDR de Benjamini-Hochberg, alpha=0.05)")

    # ---- Exporta JSON estruturado para uso no Capítulo 5 ----
    output_file = run_path / "statistical_analysis.json"
    serializable = []
    for r in all_results:
        r_copy = dict(r)
        if 'ci95_diff' in r_copy:
            r_copy['ci95_diff'] = list(r_copy['ci95_diff'])
        serializable.append(r_copy)

    with open(output_file, 'w') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Resultados estruturados salvos em: {output_file}")


if __name__ == '__main__':
    main()