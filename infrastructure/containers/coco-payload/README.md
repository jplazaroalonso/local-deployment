# Confidential Containers Payload

This directory contains the build assets for the Confidential Containers (CoCo) payload image.

## Contents

*   **`Dockerfile`**: Multi-stage build for the payload image.
*   **`patches/`**: Source code patches for components (e.g., integrity checks, config adaptations).

## Usage

This image is built via the `manage_coco.py` script located in `infrastructure/rancher-desktop/scripts/`.

```bash
# Example build trigger
python3 infrastructure/rancher-desktop/scripts/manage_coco.py build
```
