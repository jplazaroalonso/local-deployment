# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/goharbor/harbor.git .

# Stage 2: Build
FROM golang:1.23 as builder
WORKDIR /src
COPY --from=downloader /src .
RUN make exporter

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /src/make/common/binary/harbor_exporter /usr/local/bin/harbor_exporter
ENTRYPOINT ["/usr/local/bin/harbor_exporter"]
