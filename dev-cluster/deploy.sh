#!/usr/bin/env bash
# libre365 - bring up the local k3d dev cluster, reusing the production Helm
# charts/values (infra/k8s/helm-values/) and raw manifests
# (infra/k8s/manifests/), with the dev-speed hardening overlays
# (infra/k8s/helm-values/dev/) layered on top. See dev-cluster/README.md for
# the full rationale (why k3d over docker-compose here, why grommunio-dev
# stays on docker-compose, what "durcir en dev" means concretely).
#
# Requires: an apt-based distro (Ubuntu/Debian - what step 1/14 below
# installs for) to reach the docker.com/helm.sh/k3d.io/pkg.k8s.io install
# scripts, sudo rights, and network access to those 4 hosts plus every Helm
# repo/OCI registry added in step 5/14. Idempotent: safe to re-run (each
# install step is skipped once its tool is already on PATH, helm upgrade
# --install/kubectl apply/cluster creation skipped if already present).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLUSTER_NAME="libre365-dev"
NAMESPACE="libre365"
CONNECTORS=(notification-hub unified-search presence-aggregator onlyoffice-mentions peertube-ingest)
# Host CPU architecture in the naming every tool downloaded below actually
# uses (Go/Docker convention: "amd64"/"arm64", not uname -m's own
# "x86_64"/"aarch64") - found necessary running this script on an ARM64 VM
# (e.g. an Apple Silicon Mac's Ubuntu VM): unrelated to which hypervisor
# runs that VM (Apple's own Virtualization.framework, in that case) - this
# is purely about the CPU instructions the VM's own Linux kernel executes.
case "$(uname -m)" in
  x86_64) HOST_ARCH="amd64" ;;
  aarch64 | arm64) HOST_ARCH="arm64" ;;
  *) HOST_ARCH="$(uname -m)" ;; # unmapped - passed through as-is, a download further below will just 404 loudly rather than silently fetching the wrong binary.
esac
# Keep in sync by hand with platform.yaml's services.keycloak.version -
# scripts/sync_platform.py patches infra/k8s/manifests/keycloak.yaml's
# `spec.image` tag, but not this shell variable (see that file's header
# comment on why the operator install isn't automated the same way).
KEYCLOAK_VERSION="26.7.3"
# Novu has no official Helm chart at all (verified: novuhq/helm-charts, the
# repo this used to point at, does not exist on GitHub, and its gh-pages
# index.yaml 404s - found by actually running this script). The closest
# thing is this community, explicitly "not officially supported by the
# Novu team" chart, published as an OCI artifact (no index.yaml repo to
# `helm repo add` at all) - kept as a shell variable, same pattern as
# KEYCLOAK_VERSION above, since OCI references are pinned by `--version` at
# install time, not resolved through a repo's own index.
NOVU_CHART="oci://ghcr.io/nova-edge/charts/novu"
NOVU_CHART_VERSION="0.2.1"

echo "==> 1/14 Prerequisites (docker, kubectl, helm, k3d)"
# Installs whatever is missing, using each project's own official install
# method - skips a tool entirely if it's already on PATH, so re-running
# this script never reinstalls anything. Ubuntu/Debian only (apt-based) -
# see this script's header. Docker specifically needs a fresh shell/login
# to pick up the new `docker` group membership, so this step exits early
# right after installing it rather than pressing on with a `docker` command
# that would still fail with a permission error in the *current* shell.
if ! command -v docker >/dev/null 2>&1; then
  echo "    docker: not found, installing (get.docker.com)"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  cat <<'EOF'

Docker was just installed and your user was added to the "docker" group,
but that only takes effect in a NEW shell session. Log out and back in (or
run `newgrp docker`), then re-run this script to continue.
EOF
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  cat <<EOF
    ! docker is installed but not usable by ${USER} in this shell (the
      "docker" group membership isn't active here yet). Run \`newgrp
      docker\` or log out/in, then re-run this script.
EOF
  exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
  # Three fallbacks, in order, since any one of these hosts can be
  # unreachable on a given machine (DNS restrictions, a corporate/hosting
  # provider blocklist) while the others aren't - found the hard way:
  # pkg.k8s.io failing to resolve while download.docker.com resolved fine
  # moments earlier in this same install step.
  if command -v apt-get >/dev/null 2>&1 && curl -fsS --connect-timeout 5 https://pkg.k8s.io >/dev/null 2>&1; then
    echo "    kubectl: not found, installing (pkg.k8s.io apt repo)"
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://pkg.k8s.io/core:/stable:/v1.31/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkg.k8s.io/core:/stable:/v1.31/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq kubectl
  elif curl -fsS --connect-timeout 5 https://dl.k8s.io >/dev/null 2>&1; then
    echo "    kubectl: not found, pkg.k8s.io unreachable - installing the binary directly from dl.k8s.io instead"
    kubectl_version="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${kubectl_version}/bin/linux/${HOST_ARCH}/kubectl"
    sudo install -o root -g root -m 0755 /tmp/kubectl /usr/local/bin/kubectl
    rm -f /tmp/kubectl
  elif command -v snap >/dev/null 2>&1; then
    echo "    kubectl: not found, pkg.k8s.io/dl.k8s.io both unreachable - installing via snap instead"
    sudo snap install kubectl --classic
  else
    echo "    ! kubectl: not found, and none of the apt repo, the direct binary download, or snap are reachable/available - install it manually (https://kubernetes.io/docs/tasks/tools/) and re-run."
    exit 1
  fi
fi
if ! command -v helm >/dev/null 2>&1; then
  echo "    helm: not found, installing (get.helm.sh)"
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi
if ! command -v k3d >/dev/null 2>&1; then
  echo "    k3d: not found, installing (k3d.io)"
  curl -fsSL https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
fi

echo "==> 2/14 grommunio-dev (docker-compose, study 4.6 - not part of the k3d cluster, see dev-cluster/README.md's 'Why grommunio-dev stays on docker-compose')"
# grommunio/gromox-core only ever publishes linux/amd64 images (verified via
# the Docker Hub API, see platform.yaml's grommunio_dev entry) - on a
# non-amd64 host (ARM64, e.g. an Apple Silicon Mac's Ubuntu VM) Docker can
# only run it through QEMU user-mode emulation, which needs the host
# kernel's binfmt_misc to have an interpreter registered for the foreign
# architecture; without it, the container fails immediately with
# `exec /init: exec format error` rather than falling back to (slower)
# emulation on its own. Skipped entirely on an amd64 host, and skipped here
# too if some other mechanism (a distro package, a previous manual run of
# this same command) already registered it - `tonistiigi/binfmt` itself is
# idempotent, but checking first avoids the extra `docker run --privileged`
# on every single re-run of this script.
if [ "${HOST_ARCH}" != "amd64" ] && [ ! -e /proc/sys/fs/binfmt_misc/qemu-x86_64 ]; then
  echo "    non-amd64 host (${HOST_ARCH}): registering QEMU emulation for linux/amd64 images (tonistiigi/binfmt)"
  docker run --privileged --rm tonistiigi/binfmt --install all
fi
if [ ! -f dev-cluster/grommunio-dev/.env ]; then
  cp dev-cluster/grommunio-dev/.env.example dev-cluster/grommunio-dev/.env
fi
docker compose -f dev-cluster/grommunio-dev/docker-compose.yml up -d
# Emulated boot (non-amd64 host, see above) takes noticeably longer than
# native - supervisord starts ~18 internal services one by one - so this
# step alone gets a longer allowance than wait-for-healthy.sh's own 600s
# default would otherwise give the WHOLE stack collectively further down.
dev-cluster/grommunio-dev/scripts/wait-for-healthy.sh 900

echo "==> 3/14 k3d cluster"
if k3d cluster list -o json 2>/dev/null | grep -q "\"name\":\"${CLUSTER_NAME}\""; then
  echo "    cluster '${CLUSTER_NAME}' already exists, skipping creation."
else
  k3d cluster create --config dev-cluster/k3d-config.yaml
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

echo "==> 4/14 namespace"
kubectl apply -f infra/k8s/manifests/namespace.yaml

echo "==> 5/14 Helm repos (see infra/k8s/helm-values/README.md)"
helm repo add ananace-charts https://ananace.gitlab.io/charts >/dev/null
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm >/dev/null
# Novu: no `helm repo add` here at all - see $NOVU_CHART/$NOVU_CHART_VERSION's
# own comment above (OCI artifact, not an index.yaml-based repo).
# seafile-charts/onlyoffice/peertube-helm repos are marked "to be confirmed"
# in infra/k8s/helm-values/README.md (no single identified official chart at
# the time of writing) - if a repo add fails because the chart moved, this
# script keeps going (`|| true`) rather than blocking the whole dev tier on
# one unresolved brick, but that brick's `helm upgrade --install` a few
# lines below will then fail loudly, which is the correct behavior (fail on
# the actual missing chart, not silently skip).
#
# [CORRECTED] all three URLs below used to be fabricated - none of them
# ever resolved (404 on every single one, found by actually running this
# script). Replaced with the real repos each project's own current README
# documents (verified by reading those READMEs directly, not by reaching
# the gh-pages endpoints themselves - this sandboxed environment's egress
# proxy blocks arbitrary custom domains including every *.github.io site,
# so these are still [UNCERTAIN] in the sense that the index.yaml itself
# wasn't independently fetched - confirm on first real run):
#   seafile-charts: haiwen's OWN org (Seafile's actual publisher, not a
#     random community fork) - chart is "ce" (Community Edition), not
#     "seafile-ce" (see the `helm upgrade --install seafile` line below).
#   onlyoffice: ONLYOFFICE's OWN download domain (github.com/ONLYOFFICE/
#     Kubernetes-Docs' documented repo) - chart is "docs", not "docs-cloud"
#     (see the `helm upgrade --install onlyoffice` line below).
#   peertube-helm: no official PeerTube chart exists (same "no first-party
#     chart" situation as Novu) - zendet/peertube-helm chosen as the most
#     plausible community option found; chart name "peertube" unchanged.
helm repo add seafile-charts https://haiwen.github.io/seafile-helm-chart/repo >/dev/null || true
helm repo add onlyoffice https://download.onlyoffice.com/charts/stable >/dev/null || true
helm repo add peertube-helm https://zendet.github.io/peertube-helm/ >/dev/null || true
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/ >/dev/null
helm repo add openbao https://openbao.github.io/openbao-helm/ >/dev/null || true
helm repo add external-secrets https://charts.external-secrets.io >/dev/null
helm repo add oauth2-proxy https://oauth2-proxy.github.io/manifests >/dev/null
helm repo update >/dev/null

echo "==> 6/14 Keycloak Operator (cluster-scoped CRDs + controller, study 1.7)"
# No Helm chart for the Operator controller itself (see
# infra/k8s/manifests/keycloak.yaml's header) - raw kubectl apply of the
# official pinned manifests, $KEYCLOAK_VERSION set at the top of this
# script. Cluster-scoped (not namespaced), safe to re-run.
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/keycloaks.k8s.keycloak.org-v1.yml"
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/keycloakrealmimports.k8s.keycloak.org-v1.yml"
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/kubernetes.yml"
# Real manifest (verified for 26.3.3): the "keycloak-operator" Deployment
# declares no namespace of its own, so `kubectl apply` lands it in
# whatever namespace the current context defaults to ("default" here,
# k3d's own default - this script never changes it) - NOT "$NAMESPACE".
kubectl rollout status deployment/keycloak-operator -n default --timeout=120s 2>/dev/null || \
  echo "    ! could not confirm the operator controller's Deployment - inspect \`kubectl get deploy -A -l app.kubernetes.io/name=keycloak-operator\` if the next step fails."

echo "==> 7/14 Secrets: OpenBao + External Secrets Operator (dev mode, study 4.5)"
# Dev-mode OpenBao (fixed root token, in-memory) + ESO, wired together by
# the DEV-ONLY ClusterSecretStore (static token, not the production
# Kubernetes-auth one - see infra/k8s/manifests/dev/external-secrets-store.yaml's
# own comment for why). Every chart below that references an
# existingSecret (Keycloak, the Postgres-backed ones, etc.) needs this
# done FIRST, or its pods just sit waiting for a Secret that doesn't exist
# yet - harmless, but confusing to watch.
helm upgrade --install openbao openbao/openbao -n "$NAMESPACE" \
  -f infra/k8s/helm-values/openbao.yaml -f infra/k8s/helm-values/dev/openbao.yaml
helm upgrade --install external-secrets external-secrets/external-secrets -n "$NAMESPACE" \
  -f infra/k8s/helm-values/external-secrets.yaml -f infra/k8s/helm-values/dev/external-secrets.yaml
# [CORRECTED] `kubectl rollout status` only supports the RollingUpdate
# strategy - found by actually running this script: OpenBao's chart (a
# HashiCorp Vault fork, inheriting its chart conventions) deploys as a
# StatefulSet with `updateStrategy: OnDelete` (so an operator can unseal
# pods one at a time during a real upgrade, not relevant to a single-replica
# dev instance but still the chart's default), which made `kubectl rollout
# status statefulset/openbao` fail immediately with "rollout status is only
# available for RollingUpdate strategy type" - not silenced by `|| true`
# unlike the Deployment attempt before it, so this stopped the whole script.
# `kubectl wait --for=condition=Ready` checks pod readiness directly instead
# of the rollout mechanism, so it works regardless of the update strategy.
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=openbao -n "$NAMESPACE" --timeout=120s
# [CORRECTED, twice] `helm upgrade --install external-secrets` above
# returns as soon as its manifests (including its own CRDs) are applied,
# but the API server can take a few seconds to actually register a
# brand-new CRD - found by actually running this script: `kubectl apply -f
# .../external-secrets-store.yaml` (a ClusterSecretStore) failed with "no
# matches for kind ClusterSecretStore ... ensure CRDs are installed
# first". A first fix added `kubectl wait --for=condition=Established` on
# the CRDs, which turned out to be insufficient: `kubectl wait` confirms
# the CRD server-side, but `kubectl apply` separately relies on `kubectl`'s
# own LOCAL, on-disk discovery cache (~/.kube/cache/discovery, ~10 minute
# TTL) to resolve "kind: ClusterSecretStore" to its REST endpoint - a cache
# populated by earlier `kubectl` calls in this very script, before these
# CRDs existed, and `condition=Established` becoming true server-side does
# not invalidate it. A short retry loop is the standard, robust fix for
# this well-known kubectl gotcha (each attempt is a fresh process, and the
# cache TTL/staleness resolves itself within a few tries) - simpler and
# more portable than reaching into kubectl's cache directory by hand.
apply_with_crd_retry() {
  local file="$1" attempt
  for attempt in $(seq 1 10); do
    if kubectl apply -f "$file" 2>/tmp/kubectl-apply-err; then
      cat /tmp/kubectl-apply-err >&2
      return 0
    fi
    if ! grep -q "ensure CRDs are installed first" /tmp/kubectl-apply-err; then
      cat /tmp/kubectl-apply-err >&2
      return 1
    fi
    echo "    kubectl's discovery cache hasn't picked up the new CRD yet (attempt ${attempt}/10), retrying in 3s..."
    sleep 3
  done
  cat /tmp/kubectl-apply-err >&2
  return 1
}
apply_with_crd_retry infra/k8s/manifests/dev/external-secrets-store.yaml
apply_with_crd_retry infra/k8s/manifests/external-secrets.yaml
./dev-cluster/seed-openbao-dev-secrets.sh

echo "==> 8/14 Helm releases (production values + dev/ hardening overlay, NOT the -100/-2000 sizing overlays)"
helm upgrade --install keycloak-postgres bitnami/postgresql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/keycloak-postgres.yaml -f infra/k8s/helm-values/dev/keycloak-postgres.yaml
helm upgrade --install synapse ananace-charts/matrix-synapse -n "$NAMESPACE" \
  -f infra/k8s/helm-values/synapse.yaml -f infra/k8s/helm-values/dev/synapse.yaml
helm upgrade --install element-web ananace-charts/matrix-element-web -n "$NAMESPACE" \
  -f infra/k8s/helm-values/element-web.yaml -f infra/k8s/helm-values/dev/element-web.yaml
helm upgrade --install seafile seafile-charts/ce -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seafile.yaml -f infra/k8s/helm-values/dev/seafile.yaml
helm upgrade --install onlyoffice onlyoffice/docs -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice.yaml -f infra/k8s/helm-values/dev/onlyoffice.yaml
helm upgrade --install vikunja vikunja/vikunja -n "$NAMESPACE" \
  -f infra/k8s/helm-values/vikunja.yaml -f infra/k8s/helm-values/dev/vikunja.yaml
helm upgrade --install seaweedfs seaweedfs/seaweedfs -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seaweedfs.yaml -f infra/k8s/helm-values/dev/seaweedfs.yaml
helm upgrade --install peertube peertube-helm/peertube -n "$NAMESPACE" \
  -f infra/k8s/helm-values/peertube.yaml -f infra/k8s/helm-values/dev/peertube.yaml
helm upgrade --install novu "$NOVU_CHART" --version "$NOVU_CHART_VERSION" -n "$NAMESPACE" \
  -f infra/k8s/helm-values/novu.yaml -f infra/k8s/helm-values/dev/novu.yaml
helm upgrade --install external-dns external-dns/external-dns -n "$NAMESPACE" \
  -f infra/k8s/helm-values/external-dns.yaml -f infra/k8s/helm-values/dev/external-dns.yaml

echo "==> 9/14 Keycloak instance (Operator CR, not a Helm release)"
# Applied after the operator (step 6/14) and keycloak-postgres (step
# 8/14) above, since it references both - see
# infra/k8s/manifests/keycloak.yaml's header for why this isn't a Helm
# release like everything else in step 8/14. The dev/ variant (not the
# production manifest) is applied here: unlike every Helm-backed brick,
# Keycloak has no `-f base -f dev/` overlay to shrink it, so
# infra/k8s/manifests/dev/keycloak.yaml is a full second CR instead -
# single instance, dev-sized resources (see its own header for why
# applying the production 2-instance/2Gi-request sizing here used to eat
# most of a modest dev machine's RAM before anything else even started).
kubectl apply -f infra/k8s/manifests/dev/keycloak.yaml
kubectl wait --for=condition=Ready keycloak/keycloak -n "$NAMESPACE" --timeout=180s

echo "==> 10/14 Keycloak realm + OIDC clients + test user (study 1.7/4.4)"
# Exposes ONLY Keycloak's NodePort now (targeted, not the full
# expose_all_services below: the connectors/gokapi/caddy-dev Services this
# script installs later don't exist yet, and expose_service already
# tolerates a missing Service by skipping with a warning) - needed before
# provision-keycloak-dev.sh can reach the admin REST API, and before
# oauth2-proxy (step 13/14 below) starts: it fetches its OIDC client from
# this realm at startup and would fail if the realm didn't exist yet.
# "keycloak-service" (not "keycloak"): the Operator's own auto-created
# Service name - see infra/k8s/manifests/keycloak.yaml's comment.
source "$(dirname "${BASH_SOURCE[0]}")/lib-expose.sh"
expose_service keycloak-service 0 8080
"$(dirname "${BASH_SOURCE[0]}")/provision-keycloak-dev.sh" "$NAMESPACE"

echo "==> 11/14 In-house connectors: build + import images, apply manifests"
for name in "${CONNECTORS[@]}"; do
  echo "    building libre365/${name}:dev"
  docker build -t "libre365/${name}:dev" "connectors/${name}"
  k3d image import "libre365/${name}:dev" -c "$CLUSTER_NAME"
done
kubectl apply -f infra/k8s/manifests/connectors/
kubectl apply -f infra/k8s/manifests/gokapi.yaml
kubectl apply -f infra/k8s/manifests/dev/caddy.yaml
kubectl rollout status deployment/caddy-dev -n "$NAMESPACE" --timeout=60s

echo "==> 12/14 CoreDNS: resolve every platform.yaml domain to caddy-dev (study 1.7, SSO/OIDC)"
# Every OIDC config in this repo (Keycloak's KC_HOSTNAME, each app's
# issuer/authurl, the two oauth2-proxy gates) uses the real public domain
# unconditionally - the same value in production and dev, deliberately
# never hard-coded to a dev-only alternative (see docs/oidc.md). This
# cluster has no real DNS for it, so patch CoreDNS instead - see
# patch-coredns-hosts.sh's own header for the full rationale and its one
# unverified assumption (k3d's default Corefile layout).
"$(dirname "${BASH_SOURCE[0]}")/patch-coredns-hosts.sh" "$NAMESPACE"

echo "==> 13/14 oauth2-proxy: Keycloak SSO gates for OnlyOffice/Novu (study 1.7)"
# Installed only now, not alongside the other Helm releases above: both
# fetch their OIDC discovery document from the realm's public domain at
# startup and would otherwise fail before CoreDNS could resolve it (see
# step 12/14 just above).
helm upgrade --install oauth2-proxy-onlyoffice oauth2-proxy/oauth2-proxy -n "$NAMESPACE" \
  -f infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml
helm upgrade --install oauth2-proxy-novu oauth2-proxy/oauth2-proxy -n "$NAMESPACE" \
  -f infra/k8s/helm-values/oauth2-proxy-novu.yaml

echo "==> 14/14 Production caddy.yaml's Service + exposing services as NodePort"
# Applies the REAL infra/k8s/manifests/caddy.yaml as-is - not to run
# production Caddy in dev (dev routing is caddy-dev, applied above), but so
# its Service exists with the exact same external-dns hostname annotation
# used in production, letting check-external-dns.sh validate against the
# real thing instead of a hand-copied duplicate that could silently drift
# from it. Its Deployment pods are expected to never become Ready here
# (registry.libre365.example.org doesn't exist, and caddy-injection.yaml's
# banner ConfigMap isn't applied in this dev flow) - harmless, only the
# Service+annotation matters for this test. k3d's built-in Klipper load
# balancer still assigns the LoadBalancer Service an IP regardless.
kubectl apply -f infra/k8s/manifests/caddy.yaml
source "$(dirname "${BASH_SOURCE[0]}")/lib-expose.sh"
expose_all_services

cat <<'EOF'

Dev cluster ready. Services are reachable on localhost at the same ports
already used by docker-compose (see platform.yaml / dev-cluster/README.md).
Run `kubectl get pods -n libre365` to watch rollout status - some charts
(Keycloak, Synapse, OnlyOffice) take a minute or two to become ready even in
the hardened dev configuration.

grommunio-dev (step 2/14 above) is NOT part of this k3d cluster - it's a
separate docker-compose stack (study 4.6), already started by this same run.
EOF
