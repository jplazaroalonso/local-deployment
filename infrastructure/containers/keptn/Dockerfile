# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/keptn/lifecycle-toolkit.git .

# Stage 2: Build
FROM golang:1.23 as builder
WORKDIR /src
COPY --from=downloader /src .
# Keptn V2 (Lifecycle Toolkit) typically builds operator
WORKDIR /src/lifecycle-operator
RUN go build -o ../keptn-operator main.go


# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /src/keptn-operator /usr/local/bin/keptn-operator
ENTRYPOINT ["/usr/local/bin/keptn-operator"]
