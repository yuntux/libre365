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
# Keep in sync by hand with platform.yaml's services.keycloak.version -
# scripts/sync_platform.py patches infra/k8s/manifests/keycloak.yaml's
# `spec.image` tag, but not this shell variable (see that file's header
# comment on why the operator install isn't automated the same way).
KEYCLOAK_VERSION="26.7.3"

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
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
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
if [ ! -f dev-cluster/grommunio-dev/.env ]; then
  cp dev-cluster/grommunio-dev/.env.example dev-cluster/grommunio-dev/.env
fi
docker compose -f dev-cluster/grommunio-dev/docker-compose.yml up -d
dev-cluster/grommunio-dev/scripts/wait-for-healthy.sh

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
helm repo add novu https://novuhq.github.io/helm-charts >/dev/null
# seafile-charts/onlyoffice/peertube-helm repos are marked "to be confirmed"
# in infra/k8s/helm-values/README.md (no single identified official chart at
# the time of writing) - added best-effort here; if a repo add fails because
# the chart moved, this script keeps going (`|| true`) rather than blocking
# the whole dev tier on one unresolved brick, but that brick's
# `helm upgrade --install` a few lines below will then fail loudly, which is
# the correct behavior (fail on the actual missing chart, not silently skip).
helm repo add seafile-charts https://seafile-charts.github.io/seafile-charts >/dev/null || true
helm repo add onlyoffice https://onlyoffice.github.io/docs-cloud-chart >/dev/null || true
helm repo add peertube-helm https://peertube-helm.github.io/charts >/dev/null || true
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
kubectl rollout status deployment/openbao -n "$NAMESPACE" --timeout=120s 2>/dev/null || \
  kubectl rollout status statefulset/openbao -n "$NAMESPACE" --timeout=120s
kubectl apply -f infra/k8s/manifests/dev/external-secrets-store.yaml
kubectl apply -f infra/k8s/manifests/external-secrets.yaml
./dev-cluster/seed-openbao-dev-secrets.sh

echo "==> 8/14 Helm releases (production values + dev/ hardening overlay, NOT the -100/-2000 sizing overlays)"
helm upgrade --install keycloak-postgres bitnami/postgresql -n "$NAMESPACE" \
  -f infra/k8s/helm-values/keycloak-postgres.yaml -f infra/k8s/helm-values/dev/keycloak-postgres.yaml
helm upgrade --install synapse ananace-charts/matrix-synapse -n "$NAMESPACE" \
  -f infra/k8s/helm-values/synapse.yaml -f infra/k8s/helm-values/dev/synapse.yaml
helm upgrade --install element-web ananace-charts/matrix-element-web -n "$NAMESPACE" \
  -f infra/k8s/helm-values/element-web.yaml -f infra/k8s/helm-values/dev/element-web.yaml
helm upgrade --install seafile seafile-charts/seafile-ce -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seafile.yaml -f infra/k8s/helm-values/dev/seafile.yaml
helm upgrade --install onlyoffice onlyoffice/docs-cloud -n "$NAMESPACE" \
  -f infra/k8s/helm-values/onlyoffice.yaml -f infra/k8s/helm-values/dev/onlyoffice.yaml
helm upgrade --install vikunja vikunja/vikunja -n "$NAMESPACE" \
  -f infra/k8s/helm-values/vikunja.yaml -f infra/k8s/helm-values/dev/vikunja.yaml
helm upgrade --install seaweedfs seaweedfs/seaweedfs -n "$NAMESPACE" \
  -f infra/k8s/helm-values/seaweedfs.yaml -f infra/k8s/helm-values/dev/seaweedfs.yaml
helm upgrade --install peertube peertube-helm/peertube -n "$NAMESPACE" \
  -f infra/k8s/helm-values/peertube.yaml -f infra/k8s/helm-values/dev/peertube.yaml
helm upgrade --install novu novu/novu -n "$NAMESPACE" \
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
