#!/usr/bin/env bash
# libre365 - provisions the k3d dev cluster's Keycloak: the "libre365"
# realm, every OIDC client (infra/ansible/roles/keycloak_realm), AND the
# representative test user (study 4.4, point 2) that
# tests/integration/conftest.py and every scenario in that suite log in
# as.
#
# Why this exists (see docs/ next to this file / infra/ansible/roles/
# keycloak_realm/README.md for the full story): the same Ansible role
# already does this for a real deployment (infra/ansible/site.yml), but
# nothing wired it into the k3d dev cluster at all - Keycloak came up with
# only its default "master" realm, no "libre365" realm, no OIDC clients,
# and certainly no test user. Every OIDC/SSO integration test would fail
# for a reason that had nothing to do with what it was actually testing.
#
# Runs the REAL role (not a dev-only duplicate) with two dev-specific
# overrides:
#   - `keycloak_base_url=http://localhost:8080`: the role's default
#     (`https://sso.<domain>`) requires the domain-routing/CoreDNS setup
#     documented in dev-cluster/README.md's "Testing Keycloak SSO/OIDC
#     end-to-end" AND real TLS, neither needed just to talk to the admin
#     REST API directly via the exposed NodePort.
#   - `keycloak_realm_test_user_enabled=true`: OFF by default (see that
#     var's own comment in the role) - turned on explicitly here, and only
#     here / in the CI ephemeral-staging workflow, never in
#     infra/ansible/site.yml (the production playbook).
#
# Idempotent (community.general.keycloak_* modules are natively
# idempotent, per the role's own header comment) - safe to re-run.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

NAMESPACE="${1:-libre365}"
KEYCLOAK_ADMIN_PASSWORD="devonly-changeme-keycloak-admin"   # matches seed-openbao-dev-secrets.sh
TEST_USER_PASSWORD="devonly-changeme-test-user"              # matches TEST_USER_PASSWORD's dev default (see tests/integration/README.md); override with -e if you changed it

echo "Waiting for Keycloak's admin REST API to answer..."
i=0
while [ "$i" -lt 60 ]; do
  if curl -sf "http://127.0.0.1:8080/realms/master/.well-known/openid-configuration" > /dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 5
done

cd infra/ansible
ansible-playbook -i inventory/hosts.ini.example playbooks/keycloak-realm.yml \
  -e "keycloak_base_url=http://localhost:8080" \
  -e "vault_keycloak_admin_password=${KEYCLOAK_ADMIN_PASSWORD}" \
  -e "keycloak_realm_test_user_enabled=true" \
  -e "keycloak_realm_test_user_password=${TEST_USER_PASSWORD}"

echo "Keycloak realm + OIDC clients + test user (${NAMESPACE}) provisioned."
