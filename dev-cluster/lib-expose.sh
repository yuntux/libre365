#!/usr/bin/env bash
# libre365 - chart-agnostic NodePort exposure for the k3d dev cluster.
#
# Why this exists: this sandboxed development context has no network access
# to charts.bitnami.com / ananace.gitlab.io / the other third-party chart
# repositories, so the exact Service port layout each chart produces
# (single port? named "http"? port 80 vs 8080?) could not be verified ahead
# of time by templating the real charts. Rather than guess a
# chart-specific `service.nodePorts.*` values key per brick (which could
# silently be wrong and fail at deploy time with no clear error), this
# script uses ONLY the generic, Helm-wide `app.kubernetes.io/instance` /
# `app.kubernetes.io/name` labels to find each release's Service after
# install, then patches it directly with `kubectl patch` to type=NodePort
# with an explicit nodePort matching platform.yaml - the same numbers
# already baked into dev-cluster/k3d-config.yaml's `ports:` list (the k3d
# load balancer forwards each of those host ports to the SAME port number
# on the cluster nodes, so the Service's nodePort must match exactly).
#
# Assumption to verify on first real run (not verifiable from this sandbox,
# no live cluster available here): each release's Service exposes its main
# HTTP port at array index 0, except the two 2-port bricks (synapse,
# minio) which are assumed to list their two ports in the same order as
# EXPOSE_MAP below. If a chart's Service instead nests the HTTP port at a
# different index (a different port comes first, e.g. a metrics port), the
# `replace` patch below will target the wrong port - inspect
# `kubectl get service <name> -n libre365 -o yaml` and adjust the index in
# EXPOSE_MAP accordingly.

# key: "<service-name>:<port-array-index>", value: nodePort (== platform.yaml port).
declare -A EXPOSE_MAP=(
  [keycloak:0]=8080
  [synapse:0]=8008
  [synapse:1]=8448
  [element-web:0]=8081
  [seafile:0]=8082
  [onlyoffice:0]=8083
  [vikunja:0]=3456
  [minio:0]=9000
  [minio:1]=9001
  [peertube:0]=9002
  # The Novu chart's naming convention for its per-component Services
  # (api/worker/ws/web) is a second unverified assumption on top of the
  # port-index one described above: "novu-api" follows the common
  # <release>-<subchart> pattern, not confirmed against a live template of
  # novuhq/helm-charts from this sandbox. Adjust with
  # `kubectl get services -n libre365 -l app.kubernetes.io/instance=novu`
  # if the real name differs.
  [novu-api:0]=13000
  [gokapi:0]=53842
  [caddy-dev:0]=10080
  [notification-hub:0]=4001
  [unified-search:0]=4002
  [presence-aggregator:0]=4003
  [onlyoffice-mentions:0]=4004
  [peertube-ingest:0]=4005
)

expose_service() {
  local svc="$1" idx="$2" nodeport="$3" ns="${4:-libre365}"

  if ! kubectl get service "$svc" -n "$ns" >/dev/null 2>&1; then
    echo "    ! service '$svc' not found in namespace '$ns' yet - skipping (rollout still in progress?)"
    return 0
  fi

  kubectl patch service "$svc" -n "$ns" -p '{"spec":{"type":"NodePort"}}' >/dev/null

  if ! kubectl patch service "$svc" -n "$ns" --type=json \
      -p="[{\"op\":\"replace\",\"path\":\"/spec/ports/${idx}/nodePort\",\"value\":${nodeport}}]" >/dev/null 2>&1; then
    echo "    ! failed to set nodePort=${nodeport} on ${svc}[${idx}] - does that port index exist? See lib-expose.sh header comment."
    return 1
  fi
  echo "    ${svc}[${idx}] -> NodePort ${nodeport}"
}

expose_all_services() {
  local failures=0
  for key in "${!EXPOSE_MAP[@]}"; do
    local svc="${key%%:*}" idx="${key##*:}" nodeport="${EXPOSE_MAP[$key]}"
    expose_service "$svc" "$idx" "$nodeport" || failures=$((failures + 1))
  done
  if [ "$failures" -gt 0 ]; then
    echo "    ${failures} service(s) could not be exposed - see messages above, safe to re-run this step alone once those pods/services exist."
  fi
}
