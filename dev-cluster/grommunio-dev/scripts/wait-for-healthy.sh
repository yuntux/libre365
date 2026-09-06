#!/usr/bin/env bash
# Waits for docker-compose services declaring a healthcheck to become
# "healthy" (and does a simple TCP check for those that don't declare one,
# e.g. grommunio-dev - see comment in docker-compose.yml), before running
# the tests/integration/ suite in CI (study, chapter 5.5).
#
# Usage:
#   ./scripts/wait-for-healthy.sh [timeout_seconds]
#
# To be run from the docker-compose/ directory (or by passing
# COMPOSE_FILE/COMPOSE_PROJECT_NAME in the environment).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${COMPOSE_DIR}"

TIMEOUT="${1:-600}"
INTERVAL=5
ELAPSED=0

# Services with no native Docker HEALTHCHECK in docker-compose.yml: checked
# with a simple TCP check on the published port rather than via `docker
# compose ps` (which would always report them as "running", not "healthy").
declare -A TCP_ONLY_SERVICES=(
  [grommunio-dev]="${GROMMUNIO_DEV_HTTP_PORT:-8443}"
)

echo "==> Waiting for the libre365 stack (dev/test) to become available..."

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
    # No healthcheck declared for this service: "running" is considered
    # sufficient, unless it appears in TCP_ONLY_SERVICES above.
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
        echo "  - ${service}: waiting (TCP:${TCP_ONLY_SERVICES[${service}]})"
      fi
      continue
    fi
    if ! is_healthy_via_compose "${service}"; then
      ALL_OK=false
      echo "  - ${service}: waiting"
    fi
  done

  if [ "${ALL_OK}" = "true" ]; then
    echo "==> All services are available."
    exit 0
  fi

  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "==> Timeout (${TIMEOUT}s) reached: the stack is not fully available." >&2
    docker compose ps >&2 || true
    exit 1
  fi

  sleep "${INTERVAL}"
  ELAPSED=$((ELAPSED + INTERVAL))
done
