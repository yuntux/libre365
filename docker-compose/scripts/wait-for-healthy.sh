#!/usr/bin/env bash
# Attend que les services docker-compose declarant un healthcheck soient
# "healthy" (et fait un simple TCP-check pour ceux qui n'en declarent pas,
# ex. grommunio-dev - cf. commentaire dans docker-compose.yml), avant de
# lancer la suite tests/integration/ en CI (etude, chapitre 5.5).
#
# Usage:
#   ./scripts/wait-for-healthy.sh [timeout_seconds]
#
# A executer depuis le repertoire docker-compose/ (ou en lui passant
# COMPOSE_FILE/COMPOSE_PROJECT_NAME dans l'environnement).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${COMPOSE_DIR}"

TIMEOUT="${1:-600}"
INTERVAL=5
ELAPSED=0

# Services sans HEALTHCHECK Docker natif dans docker-compose.yml : verifies
# par un simple TCP-check sur le port publie plutot que par `docker compose
# ps` (qui les rapporterait toujours comme "running", pas "healthy").
declare -A TCP_ONLY_SERVICES=(
  [grommunio-dev]="${GROMMUNIO_DEV_HTTP_PORT:-8443}"
)

echo "==> Attente de la disponibilite de la stack libre365 (dev/test)..."

compose_services() {
  docker compose config --services
}

is_healthy_via_compose() {
  local service="$1"
  local cid
  cid="$(docker compose ps -q "${service}" 2>/dev/null || true)"
  if [ -z "${cid}" ]; then
    return 1
  fi
  local status
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "${cid}" 2>/dev/null || echo "unknown")"
  if [ "${status}" = "healthy" ]; then
    return 0
  fi
  if [ "${status}" = "no-healthcheck" ]; then
    # Pas de healthcheck declare pour ce service : on considere "running"
    # comme suffisant, sauf s'il figure dans TCP_ONLY_SERVICES ci-dessus.
    local running
    running="$(docker inspect --format '{{.State.Running}}' "${cid}" 2>/dev/null || echo "false")"
    [ "${running}" = "true" ]
    return $?
  fi
  return 1
}

is_tcp_open() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null
}

while true; do
  ALL_OK=true

  for service in $(compose_services); do
    if [ -n "${TCP_ONLY_SERVICES[${service}]:-}" ]; then
      if ! is_tcp_open "${TCP_ONLY_SERVICES[${service}]}"; then
        ALL_OK=false
        echo "  - ${service}: en attente (TCP:${TCP_ONLY_SERVICES[${service}]})"
      fi
      continue
    fi
    if ! is_healthy_via_compose "${service}"; then
      ALL_OK=false
      echo "  - ${service}: en attente"
    fi
  done

  if [ "${ALL_OK}" = "true" ]; then
    echo "==> Tous les services sont disponibles."
    exit 0
  fi

  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "==> Timeout (${TIMEOUT}s) atteint : la stack n'est pas entierement disponible." >&2
    docker compose ps >&2 || true
    exit 1
  fi

  sleep "${INTERVAL}"
  ELAPSED=$((ELAPSED + INTERVAL))
done
