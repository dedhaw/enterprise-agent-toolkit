# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ---------------------------------------------------------------------------
# deploy_kuberay_controller
#
# Deploys the KubeRay operator and a RayCluster into the namespace defined by
# kuberay_namespace (default: ray-system).
#
# Two-step installation:
#   1. KubeRay operator  — pulled from the upstream kuberay Helm repository.
#      The version is pinned in agentic-metadata.cfg (kuberay_operator_version).
#   2. RayCluster CR     — deployed from the bundled chart at
#      core/helm-charts/kuberay/, parameterised by kuberay_* values in
#      agentic-config.cfg.
#
# After deployment the in-cluster addresses are:
#   Ray Client API : ray://<cluster-name>-head-svc.<namespace>.svc.cluster.local:10001
#   Dashboard      : http://<cluster-name>-head-svc.<namespace>.svc.cluster.local:8265
#
# Worker count and resources are controlled entirely via agentic-config.cfg:
#   kuberay_worker_replicas       — initial worker count
#   kuberay_worker_min_replicas   — autoscaler lower bound
#   kuberay_worker_max_replicas   — autoscaler upper bound
#   kuberay_worker_cpu_request    — guaranteed CPU per worker (e.g. 500m)
#   kuberay_worker_cpu_limit      — max CPU per worker (e.g. 2)
#   kuberay_worker_memory_request — guaranteed RAM per worker (e.g. 2Gi)
#   kuberay_worker_memory_limit   — max RAM per worker (e.g. 4Gi)
#   kuberay_ray_image             — Ray container image (e.g. rayproject/ray:2.9.0-py310)
#
# Prerequisites:
#   • Kubernetes cluster is running   (kubectl get nodes)
#   • SCRIPT_DIR resolves to core/
#   • kuberay_operator_version is set (loaded from agentic-metadata.cfg)
# ---------------------------------------------------------------------------

deploy_kuberay_controller() {
    local _ns="${kuberay_namespace:-ray-system}"
    local _operator_ver="${kuberay_operator_version:-1.1.0}"
    local _cluster_chart="${SCRIPT_DIR}/helm-charts/kuberay"
    local _cluster_name="ray-cluster"

    # Resolved config values — fall back to sensible defaults so the function
    # is safe to call even when config keys are absent (e.g. during testing).
    local _worker_replicas="${kuberay_worker_replicas:-2}"
    local _worker_min="${kuberay_worker_min_replicas:-1}"
    local _worker_max="${kuberay_worker_max_replicas:-4}"
    local _worker_cpu_req="${kuberay_worker_cpu_request:-500m}"
    local _worker_cpu_lim="${kuberay_worker_cpu_limit:-2}"
    local _worker_mem_req="${kuberay_worker_memory_request:-2Gi}"
    local _worker_mem_lim="${kuberay_worker_memory_limit:-4Gi}"
    local _ray_image="${kuberay_ray_image:-rayproject/ray:2.9.0-py310}"

    echo "${BLUE}=====================================================================${NC}"
    echo "${BLUE}  Deploying KubeRay Operator & Cluster${NC}"
    echo "${BLUE}  Namespace     : ${_ns}${NC}"
    echo "${BLUE}  Operator ver  : ${_operator_ver}${NC}"
    echo "${BLUE}  Ray image     : ${_ray_image}${NC}"
    echo "${BLUE}  Workers       : ${_worker_replicas} (min ${_worker_min} / max ${_worker_max})${NC}"
    echo "${BLUE}  Worker CPU    : request=${_worker_cpu_req}  limit=${_worker_cpu_lim}${NC}"
    echo "${BLUE}  Worker Memory : request=${_worker_mem_req}  limit=${_worker_mem_lim}${NC}"
    echo "${BLUE}=====================================================================${NC}"

    # ── Validate chart exists ─────────────────────────────────────────────────
    if [[ ! -d "${_cluster_chart}" ]]; then
        echo "${RED}ERROR: KubeRay cluster chart not found at ${_cluster_chart}${NC}"
        exit 1
    fi

    # ── Ensure Helm is available ──────────────────────────────────────────────
    if ! command -v helm &>/dev/null; then
        echo "${CYAN}Installing Helm...${NC}"
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    fi

    # ── Namespace ─────────────────────────────────────────────────────────────
    echo "${CYAN}[1/4] Creating namespace '${_ns}'...${NC}"
    kubectl create namespace "${_ns}" --dry-run=client -o yaml | kubectl apply -f -

    # ── Step 1: KubeRay operator ──────────────────────────────────────────────
    echo "${CYAN}[2/4] Adding KubeRay Helm repository...${NC}"
    helm repo add kuberay https://ray-project.github.io/kuberay-helm/ 2>/dev/null || true
    helm repo update kuberay 2>/dev/null || helm repo update

    echo "${CYAN}[2/4] Installing KubeRay operator v${_operator_ver}...${NC}"
    helm upgrade --install kuberay-operator kuberay/kuberay-operator \
        --version "${_operator_ver}" \
        --namespace "${_ns}" \
        --wait \
        --timeout 5m

    # ── Step 2: RayCluster ───────────────────────────────────────────────────
    echo "${CYAN}[3/4] Deploying RayCluster '${_cluster_name}'...${NC}"
    helm upgrade --install "${_cluster_name}" "${_cluster_chart}" \
        --namespace "${_ns}" \
        --set cluster.name="${_cluster_name}" \
        --set cluster.rayImage="${_ray_image}" \
        --set cluster.worker.replicas="${_worker_replicas}" \
        --set cluster.worker.minReplicas="${_worker_min}" \
        --set cluster.worker.maxReplicas="${_worker_max}" \
        --set cluster.worker.cpuRequest="${_worker_cpu_req}" \
        --set cluster.worker.cpuLimit="${_worker_cpu_lim}" \
        --set cluster.worker.memoryRequest="${_worker_mem_req}" \
        --set cluster.worker.memoryLimit="${_worker_mem_lim}" \
        --wait \
        --timeout 10m

    # ── Wait for head pod ────────────────────────────────────────────────────
    # The KubeRay operator creates the head pod asynchronously after the
    # RayCluster CR is accepted.  Poll until at least one pod with the head
    # label exists before handing off to `kubectl wait`, which fails
    # immediately when no matching pods are found.
    echo "${CYAN}[4/4] Waiting for Ray head pod to be created...${NC}"
    local _deadline=$(( $(date +%s) + 300 ))
    until kubectl get pod -l "ray.io/node-type=head" -n "${_ns}" \
              --no-headers 2>/dev/null | grep -q .; do
        if (( $(date +%s) >= _deadline )); then
            echo "${RED}ERROR: Ray head pod did not appear within 300 s.${NC}"
            kubectl get events -n "${_ns}" --sort-by='.lastTimestamp' | tail -20
            exit 1
        fi
        echo "${CYAN}  ... pod not yet created, retrying in 5 s${NC}"
        sleep 5
    done

    echo "${CYAN}[4/4] Ray head pod exists — waiting for Ready condition...${NC}"
    kubectl wait pod \
        --selector "ray.io/node-type=head" \
        --namespace "${_ns}" \
        --for condition=Ready \
        --timeout 300s

    # ── Print access information ──────────────────────────────────────────────
    local _head_svc="${_cluster_name}-head-svc"
    echo ""
    echo "${GREEN}=====================================================================${NC}"
    echo "${GREEN}  KubeRay deployed successfully!${NC}"
    echo "${GREEN}  Namespace        : ${_ns}${NC}"
    echo "${GREEN}  Ray Client API   : ray://${_head_svc}.${_ns}.svc.cluster.local:10001${NC}"
    echo "${GREEN}  Dashboard (in-cluster): http://${_head_svc}.${_ns}.svc.cluster.local:8265${NC}"
    echo "${GREEN}  Dashboard (local port-forward):${NC}"
    echo "${GREEN}    kubectl port-forward svc/${_head_svc} 8265:8265 -n ${_ns}${NC}"
    echo "${GREEN}    then open: http://localhost:8265${NC}"
    echo "${GREEN}=====================================================================${NC}"
    echo ""
    echo "${CYAN}To use Ray from the Coding Agent, set these values in the Coding Agent Helm chart:${NC}"
    echo "${CYAN}  ray.enabled=true${NC}"
    echo "${CYAN}  ray.address=ray://${_head_svc}.${_ns}.svc.cluster.local:10001${NC}"
    echo ""
}
