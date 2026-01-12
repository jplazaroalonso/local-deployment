# Rancher Desktop Infrastructure

This directory contains the operational components, scripts, and artifacts required to set up and manage Confidential Containers (CoCo) on Rancher Desktop.

## Contents

*   **`scripts/`**: Automation scripts.
    *   `manage_coco.py`: The main entry point for setting up, building, and validating the CoCo environment.
*   **`artifacts/`**: Configuration files and manifests generated or used during the setup process.
*   **Infrastructure References**:
    *   **Payload Build**: `infrastructure/containers/coco-payload/`
    *   **Deployments**: `infrastructure/deployments/confidential-containers/`

## Usage

The primary interaction with this directory is through the `manage_coco.py` script.

```bash
# Run from the root of the monorepo or this directory
python3 infrastructure/rancher-desktop/scripts/manage_coco.py setup
```

For detailed setup instructions, please refer to the **[Documentation](../../docs/rancher/README.md)** directory.
