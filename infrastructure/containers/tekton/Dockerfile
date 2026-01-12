# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/tektoncd/pipeline.git .

# Stage 2: Build
FROM golang:1.24 as builder
WORKDIR /src
COPY --from=downloader /src .
ARG CACHEBUST=1
RUN ls -F ./cmd
ENV CGO_ENABLED=0
# Build all required binaries present in cmd
RUN go build -o tekton-controller ./cmd/controller && \
    go build -o tekton-webhook ./cmd/webhook && \
    go build -o tekton-entrypoint ./cmd/entrypoint && \
    go build -o tekton-nop ./cmd/nop && \
    go build -o tekton-resolvers ./cmd/resolvers && \
    go build -o tekton-sidecarlogresults ./cmd/sidecarlogresults && \
    go build -o tekton-workingdirinit ./cmd/workingdirinit && \
    go build -o tekton-events ./cmd/events

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
# Copy all binaries to /usr/local/bin
COPY --from=builder /src/tekton-controller /usr/local/bin/controller
COPY --from=builder /src/tekton-webhook /usr/local/bin/webhook
COPY --from=builder /src/tekton-entrypoint /usr/local/bin/entrypoint
COPY --from=builder /src/tekton-nop /usr/local/bin/nop
COPY --from=builder /src/tekton-resolvers /usr/local/bin/resolvers
COPY --from=builder /src/tekton-sidecarlogresults /usr/local/bin/sidecarlogresults
COPY --from=builder /src/tekton-workingdirinit /usr/local/bin/workingdirinit
COPY --from=builder /src/tekton-events /usr/local/bin/events

# Default entrypoint (can be overridden)
ENTRYPOINT ["/usr/local/bin/controller"]
