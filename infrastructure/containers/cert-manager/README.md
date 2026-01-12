# Cert-Manager Immutable Image

This directory contains the configuration and build instructions for creating an immutable Cert-Manager container image from source.

## Component Description
Cert-Manager automates the management and issuance of TLS certificates in Kubernetes. This build creates a minimal image for the Cert-Manager controller.

## Build Flow

```mermaid
graph TD
    subgraph Stage 1: Downloader
    A[Start] --> B[Alpine/Git]
    B -->|Clone Source| C[Source Code]
    end
    
    subgraph Stage 2: Builder
    C --> D[Golang Image]
    D -->|Make Build| E[Compiled Binary]
    end
    
    subgraph Stage 3: Final
    E --> F[Distroless Static]
    F -->|Copy Binary| G[Final Immutable Image]
    end
```

## How to Build
This image is designed to be built using `nerdctl` and stored in the local containerd namespace.

1. **Check Version**: Ensure `config.yaml` specifies the desired version.
2. **Build Command**:
   ```bash
   # Extract version from config
   VERSION=$(grep 'version:' config.yaml | awk '{print $2}' | tr -d '"')
   
   # Build with nerdctl
   nerdctl build --build-arg VERSION=$VERSION -t cert-manager:$VERSION .
   ```
