#!/usr/bin/env bash
# libre365 - bring up the local k3d dev cluster, reusing the production Helm
# charts/values (infra/k8s/helm-values/) and raw manifests
# (infra/k8s/manifests/), with the dev-speed hardening overlays
# (infra/k8s/helm-values/dev/) layered on top. See dev-cluster/README.md for
# the full rationale (why k3d over docker-compose here, why grommunio-dev
# stays on docker-compose, what "durcir en dev" means concretely).
#
# Requires: k3d, kubectl, helm, docker (to build the connector images), all
# on PATH. Idempotent: safe to re-run (helm upgrade --install, kubectl apply,
# cluster creation skipped if the cluster already exists).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLUSTER_NAME="libre365-dev"
NAMESPACE="libre365"
CONNECTORS=(notification-hub unified-search presence-aggregator onlyoffice-mentions peertube-ingest)

echo "==> 1/8 k3d cluster"
if k3d cluster list -o json 2>/dev/null | grep -q "\"name\":\"${CLUSTER_NAME}\""; then
  echo "    cluster '${CLUSTER_NAME}' already exists, skipping creation."
else
  k3d cluster create --config dev-cluster/k3d-config.yaml
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

echo "==> 2/8 namespace"
kubectl apply -f infra/k8s/manifests/namespace.yaml

echo "==> 3/8 Helm repos (see infra/k8s/helm-values/README.md)"
helm repo add ananace-charts https://ananace.gitlab.io/charts >/dev/null
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null
helm repo add minio https://charts.min.io/ >/dev/null
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
helm repo update >/dev/null

echo "==> 4/8 Secrets: OpenBao + External Secrets Operator (dev mode, study 4.5)"
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

echo "==> 5/8 Helm releases (production values + dev/ hardening overlay, NOT the -100/-2000 sizing overlays)"
helm upgrade --install keycloak bitnami/keycloak -n "$NAMESPACE" \
  -f infra/k8s/helm-values/keycloak.yaml -f infra/k8s/helm-values/dev/keycloak.yaml
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
helm upgrade --install minio minio/minio -n "$NAMESPACE" \
  -f infra/k8s/helm-values/minio.yaml -f infra/k8s/helm-values/dev/minio.yaml
helm upgrade --install peertube peertube-helm/peertube -n "$NAMESPACE" \
  -f infra/k8s/helm-values/peertube.yaml -f infra/k8s/helm-values/dev/peertube.yaml
helm upgrade --install novu novu/novu -n "$NAMESPACE" \
  -f infra/k8s/helm-values/novu.yaml -f infra/k8s/helm-values/dev/novu.yaml
helm upgrade --install external-dns external-dns/external-dns -n "$NAMESPACE" \
  -f infra/k8s/helm-values/external-dns.yaml -f infra/k8s/helm-values/dev/external-dns.yaml

echo "==> 6/8 In-house connectors: build + import images, apply manifests"
for name in "${CONNECTORS[@]}"; do
  echo "    building libre365/${name}:dev"
  docker build -t "libre365/${name}:dev" "connectors/${name}"
  k3d image import "libre365/${name}:dev" -c "$CLUSTER_NAME"
done
kubectl apply -f infra/k8s/manifests/connectors/
kubectl apply -f infra/k8s/manifests/gokapi.yaml
kubectl apply -f infra/k8s/manifests/dev/caddy.yaml

echo "==> 7/8 Production caddy.yaml's Service (for external-dns testing only)"
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

echo "==> 8/8 Exposing services as NodePort (matching platform.yaml's port numbers)"
source "$(dirname "${BASH_SOURCE[0]}")/lib-expose.sh"
expose_all_services

cat <<'EOF'

Dev cluster ready. Services are reachable on localhost at the same ports
already used by docker-compose (see platform.yaml / dev-cluster/README.md).
Run `kubectl get pods -n libre365` to watch rollout status - some charts
(Keycloak, Synapse, OnlyOffice) take a minute or two to become ready even in
the hardened dev configuration.

grommunio-dev is NOT part of this cluster - start it separately with
`docker compose -f dev-cluster/grommunio-dev/docker-compose.yml up -d`.
EOF
