# Open Policy Agent (OPA) Immutable Image

This directory contains the configuration and build instructions for creating an immutable OPA container image from source.

## Component Description
Open Policy Agent (OPA) is an open source, general-purpose policy engine that unifies policy enforcement across the stack. This build creates a minimal image for the OPA agent.

## Build Flow

```mermaid
graph TD
    subgraph Stage 1: Downloader
    A[Start] --> B[Alpine/Git]
    B -->|Clone Source| C[Source Code]
    end
    
    subgraph Stage 2: Builder
    C --> D[Golang Image]
    D -->|Go Build OPA| E[Compiled Binary]
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
   nerdctl build --build-arg VERSION=$VERSION -t opa:$VERSION .
   ```
