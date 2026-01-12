#!/usr/bin/env python3
import argparse
import platform
import subprocess
import sys
import shutil
import time
import os

"""
manage_coco.py - Unified Management Script for Confidential Containers on Rancher Desktop

This script handles the automated setup and validation of CoCo.
It is designed to work across macOS (ARM64/Intel), Linux, and Windows (WSL2).

KEY PARAMETERS (Internal Configuration):
----------------------------------------
1. COCO_OPERATOR_REF (v0.12.0):
   We pin to version 0.12.0 of the operator. Newer versions or unstable branches 
   may have breaking changes or missing index images for ARM64.

2. PAYLOAD_IMAGE (enclave-cc-SIM-sample-kbc-latest):
   On macOS/ARM64 and WSL, we lack real Trusted Execution Environment (TEE) hardware 
   (like Intel TDX or AMD SEV). We use a 'Simulation' (SIM) payload which runs 
   the CoCo stack (guest kernel + shim) in QEMU without hardware encryption.
   
3. RUNTIME_CLASSES:
   The script configures 'kata', 'kata-qemu', and 'kata-clh'.
   On validation, it auto-detects 'enclave-cc' (created by the SIM payload) or falls back to 'kata-qemu'.

PROCESS FLOW:
-------------
[SETUP]
1. Label Nodes: Applies 'confidentialcontainers.org/enabled=true' to allow scheduling.
2. Install Operator: Applies the Kustomize manifests from the official repo.
3. Configure CcRuntime:
   - Creates a 'CcRuntime' CRD instance.
   - PATCHING: Rancher Desktop's VM is often Alpine Linux (OpenRC-based), while CoCo 
     expects Systemd. We inject a shell script ('installCmd') that:
     a. Replaces 'systemctl' calls with 'rc-service'.
     b. Installs 'containerd-shim-rune-v2' to '/usr/bin' with 'install -m 755' to fix permission issues.
   - Volumes: Mounts host paths (/opt/confidential-containers, /etc/*) to persist binaries.

[VALIDATE]
1. Runtime Detection: Scans cluster for 'enclave-cc', 'kata-qemu', or 'kata'.
2. Pod Deployment: Deploys a simple Nginx pod securely.
3. Verification: Checks if the pod reaches 'Running' state.
"""

# =============================================================================
# Constants
# =============================================================================

# COCO_OPERATOR_URL removed in favor of kustomize URL in setup_coco
# Using a temp file for the CcRuntime manifest
CC_RUNTIME_MANIFEST = "cc-runtime.yaml"

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BLUE = '\033[94m'

def log_info(msg):
    print(f"{Colors.GREEN}[INFO]{Colors.RESET} {msg}")

def log_warn(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")

def log_error(msg):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_section(title):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}  {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def ask_confirm(question):
    """Interactively ask for user confirmation."""
    while True:
        choice = input(f"{Colors.YELLOW}[?] {question} (y/n): {Colors.RESET}").lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False


# =============================================================================
# Platform Detection
# =============================================================================

def detect_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if "microsoft" in platform.uname().release.lower():
        system = "wsl"
        
    return system, machine

# =============================================================================
# Kubernetes Helpers
# =============================================================================

def run_kubectl(args, input_data=None):
    cmd = ["kubectl"] + args
    try:
        proc = subprocess.run(
            cmd, 
            input=input_data if input_data else None,
            capture_output=True, 
            text=True, 
            check=True
        )
        return proc.stdout.strip()
    except subprocess.CalledProcessError as e:
        log_error(f"kubectl command failed: {' '.join(cmd)}")
        log_error(e.stderr)
        raise e

def wait_for_pod(namespace, label_selector, timeout=300):
    log_info(f"Waiting for pod with label {label_selector} in {namespace} to be Running...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            status = run_kubectl([
                "get", "pods", "-n", namespace, "-l", label_selector, 
                "-o", "jsonpath='{.items[0].status.phase}'"
            ])
            # Handle potential quote wrapping
            status = status.strip("'")
            if status == "Running":
                return True
        except:
            pass
        time.sleep(5)
    return False

def wait_for_crd(crd_name, timeout=60):
    log_info(f"Waiting for CRD {crd_name} to be established...")
    cmd = ["wait", "--for", "condition=established", f"crd/{crd_name}", f"--timeout={timeout}s"]
    try:
        run_kubectl(cmd)
        log_info(f"CRD {crd_name} is ready.")
        return True
    except:
        log_warn(f"Timed out waiting for CRD {crd_name}.")
        return False

# =============================================================================
# Handlers
# =============================================================================

def check_prereqs():
    log_section("Checking Prerequisites")
    
    # 1. Check kubectl
    if not shutil.which("kubectl"):
        log_warn("kubectl not found in PATH.")
        system, machine = detect_platform() # Get platform info here for install_kubectl
        if ask_confirm("Do you want to attempt to install kubectl automatically?"):
             install_kubectl(system, machine)
             if not shutil.which("kubectl"):
                 log_error("Installation failed or kubectl still not in PATH. Please install manually.")
                 return False
        else:
            return False
    log_info("kubectl found.")
    
    # 2. Check cluster connection
    try:
        run_kubectl(["cluster-info"])
        log_info("Connected to Kubernetes cluster.")
    except:
        log_error("Cannot connect to Kubernetes cluster. Is Rancher Desktop running?")
        return False

    # 3. OS Checks
    system, machine = detect_platform()
    log_info(f"Detected Platform: OS={system}, Arch={machine}")
    
    if system == "linux":
        # Check KVM permissions
        if not os.access("/dev/kvm", os.W_OK):
            log_warn("/dev/kvm is not writable by current user.")
            if ask_confirm(f"Add user '{os.environ.get('USER')}' to 'kvm' group? (Requires sudo)"):
                try:
                    subprocess.run(["sudo", "usermod", "-aG", "kvm", os.environ.get("USER")], check=True)
                    log_info("User added to kvm group. REMINDER: You may need to log out and back in for this to take effect.")
                    log_warn("Assuming checking continues...")
                except subprocess.CalledProcessError:
                    log_error("Failed to add user to kvm group.")
            else:
                log_warn("Skipping KVM permission fix. CoCo may fail.")

    if system == "wsl":
        # Check for nested virtualization (best effort)
        try:
            with open("/dev/kvm", "r") as f:
                pass
            log_info("KVM device node found (/dev/kvm).")
        except:
            log_warn("/dev/kvm not readable. Ensure 'nestedVirtualization=true' is set in .wslconfig")
            
    return True

def install_kubectl(system, machine):
    log_info("Attempting to install kubectl...")
    
    # Determine URL
    dl_url = ""
    if system == "darwin":
        arch = "arm64" if machine in ["arm64", "aarch64"] else "amd64"
        dl_url = f"https://dl.k8s.io/release/v1.29.0/bin/darwin/{arch}/kubectl"
    elif system in ["linux", "wsl"]:
         arch = "arm64" if machine in ["arm64", "aarch64"] else "amd64"
         dl_url = f"https://dl.k8s.io/release/v1.29.0/bin/linux/{arch}/kubectl"
    else:
        log_error(f"Auto-install not supported for {system}/{machine}")
        return

    try:
        log_info(f"Downloading kubectl from {dl_url}...")
        subprocess.run(["curl", "-LO", dl_url], check=True)
        subprocess.run(["chmod", "+x", "kubectl"], check=True)
        
        log_info("Moving kubectl to /usr/local/bin/ (may ask for sudo password)...")
        subprocess.run(["sudo", "mv", "kubectl", "/usr/local/bin/kubectl"], check=True)
        log_info("kubectl installed successfully.")
    except Exception as e:
        log_error(f"Failed to install kubectl: {e}")



# =============================================================================
# Build Logic
# =============================================================================

def load_config(infra_dir):
    config_path = os.path.join(infra_dir, "config.yaml")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    if ':' in line and not line.strip().startswith('#'):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")
        except Exception as e:
            log_warn(f"Failed to parse config.yaml: {e}. Using defaults.")
    else:
        log_warn(f"config.yaml not found at {config_path}. Using defaults.")
    return config

def build_coco():
    log_section("Building Custom CoCo Payload")
    
    system, machine = detect_platform()
    log_info(f"Detected Platform for Build: OS={system}, Arch={machine}")
    
    # Determine Arch for Docker
    target_arch = "amd64"
    if machine in ["arm64", "aarch64"]:
        target_arch = "arm64"
    
    log_info(f"Target Architecture: {target_arch}")
    
    # Use local tag
    image_name = "k8s.io/coco-payload-arm64:local"
    
    # Determine absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Script is in infrastructure/rancher-desktop/scripts
    # We want to go to infrastructure/containers/coco-payload
    
    # Go up to 'infrastructure'
    # script_dir = .../infrastructure/rancher-desktop/scripts
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir))) # Assuming we are deep
    # Actually, simpler:
    # script_dir = infrastructure/rancher-desktop/scripts
    # ../.. = infrastructure
    infra_dir = os.path.dirname(os.path.dirname(script_dir))
    
    config = load_config(infra_dir)
    coco_version = config.get("coco_payload_version", "v0.11.0")

    payload_dir = os.path.join(infra_dir, "containers", "coco-payload")
    
    if not os.path.exists(payload_dir):
        log_error(f"Payload directory not found at {payload_dir}")
        sys.exit(1)

    # Prepare Build Context
    # We build in a temp dir in the infrastructure/containers/coco-payload/build-ctx to keep it local?
    # Or keep using infrastructure/rancher-desktop/payload-build-ctx?
    # Let's use a temp dir relative to the script for artifacts, but point the build content correctly.
    
    rancher_desktop_dir = os.path.dirname(script_dir)
    build_ctx = os.path.join(rancher_desktop_dir, "payload-build-ctx")
    
    if os.path.exists(build_ctx):
        shutil.rmtree(build_ctx)
    os.makedirs(build_ctx)
    os.makedirs(os.path.join(build_ctx, "artifacts"))
    
    # Patches are now embedded in Dockerfile, so NO COPY needed.
    
    # Generate Config Files
    log_info(f"Generating configuration files in {build_ctx}/artifacts/...")
    
    # enclave-cc.yaml
    enclave_cc_yaml = """
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: enclave-cc
handler: enclave-cc
scheduling:
  nodeSelector:
    confidentialcontainers.org/enabled: "true"
"""
    with open(os.path.join(build_ctx, "artifacts", "enclave-cc.yaml"), "w") as f:
        f.write(enclave_cc_yaml)

    # config.json (Standard CoCo config)
    config_json = """{
  "ociVersion": "1.0.2-dev",
  "process": {
    "terminal": false,
    "user": { "uid": 0, "gid": 0 },
    "args": [ "/bin/enclave-agent" ],
    "env": [ "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "ENCLAVE_AGENT=true", "TERM=xterm", "SHIMS=rune io.containerd.rune.v2 enclave-cc", "SNAPSHOTTER_HANDLER_MAPPING=rune:overlayfs,io.containerd.rune.v2:overlayfs,enclave-cc:overlayfs", "PULL_TYPE_MAPPING=rune:auth,io.containerd.rune.v2:auth,enclave-cc:auth" ],
    "cwd": "/",
    "capabilities": { "bounding": ["CAP_AUDIT_WRITE", "CAP_KILL", "CAP_NET_BIND_SERVICE"], "effective": ["CAP_AUDIT_WRITE", "CAP_KILL", "CAP_NET_BIND_SERVICE"], "inheritable": ["CAP_AUDIT_WRITE", "CAP_KILL", "CAP_NET_BIND_SERVICE"], "permitted": ["CAP_AUDIT_WRITE", "CAP_KILL", "CAP_NET_BIND_SERVICE"], "ambient": ["CAP_AUDIT_WRITE", "CAP_KILL", "CAP_NET_BIND_SERVICE"] },
    "rlimits": [{ "type": "RLIMIT_NOFILE", "hard": 65535, "soft": 65535 }],
    "noNewPrivileges": true
  },
  "root": { "path": "rootfs" },
  "hostname": "rune",
  "mounts": [
    { "destination": "/proc", "type": "proc", "source": "proc" },
    { "destination": "/dev", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "strictatime", "mode=755", "size=65536k"] },
    { "destination": "/dev/pts", "type": "devpts", "source": "devpts", "options": ["nosuid", "noexec", "newinstance", "ptmxmode=0666", "mode=0620", "gid=5"] },
    { "destination": "/dev/shm", "type": "tmpfs", "source": "shm", "options": ["nosuid", "noexec", "nodev", "mode=1777", "size=65536k"] },
    { "destination": "/dev/mqueue", "type": "mqueue", "source": "mqueue", "options": ["nosuid", "noexec", "nodev"] },
    { "destination": "/sys", "type": "sysfs", "source": "sysfs", "options": ["nosuid", "noexec", "nodev", "ro"] },
    { "destination": "/run/containerd", "type": "bind", "source": "/run/k3s/containerd", "options": ["rbind", "rprivate"] },
    { "destination": "/var/lib/containerd", "type": "bind", "source": "/var/lib/rancher/k3s/agent/containerd", "options": ["rbind", "rprivate"] },
    { "destination": "/opt/confidential-containers", "type": "bind", "source": "/opt/confidential-containers", "options": ["rbind", "rprivate"] }
  ],
  "linux": { "resources": { "devices": [{ "allow": false, "access": "rwm" }] }, "namespaces": [ { "type": "pid" }, { "type": "ipc" }, { "type": "uts" }, { "type": "mount" } ] }
}"""
    with open(os.path.join(build_ctx, "artifacts", "config.json"), "w") as f:
        f.write(config_json)

    # shim-rune-config.toml
    shim_config = """[log]
level = "debug"

[shim]
agent_sock = "/run/rune/enclave-agent.sock"

[containerd]
agent_container_instance = "/opt/confidential-containers/share/enclave-cc-agent-instance"
agent_container_root_dir = "/run/containerd/agent-enclave"
boot_container_instance = "/opt/confidential-containers/share/enclave-cc-boot-instance"
"""
    with open(os.path.join(build_ctx, "artifacts", "shim-rune-config.toml"), "w") as f:
        f.write(shim_config)

    dockerfile_path = os.path.join(payload_dir, "Dockerfile")
    

    
    config = load_config(infra_dir)
    coco_version = config.get("coco_payload_version", "v0.11.0")

    # Run Docker Build
    log_info(f"Starting Multi-Stage Docker Build (Version: {coco_version})...")
    cmd = [
        "nerdctl", "--namespace", "k8s.io", "build",
        "--build-arg", f"TARGETARCH={target_arch}",
        "--build-arg", f"COCO_VERSION={coco_version}",
        "-f", dockerfile_path,
        "-t", image_name,
        build_ctx
    ]
    
    try:
        subprocess.run(cmd, check=True)
        log_info("Build Successful.")
    except subprocess.CalledProcessError:
        log_error("Build Failed.")
        sys.exit(1)
        
    log_info(f"Skipping push for local image ({image_name}). It should be available in 'k8s.io' namespace.")
    log_info(f"Verify with: nerdctl -n k8s.io images | grep coco")
    # log_info(f"Pushing {image_name} to ttl.sh (ephemeral)...")
    # try:
    #     subprocess.run(["nerdctl", "--namespace", "k8s.io", "push", image_name], check=True)
    # except subprocess.CalledProcessError:
    #     log_error("Push Failed.")
    
    # Cleanup Context
    # shutil.rmtree(build_ctx) # Optional: Keep for debug or clean


def setup_coco():
    log_section("Setting up Confidential Containers")
    
    system, machine = detect_platform()
    
    # 0. Label Nodes
    log_info("Labeling nodes for CoCo eligibility...")
    try:
        # Best effort labeling
        run_kubectl(["label", "nodes", "--all", "node-role.kubernetes.io/worker=", "--overwrite"])
        run_kubectl(["label", "nodes", "--all", "confidentialcontainers.org/enabled=true", "--overwrite"])
    except:
        log_warn("Failed to label nodes. Ensure you have permissions or the nodes are already labeled.")

    # 1. Install Operator
    # We read version from config.yaml
    script_dir = os.path.dirname(os.path.abspath(__file__))
    infra_dir = os.path.dirname(os.path.dirname(script_dir))
    config = load_config(infra_dir)
    operator_version = config.get("coco_operator_version", "v0.12.0")
    
    operator_kustomize_url = f"github.com/confidential-containers/operator/config/release?ref={operator_version}"
    log_info(f"Applying Operator from {operator_kustomize_url}...")
    try:
        run_kubectl(["apply", "-k", operator_kustomize_url])
    except:
        return

    # 2. Wait for Operator to initialize (wait for CRD)
    log_info("Waiting for Operator to initialize...")
    if not wait_for_crd("ccruntimes.confidentialcontainers.org"):
        log_error("CRD not ready. Aborting setup.")
        return
    
    # 3. Create CcRuntime
    # Payload image logic based on arch
    # payload_tag = "enclave-cc-SIM-sample-kbc-latest" # Simulation payload for local dev 
    # Use our custom built ARM64 payload
    payload_image = "k8s.io/coco-payload-arm64:local"
    
    # CRITICAL: We patch the script to replace 'systemctl' with 'rc-service' because
    # Rancher Desktop (macOS/Alpine) uses OpenRC, but the script expects systemd.
    install_script_cmd = (
        r"echo 'Installing CoCo artifacts...' && "
        r"mkdir -p /opt/confidential-containers/share/enclave-cc-agent-instance/rootfs/bin && "
        r"cp /opt/enclave-cc-artifacts/agent/enclave-agent /opt/confidential-containers/share/enclave-cc-agent-instance/rootfs/bin/enclave-agent && "
        r"chmod +x /opt/confidential-containers/share/enclave-cc-agent-instance/rootfs/bin/enclave-agent && "
        r"cp /opt/enclave-cc-artifacts/config.json /opt/confidential-containers/share/enclave-cc-agent-instance/ && "
        r"mkdir -p /opt/confidential-containers/share/enclave-cc-boot-instance/rootfs/bin && "
        r"cp /opt/enclave-cc-artifacts/agent/enclave-agent /opt/confidential-containers/share/enclave-cc-boot-instance/rootfs/bin/enclave-agent && "
        r"chmod +x /opt/confidential-containers/share/enclave-cc-boot-instance/rootfs/bin/enclave-agent && "
        r"mkdir -p /etc/enclave-cc && "
        r"cp /opt/enclave-cc-artifacts/shim-rune-config.toml /etc/enclave-cc/config.toml && "
        r"mkdir -p /opt/confidential-containers/bin && "
        r"cp -f /opt/enclave-cc-artifacts/shim/containerd-shim-rune-v2 /opt/confidential-containers/bin/containerd-shim-rune-v2 && "
        r"nsenter --target 1 --mount -- ln -sf /opt/confidential-containers/bin/containerd-shim-rune-v2 /usr/bin/containerd-shim-rune-v2 && "
        r"nsenter --target 1 --mount -- chmod 755 /usr/bin/containerd-shim-rune-v2 && "
        r"echo 'Configuring containerd...' && "
        r"nsenter --target 1 --mount -- sh -c 'grep -q \"enclave-cc\" /etc/containerd/config.toml || cat <<EOF >> /etc/containerd/config.toml\n[plugins.\"io.containerd.grpc.v1.cri\".containerd.runtimes.enclave-cc]\n  runtime_type = \"io.containerd.rune.v2\"\n  cri_handler = \"cc\"\nEOF' && "
        r"echo 'Restarting containerd...' && "
        r"nsenter --target 1 --mount -- rc-service containerd restart && "
        r"echo 'Installation complete. Sleeping...' && "
        r"sleep infinity"
    )

    cc_runtime_yaml = f"""
apiVersion: confidentialcontainers.org/v1beta1
kind: CcRuntime
metadata:
  name: cc-runtime
  namespace: confidential-containers-system
spec:
  runtimeName: kata
  # We explicitly select nodes with 'kubernetes.io/os: linux' to bypass strict hardware feature checks.
  # By default, the operator might look for specific TEE hardware traits which are missing in this emulated env.
  ccNodeSelector:
    matchLabels:
      kubernetes.io/os: linux
  config:
    installType: bundle
    # We use the 'enclave-cc-SIM-sample-kbc-latest' image.
    # 'SIM' stands for Simulation, which is required for running CoCo on macOS (via QEMU) 
    # as we don't have access to real TEE hardware (SEV/TDX/etc.) on Apple Silicon.
    # USE CUSTOM IMAGE:
    payloadImage: "{payload_image}"
    imagePullPolicy: "IfNotPresent"
    
    # We explicitly define the install/uninstall commands because the directory structure 
    # in this specific payload image (/opt/enclave-cc-artifacts/) differs from the 
    # operator's default expectation.
    installCmd: ["/bin/sh", "-c", "{install_script_cmd}"]
    uninstallCmd: ["/opt/enclave-cc-artifacts/scripts/enclave-cc-deploy.sh", "uninstall"]
    cleanupCmd: ["/opt/enclave-cc-artifacts/scripts/enclave-cc-deploy.sh", "cleanup"]

    # The installer script expects to write to host paths which are not mounted by default 
    # when we override the install command or because of the bundle type.
    # We must explicitly mount them to allow persistent installation.
    installerVolumes:
      - name: host-opt-cc
        hostPath:
          path: /opt/confidential-containers
          type: DirectoryOrCreate
      - name: host-etc-enclave-cc
        hostPath:
          path: /etc/enclave-cc
          type: DirectoryOrCreate
      - name: host-etc-containerd
        hostPath:
          path: /etc/containerd
          type: DirectoryOrCreate
      # - name: host-usr-bin-shim  <-- Removed to avoid 0-byte file issue
      #   hostPath: ...
          
    installerVolumeMounts:
      - name: host-opt-cc
        mountPath: /opt/confidential-containers
      - name: host-etc-enclave-cc
        mountPath: /etc/enclave-cc
      - name: host-etc-containerd
        mountPath: /etc/containerd
      # - name: host-usr-bin-shim
      #   mountPath: /usr/bin/containerd-shim-rune-v2
    
    # The script crashes if DECRYPT_CONFIG or OCICRYPT_CONFIG are not set.
    # We provide an empty JSON object (base64 encoded): "e30="
    environmentVariables:
      - name: DECRYPT_CONFIG
        value: "e30="
      - name: OCICRYPT_CONFIG
        value: "e30="

    runtimeClasses:
      - name: kata
        snapshotter: overlayfs
        pulltype: auth
      - name: kata-qemu
        snapshotter: overlayfs
        pulltype: auth
      - name: kata-clh
        snapshotter: overlayfs
        pulltype: auth
"""
    log_info("Applying CcRuntime configuration...")
    try:
        run_kubectl(["apply", "-f", "-"], input_data=cc_runtime_yaml)
        log_info("CcRuntime applied.")
    except Exception as e:
        log_error(f"Failed to apply CcRuntime: {e}")
        return

    log_info("Setup complete. The operator will now install the runtime classes.")
    log_info("You can check progress with: kubectl get pods -n confidential-containers-system")

def validate_coco():
    log_section("Validating CoCo Installation")
    
    system, machine = detect_platform()
    
    # Check for available RuntimeClasses
    log_info("Checking available RuntimeClasses...")
    available_rcs = []
    try:
        rc_output = run_kubectl(["get", "runtimeclass", "-o", "jsonpath={.items[*].metadata.name}"])
        available_rcs = rc_output.split()
    except:
        pass
        
    log_info(f"Found RuntimeClasses: {available_rcs}")

    runtime_class = "kata"
    
    # Priority selection
    if "enclave-cc" in available_rcs:
        runtime_class = "enclave-cc"
        log_info("Selection: Using 'enclave-cc' (detected from CoCo installation).")
    elif "kata-qemu" in available_rcs and machine in ["arm64", "aarch64"]:
        runtime_class = "kata-qemu"
        log_info("Selection: Using 'kata-qemu' (optimized for ARM64/Emulation).")
    elif "kata" in available_rcs:
        runtime_class = "kata"
        log_info("Selection: Using generic 'kata'.")
    else:
        log_error("No CoCo RuntimeClasses (enclave-cc, kata*) found.")
        log_error("It seems CoCo is not installed or the operator failed.")
        log_error("Please run 'python3 scripts/manage_coco.py setup' first.")
        return
    
    log_info(f"Target RuntimeClass: {runtime_class}")
    
    # Check if RuntimeClass exists
    log_info(f"Waiting for RuntimeClass '{runtime_class}' to be available...")
    rc_ready = False
    for i in range(24): # Wait up to 2 minutes
        try:
            run_kubectl(["get", "runtimeclass", runtime_class])
            rc_ready = True
            break
        except:
            time.sleep(5)
            
    if not rc_ready:
        log_error(f"RuntimeClass '{runtime_class}' not found after waiting. Is the operator pod running without errors?")
        return

    # Create Test Pod
    pod_name = "test-coco-start" # Use simple name
    pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  labels:
    app: test-coco
spec:
  restartPolicy: Never
  runtimeClassName: {runtime_class}
  containers:
  - name: nginx
    image: nginx:alpine
"""
    
    log_info(f"Deploying test pod '{pod_name}'...")
    
    # Clean up old pod
    run_kubectl(["delete", "pod", pod_name, "--ignore-not-found=true", "--wait=true"])
    
    try:
        run_kubectl(["apply", "-f", "-"], input_data=pod_yaml)
    except:
        return

    # Wait for running
    if wait_for_pod("default", "app=test-coco"):
        log_info(f"Pod '{pod_name}' is RUNNING!")
        
        # Check Kernel
        try:
            pod_kernel = run_kubectl(["exec", pod_name, "--", "uname", "-r"])
            log_info(f"Pod Kernel: {pod_kernel}")
            
            # Since we are outside, we can't easily get Node kernel via kubectl without privileges or another pod
            # But seeing a kernel output typical of Kata (often has '-kata' or diff version) is a good sign.
            log_info("Verification Successful: Pod started with CoCo runtime.")
        except:
             log_warn("Could not check kernel version inside pod.")
    else:
        log_error(f"Pod '{pod_name}' failed to start or timed out.")
        
        # Describe for debug
        log_info("Pod Description (last 20 lines):")
        desc = subprocess.run(["kubectl", "describe", "pod", pod_name], capture_output=True, text=True).stdout
        print("\n".join(desc.splitlines()[-20:]))

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Confidential Containers on Rancher Desktop")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    subparsers.add_parser("check-prereqs", help="Check prerequisites")
    subparsers.add_parser("setup", help="Install Operator and Runtime")
    subparsers.add_parser("build", help="Build Custom Payload (Multi-Arch, Dockerized)")
    subparsers.add_parser("validate", help="Validate installation with a test pod")
    
    args = parser.parse_args()
    
    if args.command == "check-prereqs":
        if check_prereqs():
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.command == "build":
        if check_prereqs():
            build_coco()
    elif args.command == "setup":
        if check_prereqs():
            setup_coco()
    elif args.command == "validate":
        if check_prereqs():
            validate_coco()
    else:
        parser.print_help()
