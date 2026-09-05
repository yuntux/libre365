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

echo "==> 1/6 k3d cluster"
if k3d cluster list -o json 2>/dev/null | grep -q "\"name\":\"${CLUSTER_NAME}\""; then
  echo "    cluster '${CLUSTER_NAME}' already exists, skipping creation."
else
  k3d cluster create --config dev-cluster/k3d-config.yaml
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

echo "==> 2/6 namespace"
kubectl apply -f infra/k8s/manifests/namespace.yaml

echo "==> 3/6 Helm repos (see infra/k8s/helm-values/README.md)"
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
helm repo update >/dev/null

echo "==> 4/6 Helm releases (production values + dev/ hardening overlay, NOT the -100/-2000 sizing overlays)"
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

echo "==> 5/6 In-house connectors: build + import images, apply manifests"
for name in "${CONNECTORS[@]}"; do
  echo "    building libre365/${name}:dev"
  docker build -t "libre365/${name}:dev" "connectors/${name}"
  k3d image import "libre365/${name}:dev" -c "$CLUSTER_NAME"
done
kubectl apply -f infra/k8s/manifests/connectors/
kubectl apply -f infra/k8s/manifests/gokapi.yaml
kubectl apply -f infra/k8s/manifests/dev/caddy.yaml

echo "==> 6/6 Exposing services as NodePort (matching platform.yaml's port numbers)"
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
