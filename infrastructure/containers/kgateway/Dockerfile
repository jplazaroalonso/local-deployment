# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/kgateway-dev/kgateway.git .

# Stage 2: Build
FROM golang:1.25 as builder
WORKDIR /src
COPY --from=downloader /src .
RUN CGO_ENABLED=0 go build -o kgateway ./cmd/kgateway

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /src/kgateway /usr/local/bin/kgateway
ENTRYPOINT ["/usr/local/bin/kgateway"]
