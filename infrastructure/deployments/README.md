# Infrastructure Deployments

This directory contains the Kubernetes deployment configurations.

## Structure

*   **`kustomize/`**: Contains Kustomize bases and overlays.
    *   **`confidential-containers/`**: Kustomize configuration for CoCo resources.
*   **`kubernetes/`**: Contains raw Kubernetes manifests.
    *   **`confidential-containers/`**: Manifests for CoCo (RuntimeClass, CcRuntime).

## Usage

To apply the Confidential Containers configuration via Kustomize:

```bash
kubectl apply -k infrastructure/deployments/kustomize/confidential-containers
```

Note: The `CcRuntime` resource is currently managed dynamically by `manage_coco.py` to handle local image tags and patching, but a sample is provided in `kubernetes/confidential-containers/cc-runtime-sample.yaml`.
