FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY . .

RUN go build -o go-api

FROM alpine:3.19

WORKDIR /
COPY --from=builder /app/go-api /go-api

RUN chmod +x /go-api

EXPOSE 8080
CMD ["/go-api"]
