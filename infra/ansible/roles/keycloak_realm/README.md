# `keycloak_realm` role

Creates the firm's main Keycloak realm, natively enables TOTP and
WebAuthn/FIDO2 (study 1.7), and creates one confidential OIDC client per
stack component that natively supports OIDC.

Serves as the **reference convention** for the structure of subsequent roles
in this repository (`tasks/`, `defaults/`, `templates/`, `handlers/`) — roles
to be added for the other components (Seafile, Vikunja, OnlyOffice, Matrix,
etc., once they are extracted from the playbooks into dedicated roles) should
reuse this same structure rather than an ad hoc pattern per component.

## Main variables (`defaults/main.yml`)

- `keycloak_realm_name`, `keycloak_realm_display_name`
- `keycloak_realm_webauthn_enabled` — enables WebAuthn/passwordless in the
  browser flow (1.7: "both as a second factor and as a primary
  passwordless factor")
- `keycloak_oidc_clients` — list of OIDC clients to create (one per
  OIDC-compatible component; Grommunio is deliberately absent from it, see
  the comment in the file)
- `keycloak_realm_test_user_enabled` (default `false`) — creates the
  representative test user (study 4.4, point 2) that every scenario in
  `tests/integration/` and the ephemeral staging workflow log in as.
  **OFF by default and never turned on by `site.yml`** (the production
  playbook): a fake "consultant" account has no reason to exist in a real
  production realm. Only `dev-cluster/provision-keycloak-dev.sh` and
  `.github/workflows/ephemeral-staging.yml` pass
  `-e keycloak_realm_test_user_enabled=true` explicitly, alongside
  `-e keycloak_realm_test_user_password=...` (no default - always supplied
  explicitly, the same convention as `keycloak_admin_password`).
  Username/email come from `platform.yaml`'s `test_dataset` (single
  source, also read by `tests/integration/_platform_defaults.py`).

## Not covered by this role

- **OTP via SMS and email**: the study (1.7, lines ~266-268) is explicit —
  these two channels "are not natively covered by Keycloak" and require a
  custom Keycloak SPI, treated as a development project of its own, not an
  option of this role.
- **High availability of the Keycloak cluster** (nodes, distributed cache):
  handled by the Helm manifests (`infra/k8s/helm-values/keycloak.yaml`, out
  of scope for this task), not by this application configuration role.

## Secrets

The generated client secrets are written on the Ansible controller under
`infra/ansible/secrets/keycloak-clients/<client_id>.env` (a directory to
exclude from version control) — to be transferred to the secrets vault
adopted by the firm (study 4.5), never left in plaintext in the repository.
