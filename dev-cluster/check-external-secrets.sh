#!/usr/bin/env bash
# libre365 - verify External Secrets Operator actually created a real
# Kubernetes Secret (with the expected key) for every ExternalSecret in
# infra/k8s/manifests/external-secrets.yaml, after
# ./seed-openbao-dev-secrets.sh populated OpenBao's dev-mode KV store.
#
# This validates the OpenBao -> ESO -> Kubernetes Secret path end to end
# in the k3d dev cluster. It does NOT validate the [CONVENTION]/
# [UNCERTAIN] secretKey names against the real third-party charts
# themselves (that can only be confirmed by actually deploying that exact
# chart - see infra/k8s/manifests/external-secrets.yaml's own confidence
# grading) - only that the Secret this repo asked for gets created with
# the key this repo asked for.

set -euo pipefail

NAMESPACE="libre365"

# secret-name:key pairs, one per ExternalSecret target in
# infra/k8s/manifests/external-secrets.yaml.
EXPECTED="
synapse-oidc-secret:client-secret
vikunja-oidc-secret:client-secret
onlyoffice-jwt-secret:secret
external-dns-ovh-credentials:application-key
external-dns-ovh-credentials:application-secret
external-dns-ovh-credentials:consumer-key
keycloak-admin-secret:admin-password
keycloak-postgres-secret:password
keycloak-postgres-secret:postgres-password
synapse-postgres-secret:password
synapse-postgres-secret:postgres-password
vikunja-postgres-secret:password
vikunja-postgres-secret:postgres-password
peertube-postgres-secret:password
peertube-postgres-secret:postgres-password
visio-meet-postgres-secret:password
visio-meet-postgres-secret:postgres-password
onlyoffice-redis-secret:redis-password
novu-mongodb-secret:mongodb-root-password
minio-root-credentials:rootUser
minio-root-credentials:rootPassword
seafile-mysql-secret:password
"

echo "==> Waiting for External Secrets Operator to be ready"
kubectl rollout status deployment/external-secrets -n "$NAMESPACE" --timeout=120s

echo "==> Waiting for the first sync pass"
sleep 15 # ESO's default refreshInterval on an ExternalSecret with none set
         # is 1h - but its FIRST sync after creation happens immediately;
         # this just gives that initial reconcile a moment to complete.

failures=0
for entry in $EXPECTED; do
  secret="${entry%%:*}"
  key="${entry##*:}"
  if kubectl get secret "$secret" -n "$NAMESPACE" -o jsonpath="{.data.${key}}" 2>/dev/null | grep -q .; then
    echo "    OK   ${secret}[${key}]"
  else
    echo "    MISSING   ${secret}[${key}]"
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  echo
  echo "==> $failures secret key(s) missing - showing the ExternalSecret resources' status for context:"
  kubectl get externalsecret -n "$NAMESPACE" -o wide
  exit 1
fi

echo
echo "All expected Secrets/keys were created by External Secrets Operator from OpenBao."
