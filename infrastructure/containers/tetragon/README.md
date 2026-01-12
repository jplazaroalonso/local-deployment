# Tetragon Immutable Image

This directory contains the configuration and build instructions for creating an immutable Tetragon container image from source.

## Component Description
Tetragon provides eBPF-based transparent security observability and runtime enforcement. This build creates a minimal image for the Tetragon agent.

## Build Flow

```mermaid
graph TD
    subgraph Stage 1: Downloader
    A[Start] --> B[Alpine/Git]
    B -->|Clone Source| C[Source Code]
    end
    
    subgraph Stage 2: Builder
    C --> D[Golang Image]
    D -->|Make Tetragon| E[Compiled Binary]
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
   nerdctl build --build-arg VERSION=$VERSION -t tetragon:$VERSION .
   ```
