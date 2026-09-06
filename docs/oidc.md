# Keycloak OIDC coverage (study 1.7)

Study 1.7 says SSO via Keycloak has to be "checked service by service"
rather than assumed. This file is that check, kept current: which
components have a real, working OIDC chain today, which deliberately don't,
and how a future gap of the same shape gets caught automatically instead of
by another manual audit.

## What "a complete chain" means here

Every entry in `infra/ansible/roles/keycloak_realm/defaults/main.yml`'s
`keycloak_oidc_clients` is expected to be backed by three things, all
present, all consistent:

1. A Keycloak client definition (the realm entry itself).
2. The matching `client_id` configured on the application side, in its
   `infra/k8s/helm-values/*.yaml` (or `infra/k8s/manifests/gokapi.yaml`).
3. A real `ExternalSecret` in `infra/k8s/manifests/external-secrets.yaml`
   backing the client secret the application references — never a
   hardcoded or dangling `secretKeyRef`.

`scripts/sync_platform.py`'s `check_oidc_coverage()` enforces (2) and (3)
for every client declared in (1), unconditionally, on every run (`apply`
and `--check` alike) — see that function's docstring. It is covered by
offline unit tests in `scripts/test_sync_platform.py` that reproduce each
gap found below, so a regression of the same shape fails CI immediately
instead of waiting for another manual review.

## Audit findings and fixes

A full pass across every component in the stack found the following gaps,
all fixed on this branch:

| Component | Finding | Fix |
|---|---|---|
| **Gokapi** | `GOKAPI_OAUTH_CLIENT_ID` was set, but no `GOKAPI_OAUTH_CLIENT_SECRET` was ever wired to a real secret — no matching `ExternalSecret` existed at all. | Added `gokapi-oidc-secret` `ExternalSecret` (`infra/k8s/manifests/external-secrets.yaml`, sourced from `libre365/gokapi`/`oidc-client-secret` in OpenBao); `gokapi.yaml` already referenced it by name. |
| **Seafile** | `ENABLE_OAUTH`/`OAUTH_CLIENT_ID` were set with no `OAUTH_CLIENT_SECRET` at all — the OAuth token exchange could never complete. | Added `OAUTH_CLIENT_SECRET` (`secretKeyRef` → `seafile-oidc-secret`) to `seafile.yaml`, and the matching `ExternalSecret`. |
| **PeerTube** | The `openid_connect` plugin block had a `client_id` but no `client_secret` at all. | Added a `client_secret` block (`existingSecret: peertube-oidc-secret`) to `peertube.yaml`, and the matching `ExternalSecret`. **[UNCERTAIN]**: the community chart's exact field shape for injecting a Secret into a plugin setting isn't independently confirmed — see that file's own comment; verify against the real chart before deploying. |
| **Visio (LaSuite Meet)** | Full app-side OIDC config (`OIDC_RP_CLIENT_ID: "visio-meet"`, etc.) in `visio-meet.yaml`, but no `visio-meet` Keycloak client existed anywhere — the realm would reject every login attempt. | Added the `visio-meet` client to `keycloak_realm/defaults/main.yml` (redirect URI inferred from mozilla-django-oidc's default callback path, `/oidc/callback/` — LaSuite Meet is a Django app, per that file's env var naming convention; not independently confirmed against LaSuite Meet's own source), plus `visio-meet-oidc-secret`. |
| **Matrix / Synapse** | Two conflicting configs: the Helm chart's native `synapse.oidc` block used `client_id: "synapse"` (wrong, unused), while a separate Ansible-rendered ConfigMap (`playbooks/matrix.yml`) used the correct `client_id: "matrix-synapse"` — but that ConfigMap was never actually consumed by anything (`grep` for its name/`extraConfig` found no reference anywhere in the chart wiring). | Fixed `synapse.yaml`'s own `client_id` to `"matrix-synapse"` (matching the realm and `synapse-oidc-secret`, which was already correct); deleted the dead `playbooks/matrix.yml` and its template rather than reconciling two configs when only one was ever live. |
| **OnlyOffice Document Server** | Had a Keycloak client, but Community Edition has no standalone end-user login when embedded via a host app — it's reached exclusively via JWT-signed requests from Seafile (`onlyoffice-jwt-secret`, already correctly wired on both sides). The client had nothing that could ever use it. | Removed the `onlyoffice` Keycloak client — a modeling error, not a missing wire-up; inventing a login flow for it would misrepresent the architecture. |
| **Novu** | Had a Keycloak client, but the notification-center widget authenticates subscribers via an HMAC-signed subscriber hash derived from the API key, not OIDC — and Novu's own admin dashboard is not exposed publicly in this stack at all (no Caddy site, no domain). Corroborated by an existing comment already in `infra/k8s/helm-values/novu.yaml` itself: "Novu is not exposed directly to consultants as a standalone application, but integrated into the top bar". | Removed the `novu` Keycloak client for the same reason as OnlyOffice. |

## Components with no client — by design

- **Grommunio**: application SSO for `grommunio-web` is not treated as a
  priority by the study (the web admin UI stays disabled anyway, see
  `playbooks/grommunio.yml`) — left for future extension, not a gap.
- **Element Web / Element Call**: no client — both are Matrix clients that
  authenticate against Synapse (already OIDC-wired above), never against
  Keycloak directly.
- **MinIO**: no end-user login surface in this architecture (internal S3
  backend only) — no client needed.

## Automated regression coverage

- **Structural (offline, always-on)**: `scripts/sync_platform.py`'s
  `check_oidc_coverage()`, run unconditionally by every `sync_platform.py`
  invocation (including `--check`, i.e. CI). Its tests in
  `scripts/test_sync_platform.py` reproduce each finding above (a client
  with no app-side `client_id`, a `client_id` with no secret reference at
  all, a referenced secret with no matching `ExternalSecret`, and a client
  missing from the file-mapping itself) — this is what would have caught
  every one of these gaps automatically instead of requiring a manual
  audit.
- **Live end-to-end (`tests/integration/test_sso_e2e.py`)**: covers
  Seafile, Vikunja, Matrix, OnlyOffice, and Grommunio today — each of these
  accepts a Keycloak-issued bearer token directly against a protected API
  endpoint, which is what that test's generic "no token → rejected, token →
  accepted" pattern requires. Gokapi and PeerTube are **not** added to it:
  both delegate to Keycloak via a browser redirect that ends in an
  application-issued session/token of their own (Gokapi's native OIDC login
  page; PeerTube's `openid-connect` plugin exchanging the code for a
  PeerTube access token), not by accepting the Keycloak token itself as a
  bearer credential on their API — the same category `test_sso_e2e.py`'s
  own docstring already carves out for OnlyOffice/Grommunio's "broad,
  deliberately loose" codes. Writing a same-shape test for them without a
  live instance to confirm the exact redirect/session mechanics would risk
  the same kind of unverified assumption this audit was meant to close, so
  it's left as a documented follow-up rather than guessed. Visio (LaSuite
  Meet) is not wired into the local dev/test tier at all yet (no
  `platform.yaml` port/service entry — see that file's `visio` section),
  so there is no environment for `test_sso_e2e.py` to target either.
