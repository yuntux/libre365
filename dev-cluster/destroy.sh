#!/usr/bin/env bash
# libre365 - tear down the local k3d dev cluster entirely.
#
# This deletes the k3d cluster (all nodes, all in-cluster state - Postgres/
# MariaDB/MongoDB/SeaweedFS data included, since nothing here is backed by a
# persistent volume outside the cluster). grommunio-dev (docker-compose,
# not part of this cluster) is untouched - stop it separately with
# `docker compose -f dev-cluster/grommunio-dev/docker-compose.yml down` if needed.

set -euo pipefail

CLUSTER_NAME="libre365-dev"

if k3d cluster list -o json 2>/dev/null | grep -q "\"name\":\"${CLUSTER_NAME}\""; then
  k3d cluster delete "$CLUSTER_NAME"
else
  echo "cluster '${CLUSTER_NAME}' does not exist, nothing to do."
fi
