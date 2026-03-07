# Makefile for the TCC benchmarking project
# Usage: make <target>

.PHONY: help build up down logs bench run-go-local run-rust-local curl-go curl-rust

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Common targets:"
	@echo "  build             Build docker images (docker compose build)"
	@echo "  up                Start services (docker compose up --build)"
	@echo "  down              Stop services (docker compose down)"
	@echo "  logs              Follow docker compose logs for all services"
	@echo "  run-go-local      Run the Go API locally (requires Go)"
	@echo "  run-rust-local    Run the Rust API locally (requires Rust/Cargo)"
	@echo "  bench             Run the provided benchmark.sh (requires wrk)"
	@echo "  curl-go           Query the Go API (/days-since)"
	@echo "  curl-rust         Query the Rust API (/days-since)"

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

run-go-local:
	@echo "Running Go API locally (press Ctrl+C to stop)"
	cd go-api && go run main.go

run-rust-local:
	@echo "Running Rust API locally (press Ctrl+C to stop)"
	cd rust-api && cargo run --release

bench:
	@echo "Running benchmark.sh (ensure wrk is installed)"
	chmod +x benchmark.sh && ./benchmark.sh

curl-go:
	@echo "Querying Go API: http://localhost:8080/days-since"
	curl -s http://localhost:8080/days-since | jq . || curl -s http://localhost:8080/days-since

curl-rust:
	@echo "Querying Rust API: http://localhost:8081/days-since"
	curl -s http://localhost:8081/days-since | jq . || curl -s http://localhost:8081/days-since
