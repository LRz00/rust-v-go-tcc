FROM rust:1.83 AS builder

WORKDIR /app
COPY . .

RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/rust-api /usr/local/bin/rust-api
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/rust-api"]
