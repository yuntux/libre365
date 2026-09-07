#!/usr/bin/env bash
# libre365 - writes dev-only dummy values into OpenBao's dev-mode KV store
# at the exact paths/properties infra/k8s/manifests/external-secrets.yaml
# expects, so every chart that needs one of these Secrets can actually
# start in the k3d dev cluster (Keycloak, the Postgres-backed charts, etc.
# would otherwise get stuck trying to mount a Secret that doesn't exist).
#
# NEVER reuses these values anywhere real - they're arbitrary dev-only
# strings, the same spirit as dev-cluster/grommunio-dev/.env.example's
# "devonly-changeme-*" passwords. See dev-cluster/README.md, "Testing
# secret propagation", for what this validates (and what it doesn't: OVH
# credentials get a dummy value here too, since nothing calls the real OVH
# API from a "libre365-dev" domain in this test - see
# check-external-dns.sh for that separate concern).

set -euo pipefail

NAMESPACE="libre365"

# Chart-agnostic pod discovery (app.kubernetes.io/instance=<release name>),
# same convention already used by lib-expose.sh - not independently
# verified against a live openbao-helm chart template from this sandboxed
# environment (see infra/k8s/helm-values/openbao.yaml's own caveat).
OPENBAO_POD="$(kubectl get pod -n "$NAMESPACE" -l app.kubernetes.io/instance=openbao -o jsonpath='{.items[0].metadata.name}')"

bao_kv_put() {
  local path="$1"
  shift
  kubectl exec -n "$NAMESPACE" "$OPENBAO_POD" -- \
    env VAULT_TOKEN=libre365-dev-root-token VAULT_ADDR=http://127.0.0.1:8200 \
    bao kv put "secret/${path}" "$@" >/dev/null
  echo "    seeded secret/${path}"
}

echo "==> Seeding dev-only dummy secrets into OpenBao ($OPENBAO_POD)"

bao_kv_put "libre365/synapse" oidc-client-secret=devonly-changeme-synapse-oidc
bao_kv_put "libre365/vikunja" oidc-client-secret=devonly-changeme-vikunja-oidc
# [ADDED] found live on a user's VM: oauth2-proxy-onlyoffice/-novu and
# gokapi's own init container all crash-looped with "secret ... not
# found" - external-secrets.yaml's onlyoffice-oidc-secret/novu-oidc-secret/
# gokapi-oidc-secret ExternalSecrets were never seeded here at all,
# unlike synapse/vikunja/seafile's own oidc-client-secret above. Same
# known limitation as those three: this dummy value won't match
# Keycloak's own auto-generated client secret (infra/ansible/roles/
# keycloak_realm never sets an explicit client_secret - see that role's
# own "Retrieve the generated secret" task), so the real OIDC login flow
# still won't authenticate end-to-end - out of scope to fix here, this
# only unblocks the pods from crash-looping on Secret creation.
bao_kv_put "libre365/gokapi" oidc-client-secret=devonly-changeme-gokapi-oidc
# oauth2-proxy validates its own cookie secret strictly (must decode to
# 16/24/32 raw bytes) - a free-text "devonly-changeme-*" string like the
# rest of this file uses would crash the container with a DIFFERENT
# error ("cookie_secret must be 16, 24, or 32 bytes"). base64 of a
# 32-byte string instead, still an obviously-fake dev-only value.
bao_kv_put "libre365/onlyoffice" \
  jwt-secret=devonly-changeme-onlyoffice-jwt \
  oidc-client-id=onlyoffice \
  oidc-client-secret=devonly-changeme-onlyoffice-oidc \
  oauth2-proxy-cookie-secret=ZGV2b25seS1vbmx5b2ZmaWNlLWNvb2tpZS0zMmJ5dGU=
bao_kv_put "libre365/onlyoffice-postgres" password=devonly-changeme-onlyoffice-pg postgres-password=devonly-changeme-onlyoffice-pg-super
bao_kv_put "libre365/external-dns-ovh" \
  application-key=devonly-changeme-ovh-app-key \
  application-secret=devonly-changeme-ovh-app-secret \
  consumer-key=devonly-changeme-ovh-consumer-key
bao_kv_put "libre365/keycloak" admin-username=admin admin-password=devonly-changeme-keycloak-admin
bao_kv_put "libre365/keycloak-postgres" username=keycloak password=devonly-changeme-kc-pg postgres-password=devonly-changeme-kc-pg-super
bao_kv_put "libre365/synapse-postgres" password=devonly-changeme-synapse-pg postgres-password=devonly-changeme-synapse-pg-super
bao_kv_put "libre365/vikunja-postgres" password=devonly-changeme-vikunja-pg postgres-password=devonly-changeme-vikunja-pg-super
bao_kv_put "libre365/peertube-postgres" password=devonly-changeme-peertube-pg postgres-password=devonly-changeme-peertube-pg-super
bao_kv_put "libre365/visio-meet-postgres" password=devonly-changeme-visio-pg postgres-password=devonly-changeme-visio-pg-super
bao_kv_put "libre365/onlyoffice-redis" password=devonly-changeme-onlyoffice-redis
bao_kv_put "libre365/onlyoffice-rabbitmq" password=devonly-changeme-onlyoffice-rabbitmq
bao_kv_put "libre365/novu-mongodb" root-password=devonly-changeme-novu-mongo
bao_kv_put "libre365/novu" \
  api-key=devonly-changeme-novu-api-key \
  oidc-client-id=novu \
  oidc-client-secret=devonly-changeme-novu-oidc \
  oauth2-proxy-cookie-secret=ZGV2b25seS1ub3Z1LWNvb2tpZS1zZWNyZXQtMzJieXQ=
bao_kv_put "libre365/seaweedfs" s3-access-key=devonly-seaweedfs-access s3-secret-key=devonly-changeme-seaweedfs-secret admin-user=admin admin-password=devonly-changeme-seaweedfs-admin
# [CORRECTED] "password" alone used to be the only property here, a guess
# later found wrong by actually running dev-cluster/deploy.sh - the real
# seafile-mysql-secret/seafile-secret ExternalSecrets (external-secrets.yaml)
# need all 3 bitnami/mysql key names, plus a separate libre365/seafile path
# for Seafile's own non-MySQL credentials (see that file's own comments).
bao_kv_put "libre365/seafile-mysql" \
  root-password=devonly-changeme-seafile-mysql-root \
  password=devonly-changeme-seafile-mysql \
  replication-password=devonly-changeme-seafile-mysql-repl
bao_kv_put "libre365/seafile" \
  oidc-client-secret=devonly-changeme-seafile-oidc \
  jwt-private-key=devonly-changeme-seafile-jwt \
  admin-password=devonly-changeme-seafile-admin

echo "==> Done. External Secrets Operator should sync these into real Secrets within its next poll interval."
