# Stage 1: Build UI
FROM node:22-bookworm AS ui-builder
ARG VERSION
WORKDIR /src
RUN git clone --depth 1 --branch ${VERSION} https://github.com/argoproj/argo-cd.git .
WORKDIR /src/ui
RUN yarn install --frozen-lockfile && \
    yarn build

# Stage 2: Build Binaries
FROM golang:1.24 AS builder
ARG VERSION
WORKDIR /src
COPY --from=ui-builder /src .
ENV CGO_ENABLED=0
# Build the unified binary with version flags
RUN /bin/sh -c 'CLEAN_VERSION=$(echo "$VERSION" | sed "s/^v//"); \
    echo "Original VERSION: $VERSION"; \
    echo "Clean VERSION: $CLEAN_VERSION"; \
    go build -v -ldflags="-X github.com/argoproj/argo-cd/v2/common.version=$CLEAN_VERSION" -o /usr/local/bin/argocd ./cmd'

# Stage 3: Final Image
FROM debian:bookworm-slim

# Create non-root user
RUN groupadd -g 999 argocd && \
    useradd -r -u 999 -g argocd argocd

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    gnupg \
    openssh-client \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Kustomize
RUN curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash && \
    mv kustomize /usr/local/bin/

# Install Helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh && \
    rm get_helm.sh

# Copy built binary
COPY --from=builder /usr/local/bin/argocd /usr/local/bin/argocd

# Create symlinks
RUN ln -s /usr/local/bin/argocd /usr/local/bin/argocd-server && \
    ln -s /usr/local/bin/argocd /usr/local/bin/argocd-repo-server && \
    ln -s /usr/local/bin/argocd /usr/local/bin/argocd-application-controller && \
    ln -s /usr/local/bin/argocd /usr/local/bin/argocd-applicationset-controller && \
    ln -s /usr/local/bin/argocd /usr/local/bin/argocd-notifications-controller && \
    ln -s /usr/local/bin/argocd /usr/local/bin/argocd-notifications

# Copy wrapper scripts
COPY --from=builder /src/hack/git-verify-wrapper.sh /usr/local/bin/
COPY --from=builder /src/hack/gpg-wrapper.sh /usr/local/bin/

USER 999
WORKDIR /app
