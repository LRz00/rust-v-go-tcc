# TCC - API Benchmarking Project

This repository contains a small benchmark project comparing two HTTP APIs (Go and Rust) backed by a PostgreSQL database. The repo includes Dockerfiles for each API and a `docker-compose.yml` to run everything together.

Contents
- `docker-compose.yml` — orchestration for PostgreSQL, Go API and Rust API
- `go-api/` — Go implementation and Dockerfile
- `rust-api/` — Rust implementation (Actix Web) and Dockerfile
- `init.sql` — SQL run by the Postgres container to initialize data
- `benchmark.sh` — small script that runs `wrk` load tests against both APIs

What the services do
- postgres: Postgres 16 database, seeded with `init.sql`.
- go-api: Listens on port 8080 (container). Exposes endpoint `/days-since` which reads `reference_date` from `base_date` and returns JSON: `{"days_since": <int>}`.
- rust-api: Listens on port 8080 inside its container, mapped to host 8081 by `docker-compose`. Endpoint `/days-since` returns the same JSON shape.

Ports (default from `docker-compose.yml`)
- Postgres: host 5432 -> container 5432
- Go API: host 8080 -> container 8080
- Rust API: host 8081 -> container 8080

Run locally with Docker Compose
1. Make sure Docker (and Docker Compose) are installed and running.
2. From the repo root run:

```bash
docker compose up --build
```

This will build both API images and start Postgres. The Postgres service uses a healthcheck; the APIs are configured to wait until Postgres is healthy.

API usage
- Go API: http://localhost:8080/days-since
- Rust API: http://localhost:8081/days-since

Both return JSON, example:

```json
{"days_since": 123}
```

Environment variables
- Postgres container variables are set in `docker-compose.yml` (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB).
- `go-api` supports overriding the DB connection via `DATABASE_URL` environment variable (example: `host=postgres user=tcc password=tcc dbname=tcc sslmode=disable`). It also accepts a `PORT` env var to change the listening port.
- `rust-api` reads `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` env vars (defaults hard-coded to match `docker-compose.yml`).

Running the benchmarks
The provided `benchmark.sh` uses `wrk` to stress test both APIs at various connection counts. Example (from repo root):

```bash
# ensure wrk is installed (Debian/Ubuntu example)
sudo apt update && sudo apt install -y wrk

# make script executable and run
chmod +x benchmark.sh
./benchmark.sh
```

Notes and troubleshooting
- If an API returns errors when starting, check container logs:
  - `docker compose logs go-api`
  - `docker compose logs rust-api`
  - `docker compose logs postgres`
- If the DB is not reachable, confirm `POSTGRES_HOST` inside `rust-api` or `DATABASE_URL` for the Go app points to `postgres` (the compose service name) when running under Docker Compose.
- The `depends_on` with `condition: service_healthy` in `docker-compose.yml` requires a Docker Compose engine that supports healthcheck-based dependencies (Compose v2 behavior).

Running the services without Docker (dev)
- Go:
  - cd `go-api`
  - `go run main.go` (set `DATABASE_URL` environment variable if needed)
- Rust:
  - cd `rust-api`
  - `cargo run --release` (set `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` as needed)

Files to look at
- `init.sql` — seeds `base_date` used by both APIs
- `go-api/main.go` — Go implementation
- `rust-api/src/main.rs` — Rust implementation
- `benchmark.sh` — wrk-based benchmark script


