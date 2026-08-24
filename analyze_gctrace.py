#!/usr/bin/env python3
import re
import statistics
import sys
import json
from pathlib import Path

GC_LINE_PATTERN = re.compile(
    r"gc (?P<n>\d+) @(?P<elapsed>[\d.]+)s (?P<cpu_pct>\d+)%: "
    r"(?P<stw1>[\d.]+)\+(?P<concurrent>[\d.]+)\+(?P<stw2>[\d.]+) ms clock"
)

def parse_gctrace(path):
    events = []
    for line in path.read_text().splitlines():
        m = GC_LINE_PATTERN.search(line)
        if not m:
            continue
        events.append({
            "n": int(m.group("n")),
            "elapsed_s": float(m.group("elapsed")),
            "stw_ms": float(m.group("stw1")) + float(m.group("stw2")),
            "concurrent_ms": float(m.group("concurrent"))
        })
    return events

def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)

def summarize(events):
    if not events:
        return None
    values = sorted(e["stw_ms"] for e in events)
    return {
        "total_gc_cycles": len(events),
        "stw_mean_ms": statistics.mean(values),
        "stw_median_ms": statistics.median(values),
        "stw_p95_ms": percentile(values, 95),
        "stw_p99_ms": percentile(values, 99),
        "stw_max_ms": max(values)
    }

def read_wrk_p99(scenario_dir):
    path = scenario_dir / "wrk_summary.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    p99_us = float(data.get("latency", {}).get("p99", 0))
    return p99_us / 1000 if p99_us > 0 else None

def get_variant(name):
    if name.startswith("go_heavy_mock_"):
        return "heavy_mock"
    if name.startswith("go_heavy_"):
        return "heavy"
    return None

def get_connections(name):
    m = re.search(r"_c(\d+)$", name)
    return int(m.group(1)) if m else None

def analyze_scenario(path, rep):
    gctrace = path / "gctrace.log"
    if not gctrace.exists():
        return None

    result = {
        "rep": rep,
        "scenario": path.name,
        "language": "go",
        "variant": get_variant(path.name),
        "connections": get_connections(path.name)
    }

    summary = summarize(parse_gctrace(gctrace))
    if summary is None:
        result["status"] = "no_gc_events"
        return result

    result["status"] = "ok"
    result.update(summary)

    p99 = read_wrk_p99(path)
    if p99 is not None:
        result["wrk_p99_ms"] = p99
        result["stw_max_p99_ratio"] = summary["stw_max_ms"] / p99

    return result

def aggregate_metric(results, key):
    values = [
        r[key] for r in results
        if r.get("status") == "ok" and key in r
    ]
    if not values:
        return None
    return {
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "n": len(values)
    }

def aggregate_scenario(results):
    first = results[0]
    return {
        "scenario": first["scenario"],
        "language": "go",
        "variant": first["variant"],
        "connections": first["connections"],
        "aggregate": {
            "replications": len(results),
            "successful_replications": sum(
                r.get("status") == "ok" for r in results
            ),
            "failed_replications": sum(
                r.get("status") != "ok" for r in results
            ),
            "total_gc_cycles": aggregate_metric(results, "total_gc_cycles"),
            "stw_mean_ms": aggregate_metric(results, "stw_mean_ms"),
            "stw_median_ms": aggregate_metric(results, "stw_median_ms"),
            "stw_p95_ms": aggregate_metric(results, "stw_p95_ms"),
            "stw_p99_ms": aggregate_metric(results, "stw_p99_ms"),
            "stw_max_ms": aggregate_metric(results, "stw_max_ms"),
            "wrk_p99_ms": aggregate_metric(results, "wrk_p99_ms"),
            "stw_max_p99_ratio": aggregate_metric(results, "stw_max_p99_ratio")
        },
        "replications": results
    }

def rep_sort_key(path):
    m = re.fullmatch(r"rep(\d+)", path.name)
    return (0, int(m.group(1))) if m else (1, path.name)

def run_all_heavy(analysis_dir):
    if not analysis_dir.is_dir():
        print(f"Erro: diretório não encontrado: {analysis_dir}")
        sys.exit(1)

    reps = sorted(
        [
            p for p in analysis_dir.iterdir()
            if p.is_dir() and p.name.startswith("rep") and (p / "run").is_dir()
        ],
        key=rep_sort_key
    )

    grouped = {}

    for rep_dir in reps:
        run_dir = rep_dir / "run"
        for scenario_dir in sorted(run_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            if not (
                scenario_dir.name.startswith("go_heavy_")
                or scenario_dir.name.startswith("go_heavy_mock_")
            ):
                continue
            result = analyze_scenario(scenario_dir, rep_dir.name)
            if result:
                grouped.setdefault(result["scenario"], []).append(result)

    output = {
        "source_directory": str(analysis_dir),
        "replications_found": len(reps),
        "replications": [p.name for p in reps],
        "language": "go",
        "scenario_types": ["heavy", "heavy_mock"],
        "scenarios_analyzed": len(grouped),
        "results": [
            aggregate_scenario(grouped[name])
            for name in sorted(grouped)
        ]
    }

    output_file = analysis_dir / "gctrace_summary_all_reps.json"
    output_file.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    print(f"Replicações encontradas: {len(reps)}")
    print(f"Cenários agrupados: {len(grouped)}")
    print(f"Resumo salvo em: {output_file}")

def run_single(path):
    result = analyze_scenario(path, None)
    if result is None:
        print(f"Erro: {path / 'gctrace.log'} não encontrado")
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False))

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  analyze_gctrace.py <diretorio_do_cenario>")
        print("  analyze_gctrace.py <diretorio_analysis> --all-heavy")
        sys.exit(1)

    path = Path(sys.argv[1])
    if len(sys.argv) >= 3 and sys.argv[2] == "--all-heavy":
        run_all_heavy(path)
    else:
        run_single(path)

if __name__ == "__main__":
    main()