# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
RUN git clone --depth 1 --branch v1.19.2 https://github.com/cert-manager/cert-manager.git .

# Stage 2: Build
FROM golang:1.25 as builder
COPY --from=downloader /src /src
WORKDIR /src/cmd/controller
RUN CGO_ENABLED=0 go build -o /bin/controller .

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /bin/controller /app/cmd/controller/controller
ENTRYPOINT ["/app/cmd/controller/controller"]
