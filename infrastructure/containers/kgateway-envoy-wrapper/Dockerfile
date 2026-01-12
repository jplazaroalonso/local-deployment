# Stage 1: Download Source
FROM --platform=linux/amd64 alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/kgateway-dev/kgateway.git .

# Stage 2: Build envoyinit wrapper (cross-compile for amd64 if needed, or build on amd64 base)
FROM --platform=linux/amd64 golang:1.25 as builder
WORKDIR /src
COPY --from=downloader /src .
# Ensure we build for AMD64
RUN CGO_ENABLED=0 GOARCH=amd64 go build -o envoyinit ./cmd/envoyinit/...

# Stage 3: Prepare Envoy base - use upstream wrapper image for binary
# This ensures we have the correct Envoy build (Gloo extensions) for AMD64
FROM --platform=linux/amd64 cr.kgateway.dev/kgateway-dev/envoy-wrapper:v2.1.2 as envoy-base

# Stage 4: Final Immutable Image
FROM --platform=linux/amd64 debian:bookworm-slim

# Copy Envoy binary from upstream base (it has the required filters)
COPY --from=envoy-base /usr/local/bin/envoy /usr/local/bin/envoy

# Copy envoyinit wrapper (built from source)
COPY --from=builder /src/envoyinit /usr/local/bin/envoyinit

# Copy docker-entrypoint script
COPY --from=downloader /src/cmd/envoyinit/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create non-root user
RUN groupadd -g 1000 envoy && useradd -r -u 1000 -g envoy envoy

# Install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

USER envoy

ENTRYPOINT ["/docker-entrypoint.sh"]
