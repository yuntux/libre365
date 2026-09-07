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
# Keycloak itself is NOT in this list: it's an Operator CR now, not a Helm
# release (see infra/k8s/manifests/keycloak.yaml) - iterate on it with
# `kubectl apply -f infra/k8s/manifests/dev/keycloak.yaml` (the dev-sized
# CR deploy.sh itself applies, not the production one), the same way as
# gokapi/caddy's raw manifests (also not covered by this script).
HELM_CHARTS=(keycloak-postgres synapse element-web seafile-mysql seafile-memcached seafile onlyoffice vikunja seaweedfs peertube novu external-dns openbao external-secrets)

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
  chart_version=""
  case "$target" in
    keycloak-postgres) chart="bitnami/postgresql" ;;
    synapse) chart="ananace-charts/matrix-synapse" ;;
    element-web) chart="ananace-charts/element-web" ;;
    seafile-mysql) chart="bitnami/mysql" ;;
    seafile-memcached) chart="bitnami/memcached" ;;
    seafile) chart="seafile-charts/ce" ;;
    onlyoffice) chart="onlyoffice/docs" ;;
    vikunja) chart="vikunja/vikunja" ;;
    seaweedfs) chart="seaweedfs/seaweedfs" ;;
    peertube) chart="peertube-helm/peertube" ;;
    # No official Novu chart exists at all (see deploy.sh's own comment) -
    # this is the community OCI chart, pinned by --version since OCI
    # references aren't resolved through a repo's own index like every
    # other chart here.
    novu) chart="oci://ghcr.io/nova-edge/charts/novu"; chart_version="0.2.1" ;;
    external-dns) chart="external-dns/external-dns" ;;
    openbao) chart="openbao/openbao" ;;
    external-secrets) chart="external-secrets/external-secrets" ;;
  esac
  if [ -n "$chart_version" ]; then
    helm upgrade --install "$target" "$chart" --version "$chart_version" -n "$NAMESPACE" -f "$base" -f "$dev_overlay"
  else
    helm upgrade --install "$target" "$chart" -n "$NAMESPACE" -f "$base" -f "$dev_overlay"
  fi
  echo "==> Force-deleting its pod(s) so the new values are picked up immediately"
  kubectl delete pod -n "$NAMESPACE" -l "app.kubernetes.io/instance=${target}" --grace-period=0 --force --ignore-not-found

else
  echo "Unknown target: '${target}'"
  usage
fi
