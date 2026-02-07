# Gatekeeper Dockerfile
# Permission routing sidecar for Fleetclaw

FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum* ./
RUN go mod download

# Copy source
COPY *.go ./

# Build
RUN CGO_ENABLED=0 GOOS=linux go build -o gatekeeper .

# Runtime image
FROM alpine:3.19

RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /app/gatekeeper .

# Default port
ENV GATEKEEPER_PORT=8081
ENV AGENT_PORT=8080

EXPOSE 8081

CMD ["./gatekeeper"]
