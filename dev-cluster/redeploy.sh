#!/usr/bin/env bash
# libre365 - fast single-brick iteration for the k3d dev cluster.
#
# The whole point of hardening this cluster for dev speed is to make the
# edit/rebuild/observe loop fast for the ONE thing being worked on right
# now, without re-running deploy.sh's full 8-chart install. Two modes:
#
#   dev-cluster/redeploy.sh <connector-name>
#     Rebuilds one connector's Docker image, re-imports it into k3d, and
#     force-deletes its pod so the Deployment immediately recreates it with
#     the fresh image (--grace-period=0 --force: no graceful shutdown wait,
#     this is a dev inner loop, not a production rollout).
#
#   dev-cluster/redeploy.sh <helm-release-name>
#     Re-runs `helm upgrade` for that one release (base + dev overlay), then
#     force-deletes its pod(s) the same way, for the case where you changed
#     an infra/k8s/helm-values/*.yaml file rather than connector code.
#
# This script deliberately does NOT touch NodePort exposure (dev-cluster/
# lib-expose.sh) - a pod restart never changes its Service, so re-running
# that step here would just be wasted work on every iteration.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

NAMESPACE="libre365"
CLUSTER_NAME="libre365-dev"
CONNECTORS=(notification-hub unified-search presence-aggregator onlyoffice-mentions peertube-ingest)
HELM_CHARTS=(keycloak synapse element-web seafile onlyoffice vikunja minio peertube novu external-dns openbao external-secrets)

usage() {
  echo "Usage: $0 <connector-name|helm-release-name>"
  echo "  Connectors:   ${CONNECTORS[*]}"
  echo "  Helm releases: ${HELM_CHARTS[*]}"
  exit 1
}

[ $# -eq 1 ] || usage
target="$1"

is_in() { local needle="$1"; shift; for x in "$@"; do [ "$x" = "$needle" ] && return 0; done; return 1; }

if is_in "$target" "${CONNECTORS[@]}"; then
  echo "==> Rebuilding connector '${target}'"
  docker build -t "libre365/${target}:dev" "connectors/${target}"
  k3d image import "libre365/${target}:dev" -c "$CLUSTER_NAME"
  echo "==> Force-deleting its pod(s) for an immediate restart"
  kubectl delete pod -n "$NAMESPACE" -l "app.kubernetes.io/name=${target}" --grace-period=0 --force --ignore-not-found

elif is_in "$target" "${HELM_CHARTS[@]}"; then
  echo "==> helm upgrade for release '${target}' (base + dev overlay)"
  base="infra/k8s/helm-values/${target}.yaml"
  dev_overlay="infra/k8s/helm-values/dev/${target}.yaml"
  chart=""
  case "$target" in
    keycloak) chart="bitnami/keycloak" ;;
    synapse) chart="ananace-charts/matrix-synapse" ;;
    element-web) chart="ananace-charts/matrix-element-web" ;;
    seafile) chart="seafile-charts/seafile-ce" ;;
    onlyoffice) chart="onlyoffice/docs-cloud" ;;
    vikunja) chart="vikunja/vikunja" ;;
    minio) chart="minio/minio" ;;
    peertube) chart="peertube-helm/peertube" ;;
    novu) chart="novu/novu" ;;
    external-dns) chart="external-dns/external-dns" ;;
    openbao) chart="openbao/openbao" ;;
    external-secrets) chart="external-secrets/external-secrets" ;;
  esac
  helm upgrade --install "$target" "$chart" -n "$NAMESPACE" -f "$base" -f "$dev_overlay"
  echo "==> Force-deleting its pod(s) so the new values are picked up immediately"
  kubectl delete pod -n "$NAMESPACE" -l "app.kubernetes.io/instance=${target}" --grace-period=0 --force --ignore-not-found

else
  echo "Unknown target: '${target}'"
  usage
fi
