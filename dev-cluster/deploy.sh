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
# [CORRECTED] found by actually running this script ("Error: repo vikunja
# not found" - a `helm repo add vikunja` that was never added at all, for
# a chart never actually matched against its real schema either - see
# infra/k8s/helm-values/vikunja.yaml's own header for the full story).
# go-vikunja/helm-chart is also an OCI artifact, same pinning pattern as
# Novu above.
VIKUNJA_CHART="oci://ghcr.io/go-vikunja/helm-chart/vikunja"
VIKUNJA_CHART_VERSION="2.3.0"

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
# [ADDED] found live on a user's VM: step 10/14 below (provision-keycloak-dev.sh)
# shells out to `ansible-playbook` to run the REAL infra/ansible/roles/
# keycloak_realm role (not a dev-only duplicate - see that script's own
# header) - never installed by this step even though every other tool this
# script depends on is. Same version pin as CI's own `ansible-lint` job
# (.github/workflows/lint-and-test.yml) so a contributor's dev cluster and
# CI run the exact same Ansible against this repo's roles. `--user` (not a
# venv) to keep this script dependency-free of any activation step in
# later steps of the same shell; `--break-system-packages` as a fallback
# for newer Debian/Ubuntu's PEP 668-protected system Python, only tried if
# the plain install refuses to run at all.
if ! command -v ansible-playbook >/dev/null 2>&1; then
  echo "    ansible: not found, installing (pip, same version pin as CI's ansible-lint job)"
  pip3 install --user "ansible-core>=2.15,<2.17" 2>/dev/null || \
    pip3 install --user --break-system-packages "ansible-core>=2.15,<2.17"
  export PATH="$HOME/.local/bin:$PATH"
fi
ansible-galaxy collection install -r infra/ansible/requirements.yml >/dev/null

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

# [ADDED] found live on a user's VM: right after a VM reboot (or under
# real disk/memory pressure from this many charts running at once - see
# this script's own dev-cluster/README.md notes on VM sizing), k3d's
# node containers take a little while to fully restabilize (containerd/
# CNI reinitializing), during which the kubelet applies disk-pressure/
# memory-pressure taints that block ALL scheduling cluster-wide. Without
# this check, that surfaced as a cryptic "0/3 nodes are available: ...
# untolerated taint(s)" deep inside a later step's `kubectl wait` call,
# with nothing pointing at the real cause. Checked once, up front, with
# a clear diagnostic if it doesn't clear in time - a real VM resource
# constraint at that point, not something this script can fix for you.
echo "==> 3.5/14 Node health preflight"
# [ADDED] found live on a user's VM: containerd creates a short-lived
# "lease" for every image pull attempt, to protect its in-flight content
# from garbage collection while the pull is running - by default it
# expires 24h after creation, whether the pull succeeded, failed, or the
# image was later removed entirely. Re-running this script many times in
# one session (retrying a broken chart, waiting out a slow pull, etc., all
# real recurring events on this script's own history - see the comments
# throughout step 8/14) creates one of these leases per attempt, and they
# pile up faster than the 24h expiry clears them. Confirmed live: one node
# alone carried 23GB of orphaned overlayfs snapshot layers pinned by
# ~20 stale leases, invisible to both `crictl images` (only 3.6GB of
# actually-referenced images) and `crictl rmi --prune` (which only reaps
# unreferenced IMAGES, not leases) - none of it tied to any currently
# running pod. Only the numbered/random-suffix leases carrying
# containerd's own `containerd.io/gc.expire` label are removed here -
# confirmed live that's exactly the pull-tracking kind; every other lease
# (named by a real container ID, no gc.expire label) backs a live
# container's own snapshot and is left untouched. Removing a stale lease
# doesn't free space by itself - it just drops the pin, so containerd's
# normal GC can reclaim the now-unreferenced content on its own right
# after. `|| true` throughout: a node with no stale leases (or, on the
# very first run, no nodes yet) is the common case, not an error.
for node in $(docker ps --filter "name=^k3d-${CLUSTER_NAME}-" --format '{{.Names}}' 2>/dev/null); do
  for lease in $(docker exec "$node" ctr -n k8s.io leases ls 2>/dev/null | awk '$3 ~ /gc\.expire/ {print $1}'); do
    docker exec "$node" ctr -n k8s.io leases rm "$lease" >/dev/null 2>&1 || true
  done
done
kubectl wait --for=condition=Ready node --all --timeout=120s
node_wait_start=$(date +%s)
while kubectl get nodes -o jsonpath='{.items[*].spec.taints[*].key}' | grep -qE 'disk-pressure|memory-pressure'; do
  if [ $(( $(date +%s) - node_wait_start )) -gt 180 ]; then
    cat <<'EOF'
    ! Node(s) still under disk-pressure/memory-pressure after 3 minutes -
      this is a real VM resource constraint, not a repo bug. Free up disk
      space (e.g. `docker image prune -af`) or memory, then re-run this
      script. See dev-cluster/README.md for more on VM sizing.
EOF
    exit 1
  fi
  echo "    node(s) under disk-pressure/memory-pressure, waiting for the kubelet to clear it..."
  sleep 5
done

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
# [CORRECTED] This third CRD was missing here - found by actually running
# this script: the operator controller (below) CrashLoopBackOff'd on
# startup with "Couldn't start informer for
# keycloaksamlclients.k8s.keycloak.org/v2alpha1 resources ... 404 Not
# Found", because 26.7.3's operator watches this CRD unconditionally even
# though nothing in this repo configures SAML clients. Confirmed this file
# exists at the pinned $KEYCLOAK_VERSION (verified: 200, unlike a guessed
# "keycloaksamlclientscopes" filename, which 404s - there is no such CRD).
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/keycloaksamlclients.k8s.keycloak.org-v1.yml"
# [CORRECTED] a FOURTH CRD, same story as samlclients above -
# "Couldn't start informer for keycloakoidcclients.k8s.keycloak.org/
# v2alpha1 resources ... 404 Not Found" - found live on a user's VM
# hitting this exact CrashLoopBackOff right after the samlclients fix
# above went in, since the operator only surfaces the NEXT missing CRD
# once the previous one is fixed (each is checked at startup). This time
# confirmed EXHAUSTIVELY rather than one guess at a time: the pinned
# $KEYCLOAK_VERSION's kubernetes/ directory contains exactly four CRD
# manifest files total (keycloaks, keycloakrealmimports,
# keycloaksamlclients, keycloakoidcclients) plus kubernetes.yml/
# kustomization.yml/a cluster-wide/ subdir - so these four `kubectl
# apply` lines are now the complete, closed set for this operator
# version, not another partial fix.
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/keycloakoidcclients.k8s.keycloak.org-v1.yml"
kubectl apply -f "https://raw.githubusercontent.com/keycloak/keycloak-k8s-resources/${KEYCLOAK_VERSION}/kubernetes/kubernetes.yml"
# Real manifest (verified for 26.3.3): the "keycloak-operator" Deployment
# declares no namespace of its own, so `kubectl apply` lands it in
# whatever namespace the current context defaults to ("default" here,
# k3d's own default - this script never changes it) - NOT "$NAMESPACE".
# [ADDED] found live on a user's VM: step 9/14's `kubectl wait
# --for=condition=Ready keycloak/keycloak` timed out with ZERO events on
# the CR and no Pod ever created for it - not a slow reconcile, the
# operator was never even looking at it. Root cause, confirmed against
# the real manifest: all four of its controllers ship with
# `QUARKUS_OPERATOR_SDK_CONTROLLERS_*_NAMESPACES=JOSDK_WATCH_CURRENT` -
# the Java Operator SDK's own sentinel for "only the namespace the
# operator itself runs in" (here, "default", per the comment above) - so
# a CR applied into any OTHER namespace (every CR this repo applies goes
# into "$NAMESPACE", i.e. "libre365") is invisible to it: no informer
# watches it, so no reconcile, no status, no events, ever. The upstream
# manifest's assumption (operator and its CRs share one namespace) just
# doesn't match this repo's layout (one shared operator, app resources in
# their own namespace) - this is the SDK's own documented fix for that
# mismatch (quarkus.operator-sdk.controllers.<name>.namespaces, one
# specific namespace instead of the "current namespace only" sentinel),
# not a version/CRD gap like the four `kubectl apply`s above.
# [ADDED] confirmed live right after the env-var change above went in:
# retargeting the informers at "$NAMESPACE" isn't enough on its own - the
# upstream manifest's RoleBindings (one per controller, granting each
# ClusterRole - e.g. `keycloakcontroller-cluster-role` - only within the
# RoleBinding's OWN namespace, "default", same landing-namespace story as
# the Deployment itself) never granted the operator's ServiceAccount any
# access to "$NAMESPACE" at all. Without this, the operator crash-loops
# immediately on startup: "keycloaks.k8s.keycloak.org is forbidden: User
# \"system:serviceaccount:default:keycloak-operator\" cannot list
# resource \"keycloaks\" ... in the namespace \"libre365\"" (403, straight
# from the API server, not a bug in the operator itself). Mirrors the
# same four RoleBindings into "$NAMESPACE", pointing at the same
# ClusterRoles and the same ServiceAccount (cross-namespace subject
# reference - RBAC allows a RoleBinding's subject to live in a different
# namespace than the binding itself) - `kubectl create ... --dry-run=client
# -o yaml | kubectl apply -f -` for idempotency (`kubectl create` alone
# fails on a second run with "already exists").
for role in keycloakcontroller-cluster-role keycloakrealmimportcontroller-cluster-role \
            keycloaksamlclientcontroller-cluster-role keycloakoidcclientcontroller-cluster-role; do
  kubectl create rolebinding "${role}-${NAMESPACE}" \
    --clusterrole="$role" --serviceaccount=default:keycloak-operator \
    -n "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
done
kubectl set env deployment/keycloak-operator -n default \
  QUARKUS_OPERATOR_SDK_CONTROLLERS_KEYCLOAKCONTROLLER_NAMESPACES="$NAMESPACE" \
  QUARKUS_OPERATOR_SDK_CONTROLLERS_KEYCLOAKREALMIMPORTCONTROLLER_NAMESPACES="$NAMESPACE" \
  QUARKUS_OPERATOR_SDK_CONTROLLERS_KEYCLOAKSAMLCLIENTCONTROLLER_NAMESPACES="$NAMESPACE" \
  QUARKUS_OPERATOR_SDK_CONTROLLERS_KEYCLOAKOIDCCLIENTCONTROLLER_NAMESPACES="$NAMESPACE"
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
# [ADDED] found by actually running this script: a chart with hooks (a
# pre-install/pre-upgrade Job, e.g. seafile/onlyoffice/vikunja's DB
# migration or "stop the previous instance" scripts) that fails leaves
# its Helm release stuck in "failed" state instead of cleanly absent - a
# later re-run of `helm upgrade --install` on the very same release name
# then treats it as a genuine UPGRADE and runs upgrade-only hooks meant
# for an instance that was never actually running, which then fail too
# ("pre-upgrade hooks failed: ... BackoffLimitExceeded"), forcing a manual
# `helm uninstall --no-hooks` before every retry. This wrapper detects
# that stuck state up front and clears it automatically, so a broken
# previous attempt (this script's own earlier bugs, or a future one)
# self-heals into a clean install on the next run instead of wedging.
helm_install() {
  local release="$1"
  shift
  local status
  status="$(helm status "$release" -n "$NAMESPACE" 2>/dev/null | awk -F': ' '/^STATUS:/{print $2}' || true)"
  case "$status" in
    failed | pending-install | pending-upgrade | pending-rollback)
      echo "    release '${release}' is stuck in '${status}' state from a previous run - uninstalling it first (--no-hooks) for a clean install"
      helm uninstall "$release" -n "$NAMESPACE" --no-hooks || true
      ;;
  esac
  helm upgrade --install "$release" "$@"
}

helm_install openbao openbao/openbao -n "$NAMESPACE" \
  -f infra/k8s/helm-values/openbao.yaml -f infra/k8s/helm-values/dev/openbao.yaml
helm_install external-secrets external-secrets/external-secrets -n "$NAMESPACE" \
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
# [CORRECTED] a second, distinct race hits the exact same `apply` calls -
# found by actually running this script: `kubectl apply -f
# .../external-secrets-store.yaml` (a ClusterSecretStore, validated by
# external-secrets' own ValidatingWebhookConfiguration) failed with "failed
# calling webhook ... no endpoints available for service
# external-secrets-webhook" on a fresh install, because the webhook pod
# isn't Ready (and its Service has no registered Endpoints) yet in the
# handful of seconds right after `helm upgrade --install external-secrets`
# returns - unrelated to the discovery-cache race above (different error
# text entirely), so the original grep only matching "ensure CRDs are
# installed first" let this one fall straight through and abort the
# script. Waiting for the webhook Deployment itself is the direct fix for
# the common case; the retry loop's error-matching is also widened as a
# safety net for the brief extra lag between the Deployment going Ready
# and its Service actually gaining Endpoints (kube-proxy/endpoint
# controller propagation, not instantaneous either).
kubectl wait --for=condition=Available deployment/external-secrets-webhook -n "$NAMESPACE" --timeout=120s
apply_with_crd_retry() {
  local file="$1" attempt
  for attempt in $(seq 1 10); do
    if kubectl apply -f "$file" 2>/tmp/kubectl-apply-err; then
      cat /tmp/kubectl-apply-err >&2
      return 0
    fi
    if ! grep -qE "ensure CRDs are installed first|no endpoints available for service" /tmp/kubectl-apply-err; then
      cat /tmp/kubectl-apply-err >&2
      return 1
    fi
    echo "    kubectl's discovery cache or the external-secrets webhook isn't ready yet (attempt ${attempt}/10), retrying in 3s..."
    sleep 3
  done
  cat /tmp/kubectl-apply-err >&2
  return 1
}
apply_with_crd_retry infra/k8s/manifests/dev/external-secrets-store.yaml
apply_with_crd_retry infra/k8s/manifests/external-secrets.yaml
./dev-cluster/seed-openbao-dev-secrets.sh

echo "==> 8/14 Helm releases (production values + dev/ hardening overlay, NOT the -100/-2000 sizing overlays)"
helm_install keycloak-postgres bitnami/postgresql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/keycloak-postgres.yaml -f infra/k8s/helm-values/dev/keycloak-postgres.yaml
helm_install synapse ananace-charts/matrix-synapse -n "$NAMESPACE" \
  -f infra/k8s/helm-values/synapse.yaml -f infra/k8s/helm-values/dev/synapse.yaml
helm_install element-web ananace-charts/element-web -n "$NAMESPACE" \
  -f infra/k8s/helm-values/element-web.yaml -f infra/k8s/helm-values/dev/element-web.yaml
# seafile-mysql/seafile-memcached: the real seafile-charts/ce chart has no
# bundled database or cache of its own (found by actually running this
# script, then verifying the chart's real source) - see
# infra/k8s/helm-values/seafile-mysql.yaml's header for the full story.
# Installed before `seafile` itself since it depends on both by hostname.
helm_install seafile-mysql bitnami/mysql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seafile-mysql.yaml -f infra/k8s/helm-values/dev/seafile-mysql.yaml
helm_install seafile-memcached bitnami/memcached -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seafile-memcached.yaml -f infra/k8s/helm-values/dev/seafile-memcached.yaml
kubectl apply -f infra/k8s/manifests/seafile-extra-env.yaml
helm_install seafile seafile-charts/ce -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seafile.yaml -f infra/k8s/helm-values/dev/seafile.yaml
# onlyoffice-postgres/onlyoffice-redis: the real onlyoffice/docs chart has
# no bundled database or cache of its own (found by actually running this
# script, then verifying the chart's real source) - see
# infra/k8s/helm-values/onlyoffice-postgres.yaml's header for the full
# story. Installed before `onlyoffice` itself since its pre-install Job
# (DB migration) depends on both by hostname.
helm_install onlyoffice-postgres bitnami/postgresql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice-postgres.yaml -f infra/k8s/helm-values/dev/onlyoffice-postgres.yaml
helm_install onlyoffice-redis bitnami/redis -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice-redis.yaml -f infra/k8s/helm-values/dev/onlyoffice-redis.yaml
# [ADDED] found missing by actually running this script: the chart also
# requires an AMQP broker unconditionally (its own default
# `connections.amqpExistingSecret: "rabbitmq"` pointed at a Secret that
# was never provisioned) - a failure only visible once `docservice`'s
# image had actually finished pulling ("Error: secret 'rabbitmq' not
# found" -> CreateContainerConfigError), unrelated to the pre-install
# Job above (which never touches AMQP). See
# infra/k8s/helm-values/onlyoffice-rabbitmq.yaml's own header for the
# full story.
helm_install onlyoffice-rabbitmq bitnami/rabbitmq -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice-rabbitmq.yaml -f infra/k8s/helm-values/dev/onlyoffice-rabbitmq.yaml
# [ADDED] found live on a user's VM: `onlyoffice`'s pre-install Job
# (DB migration) failed with "timed out waiting for the condition"
# immediately after this RabbitMQ install, on a cluster busy upgrading
# several other releases at once - none of the three dependencies above
# had an explicit readiness wait before this point (unlike, e.g., the
# openbao/external-secrets-webhook waits earlier in this script), so a
# freshly-installed one (RabbitMQ here, Postgres/Redis on a first run)
# could still be starting up when the pre-install Job tries to reach it.
# Not confirmed as the root cause of that specific timeout (the
# pre-install Job only touches Postgres, which was already running in
# that case - more likely plain resource contention, same recurring
# pattern already seen on this VM), but a real gap either way: closing
# it here removes one more variable rather than leaving it open.
# [CORRECTED] 120s was too tight - found live on a user's VM: a pod that
# had to wait out a node's disk-pressure taint before it could even be
# scheduled, THEN cold-pull its (uncached) image, took ~15 minutes total
# from a completely idle cluster - `kubectl wait` doesn't distinguish "not
# ready yet" from "will never be ready", so this timed out and aborted the
# whole script (`set -euo pipefail`) even though the pod finished starting
# on its own moments later. 600s covers a real cold pull + scheduling
# delay on a modest dev VM without masking an actual stuck pod for long -
# still fails loudly, just not on ordinary slowness.
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=onlyoffice-postgres -n "$NAMESPACE" --timeout=600s
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=onlyoffice-redis -n "$NAMESPACE" --timeout=600s
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=onlyoffice-rabbitmq -n "$NAMESPACE" --timeout=600s
# [CORRECTED] found by actually running this script: the chart's own
# `ds-files`/`ds-runtime-config` PVCs hardcode `accessModes:
# [ReadWriteMany]`, which k3d's `local-path` StorageClass cannot provision
# - see infra/k8s/manifests/dev/onlyoffice-storage.yaml's header for the
# full story. Applied before the release itself since the statically
# pre-provisioned PVCs it references via `persistence.existingClaim` must
# already exist.
kubectl apply -f infra/k8s/manifests/dev/onlyoffice-storage.yaml
helm_install onlyoffice onlyoffice/docs -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice.yaml -f infra/k8s/helm-values/dev/onlyoffice.yaml
# vikunja-postgres: the real go-vikunja/helm-chart `vikunja` chart has no
# bundled database of its own (defaults to SQLite) - see
# infra/k8s/helm-values/vikunja-postgres.yaml's header for the full story.
# Installed before `vikunja` itself since it depends on it by hostname.
helm_install vikunja-postgres bitnami/postgresql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/vikunja-postgres.yaml -f infra/k8s/helm-values/dev/vikunja-postgres.yaml
helm_install vikunja "$VIKUNJA_CHART" --version "$VIKUNJA_CHART_VERSION" -n "$NAMESPACE" \
  -f infra/k8s/helm-values/vikunja.yaml -f infra/k8s/helm-values/dev/vikunja.yaml
helm_install seaweedfs seaweedfs/seaweedfs -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seaweedfs.yaml -f infra/k8s/helm-values/dev/seaweedfs.yaml
helm_install peertube peertube-helm/peertube -n "$NAMESPACE" \
  -f infra/k8s/helm-values/peertube.yaml -f infra/k8s/helm-values/dev/peertube.yaml
# --skip-schema-validation: this chart's own bundled values.schema.json
# (every published version through 0.2.1, the one pinned here) has a real
# authoring bug - its "service" schema nests "required": ["type"] one
# level too deep, inside "properties" instead of alongside it, which makes
# "required" look like a property needing its own sub-schema instead of
# the JSON Schema "required" keyword. Helm validates the schema itself
# against the JSON Schema metaschema before even looking at our values, so
# this fails unconditionally regardless of what's in novu.yaml - found by
# actually running this script (helm-template-validate CI job's own run,
# then confirmed against the exact pinned tag's real values.schema.json on
# github.com/Nova-Edge/novu-chart). Not something a values file can work
# around.
helm_install novu "$NOVU_CHART" --version "$NOVU_CHART_VERSION" -n "$NAMESPACE" \
  --skip-schema-validation \
  -f infra/k8s/helm-values/novu.yaml -f infra/k8s/helm-values/dev/novu.yaml
helm_install external-dns external-dns/external-dns -n "$NAMESPACE" \
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
helm_install oauth2-proxy-onlyoffice oauth2-proxy/oauth2-proxy -n "$NAMESPACE" \
  -f infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml
helm_install oauth2-proxy-novu oauth2-proxy/oauth2-proxy -n "$NAMESPACE" \
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
