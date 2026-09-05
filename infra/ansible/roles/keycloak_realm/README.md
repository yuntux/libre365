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
