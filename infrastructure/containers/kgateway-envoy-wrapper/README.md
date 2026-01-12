# kgateway envoy-wrapper

This container builds the envoy-wrapper (envoyinit) component from the kgateway source.

## Components

- **envoyinit**: Go wrapper that manages Envoy proxy configuration
- **Envoy**: The Envoy proxy binary (built from envoyproxy/envoy)

## Build

```bash
nerdctl -n k8s.io build \
  -t envoy-wrapper:v2.1.2 \
  --build-arg VERSION=v2.1.2 \
  .
```

## Notes

- This builds from the kgateway source at the specified VERSION tag
- The Envoy base image is from the official envoyproxy/envoy for ARM64 compatibility
- The envoyinit wrapper is built from `cmd/envoyinit` in the kgateway repo
