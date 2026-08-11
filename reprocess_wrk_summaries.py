#!/usr/bin/env python3
"""
Reprocessa todos os wrk_output.txt já coletados, gerando um novo
wrk_summary_fixed.json ao lado de cada wrk_summary.json original,
SEM sobrescrever os arquivos existentes.

Corrige dois bugs identificados por auditoria cruzada entre a saída
bruta do wrk e os campos extraídos:

  1. requests_per_sec: o parser original (benchmark.sh) capturava a
     linha "Req/Sec" da seção "Thread Stats" do wrk, que é a média
     POR THREAD, não o total agregado do teste. O valor correto é o
     da linha separada "Requests/sec:", ao final do output.

  2. errors (Non-2xx/3xx): o parser original usava
     `grep -oE "[0-9]+" | head -1` na linha "Non-2xx or 3xx responses: N",
     capturando o primeiro dígito que aparece na linha inteira — que é
     o "2" do próprio texto "2xx", não o valor N no final da linha.

  3. socket_errors (timeout): mesma classe de bug do item 2, mas na
     linha "Socket errors: connect X, read Y, write Z, timeout W" —
     o valor relevante para "erro de fato" é apenas o de timeout, não
     connect/read/write (que não representam requisições falhas do
     ponto de vista de erro HTTP).

Uso:
    python3 reprocess_wrk_summaries.py <diretorio_raiz>

Onde <diretorio_raiz> é, por exemplo, benchmark_results_replicated —
o script varre recursivamente por qualquer wrk_output.txt encontrado.
"""

import json
import re
import sys
from pathlib import Path


def parse_wrk_output_fixed(wrk_output: str) -> dict:
    """Reimplementação corrigida do parsing feito em benchmark.sh
    (função parse_wrk_output), preservando o MESMO formato de saída
    de wrk_summary.json para compatibilidade com analyze_results.py."""

    lines = wrk_output.splitlines()

    # --- Latência (Thread Stats) — não afetada pelos bugs, mantém a
    # mesma lógica do parser original ---
    latency_avg = latency_stdev = latency_max = "0ms"
    for line in lines:
        if re.match(r"^\s+Latency\s", line):
            parts = line.split()
            # ["Latency", avg, stdev, max, "+/-", "Stdev"]
            if len(parts) >= 4:
                latency_avg, latency_stdev, latency_max = parts[1], parts[2], parts[3]
            break

    # --- Percentis customizados (script Lua) — não afetados ---
    latency_p95 = "0"
    latency_p99 = "0"
    for line in lines:
        if line.strip().startswith("P95:"):
            latency_p95 = line.split("P95:")[1].strip()
        elif line.strip().startswith("P99:"):
            latency_p99 = line.split("P99:")[1].strip()

    # --- Total de requisições / duração / transfer (linha "requests in") ---
    total_requests = "0"
    total_time = "0s"
    for line in lines:
        m = re.search(r"([\d.]+[kKmM]?) requests in ([\d.]+\w+),", line)
        if m:
            total_requests = m.group(1)
            total_time = m.group(2)
            break

    # --- Transfer/sec (mantido igual ao original, mesmo sendo taxa e
    # não total — não afeta nenhuma métrica de H1-H5) ---
    total_read = "0"
    for line in lines:
        if "Transfer/sec:" in line:
            parts = line.split()
            if len(parts) >= 2:
                total_read = parts[1]
            break

    # --- BUG 1 CORRIGIDO: requests_per_sec deve vir da linha agregada
    # "Requests/sec:", não da linha "Req/Sec" dentro de Thread Stats ---
    req_sec_avg = "0"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Requests/sec:"):
            parts = stripped.split(":", 1)[1].strip().split()
            if parts:
                req_sec_avg = parts[0]
            break

    # stdev/max por-thread são mantidos como informação complementar
    # (não usados como throughput agregado), extraídos da linha
    # "Req/Sec" de Thread Stats, agora corretamente rotulados.
    req_sec_thread_stdev = "0"
    req_sec_thread_max = "0"
    for line in lines:
        if re.match(r"^\s+Req/Sec\s", line):
            parts = line.split()
            if len(parts) >= 4:
                req_sec_thread_stdev, req_sec_thread_max = parts[2], parts[3]
            break

    # --- BUG 2 CORRIGIDO: Non-2xx/3xx — extrai o número APÓS o ":",
    # não o primeiro dígito da linha inteira ---
    non2xx = 0
    for line in lines:
        if "Non-2xx" in line:
            after_colon = line.split(":", 1)[1] if ":" in line else ""
            m = re.search(r"(\d+)", after_colon)
            if m:
                non2xx = int(m.group(1))
            break

    # --- BUG 3 CORRIGIDO: Socket errors — extrai especificamente o
    # valor de "timeout", não o primeiro número da linha ---
    socket_timeout_errors = 0
    for line in lines:
        if "Socket errors" in line:
            m = re.search(r"timeout\s+(\d+)", line)
            if m:
                socket_timeout_errors = int(m.group(1))
            break

    total_errors = non2xx + socket_timeout_errors

    return {
        "latency": {
            "avg": latency_avg,
            "stdev": latency_stdev,
            "max": latency_max,
            "p95": latency_p95,
            "p99": latency_p99,
        },
        "requests_per_sec": {
            "avg": req_sec_avg,
            "stdev": req_sec_thread_stdev,
            "max": req_sec_thread_max,
        },
        "total": {
            "requests": total_requests,
            "duration": total_time,
            "transfer": total_read,
        },
        "errors": str(total_errors),
        # Campos extras de auditoria, não usados por analyze_results.py,
        # mas úteis para conferência manual do reprocessamento.
        "_audit": {
            "non2xx_or_3xx": non2xx,
            "socket_timeout_errors": socket_timeout_errors,
        },
    }


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 reprocess_wrk_summaries.py <diretorio_raiz>")
        sys.exit(1)

    root = Path(sys.argv[1])
    if not root.exists():
        print(f"Erro: {root} não encontrado")
        sys.exit(1)

    wrk_output_files = list(root.rglob("wrk_output.txt"))
    print(f"Encontrados {len(wrk_output_files)} arquivos wrk_output.txt em {root}")

    processed = 0
    changed_throughput = 0
    changed_errors = 0
    errors_found = []

    for wrk_output_path in wrk_output_files:
        try:
            wrk_output = wrk_output_path.read_text()
            fixed = parse_wrk_output_fixed(wrk_output)

            out_path = wrk_output_path.parent / "wrk_summary_fixed.json"
            with open(out_path, "w") as f:
                json.dump(fixed, f, indent=4)

            # Compara com o original, se existir, para relatório de mudanças
            original_path = wrk_output_path.parent / "wrk_summary.json"
            if original_path.exists():
                original = json.loads(original_path.read_text())
                orig_thr = original.get("requests_per_sec", {}).get("avg", "0")
                fixed_thr = fixed["requests_per_sec"]["avg"]
                if str(orig_thr) != str(fixed_thr):
                    changed_throughput += 1

                orig_err = str(original.get("errors", "0"))
                fixed_err = str(fixed["errors"])
                if orig_err != fixed_err:
                    changed_errors += 1

            processed += 1
        except Exception as e:
            errors_found.append((str(wrk_output_path), str(e)))

    print(f"\nProcessados com sucesso: {processed}")
    print(f"Arquivos onde requests_per_sec mudou: {changed_throughput}")
    print(f"Arquivos onde errors mudou: {changed_errors}")

    if errors_found:
        print(f"\nFalhas ao processar {len(errors_found)} arquivo(s):")
        for path, err in errors_found[:20]:
            print(f"  {path}: {err}")

    print(f"\nArquivos 'wrk_summary_fixed.json' gerados ao lado de cada wrk_summary.json original.")
    print("Nenhum arquivo original foi sobrescrito.")


if __name__ == "__main__":
    main()