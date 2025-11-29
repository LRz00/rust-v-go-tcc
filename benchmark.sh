#!/bin/bash

echo "=============================="
echo "Benchmark API Go"
echo "=============================="

for CONN in 10 50 100 300 500
do
  echo ""
  echo "Go - Conexões: $CONN"
  wrk -t4 -c$CONN -d30s http://localhost:8080/days-since
done

echo ""
echo "=============================="
echo "Benchmark API Rust"
echo "=============================="

for CONN in 10 50 100 300 500
do
  echo ""
  echo "Rust - Conexões: $CONN"
  wrk -t4 -c$CONN -d30s http://localhost:8081/days-since
done
