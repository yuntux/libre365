#!/usr/bin/env bash
# libre365 - extracts caddy-dev's own internal CA root certificate
# (Caddy's `local_certs` global option, see infra/k8s/manifests/dev/
# caddy.yaml's own header comment) and publishes it as a ConfigMap
# ("caddy-dev-ca", key "ca.crt") any pod in the namespace can mount, so it
# can trust HTTPS connections to *.{{ domains.base }} the same way it
# would trust a real, publicly-issued certificate in production.
#
# Why this is needed at all: every OIDC config in this repo (Keycloak,
# oauth2-proxy, Vikunja, Synapse...) hits "https://<domain>" unconditionally
# - dev and production alike (see docs/oidc.md) - and in the k3d dev
# cluster that domain resolves to caddy-dev (see patch-coredns-hosts.sh),
# which now really does terminate TLS there (see dev/caddy.yaml). Its
# certificate is signed by Caddy's own internal CA though, not a
# publicly-trusted one, so a pod's default system trust store has no
# reason to accept it. oauth2-proxy has its own `--ssl-insecure-skip-verify`
# flag for this (see infra/k8s/helm-values/dev/oauth2-proxy-*.yaml); found
# live on a user's VM that Gokapi (gokapi.yaml) has no such flag at all
# (checked Gokapi's own docs/advanced.rst - no OAuth/TLS-related env var
# exists), so its OIDC discovery call needs a real CA it can actually
# trust instead - this script is what supplies it.
#
# Idempotent: overwrites the existing ConfigMap with the current CA cert
# on every re-run (a no-op once caddy-dev's own persistent volume - see
# dev/caddy.yaml's own comment - keeps that CA stable across restarts).
#
# Unverified from this sandboxed environment (no live k3d cluster
# available here to actually run this against): the exact path Caddy's
# official Docker image stores its internal CA root certificate at
# (`/data/caddy/pki/authorities/local/root.crt`, per Caddy's own
# documentation/community reports) - confirm with
# `kubectl exec deploy/caddy-dev -n <namespace> -- find /data/caddy/pki`
# if a future Caddy version changes this layout.

set -euo pipefail

NAMESPACE="${1:-libre365}"
CA_CERT_PATH="/data/caddy/pki/authorities/local/root.crt"

echo "==> Waiting for caddy-dev's internal CA certificate to exist..."
i=0
until kubectl exec -n "$NAMESPACE" deployment/caddy-dev -- test -f "$CA_CERT_PATH" 2>/dev/null; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "    ! caddy-dev never generated ${CA_CERT_PATH} - has it received at least one HTTPS request yet (Caddy generates its internal CA lazily, on first use of automatic HTTPS)?" >&2
    exit 1
  fi
  sleep 2
done

CA_CERT=$(kubectl exec -n "$NAMESPACE" deployment/caddy-dev -- cat "$CA_CERT_PATH")

kubectl create configmap caddy-dev-ca -n "$NAMESPACE" \
  --from-literal=ca.crt="$CA_CERT" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Published caddy-dev's internal CA as configmap/caddy-dev-ca (key ca.crt) in namespace ${NAMESPACE}"
