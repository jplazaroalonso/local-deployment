# Multi-Stage Build for Confidential Containers Payload
# Supports multi-architecture builds (AMD64/ARM64)

ARG TARGETARCH

# --- Stage 1: Clone & Patch ---
FROM golang:1.23 AS source
WORKDIR /src
ARG COCO_VERSION=v0.11.0
# Clone specific version to ensure stability
RUN git clone --depth 1 --branch ${COCO_VERSION} https://github.com/confidential-containers/enclave-cc.git .

# Apply Patches inline using heredocs
# 1. create.go patch
COPY <<EOF /src/src/shim/runtime/v2/rune/v2/create.go
package v2

import (
	"context"
	"os"
	"path/filepath"

	"github.com/confidential-containers/enclave-cc/src/shim/runtime/v2/rune/config"
	"github.com/confidential-containers/enclave-cc/src/shim/runtime/v2/rune/oci"
	shimtypes "github.com/confidential-containers/enclave-cc/src/shim/runtime/v2/rune/types"
	"github.com/containerd/containerd/runtime/v2/runc"
	taskAPI "github.com/containerd/containerd/runtime/v2/task"
	"github.com/opencontainers/runtime-spec/specs-go"
	"github.com/sirupsen/logrus"
)

var ContainerBase = "/run/enclave-cc/app"

func create(ctx context.Context, s *service, r *taskAPI.CreateTaskRequest) (*runc.Container, error) {
	ociSpec, err := config.LoadSpec(filepath.Join(r.Bundle, configFilename))
	if err != nil {
		return nil, err
	}

	containerType, err := oci.ContainerType(*ociSpec)
	if err != nil {
		return nil, err
	}
	sandboxNamespace, err := oci.SandboxNamespace(*ociSpec)
	if err != nil {
		return nil, err
	}

	var container *runc.Container

	switch containerType {
	case shimtypes.PodSandbox:
		container, err = handlePodSandbox(ctx, s, r, sandboxNamespace)
		if err != nil {
			return nil, err
		}
	case shimtypes.PodContainer:
		container, err = handlePodContainer(ctx, s, r, sandboxNamespace, ociSpec)
		if err != nil {
			return nil, err
		}
	}

	return container, nil
}

func handlePodSandbox(ctx context.Context, s *service, r *taskAPI.CreateTaskRequest, sandboxNamespace string) (*runc.Container, error) {
	container, err := runc.NewContainer(ctx, s.platform, r)
	if err != nil {
		return nil, err
	}

	if sandboxNamespace != shimtypes.KubeSystemNS {
		ar := &taskAPI.CreateTaskRequest{
			ID:       generateID(),
			Terminal: false,
			Options:  r.Options,
		}

		// Create agent enclave container
		agentContainer, err := createAgentContainer(ctx, s, ar)
		if err != nil {
			return nil, err
		}

		if err := writeAgentIDFile(r.Bundle, ar.ID); err != nil {
			return nil, err
		}

		s.agentID = ar.ID
		s.pauseID = r.ID
		s.containers[ar.ID] = agentContainer
		s.agent = &agent{
			ID:     agentContainer.ID,
			Bundle: agentContainer.Bundle,
			URL:    AgentURL,
		}

	}

	return container, nil
}

func handlePodContainer(ctx context.Context, s *service, r *taskAPI.CreateTaskRequest, sandboxNamespace string, ociSpec *specs.Spec) (*runc.Container, error) {
	if sandboxNamespace != shimtypes.KubeSystemNS {
		// BYPASS SEFS LOGIC for dynamic image support
		logrus.WithField("Rootfs", r.Rootfs).Info("Using existing Rootfs from containerd")
	}

	container, err := runc.NewContainer(ctx, s.platform, r)
	if err != nil {
		return nil, err
	}

	return container, nil
}

// readAgentIDFile reads the agent container id information from the path
func readAgentIDFile(path string) (string, error) {
	data, err := os.ReadFile(filepath.Join(path, agentIDFile))
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// writeAgentIDFile writes the agent container id information into the path
func writeAgentIDFile(path, id string) error {
	return os.WriteFile(filepath.Join(path, agentIDFile), []byte(id), defaultFilePerms)
}
EOF

# 2. images.rs patch
COPY <<EOF /src/src/enclave-agent/src/services/images.rs
use std::path::Path;
use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;
use image_rs::config::ImageConfig;
use image_rs::image::ImageClient;
use image_rs::snapshots;
use kata_sys_util::validate;
use log::info;
use protocols::image;
use tokio::sync::Mutex;
use ttrpc::{self, error::get_rpc_status as ttrpc_error};

use crate::config::DecryptConfig;

const CONTAINER_BASE: &str = "/run/enclave-cc/containers";

pub struct ImageService {
    dc: DecryptConfig,
    image_client: Arc<Mutex<ImageClient>>,
}

impl ImageService {
    pub fn new(dc: DecryptConfig) -> Self {
        let new_config = ImageConfig {
            default_snapshot: snapshots::SnapshotType::Overlay,
            security_validate: dc.security_validate.map_or(true, |v| v),
            ..Default::default()
        };
        Self {
            dc,
            image_client: Arc::new(Mutex::new(ImageClient {
                config: new_config,
                ..Default::default()
            })),
        }
    }

    async fn pull_image(&self, req: &image::PullImageRequest) -> Result<String> {
        let image = req.get_image();
        let cid = self.get_container_id(req)?;
        let source_creds = (!req.get_source_creds().is_empty()).then(|| req.get_source_creds());
        let bundle_path = Path::new(CONTAINER_BASE).join(&cid);

        let dc_string = self
            .dc
            .key_provider
            .to_owned()
            .map_or(String::default(), |v| v);
        let dc_str = if dc_string.is_empty() {
            None
        } else {
            Some(dc_string.as_str())
        };

        info!("Pulling {:?}", image);
        self.image_client
            .lock()
            .await
            .pull_image(image, &bundle_path, &source_creds, &dc_str)
            .await?;

        Ok(image.to_owned())
    }

    fn get_container_id(&self, req: &image::PullImageRequest) -> Result<String> {
        let cid = req.get_container_id().to_string();
        validate::verify_id(&cid)?;
        Ok(cid)
    }
}

#[async_trait]
impl protocols::image_ttrpc::Image for ImageService {
    async fn pull_image(
        &self,
        _ctx: &ttrpc::r#async::TtrpcContext,
        req: image::PullImageRequest,
    ) -> ttrpc::Result<image::PullImageResponse> {
        match self.pull_image(&req).await {
            Ok(r) => {
                info!("Pull image {:?} successfully", r);
                let mut resp = image::PullImageResponse::new();
                resp.image_ref = r;
                return Ok(resp);
            }
            Err(e) => {
                return Err(ttrpc_error(ttrpc::Code::INTERNAL, e.to_string()));
            }
        }
    }
}
EOF

# [ARM64 FIX] Remove 'keywrap-native' (SGX) and switch 'snapshot-unionfs' (Occlum) to 'snapshot-overlayfs'
RUN sed -i 's/"image-rs\/keywrap-native", //g' /src/src/enclave-agent/Cargo.toml && \
	sed -i 's/image-rs\/snapshot-unionfs/image-rs\/snapshot-overlayfs/g' /src/src/enclave-agent/Cargo.toml

# --- Stage 2: Build Shim (Go) ---
FROM golang:1.23-alpine AS shim-builder
ARG TARGETARCH
WORKDIR /build
# Copy full source to preserve relative dependencies
COPY --from=source /src /src
WORKDIR /src/src/shim

# Build shim based on architecture
RUN if [ "$TARGETARCH" = "arm64" ]; then \
	export GOARCH=arm64; \
	else \
	export GOARCH=amd64; \
	fi && \
	export GOOS=linux && \
	export CGO_ENABLED=0 && \
	go build -mod=vendor -o /build/containerd-shim-rune-v2 ./cmd/containerd-shim-rune-v2

# --- Stage 3: Build Agent (Rust) ---
# Use a cross-compilation image that supports musl linking for both arches
FROM messense/rust-musl-cross:aarch64-musl AS agent-builder-arm64
FROM messense/rust-musl-cross:x86_64-musl AS agent-builder-amd64

FROM agent-builder-${TARGETARCH} AS agent-builder
ARG TARGETARCH
USER root
WORKDIR /src
# Copy full source to preserve relative dependencies
COPY --from=source /src /src
WORKDIR /src/src/enclave-agent

# Configure cargo for static musl build
RUN if [ "$TARGETARCH" = "arm64" ]; then \
	export RUST_TARGET="aarch64-unknown-linux-musl"; \
	else \
	export RUST_TARGET="x86_64-unknown-linux-musl"; \
	fi && \
	rustup target add $RUST_TARGET && \
	cargo build --release --target $RUST_TARGET --no-default-features --features simple && \
	cp target/$RUST_TARGET/release/enclave-agent /agent-bin

# --- Stage 4: Assembly ---
FROM alpine:latest
WORKDIR /opt/enclave-cc-artifacts

# Copy binaries
COPY --from=shim-builder /build/containerd-shim-rune-v2 ./shim/
COPY --from=agent-builder /agent-bin ./agent/enclave-agent

# Config files (passed from build context via artifacts dir)
COPY artifacts/config.json ./
COPY artifacts/shim-rune-config.toml ./
COPY artifacts/enclave-cc.yaml ./runtimeclass/

CMD ["/bin/sh", "-c", "echo 'Payload Image Ready' && ls -R /opt/enclave-cc-artifacts"]
