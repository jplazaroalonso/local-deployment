# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/open-policy-agent/opa.git .

# Stage 2: Build
FROM golang:1.23 as builder
WORKDIR /src
COPY --from=downloader /src .
RUN go build -o opa ./

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /src/opa /usr/local/bin/opa
ENTRYPOINT ["/usr/local/bin/opa"]
