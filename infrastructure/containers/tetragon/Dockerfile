# Stage 1: Download Source
FROM alpine/git:latest as downloader
WORKDIR /src
ARG VERSION
RUN git clone --depth 1 --branch ${VERSION} https://github.com/cilium/tetragon.git .

# Stage 2: Build
FROM golang:1.25 as builder
WORKDIR /src
COPY --from=downloader /src .

# Install BPF build dependencies
RUN apt-get update && apt-get install -y \
    clang \
    llvm \
    gcc \
    make \
    libbpf-dev \
    && rm -rf /var/lib/apt/lists/*

# Build Tetragon (forcing local BPF build if possible, or compiling manually)
# Trying standard make, assuming it detects clang. If not, we might need specific flags.
# Using 'tetragon-bpf-local' if available, otherwise trying to bypass docker check.
# The previous log showed make -C bpf invoked.
# Let's try to set CLANG=clang and see if it avoids docker.
# Or check if there is a 'local' target.
# Assumption: running 'make -C bpf' directly might work.
RUN make -C bpf && make -C bpf objs/bpf_alignchecker.o && make tetragon

# Stage 3: Final Immutable Image
FROM gcr.io/distroless/static:latest
USER 0:0
COPY --from=builder /src/tetragon /usr/local/bin/tetragon
# Copy BPF object files
COPY --from=builder /src/bpf/objs /var/lib/tetragon/
COPY --from=builder /src/bpf/objs/bpf_alignchecker.o /var/lib/tetragon/
ENTRYPOINT ["/usr/local/bin/tetragon"]
