# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/goharbor/harbor.git .

# Stage 2: Build
FROM golang:1.23 as builder
WORKDIR /src
COPY --from=downloader /src .
# Trivy adapter source is in src/pkg/trivyadapter or similar, usually built via make
RUN make trivy-adapter

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /src/make/common/binary/trivy-adapter /usr/local/bin/trivy-adapter
ENTRYPOINT ["/usr/local/bin/trivy-adapter"]
